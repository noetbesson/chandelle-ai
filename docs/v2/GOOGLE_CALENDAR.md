# Disponibilités depuis Google Calendar

Dans **Nos disponibilités**, chaque personne peut maintenant importer son agenda
Google au lieu de saisir ses créneaux à la main.

## Quel lien utiliser ?

Depuis Google Calendar sur ordinateur : **Paramètres → Paramètres de mes agendas
→ choisir l’agenda → Intégrer l’agenda → Adresse secrète au format iCal**.
L’adresse publique au format iCal fonctionne également si cet agenda est public.
Le lien doit être une URL Google HTTPS se terminant par `basic.ics`.

Le lien habituel de navigation ou de partage Google Calendar n’est pas un flux
d’événements lisible sans authentification. Ne pas rendre un agenda privé public
pour cette fonctionnalité : utiliser l’adresse secrète iCal. Si l’administrateur
Google Workspace masque cette adresse, cette intégration par lien ne peut pas
lire l’agenda privé ; une connexion OAuth serait une autre intégration, non livrée ici.

L’adresse secrète donne accès à l’agenda : la coller seulement dans le champ de
l’application, pas dans Git, un ticket ou une conversation publique.

## Utiliser

1. Relancer le backend et recharger l’interface après cette modification.
2. Terminer les deux entretiens, puis ouvrir **Nos disponibilités** sous votre profil.
3. Coller l’adresse iCal, choisir le premier jour, une période de 1 à 31 jours et
   les heures quotidiennes pendant lesquelles vous acceptez une sortie.
4. Cliquer **Calculer mes disponibilités**. Les plages précédentes de cette
   personne sont remplacées uniquement si le téléchargement et l’analyse réussissent.
5. L’autre personne importe son propre agenda ou saisit manuellement ses créneaux.
   Chandelle utilise l’intersection pour les recommandations, y compris vocales.

Par défaut : 14 jours, 08:00–23:00, heures de Paris. Les événements sont retirés
des plages choisies ; seules les périodes libres d’au moins 30 minutes restent.
Un agenda vide donne toutes les plages choisies ; un agenda plein donne zéro
disponibilité, sans réactivation silencieuse du calendrier fictif.

## Mise à jour et limites

Il s’agit d’un **import ponctuel**, pas d’une synchronisation de fond. Le lien
n’est pas enregistré : le recoller pour actualiser après un changement dans
Google. L’écran affiche la date et la période du dernier import. Un seul agenda
Google est lu ; les autres agendas superposés dans l’interface Google ne sont pas
inclus automatiquement. L’import tient compte du contenu réellement reçu, pas
des modifications que Google n’aurait pas encore répercutées dans son flux iCal.

Les événements récurrents quotidiens, hebdomadaires, mensuels et annuels,
exceptions EXDATE/RECURRENCE-ID, journées entières et durées sur plusieurs jours
sont pris en compte. Les événements annulés ou déclarés transparents (« Libre »)
ne bloquent pas. Les fuseaux explicités sont respectés ; dates entières et heures
flottantes utilisent X-WR-TIMEZONE, sinon Paris. Les heures locales ambiguës sont
refusées si leur instant ne peut pas être déterminé.

L’import refuse les récurrences à la seconde/minute/heure et les règles ayant
plusieurs heures/minutes/secondes explicites par occurrence, plutôt que de
fabriquer des disponibilités incomplètes. Limites : 5 Mo, 5 000 composants VEVENT,
10 000 occurrences développées, 500 créneaux libres persistés. Pas de troncature
silencieuse : un dépassement ne remplace pas les créneaux précédents.

## Confidentialité et architecture réelle

- `backend/integrations/google_calendar.py` : téléchargement Google HTTPS sans
  redirection, URL limitée au chemin iCal, borne de taille et délai ; parsing via
  `icalendar` et `recurring-ical-events`, extraction des seules plages occupées.
  Les URL iCal sont masquées dans les logs de requêtes httpx ; erreurs nettoyées.
- `A_calendar/service.py` : soustraction des plages occupées aux horaires choisis,
  conservation des créneaux libres et intersection du couple. Contrat TimeWindow
  et moteur E inchangés ; la saisie manuelle reste disponible.
- `POST /api/v2/availability/google-calendar` : authentification membre et deux
  entretiens terminés ; identité/couple dérivés du token, pas du corps utilisateur.
- `v2_availability` conserve uniquement les créneaux libres. La nouvelle table
  `v2_calendar_imports` conserve date d’import, période et heures choisies. Ni URL,
  titre, description, participants, lieu, ni événements bruts n’y sont stockés.
- `GET /availability` expose uniquement les informations d’import du propriétaire
  et les créneaux communs. Le partenaire ne reçoit pas l’agenda individuel.
- Import et saisie manuelle invalident les suggestions en attente. La saisie
  manuelle remplace aussi les métadonnées d’import. L’effacement personnel et le
  reset local effacent les métadonnées.

Pas de clé Google ni de configuration OAuth nécessaire pour les URL iCal
accessibles. Aucun lien personnel réel n’a été utilisé pendant le développement.

## Installation et vérification

Les deux dépendances ajoutées sont épinglées dans `backend/requirements.txt`.
Elles ont été installées dans l’environnement de ce workspace. Pour un autre clone :

```bash
.venv/bin/python -m pip install -r backend/requirements.txt
bash scripts/run.sh
```

Dans cet environnement géré par uv sans pip, utiliser plutôt :

```bash
uv pip install --python .venv/bin/python -r backend/requirements.txt
```

`bash scripts/check.sh` inclut les tests du calendrier avec un faux serveur HTTP
Google, sans appel réseau. Ils couvrent aussi la confidentialité, la persistance,
les erreurs de lien, le maintien des anciens créneaux et une recommandation réelle
sur un jour rendu libre par l’import.

## Références consultées

- [Google : adresse secrète iCal](https://support.google.com/calendar/answer/37648?hl=fr)
- [Google : agenda public](https://support.google.com/calendar/answer/37083?hl=fr)
- [Google FreeBusy, autre voie nécessitant autorisation](https://developers.google.com/workspace/calendar/api/v3/reference/freebusy/query)
- [Bibliothèque de récurrences](https://recurring-ical-events.readthedocs.io/en/latest/reference/api.html)
