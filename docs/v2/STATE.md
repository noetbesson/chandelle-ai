# État courant

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


## 27 septembre 2026 : Ask et Discover raccordés au web

Ce bloc remplace les anciens constats sur un catalogue fictif ou deux recherches séparées.
L'interface de cartes reste en place. Ask et Discover passent par `/api/v2/dates/search`,
avec analyse LLM obligatoire, recherche web, validation des URL citées, filtres traçables,
classement B et composition E. Aucun catalogue statique ni repli vers les anciennes données.
Le cache des faits publics et les recherches privées restent dans la SQLite existante.

Les cartes tolèrent les prix, horaires et coordonnées inconnus. Ces valeurs restent
inconnues et empêchent une composition qui nécessiterait de les inventer. Les heures
suggérées ne sont pas des disponibilités réservables. Une panne, une réponse web vide
et une élimination par filtre donnent des messages différents.

Validation : 255 tests Python hors ligne réussis ; sept suites JavaScript, compilation
TypeScript, contrat généré, parcours API et deux scénarios navigateur à 375 px et desktop
réussis. Les fournisseurs des régressions sont simulés. Deux appels réels distincts ont
été exécutés avec le quota de l'application ; voir TEST_MATRIX pour les résultats exacts.
Le dernier appel réel produit une carte restaurant sourcée, aucun programme complet.
Il ne démontre pas une couverture exhaustive ni une disponibilité réelle des lieux.

Point de reprise : améliorer la diversité et les champs factuels retournés par le web
(prix avec unité, horaires et coordonnées publiés). Le lot réel testé ne contient pas
la balade demandée. Ne pas remplir ce manque par des tarifs ou programmes inventés.
Serveur local relancé sur http://127.0.0.1:8000 ; health OK, configuration de recherche
active et assets corrigés vérifiés. Instance de tests isolée arrêtée après validation.
Les modifications sont locales ; aucun commit, push ni déploiement dans cette mission.


STATUS: STREAM_REORGANIZATION_COMPLETE

STATUS: CONTINUOUS_MEMORY_COMPLETE
V2_DONE = PASS
MERGE_DONE = PASS
LAST_UPDATED: 2026-09-27

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


## Activation OpenAI locale vérifiée, 26 septembre 2026

Sur demande utilisateur, le fichier privé backend/integrations/.env a été déplacé vers .env à la racine, sans affichage de son contenu. Le fichier reste ignoré par Git. Le serveur Chandelle identifié sur 127.0.0.1:8000 a été redémarré via scripts/run_ai.ps1, en arrière-plan. GET /api/v2/integrations confirme enabled/configured/available=true, mode=openai et web_enabled=true, modèle gpt-4.1-mini.

Un seul appel réel du smoke existant a réussi avec RUN_LIVE_OPENAI_SMOKE=1 et une demande synthétique sans données personnelles : 140 tokens en entrée, 14 en sortie, 154 au total. Résultat success conservé dans v2_ai_calls, réserve locale de 0,02 USD (pas une facture). La recherche web est activée mais n'a pas été testée en live pendant cette opération. Gradium/Pipelex et le pipeline vidéo ne sont pas validés par ce test. Aucun push ni déploiement. La révocation de la clé précédemment visible en capture reste à confirmer par le propriétaire du compte.


## Ask raccordé à la recherche web OpenAI, 26 septembre 2026

Ask utilisait par défaut le catalogue synthétique ; le mode OpenAI existant analysait la demande mais ne recherchait pas de lieux réels. Le mode web est désormais sélectionné par défaut lorsque disponible, avec consentement explicite avant envoi. Il utilise le même endpoint /discovery/web, les mêmes citations, le cache privé et le quota existants. Budget pour deux, date/heure, rayon indicatif et nombre d'activités sont transmis dans un objet plan validé. Les propositions sont affichées dans Ask avec les sources et les limites de vérification. Le catalogue local et garder/remplacer restent disponibles. Aucun enregistrement automatique en mémoire.

