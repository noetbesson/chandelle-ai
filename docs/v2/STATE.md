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

## Réception PWA depuis le partage du téléphone

Le formulaire vidéo et le backend existants sont réutilisés. Nouveau : manifeste,
icônes PNG, service worker avec cache limité aux assets publics, page /installer
et réception /partager. Le POST natif /api/receive-share est intercepté sur
l'appareil ; aucun ajout anonyme en mémoire côté serveur. Réception fichier ou
lien seul, choix explicite du profil, consentement, traitement et reprise du suivi.
Les brouillons expirent après 24 h au prochain accès, avec un maximum de cinq.

Validation réelle dans Edge à 375 px : navigation POST interceptée par le worker,
IndexedDB réel, lien seul, fichier MP4 synthétique traité par FFmpeg et FastAPI,
facts privés au bon propriétaire, suppression, conflit de profil et quota/expiration.
Le menu natif Android n'est pas simulé comme un succès : il reste à vérifier sur
un téléphone avec la PWA installée en HTTPS. Aucune connexion API externe ni
publication effectuée. Les fichiers TypeScript inactifs ont été supprimés à la
demande utilisateur avant ce changement ; les mentions précédentes sont historiques.

Point de reprise : démarrer le projet, ouvrir /installer ; pour un téléphone,
utiliser un hébergement HTTPS autorisé séparément. Configurer Gradium et le backend
de normalisation côté serveur seulement si une transcription live est souhaitée.

Le serveur de test isolé sur 127.0.0.1:8314 a été arrêté après vérification.
Les 198 tests Python, trois suites Node et le parcours navigateur réel passent.

## OpenAI : première tranche Discover et discussions (26 septembre 2026)

Nouveaux formulaires dans les écrans Discover et Memories existants. POST /api/v2/discovery/web utilise Responses web_search à la demande, une recherche maximum, références cliquables et cache privé de six heures dans la SQLite existante. Le profil public du couple peut fournir des thèmes autorisés ; aucun nom, exclusion ou note privée envoyé pour cette personnalisation. La demande saisie est envoyée avec consentement explicite.

Les réponses restent des pistes sourcées : elles ne constituent pas un inventaire exhaustif des sorties franciliennes, des séances garanties ou des créneaux disponibles. Aucun connecteur de compte AlloCiné, Google Maps, Tripadvisor ou UGC n'est annoncé. Pas d'injection automatique de ces pistes dans v2_activities ni dans le moteur de composition : prix, horaires et localisation structurés restent à vérifier avant ce raccordement. Le catalogue du planificateur reste synthétique.

POST /conversations est désormais utilisable depuis Memories. Extraction OpenAI opt-in, alternative française locale limitée ; faits rattachés au profil authentifié, canoniques pour le classement existant, correction/suppression inchangées. Une exclusion retire réellement les activités concernées. Les envies temporaires décroissent puis expirent après 45 jours ; les refus restent durables. Les doublons de faits actifs sont réutilisés sans renforcement artificiel. Les messages bruts sont toujours enregistrés par l'implémentation existante. Ce formulaire n'est pas encore un dialogue multi-tour avec historique assistant et proposition d'actions.

Quota atomique et persistant pour les appels Discover/discussions/planification : réserves de 0,10 USD/web et 0,02 USD/texte, seuils par défaut 1 USD/jour UTC et 10 USD cumulés. Compteur local conservateur, PAS facture ni solde OpenAI ; aucune conversion EUR/USD implicite. Les essais échoués conservent leur réserve. Le reset démo ne remet pas le compteur à zéro. Fournisseurs vidéo indépendants non couverts, laissés désactivés dans l'exemple. Pas de relance automatique payante ; explications de plans locales par défaut.

Validation : 206 tests Python hors réseau ; quatre suites Node, vérification des routes frontend, parcours réel Edge 375 px réussis. Après les derniers ajustements de validation, 32 tests ciblés supplémentaires réussis. Aucun appel OpenAI réel ni crédit consommé par ces vérifications. Pas de commit, push ni publication.

Reprise : lire la section de lancement OpenAI dans CONTRACTS.md. Configurer la clé hors chat, activer les deux indicateurs côté serveur, lancer scripts/run_ai.ps1 puis effectuer une recherche ciblée avec son consentement. Vérifier un vrai résultat cité et le compteur avant d'élargir. Le serveur temporaire de test est arrêté en fin de vérification.
