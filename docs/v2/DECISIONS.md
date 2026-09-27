# Decisions

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


## 27 septembre 2026 : suppression du catalogue d'activités fictives

- Un seul parcours E/C alimente Ask, Discover et les suggestions. Le client CLI de C
  appelle cette API authentifiée au lieu d'entretenir son propre collecteur/fichier.
- Les fichiers d'activités statiques V1, E, peer et le cache JSON parallèle ont été
  supprimés, ainsi que les modules mock servis au navigateur. Les tests injectent des
  réponses fournisseur générées à la demande, hors imports de l'application.
- Le manque de prix/dates/coordonnées ne supprime pas une piste de découverte ; il
  empêche sa composition lorsque ces informations sont nécessaires. La disponibilité
  inconnue est affichée comme telle ; une indisponibilité explicite élimine la fiche.
- Normaliser « Paris » et les noms des départements franciliens avant le filtre IDF.
  La comparaison brute avec les seuls codes numériques éliminait les neuf fiches du
  premier appel live. Chaque filtre enregistre désormais ses pertes exactes.
- Les demandes de visite de lieux permanents peuvent recevoir un horaire proposé,
  étiqueté comme tel. Les séances/événements exigent leurs horaires publiés.
- Aucun catalogue de secours si l'analyse, la recherche ou le quota échoue. Les
  réponses sont explicites et les limites fournisseur restent visibles dans les faits.


1. Add V2 beside V1; retain all V1 models and routes. Do not modify shared/A/D/F contracts.
2. SQLite SQL facts and append-only events are authoritative. JSON payloads are acceptable for typed bounded subdocuments, not permission checks. Schema migrations are root-owned.
3. Local identity uses member capability tokens (hashed at rest), delivered only on couple creation and explicit local handoff. This is local device privacy, not production authentication. Member headers are required on personal data; a member ID alone never authorizes access. Shared device handoff clears rendered answers. No global listing of tokens.
4. Consent PRIVATE excludes planning; COUPLE_RECOMMENDATION allows internal structured preference influence but not verbatim disclosure; SHARED permits display. Never derive free-text content into shared snapshots. Recompute derived profile on every mutation/revoke.
5. V2 uses independent modules under existing streams; old SQLite couple_profiles remains untouched. Root owns backend/db schema and integrations/domain/API.
6. Frontend Next starter has no installed runtime; implement no-build ES-module SPA under frontend/v2, served by FastAPI at /app (and eventually root with V1 at /v1/demo). Preserve V1 /static resources.
7. No live network tests. Real OpenAI SDK adapter is opt-in and validates structured responses with deterministic fallbacks.
8. Responses SDK verified locally (openai 3.19.2, Responses.parse text_format present) and against official Structured Outputs documentation: https://developers.openai.com/api/docs/guides/structured-outputs . Adapter uses Pydantic parse, store=False, bounded timeout/retry; explanation payload contains public catalog facts and numeric scores only.
9. E receives a backward-compatible optional max_activities parameter (default retains V1 four-stop behavior). V2 explicitly passes 1–3. Persisted V2 UUIDs replace E's reused local plan IDs.
10. C fairness: .60 min(A,B)+.40 mean(A,B), individual .45 + min(.4,.2*interest matches) + .1 saved/liked; shared/query bonuses .05/.08; repeat penalty .2*novelty; distance penalty min(.15,.015*km); greedy category diversity penalty .035 per prior category. All hard exclusions happen first. Demo origin Paris center, conservative 4 km/h walking distance.
11. Onboarding identity field privacy does not alter the public welcome pseudonym; private pronouns/name stay in owner memory. Photo visibility defaults owner-only, including authenticated downloads.

## Fusion avec le projet ami — 26 septembre 2026

