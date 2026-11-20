"""Tests des sources iCloud (IMAP simulé), agenda par lien secret et assemblage."""

from datetime import datetime, timedelta

import pytest

from assistant_vocal.sources import AgendaIcs, Assemblage, ErreurSource, Icloud, utf7_imap

MAIL = (
    "From: =?utf-8?q?C=C3=A9line_Roux?= <celine@exemple.fr>\r\n"
    "Subject: =?utf-8?q?R=C3=A9union_demain_?=\r\n"
    "Date: Thu, 19 Nov 2026 09:00:00 +0100\r\n"
    "Content-Type: text/plain; charset=utf-8\r\n\r\n"
    "Bonjour, on se voit demain à 10 h ?\r\n"
).encode()


class FauxImap:
    def __init__(self, refuser=False):
        self.refuser, self.journal, self.capabilities = refuser, [], ("IMAP4REV1", "MOVE")

    def login(self, u, p):
        import imaplib
        if self.refuser:
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")

    def select(self, boite, readonly=False):
        self.journal.append(("select", boite, readonly))
        return "OK", [b"2"]

    def uid(self, cmd, *args):
        self.journal.append((cmd, *args))
        if cmd == "SEARCH":
            return "OK", [b"7 8"]
        if cmd == "FETCH":
            return "OK", [(b"1 (BODY[] {10}", MAIL), b")"]
        return "OK", [None]

    def create(self, nom):
        self.journal.append(("create", nom))

    def subscribe(self, nom):
        pass

    def expunge(self):
        self.journal.append(("expunge",))

    def logout(self):
        pass


def test_utf7_imap():
    assert utf7_imap("Assistant/À répondre") == "Assistant/&AMA- r&AOk-pondre"
    assert utf7_imap("Entwürfe") == "Entw&APw-rfe"
    assert utf7_imap("A&B") == "A&-B"


def test_icloud_lecture_sans_marquer_lu():
    faux = FauxImap()
    mails = Icloud("moi@icloud.com", "abcd", imap_factory=lambda: faux).mails_non_lus(10)
    assert [m["id"] for m in mails] == ["8", "7"]  # plus récent d'abord
    assert mails[0]["de"] == "Céline Roux <celine@exemple.fr>" and mails[0]["objet"] == "Réunion demain"
    assert "10 h" in mails[0]["corps"]
    assert ("select", "INBOX", True) in faux.journal  # lecture seule
    assert all(a[2] == "(BODY.PEEK[])" for a in faux.journal if a[0] == "FETCH")


def test_icloud_rangement():
    faux = FauxImap()
    ic = Icloud("moi@icloud.com", "abcd", imap_factory=lambda: faux)
    ic.ranger("8", "À répondre", archiver=True, marquer_lu=True)
    assert ("create", '"Assistant/&AMA- r&AOk-pondre"') in faux.journal
    assert ("MOVE", b"8", '"Assistant/&AMA- r&AOk-pondre"') in faux.journal
    assert ("STORE", b"8", "+FLAGS", r"(\Seen)") in faux.journal
    faux.journal.clear()
    ic.ranger("9", "Urgent", archiver=False, marquer_lu=False)
    assert faux.journal[-1] == ("STORE", b"9", "+FLAGS", r"(\Flagged)")


def test_icloud_mauvais_mot_de_passe():
    with pytest.raises(ErreurSource, match="mot de passe pour app"):
        Icloud("moi@icloud.com", "x", imap_factory=lambda: FauxImap(refuser=True)).mails_non_lus(5)


