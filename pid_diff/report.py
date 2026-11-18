"""Mise en forme des résultats : console, JSON, CSV et HTML."""

from __future__ import annotations

import base64
import csv
import html
import io
import json
import os
import sys

from .diff import Resultat

LIBELLES = {
    "equipement": "Équipement", "instrument": "Instrument", "ligne": "Ligne",
    "vanne": "Vanne", "autre": "Autre", "texte": "Texte",
}


def _lib(cat: str) -> str:
    return LIBELLES.get(cat, cat)


def _pos(p) -> str:
    return f"({p[0]:.0f}, {p[1]:.0f})"


def lignes_differences(r: Resultat) -> list[dict]:
    """Liste à plat de toutes les différences (base des sorties CSV/JSON)."""
    out: list[dict] = []
    for e in r.ajoutes:
        out.append({"type": "AJOUTÉ", "categorie": _lib(e.categorie), "repere": e.tag,
                    "page": e.page, "detail": ", ".join(f"{k}={v}" for k, v in e.attributs.items())})
    for e in r.supprimes:
        out.append({"type": "SUPPRIMÉ", "categorie": _lib(e.categorie), "repere": e.tag,
                    "page": e.page, "detail": ", ".join(f"{k}={v}" for k, v in e.attributs.items())})
    for rn in r.renommes:
        out.append({"type": "RENOMMÉ", "categorie": _lib(rn.nouveau.categorie),
                    "repere": rn.nouveau.tag, "page": rn.nouveau.page,
                    "detail": f"{rn.ancien.tag} → {rn.nouveau.tag}"})
    for m in r.modifies:
        details = [f"{k} : {a if a is not None else '∅'} → {b if b is not None else '∅'}"
                   for k, (a, b) in m.attributs.items()]
        if m.deplacement:
            txt = f"déplacé {_pos(m.deplacement[0])} → {_pos(m.deplacement[1])}"
            if m.page:
                txt += f" (page {m.page[0]} → {m.page[1]})"
            details.append(txt)
        out.append({"type": "MODIFIÉ", "categorie": _lib(m.categorie), "repere": m.tag,
                    "page": r.b.elements[m.tag].page, "detail": " ; ".join(details)})
    for a, b in r.connexions_ajoutees:
        out.append({"type": "CONNEXION AJOUTÉE", "categorie": "Topologie",
                    "repere": f"{a} ↔ {b}", "page": "", "detail": ""})
    for a, b in r.connexions_supprimees:
        out.append({"type": "CONNEXION SUPPRIMÉE", "categorie": "Topologie",
                    "repere": f"{a} ↔ {b}", "page": "", "detail": ""})
    for t in r.textes_ajoutes:
        out.append({"type": "TEXTE AJOUTÉ", "categorie": "Texte", "repere": t.tag,
                    "page": t.page, "detail": ""})
    for t in r.textes_supprimes:
        out.append({"type": "TEXTE SUPPRIMÉ", "categorie": "Texte", "repere": t.tag,
                    "page": t.page, "detail": ""})
    return out


# ---------------------------------------------------------------- console

