# Jarvis — assistant vocal pour vos mails et votre agenda

Un assistant personnel façon IA de film de science-fiction, qui tourne sur votre ordinateur et
s'utilise aussi depuis votre téléphone :

- **lit vos mails non lus** (iCloud et/ou Gmail) et vous en fait **un résumé à voix haute** ;
- **présente votre Google Agenda**, vous **rappelle vos rendez-vous** et peut en **ajouter** ;
- **trie** votre boîte (Urgent, À répondre, Promotions…) et **apprend de vos corrections** ;
- **rédige vos réponses** à la voix et ne les envoie qu'après votre accord ;
- repère les **rendez-vous proposés dans vos mails** et propose de les mettre à l'agenda ;
- vous **désabonne** des newsletters en une phrase ;
- met en avant vos **contacts prioritaires** ;
- **briefing automatique** chaque matin à l'heure choisie ;
- **mode mains libres** : « Jarvis… » suffit, puis la conversation continue sans répéter son nom.

Rien n'est supprimé, et aucun mail ne part sans votre confirmation.

## 1. Installer et lancer (Mac)

1. Téléchargez ce dossier sur votre Mac.
2. Double-cliquez sur **`assistant_vocal/demarrage_auto_mac.command`**. La première fois, il installe
   tout (une minute), puis Jarvis tourne en arrière-plan et **redémarre tout seul avec le Mac**.
   La page s'ouvre sur `http://127.0.0.1:5050`.
   - Si macOS bloque le fichier : clic droit → *Ouvrir*.
   - Pour arrêter : `arreter_demarrage_auto_mac.command`. Pour un lancement ponctuel :
     `lancer_mac.command` (Windows : `lancer_windows.bat`).
3. Sans réglages, Jarvis tourne en **mode démo** (mails et rendez-vous fictifs).

## 2. Brancher vos comptes : ⚙ Réglages → « Comptes et clés »

Tout se fait dans la page, avec un bouton **Tester** pour chaque service. Les clés et mots de passe
sont rangés dans le **Trousseau du Mac** (jamais réaffichés dans la page).

| Réglage | Où le trouver | À quoi il sert |
|---|---|---|
| **Clé Claude** | <https://console.anthropic.com> → API Keys | résumés, tri, réponses (sans elle : tri par mots-clés) |
| **Clé ElevenLabs** (gratuit) | <https://elevenlabs.io> → Profil → API Keys | voix « Jarvis » **et micro sur téléphone** |
| **Adresse + mot de passe pour app iCloud** | <https://account.apple.com> → Connexion et sécurité → Mots de passe pour app | lire, trier et répondre à vos mails iCloud |
| **Lien secret iCal** (Google Agenda, lecture seule) | calendar.google.com → ⚙ → votre agenda → Intégrer l'agenda → « Adresse secrète au format iCal » | lire l'agenda en 2 minutes |
| **Fichier d'identifiants Google** (accès complet) | voir ci-dessous | lire **et ajouter** des rendez-vous ; Gmail |
| **Contacts prioritaires** | une adresse par ligne (ou ★ sur un mail) | toujours en tête du résumé |
| **Code d'accès** | à choisir | obligatoire pour utiliser Jarvis depuis le téléphone |

Pour iCloud, utilisez un **mot de passe pour app** (`abcd-efgh-ijkl-mnop`), pas votre mot de passe
Apple. iCloud n'ayant pas de libellés, le tri **déplace** les mails à archiver dans des dossiers
`Assistant/Promotions`, `Assistant/Newsletters`… (visibles dans Mail) ; les urgents reçoivent un
drapeau.

**Accès Google complet** (environ 10 minutes, une seule fois) : sur <https://console.cloud.google.com>,
créez un projet, activez **Google Calendar API** (et **Gmail API** si vous voulez Gmail), configurez
l'écran de consentement (« Externe », votre adresse en utilisateur test), puis *Identifiants → ID client
OAuth → Application de bureau* et téléchargez le JSON. Déposez-le dans les Réglages et cliquez sur
**Autoriser Google** : la page d'autorisation s'ouvre sur le Mac.

## 3. Utiliser Jarvis sur le téléphone

Le micro d'un téléphone ne fonctionne que sur une adresse **https**. La solution la plus simple et
privée est **Tailscale** (gratuit) : un réseau personnel entre vos appareils, qui fonctionne aussi
hors de chez vous.

