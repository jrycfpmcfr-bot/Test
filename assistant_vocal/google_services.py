"""Accès à Gmail et Google Agenda (OAuth « application de bureau », jetons stockés en local)."""

from __future__ import annotations

import base64
import html
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from .config import Config

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",  # lire, étiqueter, archiver (pas de suppression définitive)
    "https://www.googleapis.com/auth/calendar.events",  # lire et créer des événements
]
PREFIXE_LIBELLE = "Assistant"
MAX_CORPS = 4000


def _texte_depuis_html(contenu: str) -> str:
    contenu = re.sub(r"(?is)<(script|style).*?</\1>", " ", contenu)
    contenu = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", contenu)
    contenu = re.sub(r"<[^>]+>", " ", contenu)
    return html.unescape(contenu)


def _decoder(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def extraire_corps(payload: dict) -> str:
    """Renvoie le texte d'un message Gmail (text/plain de préférence, sinon HTML nettoyé)."""
    textes, htmls = [], []

    def parcourir(partie: dict) -> None:
        mime = partie.get("mimeType", "")
        data = partie.get("body", {}).get("data")
        if data and mime == "text/plain":
            textes.append(_decoder(data))
        elif data and mime == "text/html":
            htmls.append(_texte_depuis_html(_decoder(data)))
        for sous in partie.get("parts", []) or []:
            parcourir(sous)

    parcourir(payload)
    corps = "\n".join(textes) if textes else "\n".join(htmls)
    corps = re.sub(r"[ \t\r\f\v]+", " ", corps)
    corps = re.sub(r"\n\s*\n+", "\n", corps).strip()
    return corps[:MAX_CORPS]


def convertir_message(msg: dict) -> dict:
    entetes = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    try:
        date = parsedate_to_datetime(entetes.get("date", "")).isoformat()
    except (TypeError, ValueError):
        date = ""
    return {
        "id": msg["id"],
        "thread_id": msg.get("threadId", ""),
        "de": entetes.get("from", ""),
        "objet": entetes.get("subject", "(sans objet)"),
        "date": date,
        "extrait": html.unescape(msg.get("snippet", "")),
        "corps": extraire_corps(msg.get("payload", {})),
        "libelles": msg.get("labelIds", []),
    }


def convertir_evenement(ev: dict) -> dict:
    debut = ev.get("start", {})
    fin = ev.get("end", {})
    return {
        "id": ev.get("id", ""),
        "titre": ev.get("summary", "(sans titre)"),
        "debut": debut.get("dateTime") or debut.get("date", ""),
        "fin": fin.get("dateTime") or fin.get("date", ""),
        "journee_entiere": "date" in debut and "dateTime" not in debut,
        "lieu": ev.get("location", ""),
        "description": (ev.get("description") or "")[:500],
    }


class Google:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._gmail = None
        self._agenda = None
        self._libelles: dict[str, str] = {}

    # --- Connexion -------------------------------------------------------
    def _identifiants(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds = None
        if self.cfg.token_google.is_file():
            creds = Credentials.from_authorized_user_file(str(self.cfg.token_google), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(str(self.cfg.credentials_google), SCOPES)
            creds = flow.run_local_server(port=0, prompt="consent")
        self.cfg.token_google.write_text(creds.to_json(), encoding="utf-8")
        self.cfg.token_google.chmod(0o600)
        return creds

    def connecter(self) -> None:
        from googleapiclient.discovery import build

        creds = self._identifiants()
        self._gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
        self._agenda = build("calendar", "v3", credentials=creds, cache_discovery=False)

    @property
    def gmail(self):
        if self._gmail is None:
            self.connecter()
        return self._gmail

    @property
    def agenda(self):
        if self._agenda is None:
            self.connecter()
        return self._agenda

    # --- Gmail -----------------------------------------------------------
    def mails_non_lus(self, maximum: int) -> list[dict]:
        rep = self.gmail.users().messages().list(
            userId="me", q="is:unread in:inbox", maxResults=maximum
        ).execute()
        mails = []
        for ref in rep.get("messages", []):
            msg = self.gmail.users().messages().get(userId="me", id=ref["id"], format="full").execute()
            mails.append(convertir_message(msg))
        return mails

    def _id_libelle(self, nom: str) -> str:
        if not self._libelles:
            for lib in self.gmail.users().labels().list(userId="me").execute().get("labels", []):
                self._libelles[lib["name"]] = lib["id"]
        if nom not in self._libelles:
            cree = self.gmail.users().labels().create(
                userId="me",
                body={"name": nom, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
            ).execute()
            self._libelles[nom] = cree["id"]
        return self._libelles[nom]

    def ranger(self, mail_id: str, categorie: str, archiver: bool, marquer_lu: bool) -> None:
        ajouter = [self._id_libelle(f"{PREFIXE_LIBELLE}/{categorie}")]
        retirer = []
        if archiver:
            retirer.append("INBOX")
        if marquer_lu:
            retirer.append("UNREAD")
        self.gmail.users().messages().modify(
            userId="me", id=mail_id, body={"addLabelIds": ajouter, "removeLabelIds": retirer}
        ).execute()

    def marquer_lu(self, mail_id: str) -> None:
        self.gmail.users().messages().modify(
            userId="me", id=mail_id, body={"removeLabelIds": ["UNREAD"]}
        ).execute()

    # --- Agenda ----------------------------------------------------------
    def evenements(self, jours: int) -> list[dict]:
        maintenant = datetime.now().astimezone()
        debut = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
        rep = self.agenda.events().list(
            calendarId="primary",
            timeMin=debut.isoformat(),
            timeMax=(debut + timedelta(days=jours)).isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=50,
        ).execute()
        return [convertir_evenement(ev) for ev in rep.get("items", [])]

    def creer_evenement(self, titre: str, debut: str, fin: str, description: str = "") -> dict:
        corps = {
            "summary": titre,
            "description": description,
            "start": {"dateTime": debut},
            "end": {"dateTime": fin},
        }
        ev = self.agenda.events().insert(calendarId="primary", body=corps).execute()
        return convertir_evenement(ev)
