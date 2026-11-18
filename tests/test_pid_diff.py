import os
import subprocess
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from pid_diff import Classifieur, comparer, lire  # noqa: E402
from pid_diff.model import EQUIPEMENT, INSTRUMENT, LIGNE, VANNE  # noqa: E402
from pid_diff.tags import Mot, fusionner_bulles  # noqa: E402

EX = os.path.join(RACINE, "exemples")


@pytest.fixture(scope="session", autouse=True)
def exemples():
    subprocess.run([sys.executable, os.path.join(EX, "generer_exemples.py")], check=True,
                   capture_output=True)


@pytest.mark.parametrize("texte,attendu", [
    ("P-101A", EQUIPEMENT), ("V-200", EQUIPEMENT), ("TK-01", EQUIPEMENT),
    ("FIC-101", INSTRUMENT), ("PT 2001", INSTRUMENT), ("LSHH-300", INSTRUMENT),
    ("XV-2001", VANNE), ("PSV-101", VANNE), ("HV-12", VANNE),
    ('6"-P-1001-A1A', LIGNE), ("DN150-PW-1001-B2", LIGNE),
    ("NOTE 1", None), ("REV A", None), ("101", None),
])
def test_classification(texte, attendu):
    assert Classifieur().classer(texte) == attendu


def test_tag_canonique():
    c = Classifieur()
    assert c.tag_canonique("fic 101") == "FIC-101"
    assert c.tag_canonique("FIC101") == "FIC-101"


def test_fusion_bulle():
    mots = [Mot("FIC", 100, 100, 112, 108), Mot("101", 101, 109, 113, 117)]
    assert [m.texte for m in fusionner_bulles(mots)] == ["FIC-101"]


def _cmp(ext):
    c = Classifieur()
    return comparer(lire(os.path.join(EX, f"pid_revA.{ext}"), c),
                    lire(os.path.join(EX, f"pid_revB.{ext}"), c))


def test_pdf():
    r = _cmp("pdf")
    assert {e.tag for e in r.ajoutes} == {"P-101B", '3"-P-1003-A1A'}
    assert {e.tag for e in r.supprimes} == {"LT-102"}
    assert [(x.ancien.tag, x.nouveau.tag) for x in r.renommes] == [("HV-104", "HV-105")]
    assert [m.tag for m in r.modifies] == ["PI-103"] and r.modifies[0].deplacement
    assert any("HV-105" in t.tag for t in r.textes_ajoutes)


def test_dexpi():
    r = _cmp("xml")
    assert {e.tag for e in r.ajoutes} == {"P-101B", '3"-P-1003-A1A'}
    assert {e.tag for e in r.supprimes} == {"LT-102"}
    mods = {m.tag: m.attributs for m in r.modifies}
    assert mods["V-101"]["DesignPressure"] == ("10 bar", "12 bar")
    assert mods["FV-101"]["FailAction"] == ("FC", "FO")
    assert ('3"-P-1003-A1A', "V-101/N1") in r.connexions_ajoutees


def test_dxf():
    pytest.importorskip("ezdxf")
    r = _cmp("dxf")
    assert {e.tag for e in r.ajoutes} == {"P-101B"}
    assert {e.tag for e in r.supprimes} == {"LT-102"}


def test_identiques_et_code_retour(tmp_path):
    a = os.path.join(EX, "pid_revA.pdf")
    html = tmp_path / "r.html"
    p = subprocess.run([sys.executable, "-m", "pid_diff", a, a, "--html", str(html)],
                       cwd=RACINE, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "Aucune différence" in p.stdout
    p = subprocess.run([sys.executable, "-m", "pid_diff", a, os.path.join(EX, "pid_revB.pdf"),
                        "--html", str(html), "--json", str(tmp_path / "r.json")],
                       cwd=RACINE, capture_output=True, text=True)
    assert p.returncode == 1
    assert "data:image/png;base64" in html.read_text(encoding="utf-8")
