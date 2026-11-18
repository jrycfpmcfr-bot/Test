"""Comparaison de deux schémas."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from .model import Element, Schema


@dataclass
class Modification:
    tag: str
    categorie: str
    # nom d'attribut -> (ancienne valeur, nouvelle valeur) ; None = absent
    attributs: dict[str, tuple[Optional[str], Optional[str]]] = field(default_factory=dict)
    deplacement: Optional[tuple[tuple[float, float], tuple[float, float]]] = None
    page: Optional[tuple[int, int]] = None


@dataclass
class Renommage:
    ancien: Element
    nouveau: Element


@dataclass
class Resultat:
    a: Schema
    b: Schema
    ajoutes: list[Element] = field(default_factory=list)
    supprimes: list[Element] = field(default_factory=list)
    modifies: list[Modification] = field(default_factory=list)
    renommes: list[Renommage] = field(default_factory=list)
    textes_ajoutes: list[Element] = field(default_factory=list)
    textes_supprimes: list[Element] = field(default_factory=list)
    connexions_ajoutees: list[tuple[str, str]] = field(default_factory=list)
    connexions_supprimees: list[tuple[str, str]] = field(default_factory=list)
    # page -> chemin / image PIL de superposition, rempli par visual.py
    images: dict[int, object] = field(default_factory=dict)
    pixels_differents: dict[int, float] = field(default_factory=dict)

    @property
    def identiques(self) -> bool:
        return not (self.ajoutes or self.supprimes or self.modifies or self.renommes
                    or self.textes_ajoutes or self.textes_supprimes
                    or self.connexions_ajoutees or self.connexions_supprimees
                    or any(v > 0.0005 for v in self.pixels_differents.values()))


def _seuil_deplacement(a: Schema, b: Schema, relatif: float) -> float:
    """Seuil de déplacement : `relatif` × diagonale de la page (ou 5 unités par défaut)."""
    tailles = list(a.pages.values()) + list(b.pages.values())
    if not tailles:
        return 5.0
    diag = max(math.hypot(w, h) for w, h in tailles)
    return relatif * diag if diag > 0 else 5.0


def comparer(a: Schema, b: Schema, seuil_relatif: float = 0.01,
             ignorer_positions: bool = False,
             ignorer_attributs: tuple[str, ...] = ()) -> Resultat:
    r = Resultat(a=a, b=b)
    seuil = _seuil_deplacement(a, b, seuil_relatif)

    tags_a, tags_b = set(a.elements), set(b.elements)
    supprimes = [a.elements[t] for t in sorted(tags_a - tags_b)]
    ajoutes = [b.elements[t] for t in sorted(tags_b - tags_a)]

    for tag in sorted(tags_a & tags_b):
        ea, eb = a.elements[tag], b.elements[tag]
        mod = Modification(tag=tag, categorie=eb.categorie)
        for cle in sorted(set(ea.attributs) | set(eb.attributs)):
            if cle in ignorer_attributs:
                continue
            va, vb = ea.attributs.get(cle), eb.attributs.get(cle)
            if va != vb:
                mod.attributs[cle] = (va, vb)
        if ea.categorie != eb.categorie:
            mod.attributs["Catégorie"] = (ea.categorie, eb.categorie)
        if not ignorer_positions:
            pa, pb = ea.position(), eb.position()
            if pa and pb and (ea.page != eb.page or math.dist(pa, pb) > seuil):
                mod.deplacement = (pa, pb)
                if ea.page != eb.page:
                    mod.page = (ea.page, eb.page)
        if mod.attributs or mod.deplacement:
            r.modifies.append(mod)

    # Détection des renommages : un élément supprimé et un élément ajouté de même
    # catégorie, au même endroit de la même page.
    if not ignorer_positions:
        for s in list(supprimes):
            ps = s.position()
            if ps is None:
                continue
            candidats = [e for e in ajoutes if e.categorie == s.categorie and e.page == s.page
                         and e.position() is not None and math.dist(ps, e.position()) <= seuil]
            if candidats:
                n = min(candidats, key=lambda e: math.dist(ps, e.position()))
                r.renommes.append(Renommage(s, n))
                supprimes.remove(s)
                ajoutes.remove(n)

    r.ajoutes, r.supprimes = ajoutes, supprimes

    # Textes libres : comparaison en multi-ensemble (indépendante de la position)
    ca = Counter(t.tag for t in a.textes)
    cb = Counter(t.tag for t in b.textes)
    for texte, n in (ca - cb).items():
        r.textes_supprimes.extend([t for t in a.textes if t.tag == texte][-n:])
    for texte, n in (cb - ca).items():
        r.textes_ajoutes.extend([t for t in b.textes if t.tag == texte][-n:])

    # Topologie
    renomme = {x.ancien.tag: x.nouveau.tag for x in r.renommes}
    conn_a = {tuple(sorted((renomme.get(x, x), renomme.get(y, y)))) for x, y in a.connexions}
    r.connexions_supprimees = sorted(conn_a - b.connexions)
    r.connexions_ajoutees = sorted(b.connexions - conn_a)
    return r
