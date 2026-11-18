"""Lecture des P&ID scannés (PNG, JPG, TIFF...).

Par défaut seule la comparaison visuelle est possible. Si « pytesseract » et
Tesseract OCR sont installés, le texte est extrait pour comparer les repères.
"""

from __future__ import annotations

from PIL import Image

from ..model import Schema
from ..tags import Classifieur, Mot
from .texte import mots_vers_schema


def lire_image(chemin: str, classifieur: Classifieur, ocr: bool = True) -> Schema:
    schema = Schema(source=chemin, format="image")
    img = Image.open(chemin)
    schema.pages[1] = (float(img.width), float(img.height))
    if not ocr:
        return schema
    try:
        import pytesseract
        donnees = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except Exception:  # pytesseract absent ou binaire tesseract introuvable
        schema.avertissements.append(
            f"{chemin} : OCR indisponible (installer tesseract + pytesseract) ; "
            "seule la comparaison visuelle est réalisée.")
        return schema
    mots = []
    for i, texte in enumerate(donnees["text"]):
        if texte.strip() and float(donnees["conf"][i]) > 50:
            x, y, w, h = (donnees[k][i] for k in ("left", "top", "width", "height"))
            mots.append(Mot(texte, x, y, x + w, y + h, 1))
    mots_vers_schema(schema, mots, classifieur)
    return schema


def charger_pages_image(chemin: str):
    img = Image.open(chemin)
    pages = []
    i = 0
    while True:  # TIFF multipage
        try:
            img.seek(i)
        except EOFError:
            break
        pages.append(img.convert("L").copy())
        i += 1
    return pages
