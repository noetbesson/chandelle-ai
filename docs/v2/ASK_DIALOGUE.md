# Ask : dialogue libre et recommandations réelles

## Utilisation

Depuis ce dépôt : `bash scripts/run_voice.sh`. Le lanceur lit automatiquement
le `.env` à la racine et ne demande que les valeurs manquantes. `bash scripts/run.sh`
charge aussi ce fichier. Les variables déjà exportées dans le terminal sont
prioritaires, y compris une désactivation explicite à 0. Le fichier est lu comme
une configuration, sans `source`, `eval` ni interpolation de commandes.

Renseigner `OPENAI_API_KEY`, `GRADIUM_API_KEY`, `GRADIUM_VOICE_ID`, puis mettre
`OPENAI_ENABLED=1`, `GRADIUM_ENABLED=1` et, si souhaité, `OPENAI_WEB_ENABLED=1`.
Le modèle complet sans secret est `backend/integrations/.env.example`.
`bash scripts/run_voice.sh --check-env` vérifie les champs sans afficher les
valeurs, démarrer le serveur ou appeler les fournisseurs. Ce diagnostic ne prouve
pas qu’une clé est acceptée par son fournisseur. Voir [LOCAL_ENV.md](LOCAL_ENV.md).

Ask est la page principale. Le chandelier y apparaît immédiatement ; cliquer
sur la chandelle lance la conversation. Dans « Options du dialogue », cocher
l’autorisation OpenAI pour un dialogue libre. Cocher aussi le web pour rechercher des sorties qui manquent dans
le cache local. Ces cases ne remplacent pas l’activation côté serveur. Micro au
clic, arrêt au clic ou après 45 secondes ; clic pendant la lecture pour parler.
Le chandelier continue de suivre le volume. Le clavier utilise le même dialogue.

Exemples : « On veut un restaurant japonais calme à Paris samedi, quatre-vingts
euros pour deux » ; « finalement cinquante euros » ; « plutôt une expo » ;
« pourquoi celle-là ? » ; « d’autres idées » ; « organise un programme de 18 h à 22 h ».
Il n’y a plus de seuil de trois messages dans le parcours actuel.

Sans OpenAI, l’interface annonce un mode local limité. Il comprend des catégories,
quelques corrections et montants parlés courants ; ce n’est pas une compréhension
linguistique générale. Aucun appel fournisseur n’a été effectué pendant les tests.

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
3. C lit les fiches réelles via `ActivitySource.activities()`. L’implémentation
   actuelle `DiscoveryCache` réutilise `data/activities.json`, sans copie en SQL
   ni modification du contrat partagé Activity. Le classement local utilise les
   profils consentis des deux personnes ; leurs notes ne sont pas envoyées au LLM.
4. En l’absence de fiche pertinente, le web existant peut être appelé avec le
   consentement séparé. Une seule recherche maximum par tour ; cache privé de six
   heures et quota atomique déjà existant. La zone vient maintenant de la demande
   du dialogue ; le formulaire web historique garde l’Île-de-France par défaut.
5. E compose uniquement quand les données sont suffisantes : événements datés
   avec prix, coordonnées, début/fin précis, contraintes et créneau compatibles.
   Les programmes enregistrés sont utilisables dans l’historique, l’acceptation,
   la préparation humaine et l’export ICS existants. Les places ne sont pas garanties.

Les idées réelles restent accessibles sans agenda. Un programme exige un créneau
explicitement demandé ou des disponibilités enregistrées : aucun vendredi fictif
n’est choisi silencieusement par le nouveau dialogue. Un agenda incomplet, vide,
expiré, sans intersection ou incompatible avec la demande a un diagnostic distinct.
L’absence d’activité faisable a son propre diagnostic.

## Raccorder la future base de restaurants/activités

Fichier : `backend/streams/C_discovery/recommendations.py`.

Implémenter `ActivitySource.activities() -> list[dict]`, normaliser les lignes de
la future base selon le contrat Activity existant, puis injecter l’instance via
`RealRecommendations(db, memory, source=...)` dans la composition API. Les IDs
stables sont indispensables aux corrections, à l’évitement et à la sélection.
Ne pas remplacer les valeurs inconnues par zéro ou par un horaire par défaut.
Le champ source du contrat actuel reste celui de la collecte OpenAI ; une source
fournisseur différente nécessitera un adaptateur explicite/une évolution coordonnée
du contrat, pas un faux libellé de provenance.

Le cache de quatre fiches demeure petit et incomplet : ce code ne crée pas une
base exhaustive de restaurants. Les résultats web sont des pistes citées, pas des
candidats E automatiquement fiables. Leur conformité au profil, prix et horaires
n’est pas validée comme celle d’un programme ; la fiche l’indique. Un lieu permanent
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
  "web_consent": false
}
```

Réponse : `session_id`, `revision`, `reply`, `intent`, `suggestions`, `plans`,
`mode`, `fallback`, `diagnostic`, éventuellement `web` et `retrieval`.
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
tour OpenAI (0,02 USD), plus éventuellement une réserve web (0,10 USD). Ce compteur
local n’est pas une facture fournisseur. `store=False`, timeout borné, aucun retry SDK.

## Validation et limites

Tests du contrat Responses avec faux SDK, suite sans connexions réseau et navigateur
réel avec fournisseurs désactivés. La fluidité d’un véritable modèle, la latence et
le microphone réel restent à vérifier avec vos configurations activées. Le transport
reste par tours, sans écoute permanente ni interruption vocale automatique.

Référence utilisée pour l’adaptateur : [Structured Outputs, documentation OpenAI](https://developers.openai.com/api/docs/guides/structured-outputs).

## Après un redémarrage du serveur

Recharger l’onglet ouvert (⌘R sur Mac) : redémarrer le serveur ne remplace pas
le JavaScript déjà en mémoire dans une page. La version courante affiche
le chandelier directement dans Ask et uniquement le catalogue dans Discover.
Aucun effacement des profils, cookies ou données locales n’est nécessaire.