12. Garder un seul runtime FastAPI/SQLite et la SPA sans build. Les modules TypeScript sont des références adaptées, pas un deuxième backend caché. Aucun script ni fichier de consignes de l’archive n’est exécuté.
13. La compatibilité des tests existants inclut la trace `parse/memories/candidates/plan` et le registre `v2_schema=1`. L’extension additive est enregistrée séparément dans `v2_extensions(peer_merge,1)` ; aucune table V1 ni réponse historique n’est supprimée.
14. Disponibilités : chaque personne gère uniquement ses propres créneaux. Seule l’intersection est exposée à l’autre personne. Sans configuration : démo existante ; dès la première saisie : les deux personnes doivent fournir un créneau compatible. Fuseau Paris, instants UTC persistés, heures locales ambiguës/inexistantes refusées. La composition E ne traverse pas un changement d’heure ; elle le signale au lieu d’inventer des horaires.
15. Inspirations : import inerte, aucun téléchargement. Réutiliser les faits/événements/provenance B au lieu de créer une mémoire concurrente. Les goûts proposés ne participent pas au ranking avant confirmation. Conserver les trois niveaux de consentement du dépôt, même si le projet ami autorisait l’influence des préférences privées.
16. Déduplication par propriétaire/plateforme/URL canonique ou texte normalisé ; les paramètres de tracking ne créent pas de nouveau goût. Les envies temporaires confirmées décroissent par jour (`exp(-jours/30)`), expirent à 45 jours et restent consultables comme provenance. Date inconnue : poids 0.1, jamais remplacée par la date d’import. Maximum par goût, pas de cumul artificiel des doublons. Une correction conserve la source d’import et sa chaîne de supersession.
17. Catalogue ami : conserver les 36 exemples originaux dans `mocks/peer/catalogue.json`, IDs `peer_XX`, adapter catégories/tags et attribuer des créneaux explicitement fictifs. `CatalogService.seed()` garde ses 40 lignes de base ; la composition API ajoute les 36 lignes, soit 76. Prix inconnu/complet restent consultables mais exclus des programmes. Aucune disponibilité commerciale n’est affirmée.
18. Réservation : préparation seulement après acceptation ; aucun paiement, écriture auprès d’un fournisseur ou confirmation automatique. Les activités de démo ne reçoivent jamais de faux liens. Export ICS authentifié et privé, lignes UTF-8 repliées, contenu échappé, dates UTC, événements provisoires.
19. Les choix imposés (1–3) utilisent le validateur E existant ; la comparaison (1–5) ne promet pas leur faisabilité. Les suggestions en attente expirent lors d’une modification d’agenda. Les actions frontend utilisent les endpoints communs ; un import de fichier commencé sous A ne peut pas être envoyé sous B.

## Nettoyage architectural — 26 septembre 2026

20. Nettoyage du 2026-09-26 : supprimer le squelette Next.js inutilisé et son lockfile ; la SPA native est l’unique frontend actif. Cette décision remplace la conservation provisoire du starter mentionnée en décision 6. Conserver V1, noms/imports des streams, contrats et fixtures encore utilisés.
21. Ne servir que les assets applicatifs sous `frontend/v2` : tests JavaScript déplacés dans `frontend/tests`, parcours TestClient dans `scripts/verify_frontend_api.py`. Unifier la vérification avec `bash scripts/check.sh`.
22. README racine comme point d’entrée GitHub ; documentation courante indexée dans `docs/v2/README.md`, anciens rapports/passations/revues/prompt regroupés dans `docs/v2/archive`. Les preuves de test historiques conservent leurs commandes originales.

## Réorganisation MECE des streams — 26 septembre 2026

