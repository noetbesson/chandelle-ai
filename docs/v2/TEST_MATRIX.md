# Test evidence

## 27 septembre 2026 : profondeur et coût de recherche

À la demande de Maxime, le plafond passe de 2 à 4 appels outils web par demande,
avec un objectif de 16 fiches distinctes au maximum, réparties entre catégories.
La requête est ciblée par le texte utilisateur, les catégories, le budget, la date,
la zone et, sur choix explicite, les thèmes partagés autorisés du couple. Les notes
privées et les refus personnels ne sont pas envoyés au web ; le filtrage local reste
applicable et cette hausse ne corrige pas les refus éliminant les résultats.

Réglages : `OPENAI_WEB_MAX_TOOL_CALLS=4` (1..4), `OPENAI_WEB_RESULT_LIMIT=16` (1..16),
9 000 tokens de sortie, timeout 50 s, zéro retry. Configuration invalide : aucun
appel payant. Le cache tient compte de la profondeur. Les traces distinguent maintenant
le nombre de fiches brutes, d'appels outils terminés, de recherches (`action.type=search`)
et de sources. Les anciens historiques ne permettent pas de compter les appels outils
exacts ; leurs tokens sont enregistrés, pas la facture fournisseur.

Plafond local de réservations : 2 USD/jour sur cette machine (anciennement 1), total
10 USD conservé ; 0,10 USD réservé par tentative web et 0,02 USD par analyse. Ce sont
des allocations prudentes, pas les coûts facturés ni un solde OpenAI.

Tarifs consultés dans OpenAI Docs le 27/09/2026 : recherche web 10 USD/1 000 appels ;
GPT-4.1-mini entrée 0,40 USD/million de tokens, sortie 1,60 USD/million. Le contenu
web est facturé par bloc fixe de 8 000 tokens d'entrée/appel. Donc 100 appels outils
représentent 1,32 USD avant les autres tokens. Estimation de 100 demandes complètes
utilisant chacune quatre recherches : environ 6 à 10 USD selon les tokens, hors taxes,
services additionnels et éventuels tarifs différents. Ce n'est pas un devis garanti.
Sources : https://developers.openai.com/api/docs/pricing et
https://developers.openai.com/api/docs/models/gpt-4.1-mini .

Validation : `python scripts/test_offline.py backend/tests/test_ai_discovery.py
backend/tests/test_web_pipeline.py backend/tests/test_date_deck.py --tb=short
--basetemp .runtime/search-depth-tests` : **40 passed in 43.25s**. Fournisseurs simulés,
aucun appel API payant effectué pour cette modification. Le plafond configuré ne
prouve pas que le modèle utilise quatre recherches ou retourne seize lieux.


## Recherche web et cartes communes, 27 septembre 2026

### Régressions locales exécutées

`python scripts/test_offline.py --tb=short --basetemp .runtime/web-regression-final`
: **255 passed in 150.05s**. Réseau interdit ; fournisseurs simulés. Journal :
`.runtime/web-regression-final.txt`. Les tests qui dépendaient des anciens catalogues
utilisent des réponses fournisseur injectées. Les algorithmes, l'authentification,
la mémoire et les agendas gardent leurs vérifications.

Sept suites Node passent : `test_ai`, `test_ui`, `test_experiences`, `test_share`,
`test_calendar`, `test_date_deck`, `test_activity_cards`. Compilation TypeScript et
`generate_date_contract.py --check` réussis. Tous les modules app `.mjs` passent
`node --check`. `verify_frontend_api.py` passe avec le fournisseur de test injecté.

`test_activity_cards_browser.cjs` : navigateur Edge, 375×812 et desktop, vraie API
locale avec SQLite isolée et fournisseur simulé. Swipe réel, clavier, garder/passer,
sélection entre vues, chevauchement, erreur/reprise de composition, remplacement
sans modifier l'autre étape, confirmation et changement d'identité : PASS.
`test_web_cards_browser.cjs` : Ask/Discover même route, source affichée, prix inconnu,
réponse réelle enregistrée rendue dans les cartes et trois états vides distincts : PASS.
Le rendu de la preuve enregistrée ne constitue pas un deuxième appel fournisseur.
Les captures `.runtime/web-live-cards-mobile.png` et `web-live-cards-desktop.png`
ont été inspectées. Aucun test sur téléphone physique n'est revendiqué.

### Appels réellement exécutés, distincts des simulations

`RUN_LIVE_WEB_PIPELINE=1 python scripts/live_web_pipeline.py`, profil de test isolé,
clé du serveur et réservations du quota SQLite principal. Deux exécutions seulement.

