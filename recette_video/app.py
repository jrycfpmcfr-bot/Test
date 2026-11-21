"""Application web : FastAPI + une page HTML."""

from __future__ import annotations

import base64
import os
import secrets
import shutil
import tempfile
import threading
import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from . import analyse, extraction

STATIC = Path(__file__).parent / "static"
RACINE = Path(tempfile.gettempdir()) / "recette_video"
RACINE.mkdir(exist_ok=True)

app = FastAPI(title="Recette vidéo")


@app.middleware("http")
async def mot_de_passe(request: Request, appel_suivant):
    """Si APP_PASSWORD est défini, le navigateur demande un mot de passe (nom d'utilisateur libre)."""
    attendu = os.environ.get("APP_PASSWORD")
    if not attendu or request.url.path == "/sante":
        return await appel_suivant(request)
    entete = request.headers.get("authorization", "")
    if entete.lower().startswith("basic "):
        try:
            _, _, donne = base64.b64decode(entete[6:]).decode("utf-8").partition(":")
        except Exception:
            donne = ""
        if secrets.compare_digest(donne.encode(), attendu.encode()):
            return await appel_suivant(request)
    return Response(
        "Mot de passe requis.", status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Recette Video", charset="UTF-8"'},
    )


@app.get("/sante")
def sante() -> dict:
    return {"ok": True}

travaux: dict[str, dict] = {}
verrou = threading.Lock()

ETAPES = ["telechargement", "images", "audio", "commentaires", "recette"]


def _maj(id_: str, **champs) -> None:
    with verrou:
        travaux[id_].update(champs)


def _traiter(id_: str, url: str, video_envoyee: Path | None, cookies: Path | None, commentaires_colles: str) -> None:
    dossier = RACINE / id_
    try:
        # 1. Vidéo + métadonnées + commentaires
        _maj(id_, etape="telechargement")
        if video_envoyee is not None:
            contenu = extraction.ContenuVideo(dossier=dossier, video=video_envoyee, titre=video_envoyee.stem)
        else:
            contenu = extraction.telecharger(url, dossier, cookies)

        duree, a_audio = extraction.duree_et_audio(contenu.video)
        contenu.duree = contenu.duree or duree
        _maj(id_, titre=contenu.titre, auteur=contenu.auteur, duree=contenu.duree)

        # 2. Images
        _maj(id_, etape="images")
        contenu.images = extraction.extraire_images(contenu.video, dossier / "images", contenu.duree)
        _maj(id_, images=[{"seconde": im.seconde} for im in contenu.images])

        # 3. Audio
        _maj(id_, etape="audio")
        if a_audio:
            try:
                audio = extraction.extraire_audio(contenu.video, dossier)
                contenu.transcription, contenu.langue_audio = extraction.transcrire(audio)
            except Exception as e:  # la recette reste possible sans l'audio
                contenu.avertissements.append(f"Transcription de l'audio impossible : {e}")
        else:
            contenu.avertissements.append("La vidéo n'a pas de piste audio.")
        _maj(id_, transcription=contenu.transcription)

        # 4. Commentaires
        _maj(id_, etape="commentaires")
        if commentaires_colles.strip():
            contenu.commentaires += extraction.commentaires_depuis_texte(commentaires_colles)
            contenu.avertissements = [a for a in contenu.avertissements if "commentaire" not in a.lower()]
        _maj(
            id_,
            nb_commentaires=len(contenu.commentaires),
            description=contenu.description,
            avertissements=list(contenu.avertissements),
        )

        # 5. Recette
        _maj(id_, etape="recette")
        recette = analyse.rediger_recette(contenu)
        _maj(id_, etat="termine", etape="fini", recette=recette.model_dump())
    except Exception as e:
        traceback.print_exc()
        _maj(id_, etat="erreur", erreur=_message_erreur(e))
    finally:
        for fichier in dossier.glob("*"):
            if fichier.is_file() and fichier.suffix != ".jpg":
                fichier.unlink(missing_ok=True)  # on ne garde que les images


def _message_erreur(e: Exception) -> str:
    texte = str(e)
    bas = texte.lower()
    if "login" in bas or "cookies" in bas or "rate-limit" in bas or "private" in bas:
        return (
            "Le réseau social demande d'être connecté pour lire cette vidéo. Ajoutez votre fichier "
            "cookies.txt (exporté depuis votre navigateur) ou téléversez directement la vidéo. "
            f"Détail : {texte}"
        )
    if "authentication" in bas or "api_key" in bas or "x-api-key" in bas:
        return "Clé API Anthropic manquante ou invalide (variable ANTHROPIC_API_KEY)."
    return texte


@app.get("/", response_class=HTMLResponse)
def accueil() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.post("/api/analyses")
async def creer_analyse(
    url: str = Form(""),
    commentaires: str = Form(""),
    video: UploadFile | None = File(None),
    cookies: UploadFile | None = File(None),
) -> dict:
    url = url.strip()
    if not url and (video is None or not video.filename):
        raise HTTPException(400, "Indiquez un lien Facebook / Instagram ou envoyez un fichier vidéo.")
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Le lien doit commencer par http:// ou https://")

    id_ = uuid.uuid4().hex[:12]
    dossier = RACINE / id_
    dossier.mkdir(parents=True)

    chemin_video = None
    if video is not None and video.filename:
        ext = Path(video.filename).suffix.lower()
        if ext not in extraction.VIDEO_EXTS:
            raise HTTPException(400, f"Format vidéo non reconnu : {ext}")
        chemin_video = dossier / f"video{ext}"
        with chemin_video.open("wb") as f:
            shutil.copyfileobj(video.file, f)

    chemin_cookies = None
    if cookies is not None and cookies.filename:
        chemin_cookies = dossier / "cookies.txt"
        with chemin_cookies.open("wb") as f:
            shutil.copyfileobj(cookies.file, f)

    with verrou:
        travaux[id_] = {"id": id_, "etat": "en_cours", "etape": "telechargement", "url": url}
    threading.Thread(
        target=_traiter, args=(id_, url, chemin_video, chemin_cookies, commentaires), daemon=True
    ).start()
    return {"id": id_}


@app.get("/api/analyses/{id_}")
def lire_analyse(id_: str) -> dict:
    with verrou:
        travail = travaux.get(id_)
        if travail is None:
            raise HTTPException(404, "Analyse introuvable.")
        return dict(travail, etapes=ETAPES)


@app.get("/api/analyses/{id_}/images/{n}")
def image(id_: str, n: int) -> FileResponse:
    if id_ not in travaux:
        raise HTTPException(404)
    chemin = RACINE / id_ / "images" / f"image_{n:02d}.jpg"
    if not chemin.is_file():
        raise HTTPException(404)
    return FileResponse(chemin, media_type="image/jpeg")