def test_agenda_ics_recurrent():
    demain = (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    debut = demain - timedelta(days=7)
    ics = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:test\r\n"
        "BEGIN:VEVENT\r\nUID:sport\r\nSUMMARY:Sport\r\n"
        f"DTSTART:{debut:%Y%m%dT%H%M%S}\r\nDTEND:{debut + timedelta(hours=1):%Y%m%dT%H%M%S}\r\n"
        "RRULE:FREQ=WEEKLY\r\nEND:VEVENT\r\n"
        "BEGIN:VEVENT\r\nUID:ferie\r\nSUMMARY:Jour férié\r\n"
        f"DTSTART;VALUE=DATE:{demain:%Y%m%d}\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    ).encode()
    evs = AgendaIcs("webcal://exemple/secret.ics", telecharger=lambda url: ics).evenements(7)
    titres = [e["titre"] for e in evs]
    assert "Sport" in titres and "Jour férié" in titres
    sport = next(e for e in evs if e["titre"] == "Sport")
    assert sport["debut"].startswith(demain.strftime("%Y-%m-%dT09:00"))
    assert next(e for e in evs if e["titre"] == "Jour férié")["journee_entiere"] is True
    with pytest.raises(ErreurSource, match="lecture seule"):
        AgendaIcs("https://x").creer_evenement("a", "b", "c")


def test_assemblage_prefixe_et_panne_partielle():
    class Ok:
        def __init__(self):
            self.ranges = []
        def mails_non_lus(self, n):
            return [{"id": "1", "date": "2026-11-19T10:00:00+01:00"}]
        def ranger(self, *a):
            self.ranges.append(a)

    class Panne:
        def mails_non_lus(self, n):
            raise RuntimeError("hors ligne")

    ok = Ok()
    a = Assemblage({"icloud": ok, "gmail": Panne()})
    mails = a.mails_non_lus(10)
    assert [m["id"] for m in mails] == ["icloud:1"] and mails[0]["boite"] == "icloud"
    assert a.erreurs == ["gmail : hors ligne"]
    a.ranger("icloud:1", "Urgent", False, False)
    assert ok.ranges == [("1", "Urgent", False, False)]
    with pytest.raises(ErreurSource):
        Assemblage({"gmail": Panne()}).mails_non_lus(5)


def test_envoi_reponse_et_desabonnement():
    from assistant_vocal.envoi import analyser_desabonnement, construire_reponse, message_desabonnement
    mail = {"id": "8", "de": "Céline Roux <celine@exemple.fr>", "objet": "Réunion demain",
            "message_id": "<abc@exemple.fr>", "references": "<zzz@exemple.fr>", "repondre_a": ""}
    m = construire_reponse(mail, "Oui, à demain.", "moi@icloud.com")
    assert m["To"] == "Céline Roux <celine@exemple.fr>" and m["Subject"] == "Re: Réunion demain"
    assert m["In-Reply-To"] == "<abc@exemple.fr>" and m["References"] == "<zzz@exemple.fr> <abc@exemple.fr>"
    d = analyser_desabonnement("<mailto:quit@liste.fr?subject=stop>, <https://liste.fr/u/1>", "List-Unsubscribe=One-Click")
    assert d == {"https": "https://liste.fr/u/1", "mailto": "mailto:quit@liste.fr?subject=stop", "un_clic": True}
    assert analyser_desabonnement("<http://non-securise.fr>", None) is None
    q = message_desabonnement("mailto:quit@liste.fr?subject=stop", "moi@icloud.com")
    assert q["To"] == "quit@liste.fr" and q["Subject"] == "stop"


def test_icloud_repond_par_smtp():
    envoyes = []

    class FauxSmtp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def starttls(self): envoyes.append("tls")
        def login(self, u, p): envoyes.append(("login", u))
        def send_message(self, m): envoyes.append(m)

    faux = FauxImap()
    ic = Icloud("moi@icloud.com", "pw", imap_factory=lambda: faux, smtp_factory=FauxSmtp)
    mails = ic.mails_non_lus(1)
    ic.repondre(mails[0], "Oui, 10 h me va.")
    assert envoyes[0] == "tls" and envoyes[1] == ("login", "moi@icloud.com")
    assert envoyes[2]["To"] == "Céline Roux <celine@exemple.fr>" and "10 h" in envoyes[2].get_content()
    assert ("STORE", b"8", "+FLAGS", r"(\Seen)") in faux.journal  # original marqué lu


def test_icloud_desabonnement_un_clic():
    from types import SimpleNamespace
    appels = []
    ic = Icloud("moi@icloud.com", "pw", imap_factory=FauxImap)
    mail = {"desabonnement": {"https": "https://liste.fr/u/1", "mailto": None, "un_clic": True}}
    poster = lambda url, **kw: appels.append((url, kw["data"])) or SimpleNamespace(status_code=200)
    assert ic.desabonner(mail, poster=poster) == "fait"
    assert appels == [("https://liste.fr/u/1", {"List-Unsubscribe": "One-Click"})]
    sans = {"desabonnement": {"https": "https://liste.fr/page", "mailto": None, "un_clic": False}}
    assert ic.desabonner(sans) == "https://liste.fr/page"  # à ouvrir soi-même
