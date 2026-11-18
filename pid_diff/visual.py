"""Comparaison visuelle : superposition des deux révisions.

Code couleur de l'image produite :
  - gris   : inchangé
  - rouge  : présent uniquement dans l'ancienne révision (supprimé)
  - vert   : présent uniquement dans la nouvelle révision (ajouté)
  - cadres : rouge = repère supprimé, vert = ajouté, orange = modifié/déplacé, bleu = renommé
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .diff import Resultat

ROUGE = (220, 30, 30)
VERT = (20, 160, 40)
ORANGE = (240, 140, 0)
BLEU = (30, 90, 230)
GRIS = (190, 190, 190)


def _pages(chemin: str, fmt: str, dpi: int):
    if fmt == "pdf":
        from .readers.pdf import rendre_pages_pdf
        return rendre_pages_pdf(chemin, dpi), dpi / 72
    if fmt == "image":
        from .readers.image import charger_pages_image
        return charger_pages_image(chemin), 1.0
    return None, 1.0


def superposer(img_a: Image.Image, img_b: Image.Image, tolerance: int = 1):
    """Retourne (image RGB de superposition, fraction de pixels différents)."""
    if img_b.size != img_a.size:
        img_b = img_b.resize(img_a.size, Image.LANCZOS)
    noir_a = np.asarray(img_a) < 160
    noir_b = np.asarray(img_b) < 160
    if tolerance > 0:
        k = 2 * tolerance + 1
        large_a = np.asarray(img_a.filter(ImageFilter.MinFilter(k))) < 160
        large_b = np.asarray(img_b.filter(ImageFilter.MinFilter(k))) < 160
    else:
        large_a, large_b = noir_a, noir_b
    seul_a = noir_a & ~large_b
    seul_b = noir_b & ~large_a
    commun = (noir_a | noir_b) & ~seul_a & ~seul_b

    sortie = np.full(noir_a.shape + (3,), 255, dtype=np.uint8)
    sortie[commun] = GRIS
    sortie[seul_a] = ROUGE
    sortie[seul_b] = VERT
    total = max(int((noir_a | noir_b).sum()), 1)
    return Image.fromarray(sortie), float((seul_a.sum() + seul_b.sum()) / total)


def _cadre(draw: ImageDraw.ImageDraw, el, echelle: float, couleur, marge: float = 4) -> None:
    if el.bbox is None:
        return
    x0, y0, x1, y1 = (v * echelle for v in el.bbox)
    draw.rectangle([x0 - marge, y0 - marge, x1 + marge, y1 + marge], outline=couleur, width=3)


def comparaison_visuelle(r: Resultat, dpi: int = 100, tolerance: int = 1) -> None:
    pages_a, ech_a = _pages(r.a.source, r.a.format, dpi)
    pages_b, ech_b = _pages(r.b.source, r.b.format, dpi)
    if not pages_a or not pages_b:
        return
    if len(pages_a) != len(pages_b):
        r.a.avertissements.append(
            f"Nombre de pages différent : {len(pages_a)} (ancien) / {len(pages_b)} (nouveau).")

    for i, (pa, pb) in enumerate(zip(pages_a, pages_b), start=1):
        img, frac = superposer(pa, pb, tolerance)
        draw = ImageDraw.Draw(img)
        # Rapport d'échelle si la page B a été redimensionnée
        fb = ech_b * (pa.width / pb.width)
        for el in r.supprimes + r.textes_supprimes:
            if el.page == i:
                _cadre(draw, el, ech_a, ROUGE)
        for el in r.ajoutes + r.textes_ajoutes:
            if el.page == i:
                _cadre(draw, el, fb, VERT)
        for m in r.modifies:
            el = r.b.elements[m.tag]
            if el.page == i:
                _cadre(draw, el, fb, ORANGE)
        for rn in r.renommes:
            if rn.nouveau.page == i:
                _cadre(draw, rn.nouveau, fb, BLEU)
        r.images[i] = img
        r.pixels_differents[i] = frac
