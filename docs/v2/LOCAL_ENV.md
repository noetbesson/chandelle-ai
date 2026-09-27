# Clés locales et démarrage

Les commandes `bash scripts/run.sh` et `bash scripts/run_voice.sh` chargent
automatiquement le `.env` à la racine du checkout. Copier le modèle
`backend/integrations/.env.example` seulement si aucun fichier personnel n’existe.

Champs nécessaires pour Ask avec la voix et le dialogue libre :

```dotenv
OPENAI_API_KEY=
GRADIUM_API_KEY=
GRADIUM_VOICE_ID=
OPENAI_ENABLED=1
GRADIUM_ENABLED=1
OPENAI_WEB_ENABLED=1
OPENAI_DAILY_RESERVE_USD=1
OPENAI_TOTAL_RESERVE_USD=10
REELS_LIVE_ENABLED=0
```

Renseigner les trois valeurs vides dans l’éditeur local, jamais dans le chat.
Le consentement cloud et le consentement web restent nécessaires dans Ask.
Mettre `OPENAI_WEB_ENABLED=0` pour désactiver le web sans nouvelle question au
lancement. `run_voice.sh` active Gradium par défaut uniquement si cette option
n’est pas renseignée ; une valeur explicite `GRADIUM_ENABLED=0` est respectée.

`bash scripts/run_voice.sh --check-env` vérifie la présence des trois valeurs,
la syntaxe et les options, avec résultat masqué. Il ne vérifie ni le solde, ni la
validité distante des clés, ni l’appartenance du voice ID au compte Gradium.
Aucun serveur et aucun appel fournisseur ne sont lancés par ce diagnostic.

Le fichier est analysé comme des données : aucune commande shell, aucune
interpolation `${...}`, seulement les noms autorisés par le lanceur. Les variables
exportées dans le terminal prennent priorité, même vides ou désactivées. Les clés
sont transmises dans l’environnement du serveur, jamais dans ses arguments ni au
navigateur. Le serveur écoute uniquement sur 127.0.0.1. Les erreurs de configuration
n’affichent pas les valeurs. L’import Python de l’application et les tests ne
chargent pas ce fichier ; un lancement uvicorn direct exige des variables exportées.

Sous macOS/Linux, réserver les permissions à son compte avec `chmod 600 .env`.
Le fichier reste du texte local : toute personne ou application pouvant lire ce
compte peut le lire. Git l’ignore ; ne pas le forcer dans un commit ni le partager.
Le voice ID identifie une voix et n’est pas une clé d’authentification, mais reste
rangé ici avec la configuration.

Pour plusieurs checkouts, conserver un seul fichier et utiliser un lien `.env`
ignoré ou `CHANDELLE_ENV_FILE=/chemin/vers/.env bash scripts/run_voice.sh`.
Un lien cassé ou un chemin explicite absent produit une erreur. Les modifications
sont lues au prochain démarrage, sans rechargement à chaud du serveur.

## Après un redémarrage du serveur

Recharger l’onglet ouvert (⌘R sur Mac) : redémarrer le serveur ne remplace pas
le JavaScript déjà en mémoire dans une page. La version courante affiche
le chandelier directement dans Ask et uniquement le catalogue dans Discover.
Aucun effacement des profils, cookies ou données locales n’est nécessaire.
