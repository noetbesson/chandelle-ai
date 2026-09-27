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

## Discover vocal Gradium — 2026-09-26

Bouton Discover → Discuter avec Chandelle, dialogue guidé français par tours,
transcription corrigible, synthèse et recommandation réelle via E/A/B/C.
Adaptateur REST Gradium opt-in, clé uniquement serveur, mode texte disponible.
Échange vocal temporaire sans apprentissage automatique ; plans persistés.
Changements antérieurs de mémoire continue conservés. Configuration et limites
dans [GRADIUM.md](GRADIUM.md). Lancer `bash scripts/run_voice.sh`.

Validation : 171 tests Python et suites JS/API réussis ; fournisseur simulé.
Aucun appel Gradium live, test micro réel, commit, push ou déploiement effectué par cette intervention.
Cette section remplace uniquement la mention antérieure « Gradium non raccordé ».

## Interface vocale compacte

Discover affiche désormais un cercle coloré animé, sans historique ni transcription
visibles. Bleu = lecture réelle, vert = parole utilisateur, violet = traitement.
Prise terminée au clic ou après 45 s, transcription envoyée automatiquement.
Clavier en volet fermé, interruption au clic, fermeture explicite, réduction
des animations respectée. API Gradium et moteur de recommandation inchangés.

Validation du cercle : `bash scripts/check.sh` → **171 passed in 16.40s**,
suites JS et parcours API PASS. Aucun test visuel/micro réel effectué.

## Google Calendar par lien iCal

Nos disponibilités accepte maintenant l’adresse iCal Google de chaque personne.
Le stream A calcule plages choisies moins événements, puis l’intersection du
couple. Import ponctuel 1–31 jours, heures quotidiennes réglables, 30 minutes
minimum. URL et événements non persistés ; date/période d’import propres au membre.
Pas d’OAuth ni de synchronisation automatique. Les événements récurrents,
exceptions, journées entières et fuseaux sont couverts. Échec = anciens créneaux
conservés. Métadonnées effacées avec les données personnelles.
Guide : [GOOGLE_CALENDAR.md](GOOGLE_CALENDAR.md). Bibliothèques iCalendar installées
dans ce workspace ; aucun agenda personnel ni appel Google réel utilisé.

Validation Google Calendar : `bash scripts/check.sh` → **193 passed in 18.74s**,
suites JS et parcours API PASS. Aucun test sur agenda personnel ou navigateur réel.
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
## Transfert de discovery — 26 septembre 2026

La branche locale `feature/discovery` ajoute au nouveau dépôt la collecte
Responses/web_search depuis l'ancien dépôt, le contrat Activity officiel, le
cache local de cinq activités réelles vérifiées, la réponse brute du premier
test et huit tests hors ligne. La clé `.env` n'a pas été copiée.
Les modules `C_discovery/service.py`, `legacy.py` et `__init__.py` existants
sont conservés. Le catalogue V2 de la démo n'est pas encore alimenté par ce
nouveau cache ; le transfert porte les fichiers de découverte sans modifier
le comportement de l'API existante. Voir DECISIONS et TEST_MATRIX pour les
contrats et validations de ce transfert.

## Discovery — synchronisation du 26 septembre 2026

La branche locale `feature/discovery` intègre le contrat Activity, `.env.example` et le code de collecte OpenAI. Le cache local contient quatre activités vérifiées issues du second test limité à cinq résultats. La recherche live reste désactivée dans `.env` ; le catalogue V2 n’utilise pas encore ce cache et continue de proposer des exemples fictifs.


## Discovery visible dans le frontend

La page Discover lit maintenant `/api/v2/activities/real` et affiche les quatre fiches du cache local, avec lien vers leur page source et mention de vérification des horaires. Le catalogue fictif reste disponible pour composer les programmes. Les fiches réelles ne sont pas encore planifiables faute de prix, durée et coordonnées vérifiés ; L’affichage du cache ne déclenche aucun appel OpenAI. Le formulaire de recherche web distinct peut en déclencher un après activation serveur et consentement.

## Fusion des branches : validation en attente

Les résultats de tests ci-dessus concernent les branches avant fusion.
La version combinée doit encore être testée, notamment l’affichage du
cache réel et le formulaire de recherche web dans Discover.

Le quota de la recherche web interactive ne couvre pas automatiquement
la commande de collecte importée de feature/discovery.
