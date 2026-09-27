# Ask vocal — configuration et utilisation

> Parcours courant : [dialogue libre et recommandations réelles](ASK_DIALOGUE.md).
> Le frontend utilise une session OpenAI optionnelle. Discover conserve le catalogue.


Implémenté dans le workspace `chandelle-codex-E`. Les autres clones locaux ne
reçoivent pas automatiquement ces modifications non commitées.

## Lancer

Depuis ce projet, après installation des dépendances Python habituelles :

```bash
bash scripts/run_voice.sh
```

Le script lit le `.env` local : `GRADIUM_API_KEY`, `GRADIUM_VOICE_ID` et
`GRADIUM_ENABLED=1`. Il demande en saisie masquée seulement les valeurs manquantes ;
elles restent alors dans le processus, sans écriture automatique. OpenAI et le web
se configurent de même avec leurs clés/options dans [LOCAL_ENV.md](LOCAL_ENV.md).
Ne pas coller de clé dans une conversation. Arrêter un ancien serveur sur le même
port avant de relancer. Diagnostic sans appel API :
`bash scripts/run_voice.sh --check-env`.

Ouvrir http://127.0.0.1:8000, terminer les deux entretiens si nécessaire, puis
**Ask**, puis cliquer sur le chandelier déjà visible. Les activités restent consultables dans Discover.
Le lanceur propose aussi OpenAI et la recherche web ; autoriser séparément leur
utilisation dans « Options du dialogue » pour activer la compréhension libre et la recherche.

1. Chandelle demande votre envie de sortie et lit la question.
2. Toucher la chandelle pour parler et autoriser le micro (45 secondes maximum).
3. Toucher de nouveau la chandelle pour terminer : transcription et envoi automatiques, sans texte affiché.
4. Décrire ses envies, poser des questions ou changer les contraintes librement.
   **Trouver des idées** recherche des activités sans exiger un agenda commun.
5. Demander un programme quand le créneau et les données des activités le permettent.
   Ouvrir sa fiche pour voir les activités et le coût à deux.

Le micro nécessite localhost ou HTTPS. Si la lecture automatique est bloquée,
toucher la chandelle pour lancer la lecture. Le texte reste utilisable sans Gradium ou si le
micro/fournisseur est indisponible. Une absence de programme faisable est
signalée ; aucune recommandation fictive n'est substituée au moteur.

## Variables serveur

| Nom | Usage |
| --- | --- |
| GRADIUM_ENABLED | Activation explicite ; le launcher vocal l'active |
| GRADIUM_API_KEY | Clé secrète, exclusivement côté serveur |
| GRADIUM_VOICE_ID | Identifiant de voix choisi sur Gradium |
| GRADIUM_STT_MODEL | Modèle de transcription, facultatif ; défaut du fournisseur |
| GRADIUM_TTS_MODEL | Modèle de synthèse, facultatif ; défaut du fournisseur |

Le lancement habituel `bash scripts/run.sh` fonctionne aussi si ces variables
sont exportées ou présentes dans `.env`. Les variables exportées sont prioritaires.
Aucune dépendance nouvelle : python-dotenv et httpx sont déjà déclarés.

## Périmètre réellement implémenté

Dialogue libre avec OpenAI activé et autorisé ; mode local limité sinon. Gradium
transcrit et synthétise ; H interprète et conserve le contexte ; C cherche les
sources réelles ; E compose le programme. Le transport audio reste par tours,
sans écoute permanente ni interruption vocale automatique. Une date explicitement
demandée peut définir un créneau ; aucun agenda n’est modifié par la conversation.
Les idées ne nécessitent pas de disponibilités communes. Le catalogue réel reste
limité et la recherche web fournit des pistes dont les informations sont à confirmer.

L'audio est envoyé à Gradium pour transcription ; les réponses lui sont envoyées
pour synthèse. Les données de mémoire brutes et la clé ne partent pas au navigateur
ou au fournisseur dans le payload vocal. L'échange n'alimente pas automatiquement
la mémoire continue : ses messages/audio restent temporaires, les plans sont
enregistrés selon le fonctionnement existant. La navigation/changement de profil
arrête le micro et la lecture, et invalide les résultats tardifs.

## Fichiers et endpoints

- `backend/integrations/gradium.py` : REST ASR/TTS, délais, validation WAV, erreurs nettoyées.
- `backend/streams/H_conversation/dialogue.py` : session et dialogue ; `voice.py` conserve le protocole guidé historique.
- `backend/api/routes.py` : `POST /api/v2/ask/chat` (ancien chemin `/discover/chat` conservé), `/voice/transcribe`,
  `/voice/speak`. Capacité du membre + deux entretiens terminés requis.
- `frontend/app/voice.mjs` : enregistrement, WAV PCM mono, transcription,
  lecteur et conversation, intégré à `app.mjs`.
- `/api/v2/integrations` expose seulement l'état configuré/activé/disponible.

Vérification : `bash scripts/check.sh`. Tests de contrat avec faux transport
HTTP Gradium, tests d'identité et de microphone simulé. Aucun appel fournisseur
live ni essai micro dans un navigateur réel effectué à la livraison ; ces deux
points restent à vérifier avec la configuration locale de l'utilisateur.

## Références officielles consultées

- [Transcription REST](https://docs.gradium.ai/guides/speech-to-text-rest)
- [Contrat ASR REST](https://docs.gradium.ai/api-reference/endpoint/stt-post)
- [Synthèse REST](https://docs.gradium.ai/guides/text-to-speech-rest)
- [Voix Gradium](https://docs.gradium.ai/guides/voices/flagship-voices)

## Interface vocale compacte

Chandelier SVG à trois bougies inspiré du dessin fourni : flammes dorées pendant
la lecture, orangées pendant l’enregistrement, mauves pendant les traitements.
Leur taille suit le volume sonore mesuré localement, avec retour progressif au
repos dans les silences ; elle ne dépend pas de la durée de parole. Le micro
n’est jamais envoyé aux haut-parleurs par cette visualisation. Le libellé
indique aussi l’état. Un clic pendant la lecture l’interrompt pour parler.
Pas de transcript visible ni de lecteur audio ; clavier et dernière réponse
accessibles dans un volet fermé. Le bouton Terminer ferme micro/lecture et invalide
les requêtes tardives. Animations désactivées si réduction des mouvements demandée.
L’arrêt au silence n’est pas automatique : toucher la chandelle termine la prise.
