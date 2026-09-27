# Découverte web commune à Ask et Discover

Le parcours actif est `PlanningService.query` → `WebDiscovery.search` →
`CatalogService.filter_web` → cartes et composition. Le front utilise
`POST /api/v2/dates/search`, authentifié par `X-Member-Token`.

`web_models.py` définit les faits sourcés et leurs champs inconnus. `web.py` utilise
OpenAI Responses et `web_search`, puis vérifie le schéma et la présence des URL
parmi les sources renvoyées. Une référence ne garantit pas une disponibilité.
`service.py` normalise les départements d'Île-de-France, applique les filtres et
classe selon la mémoire autorisée. Les faits publics rejoignent la SQLite existante.

Les anciens fichiers de catalogue et le collecteur CLI parallèle sont retirés.
La commande suivante est un simple client de la même API locale ; elle ne lance
pas un deuxième collecteur ni une exportation JSON servant de source de secours :

```powershell
python -m backend.streams.C_discovery.run_discovery --query "Un restaurant japonais puis une balade"
```

Fournir `CHANDELLE_MEMBER_TOKEN` dans l'environnement du terminal, jamais dans le
chat ou un fichier livré. Le serveur doit être lancé avec sa configuration privée.
Voir le README racine pour les clés, quotas et commandes de test.

Les résultats de recherche sont privés, valables six heures dans le cache ; les
sélections expirent après 24 heures. Un import des modules ne lance aucun appel.
Quatre appels outils maximum et 9 000 tokens de sortie par recherche ; zéro retry SDK.
`OPENAI_WEB_MAX_TOOL_CALLS` accepte 1 à 4 et `OPENAI_WEB_RESULT_LIMIT` 1 à 16.
Ces valeurs sont des plafonds, pas un nombre de résultats garanti.
Le quota SQLite existant s'applique. Aucun flux n'utilise les anciens fichiers
`mocks/` ou une valeur de prix/durée inventée pour remplir une carte.

Les traces stockent l'empreinte de la demande, le mode d'analyse, les nombres bruts,
les pertes par filtre, les champs inconnus et les combinaisons. Le texte personnel
reste absent des logs. Les tests du fournisseur sont simulés et séparés du script
live explicitement activable. Voir `docs/v2/TEST_MATRIX.md` pour les preuves réelles.
