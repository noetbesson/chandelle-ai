# Identité éditoriale Chandelle — 27 septembre 2026

Implémentation dans le worktree `noe/api_gradium`. SPA native HTML/CSS/JavaScript,
servie par le montage `/v2-static` existant. Aucun changement des endpoints,
payloads, données catalogue, scoring, recommandations ou consentements.

## Fichiers et responsabilités

| Fichier | Changement |
| --- | --- |
| frontend/app/style.css | Tokens de palette et de polices, navigation, feed vertical, lignes à deux colonnes, responsive |
| frontend/app/index.html | Langue fr, couleur de thème, préchargement de la police locale, script Motion local, version des assets |
| frontend/app/app.mjs | Logo partagé et appel au rendu Discover, en conservant requêtes, filtres et gestionnaires d'actions |
| frontend/app/discover.mjs | discoverPage, discoverSections, discoverActivityRow, activityMeta ; fonctions de présentation pures |
| frontend/app/chandelier.mjs | candleDrawing extrait du composant vocal, SVG inchangé partagé entre logo et Ask |
| frontend/app/voice.mjs | Import du dessin partagé ; contrôleur audio et dialogue inchangés par cette refonte |
| frontend/app/icons.mjs | SVG exacts Calendar22, LocationPin, Euro |
| frontend/app/visuals.mjs | Animations Motion, préférence de mouvement réduit, nettoyage des animations et repli des images en erreur |
| frontend/app/public/fonts/Conjiote Personal Use.otf | Copie binaire de la police fournie dans font/ à la racine |
| frontend/app/vendor/ | Distribution officielle gratuite Motion 13.4.4, licence MIT et provenance |
| frontend/app/ICONS-LICENSES.md | Sources, auteurs et licences des trois icônes |
| frontend/tests/test_discover.mjs, test_visuals.mjs | Métadonnées inconnues, regroupement, échappement, actions, mouvement réduit et nettoyage |
| scripts/check.sh, scripts/verify_frontend_api.py | Ajout des vérifications de présentation et livraison HTTP des assets locaux |

## Polices et palette

Le fichier réel est `font/Conjiote Personal Use.otf`, fourni par l'utilisateur.
Il n'existait pas de `public/fonts` servi au navigateur. La copie dans
`frontend/app/public/fonts/` utilise le montage statique existant, sans nouvelle
route backend ; les deux fichiers ont le même SHA-256 :
`58ad08212630bbe581e1ceb1f9e573c7500a260033858f0f21869311b5c541ba`.

`@font-face` déclare Conjiote (OpenType, poids 400, font-display: swap).
`--font-display` et `.font-display` désignent Conjiote, réservée au logo, h1/h2,
titres de catégories et motifs typographiques de remplacement.
`--font-body` et `.font-body` utilisent `"Helvetica Neue", Helvetica, Arial,
sans-serif`. Corps, descriptions, titres des activités, metadata, prix, boutons,
labels, navigation et formulaires héritent de cette stack. Aucune police téléchargée.

Palette centralisée : crème #fbf2d1, rouge #7a0002, accent #ffcc65,
texte #230f00 et variante #4e0a01. Les couleurs sémantiques de confidentialité,
succès et erreur sont conservées. Pas de grandes surfaces rouges ni d'ombres.

## Discover et logo

La liste réelle est regroupée par `type` uniquement à l'affichage, sans modifier
les objets et en conservant leur ordre au sein de chaque catégorie. Aucune section
vide n'est inventée. Les filtres utilisent toujours leurs paramètres API existants.
Les exemples fictifs gardent comparaison, affinités et accès au programme dans
une section explicitement nommée, repliée par défaut.

Chaque ligne contient un visuel à gauche (36 % sur mobile) et les informations
à droite. Les URL HTTP(S) d'images utilisent object-fit: cover ; une illustration
typographique locale reste visible en cas d'absence ou d'échec. Les quatre sorties
réelles actuellement présentes n'ont pas de photos. Aucun visuel de lieu inventé.
Les prix inconnus restent « Prix à confirmer », zéro signifie « Gratuit » ; dates,
heures, lieux, score et raison ne s'affichent que lorsqu'ils sont fournis.
Titres d'activité limités visuellement à deux lignes, texte complet conservé dans
le DOM et l'attribut title. Le titre Discover reste sur deux lignes aux tailles testées.

Le logo réutilise exactement le chandelier d'Ask. Seuls ses chemins de flamme
oscillent doucement (3,6 s et plus). Ask conserve sa réaction au volume local.
Motion gère l'entrée opacity 0→1 / translateY 12→0, un décalage progressif borné
et la pression scale .98 sur les actions des lignes. Hover discret sur ordinateur.
`prefers-reduced-motion` désactive ces animations, y compris après un changement
de préférence ; navigation et changement de profil nettoient leurs ressources.

## Adaptation des dépendances

Pas de React, pnpm ou shadcn dans ce projet : les registres demandés contiennent
des SVG et non des composants React. Exports locaux réellement utilisés :
`Calendar22` (arcticons:calendar-22), `LocationPin` (mage:location-pin),
`Euro` (pepicons-pencil:euro). Tracés d'origine conservés.

Motion 13.4.4 est installé par sa distribution navigateur officielle, copiée et
servie localement. Aucun Motion+, abonnement, CDN à l'exécution ou nouvelle étape
de compilation. Il n'y a donc pas de commande TypeScript/lint/build à inventer :
la validation du projet est `bash scripts/check.sh`, incluant syntaxe JS, suites
Node, Python et parcours réels FastAPI.

## Validation finale

`bash scripts/check.sh` code 0 : 303 tests Python réussis, 12 ignorés,
5 sous-tests réussis en 50,39 s. Toutes les suites Node, syntaxe JS/shell,
parcours API et livraison des assets passent. Rendu inspecté à 375, 390, 430
et 1280 px ; recherche, comparaison, Ask et Settings vérifiés en navigateur.
Aucun appel fournisseur. Détails et limites dans TEST_MATRIX.md.