Un appel réel sur une demande synthétique restaurant japonais puis balade a renvoyé status=completed, mode=openai_web et une source. La réponse ne valide ni le prix total ni tout le trajet et contient une incohérence d'arrondissement : ce test prouve la connexion et les suggestions, pas leur exactitude complète. Aucun nouvel appel pour corriger ce contenu ; réserve locale 0,10 USD, facture non mesurée. Serveur local redémarré sur 8000, schéma WebPlan et indicateurs OpenAI vérifiés. Modifications locales non poussées.

## Agendas A et proactivité G, 26 septembre 2026

Ajout dans la stack existante : OAuth web Google/MSAL, tokens et plages occupées chiffrés, agenda principal, rafraîchissement explicite, croisement A sans fallback fictif dès qu'un compte est connecté. UI dans Disponibilités, confirmations dans le DatePlan et notifications dans le fil. Deux accords sur une empreinte du programme autorisent création/mise à jour/suppression ; résultats par membre et reprises idempotentes. La déconnexion conserve les événements distants et traite une reconnexion comme une nouvelle connexion, éventuellement un autre compte : les anciens événements ne sont pas adoptés automatiquement.

G utilise les dates effectives des programmes acceptés/terminés, les créneaux communs et les signaux récents autorisés. Accord séparé des deux personnes pour les propositions. Analyse locale d'humeur, OpenAI facultatif avec consentement individuel, quotas existants et une tentative par jour/personne. Un narrateur de Reel et un ancien import ne deviennent pas l'humeur de l'utilisateur. Notifications en base, déduplication et lecture individuelle. Le job APScheduler quotidien ou accéléré est implémenté ; pas de tâche Windows externe.

Validation : 236 tests Python + 5 sous-tests passés, cinq suites Node et contrôle frontend/API passés. Le navigateur à 375 px a exécuté créneaux manuels, accords des deux profils, déclenchement de démo, notification persistante, ouverture, garder/remplacer et acceptation. Les appels calendriers sont simulés dans les tests, pas de validation OAuth réelle. Dépendances installées, pip check sans incohérence. Import cyclique détecté puis corrigé ; arrêt du scheduler rendu idempotent.

Serveur local 127.0.0.1:8000 redémarré avec la version calendrier. État observé après activation locale : providers google=false/outlook=false, scheduler_running=true, OpenAI toujours available=true. Passage quotidien à 09:00 Europe/Paris tant que le serveur reste allumé ; il ne traite que les couples ayant donné les deux accords. Clé de chiffrement générée uniquement dans le .env ignoré ; aucune valeur secrète affichée. Aucun appel fournisseur calendrier ou nouvel appel OpenAI réel durant cette tranche. Modifications non committées et non poussées, ajouts Ask antérieurs conservés.

Point de reprise : suivre README « Agendas Google / Outlook », créer les clients OAuth et callbacks exacts, connecter deux comptes de test, vérifier lecture/création/modification/suppression puis observer le premier passage quotidien et sa notification. Le scheduler local est déjà activé, les consentements utilisateurs restent nécessaires. Le catalogue de programmes reste fictif, même lorsque la disponibilité vient d'un agenda réel. Pour écrire ces programmes dans des agendas de test : CHANDELLE_DEV=1 et CALENDAR_ALLOW_DEMO_EVENTS=1. Pas de conversion automatique des propositions web d'Ask. CalDAV Apple non implémenté ; export ICS disponible. Pas de synchronisation des déplacements distants vers le contenu du DatePlan, pas de web push et un seul worker serveur pris en charge.


## Deck de programmes composables, 26 septembre 2026

