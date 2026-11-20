"""Réglages de l'assistant : variables d'environnement, fichier .env et Trousseau du système.

Les secrets (clés, mots de passe) sont rangés dans le Trousseau macOS / le Gestionnaire
d'identifiants Windows quand il est disponible, sinon dans ~/.assistant_vocal/.env (lisible par
vous seul).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

SERVICE_TROUSSEAU = "Jarvis assistant"
SECRETS = ["ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "ICLOUD_MOT_DE_PASSE_APP", "GOOGLE_AGENDA_ICS", "ASSISTANT_CODE"]
REGLAGES = ["ASSISTANT_NOM", "ASSISTANT_UTILISATEUR", "ICLOUD_ADRESSE", "ELEVENLABS_VOICE_ID", "ASSISTANT_GMAIL",
            "ASSISTANT_HOTE", "ASSISTANT_MAX_MAILS", "ASSISTANT_JOURS_AGENDA"]
VOIX_DEFAUT = "onwK4e9ZLuTAKqWW03F9"  # « Daniel » : voix masculine grave et posée de la bibliothèque ElevenLabs

_charges: set[str] = set()  # clés que nous avons mises dans l'environnement (rechargeables)


def _lire_env(chemin: Path) -> dict[str, str]:
    valeurs = {}
    if chemin.is_file():
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                cle, valeur = ligne.split("=", 1)
                valeurs[cle.strip()] = valeur.strip().strip('"').strip("'")
    return valeurs


def _appliquer(valeurs: dict[str, str]) -> None:
    for cle, valeur in valeurs.items():
        if cle not in os.environ or cle in _charges:
            os.environ[cle] = valeur
            _charges.add(cle)


def trousseau():
    """Le Trousseau du système, ou None s'il n'y en a pas (Linux sans trousseau, conteneur…)."""
    try:
        import keyring
        from keyring.backends import fail

        k = keyring.get_keyring()
        return None if isinstance(k, fail.Keyring) else keyring
    except Exception:
        return None


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
    elevenlabs_voix: str = VOIX_DEFAUT
    port: int = 5050
    hote: str = "127.0.0.1"
    icloud_adresse: str = ""
    icloud_mot_de_passe: str = ""
    agenda_ics: str = ""
    gmail_actif: bool = True
    code_acces: str = ""

    @property
    def credentials_google(self) -> Path:
        return self.dossier / "credentials.json"

    @property
    def token_google(self) -> Path:
        return self.dossier / "token.json"

    @property
    def fichier_env(self) -> Path:
        return self.dossier / ".env"

    @property
    def ia_active(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))

    @property
    def voix_premium(self) -> bool:
        return bool(self.elevenlabs_cle and self.elevenlabs_voix)


def charger_config() -> Config:
    for cle in list(_charges):  # rechargement : on repart de l'environnement d'origine
        os.environ.pop(cle, None)
    _charges.clear()
    _appliquer(_lire_env(Path.cwd() / ".env"))
    dossier = Path(os.environ.get("ASSISTANT_DOSSIER", Path.home() / ".assistant_vocal")).expanduser()
    _appliquer(_lire_env(dossier / ".env"))
    k = trousseau()
    if k is not None:
        for nom in SECRETS:
            if nom not in os.environ:
                try:
                    valeur = k.get_password(SERVICE_TROUSSEAU, nom)
                except Exception:
                    valeur = None
                if valeur:
                    _appliquer({nom: valeur})

    e = os.environ.get
    cfg = Config(
        nom=e("ASSISTANT_NOM", "Jarvis") or "Jarvis",
        utilisateur=e("ASSISTANT_UTILISATEUR", "Monsieur") or "Monsieur",
        dossier=dossier,
        modele=e("ASSISTANT_MODELE", "claude-opus-5-5"),
        max_mails=int(e("ASSISTANT_MAX_MAILS", "15") or 15),
        jours_agenda=int(e("ASSISTANT_JOURS_AGENDA", "7") or 7),
        elevenlabs_cle=e("ELEVENLABS_API_KEY", ""),
        elevenlabs_voix=e("ELEVENLABS_VOICE_ID") or VOIX_DEFAUT,
        port=int(e("ASSISTANT_PORT", "5050")),
        hote=e("ASSISTANT_HOTE", "127.0.0.1") or "127.0.0.1",
        icloud_adresse=e("ICLOUD_ADRESSE", ""),
        icloud_mot_de_passe=e("ICLOUD_MOT_DE_PASSE_APP", "").replace(" ", ""),
        agenda_ics=e("GOOGLE_AGENDA_ICS", ""),
        gmail_actif=e("ASSISTANT_GMAIL", "1").lower() not in ("0", "false", "non"),
        code_acces=e("ASSISTANT_CODE", ""),
    )
    demo_env = e("ASSISTANT_DEMO", "").lower()
    rien = not (cfg.credentials_google.is_file() or (cfg.icloud_adresse and cfg.icloud_mot_de_passe) or cfg.agenda_ics)
    cfg.demo = demo_env in ("1", "true", "oui") or (demo_env not in ("0", "false", "non") and rien)
    return cfg


def enregistrer_reglages(cfg: Config, valeurs: dict[str, str]) -> str:
    """Enregistre les réglages modifiés. Une valeur vide efface le réglage.
    Renvoie où les secrets ont été rangés (« trousseau » ou « fichier »)."""
    cfg.dossier.mkdir(parents=True, exist_ok=True)
    env = _lire_env(cfg.fichier_env)
    k = trousseau()
    for cle, valeur in valeurs.items():
        if cle not in SECRETS and cle not in REGLAGES:
            continue
        valeur = (valeur or "").strip()
        if cle in SECRETS and k is not None:
            try:
                if valeur:
                    k.set_password(SERVICE_TROUSSEAU, cle, valeur)
                else:
                    try:
                        k.delete_password(SERVICE_TROUSSEAU, cle)
                    except Exception:
                        pass
                env.pop(cle, None)
                continue
            except Exception:
                pass  # trousseau indisponible : repli sur le fichier
        if valeur:
            env[cle] = valeur
        else:
            env.pop(cle, None)
    lignes = ["# Réglages de Jarvis (modifiables depuis la page Réglages)"]
    lignes += [f"{c}={v}" for c, v in env.items()]
    cfg.fichier_env.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    cfg.fichier_env.chmod(0o600)
    return "trousseau" if k is not None else "fichier"


def etat_reglages(cfg: Config) -> dict:
    """Ce que la page Réglages peut afficher : les réglages en clair, les secrets seulement « renseigné ou non »."""
    e = os.environ.get
    return {
        "reglages": {c: e(c, "") for c in REGLAGES},
        "secrets": {c: bool(e(c)) for c in SECRETS},
        "google_credentials": cfg.credentials_google.is_file(),
        "google_connecte": cfg.token_google.is_file(),
        "rangement": "trousseau" if trousseau() is not None else "fichier",
    }
