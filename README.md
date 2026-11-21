# pid_diff — comparaison de deux schémas P&ID

Programme Python qui lit deux révisions d'un P&ID et liste leurs différences :

- **repères ajoutés / supprimés** (équipements, instruments, vannes, lignes) ;
- **repères renommés** (ex. `HV-104 → HV-105` au même endroit) ;
- **attributs modifiés** (pression de calcul, diamètre, position de sécurité…) ;
- **éléments déplacés** sur le plan ;
- **connexions modifiées** (topologie, format DEXPI) ;
- **textes / notes modifiés** (cartouche, notes) ;
- **superposition visuelle** : rouge = supprimé, vert = ajouté, gris = inchangé.

## Formats lus

| Format | Ce qui est comparé |
|---|---|
| **PDF vectoriel** (export Plant 3D, SmartPlant, AVEVA…) | repères et textes + superposition visuelle |
| **DEXPI / Proteus XML** | objets, tous leurs attributs et la topologie — le plus précis |
| **DXF** (AutoCAD) | blocs avec attributs (TAG…) + textes |
| **Image** PNG / JPG / TIFF (scan) | superposition visuelle ; repères si Tesseract OCR est installé |

Les DWG doivent être convertis en DXF ou en PDF au préalable.

## Installation

```bash
pip install -r requirements.txt
```

## Utilisation

```bash
python -m pid_diff ancien.pdf nouveau.pdf
python -m pid_diff ancien.pdf nouveau.pdf --html rapport.html --csv differences.csv
python -m pid_diff rev_A.xml rev_B.xml --json differences.json
```

Exemple de sortie :

```
+ Ajoutés (2)
  + [Ligne] 3"-P-1003-A1A
  + [Équipement] P-101B
- Supprimés (1)
  - [Instrument] LT-102
~ Renommés (1)
  ~ [Vanne] HV-104 → HV-105
~ Modifiés (1)
  ~ [Instrument] PI-103
      position : (520, 563) → (560, 553)
```

Options utiles :

| Option | Rôle |
|---|---|
| `--html FICHIER` | rapport HTML avec tableau et superposition visuelle de chaque page |
| `--csv FICHIER` | tableau des différences pour Excel (séparateur `;`) |
| `--json FICHIER` | export JSON |
| `--images DOSSIER` | superpositions PNG par page |
| `--ignorer-positions` | ne signale pas les déplacements |
| `--ignorer-attribut NOM` | n'analyse pas cet attribut (répétable) |
| `--seuil-deplacement 0.01` | déplacement minimal signalé (fraction de la diagonale de page) |
| `--dpi 150` / `--tolerance 2` | finesse / tolérance de la comparaison visuelle |
| `--sans-textes`, `--sans-visuel` | allège le rapport |
| `--config motifs.json` | règles de reconnaissance des repères propres à votre projet |

Code retour : `0` si les schémas sont identiques, `1` s'il y a des différences.

## Exemples fournis

`exemples/` contient deux révisions d'un même P&ID en PDF, DEXPI et DXF
(régénérables avec `python exemples/generer_exemples.py`, nécessite `reportlab`) :

```bash
python -m pid_diff exemples/pid_revA.pdf exemples/pid_revB.pdf --html rapport.html
```

## Adapter la reconnaissance des repères

Dans un PDF, le programme devine quels textes sont des repères avec des
expressions régulières (conventions ISA 5.1). Si votre projet utilise une autre
codification (ex. `10-P-001A`), fournissez un fichier JSON :

```json
{
  "motifs": [
    {"categorie": "ligne",      "regex": "^\\d+\"-[A-Z]{1,3}-\\d{3,5}-[A-Z0-9]+$"},
    {"categorie": "equipement", "regex": "^\\d{2}-[A-Z]{1,2}-\\d{3}[A-Z]?$"},
    {"categorie": "instrument", "regex": "^\\d{2}-[A-Z]{2,4}-\\d{3,4}$"},
    {"categorie": "vanne",      "regex": "^\\d{2}-[A-Z]{0,2}V-\\d{3,4}$"}
  ],
  "ignorer": ["^REV ", "^DN\\d+$"]
}
```

Catégories : `equipement`, `instrument`, `vanne`, `ligne`, `autre`. Le premier
motif qui correspond l'emporte.

## Limites

- Les **PDF scannés** ne contiennent pas de texte : seule la superposition
  visuelle est faite, sauf si Tesseract OCR + `pytesseract` sont installés.
- La superposition suppose que les deux révisions ont le même cadrage
  (même format de feuille) ; c'est le cas pour des révisions successives.
- En PDF/DXF, les traits de tuyauterie ne sont pas interprétés comme des
  connexions : la topologie n'est comparée qu'en DEXPI. Les changements de
  tracé apparaissent dans la superposition visuelle.

## Tests

```bash
pip install pytest reportlab
python -m pytest
```

---

# recette_video — vidéo de cuisine → recette

Application web qui transforme une vidéo de cuisine Facebook / Instagram en recette
(images de la vidéo + audio transcrit + description + commentaires, analysés par Claude).
Voir [`recette_video/README.md`](recette_video/README.md).
