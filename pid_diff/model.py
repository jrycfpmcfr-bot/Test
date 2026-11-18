"""Modèle de données commun à tous les formats de P&ID."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# Catégories d'éléments reconnues
EQUIPEMENT = "equipement"
INSTRUMENT = "instrument"
LIGNE = "ligne"
VANNE = "vanne"
AUTRE = "autre"
TEXTE = "texte"


@dataclass
class Element:
    """Un élément identifiable d'un P&ID (équipement, instrument, ligne...)."""

    tag: str
    categorie: str = AUTRE
    attributs: dict[str, str] = field(default_factory=dict)
    page: int = 1
    x: Optional[float] = None
    y: Optional[float] = None
    # Zone occupée (x0, y0, x1, y1) dans le repère du document, si connue
    bbox: Optional[tuple[float, float, float, float]] = None

    def position(self) -> Optional[tuple[float, float]]:
        if self.x is None or self.y is None:
            return None
        return (self.x, self.y)


@dataclass
class Schema:
    """Contenu extrait d'un fichier P&ID."""

    source: str
    format: str
    elements: dict[str, Element] = field(default_factory=dict)
    # Textes libres (notes, cartouche...) qui ne sont pas des repères
    textes: list[Element] = field(default_factory=list)
    # Connexions entre éléments : ensemble de paires (tag_a, tag_b) triées
    connexions: set[tuple[str, str]] = field(default_factory=set)
    # Taille des pages (largeur, hauteur) dans le repère du document
    pages: dict[int, tuple[float, float]] = field(default_factory=dict)
    avertissements: list[str] = field(default_factory=list)

    def ajouter(self, element: Element) -> None:
        """Ajoute un élément ; en cas de doublon de repère on suffixe #2, #3..."""
        tag = element.tag
        if tag in self.elements:
            n = 2
            while f"{tag}#{n}" in self.elements:
                n += 1
            element.tag = f"{tag}#{n}"
        self.elements[element.tag] = element

    def ajouter_connexion(self, a: str, b: str) -> None:
        if a and b and a != b:
            self.connexions.add(tuple(sorted((a, b))))  # type: ignore[arg-type]
