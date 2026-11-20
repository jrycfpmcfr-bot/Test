#!/bin/bash
# Double-cliquez (Mac) : rend Jarvis accessible depuis votre téléphone, en HTTPS, via Tailscale.
# Prérequis : Tailscale installé et connecté sur le Mac ET sur le téléphone (même compte),
# Jarvis lancé, et un code d'accès choisi dans ⚙ Réglages.
TS="$(command -v tailscale || true)"
[ -z "$TS" ] && [ -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ] && TS=/Applications/Tailscale.app/Contents/MacOS/Tailscale
if [ -z "$TS" ]; then
  echo "Tailscale n'est pas installé : https://tailscale.com/download (gratuit), puis relancez ce fichier."
  read -r; exit 1
fi
if ! grep -qs "ASSISTANT_CODE=" "$HOME/.assistant_vocal/.env" && ! security find-generic-password -s "Jarvis assistant" -a ASSISTANT_CODE >/dev/null 2>&1; then
  echo "Choisissez d'abord un code d'accès dans Jarvis (⚙ Réglages > Accès depuis le téléphone)."
  read -r; exit 1
fi
"$TS" serve --bg 5050 || { echo "Tailscale a refusé : suivez le lien affiché pour activer HTTPS, puis relancez."; read -r; exit 1; }
echo
"$TS" serve status
echo
echo "Sur le téléphone : ouvrez l'adresse https://… ci-dessus dans Safari (ou Chrome),"
echo "entrez votre code, puis Partager > « Sur l'écran d'accueil » pour avoir l'icône Jarvis."
read -r
