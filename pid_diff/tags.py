"""Reconnaissance des repères (tags) dans du texte libre et regroupement des mots.

Les P&ID issus de PDF ou de DXF ne contiennent que du texte positionné : il
faut donc deviner quels textes sont des repères d'équipements, d'instruments ou
de lignes. Les expressions régulières ci-dessous suivent les conventions les plus
courantes (ISA 5.1 pour les instruments) et peuvent être surchargées via un
fichier de configuration JSON (voir README).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from .model import AUTRE, EQUIPEMENT, INSTRUMENT, LIGNE, VANNE

# Motifs par défaut. L'ordre compte : le premier motif qui correspond gagne.
MOTIFS_DEFAUT: list[tuple[str, str]] = [
    # Lignes : 6"-P-1001-A1A, DN150-PW-1001-B2, 2"-HC-2003, 150-PL-101
    (LIGNE, r'^(?:\d+(?:[.,/]\d+)?\s*(?:"|in|IN)|DN\s?\d+|\d{2,4})-[A-Z]{1,4}-\d{2,6}(?:-[A-Z0-9]+)*$'),
    # Équipements à préfixe de 2 lettres qui seraient sinon pris pour des instruments
    (EQUIPEMENT, r"^(?:TK|HX|EX|CT|DR|PK|AG|BL|PU|VE|CL|FU|SK)-\d{2,5}[A-Z]?$"),
    # Vannes manuelles / tout-ou-rien : HV-101, XV-2001, MV-12, PSV-101, PCV-12
    (VANNE, r"^(?:[A-Z]{1,2}V|PSV|PRV|TSV|[FLPT]CV|BDV|SDV|ESDV|NRV|CV)-?\d{2,6}[A-Z]?$"),
    # Instruments ISA : FT-101, FIC 2001, LSHH-300, PDT-12A, TI101
    (INSTRUMENT, r"^[ABCDEFHIJKLMPQRSTUVWXYZ][A-Z]{1,4}[- ]?\d{2,6}[A-Z]?$"),
    # Équipements : P-101A, V-200, E-301, TK-01, HX-100, C-101, K-200
    (EQUIPEMENT, r"^(?:[A-Z]{1,3})-\d{2,5}[A-Z]?(?:/[A-Z])?$"),
]


@dataclass
class Mot:
    texte: str
    x0: float
    y0: float  # haut (repère avec y croissant vers le bas)
    x1: float
    y1: float
    page: int = 1

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def hauteur(self) -> float:
        return max(self.y1 - self.y0, 0.1)


class Classifieur:
    """Classe un texte en catégorie de repère (ou None si ce n'est pas un repère)."""

    def __init__(self, motifs: Optional[list[tuple[str, str]]] = None,
                 ignorer: Optional[list[str]] = None):
        self.motifs = [(cat, re.compile(m)) for cat, m in (motifs or MOTIFS_DEFAUT)]
        self.ignorer = [re.compile(m) for m in (ignorer or [])]

    @classmethod
    def depuis_fichier(cls, chemin: Optional[str]) -> "Classifieur":
        if not chemin:
            return cls()
        with open(chemin, encoding="utf-8") as f:
            conf = json.load(f)
        motifs = conf.get("motifs")
        if motifs is not None:
            motifs = [(m["categorie"], m["regex"]) for m in motifs]
        return cls(motifs=motifs, ignorer=conf.get("ignorer"))

    @staticmethod
    def normaliser(texte: str) -> str:
        t = texte.strip().upper()
        t = t.replace("–", "-").replace("—", "-").replace("”", '"').replace("''", '"')
        t = re.sub(r"\s*-\s*", "-", t)
        t = re.sub(r"\s+", " ", t)
        return t

    def classer(self, texte: str) -> Optional[str]:
        t = self.normaliser(texte)
        if any(r.search(t) for r in self.ignorer):
            return None
        for cat, regex in self.motifs:
            if regex.match(t):
                return cat
        return None

    def tag_canonique(self, texte: str) -> str:
        """Forme canonique : 'FIC 101' et 'FIC101' deviennent 'FIC-101'."""
        t = self.normaliser(texte)
        m = re.match(r"^([A-Z]{1,5})[ ]?(\d{2,6}[A-Z]?)$", t)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
        return t


_LETTRES = re.compile(r"^[A-Z]{1,5}$")
_NUMERO = re.compile(r"^\d{2,6}[A-Z]?$")


def fusionner_bulles(mots: list[Mot]) -> list[Mot]:
    """Fusionne les instruments écrits sur deux lignes dans une bulle ISA.

    Exemple : « FIC » au-dessus de « 101 », centrés l'un sur l'autre → « FIC-101 ».
    """
    utilises: set[int] = set()
    resultat: list[Mot] = []
    lettres = [(i, m) for i, m in enumerate(mots) if _LETTRES.match(m.texte.strip().upper())]
    numeros = [(i, m) for i, m in enumerate(mots) if _NUMERO.match(m.texte.strip().upper())]

    for i, haut in lettres:
        meilleur: Optional[tuple[float, int, Mot]] = None
        for j, bas in numeros:
            if j in utilises or bas.page != haut.page:
                continue
            h = max(haut.hauteur, bas.hauteur)
            dy = bas.y0 - haut.y1           # écart vertical (bas sous haut)
            dx = abs(bas.cx - haut.cx)      # décalage horizontal des centres
            if -0.3 * h <= dy <= 1.2 * h and dx <= 1.5 * h:
                score = dx + abs(dy)
                if meilleur is None or score < meilleur[0]:
                    meilleur = (score, j, bas)
        if meilleur is not None:
            _, j, bas = meilleur
            utilises.update({i, j})
            resultat.append(Mot(
                texte=f"{haut.texte.strip()}-{bas.texte.strip()}",
                x0=min(haut.x0, bas.x0), y0=haut.y0,
                x1=max(haut.x1, bas.x1), y1=bas.y1, page=haut.page,
            ))

    resultat.extend(m for k, m in enumerate(mots) if k not in utilises)
    return resultat


def regrouper_lignes(mots: Iterable[Mot]) -> list[list[Mot]]:
    """Regroupe les mots voisins d'une même ligne de texte (« FIC 101 », notes...)."""
    tries = sorted(mots, key=lambda m: (m.page, m.cy, m.x0))
    lignes: list[list[Mot]] = []
    for m in tries:
        rattache = False
        for groupe in reversed(lignes[-50:]):
            d = groupe[-1]
            if (d.page == m.page and abs(d.cy - m.cy) < 0.5 * m.hauteur
                    and -0.2 * m.hauteur <= m.x0 - d.x1 < 1.5 * m.hauteur):
                groupe.append(m)
                rattache = True
                break
        if not rattache:
            lignes.append([m])
    return lignes


def fusionner(groupe: list[Mot]) -> Mot:
    return Mot(" ".join(m.texte for m in groupe),
               min(m.x0 for m in groupe), min(m.y0 for m in groupe),
               max(m.x1 for m in groupe), max(m.y1 for m in groupe), groupe[0].page)
