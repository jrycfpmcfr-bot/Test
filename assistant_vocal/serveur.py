"""Serveur web local : sert l'interface et expose l'API utilisée par la page."""

from __future__ import annotations

import hashlib
import hmac
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, request, send_from_directory

from .config import Config, charger_config, enregistrer_reglages, etat_reglages
from .ia import CATEGORIES, IA, ErreurIA
from .memoire import Memoire, adresse_de

STATIQUE = Path(__file__).parent / "static"
log = logging.getLogger("assistant_vocal")
LIBRES = {"/connexion", "/api/connexion", "/manifest.webmanifest", "/static/icone-180.png",
          "/static/icone-512.png", "/static/style.css"}


def construire_source_par_defaut(cfg: Config):
    if not cfg.demo:
        from .sources import construire_source

        source, _google = construire_source(cfg)
        if source is not None:
            return source
    from .demo import Demo

    return Demo()


def jeton_acces(code: str) -> str:
    return hmac.new(code.encode(), b"jarvis-acces", hashlib.sha256).hexdigest()


def creer_app(cfg: Config, source=None, ia: IA | None = None) -> Flask:
    source_fixe = source is not None  # tests : la source fournie n'est jamais remplacée
    if source is None:
        source = construire_source_par_defaut(cfg)
    ia = ia or IA(cfg)
    memoire = Memoire(cfg.dossier)
    app = Flask(__name__, static_folder=None)
    etat = {"mails": [], "analyse": None, "agenda": []}
    verrou = threading.Lock()

    def erreur(message: str, code: int = 500):
        return jsonify({"erreur": message}), code

    def recharger() -> None:
        """Après un changement de réglages : relit la configuration et reconstruit les sources."""
        nonlocal cfg, source, ia
        nouvelle = charger_config()
        nouvelle.port = cfg.port
        cfg = nouvelle
        ia = IA(cfg)
        if not source_fixe:
            source = construire_source_par_defaut(cfg)
        etat.update(mails=[], analyse=None, agenda=[])

    def mail_connu(mail_id: str) -> dict | None:
        return next((m for m in etat["mails"] if m["id"] == mail_id), None)

    # --- Code d'accès (indispensable pour ouvrir Jarvis depuis le téléphone) -----------
    @app.before_request
    def controle_acces():
        if not cfg.code_acces or request.path in LIBRES:
            return None
        if hmac.compare_digest(request.cookies.get("jarvis_acces", ""), jeton_acces(cfg.code_acces)):
            return None
        if request.path.startswith("/api/"):
            return erreur("Code d'accès requis.", 401)
        return redirect("/connexion")

    @app.get("/connexion")
    def page_connexion():
        return send_from_directory(STATIQUE, "connexion.html")

    @app.post("/api/connexion")
    def api_connexion():
        code = ((request.get_json(silent=True) or {}).get("code") or "").strip()
        if not cfg.code_acces or not hmac.compare_digest(code, cfg.code_acces):
            time.sleep(1.5)  # ralentit les essais au hasard
            return erreur("Code incorrect.", 401)
        rep = jsonify({"ok": True})
        securise = request.is_secure or request.headers.get("X-Forwarded-Proto") == "https"
        rep.set_cookie("jarvis_acces", jeton_acces(cfg.code_acces), max_age=365 * 24 * 3600,
                       httponly=True, samesite="Strict", secure=securise)
        return rep

    # --- Pages ----------------------------------------------------------------------
    @app.get("/")
    def accueil():
        return send_from_directory(STATIQUE, "index.html")

    @app.get("/static/<path:fichier>")
    def statique(fichier):
        return send_from_directory(STATIQUE, fichier)

    @app.get("/manifest.webmanifest")
    def manifeste():
        return jsonify({
            "name": cfg.nom, "short_name": cfg.nom, "lang": "fr", "start_url": "/", "display": "standalone",
            "background_color": "#02070d", "theme_color": "#02070d",
            "icons": [{"src": "/static/icone-180.png", "sizes": "180x180", "type": "image/png"},
                      {"src": "/static/icone-512.png", "sizes": "512x512", "type": "image/png"}],
        })

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
            "agenda_modifiable": bool(getattr(source, "agenda_modifiable", True)),
            "boites": list(getattr(source, "boites", {}) or (["demo"] if cfg.demo else [])),
            "heure": datetime.now().astimezone().isoformat(),
        })

    # --- Mails ----------------------------------------------------------------------
    def indices_memoire(mails: list[dict]) -> str:
        lignes = []
        vip = [m["de"] for m in mails if memoire.est_prioritaire(m["de"])]
        if vip:
            lignes.append("Contacts prioritaires (à mettre en avant dans le briefing) : " + ", ".join(vip))
        appris = [(m["de"], memoire.categorie_apprise(m["de"])) for m in mails if memoire.categorie_apprise(m["de"])]
        if appris:
            lignes.append("Mes préférences de tri (à respecter) : " + "; ".join(f"{d} → {c}" for d, c in appris))
        return "\n".join(lignes)

    @app.get("/api/mails")
    def api_mails():
        try:
            mails = source.mails_non_lus(cfg.max_mails)
            analyse = ia.trier_mails(mails, indices_memoire(mails))
        except ErreurIA as e:
            return erreur(str(e), 502)
        except Exception as e:  # boîte indisponible, mot de passe refusé…
            log.exception("Lecture des mails impossible")
            return erreur(f"Lecture des mails impossible : {e}")
        par_id = {a["id"]: a for a in analyse["mails"]}
        for a in par_id.values():  # le tri appris l'emporte sur la suggestion
            m = next((x for x in mails if x["id"] == a["id"]), None)
            appris = m and memoire.categorie_apprise(m["de"])
            if appris and appris in CATEGORIES:
                a["categorie"], a["raison"] = appris, "d'après vos tris précédents"
                a["action"] = "archiver" if appris in ("Promotions", "Newsletters", "Spam probable") else "garder"
        with verrou:
            etat["mails"], etat["analyse"] = mails, analyse
        liste = []
        for m in mails:
            a = par_id.get(m["id"], {})
            evenement = None
            if a.get("evenement_titre") and a.get("evenement_debut"):
                evenement = {"titre": a["evenement_titre"], "debut": a["evenement_debut"],
                             "fin": a.get("evenement_fin") or ""}
            liste.append({
                "id": m["id"], "de": m["de"], "objet": m["objet"], "date": m["date"],
                "extrait": m["extrait"], "resume": a.get("resume", m["extrait"]),
                "categorie": a.get("categorie", "À lire"), "action": a.get("action", "garder"),
                "raison": a.get("raison", ""), "boite": m.get("boite", ""),
                "prioritaire": memoire.est_prioritaire(m["de"]),
                "desabonnable": bool(m.get("desabonnement")),
                "evenement": evenement,
            })
        liste.sort(key=lambda x: not x["prioritaire"])  # contacts prioritaires d'abord (tri stable)
        return jsonify({"resume_oral": analyse["resume_oral"], "mails": liste,
                        "avertissement": " ; ".join(getattr(source, "erreurs", []))})

    @app.get("/api/mails/<mail_id>")
    def api_mail(mail_id):
        mail = mail_connu(mail_id)
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
        suggestions = {a["id"]: a.get("categorie") for a in (etat["analyse"] or {}).get("mails", [])}
        faits, echecs, appris = 0, [], 0
        for el in elements:
            mid, cat = el.get("id"), el.get("categorie")
            mail = mail_connu(mid)
            if mail is None or cat not in CATEGORIES:
                echecs.append(mid)
                continue
            try:
                source.ranger(mid, cat, bool(el.get("archiver")), bool(el.get("marquer_lu")))
                faits += 1
                if suggestions.get(mid) and suggestions[mid] != cat:  # vous avez corrigé : Jarvis retient
                    memoire.apprendre(mail["de"], cat)
                    appris += 1
            except Exception:
                log.exception("Rangement impossible pour %s", mid)
                echecs.append(mid)
        return jsonify({"ranges": faits, "echecs": echecs, "appris": appris})

    @app.post("/api/mails/<mail_id>/brouillon")
    def api_brouillon(mail_id):
        mail = mail_connu(mail_id)
        if mail is None:
            return erreur("Mail inconnu, rechargez la liste.", 404)
        consigne = ((request.get_json(silent=True) or {}).get("consigne") or "").strip()
        if not consigne:
            return erreur("Dites ce que la réponse doit contenir.", 400)
        try:
            return jsonify({"texte": ia.rediger_reponse(mail, consigne)})
        except ErreurIA as e:
            return erreur(str(e), 502)

    @app.post("/api/mails/<mail_id>/repondre")
    def api_repondre(mail_id):
        mail = mail_connu(mail_id)
        if mail is None:
            return erreur("Mail inconnu, rechargez la liste.", 404)
        texte = ((request.get_json(silent=True) or {}).get("texte") or "").strip()
        if not texte:
            return erreur("La réponse est vide.", 400)
        if not hasattr(source, "repondre"):
            return erreur("Cette boîte ne permet pas d'envoyer de réponse.", 400)
        try:
            source.repondre(mail, texte)
        except Exception as e:
            log.exception("Envoi impossible")
            return erreur(f"Envoi impossible : {e}")
        return jsonify({"ok": True})

    @app.post("/api/mails/<mail_id>/desabonner")
    def api_desabonner(mail_id):
        mail = mail_connu(mail_id)
        if mail is None:
            return erreur("Mail inconnu, rechargez la liste.", 404)
        if not mail.get("desabonnement") or not hasattr(source, "desabonner"):
            return erreur("Ce mail ne propose pas de désabonnement.", 400)
        try:
            resultat = source.desabonner(mail)
        except Exception as e:
            log.exception("Désabonnement impossible")
            return erreur(f"Désabonnement impossible : {e}")
        if resultat == "fait":
            return jsonify({"fait": True})
        return jsonify({"fait": False, "lien": resultat})

    @app.post("/api/mails/<mail_id>/prioritaire")
    def api_prioritaire(mail_id):
        mail = mail_connu(mail_id)
        if mail is None or not adresse_de(mail["de"]):
            return erreur("Expéditeur inconnu.", 404)
        return jsonify({"prioritaire": memoire.basculer_prioritaire(mail["de"])})

    # --- Agenda ---------------------------------------------------------------------
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
        if debut.tzinfo is None:  # heure locale de l'ordinateur
            d["debut"], d["fin"] = debut.astimezone().isoformat(), fin.astimezone().isoformat()
        try:
            ev = source.creer_evenement(d["titre"], d["debut"], d["fin"], d.get("description", ""))
        except Exception as e:
            log.exception("Création d'événement impossible")
            return erreur(f"Création impossible : {e}")
        etat["agenda"].append(ev)
        return jsonify(ev)

    # --- Questions libres -----------------------------------------------------------
    @app.post("/api/demander")
    def api_demander():
        d = request.get_json(silent=True) or {}
        question = (d.get("question") or "").strip()
        if not question:
            return erreur("Question vide.", 400)
        try:
            if not etat["agenda"]:
                try:
                    etat["agenda"] = source.evenements(cfg.jours_agenda)
                except Exception:
                    log.warning("Agenda indisponible pour la question")
            rep = ia.repondre(question, etat["mails"], etat["agenda"], d.get("historique"))
        except ErreurIA as e:
            return erreur(str(e), 502)
        except Exception as e:
            log.exception("Question impossible")
            return erreur(f"Je n'ai pas pu traiter la demande : {e}")
        if rep.get("action") in ("repondre_mail", "desabonner") and not mail_connu(rep.get("mail_id", "")):
            rep["action"] = "aucune"  # mail inventé ou liste pas chargée : on n'agit pas
        return jsonify(rep)

    # --- Voix et écoute (ElevenLabs) -----------------------------------------------
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
        """Transcription de la voix (ElevenLabs) : marche dans tous les navigateurs, téléphone compris."""
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

    # --- Réglages ------------------------------------------------------------------
    @app.get("/api/reglages")
    def api_reglages():
        return jsonify(dict(etat_reglages(cfg), prioritaires=memoire.prioritaires))

    @app.post("/api/reglages")
    def api_enregistrer_reglages():
        d = request.get_json(silent=True) or {}
        rangement = enregistrer_reglages(cfg, d.get("valeurs") or {})
        if isinstance(d.get("prioritaires"), list):
            memoire.definir_prioritaires(d["prioritaires"])
        recharger()
        return jsonify({"ok": True, "rangement": rangement, "demo": cfg.demo})

    @app.post("/api/reglages/google")
    def api_fichier_google():
        f = request.files.get("fichier")
        if f is None:
            return erreur("Aucun fichier reçu.", 400)
        import json

        try:
            contenu = json.loads(f.read().decode("utf-8"))
            if "installed" not in contenu:
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            return erreur("Ce n'est pas un identifiant « Application de bureau » de Google (fichier JSON).", 400)
        cfg.dossier.mkdir(parents=True, exist_ok=True)
        cfg.credentials_google.write_text(json.dumps(contenu), encoding="utf-8")
        cfg.credentials_google.chmod(0o600)
        recharger()
        return jsonify({"ok": True})

    @app.post("/api/reglages/tester/<service>")
    def api_tester(service):
        try:
            return jsonify({"ok": True, "message": _tester(service, cfg, source)})
        except Exception as e:
            return jsonify({"ok": False, "message": str(e)})

    return app


