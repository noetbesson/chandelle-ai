# État courant

STATUS: CONTINUOUS_MEMORY_COMPLETE
V2_DONE = PASS
MERGE_DONE = PASS
LAST_UPDATED: 2026-09-26

## Application

FastAPI + SQLite + SPA native. Lancer `bash scripts/run.sh`, puis ouvrir
http://127.0.0.1:8000. La V1 reste à `/v1/demo`. Documentation et démarrage :
[README racine](../../README.md).

## Organisation livrée

- Métier regroupé dans les huit streams A–H, chacun avec un `service.py` actuel.
- `B_memory/onboarding.py` pour l’identité et les entretiens ; E conserve
  `models.py` et `planner.py` comme contrat/moteur commun.
- Compatibilité V1 explicite dans `legacy.py` ; routes et assertions historiques conservées.
- Suppression de la couche parallèle `domain` ; `integrations` limité à OpenAI et aux URLs.
- Conversations et retours d’activité sortis de la logique des routes, vers H et C.
- Références/examples/rapports regroupés dans `archive/HISTORY.md`. Schéma SQL décrit
  dans `CONTRACTS.md`. Parcours démo et installation dans le README racine.
- Frontend : `app.mjs` et `experiences.mjs` ; tests hors des ressources publiques.
- Périmètre backend/frontend/docs/scripts/mocks : **138 → 87 fichiers**, hors caches.
  Backend : **87 → 49** ; docs/v2 : **16 → 6**. Les anciens dossiers documentaires
  d’équipe et contrats JSON shared sont conservés.

## Vérification de ce tour

`bash scripts/check.sh` → code 0 : **141 tests Python en 10.38s**, deux suites
JavaScript et parcours API réussis. 138 cas existants conservés ; 3 gardes
architecturales ajoutées (propriété des streams, direction des dépendances,
absence de cycle d’import local). Réseau interdit pour la suite Python.
Détails et commandes intermédiaires dans `TEST_MATRIX.md`.

## Fonctionnalités et limites

Mémoire avec consentement, deux entretiens, 76 exemples de catalogue, imports
locaux confirmés, disponibilités communes, programmes/avis, proactivité,
préparation humaine et export ICS. OpenAI configurable et opt-in.
Aucun fournisseur live appelé ; Gradium/Dust/Pipelex/Jinko non raccordés.
Catalogue fictif, identité locale, aucune réservation ni paiement effectué.
Pas de validation visuelle dans un navigateur réel lors de cette réorganisation.

Aucun commit/push/déploiement ; changements antérieurs conservés. La réorganisation
modifie les imports Python internes, pas les routes produit ni le schéma SQL.

## Dernière simplification : tests et noms

13 fichiers de tests Python regroupés en 8, tous dans `backend/tests/`. Les 100
fonctions de test et leurs assertions ont été comparées par AST avant/après et
sont identiques (141 cas avec paramétrisation). Aucun scénario supprimé.
Code courant sans suffixe de livraison : frontend/app, api/routes.py,
backend/requirements.txt et scripts/run.sh. Routes et noms SQL versionnés conservés.
`bash scripts/check.sh` passe après ces changements.

## Mémoire continue — livraison du 2026-09-26

Choix utilisateur confirmés : deux espaces privés + un espace commun dans une
même base, historique complet conservé, préférences simples partagées
automatiquement, goûts durables séparés des envies ponctuelles.

- Questionnaire existant conservé ; B consolide maintenant les assertions entre
  échanges, renforce les répétitions et conserve les versions corrigées.
- Journal H privé persistant/paginé, reprenable via conversation_id. Recommandations
  enregistrées aussi ; signaux structurés existants conservés.
- Partage automatique limité à une allowlist exacte. Confidentialité explicite,
  restriction/révocation antérieure, isolation par propriétaire et consentements
  de recommandation préservés. L'avis de A ne corrige jamais celui de B.
- Envies séparées avec valid_to à 30 jours ; exclusion après expiration, journal
  toujours conservé. Suppression de faits, correction et effacement personnel
  restent distincts.
- Migration additive continuous_memory=1, reçus idempotents et transaction atomique
  couvrant messages/faits/événements/index/snapshots. Renvois concurrents testés.
- Interface : Memories → Mon journal personnel, messages échappés, choix de
  confidentialité, horizon et désactivation de l'apprentissage pour un message.

Validation finale : `bash scripts/check.sh` → code 0, **161 tests Python en 13.72s**,
suites Node (dont journal) et parcours API PASS. 141 cas préexistants conservés,
20 cas ajoutés. Tests Python sans réseau. Diff des chemins protégés vide.

Limites : extraction locale volontairement limitée aux préférences explicites
françaises/anglaises, sans compréhension générale du langage. Le journal n'est
pas une conversation générative avec réponses d'assistant. Adaptateur OpenAI
existant opt-in ; aucun appel live effectué. Mem0 non installé, frontière optionnelle
conservée. Identité locale existante, pas authentification de production.
Aucun test visuel dans un navigateur réel, commit, push ou déploiement.