23. Cette section remplace les emplacements provisoires des décisions 5/6/13/20–22. Regrouper l’implémentation actuelle dans `streams/A..H/service.py` : A calendrier, B mémoire, C découverte, D imports, E cycle des programmes, F préparation, G suggestions, H texte/conversations. `domain/` disparaît. Les contrats E et le schéma SQL ne sont pas réécrits.
24. Conserver le comportement V1 dans des modules `legacy.py` explicites et les exports des packages B/C/G/H. Consolider les petits modèles/repositories/services historiques B/C ; déplacer l’API autonome E dans `api/legacy_orchestrator.py`. Les imports Python internes et les imports des tests sont migrés ; aucune nouvelle couche de shims. Compatibilité conservée au niveau HTTP, données et cas de test.
25. Les primitives UTC/JSON sont dans `db/__init__.py`, les types de consentement dans B ; la validation URL dans `integrations/urls.py`. Aucun stream ne dépend de l’API. H reçoit son adaptateur d’extraction par injection pour éviter un cycle avec le repli linguistique OpenAI. Ajouter des gardes d’architecture exécutées par pytest.
26. La demande utilisateur de revoir l’ensemble du projet autorise le rangement annoncé des streams A/D/F : leurs anciens README/exemples sont conservés dans l’historique consolidé et leurs implémentations V2 occupent désormais leurs dossiers. Les contrats shared et les archives d’équipe codex-E/night-shift restent intacts.
27. Un seul historique `docs/v2/archive/HISTORY.md`, avec contenu et chemins d’origine, remplace les multiples rapports/prompts/exemples inertes. Le README racine porte installation, carte des streams et démo ; les contrats incluent le stockage SQL. Supprimer les protocoles sans appelant, pas les tests ni les fixtures réellement utilisées.
28. Le feedback d’activité appartient à C ; l’avis sur un programme appartient à E et alimente B. L’API garde les contrôles HTTP et les opérations transverses compte/uploads/effacement ; on ne multiplie pas les fichiers pour simuler une pureté absolue des couches.

29. Suite à la demande de retirer les fichiers superflus : regrouper les 13 fichiers de tests Python en 8 fichiers par responsabilité dans backend/tests, sans suppression de fonction ni d’assertion. Les doublons visuels de fichiers V1/V2 ne sont pas assimilés à une couverture fonctionnelle redondante.
30. Retirer les versions des noms de fichiers applicatifs : frontend/app, api/routes.py, requirements.txt, scripts/run.sh/init_demo.py/reset_demo.sh/test_offline.py. Maintenir les chemins HTTP, identifiants SQL, confirmation de reset et mémoire documentaire docs/v2 pour éviter une migration inutile. Les commandes historiques consignées précédemment restent inchangées.

31. Mémoire continue (choix utilisateur, 2026-09-26) : une base SQLite avec deux
    espaces PERSON privés et une projection COUPLE ; pas trois fichiers ni une
    copie concurrente des faits. Le journal brut reste privé, même lorsque des
    goûts extraits sont partagés. Historique conservé jusqu'à effacement personnel.
32. Partage automatique autorisé uniquement pour une allowlist exacte de goûts
    simples. Un choix de confidentialité explicite prime. Ni modèle ni analyse
    libre ne peuvent déclarer une information sensible « partageable ».
33. Les assertions explicites consolident une clé stable par propriétaire, sujet
    et horizon ; répétition = renforcement, changement de polarité = supersession.
    Les corrections durables priment sur la sélection initiale du questionnaire
    dans les seules projections qui sont autorisées à les lire.
34. Envies ponctuelles séparées, expiration à 30 jours (choix de durée local,
    ajustable ultérieurement). Leur journal et provenance restent conservés.
    Les demandes de recommandations passent aussi par H ; extraction locale
    automatique, aucun appel fournisseur implicite. Les autres signaux structurés
    restent capturés par les services existants (questionnaire, avis, favoris).
35. `Database.atomic()` joint les écritures imbriquées d'une interaction dans une
    transaction SQLite BEGIN IMMEDIATE. Extraction fournisseur avant transaction.
    Reçu idempotent par utilisateur/clé, empreinte du payload, relecture de l'état
    courant lors du replay pour éviter de ressusciter un fait effacé ou supersédé.
    Aucun code Mem0 copié ; frontière MemoryBackend conservée pour un adaptateur
    optionnel futur. Inspiration : https://github.com/mem0ai/mem0 (consulté ce tour).

36. Discover vocal : Gradium REST pour transcription WAV et synthèse, httpx
    existant sans nouveau SDK ; activation explicite et clé exclusivement serveur.
37. Premier dialogue guidé par tours dans H, moteur E injecté pour la vraie
    recommandation. Pas de LLM supplémentaire, de second catalogue, de migration
    SQL ni de copie des souvenirs bruts vers le fournisseur. Texte possible en repli.
