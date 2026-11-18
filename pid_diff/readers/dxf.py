"""Lecture des P&ID au format DXF (AutoCAD). Nécessite le paquet « ezdxf ».

- Les blocs (INSERT) porteurs d'attributs (TAG, REPERE, NAME...) deviennent des
  éléments, avec tous leurs attributs comparés.
- Les textes libres (TEXT / MTEXT) sont analysés comme pour un PDF.
Les fichiers DWG doivent d'abord être convertis en DXF (ODA File Converter).
"""

from __future__ import annotations

from ..model import AUTRE, Element, Schema
from ..tags import Classifieur, Mot
from .texte import mots_vers_schema

ATTRIBUTS_TAG = ("TAG", "TAGNAME", "TAG_NAME", "REPERE", "REPÈRE", "NAME", "NUMBER", "NUMERO", "ID")


def lire_dxf(chemin: str, classifieur: Classifieur) -> Schema:
    try:
        import ezdxf
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Le format DXF nécessite « pip install ezdxf ».") from exc

    schema = Schema(source=chemin, format="dxf")
    doc = ezdxf.readfile(chemin)
    msp = doc.modelspace()

    mots: list[Mot] = []
    ymax = 0.0

    def ajouter_texte(texte: str, x: float, y: float, h: float) -> None:
        nonlocal ymax
        ymax = max(ymax, y)
        larg = max(len(texte), 1) * h * 0.8
        # y DXF croît vers le haut : on l'inverse plus bas pour rester cohérent avec le PDF
        mots.append(Mot(texte, x, y, x + larg, y + h, 1))

    for e in msp:
        t = e.dxftype()
        if t == "TEXT":
            p = e.dxf.insert
            ajouter_texte(e.dxf.text, p.x, p.y, e.dxf.get("height", 2.5))
        elif t == "MTEXT":
            p = e.dxf.insert
            for i, ligne in enumerate(e.plain_text().splitlines()):
                h = e.dxf.get("char_height", 2.5)
                ajouter_texte(ligne, p.x, p.y - i * h * 1.5, h)
        elif t == "INSERT":
            attribs = {a.dxf.tag.upper(): a.dxf.text for a in e.attribs}
            tag = next((attribs[k] for k in ATTRIBUTS_TAG if attribs.get(k)), None)
            if tag is None:
                continue
            categorie = classifieur.classer(tag) or AUTRE
            attrs = {k: v for k, v in attribs.items()}
            attrs["Bloc"] = e.dxf.name
            attrs["Rotation"] = f"{e.dxf.get('rotation', 0):g}"
            p = e.dxf.insert
            schema.ajouter(Element(tag=classifieur.tag_canonique(tag), categorie=categorie,
                                   attributs=attrs, x=p.x, y=p.y))

    # Inversion de l'axe y pour que « haut » = petit y comme en PDF
    for m in mots:
        m.y0, m.y1 = ymax - m.y1, ymax - m.y0
    mots_vers_schema(schema, mots, classifieur)
    return schema
