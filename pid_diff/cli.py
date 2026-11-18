"""Interface en ligne de commande.

Exemple :
    python -m pid_diff ancien.pdf nouveau.pdf --html rapport.html
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .diff import comparer
from .readers import lire
from .report import afficher_console, ecrire_csv, ecrire_html, ecrire_images, ecrire_json
from .tags import Classifieur


def construire_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pid_diff",
        description="Lit deux schémas P&ID et liste leurs différences "
                    "(repères ajoutés/supprimés/modifiés, connexions, textes, superposition visuelle). "
                    "Formats : PDF vectoriel, DEXPI XML, DXF, image (PNG/JPG/TIFF).",
    )
    p.add_argument("ancien", help="P&ID de référence (ancienne révision)")
    p.add_argument("nouveau", help="P&ID à comparer (nouvelle révision)")
    p.add_argument("--html", metavar="FICHIER", help="rapport HTML avec superposition visuelle")
    p.add_argument("--json", metavar="FICHIER", help="export JSON des différences")
    p.add_argument("--csv", metavar="FICHIER", help="export CSV (séparateur ;) pour Excel")
    p.add_argument("--images", metavar="DOSSIER", help="enregistre les superpositions PNG par page")
    p.add_argument("--config", metavar="FICHIER",
                   help="JSON de motifs de repères personnalisés (voir README)")
    p.add_argument("--dpi", type=int, default=100, help="résolution de la comparaison visuelle (défaut 100)")
    p.add_argument("--tolerance", type=int, default=1,
                   help="tolérance de décalage en pixels pour la comparaison visuelle (défaut 1)")
    p.add_argument("--seuil-deplacement", type=float, default=0.01,
                   help="déplacement signalé au-delà de cette fraction de la diagonale de page (défaut 0.01)")
    p.add_argument("--ignorer-positions", action="store_true",
                   help="ne pas signaler les déplacements ni chercher les renommages")
    p.add_argument("--ignorer-attribut", action="append", default=[], metavar="NOM",
                   help="attribut à ne pas comparer (répétable)")
    p.add_argument("--sans-visuel", action="store_true", help="désactive la comparaison visuelle")
    p.add_argument("--sans-textes", action="store_true", help="n'affiche pas les textes libres modifiés")
    p.add_argument("--sans-ocr", action="store_true", help="n'essaie pas l'OCR sur les images")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construire_parser().parse_args(argv)
    classifieur = Classifieur.depuis_fichier(args.config)

    a = lire(args.ancien, classifieur, ocr=not args.sans_ocr)
    b = lire(args.nouveau, classifieur, ocr=not args.sans_ocr)
    r = comparer(a, b, seuil_relatif=args.seuil_deplacement,
                 ignorer_positions=args.ignorer_positions,
                 ignorer_attributs=tuple(args.ignorer_attribut))
    if args.sans_textes:
        r.textes_ajoutes, r.textes_supprimes = [], []

    if not args.sans_visuel and (args.html or args.images or a.format == b.format == "image"):
        from .visual import comparaison_visuelle
        comparaison_visuelle(r, dpi=args.dpi, tolerance=args.tolerance)

    afficher_console(r, textes=not args.sans_textes)

    if args.json:
        ecrire_json(r, args.json)
        print(f"\nJSON écrit : {args.json}")
    if args.csv:
        ecrire_csv(r, args.csv)
        print(f"CSV écrit : {args.csv}")
    if args.images:
        for c in ecrire_images(r, args.images):
            print(f"Image écrite : {c}")
    if args.html:
        ecrire_html(r, args.html)
        print(f"Rapport HTML écrit : {args.html}")

    # Code retour façon « diff » : 0 = identiques, 1 = différences
    return 0 if r.identiques else 1


if __name__ == "__main__":
    sys.exit(main())
