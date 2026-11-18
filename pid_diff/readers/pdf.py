"""Lecture des P&ID au format PDF vectoriel (export AutoCAD Plant 3D, SmartPlant, AVEVA...).

Seul le texte est exploité pour l'analyse des repères ; la comparaison des
traits (tuyauteries, symboles) est faite par la comparaison visuelle.
Un PDF scanné (image seule) ne contient pas de texte : utiliser alors la
comparaison visuelle, ou installer Tesseract pour l'OCR.
"""

from __future__ import annotations

from ..model import Schema
from ..tags import Classifieur, Mot
from .texte import mots_vers_schema


def lire_pdf(chemin: str, classifieur: Classifieur) -> Schema:
    import pdfplumber

    schema = Schema(source=chemin, format="pdf")
    mots: list[Mot] = []
    with pdfplumber.open(chemin) as pdf:
        for num, page in enumerate(pdf.pages, start=1):
            schema.pages[num] = (float(page.width), float(page.height))
            for w in page.extract_words(keep_blank_chars=False, use_text_flow=False,
                                        extra_attrs=["size"]):
                mots.append(Mot(w["text"], float(w["x0"]), float(w["top"]),
                                float(w["x1"]), float(w["bottom"]), num))
    if not mots:
        schema.avertissements.append(
            f"{chemin} : aucun texte trouvé (PDF scanné ?). Seule la comparaison visuelle est possible.")
    mots_vers_schema(schema, mots, classifieur)
    return schema


def rendre_pages_pdf(chemin: str, dpi: int = 100):
    """Rend chaque page en image PIL (niveaux de gris)."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(chemin)
    images = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            img = page.render(scale=dpi / 72).to_pil().convert("L")
            images.append(img)
    finally:
        doc.close()
    return images
