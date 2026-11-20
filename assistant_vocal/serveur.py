"""Serveur web local : sert l'interface et expose l'API utilisée par la page."""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from .config import Config
from .ia import CATEGORIES, IA, ErreurIA

STATIQUE = Path(__file__).parent / "static"
log = logging.getLogger("assistant_vocal")


def creer_app(cfg: Config, source=None, ia: IA | None = None) -> Flask:
    if source is None:
        if cfg.demo:
            from .demo import Demo
            source = Demo()
        else:
            from .google_services import Google
            source = Google(cfg)
    ia = ia or IA(cfg)
    app = Flask(__name__, static_folder=None)
    etat = {"mails": [], "analyse": None, "agenda": []}
    verrou = threading.Lock()

    def erreur(message: str, code: int = 500):
        return jsonify({"erreur": message}), code

    @app.get("/")
    def accueil():
        return send_from_directory(STATIQUE, "index.html")

    @app.get("/static/<path:fichier>")
    def statique(fichier):
        return send_from_directory(STATIQUE, fichier)

    @app.get("/api/etat")
    def api_etat():
        return jsonify({
            "nom": cfg.nom,
            "utilisateur": cfg.utilisateur,
            "demo": cfg.demo,
            "ia": cfg.ia_active,
            "voix_premium": cfg.voix_premium,
            "ecoute_serveur": bool(cfg.elevenlabs_cle),
            "categories": CATEGORIES,
            "heure": datetime.now().astimezone().isoformat(),
        })

    @app.get("/api/mails")
    def api_mails():
        try:
            mails = source.mails_non_lus(cfg.max_mails)
            analyse = ia.trier_mails(mails)
        except ErreurIA as e:
            return erreur(str(e), 502)
        except Exception as e:  # Google indisponible, jeton expiré…
            log.exception("Lecture des mails impossible")
            return erreur(f"Lecture des mails impossible : {e}")
        with verrou:
            etat["mails"], etat["analyse"] = mails, analyse
        par_id = {a["id"]: a for a in analyse["mails"]}
        liste = []
        for m in mails:
            a = par_id.get(m["id"], {})
            liste.append({
                "id": m["id"], "de": m["de"], "objet": m["objet"], "date": m["date"],
                "extrait": m["extrait"], "resume": a.get("resume", m["extrait"]),
                "categorie": a.get("categorie", "À lire"), "action": a.get("action", "garder"),
                "raison": a.get("raison", ""), "boite": m.get("boite", ""),
            })
        return jsonify({"resume_oral": analyse["resume_oral"], "mails": liste,
                        "avertissement": " ; ".join(getattr(source, "erreurs", []))})

    @app.get("/api/mails/<mail_id>")
    def api_mail(mail_id):
        mail = next((m for m in etat["mails"] if m["id"] == mail_id), None)
        if mail is None:
            return erreur("Mail inconnu, rechargez la liste.", 404)
        return jsonify(mail)

    @app.post("/api/mails/<mail_id>/lu")
    def api_marquer_lu(mail_id):
        try:
            source.marquer_lu(mail_id)
        except Exception as e:
            return erreur(f"Impossible de marquer le mail comme lu : {e}")
        return jsonify({"ok": True})

    @app.post("/api/mails/trier")
    def api_trier():
        donnees = request.get_json(silent=True) or {}
        elements = donnees.get("elements", [])
        connus = {m["id"] for m in etat["mails"]}
        faits, echecs = 0, []
        for el in elements:
            mid, cat = el.get("id"), el.get("categorie")
            if mid not in connus or cat not in CATEGORIES:
                echecs.append(mid)
                continue
            try:
                source.ranger(mid, cat, bool(el.get("archiver")), bool(el.get("marquer_lu")))
                faits += 1
            except Exception:
                log.exception("Rangement impossible pour %s", mid)
                echecs.append(mid)
        return jsonify({"ranges": faits, "echecs": echecs})

    @app.get("/api/agenda")
    def api_agenda():
        try:
            evenements = source.evenements(cfg.jours_agenda)
            resume = ia.briefing_agenda(evenements)
        except ErreurIA as e:
            return erreur(str(e), 502)
        except Exception as e:
            log.exception("Lecture de l'agenda impossible")
            return erreur(f"Lecture de l'agenda impossible : {e}")
        etat["agenda"] = evenements
        return jsonify({"resume_oral": resume, "evenements": evenements})

    @app.post("/api/agenda")
    def api_creer_evenement():
        d = request.get_json(silent=True) or {}
        try:
            debut = datetime.fromisoformat(d["debut"])
            fin = datetime.fromisoformat(d["fin"])
            if fin <= debut or not d.get("titre"):
                raise ValueError
        except (KeyError, ValueError, TypeError):
            return erreur("Titre, début et fin (ISO 8601) requis, la fin après le début.", 400)
        try:
            ev = source.creer_evenement(d["titre"], d["debut"], d["fin"], d.get("description", ""))
        except Exception as e:
            log.exception("Création d'événement impossible")
            return erreur(f"Création impossible : {e}")
        etat["agenda"].append(ev)
        return jsonify(ev)

    @app.post("/api/demander")
    def api_demander():
        d = request.get_json(silent=True) or {}
        question = (d.get("question") or "").strip()
        if not question:
            return erreur("Question vide.", 400)
        try:
            if not etat["agenda"]:
                etat["agenda"] = source.evenements(cfg.jours_agenda)
            rep = ia.repondre(question, etat["mails"], etat["agenda"], d.get("historique"))
        except ErreurIA as e:
            return erreur(str(e), 502)
        except Exception as e:
            log.exception("Question impossible")
            return erreur(f"Je n'ai pas pu traiter la demande : {e}")
        return jsonify(rep)

    @app.post("/api/voix")
    def api_voix():
        """Synthèse vocale ElevenLabs (optionnelle). Sans clé, la page utilise la voix du navigateur."""
        if not cfg.voix_premium:
            return erreur("Voix premium non configurée.", 404)
        import requests

        texte = ((request.get_json(silent=True) or {}).get("texte") or "")[:2500]
        if not texte:
            return erreur("Texte vide.", 400)
        try:
            r = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{cfg.elevenlabs_voix}",
                headers={"xi-api-key": cfg.elevenlabs_cle, "accept": "audio/mpeg"},
                json={"text": texte, "model_id": "eleven_multilingual_v2",
                      "voice_settings": {"stability": 0.65, "similarity_boost": 0.8, "style": 0.1}},
                timeout=60,
            )
        except requests.RequestException as e:
            return erreur(f"ElevenLabs injoignable : {e}", 502)
        if r.status_code != 200:
            return erreur(_erreur_elevenlabs(r), 502)
        return Response(r.content, mimetype="audio/mpeg")

    @app.post("/api/ecoute")
    def api_ecoute():
        """Transcription de la voix (ElevenLabs) pour les navigateurs sans reconnaissance vocale (Firefox…)."""
        if not cfg.elevenlabs_cle:
            return erreur("Écoute par ElevenLabs non configurée.", 404)
        import requests

        audio = request.files.get("audio")
        if audio is None:
            return erreur("Aucun son reçu.", 400)
        try:
            r = requests.post(
                "https://api.elevenlabs.io/v1/speech-to-text",
                headers={"xi-api-key": cfg.elevenlabs_cle},
                data={"model_id": "scribe_v1", "language_code": "fr"},
                files={"file": (audio.filename or "voix.webm", audio.stream, audio.mimetype or "application/octet-stream")},
                timeout=60,
            )
        except requests.RequestException as e:
            return erreur(f"ElevenLabs injoignable : {e}", 502)
        if r.status_code != 200:
            return erreur(_erreur_elevenlabs(r), 502)
        return jsonify({"texte": (r.json().get("text") or "").strip()})

    return app


def _erreur_elevenlabs(r) -> str:
    if r.status_code == 401:
        return "Clé ElevenLabs refusée : vérifiez ELEVENLABS_API_KEY."
    if r.status_code == 402 or "quota" in r.text.lower():
        return "Crédits ElevenLabs du mois épuisés : je repasse sur la voix de l'ordinateur."
    if r.status_code == 404:
        return "Voix ElevenLabs introuvable : vérifiez ELEVENLABS_VOICE_ID."
    return f"ElevenLabs a répondu {r.status_code}."