38. Échange vocal temporaire et consentement au micro au clic ; pas d'apprentissage
    implicite des transcriptions. Navigation/handoff ferme micro et audio ; les
    réponses asynchrones sont invalidées. Les changements de mémoire continue
    présents avant cette intervention restent intacts.

39. Interface vocale : remplacer le transcript par un cercle piloté par les
    événements audio playing/ended/error, pas par la seule réponse HTTP. Prises
    au clic, envoi automatique après transcription ; clavier en repli fermé.
    Arrêt et invalidation conservés lors d’une navigation ou d’un changement de profil.

40. À la demande explicite de modifier Calendar, A reçoit l’import Google iCal.
    Les liens de consultation privés ne sont pas lisibles sans OAuth ; accepter
    uniquement les adresses iCal Google HTTPS. Aucune redirection ni URL externe.
41. Import ponctuel sans stockage du lien secret : seuls créneaux libres et
    métadonnées non sensibles sont conservés. Refuser les flux invalides au lieu
    de considérer leur contenu manquant comme du temps libre. Chaque import
    remplace les créneaux du seul propriétaire et invalide les suggestions.
42. Utiliser icalendar et recurring-ical-events pour les récurrences et exceptions,
    plutôt qu’un parseur ICS partiel fait maison. Plages de sortie choisies et
    horizon 31 jours maximum ; événements transparents/annulés exclus des occupations.
31. Raccorder l'import vidéo Python à l'API V2 et aux faits B existants. Les fichiers TypeScript déposés manuellement restent intacts et inactifs. Aucune base parallèle ni changement de D_connectors.
32. Une vidéo produit un signal proposé, privé. Seule la confirmation existante autorise son utilisation. Conserver la date du signal séparément de la date d'analyse ; absence de date signifie inconnue. Les refus repérés dans le texte retirent les propositions correspondantes.
33. Utiliser un registre de jobs opérationnel dans la même SQLite ; deux traitements maximum dans un processus. Après interruption, échec explicite et nettoyage, puis renvoi manuel. Les fournisseurs externes exigent un double accord : configuration serveur et consentement de l'import.
34. Adapter l'environnement de test à Windows : tzdata, identifiants courts pour les cas contenant des fichiers volumineux et paire de sockets interne d'asyncio. Les connexions API restent interdites dans les tests hors ligne.

35. Le partage mobile est reçu dans le service worker, puis conservé temporairement sur l'appareil. Une navigation native ne possède pas le header X-Member-Token : pas de tentative d'attribuer un profil implicitement ni de créer une route d'upload serveur anonyme.
36. Réutiliser reelForm/submitExperience et /api/v2/reels/upload. /partager est un écran de réception, pas une nouvelle mémoire. Le choix explicite de profil verrouille le brouillon ; seuls les appels authentifiés écrivent dans B.
37. Un lien seul peut devenir une piste issue du texte explicitement reçu ; demander le fichier pour le pipeline vidéo. Aucun scraping, téléchargement, récupération de comptes ou audio inventé.
38. Cache public limité à la feuille de style et aux icônes. Pas de réponses API ni de médias privés en CacheStorage. Brouillons locaux bornés et supprimables, délai d'expiration distinct de la date réelle du signal.

39. Combiner recherche web à la demande et règles locales : le modèle adapte la recherche, le code contrôle consentements, sources affichées et quota. Ne pas promettre une couverture exhaustive ni remplacer les fournisseurs par des événements inventés.
40. Garder les réponses web dans un cache privé, pas dans le catalogue planifiable, tant que le prix, les dates et la localisation ne sont pas validés. La présence d'une citation prouve une référence, pas une disponibilité ni l'exactitude de chaque phrase.
41. Avec les 50 EUR de crédit annoncés, démarrer à 1 USD/jour et 10 USD de réserves cumulées ; ne pas engager tout le crédit. Comptage conservateur par tentative, transaction SQLite immédiate, zéro retry SDK. Bloquer les modèles sans allocation validée. Les dépenses hors de cette base et les fournisseurs Reels restent hors compteur.
42. Réutiliser l'extraction et les faits de conversation existants, avec vocabulaire français local et horizon temporaire. Ne pas envoyer les notes personnelles du partenaire à la recherche web. L'utilisateur choisit séparément l'analyse cloud et la visibilité des faits enregistrés.
## Transfert de discovery — 26 septembre 2026

