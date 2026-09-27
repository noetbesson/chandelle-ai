# Discover vocal — configuration et utilisation

Le dialogue vocal est intégré au même backend que la mémoire et les cartes.
Chaque machine doit configurer ses propres accès Gradium côté serveur.

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
2. Toucher la chandelle pour parler et autoriser le micro (45 secondes maximum).
3. Toucher de nouveau la chandelle pour terminer : transcription et envoi automatiques, sans texte affiché.
4. Répondre au budget et aux précisions. Au troisième message, ou via
   **Voir ma recommandation**, le moteur actuel calcule et enregistre un programme.
5. Ouvrir la fiche pour voir le créneau, les activités et le coût à deux.

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

Chandelier SVG à trois bougies inspiré du dessin fourni : flammes dorées pendant
la lecture, orangées pendant l’enregistrement, mauves pendant les traitements.
Leur taille suit le volume sonore mesuré localement, avec retour progressif au
repos dans les silences ; elle ne dépend pas de la durée de parole. Le micro
n’est jamais envoyé aux haut-parleurs par cette visualisation. Le libellé
indique aussi l’état. Un clic pendant la lecture l’interrompt pour parler.
Pas de transcript visible ni de lecteur audio ; clavier et dernière réponse
accessibles dans un volet fermé. Le bouton Quitter ferme micro/lecture et invalide
les requêtes tardives. Animations désactivées si réduction des mouvements demandée.
L’arrêt au silence n’est pas automatique : toucher la chandelle termine la prise.

## Raccordement Windows et recherche web, 27 septembre 2026

Le lanceur `powershell -ExecutionPolicy Bypass -File scripts/run_ai.ps1` charge
désormais aussi les paramètres `GRADIUM_*` du `.env` privé à la racine.
Renseigner `GRADIUM_API_KEY`, `GRADIUM_VOICE_ID`, puis `GRADIUM_ENABLED=1` pour
activer la voix. Les modèles STT/TTS sont facultatifs. Ne pas transmettre les clés
dans le chat ou dans Git. Le fichier `backend/integrations/.env.example` contient
uniquement les noms et des valeurs vides ou désactivées.

Le dialogue Discover utilise le même service de recherche web que les formulaires
Ask/Discover. Les résultats sont des cartes individuelles, même quand des champs
manquent pour composer un programme. Le catalogue fictif n'est pas réintroduit.
Le clavier fonctionne sans Gradium ; un statut configuré ne prouve pas qu'un appel
fournisseur a réussi. Les tests du connecteur simulent le fournisseur.