Extension de E existant, même FastAPI et SQLite : génération déterministe de combinaisons d'exactement 1, 2 ou 3 étapes, score à six composantes, diversité entre trois propositions, remplacement ciblé entre voisins et composition d'une sélection fixe. Les étapes inchangées gardent leur payload complet. Un pool privé au serveur est conservé par recherche/profil et expire après 24 h. Les modifications de la mémoire, des budgets, des disponibilités et du catalogue sont revérifiées avant une édition. Aucun doublon ajouté pour masquer un manque de résultats.

Ask propose maintenant le deck en priorité (analyse OpenAI de la demande si activée, sinon local), avec le mode web toujours disponible. Composant TypeScript strict compilé en module ES pour le front actuel, pas de React ni de nouvel écran principal. Swipe/intérêt, clavier, boutons, comparaison, sélection croisée, fenêtre de remplacement et ouverture du dialogue de confirmation existant. Les mutations de ce dialogue actualisent aussi les cartes. Le cache public du service worker a changé de version pour recevoir la feuille de style mise à jour.

Scoring local fonctionnel. Méthode Pipelex PipeFunc et adaptateur optionnel avec sortie contrôlée et fallback explicite, non validés avec le runtime réel absent. Sous-titres locaux par défaut ; explications OpenAI facultatives sous quota et consentement existants. Aucun appel fournisseur réel durant cette tranche. Les activités planifiables restent synthétiques : les sorties web non vérifiées ne sont pas converties en fausses offres.

Point de reprise : installer/valider le runtime Pipelex si ce partenaire doit être montré, puis fournir à C des horaires, prix et coordonnées réels vérifiés pour que le même compositeur travaille sur des offres réelles. Tester le geste sur le téléphone Android de démonstration. Les tests Playwright sont exécutés à 375 px, pas sur un appareil physique. Aucun push, commit ou déploiement ; changements Ask/agendas/proactivité précédents conservés.

Validation finale, 27 septembre 2026 : 247 tests Python et 5 sous-tests passent, TypeScript strict et contrat généré vérifiés, six suites Node et trois parcours navigateur à 375 px passent. Le serveur utilisateur 8000 sert les nouvelles routes ; OpenAI reste disponible et le scheduler précédent reste actif. Serveur de test isolé 8320 arrêté après vérification. Les preuves et commandes sont dans TEST_MATRIX.md.

## Cartes individuelles et interface sans choix de moteur, 27 septembre 2026

Livré dans le code courant : ActivityCard, ActivitySwipeDeck, MyDateBuilder en
TypeScript strict compilé ; neuf exemples isolés, gestes et clavier, vues Découverte
et Vue d'ensemble, avertissements de cohérence, construction du programme par E.
Les sélections peuvent dépasser trois activités. Les profils, le lot enregistré et
les contraintes sont revérifiés côté serveur. Pas de nouvelle base ni backend.

Les libellés/confirmations de moteur ont été retirés d'Ask, Discover, mémoire,
inspirations, partage, paramètres, disponibilité et historique. Le mode auto/standard
suit la configuration serveur. Pas de modification des quotas ni d'activation
rétroactive des consentements enregistrés. Rapport : UI_AUDIT.md ; guide : README.

Validation finale : 254 tests Python + 5 sous-tests passent (120,93 s), sept suites
Node passent, contrat généré vérifié, compilation TypeScript stricte, vérification
frontend/API et pip check passent. Navigateur Edge 375 px / desktop : vraie API locale
avec catalogue synthétique, composition/remplacement/confirmation, gestes, erreurs
et nouvelle tentative, identité, absence de commandes de moteur. Tests Ask web avec
fournisseur simulé et partage PWA/FFmpeg passent également. Aucun appel payant exécuté.

Point de reprise : l'application sur 8000 doit être rechargée pour ses nouveaux modules.
Code non commité et non poussé ; modifications antérieures conservées. Les cartes
composables restent issues de la démo ; données web insuffisamment vérifiées séparées.
Les photos sont facultatives ; illustrations locales quand absentes. Partage Android
natif réel et intégrations fournisseurs live non validés par ces tests. Aucune politique
de confidentialité complète ajoutée : information juridique à terminer avant publication.

