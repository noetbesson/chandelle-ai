# Frontend Chandelle

L’interface active est une SPA HTML/CSS/JavaScript native dans `app/`, servie
par FastAPI. Aucun build, framework ou paquet npm n’est nécessaire.

- Les fichiers publiés au navigateur restent dans `app/` ; les tests dans `tests/`.
- Les actions produit appellent les endpoints locaux `/api/v2`.
- Préserver les consentements, l’isolation des profils et les tests de confidentialité.
- Vérification complète depuis la racine : `bash scripts/check.sh`.