31. Ajouter la collecte OpenAI Responses dans `C_discovery` à côté des services V1/V2 existants. La collecte reste une commande manuelle, désactivée sans `DISCOVERY_ENABLE_LIVE=true`, plafonnée à cinq activités et une requête Responses par exécution. `data/activities.json` est un cache local validé selon `backend/shared/activity.json` ; les scores personnalisés restent `null` dans ce cache. Le ranking du service V2 existant reste distinct. Conserver `service.py`, `legacy.py` et les tests historiques. Aligner la dépendance sur OpenAI 3 déjà présent et ajouter `python-dotenv`. Le transfert du cache ne branche pas encore ce cache sur le catalogue V2 servi par l'API.


31. Discovery réel : exposer le cache Activity validé via `GET /api/v2/activities/real` et l’afficher séparément des 76 exemples fictifs. Aucun chargement web au démarrage ou à l’affichage. Les fiches sans prix, durée ou coordonnées restent consultables avec lien source, mais ne deviennent pas des candidats E : aucune donnée de planification n’est inventée.


## Décision Ask web, 26 septembre 2026

Réutiliser WebDiscovery et son quota plutôt qu'ajouter un agent, une base ou un deuxième connecteur. Distinguer la suggestion web citée d'un programme persisté et vérifié : aucune conversion automatique d'une réponse libre en réservation ou candidat planifiable. Conserver la composition locale et la sélection des activités existantes.

## Décisions agendas et proactivité, 26 septembre 2026

La mission utilisateur autorise explicitement l'extension de A. Garder les opérations existantes sur les intervalles dans time_slots.py, réexportées par service.py, pour éviter les imports cycliques. Utiliser une interface CalendarProvider et la SQLite existante. Les tokens OAuth, le cache MSAL et les plages occupées sont chiffrés ; aucun titre personnel n'est persisté. OAuth state consommé une seule fois, PKCE SDK, cookie de liaison navigateur HttpOnly/SameSite Lax/Secure sous HTTPS, callback lié à une origine exacte, journaux d'accès expurgés de ses paramètres.

Utiliser Graph calendarView pour supporter Outlook personnel et professionnel ; getSchedule refuse les comptes personnels selon la documentation officielle. Plafonner pagination et timeouts. Toute erreur conserve le cache mais le rend inutilisable pour annoncer des disponibilités. Sans créneaux personnels explicites, fenêtre produit 18 h-23 h à Paris ; ce choix est affiché. Lecture fraîche requise (15 min), pas d'appel fournisseur caché à chaque rendu d'écran.

Chaque version du programme et chaque ensemble de connexions exigent deux confirmations. Pas d'invités externes. Événements du catalogue fictif bloqués par défaut ; double activation serveur pour écrire une DÉMO dans un compte de test. Réessayer seulement les comptes non synchronisés. Invalider le cache de disponibilités après tentative d'écriture, même en cas de résultat incertain. La déconnexion ne supprime rien chez le fournisseur.

Séparer le consentement aux propositions et celui à OpenAI. H conserve une déclaration d'humeur explicite dans la mémoire existante avec sa visibilité d'origine. G ignore le privé, les signaux périmés et les humeurs des narrateurs importés. Son analyse OpenAI facultative réutilise le budget existant, seulement sur des extraits déjà autorisés. Le retrait de consentement efface le résultat d'humeur mis en cache, conserve son horodatage de limitation ; l'effacement du profil supprime aussi cet horodatage.

Scheduler interne opt-in, un worker, verrou local et bail SQLite. Démo manuelle : seul le délai de sept jours est ignoré ; jamais les consentements et disponibilités. Le bouton historique d'opportunité utilise aussi la chaîne réelle dès qu'un agenda ou un consentement proactif existe. Le bonus événement pertinent reste nul tant que E travaille sur le catalogue fictif. Apple : documentation actuelle plus nuancée que « aucun OAuth », autorisation par compte pour certaines apps compatibles ; pas de connecteur CalDAV ou de connexion affirmée sans parcours validé. Aucun service de push tiers ajouté.


