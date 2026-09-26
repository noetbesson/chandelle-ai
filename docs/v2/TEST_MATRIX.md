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

## Transfert de discovery — 26 septembre 2026

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s backend/streams/C_discovery/tests -q` : **8 tests réussis**, aucun appel OpenAI live.
- `bash scripts/check.sh` : **149 tests Python et 5 sous-tests réussis** ; la suite s'arrête ensuite avec `node: command not found` (code 127). Les contrôles JavaScript n'ont pas été exécutés dans cet environnement.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/verify_frontend_api.py` : parcours API Python réussi.
- Validation locale du cache : **5 activités** conformes au modèle Pydantic Activity, `match_score` et `why` à `null`.
- `bash -n scripts/check.sh scripts/run.sh scripts/reset_demo.sh` et `git diff --check` : réussis.
- Aucun test live ni appel API pendant ce transfert. Le fichier `.env` n'est pas présent dans le nouveau dépôt ; le cache brut et normalisé provient du premier test effectué dans l'ancien dépôt.

## Regroupement des tests et retrait des noms de livraison

- Comparaison AST des fonctions `test_*` avant/après regroupement : **100 fonctions strictement identiques**, signatures et assertions comprises ; 13 fichiers deviennent 8. Les imports nécessaires sont adaptés hors des fonctions.
- `bash scripts/check.sh` → code 0 : **141 passed in 10.38s**, deux suites Node et parcours API TestClient PASS ; syntaxe JS/shell et `git diff --check` réussis.
- Commandes courantes : `bash scripts/run.sh` pour lancer, `bash scripts/check.sh` pour vérifier. Les anciens chemins run_v2_demo/test_v2_offline dans les preuves précédentes décrivent les commandes exécutées à ces dates.

## Synchronisation Discovery — 26 septembre 2026

- `PYTHONDONTWRITEBYTECODE=1 /private/tmp/chandelle-ai-inspect/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests backend/streams/C_discovery/tests` : **149 passed, 5 subtests passed**, code 0 ; tests hors ligne, aucun appel OpenAI. Exécution dans le dépôt local après fusion des branches.
- Vérification locale du contrat Activity, des quatre fiches (`match_score` et `why` à null), de `.env.example`, et absence de `.env` ou `backend/api` dans le diff préparé : PASS.
