# Recette Vidéo — d'une vidéo de cuisine Facebook / Instagram à une recette écrite

Application web : on colle le lien d'une vidéo (reel Instagram, vidéo Facebook) ou on envoie
le fichier, et l'application :

1. **télécharge la vidéo**, sa description et ses commentaires (`yt-dlp`) ;
2. **regarde la vidéo** : environ une image toutes les 3 s (8 à 30 images, `ffmpeg`) ;
3. **écoute l'audio** : transcription horodatée en local (`faster-whisper`) ;
4. **lit les commentaires** (souvent l'auteur y donne les quantités) ;
5. envoie le tout à **Claude**, qui croise les sources et rédige la recette : ingrédients avec
   quantités (estimées si non dites, et signalées comme telles), ustensiles, étapes illustrées
   par l'image correspondante, astuces, apports des commentaires, points incertains.

La page permet de cocher les ingrédients, multiplier les quantités, imprimer, copier ou
télécharger la recette en Markdown.

## Installation

Prérequis : Python 3.10+ et `ffmpeg` installé sur la machine.

```bash
pip install -r recette_video/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python -m recette_video          # puis ouvrir http://127.0.0.1:8000
```

Au premier lancement, le modèle de transcription Whisper (~500 Mo pour `small`) est téléchargé.

## Variables d'environnement

| Variable | Rôle | Défaut |
|---|---|---|
| `ANTHROPIC_API_KEY` | clé de l'API Claude | — |
| `CLAUDE_MODEL` | modèle Claude utilisé | `claude-opus-5-5` |
| `WHISPER_MODEL` | `tiny`, `base`, `small`, `medium`, `large-v3` | `small` |
| `COOKIES_FILE` | fichier cookies.txt utilisé pour toutes les vidéos | — |
| `COOKIES_FROM_BROWSER` | lire les cookies du navigateur (`firefox`, `chrome`…) | — |
| `HOST` / `PORT` | adresse du serveur | `127.0.0.1` / `8000` |

## Connexion à Instagram / Facebook

Instagram et Facebook bloquent souvent la lecture sans être connecté. Trois solutions :

- lancer avec `COOKIES_FROM_BROWSER=firefox` (ou `chrome`) sur un ordinateur où vous êtes connecté ;
- exporter un `cookies.txt` (extension « Get cookies.txt LOCALLY ») et l'envoyer dans
  « Options avancées » — il est effacé après l'analyse ;
- enregistrer la vidéo sur votre téléphone et l'envoyer comme fichier.

**Commentaires** : `yt-dlp` lit ceux d'Instagram (avec cookies) mais pas ceux de Facebook.
Dans ce cas, collez les commentaires utiles dans « Options avancées ».

## Mise en ligne

Voir [`DEPLOIEMENT.md`](DEPLOIEMENT.md) : Docker, Render en un clic, mot de passe (`APP_PASSWORD`).

## Tests

```bash
python -m pytest tests/test_recette_video.py
```

Les tests utilisent une vidéo générée par ffmpeg et remplacent Whisper et Claude par des faux :
ils ne font aucun appel réseau.