Serveur local redémarré après validation : le 27 septembre, HTTP 200 sur /api/v2/health,
le schéma /openapi.json expose ActivityChoice et le mode auto. Vérification en lecture
seule, sans appel externe. L'onglet local a été actualisé. Aucun commit ni push effectué.

## Chandelier vocal — 2026-09-27

Le cercle de Discover est remplacé par un chandelier SVG à trois bougies,
inspiré du dessin fourni. Flammes dorées pendant la lecture, orangées pendant
l’enregistrement ; taille pilotée par le volume RMS local, lissé et borné.
Web Audio analyse le micro sans retour aux haut-parleurs et la synthèse réellement
lue. Fermeture : annulation des animations, déconnexion et fermeture du contexte.
Réduction des mouvements respectée. API et dialogue par tours inchangés.

Validation : `bash scripts/check.sh` → **193 passed in 18.87s**, suites Node
et parcours API PASS. Aucun essai visuel/micro dans un navigateur réel ni appel
Gradium live. Modifications locales, non publiées.

Correction de chargement : la capture utilisateur montrait encore le cercle malgré
le code neuf servi sur localhost. URLs CSS, app et module vocal versionnées
`chandelier-1` pour contourner un ancien cache. Vérification HTTP locale des quatre
ressources réussie ; affichage navigateur utilisateur restant à confirmer.

## Publication chandelier avec la branche partagée — 2026-09-27

Le premier push a été refusé : noe/memory distant avait intégré main. Reprise du
commit chandelier sur cette base, conservation des ajouts Discovery réel, AI et
PWA/Reels. Résolution des conflits de documentation, imports, HTML et CSS.
La base distante contenait des restes de fusion empêchant le démarrage : fonctions
JS dupliquées, branches calendar/reel imbriquées et ancien bloc Python après le
retour de conversation. Raccordements corrigés en conservant journal, durée des
souvenirs, calendrier, Reels et point d’entrée vocal dans Discovery réel.
Dépendances déclarées de l’équipe installées dans le venv local.

Validation finale intégrée : `bash scripts/check.sh` code 0 ; **255 passed,
12 skipped, 5 subtests passed in 21.18s**, suites Node et parcours API PASS.
## Fusion locale avec les apports de Noé, 27 septembre 2026

La demande utilisateur autorise la résolution de la fusion déjà engagée sur main
entre 8906c0d (travail local) et 0208e08 (main distant, PR 5). Dix fichiers étaient
en conflit. Les deux apports sont conservés : cartes/recherche web, OAuth et
proactivité d'une part ; chandelier Gradium, journal mémoire et import iCal d'autre
part. Les versions avant résolution et les patches sont sauvegardés dans le
workspace Codex, sous `.runtime/merge-noe-20260927`.

Le dialogue vocal rejoint PlanningService.query avec identité propriétaire,
mode auto et pool composable. Les cartes restent visibles si aucun programme
complet ne peut être construit. Aucun retour au catalogue fictif. Les détails
manquants et l'absence de créneau commun sont expliqués. Un seul gestionnaire JS
par action ; fin de la voix et destruction du deck à la navigation/changement de
profil. Le journal de Noé conserve l'historique privé et ses reprises idempotentes ;
le signal d'humeur explicite de G est préservé avec sa visibilité.

Validation : 313 tests Python passent, huit suites Node, TypeScript strict,
contrat DatePlan, vérification frontend/API et pip check passent. Parcours Edge
375 px exécuté : chandelier, dialogue clavier, cartes issues du fournisseur
simulé, garder, fermeture, recherche formulaire, journal et agendas. Aucun appel
payant ou fournisseur réel. Serveur de test 8332 arrêté.

