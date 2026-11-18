"""Choix automatique du lecteur selon l'extension du fichier."""

from __future__ import annotations

import os

from ..model import Schema
from ..tags import Classifieur

EXT_IMAGES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"}


def detecter_format(chemin: str) -> str:
    ext = os.path.splitext(chemin)[1].lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".xml", ".dexpi"):
        return "dexpi"
    if ext == ".dxf":
        return "dxf"
    if ext in EXT_IMAGES:
        return "image"
    if ext == ".dwg":
        raise SystemExit("Les fichiers DWG ne sont pas lisibles directement : "
                         "convertissez-les en DXF ou en PDF.")
    raise SystemExit(f"Format non reconnu pour {chemin} (attendu : PDF, XML DEXPI, DXF, image).")


def lire(chemin: str, classifieur: Classifieur, ocr: bool = True) -> Schema:
    if not os.path.isfile(chemin):
        raise SystemExit(f"Fichier introuvable : {chemin}")
    fmt = detecter_format(chemin)
    if fmt == "pdf":
        from .pdf import lire_pdf
        return lire_pdf(chemin, classifieur)
    if fmt == "dexpi":
        from .dexpi import lire_dexpi
        return lire_dexpi(chemin)
    if fmt == "dxf":
        from .dxf import lire_dxf
        return lire_dxf(chemin, classifieur)
    from .image import lire_image
    return lire_image(chemin, classifieur, ocr=ocr)