1. Première réponse : 10 fiches brutes, 9 valides/citées, 0 après le filtre IDF.
   Cause observée : département « Paris » au lieu du code « 75 ». Après correction,
   rejeu de la réponse enregistrée sans nouvel appel : 9 passent la région, 1 est
   hors du créneau, **8 cartes**. Une seule fiche possède tous les champs nécessaires
   à la composition ; **0 programme**. Preuve : `.runtime/web-live-replayed.json`.
2. Deuxième appel après correction : HTTP 200, analyse OpenAI sans fallback, 4 fiches
   valides/citées qui décrivent le même restaurant SuMiBi Kaz. Tous les filtres de
   critères conservent les 4, déduplication 4 → 1. **1 carte, 0 programme**, prix et
   horaires inconnus, aucune balade proposée. Preuves : `.runtime/web-live-result.json`
   et `.runtime/web-live-run-2.txt`. La carte et son lien source ont été rendus dans
   le navigateur. Aucun tarif, durée ou disponibilité n'a été ajouté pour remplir un plan.

Les anciennes recherches à zéro du 27/09 à 11:55 UTC n'enregistraient ni la demande
ni les critères analysés. Leur filtre exact est donc indéterminable rétrospectivement.
Le rejeu local indicatif « japonais puis balade », 70 EUR, dans leur fenêtre du vendredi
02/10, conserve cinq anciennes activités. Ce n'est pas une preuve de leur requête exacte.
Ne pas attribuer ce cas historique au bug département constaté dans le nouveau test live.

### Couverture des causes de perte

`test_web_pipeline.py` vérifie séparément région, budget, catégorie, indisponibilité,
horaire, goût demandé, expiration, sortie malformée et URL non citée, avec compteurs
avant/après et état vide lisible. Test de régression « Paris » et doublons inclus.
Les autres filtres ont chacun une trace : rayon, refus, jours, accessibilité,
alimentation et mobilité. Les champs inconnus sont comptés ; ils ne sont pas considérés
comme une preuve de conformité à une contrainte dure. Réponse vide et panne distinctes,
upsert idempotent, mise à jour du prix et conservation du cache en panne vérifiés.

Recherche exhaustive des anciens noms de fichiers/seed et collecteurs dans backend,
frontend, scripts, mocks et README : aucun import/appel résiduel. Les mentions dans
les rapports historiques décrivent les étapes antérieures ; ce bloc les remplace.


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
## Synchronisation Discovery — 26 septembre 2026

- `PYTHONDONTWRITEBYTECODE=1 /private/tmp/chandelle-ai-inspect/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests backend/streams/C_discovery/tests` : **149 passed, 5 subtests passed**, code 0 ; tests hors ligne, aucun appel OpenAI. Exécution dans le dépôt local après fusion des branches.
- Vérification locale du contrat Activity, des quatre fiches (`match_score` et `why` à null), de `.env.example`, et absence de `.env` ou `backend/api` dans le diff préparé : PASS.


## Cache Discovery affiché — 26 septembre 2026

- `PYTHONDONTWRITEBYTECODE=1 /private/tmp/chandelle-ai-inspect/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests backend/streams/C_discovery/tests` : **150 passed, 5 subtests passed**, code 0, exécution hors ligne dans la copie de travail.
- Le test API ajouté vérifie quatre Activity réelles, leurs liens sources, leurs champs `match_score`/`why` nuls et leur absence des programmes calculés.
- Vérification JavaScript par Node indisponible dans cet environnement (`node: command not found`) ; syntaxe/frontend à valider ultérieurement sur une machine avec Node.

## Validation de la pull request #3

Les résultats ci-dessus sont historiques et ne valident pas la présente
fusion. Après résolution des conflits, relancer les tests Python des
deux branches, les tests JavaScript et le parcours Discover combiné.
Ne pas additionner les nombres de tests annoncés.


## Test OpenAI réel autorisé, 26 septembre 2026

Chargement du .env racine avec python-dotenv, puis exécution de scripts/live_openai_smoke.py avec RUN_LIVE_OPENAI_SMOKE=1 : Live Responses structured-output smoke passed. Un appel, gpt-4.1-mini, 154 tokens (140 entrée / 14 sortie), enregistré success. Après redémarrage local : /api/v2/integrations confirme activation et clé chargée ; .env toujours ignoré par Git. Aucun test web_search ni fournisseur Reels dans cette opération.


## Ask OpenAI, 26 septembre 2026

217 tests Python + 5 sous-tests passent en 70,28 s, réseau interdit via scripts/test_offline.py et dossier temporaire autorisé. Tests ajoutés : critères transmis, cache distinct par budget, rejet des contraintes invalides. Quatre suites Node passent après adaptation du double DOM du formulaire ; tests Ask : consentement, budget zéro, critères, erreurs visibles et protection au changement de profil. verify_frontend_api.py PASS.

