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
des dépendances nécessite le réseau. La mémoire et les tests fonctionnent hors ligne ;
la recherche de sorties exige le service web configuré côté serveur. Ouvrir http://127.0.0.1:8000. La base s’initialise automatiquement.
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
    C_discovery/service.py Cache des faits web, filtres, classement et favoris
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
mocks/                     Note de retrait des anciens catalogues
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

Les profils se créent uniquement via les formulaires des deux personnes ; aucun profil de démonstration ne peut être chargé.
La V1 reste accessible à `/v1/demo` et `/v1`.
Pour un couple de démonstration prêt à utiliser :
`CHANDELLE_DEV=1 bash scripts/run.sh`, puis Settings → Create test profiles.
Cette commande crée uniquement les profils, jamais des activités. Les anciennes
routes V1 de recherche renvoient 410 et indiquent la route authentifiée actuelle.

## Limites et données

Les sorties affichées proviennent exclusivement d'une recherche web demandée depuis
Ask ou Discover. Les cartes restent consultables avec un prix ou un horaire inconnu ;
la composition exige les informations nécessaires. Une citation ne prouve pas une
place disponible. Aucune réservation ni paiement automatique.

Les données restent dans `.runtime/`, exclu de Git comme `.env`, `.venv` et les
caches. Les jetons locaux isolent les profils ; ils ne constituent pas une
connexion de production. Les imports de liens ne téléchargent pas de vidéo.

Copier les paramètres utiles de `backend/integrations/.env.example` dans le `.env`
ignoré à la racine, sans écraser ses valeurs existantes. Pour la recherche, configurer
`OPENAI_API_KEY`, `OPENAI_ENABLED=1` et `OPENAI_WEB_ENABLED=1`. Sous Windows,
`powershell -ExecutionPolicy Bypass -File scripts/run_ai.ps1` charge ces paramètres.
Une absence de clé, un quota atteint ou une panne produit un message explicite,
sans recours à des données fictives. Les tests par défaut ne font aucun appel payant.

## Recherche web unique : Ask et Discover

Les deux formulaires appellent `POST /api/v2/dates/search` (alias `/api/dates/search`).
`PlanningService.query` analyse la demande, appelle `C_discovery/web.py`, vérifie les
sources puis applique les critères de mémoire, de temps et de budget. Les cartes
existantes consomment `activities` ; `proposals` contient uniquement les programmes
réalisables avec ce lot. Aucun deuxième catalogue n'alimente Discover.

Le cache privé des recherches est valable six heures et les sélections sont conservées
24 heures. Les faits publics sont mis à jour par identifiant source dans `v2_activities`.
Une panne ne vide pas cette table et ne l'utilise pas comme résultat de secours.
Les fiches marquées `demo=true` sont retirées au démarrage, sans supprimer les profils,
les souvenirs ou l'historique des programmes.

Chaque réponse porte `search_id`, `status`, `empty_reason`, `message` et `trace`.
`GET /api/v2/runs/{search_id}`, avec le jeton du propriétaire, permet de relire les
étapes : analyse, recherche, validation des sources, région, expiration, catégorie,
budget, rayon, disponibilité annoncée, horaire, exclusions, jours, accessibilité,
alimentation, mobilité, goûts demandés, doublons et composition. Les filtres indiquent
`before`, `after`, `removed` et `unknown`. Les logs `activity_search` portent le même
identifiant ; la requête y est représentée par son empreinte, sans texte personnel.

Trois situations sont distinctes : aucune piste web, pistes toutes filtrées (avec
le filtre bloquant), service indisponible. Des fiches incomplètes peuvent donner des
cartes sans programme ; le panneau explique les informations manquantes. Les prix
inconnus ne deviennent jamais zéro et les heures suggérées sont signalées.

Pour lancer le parcours navigateur sans fournisseur ni crédit, utiliser une base de
test isolée, jamais la session de l'équipe :

```powershell
$env:RUN_WEB_UI_FIXTURE='1'
$env:OPENAI_API_KEY='test-placeholder-not-a-key'
python -m uvicorn backend.tests.serve_web_fixture:app --host 127.0.0.1 --port 8321
# Dans un second terminal, avec Playwright/Edge disponibles :
node scripts/test_activity_cards_browser.cjs
```