Configuration Gradium locale : désactivée, clé et voix absentes du `.env` à la
racine (valeurs jamais affichées). Le lanceur Windows charge maintenant GRADIUM_*.
Point de reprise : guide GRADIUM.md pour configurer un compte de test, redémarrer
le serveur utilisateur, puis tester réellement micro/transcription/synthèse.
La fusion est locale ; aucun push ni déploiement effectué pendant cette opération.


## Chargement frais de l’interface — 2026-09-27

Après signalement persistant de l’ancien cercle, lecture HTTP du serveur local :
HTML/module/CSS du chandelier présents mais sans Cache-Control ; le worker PWA
conservait la CSS en cache-first. Ajout no-store sur pages et ressources UI ;
les validateurs conditionnels sont ignorés sur ces routes pour toujours renvoyer
les octets actuels. Worker public-v2 : icônes seules en cache, suppression de
l’ancien cache, activation immédiate ; updateViaCache=none à l’enregistrement.
Les profils et brouillons IndexedDB ne sont pas effacés. Un redémarrage normal
du serveur et une ouverture/recharge normale suffisent pour appliquer la nouvelle
politique ; aucun lien versionné à saisir ni nettoyage manuel du cache requis.
Validation : 263 tests Python réussis, 12 ignorés, 5 sous-tests réussis ; suites
Node/API PASS. Test dédié au cycle du worker PASS. Pas de navigateur réel testé.
## Rejet du push et correction de cache intégrée, 27 septembre 2026

Le push utilisateur de main a été refusé car origin/main avait reçu la PR 6
(1505aa3, correction de cache 117cb8b) depuis notre fusion b9f9975. Récupération
puis fusion des deux historiques, sans reset ni force-push. Les conflits de
documentation conservent les deux suivis. FastAPI garde le flux web existant et
reçoit le middleware no-store de Noé ; le worker v4 ne conserve que les icônes
et retire les anciens caches v1/v2/v3. Aucun changement des données personnelles.

Validation de ce delta : 35 tests Python ciblés, neuf suites Node et parcours
Edge mobile passent ; fournisseur simulé uniquement. Les 313 tests de la fusion
précédente restent sa référence complète, sans prétendre à une nouvelle exécution
intégrale pour ce delta de cache. Le lancement Windows doit être redémarré pour
charger la nouvelle politique HTTP. Configuration Gradium inchangée.
## Gradium chargé et vérifié en réel, 27 septembre 2026

Après ajout des accès par l'utilisateur, le `.env` racine était renseigné mais
le serveur 8000 tournait encore avec l'ancienne application, sans état Gradium ni
routes vocales. Seul ce processus Chandelle, identifié avec son parent dans le
venv du projet, a été relancé via scripts/run_ai.ps1. État HTTP après relance :
Gradium enabled/configured/available=true, routes transcribe/speak présentes.

Essai réel autorisé par le dépannage : synthèse d'une phrase fictive puis
transcription de l'audio généré, réussies. WAV réel de 2,56 s, mono 48 kHz,
transcription non vide avec Paris reconnu. Aucun audio ni texte utilisateur
envoyé. Deux appels TTS et un STT au total : le premier WAV avait un en-tête de
streaming à longueur inconnue, finalisé pour le second essai avant le contrôle
strict STT. Aucune modification du connecteur nécessaire. Preuve sans secrets :
`.runtime/gradium-live-smoke.json`. Facturation fournisseur non mesurée.

Reprise : recharger l'onglet local puis tester le microphone du navigateur. Ce
contrôle serveur prouve STT/TTS, pas l'autorisation micro ni la lecture sur chaque
téléphone. Aucun changement de code ou de secret, aucun nouveau push.

## Sources Excel nettoyées et intégrées, 27 septembre 2026

