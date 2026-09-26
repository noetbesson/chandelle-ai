# Test evidence

## Gate 0
Executed `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider`: **31 passed in 0.50s**.
Future required gates: B isolation/reopen/conflicts/retrieval/privacy; onboarding idempotency/resume/consent; C fairness/constraints; fake OpenAI and network guard; plans/reviews/uploads; G persistent actions; API errors/static/browserless end-to-end; complete regression.

## Implemented component checks
- `.venv/bin/python -m pytest -q backend/streams/B_memory/test_memory.py backend/streams/B_memory/test_v2_memory.py`: 20 passed in 0.35s (agent execution).
- `.venv/bin/python -m pytest backend/streams/C_discovery/test_v2_discovery.py backend/streams/C_discovery/test_discovery.py -q`: 9 passed (agent execution).
- `.venv/bin/python -m pytest backend/tests/test_v2_openai.py -q`: 21 passed (agent execution).
- `node --check frontend/v2/app.mjs` and `node frontend/v2/test_ui.mjs`: passed (agent execution; privacy handoff/resume module tests).
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider`: 73 passed in 1.17s before API end-to-end tests were added.
- Root temporary-database TestClient developer seed → query → accept → review → suggestion smoke: all returned HTTP 200. No socket used.

## Integration and final QA
- `.venv/bin/python -m pytest backend/tests/test_v2_api.py -q`: 23 passed in 3.95s (QA agent); all socket connects denied.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider`: 103 passed in 5.54s (root, before final DATE-history and UI fixes).
- `.venv/bin/python frontend/v2/verify_api.py`: passed actual static/onboarding/nine-screen/query/selected-activity/accept/review/memory-edit payload sequence.
- `.venv/bin/python scripts/init_v2_demo.py --database /tmp/chandelle-v2-init-check.sqlite3`: passed, initialized schema/catalog.

### Failures encountered and repaired
- Full-suite collection briefly failed with 3 collection errors due to SQL string quoting in G privacy filter. Corrected quoting; next full suite passed 96 tests.
- First global network-guard script executed pytest on import, recursively collecting itself: inner 103 tests passed but wrapper exited 3 with SystemExit collection error. Added main guard; only a subsequent clean exit is accepted as evidence.

## Final acceptance evidence
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/test_v2_offline.py`: **103 passed in 5.68s**, exit 0. Globally forbids socket.connect, connect_ex and create_connection; no live provider tests run.
- `node --check frontend/v2/app.mjs`: exit 0.
- `node frontend/v2/test_ui.mjs`: PASS: welcome/partial-completion gate, private handoff, server resume, active-token isolation, old-screen removal, pre-onboarding settings gate, private identity labels.
- `.venv/bin/python frontend/v2/verify_api.py`: PASS: static assets, 14 interview answers, 2 completions, 9 screen endpoints, query, selected activity inclusion, accept, category review, memory edit.
- `bash -n scripts/run_v2_demo.sh scripts/reset_v2_demo.sh`: exit 0.
- `git diff --check`: exit 0.
- `git check-ignore .runtime/chandelle_v2.sqlite3 .runtime/uploads/example.png .env`: all three ignored.
- Protected-path diff check (`backend/shared`, A/D/F streams, `docs/codex-E`, `docs/night-shift`): no tracked modifications. Pre-existing untracked night-shift AGENTS copy retained.
- Tracked secret/runtime filename check `git ls-files '.env*' '.runtime/*' '*.sqlite*' '*secret*'`: empty.
- Final full suite after adding full personal-data erasure: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/test_v2_offline.py` → **104 passed in 5.84s**, exit 0. This is the final acceptance count (31 original + 73 new). Earlier standard full invocation before this final addition: 103 passed in 5.64s.

## Fusion des projets — 26 septembre 2026

