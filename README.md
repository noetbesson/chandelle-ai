# Chandelle

Agent local pour organiser les sorties d’un couple : comprendre les goûts,
trouver des activités compatibles, composer un programme et préparer la sortie.
**Un processus FastAPI, une base SQLite, une interface JavaScript sans build.**

## Démarrer et vérifier

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
bash scripts/run.sh
```

Python 3.11+ ; Node 18+ pour les tests frontend uniquement. L’installation initiale
des dépendances nécessite le réseau, puis l’application et les tests fonctionnent
hors ligne. Ouvrir http://127.0.0.1:8000. La base s’initialise automatiquement.
Documentation interactive : http://127.0.0.1:8000/docs.

```bash
bash scripts/check.sh
```

## Où lire et modifier le code

```text
backend/
  api/                     Entrée HTTP, authentification des requêtes, assemblage
    app.py                 Point d’entrée du serveur
    routes.py                  Routes actuelles /api/v2
    legacy_orchestrator.py Ancienne API E, conservée pour compatibilité
    static/                Ancienne interface V1
  streams/                 Métier : une responsabilité par stream
    A_calendar/service.py  Disponibilités et créneaux communs
    B_memory/service.py    Mémoire, consentement, recherche et provenance
             onboarding.py Profils, identité locale et entretiens
    C_discovery/service.py Catalogue, filtres, classement et favoris
    D_connectors/service.py Imports de notes et exports de plateformes
    E_orchestrator/service.py Cycle de vie des programmes et retours
                   planner.py Algorithme déterministe de composition
                   models.py  Types de planification communs à V1/V2
    F_booking/service.py   Préparation humaine et export calendrier
    G_proactive/service.py Suggestions, temporisation et actions
    H_conversation/service.py Compréhension du texte et conversations
  integrations/            Adaptateur OpenAI et validation d’URL
  db/                      Schéma SQLite, connexions et sérialisation
  tests/                   Régressions d’API, sécurité, intégration et architecture
frontend/
  app/                      SPA actuelle : app.mjs, experiences.mjs, HTML, CSS
  tests/                   Tests JS non servis au navigateur
