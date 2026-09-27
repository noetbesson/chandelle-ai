# Ask : dialogue libre et recommandations réelles

## Utilisation

Depuis ce dépôt : `bash scripts/run_voice.sh`. Le lanceur lit automatiquement
le `.env` à la racine et ne demande que les valeurs manquantes. `bash scripts/run.sh`
charge aussi ce fichier. Les variables déjà exportées dans le terminal sont
prioritaires, y compris une désactivation explicite à 0. Le fichier est lu comme
une configuration, sans `source`, `eval` ni interpolation de commandes.

Renseigner `OPENAI_API_KEY`, `GRADIUM_API_KEY`, `GRADIUM_VOICE_ID`, puis mettre
`OPENAI_ENABLED=1`, `GRADIUM_ENABLED=1` et `OPENAI_WEB_ENABLED=1`.
Avec seulement les trois clés, `run_voice.sh` active ces trois options par défaut ;
une valeur explicite à 0 dans le fichier ou l'environnement reste prioritaire.
Le modèle complet sans secret est `backend/integrations/.env.example`.
`bash scripts/run_voice.sh --check-env` vérifie les champs sans afficher les
valeurs, démarrer le serveur ou appeler les fournisseurs. Ce diagnostic ne prouve
pas qu’une clé est acceptée par son fournisseur. Voir [LOCAL_ENV.md](LOCAL_ENV.md).

Ask est la page principale. Le chandelier y apparaît immédiatement ; cliquer
sur la chandelle lance la conversation. Chaque demande vocale ou écrite est envoyée
à OpenAI automatiquement ; cette utilisation est annoncée près de la chandelle.
La recherche web est également autorisée par l'envoi, sans case ni confirmation orale.
OPENAI_ENABLED=1 reste requis côté serveur. Micro au
clic, arrêt au clic ou après 45 secondes ; clic pendant la lecture pour parler.
Le chandelier continue de suivre le volume. Le clavier utilise le même dialogue.

Exemples : « On veut un restaurant japonais calme à Paris samedi, quatre-vingts
euros pour deux » ; « finalement cinquante euros » ; « plutôt une expo » ;
« pourquoi celle-là ? » ; « d’autres idées » ; « organise un programme de 18 h à 22 h ».
Il n’y a plus de seuil de trois messages dans le parcours actuel.

Si OpenAI est désactivé, indisponible ou hors quota, Ask affiche une erreur explicite
et conserve le message pour réessayer. Aucun dialogue local ne prend discrètement
le relais. Discover reste consultable sans OpenAI. L’accueil vide est local ; aucun
appel OpenAI avant une vraie demande. Les anciens clients sans consentement cloud
conservent leur mode local de compatibilité.

La navigation principale est Ask → Discover → Settings. Discover conserve la
liste et ses filtres. Settings regroupe Disponibilités, Inspirations, Memories,
History et Réglages, avec un retour Settings dans chaque rubrique. Les formulaires
web et de composition démo restent accessibles sous Réglages → Outils avancés ;
les sélections du catalogue ouvrent directement la composition. Les anciennes
suggestions de Home restent sous History → Suggestions et programmes à venir.
Afficher Ask ne démarre ni dialogue, ni micro, ni appel fournisseur. Le clavier
peut également lancer un échange sans message d’accueil supplémentaire ; Terminer
ferme la session et remet le chandelier en attente.

## Ce qui est raccordé

1. Gradium STT transforme l’audio en texte, Gradium TTS lit la réponse.
2. H conserve une session privée et demande à Responses une décision structurée :
   discuter/préciser, chercher dans la base, chercher sur le web ou composer.
   L’intention complète remplace la précédente : budget, préférences, exclusions,
   lieu, période, heures, sélections et activités déjà refusées dans cet échange.
3. C lit les fiches publiques SQLite via `DatabaseActivities` : catalogue importé
   et résultats web persistés, avec leur provenance réelle. Le classement local
   utilise les profils consentis des deux personnes ; leurs notes ne sont pas envoyées au LLM.