Les sept exports fournis ont été lus sans modifier les originaux. 8 633 lignes
de données donnent 8 471 fiches uniques après 162 doublons fusionnés :
7 760 lieux Tripadvisor, 105 films AlloCiné, 606 articles Sortiraparis.
267 lignes sans fiche utile (dont trois boutons « Keep on planning ») sont
écartées ; quatre contradictions de prix/note/compteur restent inconnues.
Archive normalisée : 482 676 octets contre 1 720 657 octets d'Excel (71,9 %
de réduction du livrable). Les JSON décompressés font 5,21 Mo ; SQLite avec
payloads et index prend environ 14,55 Mo sur la base de vérification vide.
Ces chiffres ne comparent donc pas la taille de SQLite à celle des Excel.

Le lancement normal charge le bundle par empreinte dans v2_activities ;
FTS5 et registre d'import sont dans la même SQLite. Aucune deuxième base
de production ni catalogue fictif. Au 27 septembre, 7 971 pistes éligibles ;
500 références ou fiches expirées/annulées/non localisées restent stockées
sans devenir des cartes de sorties. Les séances datées AlloCiné restent
à rechercher : une date de sortie nationale n'est pas une séance francilienne.

Ask, Discover et le dialogue réutilisent PlanningService. Recherche locale
indexée, mêmes refus/budgets/contrôles B, puis recherche web si manque de choix
ou besoin d'informations datées, guidée par huit références publiques maximum.
Les pannes web ne masquent pas les fiches utilisables. Les gammes ne deviennent
pas des euros et l'import ne vaut pas vérification. Les cartes restent gardables ;
la composition demande toujours les informations de planification requises.

Validation réelle : bundle chargé dans .runtime/chandelle_v2.sqlite3, relance
8000, GET integrations annonce imported_and_web avec 8 471/7 971 fiches.
La répétition de l'import retourne unchanged=true. Les 42 faits personnels
sont conservés. Contrôle de trois couples existants, sans mutation : pour
« restaurant japonais », deux profils conservent 80 pistes, le troisième
en exclut 80 via explicit_exclusions. Aucun refus existant n'a été effacé.

Parcours Edge mobile 375 px avec les vrais imports dans une base de test :
Discover/Ask, 50 cartes, garder, vue d'ensemble, sélection préservée, zéro appel
fournisseur. Voir TEST_MATRIX pour régressions et limites. Le serveur utilisateur
est relancé ; aucun push, commit ni déploiement effectué. Reprise : réimporter
les nouveaux exports via scripts/import_activity_workbooks.py ; compléter les
adresses, tarifs et séances par vérifications ciblées, sans supposer leurs valeurs.

## Ajout des bars, 27 septembre 2026

Bar.xlsx traité : 160 lignes, 160 identifiants uniques MisterGoodBeer, 159 adresses
à Paris et une en Seine-Saint-Denis. 160 tarifs explicitement par pinte, 111 textes
de conditions, aucune date de vérification connue. Aucun original modifié.
Le bundle commun passe de 482 676 à 495 119 octets (+12 443), pour 8 631 fiches.
L’import dans la SQLite existante ajoute 160 lignes, met à jour 0 ancienne fiche
et conserve les 8 471 précédentes. Relance idempotente unchanged=true, 160 lignes
FTS pour 160 bars. Catalogue total : 8 131 pistes éligibles au 27 septembre.

Les cartes Ask/Discover montrent source, adresse, tarif par pinte et conditions
à confirmer. Le budget par personne reste inconnu, aucune réservation disponible
n’est supposée. Recherche terrasse corrigée pour exclure « Pas de terrasse ».
Serveur local 8000 relancé via run_ai.ps1. Régressions ciblées 32 passed, TypeScript
strict et tests cartes PASS. Parcours réel du bundle dans Edge 375 px, sans appel
externe, validé sur Discover/Ask et garder/vue d’ensemble. Détails TEST_MATRIX.
Pas de commit ni push. Reprise : actualiser les exports ou vérifier les horaires,
coordonnées et budget complet avant de rendre ces pistes composables.