1. Dans Jarvis (⚙ Réglages) : choisissez un **code d'accès** et ajoutez votre **clé ElevenLabs**
   (c'est elle qui fait marcher le micro sur iPhone).
2. Installez **Tailscale** sur le Mac et sur le téléphone (<https://tailscale.com/download>), et
   connectez-vous avec le même compte sur les deux.
3. Sur le Mac, double-cliquez sur **`assistant_vocal/telephone_mac.command`**. Il affiche une adresse
   du type `https://mon-mac.tailnet-xxxx.ts.net` (la première fois, Tailscale peut demander
   d'activer HTTPS : suivez son lien).
4. Sur le téléphone, ouvrez cette adresse dans Safari, entrez votre code, puis
   *Partager → Sur l'écran d'accueil* : Jarvis devient une icône comme une app.

Le Mac doit rester allumé (Jarvis tourne dessus). Touchez le noyau pour parler : la phrase est
enregistrée, s'arrête toute seule au silence, puis est transcrite.

## Parler à Jarvis

Touchez le noyau ou le micro (sur ordinateur : maintenez **Espace**). En **mode mains libres**
(⚙ Réglages), dites « Jarvis, … » ; après sa réponse, vous avez quelques secondes pour enchaîner
sans redire son nom ; « merci Jarvis » termine la conversation. En mains libres avec la transcription
ElevenLabs, chaque phrase captée consomme des crédits.

| Vous dites | Il fait |
|---|---|
| « briefing » / « quoi de neuf » | mails + agenda |
| « résume mes mails » | analyse les non-lus et fait le point |
| « lis le mail suivant / urgent », « relis-le en entier » | lecture d'un mail |
| « réponds à Claire que c'est d'accord pour vendredi » | rédige la réponse, vous la lit, l'envoie sur « envoie » |
| « trie mes mails » puis « oui » | propose puis applique le tri (vos corrections sont retenues) |
| « désabonne-moi de la boutique » puis « oui » | désabonnement |
| « mon agenda », « qu'est-ce que j'ai demain ? » | point sur l'agenda |
| « ajoute un rendez-vous chez le dentiste jeudi à 15 h » puis « oui » | crée l'événement (accès Google complet) |
| « stop » | coupe la parole |

Sur chaque mail : **★** (contact prioritaire), **Répondre**, **+ Agenda** (si un rendez-vous y est
proposé), **Se désabonner** (newsletters).

Dans ⚙ Réglages, **Rendez-vous quotidiens** : heure du briefing automatique et rappel vocal
15 minutes avant chaque rendez-vous (tant que la page est ouverte).

## La voix

Avec ElevenLabs, voix grave et posée (« Daniel » par défaut, ou l'identifiant d'une autre voix de leur
bibliothèque) passée dans un filtre « IA » désactivable. Le compte gratuit donne environ 10 minutes
de parole par mois ; ensuite Jarvis repasse sur la voix de l'appareil. Choisissez une voix de la
bibliothèque, pas un clone de la voix d'un acteur réel.

## Confidentialité

- Jarvis tourne sur votre ordinateur ; il n'écoute que sur `127.0.0.1`. L'accès téléphone passe par
  votre réseau privé Tailscale et demande le code d'accès.
- Le texte des mails non lus est envoyé à Claude pour être résumé ; les phrases que vous dites sont
  envoyées à ElevenLabs pour être transcrites.
- Les mails sont traités comme des données : Jarvis a pour consigne de ne jamais suivre les
  instructions qu'ils contiennent, et toute action (envoi, tri, désabonnement, rendez-vous) attend
  votre confirmation.

## Pour les curieux

Réglages avancés possibles dans `~/.assistant_vocal/.env` : `ASSISTANT_MAX_MAILS` (15),
`ASSISTANT_JOURS_AGENDA` (7), `ASSISTANT_MODELE` (`claude-opus-5-5`), `ASSISTANT_PORT` (5050),
`ASSISTANT_DEMO=1`. Mémoire du tri et contacts prioritaires : `~/.assistant_vocal/memoire.json`.

Tests : `python -m pytest`.

### Version claude.ai (sans installation)

`jarvis_claude_ai.html` est une variante publiée sur claude.ai, qui passe par les connecteurs Gmail et
Google Agenda de claude.ai. Elle ne lit pas iCloud et son micro ne fonctionne que dans Chrome ou Edge
sur ordinateur.
