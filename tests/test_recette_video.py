import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from recette_video import analyse, app as appli, extraction


@pytest.fixture(scope="module")
def video(tmp_path_factory) -> Path:
    """Vidéo de test de 12 s avec une piste audio (bip)."""
    chemin = tmp_path_factory.mktemp("v") / "test.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc=size=640x360:rate=10:duration=12",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
         "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(chemin)],
        check=True,
    )
    return chemin


def recette_exemple() -> analyse.Recette:
    return analyse.Recette(
        est_une_recette=True, titre="Crêpes", resume="Des crêpes.", portions="4", temps_preparation="10 min",
        temps_cuisson="20 min", temps_total="30 min", difficulte="facile",
        ingredients=[analyse.Ingredient(nom="farine", quantite="250", unite="g", precision="",
                                        sources=["description"], estimee=False)],
        ustensiles=["poêle"],
        etapes=[analyse.Etape(numero=1, instruction="Mélangez.", duree="", temperature="", image=0)],
        astuces=[], apports_commentaires=["Ajouter une pincée de sel"], incertitudes=[],
    )


def test_nombre_images():
    assert extraction.nombre_images(0) == 8
    assert extraction.nombre_images(15) == 8
    assert extraction.nombre_images(60) == 20
    assert extraction.nombre_images(600) == 30


def test_images_et_audio(video, tmp_path):
    duree, a_audio = extraction.duree_et_audio(video)
    assert 11.5 < duree < 12.5 and a_audio
    images = extraction.extraire_images(video, tmp_path / "img", duree)
    assert len(images) == 8
    assert all(im.chemin.stat().st_size > 0 for im in images)
    assert images[0].seconde < images[-1].seconde < duree
    audio = extraction.extraire_audio(video, tmp_path)
    assert audio.stat().st_size > 100_000


def test_commentaires_colles():
    c = extraction.commentaires_depuis_texte("chef_marie: 200 g de farine\n\nTrop bon : je refais demain")
    assert c[0].auteur == "chef_marie" and c[0].texte == "200 g de farine"
    assert c[1].auteur == "" and c[1].texte.startswith("Trop bon")


def test_message_contient_toutes_les_sources(video, tmp_path):
    contenu = extraction.ContenuVideo(
        dossier=tmp_path, video=video, titre="Crêpes", auteur="chef_marie", duree=12,
        description="Recette en commentaire", transcription="[  1.0s] on met la farine",
        commentaires=[extraction.Commentaire("paul", "sel ?", 1), extraction.Commentaire("chef_marie", "250 g", 9)],
    )
    contenu.images = extraction.extraire_images(video, tmp_path / "img", 12)
    message = analyse.construire_message(contenu)[0]["content"]
    assert sum(b["type"] == "image" for b in message) == 8
    texte = "\n".join(b["text"] for b in message if b["type"] == "text")
    assert "Image 0 —" in texte
    assert "on met la farine" in texte
    assert "Recette en commentaire" in texte
    # les commentaires sont triés par « j'aime » et ceux de l'auteur sont signalés
    assert texte.index("chef_marie [AUTEUR DE LA VIDÉO]") < texte.index("paul")


def test_parcours_complet_avec_fichier(video, monkeypatch):
    appele = {}

    def faux_claude(contenu):
        appele["contenu"] = contenu
        return recette_exemple()

    monkeypatch.setattr(analyse, "rediger_recette", faux_claude)
    monkeypatch.setattr(extraction, "transcrire", lambda audio: ("[  0.0s] bonjour", "fr"))

    client = TestClient(appli.app)
    with video.open("rb") as f:
        r = client.post("/api/analyses", data={"commentaires": "paul: super"},
                        files={"video": ("crepes.mp4", f, "video/mp4")})
    assert r.status_code == 200, r.text
    id_ = r.json()["id"]
    for _ in range(100):
        t = client.get(f"/api/analyses/{id_}").json()
        if t["etat"] != "en_cours":
            break
        time.sleep(0.1)
    assert t["etat"] == "termine", t
    assert t["recette"]["titre"] == "Crêpes"
    assert t["transcription"] == "[  0.0s] bonjour"
    assert t["nb_commentaires"] == 1
    assert client.get(f"/api/analyses/{id_}/images/0").headers["content-type"] == "image/jpeg"
    assert appele["contenu"].commentaires[0].texte == "super"


def test_requete_invalide():
    client = TestClient(appli.app)
    assert client.post("/api/analyses", data={"url": ""}).status_code == 400
    assert client.post("/api/analyses", data={"url": "ftp://x"}).status_code == 400
    assert "Recette Vidéo" in client.get("/").text


def test_appel_claude(video, tmp_path):
    """Vérifie les paramètres envoyés à l'API, sans appel réseau."""
    recu = {}

    class FauxMessages:
        def parse(self, **kw):
            recu.update(kw)
            return SimpleNamespace(stop_reason="end_turn", parsed_output=recette_exemple())

    faux = SimpleNamespace(beta=SimpleNamespace(messages=FauxMessages()))
    contenu = extraction.ContenuVideo(dossier=tmp_path, video=video)
    assert analyse.rediger_recette(contenu, client=faux).titre == "Crêpes"
    assert recu["model"] == "claude-opus-5-5" and recu["output_format"] is analyse.Recette


def test_mot_de_passe(monkeypatch):
    client = TestClient(appli.app)
    monkeypatch.setenv("APP_PASSWORD", "secret")
    assert client.get("/").status_code == 401
    assert client.get("/", auth=("moi", "faux")).status_code == 401
    assert client.get("/", auth=("moi", "secret")).status_code == 200
    assert client.get("/sante").status_code == 200
    monkeypatch.delenv("APP_PASSWORD")
    assert client.get("/").status_code == 200