Nouveau scripts/test_ask_browser.cjs : Edge 375x812, API/SQLite locale isolée et réponse fournisseur simulée, consentement avant tout appel, résultat sourcé visible, limites de budget, ancien message d'erreur retiré, zéro débordement horizontal, retour au programme local PASS. Capture .runtime/ask-web-mobile.png. Le test réel séparé WebDiscovery, autorisé explicitement avec RUN_LIVE_OPENAI_SMOKE=1, a renvoyé completed et une source ; un seul appel web, enregistré dans le quota de la base principale. Le cache de ce profil de validation synthétique a été retiré, le compteur conservé. Aucun appel fournisseur dans la suite automatisée.


## Agendas et proactivité : vérifications du 26 septembre 2026

Commande finale : `.\.venv\Scripts\python.exe scripts/test_offline.py --tb=short --basetemp C:\Users\maxim\Documents\Codex\calendar-full-03 --junitxml=.runtime/calendar-tests.xml`.
Résultat exécuté : **236 passed, 5 subtests passed in 97.84s**. Log `.runtime/calendar-tests.txt`, XML `.runtime/calendar-tests.xml`. Aucun accès réseau fournisseur autorisé par ce lanceur.

19 tests calendrier dédiés couvrent chiffrement/absence de secrets dans les réponses, identité par membre, configuration absente, state/PKCE/cookie/rejeu/expiration, échange OAuth Google et MSAL simulé, refresh MSAL simulé, journaux callback, freebusy Google, pagination Outlook/free/annulé et URI refusée, croisements, cache périmé/panne sans disponibilité inventée, deux confirmations par révision, reprises après échec partiel, mise à jour/annulation, effacement, humeurs privées/anciennes, score, consentement OpenAI/cache de limitation, déclaration conversationnelle, délai depuis la date effective, scheduler start/stop et notifications/lecture isolée/doublons. Le test d'architecture des imports a détecté un cycle, corrigé en extrayant les utilitaires communs ; sa version finale passe. Un double arrêt de scheduler découvert en test a été rendu idempotent.

Suites Node exécutées : `test_ai.mjs`, `test_ui.mjs`, `test_experiences.mjs`, `test_share.mjs`, `test_calendar.mjs` : PASS. Syntaxe app.mjs et calendar.mjs : PASS. `python scripts/verify_frontend_api.py` : PASS. `python -m pip check` : aucune dépendance incohérente. `git diff --check` : PASS (avertissements LF/CRLF uniquement).

Navigateur : `node scripts/test_calendar_browser.cjs`, serveur isolé 8316 via `backend.tests.serve_share_fixture`, base `.runtime/calendar-browser-test.sqlite3`, OpenAI et scheduler désactivés pour ce test. Edge/Playwright, 375×812 : configuration OAuth absente visible, accords des deux profils, disponibilités manuelles, déclenchement de démo, notification persistée, ouverture du programme, garder/remplacer, acceptation et aperçu calendrier. PASS, aucun appel externe ; captures `.runtime/calendar-settings-mobile.png` et `.runtime/calendar-mobile.png` inspectées. Serveur de test arrêté après contrôle.

Validation réelle limitée au serveur local 8000 redémarré : `/api/v2/integrations` annonce `calendar.mode=manual_or_connected`, `providers.google=false`, `providers.outlook=false`, `scheduler_running=true`. La planification interne est active après activation dans le `.env` privé ; la cadence accélérée et l'analyse OpenAI d'humeur restent désactivées. Pas encore de passage quotidien observé (prochain passage à 09:00), mais cycle start/stop et calcul manuel validés. Pas de compte OAuth réel ni d'événement externe créé, modifié ou supprimé ; ces validations attendent les clients OAuth et comptes de test. CalDAV Apple absent.


## Deck E : vérifications terminées le 27 septembre 2026

Commande finale : `.\.venv\Scripts\python.exe scripts/test_offline.py --tb=short --basetemp C:\Users\maxim\Documents\Codex\deck-full-02 --junitxml=.runtime/deck-tests.xml` (sortie aussi enregistrée dans `.runtime/deck-tests.txt`). Résultat exécuté : **247 passed, 5 subtests passed in 112.00s**. Le lanceur impose le scoring local et interdit le réseau fournisseur. Avant les derniers garde-fous, une première régression avait passé 243 tests et 5 sous-tests ; seul le dernier résultat décrit la livraison.

