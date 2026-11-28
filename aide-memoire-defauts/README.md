# Aide-mémoire de défauts — Version 1

Application web personnelle, pensée pour le téléphone, pour retrouver vite la
signification d'un code défaut, ses causes probables et les vérifications à faire
(Siemens et Schneider en V1).

## Ce que fait la V1

- **Recherche unique** : code (`F07801`, `f7801`, `F 07801`, `OCF`…) ou symptôme
  (« moteur ne démarre pas »). Tolère les accents, la casse, les fautes de frappe
  et les variantes (démarre / démarrage).
- **Filtres** : marque, type de matériel, gamme.
- **Fiche défaut** : signification, causes (de la plus fréquente à la plus rare),
  vérifications pas à pas, remède, source (document, référence, page), fiabilité.
- **Lisibilité terrain** : gros textes, fort contraste, mode sombre par défaut,
  bouton « A± » pour agrandir encore.

## Règles sur les données

- Une fiche sans source est **écartée** au chargement et fait échouer les tests.
- Les fiches rédigées par IA portent `"genereIA": true, "verifie": false` et
  s'affichent avec le badge **« IA – à vérifier »**. Après contrôle contre la
  notice, corriger la fiche, renseigner la page et passer `"verifie": true`.
- Aucune donnée client ni nom de site dans ce dépôt. Les notes terrain (V2)
  resteront sur le téléphone, jamais dans le dépôt.

Format d'une fiche : voir `data/fiches.json`.

## Lancer en local

```bash
npm test          # tests de la recherche et validation des fiches
npm start         # http://localhost:3000 (le middleware n'est pas actif en local)
```

## Mise en ligne sur Vercel (gratuit, protégé par mot de passe)

1. Sur vercel.com : *Add New → Project*, importer ce dépôt GitHub (privé).
2. **Root Directory** : `aide-memoire-defauts`. Framework : *Other*. Pas de build.
3. *Settings → Environment Variables* : créer `AUTH_USER` et `AUTH_PASSWORD`
   (mot de passe long). Rien n'est écrit dans le code ; sans ces variables le
   site répond 503 (jamais ouvert par défaut).
4. Déployer, puis ouvrir l'URL : le navigateur demande identifiant et mot de passe.

Le fichier `middleware.js` fait l'authentification Basic (HTTPS, comparaison en
temps constant). Limites connues : pas de déconnexion ni de limitation des
essais, un seul compte. Pour un partage avec des collègues (V4), passer à de
vrais comptes (Vercel Authentication ou Cloudflare Access).

## Feuille de route

- V2 : notes terrain, favoris, historique (IndexedDB + export/import JSON).
- V3 : import depuis PDF avec validation manuelle, ajout de Yokogawa.
- V4 : hors ligne (service worker qui ne met en cache que les réponses 200), partage.