Les réponses fournisseur des tests sont générées à la demande dans
`backend/tests/web_provider.py` et `frontend/tests/activity-data.mjs`. Ces fichiers
ne sont ni montés dans les assets publics ni importés par l'application.
`RUN_LIVE_WEB_PIPELINE=1 python scripts/live_web_pipeline.py` est un test réel
facultatif : il utilise la clé serveur et le quota SQLite de l'application, crée des
profils de test séparés et écrit sa preuve dans `.runtime/web-live-result.json`.
La limite locale est une réservation prudente, pas la facture du fournisseur.
Les résultats réels et les limites observées sont dans `docs/v2/TEST_MATRIX.md`.

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

## Agendas Google / Outlook et propositions automatiques

L'extension utilise le serveur FastAPI, les profils et la SQLite V2 existants. Elle lit les plages occupées de l'agenda principal, les croise entre les deux membres et peut créer, modifier ou supprimer une sortie après leur confirmation. Aucun titre de rendez-vous personnel n'est stocké. Les jetons OAuth et le cache des plages occupées sont chiffrés avec Fernet. Une connexion remplace le compte précédent du même profil.

### Fichiers ajoutés

```text
backend/integrations/calendar/
  provider.py                 # TimeSlot, CalendarEvent, CalendarProvider
  oauth_config.py             # configuration des SDK officiels
  calendar_auth.py            # OAuth, state, PKCE, caches chiffrés
  store.py                    # persistence dans la SQLite V2
  google.py                   # Google Calendar v3
  outlook.py                  # Microsoft Graph
backend/streams/A_calendar/
  time_slots.py               # fonctions existantes partagées, sans cycle d'import
  calendar_read.py            # lecture et créneaux communs
  calendar_write.py           # confirmation à deux, écritures et reprises
backend/streams/G_proactive/
  mood_rules.py               # déclarations d'humeur explicites
  mood_tracker.py             # données récentes et consenties, OpenAI facultatif
  notification_service.py     # notifications persistantes dans le fil
  scheduler.py                # APScheduler, états et verrou de tâche
backend/api/calendar.py
backend/tests/test_calendar.py
frontend/app/calendar.mjs
frontend/tests/test_calendar.mjs
scripts/init_calendar_env.py
scripts/test_calendar_browser.cjs
```

`A_calendar/service.py`, `G_proactive/service.py`, les routes et les écrans existants sont étendus. Il n'y a pas de serveur ou de mémoire parallèle.

### Préparer le serveur de test

Depuis la racine du dépôt, sans remplacer un `.env` existant :

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe scripts/init_calendar_env.py
```

Ce script crée une clé `CALENDAR_TOKEN_KEY` privée si elle manque, conserve les réglages existants et n'affiche aucun secret. Garder cette clé lors des redémarrages ; sa perte exige une reconnexion des comptes. Le modèle public est `backend/integrations/.env.example`. Les secrets vont uniquement dans le `.env` ignoré à la racine, jamais dans le front ou dans un message.

`CALENDAR_REDIRECT_BASE` doit être exactement l'origine utilisée dans le navigateur. Par exemple `http://127.0.0.1:8000`, sans chemin final. Ne pas mélanger `localhost` et `127.0.0.1` : cookies OAuth et profils locaux sont attachés à l'origine. Hors machine locale, HTTPS est obligatoire pour le callback.

### Google, compte de test

1. Dans Google Cloud Console, créer/sélectionner un projet de test et activer **Google Calendar API**.
2. Configurer l'écran de consentement Google Auth Platform et ajouter les deux comptes aux utilisateurs de test si l'application est externe en mode test.
3. Créer un client OAuth de type **Application Web**, avec l'URI de redirection exacte : `{CALENDAR_REDIRECT_BASE}/api/calendar/callback/google`.
4. Renseigner `GOOGLE_CLIENT_ID` et `GOOGLE_CLIENT_SECRET` dans le `.env` local. Le scope demandé est `https://www.googleapis.com/auth/calendar`.
5. Relancer `powershell -ExecutionPolicy Bypass -File scripts/run_ai.ps1`. Dans Chandelle, ouvrir **Disponibilités**, choisir son profil, cliquer **Google Calendar**, accorder l'accès puis **Actualiser mon agenda**. L'autre personne fait la même chose dans son propre profil.