## Décisions du deck, 26 septembre 2026

Réutiliser les modèles E, les créneaux A, les filtres C, la mémoire B et v2_plans ; étendre PlanningService sans remplacer le planner historique. Préparer toutes les combinaisons faisables de taille exacte, bornées à cent candidats, puis diversifier. Ne pas dupliquer un programme ou relâcher un refus pour afficher artificiellement trois cartes. Les demandes explicitement ordonnées (« puis ») conservent cet ordre ; une cuisine reconnue est exigée sur l'étape restaurant.

La méthode Pipelex appelle le même calcul Python via PipeFunc. Pas de PipeLLM pour réévaluer des goûts déjà normalisés dans B/C, afin de préserver les consentements et le budget. Le backend local reste la référence et contrôle l'identité de la sortie Pipelex. Le runtime optionnel n'est pas installé/testé en réel. Les labels viennent des catégories retenues ; les explications LLM restent derrière le drapeau existant.

Un pool sauvegardé n'est pas une disponibilité éternelle : expiration 24 h liée à la recherche d'origine, refus des snapshots dont les champs de planification ont changé, vérification des règles actuelles. Le remplacement doit rester entre les voisins initiaux. Composer crée un nouveau brouillon ; swiper à droite n'accepte rien. Aucun mot du profil privé dans les explications.

Conserver le front sans framework ; écrire le deck en .mts strict et fournir le .mjs compilé au navigateur. Types générés depuis Pydantic pour les nouvelles routes. Démonstration isolée avec trois programmes fictifs, puis test intégré API/SQLite ; distinguer ces preuves d'une validation de données réelles ou d'un test sur téléphone physique.

## Décisions, cartes individuelles, 27 septembre 2026

- Réutiliser E et sa SQLite, exposer une projection des candidats déjà filtrés plutôt
  que limiter les cartes aux seules étapes des trois programmes.
- Conserver l'ancien composant DateProposalDeck comme module de compatibilité testé ;
  un seul composant est monté dans Ask : ActivitySwipeDeck. Aucun deuxième écran.
- Garder/passer n'est pas une déclaration de goût ; aucun fait mémoire n'est créé.
- Aucun plafond de trois sélections dans le navigateur. Le contrat borné à 50 cartes
  évite les requêtes démesurées ; les conflits sont signalés puis vérifiés au serveur.
- TypeScript strict et DOM natif, sans ajouter React ni bibliothèque de gestes au
  projet existant. Georgia pour les noms ; illustrations SVG locales sans photo fictive.
- Le mode standard est explicite dans les requêtes, distinct d'un consentement cloud.
  Les marques et paramètres de moteur restent dans les outils/documentation techniques.
- Conserver les confirmations de fichier, de visibilité mémoire et de calendrier.
- Corriger la lecture UTF-8 du catalogue synthétique. Réparer uniquement les titres
  présentant exactement le mauvais décodage cp1252 connu, jamais les titres personnalisés.

43. Remplacer le cercle par un dessin SVG natif, avec flammes ancrées sur les
    mèches. Mesurer le volume micro/lecture avec Web Audio, seuil de bruit,
    attaque rapide et retour progressif. Aucun nouvel envoi ni stockage des
    mesures. Ne jamais connecter le micro à la sortie audio ; réutiliser la
    source de chaque lecteur et libérer le contexte à la fermeture.
    Conserver les états textuels accessibles et respecter reduced-motion.

44. Versionner les URLs des ressources modifiées (CSS, app et import vocal) pour
    forcer leur rechargement ensemble. Une version sur le seul document HTML ne
    suffit pas à renouveler les imports JavaScript déjà en cache.

45. Publication sur noe/memory : rejouer le commit local sur l’historique distant
    sans push forcé. Conserver les fonctionnalités des deux côtés ; retirer les
    doublons de fusion qui bloquent la syntaxe, garder le traitement conversation
    transactionnel/idempotent et réunir calendar-import/reel-import dans le même
    contrôleur. Aucun changement aux contrats partagés de l’équipe.
