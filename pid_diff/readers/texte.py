"""Transformation d'une liste de mots positionnés en éléments de P&ID.

Utilisé par les lecteurs PDF et DXF (et image si l'OCR est disponible).
"""

from __future__ import annotations

from ..model import TEXTE, Element, Schema
from ..tags import Classifieur, Mot, fusionner, fusionner_bulles, regrouper_lignes


def mots_vers_schema(schema: Schema, mots: list[Mot], classifieur: Classifieur) -> None:
    mots = fusionner_bulles([m for m in mots if m.texte.strip()])

    for groupe in regrouper_lignes(mots):
        groupe.sort(key=lambda m: m.x0)
        ligne = fusionner(groupe)
        # 1. la ligne entière est un repère : « FIC 101 », « 6" - P - 1001 »
        if _ajouter_si_tag(schema, ligne, classifieur):
            continue
        # 2. plusieurs repères côte à côte : « FV-101 FIC-101 »
        if len(groupe) > 1 and all(classifieur.classer(m.texte) for m in groupe):
            for m in groupe:
                _ajouter_si_tag(schema, m, classifieur)
            continue
        # 3. sinon c'est un texte libre (note, cartouche...) ; un repère cité
        #    dans une note n'est pas un objet du schéma.
        schema.textes.append(Element(
            tag=ligne.texte.strip(), categorie=TEXTE, page=ligne.page,
            x=ligne.cx, y=ligne.cy, bbox=(ligne.x0, ligne.y0, ligne.x1, ligne.y1),
        ))


def _ajouter_si_tag(schema: Schema, m: Mot, classifieur: Classifieur) -> bool:
    cat = classifieur.classer(m.texte)
    if cat is None:
        return False
    schema.ajouter(Element(
        tag=classifieur.tag_canonique(m.texte), categorie=cat, page=m.page,
        x=m.cx, y=m.cy, bbox=(m.x0, m.y0, m.x1, m.y1),
    ))
    return True
