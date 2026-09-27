# Discover vocal — configuration et utilisation

Implémenté dans le workspace `chandelle-codex-E`. Les autres clones locaux ne
reçoivent pas automatiquement ces modifications non commitées.

## Lancer

Depuis ce projet, après installation des dépendances Python habituelles :

```bash
bash scripts/run_voice.sh
```

Le script demande la clé API Gradium en saisie masquée, puis l'identifiant d'une
voix française de votre compte Gradium. Récupérer ces informations dans le
dashboard Gradium ; ne pas coller la clé dans le code ni dans une conversation.
Le script les exporte uniquement pour le serveur lancé, sans les enregistrer.
Arrêter un ancien serveur sur le même port avant de relancer.

Ouvrir http://127.0.0.1:8000, terminer les deux entretiens si nécessaire, puis
**Discover → Discuter avec Chandelle**. Le catalogue existant reste accessible.

1. Chandelle demande votre envie de sortie et lit la question.
2. Toucher le cercle vert pour parler et autoriser le micro (45 secondes maximum).
3. Toucher de nouveau le cercle pour terminer : transcription et envoi automatiques, sans texte affiché.
4. Répondre au budget et aux précisions. Au troisième message, ou via
   **Voir ma recommandation**, le moteur actuel calcule et enregistre un programme.
5. Ouvrir la fiche pour voir le créneau, les activités et le coût à deux.

Le micro nécessite localhost ou HTTPS. Si la lecture automatique est bloquée,
toucher le cercle pour lancer la lecture. Le texte reste utilisable sans Gradium ou si le
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
sont déjà exportées. Aucun chargement implicite de `.env`. Aucune dépendance
nouvelle : les appels utilisent `httpx` déjà présent.

## Périmètre réellement implémenté

Dialogue **guidé par tours**, pas conversation générative libre ni streaming
audio continu avec interruption vocale. Gradium transcrit et synthétise ; H
pose les questions, E compose le programme avec A/B/C. Pas de clé OpenAI requise.
Les contraintes linguistiques restent celles de l'analyse locale existante :
utiliser des montants chiffrés dans la transcription, par exemple « 80 euros pour
deux ». Le créneau vient des disponibilités enregistrées ; une date dite librement
n'est pas transformée automatiquement en disponibilité. Modifier les créneaux
dans « Nos disponibilités » si nécessaire. Le catalogue reste une démonstration.

L'audio est envoyé à Gradium pour transcription ; les réponses lui sont envoyées
pour synthèse. Les données de mémoire brutes et la clé ne partent pas au navigateur
ou au fournisseur dans le payload vocal. L'échange n'alimente pas automatiquement
la mémoire continue : ses messages/audio restent temporaires, les plans sont
enregistrés selon le fonctionnement existant. La navigation/changement de profil
arrête le micro et la lecture, et invalide les résultats tardifs.

## Fichiers et endpoints

- `backend/integrations/gradium.py` : REST ASR/TTS, délais, validation WAV, erreurs nettoyées.
- `backend/streams/H_conversation/voice.py` : dialogue et appel du planner injecté.
- `backend/api/routes.py` : `POST /api/v2/discover/chat`, `/voice/transcribe`,
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

Cercle bleu animé pendant la lecture réelle, vert lorsque le micro peut être
activé et pendant l’enregistrement, violet pendant les traitements. Le libellé
indique aussi l’état. Un clic pendant la lecture l’interrompt pour parler.
Pas de transcript visible ni de lecteur audio ; clavier et dernière réponse
accessibles dans un volet fermé. Le bouton Quitter ferme micro/lecture et invalide
les requêtes tardives. Animations désactivées si réduction des mouvements demandée.
L’arrêt au silence n’est pas automatique : toucher le cercle termine la prise.
