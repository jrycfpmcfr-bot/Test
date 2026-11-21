"""Récupération de la vidéo et de son contenu : images, audio, texte, commentaires."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


@dataclass
class Commentaire:
    auteur: str
    texte: str
    likes: int = 0


@dataclass
class Image:
    chemin: Path
    seconde: float


@dataclass
class ContenuVideo:
    dossier: Path
    video: Path
    titre: str = ""
    description: str = ""
    auteur: str = ""
    url: str = ""
    duree: float = 0.0
    commentaires: list[Commentaire] = field(default_factory=list)
    images: list[Image] = field(default_factory=list)
    transcription: str = ""
    langue_audio: str = ""
    avertissements: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Téléchargement (yt-dlp)
# --------------------------------------------------------------------------- #

def _options_cookies() -> dict:
    """Instagram et Facebook exigent souvent d'être connecté : on lit les cookies."""
    opts: dict = {}
    fichier = os.environ.get("COOKIES_FILE")
    if fichier and Path(fichier).is_file():
        opts["cookiefile"] = fichier
    navigateur = os.environ.get("COOKIES_FROM_BROWSER")  # ex. "firefox", "chrome"
    if navigateur:
        opts["cookiesfrombrowser"] = (navigateur,)
    return opts


def telecharger(url: str, dossier: Path, cookies: Path | None = None) -> ContenuVideo:
    import yt_dlp

    opts = {
        "outtmpl": str(dossier / "video.%(ext)s"),
        "format": "bv*[height<=720]+ba/b[height<=720]/bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "getcomments": True,
        **_options_cookies(),
    }
    if cookies is not None:
        opts["cookiefile"] = str(cookies)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if info.get("_type") == "playlist" and info.get("entries"):
        info = next(e for e in info["entries"] if e)

    videos = [p for p in dossier.iterdir() if p.stem == "video" and p.suffix.lower() in VIDEO_EXTS]
    if not videos:
        raise RuntimeError("La vidéo n'a pas pu être téléchargée.")

    contenu = ContenuVideo(
        dossier=dossier,
        video=videos[0],
        titre=info.get("title") or "",
        description=info.get("description") or "",
        auteur=info.get("uploader") or info.get("channel") or "",
        url=info.get("webpage_url") or url,
        duree=float(info.get("duration") or 0),
    )
    for c in info.get("comments") or []:
        texte = (c.get("text") or "").strip()
        if texte:
            contenu.commentaires.append(
                Commentaire(auteur=c.get("author") or "", texte=texte, likes=int(c.get("like_count") or 0))
            )
    if not contenu.commentaires:
        contenu.avertissements.append(
            "Aucun commentaire récupéré automatiquement (Facebook ne les fournit pas, Instagram "
            "seulement avec cookies). Vous pouvez les coller dans le champ « Commentaires »."
        )
    return contenu


def commentaires_depuis_texte(texte: str) -> list[Commentaire]:
    """Commentaires collés à la main : un par ligne, « auteur: texte » facultatif."""
    resultat = []
    for ligne in texte.splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        auteur, sep, reste = ligne.partition(":")
        if sep and 0 < len(auteur) <= 40 and " " not in auteur.strip():
            resultat.append(Commentaire(auteur=auteur.strip(), texte=reste.strip()))
        else:
            resultat.append(Commentaire(auteur="", texte=ligne))
    return resultat


# --------------------------------------------------------------------------- #
# Images et audio (ffmpeg)
# --------------------------------------------------------------------------- #

def _ffprobe(video: Path) -> dict:
    sortie = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(sortie)


def duree_et_audio(video: Path) -> tuple[float, bool]:
    info = _ffprobe(video)
    duree = float(info.get("format", {}).get("duration") or 0)
    a_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
    return duree, a_audio


def nombre_images(duree: float, maximum: int = 30) -> int:
    """Environ une image toutes les 3 s, entre 8 et `maximum`."""
    return max(8, min(maximum, round(duree / 3))) if duree > 0 else 8


def extraire_images(video: Path, dossier: Path, duree: float, maximum: int = 30) -> list[Image]:
    dossier.mkdir(parents=True, exist_ok=True)
    n = nombre_images(duree, maximum)
    pas = duree / n if duree > 0 else 1.0
    images = []
    for i in range(n):
        t = round(pas * (i + 0.5), 2)  # milieu de chaque intervalle
        sortie = dossier / f"image_{i:02d}.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video),
             "-frames:v", "1", "-vf", "scale='min(768,iw)':-2", "-q:v", "4", str(sortie)],
            check=False, capture_output=True,
        )
        if sortie.is_file() and sortie.stat().st_size > 0:
            images.append(Image(chemin=sortie, seconde=t))
    return images


def extraire_audio(video: Path, dossier: Path) -> Path:
    sortie = dossier / "audio.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(sortie)],
        check=True, capture_output=True,
    )
    return sortie


# --------------------------------------------------------------------------- #
# Transcription (faster-whisper, en local)
# --------------------------------------------------------------------------- #

_modele_whisper = None


def transcrire(audio: Path) -> tuple[str, str]:
    global _modele_whisper
    from faster_whisper import WhisperModel

    if _modele_whisper is None:
        taille = os.environ.get("WHISPER_MODEL", "small")
        _modele_whisper = WhisperModel(taille, device="cpu", compute_type="int8")
    segments, info = _modele_whisper.transcribe(str(audio), vad_filter=True)
    lignes = [f"[{s.start:5.1f}s] {s.text.strip()}" for s in segments if s.text.strip()]
    return "\n".join(lignes), info.language