Commandes exécutées dans le dépôt courant :

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/test_v2_offline.py` avant fusion : **104 passed in 5.93s**, code 0.
- Première régression pendant la fusion, même commande : **2 failed, 102 passed in 6.37s**. Tests historiques exigeant les quatre étapes de trace et un seul enregistrement de schéma. Correction : métadonnées calendrier dans l’étape candidates et registre d’extension indépendant ; aucun test historique modifié.
- Après corrections, même commande : **104 passed in 6.59s**, code 0.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_peer_merge.py` : **28 passed in 2.16s**, code 0. Six cas supplémentaires ensuite ajoutés pour snapshots temporels, expiration des suggestions et rejets d’imports.
- **Final** : `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/test_v2_offline.py` : **138 passed in 10.37s**, code 0 (104 préexistants + 34 nouveaux), sockets interdits globalement.
- `node --check frontend/v2/app.mjs` : code 0.
- `node --check frontend/v2/merge.mjs` : code 0.
- `node frontend/v2/test_ui.mjs` : PASS (confidentialité/handoff/reprise existants), code 0.
- `node frontend/v2/test_merge.mjs` : PASS (imports, échappement HTML, consentement, disponibilités, limite de comparaison, prix inconnus, préparation/export, changement d’identité pendant lecture de fichier), code 0.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python frontend/v2/verify_api.py` : PASS, code 0.
- `git diff --check` : code 0.
- `git diff --name-only -- backend/shared backend/streams/A_calendar backend/streams/D_connectors backend/streams/F_booking docs/codex-E docs/night-shift` : sortie vide, code 0.
- `bash -n scripts/run_v2_demo.sh scripts/reset_v2_demo.sh` : code 0.

Pas de test navigateur réel : ni Playwright Python ni navigateur dans son cache local. Aucune installation ou exécution de fournisseur live. Les tests API de fusion couvrent persistance/réouverture, isolation, effacement, formats importés, contraintes de sélection, coûts inconnus, ICS et préparation.

### Validation après réorganisation parallèle du workspace

Les tests frontend ont été déplacés pendant cette intervention. Commande exécutée
après inspection des nouveaux chemins : `bash scripts/check.sh` → code 0,
**138 passed in 10.38s**, les deux suites Node PASS, parcours API frontend PASS,
contrôles de syntaxe JS/shell et `git diff --check` réussis. Chemins courants :
`frontend/tests/test_ui.mjs`, `frontend/tests/test_merge.mjs`,
`scripts/verify_frontend_api.py`. Les commandes précédentes avec `frontend/v2/`
sont les commandes réellement exécutées avant le déplacement.

## Nettoyage architectural — 26 septembre 2026

- Baseline : `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/test_v2_offline.py` → **138 passed in 9.26s**, code 0.
- Baseline : `node frontend/v2/test_ui.mjs && node frontend/v2/test_merge.mjs && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python frontend/v2/verify_api.py` → trois PASS, code 0 (avant déplacement).
- Après nettoyage : `bash scripts/check.sh` → **138 passed in 9.34s**, code 0 ; syntaxe des deux modules JS, deux suites Node, parcours API TestClient, syntaxe shell et `git diff --check` réussis.
- `git check-ignore .runtime/chandelle_v2.sqlite3 .runtime/uploads/example.png .env .env.local backend/example.sqlite3 frontend/node_modules/example frontend/.env.local example.pem` → les huit chemins sont ignorés, code 0.
- `git diff --name-only -- backend/shared backend/streams/A_calendar backend/streams/D_connectors backend/streams/F_booking docs/codex-E docs/night-shift` → sortie vide, code 0.
- `git ls-files '.env*' '*.sqlite*' '*.db' '*.pem' '*.key' '*DS_Store*'` → sortie vide, code 0. Contrôle de noms de fichiers sensibles, pas audit exhaustif de secrets dans l’historique Git.

Le starter Next.js n’était pas utilisé par le runtime. Les tests déplacés sont
conservés avec adaptation de leurs chemins uniquement. Aucun test live ni
installation de dépendance n’a été exécuté pour le nettoyage.

## Réorganisation MECE des streams — 26 septembre 2026

- Baseline : `bash scripts/check.sh` → code 0, **138 passed in 9.74s**, deux suites Node et parcours API frontend PASS.
- Après déplacements A–H/consolidation V1 : `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/test_v2_offline.py` → code 0, **138 passed in 9.96s**.
- Après consolidation documentaire, extraction de la conversation H et du feedback C et ajout des gardes d’architecture : `bash scripts/check.sh` → code 0, **141 passed in 9.97s** ; syntaxe JS, `frontend/tests/test_ui.mjs`, `frontend/tests/test_experiences.mjs`, parcours TestClient, syntaxe shell et `git diff --check` réussis.
- Les 3 nouveaux tests analysent le code sans importer le serveur : chaque stream possède un point d’entrée actuel ; aucun stream n’importe l’API ; le stockage n’importe pas le métier ; le graphe local n’a pas de cycle.
- Le module `test_legacy_api.py` rassemble les anciens tests `api/test_app.py`, `test_pipeline.py` et `test_system.py`, sans suppression de cas ni d’assertion. Les autres tests ont uniquement des imports adaptés aux nouveaux chemins.
- Inventaire des fichiers dans backend/frontend/docs/scripts/mocks, hors `__pycache__` et `.pyc` : **138 → 92**. Backend **87 → 54**, docs/v2 **16 → 6**. Cette mesure compare l’état au début de ce tour, pas la branche Git initiale (déjà modifiée).

Les chemins figurant dans les preuves précédentes restent historiques. Commande
courante unique : `bash scripts/check.sh`. Aucun appel live ni nouvelle dépendance.

## Regroupement des tests et retrait des noms de livraison

- Comparaison AST des fonctions `test_*` avant/après regroupement : **100 fonctions strictement identiques**, signatures et assertions comprises ; 13 fichiers deviennent 8. Les imports nécessaires sont adaptés hors des fonctions.
- `bash scripts/check.sh` → code 0 : **141 passed in 10.38s**, deux suites Node et parcours API TestClient PASS ; syntaxe JS/shell et `git diff --check` réussis.
- Commandes courantes : `bash scripts/run.sh` pour lancer, `bash scripts/check.sh` pour vérifier. Les anciens chemins run_v2_demo/test_v2_offline dans les preuves précédentes décrivent les commandes exécutées à ces dates.

## Audit de raccordement de la mémoire vidéo (26 septembre 2026)

| Vérification | Résultat observé | Code concerné |
| --- | --- | --- |
| Le code importé est-il réellement appelé ? | Oui : route enregistrée dans le FastAPI existant, formulaire Inspirations raccordé. Le dossier TypeScript préexistant est conservé mais inactif. | api/routes.py, api/reels.py, frontend/app/experiences.mjs |
| Le signal rejoint-il B ? | Oui : TasteSignal dans une inspiration PERSON de v2_facts, même base et même service. | streams/B_memory/reels.py, service.py |
| Attribution et confidentialité | Propriétaire issu du jeton serveur, paramètres d'identité refusés, inspiration privée, job inaccessible au partenaire. | api/reel_receive.py, api/reels.py |
| Influence réelle sur le classement | Classement inchangé avant confirmation, différent après consentement COUPLE_RECOMMENDATION. | tests/test_reels.py, parcours B/D/C existant |
| Ancienneté | Signal de 2020 conservé comme tel ; une confirmation temporaire ne le rend pas récent. | tests/test_reels.py |
| Doublons | Même signal_id, un seul fait actif, aucun renforcement à la relance ; même comportement en mode asynchrone. | streams/B_memory/reels.py |
| Effacement | Suppression des jobs du profil ; job annulé incapable de réécrire la mémoire ; fichiers temporaires nettoyés. | api/routes.py, tests/test_reels.py |
| Redémarrage | Job interrompu marqué failed/INTERRUPTED et fichiers nettoyés. Pas de reprise automatique annoncée. | api/reels.py |
| Formats et erreurs | MP4/MOV bornés en taille/durée, contrôle signature et FFprobe, autorisation requise, URL locale refusée. | api/reel_receive.py, integrations/reels/extract_audio.py |
| Gradium / OpenAI / Pipelex | Contrats et erreurs testés avec transports simulés ; aucun appel fournisseur réel. | tests/test_reel_media.py, test_reel_normalize.py |

Les MP4 utilisés pour la preuve sont générés localement par le vrai FFmpeg. Les
extractions audio avec et sans piste sont exécutées réellement. Les recommandations
utilisent le catalogue fictif existant. Le mode local analyse les mots de la
légende ; il ne transcrit pas l'audio sans fournisseur configuré.

Vérifications UI : `node --check` sur app.mjs/experiences.mjs, deux suites Node et
`scripts/verify_frontend_api.py` réussis. Test du formulaire multipart, consentement,
taille et échappement ; parcours existants d'entretien, choix d'activité,
acceptation, feedback et édition mémoire préservés. Vérifications sans navigateur
visuel ; aucun test de partage natif Android/iOS effectué dans ce dépôt.

Adaptations de test : tzdata pour ZoneInfo sous Windows ; six identifiants courts
pour les tests d'upload existants, car le nom automatique de l'échantillon de 5 Mio
dépassait la limite Windows des variables d'environnement. Aucune assertion retirée.
La paire de sockets interne d'asyncio est autorisée dans le lanceur Windows ; les
connexions réseau des fournisseurs restent bloquées.

Limites : identité locale par jeton, base SQLite non chiffrée, un seul processus
serveur et tâches en mémoire, pas de publication autorisée. Cet audit confirme le
raccordement fonctionnel local et les contrôles testés, pas une homologation de
sécurité pour un service public.

Résultats exécutés : suite complète `scripts/test_offline.py --tb=short
--junitxml=.runtime/memory-tests.xml` : **195 passed en 119,97 s**. Après ajout du
contrôle protégeant une inspiration corrigée manuellement contre un réimport,
les **10 tests d'intégration vidéo ont été rejoués et passent en 11,07 s**
(`.runtime/reel-final-tests.xml`). Les deux suites Node, la syntaxe JS et le parcours
API des écrans passent également. `git diff --check` ne signale aucune erreur.
Les rapports bruts restent dans `.runtime/`, ignoré par Git. Aucun test fournisseur
live, commit, push ou déploiement.

## Réception PWA depuis Instagram/TikTok

Code ajouté et testé sur la branche locale maxime/memory-reels, sans push ni
publication. La copie TypeScript supprimée précédemment n'est pas recréée.

- `scripts/test_offline.py --tb=short --junitxml=.runtime/pwa-regression.xml` :
  **198 passed en 97,09 s**, réseau fournisseurs interdit. Les 196 cas existants
  restent présents, plus deux tests de livraison PWA et de refus d'upload anonyme.
- `node frontend/tests/test_ui.mjs`, `test_experiences.mjs` et `test_share.mjs` :
  PASS. Validation du partage texte/lien/fichier, type, nom sans extension,
  taille, URL trompeuse, champs répétés, champ d'identité et métadonnées d'expiration.
- `node --check` : app.mjs, experiences.mjs, share-page.mjs, share-store.mjs,
  pwa.mjs et sw.js PASS.
- `scripts/verify_frontend_api.py` : PASS, entretiens et parcours existants conservés.
- `scripts/test_share_browser.cjs`, Playwright avec Microsoft Edge, largeur 375 px :
  PASS. Deux exécutions réussies, dont la dernière inclut la reprise d'un job.
  Vrai service worker, vraie navigation POST multipart interceptée, vrais blobs
  IndexedDB, même API FastAPI et vraie extraction FFmpeg d'un MP4 synthétique.
  Choix de profil obligatoire, lien seul sans fausse transcription, inspiration
  privée, conflit d'attribution refusé, suivi/reprise du job, suppression,
  expiration et quota vérifiés. CacheStorage contient uniquement CSS et icônes.
  Aucun débordement horizontal à 375 px ; captures contrôlées visuellement.
- Preuves locales ignorées par Git : `.runtime/pwa-regression.xml`,
  `.runtime/pwa-regression.txt`, `.runtime/pwa-link-mobile.png`,
  `.runtime/pwa-success-mobile.png`. Base de test séparée dans `.runtime/`,
  réservée aux fixtures ; aucune nouvelle base mémoire produit.
- `git diff --check` : PASS.

Le partage natif Android depuis les applications installées n'est PAS validé par
ces tests : ils simulent la navigation que le système transmet à la PWA, puis
exécutent réellement toute la réception. À vérifier sur téléphone avec HTTPS et
installation PWA. Le fichier fourni par Instagram/TikTok n'est pas garanti ; le
cas lien seul est pris en charge. Sur iOS, l'alternative documentée est l'import
manuel. Aucun appel Gradium/OpenAI/Pipelex réel ; pas de transcription live annoncée.

Le dossier temporaire de tests de ce tour est `.runtime/pwa-temp` : l'ancien
répertoire pytest était inaccessible aux permissions courantes. Aucun accès forcé
à cet ancien dossier. Les données du projet et les fichiers utilisateur préexistants
non liés à ce changement sont conservés.

## Discover OpenAI et conversations, 26 septembre 2026

- Première vérification : erreur de syntaxe dans une expression régulière et lecture Windows CP1252, corrigées avant validation. Aucun succès annoncé sur cet essai.
- `python scripts/test_offline.py backend/tests/test_openai.py backend/tests/test_api.py backend/tests/test_architecture.py --basetemp=.runtime/ai-test-second --tb=short` : 52 PASS.
- `python scripts/test_offline.py backend/tests/test_ai_discovery.py --basetemp=.runtime/ai-new-tests --tb=short` : 8 PASS. SQLite réelle, réponses OpenAI simulées, cache isolé et expiration, sources obligatoires, refus sans consentement/configuration/quota, erreurs expurgées, quota concurrent persistant, conversations françaises, exclusion effective et suppression.
- `python scripts/test_offline.py --basetemp=.runtime/ai-full-tests --tb=short` : 206 PASS en 69,84 s ; réseau interdit. Inclut garder/remplacer, Reels/PWA et isolation mémoire.
- Derniers ajustements (unités de budget explicites, refus durables, validation des URLs avec l'utilitaire existant, extraction française limitée aux déclarations directes) : `python scripts/test_offline.py backend/tests/test_ai_discovery.py backend/tests/test_openai.py backend/tests/test_architecture.py --basetemp=.runtime/ai-final-focused --tb=short` : 32 PASS.
- `node frontend/tests/test_ai.mjs`, test_ui.mjs, test_experiences.mjs, test_share.mjs : PASS.
- `node --check frontend/app/app.mjs` et ai.mjs : PASS. `python scripts/verify_frontend_api.py` : PASS. Analyse syntaxique PowerShell scripts/run_ai.ps1 : PASS (serveur live non activé).
- `node scripts/test_ai_browser.cjs` avec PLAYWRIGHT_MODULE pointant vers le runtime installé : PASS dans Edge réel à 375x812, API sur 127.0.0.1:8315, base de fixture .runtime/ai-browser-test.sqlite3, fournisseurs désactivés. Discover indique clairement non configuré, modal quota, message français enregistré en mémoire, aucun débordement horizontal, aucun appel payant. Deux exécutions réussies ; captures viewport .runtime/ai-discover-mobile.png et ai-memory-mobile.png. Capture Discover inspectée visuellement.
- `git diff --check` : PASS. Avertissements de conversion LF/CRLF seulement.

Limites : aucun appel OpenAI réel, aucune activité internet réellement ingérée lors des tests. Les réponses sourcées sont simulées dans les tests API. L'UI a été vérifiée avec configuration désactivée ; intégration fournisseur et qualité de recherche nécessitent une clé configurée et un essai réel. Les tests prouvent des changements de classement locaux, pas la disponibilité des lieux.
