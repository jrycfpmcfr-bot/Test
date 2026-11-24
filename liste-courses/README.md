# Liste de courses

Appli web (fonctionne sur téléphone et ordinateur, installable sur l'écran d'accueil) :

- **Coches** pour chaque article ; « Retirer les articles cochés » vide ce qui est pris.
- **3 façons d'ajouter** :
  - ✍️ écrire : `2 baguettes, lait et 6 œufs`
  - 🎤 dicter : appuyer sur le micro et parler (« du pain et du beurre chez Lidl pour Paul »)
  - 📷 photo d'une liste papier : le texte est lu, on corrige / décoche puis on ajoute
- **Magasin** et **qui s'en occupe** pour chaque article (menus en bas, ou « chez … » / « pour … » dans la phrase).
- **Tri** par magasin, par personne ou A → Z, et **filtres** par personne / magasin.
- Toucher un article pour le modifier (quantité, magasin, personne, note) ou le supprimer.
- ⬆️ Partager la liste (SMS, WhatsApp…) en texte.
- ⚙️ Gérer les magasins et les personnes.

La liste est enregistrée sur l'appareil (stockage du navigateur).

## Utilisation

Ouvrir `index.html` dans un navigateur, ou mieux, publier le dossier (par ex. GitHub Pages)
pour l'ouvrir en `https://` : la dictée, l'installation et le mode hors ligne en ont besoin.

- La dictée utilise la reconnaissance vocale du navigateur (Chrome, Edge, Safari).
- La photo utilise Tesseract.js, chargé depuis internet à la première utilisation.
