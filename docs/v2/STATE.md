# État courant

STATUS: STREAM_REORGANIZATION_COMPLETE
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

## Intégration mémoire vidéo, 26 septembre 2026

L'autorisation utilisateur vise explicitement ce dépôt. Les fichiers TypeScript
copiés dans `B_memory/video-memory/` ne correspondent pas à la stack Python ; ils
ont été conservés sans modification. Le pipeline Python est raccordé au FastAPI
existant, à son authentification et à la mémoire B. Aucun deuxième backend ni
stockage de préférences supplémentaire.

Entrée visible : écran Inspirations, formulaire vidéo. Sortie : inspiration privée
à confirmer dans le parcours D existant. Correction, consentement, ancienneté,
classement et effacement réutilisent B/C. Le flux local fonctionne avec une légende
et FFmpeg ; l'audio silencieux ou sans transcription n'est pas inventé.
Gradium, Pipelex et OpenAI disposent d'adaptateurs et de tests de réponses simulées.
Aucun appel réel de ces fournisseurs n'a été effectué lors de cette intégration.

Reprise : suivre le README, configurer des clés uniquement côté serveur si un test
externe est souhaité, recueillir le consentement cloud, puis vérifier une vraie
transcription. La planification de jobs distribués et l'authentification publique
restent hors du périmètre de cette application locale. Aucun commit, push ou
publication effectué.
