# Mettre l'application en ligne

Le dépôt contient un `Dockerfile` (Python + ffmpeg + modèle Whisper) et un `render.yaml`.
L'application fonctionne sur tout hébergeur capable de lancer une image Docker.

## Option recommandée : Render (≈ 5 minutes)

1. Fusionnez la pull request : Render lit `render.yaml` sur la branche par défaut.
2. Créez un compte sur https://render.com et reliez votre compte GitHub
   (autorisez l'accès au dépôt `Test`).
3. Ouvrez : **https://render.com/deploy?repo=https://github.com/jrycfpmcfr-bot/Test**
4. Render demande deux valeurs :
   - `ANTHROPIC_API_KEY` : votre clé Claude (https://console.anthropic.com → API Keys) ;
   - `APP_PASSWORD` : le mot de passe que vous taperez pour ouvrir l'application.
5. Cliquez sur **Apply**. Après la construction (5 à 10 min), Render affiche votre lien,
   du type `https://recette-video-xxxx.onrender.com`.

À l'ouverture, le navigateur demande un identifiant (n'importe lequel) et le mot de passe.

### Coût
Le plan `standard` (2 Go de mémoire, environ 25 $/mois) est indiqué dans `render.yaml`, car
la transcription audio demande de la mémoire. Pour payer moins, passez au plan `starter`
(512 Mo) et mettez `WHISPER_MODEL=tiny` : la transcription sera moins précise.
S'ajoute le coût des appels à Claude, à chaque recette.

### Instagram / Facebook depuis un serveur
Les serveurs d'hébergement sont souvent bloqués par Instagram et Facebook. Pour les
déverrouiller, donnez-leur les cookies de votre compte :

1. Dans votre navigateur connecté à Instagram/Facebook, installez l'extension
   « Get cookies.txt LOCALLY » et exportez les cookies de instagram.com et facebook.com.
2. Dans Render → votre service → **Environment** → **Secret Files**, ajoutez un fichier
   nommé `cookies.txt` avec ce contenu.

Ces cookies donnent accès à votre compte : ne les partagez pas, et refaites l'export s'ils
expirent. Si une vidéo reste bloquée, enregistrez-la sur votre téléphone et envoyez le fichier.

## Autres hébergeurs

- **Railway** : « New Project » → « Deploy from GitHub repo » ; il détecte le `Dockerfile`.
  Ajoutez les variables `ANTHROPIC_API_KEY`, `APP_PASSWORD`, `PORT=8000`.
- **Fly.io** : `fly launch` à la racine du dépôt (port interne 8000), puis
  `fly secrets set ANTHROPIC_API_KEY=... APP_PASSWORD=...`.