4. Si le catalogue fournit moins de quatre fiches ou des prix inconnus malgré un
   budget demandé, le web cherche automatiquement jusqu'à huit candidats. Leurs
   activités structurées passent par les mêmes filtres et deviennent les cartes
   Ask. S'il reste moins de quatre fiches, ou des prix inconnus malgré un budget,
   une recherche complémentaire essaie
   d'autres adresses avec les mêmes contraintes : au plus deux requêtes web par
   tour, quatre appels d'outil par requête, cache privé de six heures et quota
   atomique. Une panne de la seconde conserve les résultats de la première.
   La zone vient de la demande ; le formulaire historique garde l’Île-de-France.
5. E compose uniquement quand les données sont suffisantes : événements datés
   avec prix, coordonnées, début/fin précis, contraintes et créneau compatibles.
   Les programmes enregistrés sont utilisables dans l’historique, l’acceptation,
   la préparation humaine et l’export ICS existants. Les places ne sont pas garanties.

6. Après la recherche/composition, un second appel OpenAI explique les résultats
   réellement trouvés (IDs, noms, description, prix et horaires connus, inconnues).
   Les IDs évoqués sont validés ; les profils, scores personnels et notes privées
   ne figurent pas dans cette projection. Une question sur les résultats précédents
   utilise un seul appel. Une panne de la seconde passe conserve les résultats et
   affiche un avertissement : elle ne recrée pas le programme.

Les idées réelles restent accessibles sans agenda. Un programme exige un créneau
explicitement demandé ou des disponibilités enregistrées : aucun vendredi fictif
n’est choisi silencieusement par le nouveau dialogue. Un agenda incomplet, vide,
expiré, sans intersection ou incompatible avec la demande a un diagnostic distinct.
L’absence d’activité faisable a son propre diagnostic.

« resto paris 14 budget 40€ max » suffit pour lancer la recherche. Paris 14, 14e,
XIV et 75014 correspondent au même arrondissement ; une simple adresse « Paris »
ne permet pas d'affirmer qu'un restaurant est dans le 14e. Le budget sans unité
vaut 40 EUR pour deux ; « 40 EUR par personne » vaut 80 EUR pour deux. Les menus
individuels sont multipliés par deux, avec leurs conditions dans la description
(midi seulement, hors boissons, plat seul). Un tarif ambigu reste inconnu. Les
fiches à prix connu passent avant celles à prix inconnu. L'objectif est quatre
pistes distinctes ; jamais quatre garanties inventées si les sources en donnent moins.

## Raccorder la future base de restaurants/activités

Fichier : `backend/streams/C_discovery/recommendations.py`.

La base publique importée est déjà raccordée au même service que Discover.
Ajouter de nouvelles sources via les importeurs du catalogue ou injecter une
source respectant le contrat Activity. Conserver des IDs stables, la provenance
et les valeurs inconnues, sans transformer un prix manquant en zéro.
Les résultats web restent des pistes citées, dont la disponibilité doit être vérifiée.
Un lieu permanent
avec horaires textuels, une exposition sur plusieurs semaines ou un prix manquant
reste une suggestion. Le passage à un itinéraire réel exige des horaires de visite
structurés et une durée vérifiée. L’emplacement de départ doit aussi être connu
lorsqu’une limite de trajet du profil doit être contrôlée.

## Contrat et confidentialité

`POST /api/v2/ask/chat` :

```json
{
  "message": "Une exposition à Paris pour 80 euros à deux",
  "request_id": "UUID unique pour ce message",
  "session_id": null,
  "revision": 0,
  "recommend": false,
  "cloud_consent": true,
  "web_consent": true
}
```

