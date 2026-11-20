"""Réponses aux mails et désabonnement des listes de diffusion."""

from __future__ import annotations

import re
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from urllib.parse import unquote, urlparse


def analyser_desabonnement(entete: str | None, entete_post: str | None) -> dict | None:
    """Lit List-Unsubscribe / List-Unsubscribe-Post (RFC 2369 et 8058)."""
    if not entete:
        return None
    liens = re.findall(r"<([^>]+)>", entete)
    https = next((l for l in liens if l.lower().startswith("https://")), None)
    mailto = next((l for l in liens if l.lower().startswith("mailto:")), None)
    if not https and not mailto:
        return None
    un_clic = bool(https and entete_post and "one-click" in entete_post.lower())
    return {"https": https, "mailto": mailto, "un_clic": un_clic}


def construire_reponse(mail: dict, texte: str, de: str) -> EmailMessage:
    """Réponse à `mail` (dict d'une source) écrite par `de` (adresse de l'utilisateur)."""
    destinataire = mail.get("repondre_a") or mail.get("de", "")
    nom, adresse = parseaddr(destinataire)
    if not adresse:
        raise ValueError("Adresse de l'expéditeur introuvable.")
    objet = mail.get("objet", "")
    msg = EmailMessage()
    msg["From"] = de
    msg["To"] = formataddr((nom, adresse))
    msg["Subject"] = objet if objet.lower().startswith(("re:", "re :")) else f"Re: {objet}"
    msg["Message-ID"] = make_msgid(domain=de.split("@")[-1] if "@" in de else None)
    if mail.get("message_id"):
        msg["In-Reply-To"] = mail["message_id"]
        msg["References"] = " ".join(x for x in [mail.get("references", ""), mail["message_id"]] if x).strip()
    msg.set_content(texte.strip() + "\n")
    return msg


def message_desabonnement(mailto: str, de: str) -> EmailMessage:
    lien = urlparse(mailto)
    msg = EmailMessage()
    msg["From"] = de
    msg["To"] = unquote(lien.path)
    params = dict(p.split("=", 1) for p in lien.query.split("&") if "=" in p)
    msg["Subject"] = unquote(params.get("subject", "unsubscribe"))
    msg.set_content(unquote(params.get("body", "unsubscribe")))
    return msg


def desabonner_un_clic(url: str, poster=None) -> bool:
    """POST « List-Unsubscribe=One-Click » vers l'adresse fournie par l'expéditeur."""
    if not url.lower().startswith("https://"):
        return False
    if poster is None:
        import requests
        poster = requests.post
    r = poster(url, data={"List-Unsubscribe": "One-Click"}, timeout=20, allow_redirects=False)
    return 200 <= r.status_code < 400
