# Decisions

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

46. En développement local, les pages, modules JS et CSS doivent provenir du
    disque à chaque chargement : no-store et pas de 304 sur ces routes. Le worker
    ne conserve que les icônes, purge son ancien cache public et s’active aussitôt.
    Ne pas effacer les données utilisateur pour résoudre un problème de cache UI.

46. Discover actuel utilise une session privée plutôt que la concaténation de
    messages et un seuil de trois tours. Une décision structurée complète remplace
    les contraintes précédentes ; le backend contrôle chaque action et les IDs.
47. Séparer exploration réelle et programme daté : les idées ne nécessitent pas
    d’agenda. Aucune substitution par le catalogue fictif dans ce dialogue.
48. Réutiliser C web et ses consentements/quotas. Les notes de B restent locales ;
    le LLM reçoit seulement l’échange courant et les résultats publics bornés.
49. Source réelle injectable conforme au contrat Activity existant. Ne convertir
    en candidat E que les événements courts, datés et complets. Horaires textuels
    et périodes d’exposition ne constituent pas une séance.
50. Sessions à révision, expiration et reçu du dernier message : pas de double
    appel sur renvoi, pas de résultat croisé entre profils, suppression personnelle.
51. Correction des doubles gestionnaires frontend et de la définition inutilisée
    d’integrations héritées de la fusion. Les tests isolent l’import ASGI via
    CHANDELLE_DB_PATH pour ne pas migrer la base personnelle pendant check.sh.

52. Ask porte le dialogue vocal, le chandelier et les recommandations interactives.
    Discover est le catalogue filtrable. Déplacer les composants sans dupliquer
    H/C/E ; /ask/chat devient canonique, /discover/chat reste compatible. Les
    formulaires historiques sont secondaires dans Ask ; les sélections du catalogue
    ouvrent automatiquement le formulaire de composition concerné.

53. Lire .env uniquement dans le lanceur local, avant le démarrage du serveur,
    pour ne pas charger les clés pendant les imports/tests. Réutiliser le parseur
    python-dotenv sans interpolation ; liste de variables autorisées, erreurs
    masquées, exports prioritaires, secrets absents des arguments du processus.
    Le worktree peut partager le fichier utilisateur par lien local ignoré, sans
    copier ses clés. Diagnostic hors réseau distinct d’une validation fournisseur.

54. Distinguer la version servie de la page déjà chargée : après redémarrage,
    rappeler le rechargement de l’onglet dans le lanceur. Ne pas purger les données
    utilisateur ni forcer une actualisation qui ferait perdre un formulaire en cours.

55. Navigation principale Ask/Discover/Settings. L’état initial du chandelier est
    du HTML sans session ni ressource audio ; seul un geste utilisateur démarre
    l’échange. Regrouper les rubriques secondaires dans Settings sans changer
    leurs APIs, consentements ni mécanismes d’identité. Terminer restaure l’état
    initial ; le clavier peut commencer un échange en un seul message.

56. Refonte uniquement de présentation : grouper les activités par type dans un
    module pur, conserver requêtes/filtres/actions et distinguer le catalogue fictif.
    Partager le SVG du chandelier sans changer le contrôleur vocal. Servir police
    fournie et Motion officiel localement via le montage existant ; aucun framework
    ou pipeline de build ajouté. Conserver les sources/licences des SVG demandés.

57. Supprimer les profils utilisateur de démonstration du produit : ancien fichier
    shared non référencé, route `/dev/seed`, bouton des réglages et option CLI
    `--seed`. Les tests créent leurs propres entretiens via les API publiques.
    Ne pas deviner qu’un profil est fictif à partir de son nom : conserver les
    réponses réelles et les enrichissements explicitement consentis. Initialiser
    une base choisie en CLI ne doit pas toucher la base produit par effet d’import.
