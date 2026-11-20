"""Sources de mails et d'agenda : iCloud (IMAP), Google Agenda par lien secret (.ics), et assemblage.

Chaque source expose tout ou partie de : mails_non_lus, ranger, marquer_lu, evenements, creer_evenement.
"""

from __future__ import annotations

import base64
import email
import email.header
import email.policy
import imaplib
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from .config import Config
from .envoi import analyser_desabonnement, construire_reponse, desabonner_un_clic, message_desabonnement
from .google_services import MAX_CORPS, _texte_depuis_html

DOSSIER_RACINE = "Assistant"


class ErreurSource(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Noms de dossiers IMAP : UTF-7 modifié (RFC 3501 §5.1.3), pour « À répondre » etc.
# ---------------------------------------------------------------------------
def utf7_imap(texte: str) -> str:
    res, tampon = [], []

    def vider():
        if tampon:
            brut = "".join(tampon).encode("utf-16-be")
            res.append("&" + base64.b64encode(brut).decode().rstrip("=").replace("/", ",") + "-")
            tampon.clear()

    for c in texte:
        if 0x20 <= ord(c) <= 0x7E:
            vider()
            res.append("&-" if c == "&" else c)
        else:
            tampon.append(c)
    vider()
    return "".join(res)


def _decoder_entete(valeur: str | None) -> str:
    if not valeur:
        return ""
    return " ".join(str(email.header.make_header(email.header.decode_header(valeur))).split())


def message_vers_mail(uid: str, brut: bytes) -> dict:
    msg = email.message_from_bytes(brut, policy=email.policy.default)
    textes, htmls = [], []
    for partie in msg.walk():
        if partie.is_multipart() or partie.get_content_disposition() == "attachment":
            continue
        try:
            contenu = partie.get_content()
        except (LookupError, ValueError):
            continue
        if not isinstance(contenu, str):
            continue
        if partie.get_content_type() == "text/plain":
            textes.append(contenu)
        elif partie.get_content_type() == "text/html":
            htmls.append(_texte_depuis_html(contenu))
    corps = "\n".join(textes) if textes else "\n".join(htmls)
    corps = re.sub(r"[ \t\r\f\v]+", " ", corps)
    corps = re.sub(r"\n\s*\n+", "\n", corps).strip()
    try:
        date = parsedate_to_datetime(msg.get("Date", "")).isoformat()
    except (TypeError, ValueError):
        date = ""
    return {
        "id": uid,
        "de": _decoder_entete(msg.get("From")),
        "objet": _decoder_entete(msg.get("Subject")) or "(sans objet)",
        "date": date,
        "extrait": corps[:180],
        "corps": corps[:MAX_CORPS],
        "repondre_a": _decoder_entete(msg.get("Reply-To")),
        "message_id": (msg.get("Message-ID") or "").strip(),
        "references": " ".join((msg.get("References") or "").split()),
        "desabonnement": analyser_desabonnement(msg.get("List-Unsubscribe"), msg.get("List-Unsubscribe-Post")),
    }


# ---------------------------------------------------------------------------
# iCloud Mail (IMAP + mot de passe pour app)
# ---------------------------------------------------------------------------
class Icloud:
    HOTE, PORT = "imap.mail.me.com", 993

    SMTP_HOTE, SMTP_PORT = "smtp.mail.me.com", 587

    def __init__(self, adresse: str, mot_de_passe: str, imap_factory=None, smtp_factory=None):
        self.adresse = adresse
        self.mot_de_passe = mot_de_passe
        self._factory = imap_factory or (lambda: imaplib.IMAP4_SSL(self.HOTE, self.PORT, timeout=30))
        self._smtp_factory = smtp_factory
        self._dossiers_connus: set[str] = set()

    def _connexion(self):
        imap = self._factory()
        try:
            imap.login(self.adresse, self.mot_de_passe)
        except imaplib.IMAP4.error as e:
            raise ErreurSource(
                "iCloud refuse la connexion : utilisez votre adresse iCloud complète et un "
                "mot de passe pour app (appleid.apple.com), pas votre mot de passe Apple habituel."
            ) from e
        return imap

    def verifier(self) -> None:
        imap = self._connexion()
        imap.logout()

    def mails_non_lus(self, maximum: int) -> list[dict]:
        imap = self._connexion()
        try:
            imap.select("INBOX", readonly=True)
            typ, data = imap.uid("SEARCH", None, "UNSEEN")
            uids = (data[0] or b"").split()[-maximum:][::-1]  # les plus récents d'abord
            mails = []
            for uid in uids:
                typ, rep = imap.uid("FETCH", uid, "(BODY.PEEK[])")  # PEEK : ne marque pas comme lu
                brut = next((p[1] for p in rep if isinstance(p, tuple)), None)
                if brut:
                    mails.append(message_vers_mail(uid.decode(), brut))
            return mails
        finally:
            imap.logout()

    def _assurer_dossier(self, imap, nom: str) -> str:
        code = utf7_imap(nom)
        if code not in self._dossiers_connus:
            imap.create(f'"{code}"')  # sans effet si le dossier existe déjà
            imap.subscribe(f'"{code}"')
            self._dossiers_connus.add(code)
        return code

    def ranger(self, mail_id: str, categorie: str, archiver: bool, marquer_lu: bool) -> None:
        """iCloud n'a pas de libellés : « archiver » déplace dans Assistant/<catégorie>,
        sinon le mail reste dans la boîte de réception (et un mail Urgent reçoit un drapeau)."""
        imap = self._connexion()
        try:
            imap.select("INBOX")
            uid = mail_id.encode()
            if marquer_lu:
                imap.uid("STORE", uid, "+FLAGS", r"(\Seen)")
            if not archiver:
                if categorie == "Urgent":
                    imap.uid("STORE", uid, "+FLAGS", r"(\Flagged)")
                return
            dossier = self._assurer_dossier(imap, f"{DOSSIER_RACINE}/{categorie}")
            capacites = {str(c).upper() for c in imap.capabilities}
            if "MOVE" in capacites:
                typ, _ = imap.uid("MOVE", uid, f'"{dossier}"')
            else:
                typ, _ = imap.uid("COPY", uid, f'"{dossier}"')
                if typ == "OK":
                    imap.uid("STORE", uid, "+FLAGS", r"(\Deleted)")
                    imap.expunge()
            if typ != "OK":
                raise ErreurSource(f"Déplacement vers {categorie} refusé par iCloud.")
        finally:
            imap.logout()

    def _envoyer(self, msg) -> None:
        import smtplib

        try:
            smtp = self._smtp_factory() if self._smtp_factory else smtplib.SMTP(self.SMTP_HOTE, self.SMTP_PORT, timeout=30)
            with smtp:
                smtp.starttls()
                smtp.login(self.adresse, self.mot_de_passe)
                smtp.send_message(msg)
        except smtplib.SMTPAuthenticationError as e:
            raise ErreurSource("iCloud refuse l'envoi : vérifiez le mot de passe pour app.") from e
        except (smtplib.SMTPException, OSError) as e:
            raise ErreurSource(f"Envoi impossible : {e}") from e

    def repondre(self, mail: dict, texte: str) -> None:
        self._envoyer(construire_reponse(mail, texte, self.adresse))
        if mail.get("id"):  # la réponse est partie : on marque l'original comme lu
            try:
                self.marquer_lu(mail["id"])
            except ErreurSource:
                pass

    def desabonner(self, mail: dict, poster=None) -> str:
        d = mail.get("desabonnement") or {}
        if d.get("un_clic") and desabonner_un_clic(d["https"], poster):
            return "fait"
        if d.get("mailto"):
            self._envoyer(message_desabonnement(d["mailto"], self.adresse))
            return "fait"
        if d.get("https"):
            return d["https"]  # page à ouvrir : l'expéditeur ne propose pas de désabonnement automatique
        raise ErreurSource("Ce mail ne propose pas de désabonnement.")

    def marquer_lu(self, mail_id: str) -> None:
        imap = self._connexion()
        try:
            imap.select("INBOX")
            imap.uid("STORE", mail_id.encode(), "+FLAGS", r"(\Seen)")
        finally:
            imap.logout()


# ---------------------------------------------------------------------------
# Google Agenda par « adresse secrète au format iCal » (lecture seule, sans Google Cloud)
# ---------------------------------------------------------------------------
class AgendaIcs:
    def __init__(self, url: str, telecharger=None):
        self.url = re.sub(r"^webcal://", "https://", url.strip())
        self._telecharger = telecharger

    def _contenu(self) -> bytes:
        if self._telecharger:
            return self._telecharger(self.url)
        import requests

        r = requests.get(self.url, timeout=30)
        if r.status_code != 200:
            raise ErreurSource(f"Lien d'agenda refusé ({r.status_code}) : recopiez l'adresse secrète iCal.")
        return r.content

    def evenements(self, jours: int) -> list[dict]:
        import icalendar
        import recurring_ical_events

        cal = icalendar.Calendar.from_ical(self._contenu())
        maintenant = datetime.now().astimezone()
        debut = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
        fin = debut + timedelta(days=jours)
        sortie = []
        for ev in recurring_ical_events.of(cal).between(debut, fin):
            d, f = ev.get("DTSTART").dt, (ev.get("DTEND").dt if ev.get("DTEND") else None)
            journee = not isinstance(d, datetime)
            if not journee and d.tzinfo is None:
                d = d.astimezone()
            if f is not None and not journee and isinstance(f, datetime) and f.tzinfo is None:
                f = f.astimezone()
            sortie.append({
                "id": str(ev.get("UID", "")),
                "titre": str(ev.get("SUMMARY", "(sans titre)")),
                "debut": d.isoformat(),
                "fin": (f or d).isoformat(),
                "journee_entiere": journee,
                "lieu": str(ev.get("LOCATION", "") or ""),
                "description": str(ev.get("DESCRIPTION", "") or "")[:500],
            })
        sortie.sort(key=lambda e: e["debut"] if "T" in e["debut"] else e["debut"] + "T00:00")
        return sortie

    def creer_evenement(self, *_a, **_k):
        raise ErreurSource("Avec le lien secret, l'agenda est en lecture seule : pour ajouter des "
                           "rendez-vous, activez l'accès Google complet (voir la notice).")


# ---------------------------------------------------------------------------
# Assemblage : plusieurs boîtes mail + un agenda
# ---------------------------------------------------------------------------
class Assemblage:
    def __init__(self, boites: dict[str, object], agenda=None):
        self.boites = boites  # préfixe -> source ; les identifiants deviennent « préfixe:id »
        self.agenda = agenda
        self.erreurs: list[str] = []

    def _boite(self, mail_id: str):
        prefixe, _, ident = mail_id.partition(":")
        if prefixe not in self.boites:
            raise ErreurSource("Mail inconnu.")
        return self.boites[prefixe], ident

    def mails_non_lus(self, maximum: int) -> list[dict]:
        tous, self.erreurs = [], []
        for prefixe, src in self.boites.items():
            try:
                for m in src.mails_non_lus(maximum):
                    tous.append(dict(m, id=f"{prefixe}:{m['id']}", boite=prefixe))
            except Exception as e:  # une boîte en panne ne bloque pas l'autre
                self.erreurs.append(f"{prefixe} : {e}")
        if not tous and self.erreurs:
            raise ErreurSource(" ; ".join(self.erreurs))
        tous.sort(key=lambda m: m.get("date") or "", reverse=True)
        return tous[:maximum]

    def ranger(self, mail_id, categorie, archiver, marquer_lu):
        src, ident = self._boite(mail_id)
        src.ranger(ident, categorie, archiver, marquer_lu)

    def marquer_lu(self, mail_id):
        src, ident = self._boite(mail_id)
        src.marquer_lu(ident)

    def repondre(self, mail: dict, texte: str):
        src, ident = self._boite(mail["id"])
        src.repondre(dict(mail, id=ident), texte)

    def desabonner(self, mail: dict) -> str:
        src, ident = self._boite(mail["id"])
        return src.desabonner(dict(mail, id=ident))

    @property
    def agenda_modifiable(self) -> bool:
        return self.agenda is not None and not isinstance(self.agenda, AgendaIcs)

    def evenements(self, jours):
        if self.agenda is None:
            return []
        return self.agenda.evenements(jours)

    def creer_evenement(self, titre, debut, fin, description=""):
        if self.agenda is None:
            raise ErreurSource("Aucun agenda configuré.")
        return self.agenda.creer_evenement(titre, debut, fin, description)


def construire_source(cfg: Config):
    """Assemble les sources configurées ; None si aucune (mode démo)."""
    boites, agenda, google = {}, None, None
    if cfg.icloud_adresse and cfg.icloud_mot_de_passe:
        boites["icloud"] = Icloud(cfg.icloud_adresse, cfg.icloud_mot_de_passe)
    if cfg.credentials_google.is_file():
        from .google_services import Google

        google = Google(cfg)
        if cfg.gmail_actif:
            boites["gmail"] = google
        agenda = google  # accès complet : lecture et ajout de rendez-vous
    if agenda is None and cfg.agenda_ics:
        agenda = AgendaIcs(cfg.agenda_ics)  # lien secret : lecture seule
    if not boites and agenda is None:
        return None, None
    return Assemblage(boites, agenda), google