Onze tests dédiés couvrent les six poids, NaN refusé, taille exacte, contraintes de temps/budget/trajet, diversité et absence de doublons, authentification, couple étranger, consentement cloud, trois plans persistés, absence de contexte privé dans la réponse, remplacement/activité verrouillée, conservation des autres étapes/cartes, composition croisée et ordre recalculé, pool d'un autre profil refusé, IDs inconnus/dupliqués, changement de tarif/refus, expiration du pool d'origine, ordre « dîner puis balade », cuisine japonaise et pénurie explicite. Méthode Pipelex : structure TOML et adaptateur testé avec doubles (réussite, indisponibilité, sortie non conforme). Aucun runtime Pipelex réel exécuté.

TypeScript : compilation stricte `node frontend/node_modules/typescript/bin/tsc -p frontend/tsconfig.json` et contrôle `--noEmit` PASS. `python scripts/generate_date_contract.py --check` PASS. Les six suites Node `test_ai`, `test_ui`, `test_experiences`, `test_share`, `test_calendar`, `test_date_deck` passent ; `test_ui` et `test_date_deck` relancées après le branchement de l'actualisation depuis le dialogue historique. `node --check frontend/app/app.mjs`, `python scripts/verify_frontend_api.py` et `python -m pip check` PASS.

Navigateur Edge/Playwright, viewport 375×812, serveur isolé 8320, base `.runtime/deck-browser.sqlite3`, appels externes bloqués :
- `scripts/test_date_deck_browser.cjs` PASS : vraies routes locales search/replace/compose/accept, trois cartes, flèches clavier, événements de swipe, intérêt sans acceptation, remplacement en restant sur la même carte, sélection croisée, confirmation dans le dialogue existant, montage séparé du composant avec mocks, aucun débordement horizontal ni erreur JavaScript.
- `scripts/test_ask_browser.cjs` PASS : consentement, critères, résultats web et sources avec fournisseur simulé, retour au deck local.
- `scripts/test_calendar_browser.cjs` PASS : configuration absente, deux consentements, déclenchement manuel, notification persistante, ouvrir/garder/remplacer/accepter et panneau calendrier existants.

Captures `.runtime/deck-mobile.png` et `.runtime/deck-mock-compare-mobile.png` inspectées. Une heure coupée sur deux lignes a été corrigée. Le geste est testé par événements de pointeur dans le navigateur, pas sur téléphone Android physique. Toutes les activités de ces tests sont synthétiques, pas des offres réelles.

Serveur utilisateur 8000 redémarré via le lanceur existant, après identification de son processus. Lecture de son OpenAPI : les trois nouvelles routes sont présentes. `/api/v2/integrations` annonce toujours `OpenAI_available=true` et `scheduler_running=true`. Aucun nouvel appel payant ni écriture calendrier externe effectué dans cette tranche. Aucun commit, push ou déploiement.

## Cartes individuelles, nettoyage des choix de moteur (27 septembre 2026)

| Contrôle exécuté | Résultat observé |
| --- | --- |
| Suite offline complète, après corrections finales du catalogue | 254 passed, 5 subtests passed, 120.93 s ; .runtime/activity-tests.txt et XML |
| Sept suites Node : ai, ui, experiences, share, calendar, date_deck, activity_cards | PASS |
| tsc strict (build et noEmit), contrat Python/TS --check | PASS |
| verify_frontend_api.py et pip check | PASS |
| test_activity_cards_browser.cjs, Edge 375x812 et 1440x1000 | PASS, API/SQLite réelles de test, données synthétiques |
| Même navigateur : swipe pointeur, flèches, Entrée, garder/passer/retirer, deux vues | PASS ; garder/passer n'écrit pas de préférence |
| Composition en échec puis nouvelle tentative, remplacement, acceptation | PASS ; autres étapes conservées |
| Lot sans programme complet, composition de 4 activités, refus de profil étranger | PASS API |
| Réponse de composition après changement de profil | PASS, aucun résultat affiché au nouveau profil |
| Chevauchement / trajet / budget / durée | Avertissements locaux et refus serveur des programmes impossibles |
| test_ask_browser.cjs, fournisseur simulé | PASS, pas de case moteur ; critères et citations conservés |
| test_share_browser.cjs, worker/IndexedDB/FastAPI/FFmpeg | PASS ; autorisation fichier conservée, profils isolés |
| Audit visuel et recherche de mentions fournisseur dans les écrans testés | PASS ; rapport UI_AUDIT.md |
| git diff --check | PASS |

Captures locales : .runtime/activity-mobile.png, .runtime/activity-desktop.png.
Aucun test fournisseur payant ; aucune preuve de réservation, disponibilité réelle,
menu de partage Android natif ou mise en production. Les tests navigateur utilisent
.runtime/activity-ui-test.sqlite3, jamais la base de travail de l'équipe.