def _couleurs_actives() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def afficher_console(r: Resultat, textes: bool = True) -> None:
    c = _couleurs_actives()
    V, R, O, B, G, Z = (("\033[32m", "\033[31m", "\033[33m", "\033[34m", "\033[1m", "\033[0m")
                        if c else ("",) * 6)

    print(f"{G}Comparaison de P&ID{Z}")
    print(f"  Ancien : {r.a.source}  ({r.a.format}, {len(r.a.elements)} repères)")
    print(f"  Nouveau: {r.b.source}  ({r.b.format}, {len(r.b.elements)} repères)")
    for w in r.a.avertissements + r.b.avertissements:
        print(f"  {O}⚠ {w}{Z}")
    print()

    def section(titre, items, couleur, fmt):
        if not items:
            return
        print(f"{G}{couleur}{titre} ({len(items)}){Z}")
        for it in items:
            print(f"  {couleur}{fmt(it)}{Z}")
        print()

    section("+ Ajoutés", r.ajoutes, V,
            lambda e: f"+ [{_lib(e.categorie)}] {e.tag}" + (f"  (p.{e.page})" if e.page > 1 else ""))
    section("- Supprimés", r.supprimes, R,
            lambda e: f"- [{_lib(e.categorie)}] {e.tag}" + (f"  (p.{e.page})" if e.page > 1 else ""))
    section("~ Renommés", r.renommes, B,
            lambda x: f"~ [{_lib(x.nouveau.categorie)}] {x.ancien.tag} → {x.nouveau.tag}")

    if r.modifies:
        print(f"{G}{O}~ Modifiés ({len(r.modifies)}){Z}")
        for m in r.modifies:
            print(f"  {O}~ [{_lib(m.categorie)}] {m.tag}{Z}")
            for k, (a, b) in m.attributs.items():
                print(f"      {k} : {R}{a if a is not None else '∅'}{Z} → {V}{b if b is not None else '∅'}{Z}")
            if m.deplacement:
                print(f"      position : {_pos(m.deplacement[0])} → {_pos(m.deplacement[1])}"
                      + (f" (page {m.page[0]} → {m.page[1]})" if m.page else ""))
        print()

    section("+ Connexions ajoutées", r.connexions_ajoutees, V, lambda c_: f"+ {c_[0]} ↔ {c_[1]}")
    section("- Connexions supprimées", r.connexions_supprimees, R, lambda c_: f"- {c_[0]} ↔ {c_[1]}")
    if textes:
        section("+ Textes ajoutés", r.textes_ajoutes, V, lambda t: f'+ "{t.tag}"')
        section("- Textes supprimés", r.textes_supprimes, R, lambda t: f'- "{t.tag}"')

    for page, frac in sorted(r.pixels_differents.items()):
        print(f"Page {page} : {frac:.2%} du dessin diffère visuellement")
    if r.pixels_differents:
        print()

    if r.identiques:
        print(f"{G}{V}Aucune différence détectée.{Z}")
    else:
        print(f"{G}Résumé :{Z} {len(r.ajoutes)} ajouté(s), {len(r.supprimes)} supprimé(s), "
              f"{len(r.modifies)} modifié(s), {len(r.renommes)} renommé(s), "
              f"{len(r.connexions_ajoutees) + len(r.connexions_supprimees)} changement(s) de connexion, "
              f"{len(r.textes_ajoutes) + len(r.textes_supprimes)} changement(s) de texte.")


# ---------------------------------------------------------------- fichiers

def ecrire_json(r: Resultat, chemin: str) -> None:
    data = {
        "ancien": r.a.source, "nouveau": r.b.source,
        "identiques": r.identiques,
        "differences": lignes_differences(r),
        "pixels_differents": {str(k): v for k, v in r.pixels_differents.items()},
        "avertissements": r.a.avertissements + r.b.avertissements,
    }
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ecrire_csv(r: Resultat, chemin: str) -> None:
    # Séparateur « ; » et BOM UTF-8 pour une ouverture directe dans Excel (FR)
    with open(chemin, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["type", "categorie", "repere", "page", "detail"],
                           delimiter=";")
        w.writeheader()
        w.writerows(lignes_differences(r))


def ecrire_images(r: Resultat, dossier: str) -> list[str]:
    os.makedirs(dossier, exist_ok=True)
    chemins = []
    for page, img in sorted(r.images.items()):
        p = os.path.join(dossier, f"diff_page_{page}.png")
        img.save(p)
        chemins.append(p)
    return chemins


