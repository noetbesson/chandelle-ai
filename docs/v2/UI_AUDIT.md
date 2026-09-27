# Audit UI avant modifications, 27 septembre 2026

Périmètre : écrans actifs frontend/app. Relevé effectué avant modification. Les lignes désignent l'état initial, elles peuvent bouger ensuite.

| Fichier | Ligne(s) | Occurrence visible | Correction prévue |
| --- | --- | --- | --- |
| frontend/app/ai.mjs | 3 | Recherche OpenAI non activée ; erreurs modèle/API/fournisseur | Messages de disponibilité orientés résultat |
| frontend/app/ai.mjs | 4 | Autorisation OpenAI requise ; bouton quota ; tarif technique | Recherche normale ; paramètres serveur conservés |
| frontend/app/ai.mjs | 5 | Autoriser OpenAI ou extraction locale | Analyse normale ; confidentialité conservée |
| frontend/app/ai.mjs | 23 | Mode local / OpenAI indisponible dans notification | Résultat de l'enregistrement |
| frontend/app/ai.mjs | 30 | Cochez l'autorisation OpenAI | Retirer la validation de choix du moteur |
| frontend/app/ai.mjs | 41, 44 | OpenAI recherche / Propositions OpenAI | Recherche de sorties / Vos idées de sorties |
| frontend/app/app.mjs | 41 | Avertissement OpenAI, trois modes moteur, autorisation, quota | Choix de contenu : cartes ou pistes web ; traitement automatique |
| frontend/app/app.mjs | 44 | Refus sans autorisation OpenAI | Retirer le choix de moteur |
| frontend/app/app.mjs | 76 | p.mode et détails techniques du programme | Statut et provenance utiles seulement |
| frontend/app/app.mjs | 77 | OpenAI activé serveur ; statut/modèles JSON | Disponibilité des fonctions sans marque fournisseur |
| frontend/app/app.mjs | 79 | Modale quota OpenAI et facture | Retirer du parcours produit ; API technique conservée |
| frontend/app/calendar.mjs | 9 | mood_mode serveur, explication et option OpenAI | Signaux disponibles ; supprimer le choix de moteur |
| frontend/app/experiences.mjs | 15 | Case Gradium/OpenAI/Pipelex | Traitement standard serveur ; autorisation d'utiliser le fichier conservée |

## Surfaces dynamiques

Les détails JSON de mémoire, source et historique peuvent exposer des noms de modèles sans libellé littéral dans le front. Restreindre les champs affichés aux faits, dates, sources et visibilité utiles. Ne pas réécrire le texte libre fourni par l'utilisateur ni les noms des sources web.

## Hors suppression

Conserver les autorisations de fichier, les droits du profil, le partage des goûts avec le partenaire, l'activation des notifications proactives et la confirmation d'écriture calendrier. Ne pas inventer une case cochée : ajouter un mode de traitement standard explicite au contrat, les anciens clients gardent leur comportement.

Aucune page de confidentialité/CGU identifiée dans frontend/app (index, install et share). Ce constat n'est pas une validation juridique ni une autorisation de masquer un traitement dans une politique de confidentialité. Les mentions légales existantes et la documentation technique sont hors du nettoyage produit.

## Résultats après correction

À compléter après exécution des tests et observation navigateur.

## Compléments du relevé

- `frontend/app/app.mjs`, ancien `planCard` vers ligne 38 : badge dynamique `p.mode`
  affichant le moteur dans Home/History. Remplacé par une provenance produit.
- `frontend/app/experiences.mjs`, ligne 23 initiale : `normalization_backend` exposait
  le fournisseur dans une inspiration vidéo. Retiré ; l'état audio transcrit ou
  légende seulement reste affiché.
- `frontend/app/share-page.mjs`, ligne 64 initiale : « autorisez le traitement »
  reformulé en « ajoutez-la à vos inspirations ». L'autorisation du fichier demeure.
- Détails JSON de mémoire : suppression des métadonnées model/mode/backend,
  normalization_backend, scoring_backend, transcription_provider, cloud_consent,
  trace, fallback et embeddings. Le contenu libre saisi par la personne et les
  titres de sources ne sont pas censurés pour masquer un mot qu'elle aurait écrit.

## Diff des reformulations (extraits produit)

```diff
- J’autorise l’envoi de cette demande à OpenAI pour une recherche web.
+ [case supprimée ; demande normale avec processing=standard]
- Autoriser OpenAI à analyser ce message. Sinon, extraction locale limitée.
+ [case supprimée ; mode=auto, visibilité mémoire conservée]
- OpenAI recherche des sorties réelles…
+ Recherche de sorties en cours…
- Propositions OpenAI
+ Vos idées de sorties
- OpenAI : sorties réelles sur le web
- Trois programmes : demande analysée par OpenAI
+ Trouver des pistes réelles sur le web
+ Composer avec le catalogue de démonstration
- Voir le quota restant / Quota local OpenAI
+ [contrôle technique retiré du produit ; quota serveur inchangé]
- J’autorise l’envoi ... (Gradium, OpenAI ou Pipelex).
+ [case fournisseur supprimée ; permission d'utiliser le fichier conservée]
- Analyse ${normalization_backend}
+ [afficher uniquement la présence ou l'absence de transcription]
- Autoriser l’analyse OpenAI de mon humeur
+ [contrôle supprimé ; anciennes autorisations non modifiées]
- ${plan.mode} · demo catalog
+ Programme de démonstration
```

Les appels legacy conservent leur contrat. `auto`/`standard` expriment le fonctionnement
produit, sans forger un `cloud_consent=true`. Ne pas confondre traitement automatique,
clé disponible, succès d'un appel externe et scoring local : ces états restent distincts.

## Transparence et limites

Référence consultée : [CNIL, information sur les traitements](https://design.cnil.fr/concepts/information/).
L'information sur les usages des données reste nécessaire et ne se résume pas à un
choix de moteur. Ce nettoyage ne certifie pas la conformité du service. Aucune page
juridique complète identifiée dans le frontend actif ; à fournir et faire valider
avant ouverture publique. Aucune clause contractuelle fournisseur n'a été auditée.
Les liens et citations des résultats de recherche restent affichés.

## Vérification après correction

Tests navigateur sur les écrans Ask, mémoire, inspirations, disponibilités, paramètres
et résumé final : aucune mention OpenAI/ChatGPT/GPT ni case cloud_consent affichée.
Recherche web simulée : un clic exécute processing=standard sans consentement moteur.
Import PWA et fichier : la permission d'utiliser le fichier reste obligatoire.
Tests exécutés sans appels fournisseurs payants. Journaux techniques, source et
anciens champs de contrat peuvent toujours porter le nom du fournisseur.