Réponse : `session_id`, `revision`, `reply`, `intent`, `suggestions`, `plans`,
`mode`, `fallback`, `diagnostic`, éventuellement `web`, `retrieval` et `warning`.
Une erreur de compréhension OpenAI renvoie HTTP 503 avec `error.code` et un
message nettoyé (configuration, authentification, quota, délai, réponse invalide).
Les anciens clients peuvent toujours envoyer `web_consent=false`. Le client Ask
courant transmet les deux booléens à true, après la notice affichée dans la page.
La révision reste inchangée ; aucune action de recherche/planification ne part.
Une erreur après recherche renvoie les cartes avec `mode=openai_partial` et
`warning`. Un succès complet vaut `mode=openai`.
Renvoyer le même request_id et contenu après une réponse HTTP perdue rejoue le
dernier résultat sans nouvelle facturation ni nouveau programme. Les conflits de
révision et les requêtes simultanées renvoient 409. La protection porte sur le
dernier message et l’ouverture de session, pas un historique illimité de reçus.

`DELETE /api/v2/ask/chat/{session_id}` ferme l’échange du propriétaire.
Le frontend l’appelle à la fermeture/navigation lorsque l’identité n’a pas changé.
À défaut de livraison de cette requête, expiration d’accès après deux heures ;
purge physique lors du prochain accès au service. Au plus dix sessions actives
par personne, 24 messages conservés et les 12 derniers transmis au modèle avec
l’intention courante et les résultats publics bornés. Aucun audio en base. Pas
d’apprentissage automatique ni de modification des agendas. L’effacement personnel
supprime les sessions. Les programmes, explicitement demandés, restent des objets
communs comme auparavant. Un processus interrompu au milieu d’un appel ne relance
pas automatiquement un appel potentiellement payé : recommencer l’échange.

Les anciennes routes `/api/v2/discover/chat` (POST et DELETE) restent des alias
de compatibilité, avec les mêmes sessions et contrôles ; aucune migration des
sessions existantes ni des tables internes `discovery_*` n’est nécessaire.

Les anciens clients envoyant `messages: [...]` gardent le protocole guidé de
compatibilité. Le frontend courant utilise exclusivement le protocole à session.

Variables : `OPENAI_ENABLED`, `OPENAI_API_KEY`, `OPENAI_DIALOGUE_MODEL` (par défaut
`OPENAI_MODEL`, puis gpt-4.1-mini), `OPENAI_WEB_ENABLED`, `OPENAI_WEB_MODEL`, plus les
variables Gradium habituelles. Aucun modèle supplémentaire autorisé dans le quota :
un modèle sans réserve validée produit `model_not_budgeted`. Une réserve texte par
appel OpenAI (0,02 USD), soit 0,02 USD pour discuter ou 0,04 USD pour chercher et
expliquer, plus éventuellement une ou deux réserves web (0,10 USD chacune). Ce compteur
local n’est pas une facture fournisseur. `store=False`, timeout borné, aucun retry SDK.

## Validation et limites

Tests quotidiens : `bash scripts/check.sh` (rapide). Pour le dialogue :
`bash scripts/check.sh --ask`. Avant PR/changement transversal :
`bash scripts/check.sh --full`. Ces trois commandes interdisent les connexions réseau.
Aucun test utile supprimé ; les doubles lancements UI/experiences sont retirés.

Diagnostic réel facultatif et payant :
`RUN_LIVE_OPENAI_SMOKE=1 .venv/bin/python scripts/live_ask_smoke.py`.
Il utilise le .env, deux profils synthétiques et une base temporaire ; il teste
une demande puis une comparaison dans le même échange, sans Gradium ni web.
Ajouter `--web` pour tester « resto paris 14 budget 40€ max », vérifier au moins
trois cartes dans le bon arrondissement, leurs budgets connus et la comparaison.
Ce contrôle payé exige toujours le flag explicite et reste hors des suites usuelles.
La base personnelle n'est ni lue ni modifiée. Le microphone réel reste à vérifier. Le transport
reste par tours, sans écoute permanente ni interruption vocale automatique.

Référence utilisée pour l’adaptateur : [Structured Outputs, documentation OpenAI](https://developers.openai.com/api/docs/guides/structured-outputs).

## Après un redémarrage du serveur

Recharger l’onglet ouvert (⌘R sur Mac) : redémarrer le serveur ne remplace pas
le JavaScript déjà en mémoire dans une page. La version courante affiche
le chandelier directement dans Ask et uniquement le catalogue dans Discover.
Aucun effacement des profils, cookies ou données locales n’est nécessaire.