_CSS = """
:root{--fond:#fff;--texte:#1d1d1f;--doux:#6b6b70;--ligne:#e3e3e6;--ajout:#178a2e;--supp:#c62828;
--modif:#c86e00;--renom:#1f5bd6;--carte:#f7f7f9}
@media (prefers-color-scheme:dark){:root{--fond:#16161a;--texte:#ececf0;--doux:#a0a0a8;--ligne:#2c2c33;
--ajout:#4cc764;--supp:#ff6b6b;--modif:#ffb03a;--renom:#79a6ff;--carte:#1f1f25}}
body{background:var(--fond);color:var(--texte);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;
margin:0;padding:24px 16px;max-width:1200px;margin-inline:auto}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}
.meta{color:var(--doux);font-size:13px}
.tuiles{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}
.tuile{background:var(--carte);border:1px solid var(--ligne);border-radius:8px;padding:10px 14px;min-width:110px}
.tuile b{display:block;font-size:22px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--ligne);vertical-align:top}
th{color:var(--doux);font-weight:600}
.t{font-weight:600;white-space:nowrap}
.AJOUTÉ,.CONNEXION.AJOUTÉE,.TEXTE.AJOUTÉ{color:var(--ajout)}
.SUPPRIMÉ,.CONNEXION.SUPPRIMÉE,.TEXTE.SUPPRIMÉ{color:var(--supp)}
.MODIFIÉ{color:var(--modif)}.RENOMMÉ{color:var(--renom)}
.tbl{overflow-x:auto}
img{max-width:100%;border:1px solid var(--ligne);border-radius:6px;background:#fff}
.legende span{display:inline-block;margin-right:14px;font-size:13px}
.pastille{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:middle}
.warn{color:var(--modif)}
"""


def ecrire_html(r: Resultat, chemin: str) -> None:
    lignes = lignes_differences(r)
    e = html.escape
    nb = {
        "Ajoutés": len(r.ajoutes), "Supprimés": len(r.supprimes),
        "Modifiés": len(r.modifies), "Renommés": len(r.renommes),
        "Connexions": len(r.connexions_ajoutees) + len(r.connexions_supprimees),
        "Textes": len(r.textes_ajoutes) + len(r.textes_supprimes),
    }
    parts = [
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>Différences P&amp;ID</title><style>{_CSS}</style></head><body>",
        "<h1>Différences entre deux P&amp;ID</h1>",
        f"<div class='meta'>Ancien : {e(r.a.source)} ({e(r.a.format)}) &nbsp;·&nbsp; "
        f"Nouveau : {e(r.b.source)} ({e(r.b.format)})</div>",
    ]
    for w in r.a.avertissements + r.b.avertissements:
        parts.append(f"<p class='warn'>⚠ {e(w)}</p>")
    parts.append("<div class='tuiles'>" + "".join(
        f"<div class='tuile'><b>{v}</b>{k}</div>" for k, v in nb.items()) + "</div>")

    if lignes:
        parts.append("<h2>Liste des différences</h2><div class='tbl'><table>"
                     "<tr><th>Type</th><th>Catégorie</th><th>Repère</th><th>Page</th><th>Détail</th></tr>")
        for l in lignes:
            parts.append(f"<tr><td class='t {e(l['type'])}'>{e(l['type'])}</td><td>{e(l['categorie'])}</td>"
                         f"<td><code>{e(str(l['repere']))}</code></td><td>{e(str(l['page']))}</td>"
                         f"<td>{e(l['detail'])}</td></tr>")
        parts.append("</table></div>")
    else:
        parts.append("<p>Aucune différence de repère ou de texte détectée.</p>")

    if r.images:
        parts.append("<h2>Superposition visuelle</h2><div class='legende'>"
                     "<span><i class='pastille' style='background:#dc1e1e'></i>Supprimé</span>"
                     "<span><i class='pastille' style='background:#14a028'></i>Ajouté</span>"
                     "<span><i class='pastille' style='background:#f08c00'></i>Modifié / déplacé</span>"
                     "<span><i class='pastille' style='background:#1e5ae6'></i>Renommé</span>"
                     "<span><i class='pastille' style='background:#bebebe'></i>Inchangé</span></div>")
        for page, img in sorted(r.images.items()):
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode()
            frac = r.pixels_differents.get(page, 0)
            parts.append(f"<h2>Page {page} <span class='meta'>— {frac:.2%} du dessin diffère</span></h2>"
                         f"<img alt='Superposition page {page}' src='data:image/png;base64,{b64}'>")
    parts.append("</body></html>")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
