"""Tests de l'assistant vocal (mode démo, sans réseau ni clé API)."""

import base64
import json
from types import SimpleNamespace

import pytest

from assistant_vocal.config import Config
from assistant_vocal.demo import Demo
from assistant_vocal.google_services import convertir_message, extraire_corps
from assistant_vocal.ia import CATEGORIES, IA, tri_sans_ia
from assistant_vocal.serveur import creer_app


@pytest.fixture
def sans_cle(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)


@pytest.fixture
def client(sans_cle, tmp_path):
    cfg = Config(dossier=tmp_path, demo=True)
    source = Demo()
    app = creer_app(cfg, source=source)
    c = app.test_client()
    c.source = source
    return c


def _b64(texte):
    return base64.urlsafe_b64encode(texte.encode()).decode().rstrip("=")


def test_extraire_corps_prefere_texte_brut():
    payload = {"mimeType": "multipart/alternative", "parts": [
        {"mimeType": "text/html", "body": {"data": _b64("<p>Bonjour <b>HTML</b></p>")}},
        {"mimeType": "text/plain", "body": {"data": _b64("Bonjour texte")}},
    ]}
    assert extraire_corps(payload) == "Bonjour texte"


def test_extraire_corps_nettoie_html():
    payload = {"mimeType": "text/html",
               "body": {"data": _b64("<style>x{}</style><p>Salut&nbsp;toi</p><script>alert(1)</script>")}}
    assert extraire_corps(payload) == "Salut\xa0toi"


def test_convertir_message():
    msg = {"id": "42", "threadId": "t", "snippet": "R&amp;D", "labelIds": ["INBOX"], "payload": {
        "headers": [{"name": "From", "value": "Alice <a@x.fr>"}, {"name": "Subject", "value": "Point"},
                    {"name": "Date", "value": "Tue, 18 Nov 2026 09:00:00 +0100"}],
        "mimeType": "text/plain", "body": {"data": _b64("Corps")}}}
    m = convertir_message(msg)
    assert (m["de"], m["objet"], m["extrait"], m["corps"]) == ("Alice <a@x.fr>", "Point", "R&D", "Corps")
    assert m["date"].startswith("2026-11-18T09:00")


def test_tri_sans_ia_categories():
    r = tri_sans_ia(Demo().mails_non_lus(10), "Monsieur")
    cats = {m["id"]: m["categorie"] for m in r["mails"]}
    assert cats["d1"] == "Urgent"
    assert cats["d4"] == "Promotions"
    assert all(c in CATEGORIES for c in cats.values())
    assert "5 mails" in r["resume_oral"]


def test_api_mails_et_tri(client):
    d = client.get("/api/mails").get_json()
    assert len(d["mails"]) == 5 and d["resume_oral"]
    elements = [{"id": "d4", "categorie": "Promotions", "archiver": True},
                {"id": "inconnu", "categorie": "Urgent"},
                {"id": "d1", "categorie": "Catégorie inventée"}]
    r = client.post("/api/mails/trier", json={"elements": elements}).get_json()
    assert r["ranges"] == 1 and set(r["echecs"]) == {"inconnu", "d1"}
    assert client.source.rangements == [{"id": "d4", "categorie": "Promotions", "archiver": True}]
    assert len(client.get("/api/mails").get_json()["mails"]) == 4


def test_api_agenda_et_creation(client):
    d = client.get("/api/agenda").get_json()
    assert len(d["evenements"]) == 3
    bad = client.post("/api/agenda", json={"titre": "X", "debut": "2026-11-20T10:00:00+01:00",
                                           "fin": "2026-11-20T09:00:00+01:00"})
    assert bad.status_code == 400
    ok = client.post("/api/agenda", json={"titre": "Appel", "debut": "2026-11-20T10:00:00+01:00",
                                          "fin": "2026-11-20T10:30:00+01:00"})
    assert ok.status_code == 200 and ok.get_json()["titre"] == "Appel"


def test_api_voix_sans_config(client):
    assert client.post("/api/voix", json={"texte": "bonjour"}).status_code == 404


def test_page_et_etat(client):
    assert b"noyau" in client.get("/").data
    e = client.get("/api/etat").get_json()
    assert e["demo"] is True and e["ia"] is False and e["categories"] == CATEGORIES


def test_ia_appel_claude_simule(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    cfg = Config(dossier=tmp_path)
    ia = IA(cfg)
    sortie = {"resume_oral": "Deux mails.", "mails": [
        {"id": "d1", "resume": "Devis", "categorie": "Urgent", "action": "garder", "raison": "échéance"},
        {"id": "fantome", "resume": "?", "categorie": "À lire", "action": "garder", "raison": ""}]}
    appels = {}

    def create(**kwargs):
        appels.update(kwargs)
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text=json.dumps(sortie))])

    ia._client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    r = ia.trier_mails(Demo().mails_non_lus(2))
    assert [m["id"] for m in r["mails"]] == ["d1"]  # les identifiants inventés sont écartés
    assert appels["model"] == "claude-opus-5-5"
    assert appels["output_config"]["format"]["type"] == "json_schema"
    assert "<mails>" in appels["messages"][0]["content"]


def test_api_ecoute_sans_cle(client):
    assert client.post("/api/ecoute").status_code == 404


def test_api_ecoute_transcrit(sans_cle, tmp_path, monkeypatch):
    import io
    import requests

    appels = {}

    class Rep:
        status_code = 200
        text = ""
        def json(self):
            return {"text": " résume mes mails "}

    def faux_post(url, **kw):
        appels["url"] = url
        appels["data"] = kw["data"]
        return Rep()

    monkeypatch.setattr(requests, "post", faux_post)
    from assistant_vocal.config import Config
    from assistant_vocal.demo import Demo
    c2 = creer_app(Config(dossier=tmp_path, demo=True, elevenlabs_cle="k"), source=Demo()).test_client()
    assert c2.get("/api/etat").get_json()["ecoute_serveur"] is True
    r = c2.post("/api/ecoute", data={"audio": (io.BytesIO(b"son"), "voix.webm")}, content_type="multipart/form-data")
    assert r.get_json() == {"texte": "résume mes mails"}
    assert appels["url"].endswith("/speech-to-text") and appels["data"]["model_id"] == "scribe_v1"
