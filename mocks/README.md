# Données d’activités

Les catalogues statiques ont été supprimés. Le produit consomme exclusivement la
recherche web via `/api/v2/dates/search`. Les tests injectent leurs réponses fournisseur
dans leur propre base temporaire ; aucun jeu de test ne peut être chargé par le produit.