Le code utilise `google-auth-oauthlib` et `google-api-python-client`, avec accès hors ligne pour rafraîchir le jeton. Les politiques de test/consentement Google peuvent limiter sa durée ; une révocation ou une expiration demandera une reconnexion. [Documentation OAuth Google](https://developers.google.com/identity/protocols/oauth2/web-server).

### Outlook, compte de test

1. Dans Microsoft Entra, **App registrations**, créer une application serveur. Pour Outlook.com et les organisations, choisir le type de comptes qui accepte les comptes personnels et les annuaires d'organisation.
2. Ajouter une plateforme **Web**, callback exact `{CALENDAR_REDIRECT_BASE}/api/calendar/callback/outlook`. Pour une URL HTTP en `127.0.0.1`, suivre la configuration par manifeste documentée par Microsoft ; le portail n'accepte pas toujours cet ajout dans le champ ordinaire. `http://localhost:8000` fonctionne pour un environnement local entièrement ouvert sous cette même origine. [Règles Microsoft sur les URI de redirection](https://learn.microsoft.com/en-us/entra/identity-platform/reply-url).
3. Ajouter la permission **déléguée** Microsoft Graph `Calendars.ReadWrite`. Créer un secret client puis placer sa **valeur**, le client ID et `MICROSOFT_TENANT_ID=common` dans le `.env`. Un tenant d'entreprise peut demander un accord administrateur.
4. Relancer le serveur et choisir **Outlook / Microsoft** dans Disponibilités. Le SDK MSAL conserve son cache chiffré et renouvelle les jetons.

La lecture utilise `/me/calendarView`, occurrences récurrentes comprises, car `/me/calendar/getSchedule` ne prend pas en charge les comptes Microsoft personnels. Pagination limitée à 10 pages de 100 ; dépassement ou réponse partielle invalide bloque la disponibilité, sans faire croire que l'agenda est libre. [calendarView](https://learn.microsoft.com/en-us/graph/api/user-list-calendarview?view=graph-rest-1.0), [limite getSchedule](https://learn.microsoft.com/en-us/graph/api/calendar-getschedule?view=graph-rest-1.0).

### Tester le parcours

Les créneaux occupés viennent des agendas connectés. Sans plage personnelle saisie, les sorties sont recherchées entre 18 h et 23 h, heure de Paris, sur sept jours. Une plage saisie limite ces horaires. Un partenaire sans agenda connecté ni plage explicite n'est jamais supposé libre. Le cache est valable 15 minutes ; une erreur exige une actualisation. Un POST `/api/v2/calendar/sync` n'actualise que le compte du membre authentifié.

Accepter un programme puis ouvrir **Ajouter cette sortie aux agendas**. Chaque membre confirme la même version. Au deuxième accord, le serveur écrit dans chaque agenda connecté. Un programme modifié exige deux nouveaux accords. Après annulation, les deux confirmations autorisent la suppression. Les succès partiels sont conservés ; le bouton de nouvelle tentative ne réécrit pas le compte déjà synchronisé. Les identifiants déterministes Google et `transactionId` Outlook réduisent les doublons après interruption. Aucun invité n'est ajouté.

Les programmes proviennent de la même recherche web qu'Ask et Discover. Les deux confirmations restent nécessaires avant toute écriture externe. Les anciens programmes fictifs conservés dans l'historique restent bloqués par défaut ; `CALENDAR_ALLOW_DEMO_EVENTS` est réservé aux tests explicites.

### Proactivité et notification dans le fil

Chaque personne active ses propositions dans Disponibilités. Le job vérifie sept jours sans date confirmée passée, cherche un créneau commun d'au moins deux heures, puis appelle le même orchestrateur E. Sans historique, le délai part de la création du couple. Une sortie future déjà confirmée bloque une nouvelle proposition. Une proposition en attente n'est pas dupliquée ; un refus impose 24 heures de pause.

Score : délai admissible 0,4 + créneau 0,3 ; humeur positive suffisamment fiable des deux +0,2 ; stress/fatigue fiable d'une personne -0,15 ; événement pertinent vérifié +0,1. Seuil 0,5. Ce dernier bonus reste à zéro tant qu'aucune preuve d'événement pertinent n'est raccordée au calcul. Les humeurs et textes privés ne sont pas exposés dans la notification. Un goût isolé n'est pas une émotion, un import récent n'actualise pas la date du signal. Sans indice récent autorisé, humeur neutre et confiance zéro.

L'analyse locale est gratuite. L'analyse OpenAI facultative exige `PROACTIVE_MOOD_OPENAI=1`, la configuration OpenAI existante et un accord séparé par personne. Elle envoie au maximum cinq courts extraits de conversations mémorisées ou de feedback autorisés pour les recommandations, jamais les notes privées ; au plus une tentative par jour et par personne. Les déclarations explicites reconnues localement évitent l'appel. Le quota existant s'applique. Aucun nouvel outil de push n'est ajouté.

Pour la démo immédiate, `CHANDELLE_DEV=1` affiche **Test : ignorer les sept jours**. Ce bouton conserve les exigences d'accord et de créneau. L'API équivalente, avec le `X-Member-Token` existant, est `POST /api/proactive/trigger/{couple_id}` avec `{"demo":true}`. Avec `{}` le calcul respecte le délai normal. Le membre ne peut déclencher que son couple. La proposition et sa notification sont conservées en SQLite ; **Voir le programme** ouvre le DatePlan existant.

Pour activer le job, mettre `PROACTIVE_SCHEDULER_ENABLED=1` puis redémarrer le serveur : vérification quotidienne à 09:00 Europe/Paris. `PROACTIVE_DEMO_MODE=1` avec `CHANDELLE_DEV=1` passe à cinq minutes et réduit le délai sans sortie à cinq minutes. Le job tourne seulement quand le serveur reste allumé, avec **un seul worker** dans cette bêta. Il n'installe aucune tâche Windows ou cron externe. Dernier passage, résultat et activation réelle sont visibles dans Disponibilités et `/api/v2/proactive/settings`. Par défaut, le mécanisme est implémenté mais la planification reste désactivée.

### Apple et limites restantes

La documentation Apple actuelle décrit une autorisation par compte Apple pour certaines applications tierces compatibles, avec mot de passe d'application comme alternative. Elle ne fournit pas ici un SDK OAuth public équivalent à Google/Microsoft pour Chandelle. EventKit reste natif. Une connexion CalDAV n'est pas livrée : la découverte des calendriers, les erreurs et les accès iCloud doivent encore être validés avec un compte de test, plutôt que d'afficher une connexion non testée. L'export .ics existant est utilisable dans Apple Calendar. [Accès iCloud tiers](https://support.apple.com/en-us/121539), [mots de passe d'application et double authentification](https://support.apple.com/en-us/102654).

Google/Outlook : adaptateurs codés et tests simulés, mais OAuth réel et écritures réelles restent à valider avec les comptes autorisés. La synchronisation est **lecture des disponibilités + écriture des programmes confirmés** ; déplacer un événement chez le fournisseur affecte la prochaine lecture des disponibilités mais ne réécrit pas automatiquement le DatePlan. Un seul agenda principal par personne, pas de webhooks, pas de push mobile. Déconnecter efface les accès locaux, pas les événements distants ni l'autorisation dans le compte fournisseur. L'authentification par jetons locaux de la bêta nécessite un durcissement avant ouverture publique.


## Trois programmes composables dans Ask (26 septembre 2026)

Dans Ask, choisir « Trois programmes » en mode local ou avec analyse OpenAI, indiquer le nombre d'étapes et lancer la recherche. OpenAI exige le consentement du formulaire. Trois programmes distincts sont affichés lorsqu'au moins trois combinaisons respectent les contraintes. Si seulement une ou deux existent, leur nombre réel et une explication sont affichés. Aucune duplication ni activité inventée pour remplir les cartes.

Glisser à gauche passe à la carte suivante ; à droite marque un intérêt, sans accepter le programme. Les boutons Précédente/Suivante et les flèches du clavier donnent le même accès. « Remplacer » ouvre une fenêtre avec des critères facultatifs. « Comparer et composer » permet de garder jusqu'à trois activités prises dans plusieurs cartes. « Construire mon date » vérifie leur compatibilité, puis ouvre le programme dans le dialogue existant. L'acceptation reste une action humaine distincte.

Les cartes utilisent exclusivement les activités structurées du pipeline web commun. Les champs manquants restent inconnus ; une fiche incomplète est consultable mais ne devient pas un programme inventé. Une heure de visite suggérée ne prouve pas une disponibilité réservable. Les temps de trajet sont des estimations de marche à 4,5 km/h avec cinq minutes de marge, pas un calcul multimodal en direct.

### Fichiers de cette extension

```text
backend/api/dates.py                           # routes authentifiées, même serveur
backend/streams/E_orchestrator/
  date_composer.py                             # score, combinaisons, diversité
  date_intent.py                               # catégorie, cuisine, ordre explicite
  deck_models.py                              # contrat Pydantic du deck
  deck_operations.py                          # pool conservé, remplacement, composer
  service.py                                 # raccordement au parcours E existant
backend/integrations/date_scoring.py           # local ou runtime Pipelex optionnel
backend/integrations/pipelex_dates/
  date_scoring.mthds
  score_functions.py
frontend/src/DateProposalDeck.mts              # TypeScript strict, sans React
frontend/src/date-contract.mts                 # types générés depuis Pydantic
frontend/tests/activity-data.mjs              # contrats générés pour tests uniquement
frontend/contracts/date-deck.schema.json       # schéma généré
frontend/app/DateProposalDeck.mjs              # version compilée chargée par Ask
scripts/generate_date_contract.py
scripts/test_date_deck_browser.cjs
backend/tests/test_date_deck.py
frontend/tests/test_date_deck.mjs
```

### API et critères

Les nouvelles routes sont `/api/dates/search`, `/api/dates/{id}/replace-activity`, `/api/dates/compose`, avec alias `/api/v2/dates/...` pour le client existant. Toutes nécessitent `X-Member-Token` et les deux entretiens terminés. `couple_id` ne choisit jamais l'identité : s'il est fourni, il doit correspondre au jeton.

```json
{
  "constraints": {
    "text": "Un japonais puis une balade",
    "activity_count": 2,
    "budget": 100,
    "time_window": {"start": "2026-09-26T18:00:00+02:00", "end": "2026-09-26T23:00:00+02:00"},
    "max_total_duration_minutes": 300,
    "max_travel_time_minutes": 30,
    "mode": "auto"
  },
  "cloud_consent": false
}
```

`search` retourne `search_id`, `proposals`, `warnings`, `composition`. `compose` accepte `selected_activity_ids` et `search_id` (conseillé pour éviter d'utiliser la dernière recherche d'un autre onglet). Le pool est lié au profil qui a fait la recherche ; aucun tableau SQL supplémentaire. Il est conservé dans les champs internes des plans, jamais renvoyé au navigateur, et expire après 24 heures même après une recomposition. Les API historiques `/recommendations/query` et `/date-plans/...` restent utilisables.

Le remplacement garde toutes les données des étapes intactes, pas seulement leurs IDs. Les horaires, prix ou coordonnées modifiés depuis la recherche invalident leur ancien instantané. Les exclusions et disponibilités sont revérifiées. Pas de nouvelle recherche fournisseur. Critères de remplacement pris en charge : vocabulaire local français/anglais des catégories, japonais, italien, jazz, calme, etc., refus explicites et montant en euros. Par défaut le prix concerne une personne ; écrire « à deux » pour le total. Un texte sans critère reconnu est refusé ; ce formulaire ne prétend pas comprendre toutes les formulations.

### Ajuster les scores pour la démonstration

Dans `date_composer.py`, `SCORE_WEIGHTS` applique goût .35, créneau compatible .20, distance .15, budget .10, nouveauté .10, popularité .10. Chaque composante est bornée entre 0 et 1. Les goûts viennent des scores existants de B/C après consentement, sans réinterprétation payante. La popularité inconnue vaut .5 comme valeur neutre de calcul, sans être présentée comme un avis. Les contraintes strictes et les refus passent avant tout score.

`DIVERSITY_STRENGTH=.65` règle l'écart recherché entre propositions. Le baisser privilégie le score individuel ; le monter pénalise davantage les ressemblances. La similarité combine le recoupement d'activités (50 %), les catégories (25 %), un budget à moins de 15 % d'écart (15 %) et les tags d'ambiance communs (10 %). Un bonus .06 récompense chaque catégorie complémentaire et une pénalité réduit les attentes très longues. Les combinaisons contiennent exactement le nombre d'étapes demandé, au maximum 100 candidats et 161 700 triplets. La trace enregistre le nombre de combinaisons et les IDs choisis sans texte personnel.

Les sous-titres et explications sont déterministes par défaut pour limiter les crédits. `OPENAI_PLAN_EXPLANATIONS=1` autorise les explications courtes via l'adaptateur et le quota existants, seulement pour une recherche ayant consenti à OpenAI. Aucun appel supplémentaire n'est nécessaire pour swiper ou comparer.

### Pipelex et compilation

`DATE_SCORING_BACKEND=local` fonctionne immédiatement. `pipelex` sélectionne l'adaptateur du runtime local optionnel. Le fichier `.mthds` appelle un `PipeFunc` qui utilise exactement le même calcul Python. Aucune nouvelle clé ni requête LLM pour ce score. L'adaptateur vérifie la sortie et revient au calcul local si le runtime manque ou échoue ; `composition.scoring_backend` et `scoring_fallback` indiquent ce qui a réellement tourné. Le runtime Pipelex n'est pas installé dans l'environnement vérifié : TOML et adaptateur testés, exécution Pipelex réelle non validée. Ne pas présenter ce mode comme actif au jury avant un test du runtime.

Références officielles consultées le 26 septembre 2026 : [PipeFunc](https://docs.pipelex.com/latest/building-methods/pipes/pipe-operators/PipeFunc/) et [exécution Python des méthodes](https://docs.pipelex.com/latest/building-methods/pipes/executing-pipelines/). L'interface est adaptée au runtime actuel ; le schéma proposé avec des sous-pipes non définis n'a pas été recopié tel quel.

Le serveur sert les `.mjs` compilés inclus ; Node n'est nécessaire que pour modifier le composant TypeScript. Depuis la racine du dépôt, avec Node et pnpm disponibles :

```powershell
python scripts/generate_date_contract.py
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
python scripts/generate_date_contract.py --check
node frontend/tests/test_date_deck.mjs
python scripts/test_offline.py backend/tests/test_date_deck.py --tb=short
```

Les composants restent testables par injection de contrats générés depuis `frontend/tests/activity-data.mjs`. Aucun exemple fictif n'est servi dans `frontend/app/`. Les types sont générés depuis les modèles Pydantic et compilés en modules `.mjs`.

## Cartes d'activités, 27 septembre 2026

Ask affiche désormais une activité par carte. Garder, passer et retirer ne modifient
pas la mémoire : ce sont des choix temporaires pour cette recherche. Découverte et
Vue d'ensemble utilisent le même état. Le panneau Mon date affiche la sélection,
le prix pour deux et les avertissements d'horaires/trajets. Construire mon date
appelle la composition existante ; confirmation, remplacement et calendrier restent
sur le résumé final existant.

Fichiers front (TypeScript strict, modules compilés livrés dans `frontend/app/`) :

- `frontend/src/ActivityCard.mts` : carte, illustration SVG par catégorie, photo réelle
  lorsqu'une URL HTTPS publique figure au catalogue, repli illustration si échec.
- `frontend/src/ActivitySwipeDeck.mts` : boutons, gestes, clavier, vues communes,
  contrôle du profil actif et préchargement des trois prochaines photos disponibles.
- `frontend/src/MyDateBuilder.mts` : sélection, total, estimation à pied et conflits.
- `frontend/tests/activity-data.mjs` : contrats de test uniquement, hors assets publics.

Les types proviennent toujours de `deck_models.py` et du générateur existant.
Après une modification Python : `python scripts/generate_date_contract.py`.
Après une modification TypeScript : `node frontend/node_modules/typescript/bin/tsc -p frontend/tsconfig.json`.
Le serveur sert les `.mjs` compilés ; aucun nouveau framework ou serveur front.

`POST /api/dates/search` conserve `proposals` pour les anciens consommateurs et
ajoute `activities`, `budget_cap`, les limites de trajet/durée et `requested_steps`.
Les cartes réutilisent le lot web filtré, au plus seize fiches validées par réponse. Une sélection manuelle de 1 à
50 activités est vérifiée sans énumérer toutes les combinaisons. Même lorsqu'aucun
programme complet ne convient, les activités individuelles peuvent rester proposées.
Le serveur revalide les contraintes de mémoire et calendrier à la composition.

La recherche est enregistrée dans la SQLite existante et appartient au profil qui
l'a demandée. Expiration : 24 h. Aucun partage de notes privées dans les cartes.
Une sélection incompatible reste visible après un refus de composition ; elle ne
crée pas un faux programme. La sélection est conservée entre vues, pas après un
rechargement de page ni un changement de profil.

### Nettoyage des mentions de moteur

Audit initial et résultat : `docs/v2/UI_AUDIT.md`. Aucun libellé produit ni contrôle
des écrans actifs ne demande d'activer OpenAI/ChatGPT. Les champs techniques internes
et les anciens contrats API restent disponibles. Ask et mémoire envoient `mode=auto` ;
la recherche web et l'upload envoient `processing=standard`. Ce mode n'enregistre pas
un consentement fictif. La configuration serveur et les plafonds restent souverains.
Les permissions d'utiliser une vidéo, le partage des goûts et les confirmations de
calendrier restent explicites. La normalisation vidéo réelle reste désactivée si
`REELS_LIVE_ENABLED` vaut 0. Le scoring demeure déterministe ; ce ticket ne remplace
pas les règles locales par un appel supplémentaire au modèle.

Limites : les cartes viennent du web ; seules celles ayant prix, horaires et coordonnées
peuvent être composées. La couverture et les horaires restent à confirmer auprès des lieux. Pas de note, photo ou distance utilisateur
inventée. Les trajets sont des estimations entre coordonnées, pas des itinéraires.
Aucune page juridique complète n'est fournie par cette modification ; sa rédaction
et la validation de l'information sur les traitements restent à traiter avant
ouverture publique. Les mentions légales ne sont pas visées par le nettoyage.

Vérifications : `node frontend/tests/test_activity_cards.mjs`, puis, contre une
instance de test locale isolée, `node scripts/test_activity_cards_browser.cjs`.
`test_date_deck_browser.cjs` est conservé comme alias vers ce nouveau parcours actif.
Ne lancez pas les scripts de navigateur sur la base utilisée par l'équipe.

Arborescence du delta :

```text
backend/streams/E_orchestrator/activity_choices.py
backend/streams/E_orchestrator/{service,deck_models,deck_operations,date_composer}.py (étendus)
backend/api/dates.py (réponse étendue)
frontend/src/{ActivityCard,ActivitySwipeDeck,MyDateBuilder}.mts
frontend/app/{ActivityCard,ActivitySwipeDeck,MyDateBuilder}.mjs
frontend/tests/test_activity_cards.mjs
backend/tests/test_activity_cards.py
scripts/test_activity_cards_browser.cjs
docs/v2/UI_AUDIT.md
```

Les modules app/ai.mjs, app.mjs, experiences.mjs, calendar.mjs et share-page.mjs
portent le nettoyage produit. Les détails et diff de formulations sont dans l'audit.

### Voix Gradium et intégration de la branche de Noé

Discover contient le chandelier et le dialogue de Noé. Le bouton « Discuter avec
Chandelle » ouvre la voix ou son alternative texte. La recommandation rejoint la
même recherche web et les mêmes cartes qu'Ask ; aucun catalogue fictif ne sert de
secours. Le journal personnel est accessible depuis Memories.

Sous Windows, `scripts/run_ai.ps1` charge aussi `GRADIUM_ENABLED`,
`GRADIUM_API_KEY` et `GRADIUM_VOICE_ID` depuis le `.env` privé. Les noms et valeurs
désactivées sont dans `backend/integrations/.env.example` ; le guide détaillé est
dans [docs/v2/GRADIUM.md](docs/v2/GRADIUM.md). Sans accès configurés, le dialogue
reste utilisable au clavier. Les tests Gradium utilisent un fournisseur simulé.

L'import iCal Google et les connexions OAuth Google/Outlook coexistent dans
Disponibilités. L'import iCal est ponctuel et doit être relancé après modification
de l'agenda ; il ne remplace pas une connexion OAuth.

### Catalogue importé depuis les fichiers Excel

Les fiches fournies sont livrées dans
`backend/streams/C_discovery/data/imported_catalog.jsonl.gz` (495 Ko), avec un bilan
dans `import_report.json`. Les Excel originaux ne sont ni modifiés ni servis au
navigateur. L'archive contient 8 631 fiches uniques : 7 760 lieux Tripadvisor,
160 bars MisterGoodBeer, 105 films AlloCiné et 606 articles Sortiraparis. Le démarrage habituel importe
cette archive dans **la même** `.runtime/chandelle_v2.sqlite3`, table
`v2_activities`. Un index FTS5 permet les recherches sans charger toutes les
fiches dans le navigateur ou les envoyer au modèle. L'archive est une version
portable des données, pas une seconde base.

Ask, Discover et le dialogue vocal passent par la même recherche. Une sélection
locale suffisante évite l'appel web pour une demande générale. Une date précise
ou un manque de candidats déclenche la recherche web existante, avec au maximum
huit références publiques pour l'orienter. Ses plafonds restent inchangés. Si ce
service est indisponible, les fiches importées pertinentes restent consultables.
L'analyse de la demande peut toujours utiliser un appel texte lorsque le serveur
est configuré ; la base complète n'est jamais transmise. Les refus et règles de
confidentialité existants restent appliqués.

Les étoiles et gammes `$` / `$$ - $$$` / `$$$$` sont des indications de l'export,
jamais un prix en euros ni une validation récente. Les mentions « Open now », les
avis, doublons de liens et SVG incorporés sont retirés. Les films restent des
références pour rechercher des séances. Les articles périmés, annulés, éditoriaux
ou sans localisation francilienne suffisante ne deviennent pas des sorties.
Les dates relatives sans année restent inconnues. Les pistes incomplètes sont
gardables mais non composables tant que prix, horaires et localisation manquent.
Chaque fiche conserve la source, son identifiant et les lignes Excel d'origine.
La date d'import n'est pas la date de vérification.

Pour préparer une nouvelle version depuis les sept exports et Bar.xlsx (optionnel), puis la charger :

```powershell
python -m pip install -r scripts/requirements-import.txt
python scripts/import_activity_workbooks.py --source "CHEMIN\Data raw" --db .runtime/chandelle_v2.sqlite3
```

Pour recharger uniquement l'archive déjà préparée, sans dépendance Excel :

```powershell
python scripts/import_activity_workbooks.py --db .runtime/chandelle_v2.sqlite3
```

La reprise est idempotente : même identifiant source, même fiche. Les changements
mettent à jour cette fiche, un export partiel ne supprime pas les autres et une
archive invalide laisse la base intacte. `v2_catalog_imports` conserve l'empreinte
et le bilan du dernier import. Il n'y a ni collecte automatique des sites ni
planification d'actualisation activée pour ces fichiers.

Les 160 bars de `Bar.xlsx` sont classés dans `nightlife` et conservent leur adresse,
leurs tags et les tarifs explicitement annoncés par pinte. `pint_price_from_eur`
ne remplit jamais `price_per_person` : le budget de la sortie reste inconnu.
Les 111 textes de conditions sont conservés dans `offer_note` et affichés comme
indications de l’export non vérifiées aujourd’hui. La capacité réservable et le
badge du fournisseur ne prouvent aucune disponibilité. Une recherche « bar
terrasse » écarte les fiches marquées « Pas de terrasse ». Aucun téléchargement
de photos ou appel fournisseur n’est nécessaire pour cet import.
