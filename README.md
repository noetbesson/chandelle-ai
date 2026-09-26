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
l'état des traitements. Le dossier TypeScript `B_memory/video-memory` qui avait
été copié reste intact, mais le serveur Python ne l'exécute pas.

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
Un seul processus serveur est prévu. Il n'y a ni connexion Instagram/TikTok, ni
scraping, ni nouvelle installation PWA dans cette intégration.