mocks/                     Catalogues locaux utilisés par l’application
scripts/                   Démarrage, initialisation et vérification
```

Dans B/C/E/G/H, **`legacy.py` sert uniquement la compatibilité V1**.
Tous les tests Python sont regroupés dans
`backend/tests/`. E garde `adapters.py` et `repository.py` pour les contrats et
fixtures V1 encore testés. Le produit actuel appelle directement les `service.py`.

Lire [ARCHITECTURE.md](docs/v2/ARCHITECTURE.md) pour les responsabilités, frontières
et dépendances, puis [CONTRACTS.md](docs/v2/CONTRACTS.md) pour les routes et le stockage.
L’[état courant](docs/v2/STATE.md), les [décisions](docs/v2/DECISIONS.md) et les
[preuves de test](docs/v2/TEST_MATRIX.md) complètent ces deux documents.
Les références anciennes sont réunies dans [archive/HISTORY.md](docs/v2/archive/HISTORY.md).
`docs/codex-E`, `docs/night-shift` et `backend/shared/*.json` restent des références
historiques de l’équipe, pas des modules applicatifs actifs.

## Essayer les parcours

Créer les deux profils et terminer les entretiens, puis :

1. **Inspirations** : importer une note ou un export, confirmer les goûts et le partage.
2. **Nos disponibilités** : chaque personne renseigne ses créneaux ; A en calcule l’intersection.
3. **Discover / Ask** : comparer des activités et composer un programme pour deux.
4. Accepter le programme, puis préparer la sortie et télécharger le calendrier `.ics`.

Pour un couple de démonstration prêt à utiliser :
`CHANDELLE_DEV=1 bash scripts/run.sh`, puis Settings → Load developer demo.
La V1 reste accessible à `/v1/demo` et `/v1`.

## Limites et données

Catalogue fictif de 76 exemples. Aucune réservation, aucun paiement automatique.
Disponibilités manuelles ou démo, sans connexion à un agenda externe. Les imports
sont locaux : un lien seul ne télécharge pas une page ni une vidéo.

Les données restent dans `.runtime/`, exclu de Git comme `.env`, `.venv` et les
caches. Les capacités locales isolent les profils sur l’appareil ; elles ne
constituent pas une authentification de production.

OpenAI est opt-in : `OPENAI_ENABLED`, `OPENAI_API_KEY`, `OPENAI_MODEL`,
`OPENAI_EMBEDDING_MODEL`. Les scripts ne chargent pas automatiquement `.env`.
Le smoke live requiert `RUN_LIVE_OPENAI_SMOKE=1` et n’entre jamais dans les tests
par défaut. Gradium, Dust, Pipelex, Jinko et les sources publiques live ne sont pas
raccordés à cette version.

## Import vidéo dans la mémoire

Dans l'application, terminer les deux entretiens, choisir son profil, puis ouvrir
**Inspirations > Importer une vidéo Instagram ou TikTok**. Ajouter un MP4/MOV
obtenu avec autorisation (32 Mio, 3 minutes maximum), sa légende et éventuellement
son lien/date d'origine. Le lien ne déclenche aucun téléchargement.
Après traitement, corriger les goûts proposés et choisir leur utilisation avant
confirmation. Un import privé ne change pas les recommandations du couple.

Le code utilisé est `backend/streams/B_memory/reels.py`, raccordé à
`backend/api/reels.py` et aux adaptateurs `backend/integrations/reels/`.
Les faits rejoignent `v2_facts` dans la même base ; `v2_reel_jobs` contient seulement
l'état des traitements. L'ancienne copie TypeScript `B_memory/video-memory` a été supprimée à votre demande ;
le serveur exécute uniquement les modules Python décrits ici.

Sous Windows, depuis la racine du projet :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000 --workers 1
```

Installer FFmpeg et FFprobe localement, ou renseigner leurs chemins absolus via
`REELS_FFMPEG_PATH` et `REELS_FFPROBE_PATH`. Sur cette machine, les deux exécutables
sont déjà dans `.runtime/tools/`, dossier ignoré par Git.
Le modèle de configuration sans secret est
`backend/integrations/reels/.env.example`. Il n'est pas chargé automatiquement :
les variables doivent être définies dans l'environnement du serveur.

Par défaut, `REELS_NORMALIZATION_BACKEND=local` et `REELS_LIVE_ENABLED=0` :
extraction audio locale, aucune transcription distante, propositions limitées aux
mots de la légende. Pour Gradium et la normalisation OpenAI/Pipelex, configurer les
clés côté serveur, activer explicitement `REELS_LIVE_ENABLED=1`, sélectionner
`openai` ou `pipelex`, puis obtenir le consentement cloud dans le formulaire.
Aucune clé ne doit être placée dans le navigateur ou copiée dans le chat.

L'API authentifiée est `POST /api/v2/reels/upload` avec `X-Member-Token`, fichier
multipart `video`, `consent=true`, champs facultatifs `caption`, `source_url`,
`signal_at` et `cloud_consent=true`. Sans `wait`, elle retourne un job (202),
consultable par son propriétaire via `GET /api/v2/reels/jobs/{job_id}`.
Avec `?wait=true`, elle retourne directement le TasteSignal validé. Un doublon
réutilise le signal existant. Les fichiers temporaires sont supprimés en fin de
traitement ; après redémarrage, les travaux interrompus sont signalés en échec et
leurs fichiers supprimés. L'utilisateur peut renvoyer le fichier.

Cette application reste une démonstration locale avec identité par jeton de membre.
Un seul processus serveur est prévu. Il n'y a ni connexion aux comptes Instagram/TikTok ni scraping. La réception
PWA ajoutée ensuite est décrite ci-dessous.

## Partager depuis Instagram ou TikTok (PWA)

Cette réception utilise le pipeline mémoire ci-dessus. Elle ajoute le manifeste
`/manifest.json`, le service worker `/sw.js`, l'aide `/installer` et la page de
réception `/partager`. Dans Inspirations, le lien « Recevoir depuis le bouton
Partager du téléphone » ouvre les instructions d'installation.

Sur Android avec Chrome :
1. Ouvrir l'adresse HTTPS de Chandelle sur le téléphone, terminer les entretiens
   et ouvrir `/installer` pour activer le service worker.
2. Choisir « Installer l'application » dans Chrome. Un simple onglet n'est pas
   une destination de partage native.
3. Dans Instagram ou TikTok, choisir Partager, puis Plus/autres applications,
   puis Chandelle si cette destination est proposée par le système.
4. Choisir explicitement son profil, relire les métadonnées et autoriser l'import.
   Une vidéo reçue suit le pipeline existant ; les goûts restent privés et proposés.

Un partage peut contenir uniquement un lien, selon la plateforme et le contenu.
Dans ce cas, la page demande un MP4/MOV obtenu avec autorisation, ou permet
l'enregistrement du lien et d'une description comme piste à confirmer. Un lien
ne devient jamais une transcription. Il n'y a aucun téléchargement automatique
et aucun accès aux likes/enregistrements du compte.

Sur iPhone/Safari, utiliser le lien copié et l'import manuel dans `/partager`.
Cette PWA ne fournit pas une extension native iOS. Une connexion à notre backend
reste nécessaire pour afficher les écrans et traiter le contenu. La réception
Android native n'a pas été testée sur un téléphone physique lors de cette livraison.

Les données du partage passent d'abord dans une boîte temporaire IndexedDB du
navigateur, pas dans une deuxième mémoire de couple. Elle est limitée à cinq
partages de 32 Mio maximum, avec expiration de 24 heures nettoyée au prochain
accès. Le choix d'un profil verrouille son attribution ; l'import utilise ensuite
le jeton existant et le formulaire commun. Les brouillons sont supprimés après
succès ou annulation ; `/installer` permet aussi de tous les effacer. Annuler un
brouillon après lancement du pipeline ne supprime pas une mémoire déjà créée.
Les phases du job sont affichées et le suivi d'un partage interrompu peut reprendre
après rechargement. Les API et les contenus personnels ne sont jamais mis en cache
par le service worker. Sans service worker, l'endpoint de partage retourne une
explication (409), sans stocker de fichier anonyme sur le serveur.

### Vérification locale

Sur ordinateur, localhost/127.0.0.1 permet de tester le service worker. Dans
Chrome/Edge DevTools > Application, vérifier le manifeste et le worker, puis
simuler une navigation POST multipart vers `/api/receive-share`. Cela vérifie la
réception, pas la présence dans le menu de partage d'un téléphone. Sur téléphone,
`127.0.0.1` pointe vers le téléphone, pas vers le PC : utiliser une adresse HTTPS
accessible avec certificat reconnu. Aucun déploiement ou tunnel n'est activé ici.

La régression browserless est incluse dans `scripts/check.sh`.
Le scénario navigateur optionnel est `scripts/test_share_browser.cjs` ; il nécessite
Playwright, Microsoft Edge et le serveur de test isolé. Sur Windows :

```powershell
$env:SHARE_TEST_DB="$PWD/.runtime/pwa-browser-test.sqlite3"
$env:CHANDELLE_DEV='1'
$env:OPENAI_ENABLED='0'
$env:REELS_LIVE_ENABLED='0'
$env:REELS_NORMALIZATION_BACKEND='local'
.\.venv\Scripts\python.exe -m uvicorn backend.tests.serve_share_fixture:app --host 127.0.0.1 --port 8314 --no-access-log
```

Dans un second terminal, fournir un module Playwright installé via
`PLAYWRIGHT_MODULE` (ou disponible normalement dans Node), créer la vidéo synthétique
et lancer le test :

```powershell
.\.runtime\tools\ffmpeg.exe -nostdin -v error -f lavfi -i color=c=black:s=64x64:r=5 -t 0.4 -c:v mpeg4 -y .runtime/pwa-fixture.mp4
node scripts/test_share_browser.cjs
```

Références : [Chrome, réception de partages](https://developer.chrome.com/docs/capabilities/web-apis/web-share-target)
et [MDN, manifeste share_target](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest/Reference/share_target).
