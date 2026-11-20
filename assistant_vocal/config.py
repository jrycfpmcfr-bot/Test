"""Réglages de l'assistant, lus depuis les variables d'environnement (ou un fichier .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _charger_env(chemin: Path) -> None:
    """Charge un fichier .env simple (CLE=valeur) sans écraser l'environnement existant."""
    if not chemin.is_file():
        return
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


@dataclass
class Config:
    nom: str = "Jarvis"
    utilisateur: str = "Monsieur"
    dossier: Path = field(default_factory=lambda: Path.home() / ".assistant_vocal")
    modele: str = "claude-opus-5-5"
    demo: bool = False
    max_mails: int = 15
    jours_agenda: int = 7
    elevenlabs_cle: str = ""
    # « Daniel » : voix masculine grave et posée de la bibliothèque standard ElevenLabs.
    elevenlabs_voix: str = "onwK4e9ZLuTAKqWW03F9"
    port: int = 5050
    icloud_adresse: str = ""
    icloud_mot_de_passe: str = ""
    agenda_ics: str = ""
    gmail_actif: bool = True

    @property
    def credentials_google(self) -> Path:
        return self.dossier / "credentials.json"

    @property
    def token_google(self) -> Path:
        return self.dossier / "token.json"

    @property
    def ia_active(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))

    @property
    def voix_premium(self) -> bool:
        return bool(self.elevenlabs_cle and self.elevenlabs_voix)


def charger_config() -> Config:
    _charger_env(Path.cwd() / ".env")
    dossier = Path(os.environ.get("ASSISTANT_DOSSIER", Path.home() / ".assistant_vocal")).expanduser()
    _charger_env(dossier / ".env")
    cfg = Config(
        nom=os.environ.get("ASSISTANT_NOM", "Jarvis"),
        utilisateur=os.environ.get("ASSISTANT_UTILISATEUR", "Monsieur"),
        dossier=dossier,
        modele=os.environ.get("ASSISTANT_MODELE", "claude-opus-5-5"),
        max_mails=int(os.environ.get("ASSISTANT_MAX_MAILS", "15")),
        jours_agenda=int(os.environ.get("ASSISTANT_JOURS_AGENDA", "7")),
        elevenlabs_cle=os.environ.get("ELEVENLABS_API_KEY", ""),
        elevenlabs_voix=os.environ.get("ELEVENLABS_VOICE_ID") or "onwK4e9ZLuTAKqWW03F9",
        port=int(os.environ.get("ASSISTANT_PORT", "5050")),
        icloud_adresse=os.environ.get("ICLOUD_ADRESSE", ""),
        icloud_mot_de_passe=os.environ.get("ICLOUD_MOT_DE_PASSE_APP", "").replace(" ", ""),
        agenda_ics=os.environ.get("GOOGLE_AGENDA_ICS", ""),
        gmail_actif=os.environ.get("ASSISTANT_GMAIL", "1").lower() not in ("0", "false", "non"),
    )
    demo_env = os.environ.get("ASSISTANT_DEMO", "").lower()
    # Mode démo si demandé, ou si aucune boîte ni aucun agenda n'est encore configuré.
    rien = not (cfg.credentials_google.is_file() or (cfg.icloud_adresse and cfg.icloud_mot_de_passe) or cfg.agenda_ics)
    cfg.demo = demo_env in ("1", "true", "oui") or (demo_env not in ("0", "false", "non") and rien)
    return cfg