## Résolution de main et Gradium, 27 septembre 2026

- Fusion explicite demandée par l'utilisateur : poursuivre le MERGE_HEAD existant,
  conserver les deux parents et ne pas forcer/reset/pousser la branche partagée.
- Garder les utilitaires d'intervalles communs de A ; ajouter l'import iCal sans
  remplacer les connexions OAuth ni annoncer une synchronisation iCal automatique.
- Le dialogue de Noé appelle la même recherche web que les cartes, avec le profil
  authentifié. Les offres incomplètes restent consultables, pas de faux programme.
- Conserver les deux suites calendrier : OAuth/proactivité dans test_calendar.py,
  import iCal dans test_google_calendar_import.py. Le scénario iCal publie ses
  offres simulées sur le deuxième jour libre, sans dépendre de l'ancien catalogue.
- Étendre la liste des paramètres acceptés par run_ai.ps1 à GRADIUM_ sans activer
  la voix ou créer de secrets. Les tests du fournisseur restent simulés.


46. En développement local, les pages, modules JS et CSS doivent provenir du
    disque à chaque chargement : no-store et pas de 304 sur ces routes. Le worker
    ne conserve que les icônes, purge son ancien cache public et s’active aussitôt.
    Ne pas effacer les données utilisateur pour résoudre un problème de cache UI.
## Intégration de la PR 6 après rejet du push

Fusionner origin/main au lieu d'écraser l'historique partagé. Conserver le nom
Chandelle et les routes de recherche réelles, ajouter le middleware no-store de
Noé. Cache des icônes renommé v4 pour retirer les versions v1, v2 et v3 issues des
deux branches ; le test du worker vérifie leur suppression et préserve les caches
d'autres applications. Aucun changement aux brouillons privés IndexedDB.

## Catalogue utilisateur importé, 27 septembre 2026

La nouvelle demande fournit de vraies données et autorise leur ajout au pipeline
précédemment limité au web. Conserver une seule entrée PlanningService, les mêmes
cartes et filtres, avec un catalogue importé et une recherche web complémentaire.
Ne pas réintroduire les anciennes données synthétiques.

Le code embarque un JSONL gzip déterministe, pas les classeurs ni leurs images
SVG incorporées. L'import est une préparation facultative avec openpyxl ; le
serveur n'a aucune dépendance Excel. FTS5 indexe v2_activities dans la SQLite
existante. L'empreinte évite de réimporter au démarrage, l'identifiant du
fournisseur empêche les doublons et une erreur invalide tout le nouvel import
avant écriture. Un export partiel ne prouve pas la fermeture d'un lieu.

Conserver la provenance fichier/onglet/ligne, les contradictions et la date
d'import séparée de la date de collecte inconnue. Supprimer les colonnes
de présentation, les avis et les états instantanés non datés. Une gamme de
prix reste qualitative. Un article est une piste ; un film est une référence.
Ni l'un ni l'autre ne prouve un événement réservable. Les sources importées
ne deviennent jamais candidates E sans enrichissement web vérifié.

Ne transmettre qu'une présélection publique de huit noms/URLs au web. Les
notes privées restent dans B et les refus restent prioritaires. L'absence
d'API ne bloque pas les pistes locales. Une synthèse web pour la même identité
fournisseur remplace sa carte importée dans le résultat sans réécrire la source
d'origine. Les doublons web restent audités par l'étape commune de déduplication.

## Import Bar.xlsx, 27 septembre 2026

Étendre l’import existant, sans deuxième catalogue : MisterGoodBeer fournit ici
160 fiches de lieux permanents. Déduire la région du code postal de l’adresse,
conserver le tarif avec son unité pinte et les conditions commerciales citées.
Ne pas convertir le tarif d’une boisson en budget du date. Ignorer les capacités
réservables, badges « vérifié » et images tierces non nécessaires. La date de
collecte reste inconnue. Bar.xlsx reste optionnel pour les anciens lots de sept
fichiers. Les recherches de terrasse excluent explicitement son absence.
