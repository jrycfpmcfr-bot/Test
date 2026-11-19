# Assistant vocal — mails + agenda, interface HUD

Un assistant personnel façon IA de film de science-fiction, qui tourne sur votre ordinateur :

- **lit vos mails non lus** (Gmail) et vous en fait **un résumé à voix haute** ;
- **présente votre agenda** (Google Agenda) et peut **ajouter un rendez-vous** à la voix (après confirmation) ;
- **propose un tri** de chaque mail (Urgent, À répondre, À lire, Notifications, Newsletters, Promotions,
  Spam probable) et, si vous confirmez, le range dans des libellés Gmail `Assistant/…` et archive ce qui
  encombre ;
- se commande **à la voix** (micro du navigateur) ou au clavier, avec une interface animée bleue
  dont le noyau réagit quand l'assistant parle.

Rien n'est supprimé : l'assistant ne fait qu'ajouter des libellés, archiver et marquer comme lu,
et **seulement après votre confirmation**.

## Essai immédiat (sans compte Google)

```bash
pip install -r assistant_vocal/requirements.txt
python -m assistant_vocal --demo
```

La page s'ouvre sur `http://127.0.0.1:5050` avec des mails et rendez-vous fictifs.
Utilisez **Chrome ou Edge** (ce sont eux qui gèrent la reconnaissance vocale).

## Installation complète

### 1. Clé Claude (le « cerveau »)

Créez une clé sur <https://console.anthropic.com>, puis créez un fichier `.env` dans le dossier
`~/.assistant_vocal/` (ou dans le dossier d'où vous lancez le programme) :

```
ANTHROPIC_API_KEY=sk-ant-...
```

Sans clé, l'assistant fonctionne quand même mais trie par mots-clés et lit les objets au lieu de
vrais résumés.

### 2. Accès à Gmail et Google Agenda (une seule fois)

1. Allez sur <https://console.cloud.google.com>, créez un projet.
2. *API et services → Bibliothèque* : activez **Gmail API** et **Google Calendar API**.
3. *Écran de consentement OAuth* : type « Externe », ajoutez votre adresse comme **utilisateur test**.
4. *Identifiants → Créer → ID client OAuth → Application de bureau*, puis téléchargez le JSON.
5. Enregistrez-le sous `~/.assistant_vocal/credentials.json`.

Au premier lancement, une page Google s'ouvre pour autoriser l'accès ; le jeton est ensuite gardé dans
`~/.assistant_vocal/token.json` (sur votre machine uniquement).

### 3. Lancer

```bash
python -m assistant_vocal
```

## Parler à l'assistant

Cliquez sur le noyau, sur le micro, ou **maintenez la barre Espace** pendant que vous parlez.
Dans ⚙ *Réglages*, l'option **Écoute permanente** le fait réagir dès que vous dites son nom
(« Jarvis, quoi de neuf ? »).

| Vous dites | Il fait |
|---|---|
| « résume mes mails » | analyse les non-lus et fait le briefing oral |
| « lis le mail suivant », « lis le premier mail », « lis le mail urgent », « relis-le en entier » | lecture d'un mail |
| « trie mes mails » puis « oui » | propose puis applique le tri |
| « mon agenda », « qu'est-ce que j'ai demain ? » | briefing de l'agenda |
| « ajoute un rendez-vous chez le dentiste jeudi à 15 h » puis « oui » | crée l'événement |
| « briefing » / « quoi de neuf » | mails + agenda d'un coup |
| « stop » ou Échap | coupe la parole |
| toute autre question (« qui attend une réponse de ma part ? ») | réponse libre de Claude |

Dans la liste, vous pouvez changer la catégorie d'un mail ou cocher/décocher « archiver » avant
d'appliquer le tri.

## La voix

Par défaut, c'est la synthèse vocale du navigateur : dans ⚙ *Réglages*, choisissez une voix
française masculine (ex. « Thomas », « Paul », « Henri » selon le système) et baissez un peu la
hauteur pour un ton de majordome.

Pour une voix nettement plus naturelle, branchez **ElevenLabs** (payant) : choisissez dans leur
bibliothèque une voix posée et distinguée, puis ajoutez dans le `.env` :

```
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
```

## Réglages (`.env`)

| Variable | Rôle | Défaut |
|---|---|---|
| `ASSISTANT_NOM` | nom de l'assistant (et mot d'éveil) | `Jarvis` |
| `ASSISTANT_UTILISATEUR` | comment il vous appelle | `Monsieur` |
| `ASSISTANT_MAX_MAILS` | nombre de non-lus analysés | `15` |
| `ASSISTANT_JOURS_AGENDA` | jours d'agenda affichés | `7` |
| `ASSISTANT_MODELE` | modèle Claude | `claude-opus-5-5` |
| `ASSISTANT_PORT` | port local | `5050` |
| `ASSISTANT_DOSSIER` | dossier des identifiants | `~/.assistant_vocal` |
| `ASSISTANT_DEMO` | `1` pour forcer les données fictives | auto |

## Confidentialité

- Le serveur n'écoute que sur `127.0.0.1` : il n'est pas joignable depuis le réseau.
- Le texte des mails non lus (4 000 caractères max par mail) est envoyé à l'API Claude pour être
  résumé ; la reconnaissance vocale de Chrome/Edge passe par les serveurs de Google/Microsoft.
- Les mails sont traités comme des données : l'assistant a pour consigne de ne jamais suivre les
  instructions qu'ils contiennent et de classer les tentatives de manipulation en « Spam probable ».

## Version claude.ai (sans installation)

`jarvis_claude_ai.html` est la même interface, publiée comme page sur claude.ai : elle lit votre
boîte via le connecteur Gmail de claude.ai, utilise Claude pour les résumés et le tri, la voix et
la dictée de claude.ai, et lit et complète votre Google Agenda via son connecteur. Aucune clé ni
serveur à installer. La voix par défaut est la meilleure voix masculine française gratuite de
l'appareil (idéalement « Henri » dans Microsoft Edge), réglée plus grave et posée.