def _tester(service: str, cfg: Config, source) -> str:
    import requests

    if service == "icloud":
        from .sources import Icloud

        if not (cfg.icloud_adresse and cfg.icloud_mot_de_passe):
            raise RuntimeError("Adresse iCloud ou mot de passe pour app manquant.")
        Icloud(cfg.icloud_adresse, cfg.icloud_mot_de_passe).verifier()
        return "Connexion à iCloud réussie."
    if service == "agenda":
        evs = source.evenements(cfg.jours_agenda)
        return f"Agenda lu : {len(evs)} événement(s) dans les {cfg.jours_agenda} prochains jours."
    if service == "google":
        from .google_services import Google

        if not cfg.credentials_google.is_file():
            raise RuntimeError("Déposez d'abord le fichier d'identifiants Google.")
        Google(cfg).connecter()  # ouvre la page d'autorisation Google sur l'ordinateur la première fois
        return "Accès Google autorisé."
    if service == "claude":
        if not cfg.ia_active:
            raise RuntimeError("Clé Anthropic manquante.")
        import anthropic

        try:
            anthropic.Anthropic().models.retrieve(cfg.modele)
        except anthropic.AuthenticationError as e:
            raise RuntimeError("Clé Anthropic refusée.") from e
        return "Clé Claude valide."
    if service == "elevenlabs":
        if not cfg.elevenlabs_cle:
            raise RuntimeError("Clé ElevenLabs manquante.")
        r = requests.get(f"https://api.elevenlabs.io/v1/voices/{cfg.elevenlabs_voix}",
                         headers={"xi-api-key": cfg.elevenlabs_cle}, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(_erreur_elevenlabs(r))
        return f"Clé ElevenLabs valide, voix « {r.json().get('name', '?')} » trouvée."
    raise RuntimeError("Service inconnu.")


def _erreur_elevenlabs(r) -> str:
    if r.status_code == 401:
        return "Clé ElevenLabs refusée : vérifiez la clé dans les réglages."
    if r.status_code == 402 or "quota" in r.text.lower():
        return "Crédits ElevenLabs du mois épuisés : je repasse sur la voix de l'ordinateur."
    if r.status_code == 404:
        return "Voix ElevenLabs introuvable : vérifiez l'identifiant de voix."
    return f"ElevenLabs a répondu {r.status_code}."
