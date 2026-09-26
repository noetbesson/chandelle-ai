# Interface Chandelle

La SPA active utilise les modules JavaScript natifs, sans Next.js ni build npm.
FastAPI sert `app/index.html` à `/` et `/app`, et les ressources à `/v2-static`.

| Chemin | Rôle |
| --- | --- |
| `app/index.html` | Document d’entrée |
| `app/app.mjs` | Navigation, onboarding et parcours principaux |
| `app/experiences.mjs` | Inspirations, disponibilités, comparaison et export |
| `app/style.css` | Styles de l’interface |
| `tests/` | Tests JavaScript sans navigateur ni dépendances npm |

Depuis la racine : `bash scripts/run.sh`, puis http://127.0.0.1:8000.
Les contrôles complets se lancent avec `bash scripts/check.sh`.
Le parcours API de l’interface est dans `scripts/verify_frontend_api.py`.

La V1 reste accessible à `/v1/demo` ; ses ressources sont dans
`backend/api/static/`. Voir [l’architecture](../docs/v2/ARCHITECTURE.md).
