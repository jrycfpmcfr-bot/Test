"""Lecture des P&ID au format DEXPI / Proteus XML (norme ISO 15926 / DEXPI 1.x).

C'est le format le plus riche : il contient les repères, les classes
d'objets, les attributs (diamètre, pression de calcul...) et la topologie
(qui est connecté à qui).
"""

from __future__ import annotations

from typing import Optional

from lxml import etree

from ..model import AUTRE, EQUIPEMENT, INSTRUMENT, LIGNE, VANNE, Element, Schema

# Balise Proteus -> catégorie
CATEGORIES = {
    "Equipment": EQUIPEMENT,
    "Nozzle": AUTRE,
    "PipingNetworkSystem": LIGNE,
    "PipingComponent": VANNE,
    "ProcessInstrumentationFunction": INSTRUMENT,
    "ProcessSignalGeneratingFunction": INSTRUMENT,
    "InstrumentComponent": INSTRUMENT,
    "InstrumentationLoopFunction": INSTRUMENT,
    "ActuatingFunction": INSTRUMENT,
    "ActuatingSystem": INSTRUMENT,
}

NOMS_ATTRIBUT_TAG = (
    "TagNameAssignmentClass", "TagName", "ProcessInstrumentationFunctionNumber",
    "PipingNetworkSystemNumber", "PipingComponentNumber", "EquipmentNumber",
    "LineNumberAssignmentClass", "SubTagName", "NozzleNumber",
)


def _local(tag) -> str:
    return etree.QName(tag).localname if isinstance(tag, str) else ""


def _attributs_generiques(el) -> dict[str, str]:
    """Attributs génériques directement rattachés à l'élément (pas à ses enfants)."""
    res: dict[str, str] = {}
    for ga_group in el:
        if _local(ga_group.tag) != "GenericAttributes":
            continue
        for ga in ga_group:
            if _local(ga.tag) != "GenericAttribute":
                continue
            nom = ga.get("Name")
            if not nom:
                continue
            valeur = ga.get("Value", "")
            unite = ga.get("Units")
            if unite:
                valeur = f"{valeur} {unite}"
            res[nom] = valeur
    return res


def _tag(el, attrs: dict[str, str]) -> Optional[str]:
    if el.get("TagName"):
        return el.get("TagName")
    for nom in NOMS_ATTRIBUT_TAG:
        for cle, val in attrs.items():
            if cle.startswith(nom) and val:
                return val
    return None


def _position(el) -> Optional[tuple[float, float]]:
    for enfant in el:
        if _local(enfant.tag) == "Position":
            for loc in enfant:
                if _local(loc.tag) == "Location":
                    try:
                        return float(loc.get("X")), float(loc.get("Y"))
                    except (TypeError, ValueError):
                        return None
    return None


def lire_dexpi(chemin: str) -> Schema:
    schema = Schema(source=chemin, format="dexpi")
    arbre = etree.parse(chemin)
    racine = arbre.getroot()

    drawing = next((e for e in racine.iter() if _local(e.tag) == "Drawing"), None)
    if drawing is not None:
        ext = next((e for e in drawing if _local(e.tag) == "Extent"), None)
        if ext is not None:
            mx = next((e for e in ext if _local(e.tag) == "Max"), None)
            if mx is not None:
                schema.pages[1] = (float(mx.get("X", 0)), float(mx.get("Y", 0)))

    id_vers_tag: dict[str, str] = {}

    for el in racine.iter():
        nom_balise = _local(el.tag)
        if nom_balise not in CATEGORIES:
            continue
        attrs = _attributs_generiques(el)
        ident = el.get("ID", "")
        tag = _tag(el, attrs)
        if nom_balise == "Nozzle":
            # Une tubulure est identifiée par l'équipement parent + son numéro
            parent = el.getparent()
            parent_tag = _tag(parent, _attributs_generiques(parent)) if parent is not None else None
            if parent_tag:
                tag = f"{parent_tag}/{tag or ident}"
        if not tag:
            tag = f"[{el.get('ComponentClass', nom_balise)} {ident}]"

        if el.get("ComponentClass"):
            attrs["Classe"] = el.get("ComponentClass")
        for cle in ("ComponentName", "StockNumber"):
            if el.get(cle):
                attrs[cle] = el.get(cle)

        pos = _position(el)
        element = Element(tag=tag, categorie=CATEGORIES[nom_balise], attributs=attrs,
                          x=pos[0] if pos else None, y=pos[1] if pos else None)
        schema.ajouter(element)
        if ident:
            id_vers_tag[ident] = element.tag

    # Topologie : balises <Connection FromID=".." ToID=".."> et
    # <Association Type="is connected to" ItemID="..">
    for el in racine.iter():
        nom_balise = _local(el.tag)
        if nom_balise == "Connection":
            a, b = id_vers_tag.get(el.get("FromID", "")), id_vers_tag.get(el.get("ToID", ""))
            # La connexion appartient à un segment de tuyauterie : on relie la
            # ligne (PipingNetworkSystem) à chacune de ses extrémités.
            ligne = next((id_vers_tag.get(p.get("ID", "")) for p in el.iterancestors()
                          if _local(p.tag) == "PipingNetworkSystem"), None)
            if ligne:
                for extremite in (a, b):
                    if extremite:
                        schema.ajouter_connexion(ligne, extremite)
            elif a and b:
                schema.ajouter_connexion(a, b)
        elif nom_balise == "Association" and "connected" in (el.get("Type") or "").lower():
            parent = el.getparent()
            a = id_vers_tag.get(parent.get("ID", "")) if parent is not None else None
            b = id_vers_tag.get(el.get("ItemID", ""))
            if a and b:
                schema.ajouter_connexion(a, b)
        elif nom_balise == "Association" and (el.get("Type") or "") in (
                "is location of", "is logical end of", "is a collection including"):
            # Rattachements instrument -> ligne / équipement
            parent = el.getparent()
            a = id_vers_tag.get(parent.get("ID", "")) if parent is not None else None
            b = id_vers_tag.get(el.get("ItemID", ""))
            if a and b:
                schema.ajouter_connexion(a, b)

    if not schema.elements:
        schema.avertissements.append(f"{chemin} : aucun objet DEXPI reconnu.")
    return schema
