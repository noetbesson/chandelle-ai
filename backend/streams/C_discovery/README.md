# C_discovery

Découverte d'activités réelles à Paris par l'API OpenAI Responses et l'outil
`web_search`. Aucun scoring utilisateur. Aucun appel à D_connectors.

## Installation (Python 3.11)

Depuis la racine du dépôt :

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/streams/C_discovery/requirements.txt
cp .env.example .env
```

Renseigner `OPENAI_API_KEY` dans `.env`. Ne pas committer ce fichier : il est
ignoré par Git. `OPENAI_DISCOVERY_MODEL` permet de changer le modèle
(`gpt-4.1` par défaut).

## Premier test : 5 résultats maximum

```bash
python -m backend.streams.C_discovery.run_discovery
```

Par défaut, la commande affiche exactement :
`Live discovery disabled: no OpenAI API call made.`

Dans le fichier `.env` **à la racine du dépôt**, utiliser :

```dotenv
OPENAI_API_KEY=votre_cle_ici
DISCOVERY_ENABLE_LIVE=false
DISCOVERY_LIMIT=5
```

Garder `DISCOVERY_ENABLE_LIVE=false` pendant le développement. L'activation
nécessite une décision explicite de l'utilisateur ; seule la valeur exacte
`true` autorise le lancement manuel. Les variables déjà exportées dans le shell
priment sur `.env` (comportement de python-dotenv).

Le plafond est **5**, contrôlé avant tout appel. `DISCOVERY_LIMIT` accepte 1 à 5 ;
une valeur invalide arrête le script. `--limit` accepte aussi 1 à 5 et peut
seulement réduire la limite configurée. Aucune extension automatique.
Un lancement effectue au maximum une requête Responses, sans retry SDK,
sans boucle de recherche, cron ou refresh. L'import des modules ne lance rien.
La requête limite les appels outils à 1 et la sortie à 3 500 tokens ; aucun
budget `unlimited`. Ces plafonds ne constituent pas un budget global en dollars.
Après une réponse, le script affiche le nombre demandé et retourné, son ID et
l'usage tokens disponible, même si la normalisation échoue ensuite.
Les fichiers `input.json` et `output.json` restent les emplacements d'interface
existants ; cette commande écrit dans `data/activities.json`.

## Démo sans appel live

La démo doit lire exclusivement `backend/streams/C_discovery/data/activities.json`.
Le lecteur local disponible ne dépend pas du SDK OpenAI :

```python
from backend.streams.C_discovery.data import load_activities

activities = load_activities()
```

Si le cache manque, il signale l'absence sans lancer de recherche. Il n'existe
actuellement aucun branchement de la démo à la découverte live dans le dépôt.

Vérifications locales sans crédits (client API simulé) :

```bash
python -m unittest discover -s backend/streams/C_discovery/tests
```

## Données

- `data/raw/openai_web_YYYY-MM-DD.json` : réponse API complète, citations et sources
  incluses, sauvegardée avant validation. Un nouvel appel le même jour remplace ce brut.
- `data/activities.json` : liste d'Activity valides ; créée uniquement si au moins
  un résultat est exploitable. Une erreur ne remplace pas un précédent fichier valide.
- `backend/shared/activity.json` : exemple officiel du contrat, reproduit dans
  `normalizers/models.py`. `source_url` est un champ de collecte conservé dans
  le brut, pas un ajout au contrat Activity.

Les résultats doivent avoir un nom, un type, une source présente dans les sources
ou citations de la réponse si ces métadonnées sont fournies, et au moins une
adresse ou un site web. Si OpenAI renvoie `sources: null` et aucune citation,
le script accepte les `source_url` structurées mais affiche un avertissement :
ces pages doivent être vérifiées avant d'utiliser le fichier en démo. Les événements
sans début connu sont rejetés, ainsi que ceux hors de la fenêtre des 14 prochains
jours (jour courant inclus, borne supérieure exclue, fuseau Europe/Paris).
Les événements en cours sont acceptés si leur fin connue recouvre cette fenêtre.
Les doublons nom/adresse ou site/date sont éliminés.

Les valeurs inconnues restent `null`. Les horaires exacts ne sont jamais déduits
d'une simple date. Les champs `match_score` et `why` sont toujours `null`,
`source` vaut `openai_web`, `attribution` vaut `OpenAI web search`.
`id` est déterministe et `fetched_at` est l'heure de collecte.
Les types des champs nuls dans l'exemple sont précisés dans le modèle :
dates ISO 8601 avec fuseau, arrondissement entier, prix/note numériques,
horaires et niveau de prix textuels.

La validation contrôle structure, cohérence et présence de sources ; elle ne
constitue pas une vérification indépendante de chaque affirmation du modèle.
Avant toute extension, examiner les cinq résultats et leurs pages sources.

Premier test réel du 26 septembre 2026 : la réponse `resp_02d3ab70b30b9362006ab7cf82409c87d1a68b308bdaf31537`
a retourné 5 activités et consommé 18 888 tokens au total. Le champ API
`web_search_call.action.sources` valait `null`, sans citations attachées au
texte structuré. La réponse est conservée intacte dans `data/raw/`.
Les cinq fiches de `data/activities.json` ont ensuite été vérifiées sur les
pages d'événements de Paris.fr, accessibles par leur champ `website`. Les
horaires erronés ou approximatifs d'Ocean Days, de la Marche des Fiertés et
de Paris Sausage Walk ont été corrigés d'après ces pages officielles.

Si la clé manque, la commande affiche une erreur sans afficher de secret et
sort avec un code non nul. Une erreur réseau, API ou une réponse inexploitable
produit également un code non nul.

Références : [recherche web OpenAI](https://developers.openai.com/api/docs/guides/tools-web-search)
et [sorties structurées](https://developers.openai.com/api/docs/guides/structured-outputs).


## Test dans le nouveau dépôt — 26 septembre 2026

Un seul appel Responses avec `web_search` a demandé et retourné 5 résultats
(`resp_03779d82d141599a006ab7db2e3c3c87d192cf0183335ff94b`,
18 672 tokens). Le retour brut est dans `data/raw/openai_web_2026-09-26.json`.
Les cinq `source_url` générées étaient du texte descriptif, pas des URL :
la validation automatique a donc rejeté les cinq résultats et a conservé
l'ancien cache. Quatre fiches ont ensuite été vérifiées sur les pages officielles
et sauvegardées dans `data/activities.json`. La cinquième, hors de la fenêtre
de 14 jours, a été écartée.

Le schéma et le prompt demandent désormais une URL HTTPS exacte et interdisent
de transformer une date sans horaire en minuit. Ces changements passent les
tests locaux, mais n'ont pas encore été revérifiés par un appel live.


## Affichage local dans la démo

La page Discover lit `GET /api/v2/activities/real`, qui revalide ce cache local. Les fiches réelles sont affichées avec leur site source, séparément des exemples fictifs. Elles ne sont pas encore proposées dans les programmes : leur prix, durée ou coordonnées peuvent être inconnus. La visite de cette page ne déclenche aucun appel OpenAI.
