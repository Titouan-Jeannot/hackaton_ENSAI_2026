# BlablaCook

Application locale de repas partagés entre étudiants. Un hôte publie une table, choisit les invités et renseigne les présences après le repas. L’application et la carte fonctionnent hors ligne après installation.

## Démarrer sur son ordinateur

Depuis la racine du dépôt avec Python 3.12 et le module `venv` :

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m blablacook
```

Ouvrir [BlablaCook sur cet ordinateur](http://127.0.0.1:8000/). Le premier lancement crée et peuple la base SQLite dans `var/blablacook-demo.sqlite3`. Ctrl+C arrête le serveur. Au lancement suivant les données persistent. Lorsque la dernière table de la série de démo est passée, le démarrage ou la commande `seed` ajoute une nouvelle série en conservant l’historique.

Pour modifier le port ou les domaines acceptés, copier `.env.example` vers `.env`, modifier les valeurs, puis les exporter dans le terminal de démarrage :

```bash
set -a
. ./.env
set +a
.venv/bin/python -m blablacook
```

## Comptes et parcours de démonstration

Le mot de passe des cinq comptes fictifs est **Tablée-Démo-26**. Une nouvelle inscription accepte par défaut les domaines `campus.test` et `etudiants.test`. Le bouton de vérification locale simule la réception du lien étudiant.

| Compte | Adresse | À essayer |
| --- | --- | --- |
| Camille | `camille@campus.test` | Gérer la table de pâtes et renseigner les présences |
| Inès | `ines@campus.test` | Demander une place, annuler la soupe du soir, évaluer le repas de la veille |
| Noé | `noe@campus.test` | Déposer une demande concurrente |
| Léa | `lea@campus.test` | Organiser la table « Entre femmes » |
| Lou | `admin@campus.test` | Instruire les signalements et consulter le journal des décisions |

1. En visiteur, rechercher une table, filtrer par activité et passer de la liste à la carte. Les points représentent les secteurs fictifs. Ouvrir la fiche de la table de pâtes.
2. Se connecter comme Inès, écrire à Camille puis demander une place. Dans un autre profil de navigateur, se connecter comme Camille, ouvrir **Mes repas** et accepter Inès. Revenir sur la fiche ou l’actualiser côté Inès pour voir l’adresse.
3. Dans **Mes réservations**, annuler la table de pâtes plus de cinq heures avant son début. L’adresse disparaît. Annuler ensuite **Soupe du soir**, préconfirmée deux heures avant le repas lors du peuplement. La confirmation annonce le 1★. L’avis est visible sur le profil d’Inès.
4. Camille ouvre **Retour de la tablée de la veille** dans **Mes repas** et marque Inès présente. Chaque personne peut ensuite déposer son avis depuis son espace. Le second dépôt publie les deux avis.
5. Depuis une fiche, un profil, un message accessible ou un avis publié, envoyer un signalement. Avec Lou, ouvrir **Administration**, sélectionner le signalement et enregistrer une décision motivée.

Pour préparer la démo ou la rejouer à partir de zéro, arrêter le serveur puis choisir la commande adaptée. `reset-demo` efface les comptes, sessions et contenus de la base de démonstration désignée et y recrée les cinq comptes.

```bash
.venv/bin/python -m blablacook seed
.venv/bin/python -m blablacook reset-demo
```

## Règles et interfaces

- Les places comptent les invités confirmés, hors hôte. Une table complète continue de recevoir des demandes avant son début. L’hôte attribue manuellement chaque place libérée. Un chevauchement produit un rappel. Le minimum déclenche un avertissement qui se réactive si un invité se désiste.
- Les instants de publication ont un fuseau explicite dans l’API. Le serveur les stocke en UTC et le navigateur les affiche en heure locale. La durée par défaut est de 90 minutes. L’heure de début ferme les demandes et les annulations invité. À cinq heures exactement, l’annulation reste sans sanction.
- Le serveur vérifie l’éligibilité « Entre femmes » lors de la demande et de l’acceptation. L’adresse est accessible à l’hôte et à l’invité dont la réservation est encore confirmée. Le profil peut masquer la photo publique et la participation aux autres invités. Les photos importées sont redimensionnées et réencodées localement.
- L’hôte renseigne explicitement chaque présence après la fin. La dernière décision clôture la table. Un repas sans confirmé se termine lors du traitement des échéances. L’annulation d’un repas par l’hôte est possible jusqu’à la première décision de présence. Elle neutralise les 1★ liés au repas. Les traitements d’échéance se déclenchent lors des appels à l’API.
- Les notes d’hôte et d’invité ont des moyennes séparées. Un avis manuel isolé devient public sept jours après validation de présence. Le dépôt ferme à cet instant. Les notes d’invité sont consultables par le titulaire et par les hôtes auprès desquels il a candidaté. Une note masquée ou neutralisée sort de la moyenne.
- L’API est sous `/api`. Le catalogue public et la fiche personnelle ont des projections distinctes. L’interface utilise les mêmes routes que les tests. Les écritures authentifiées exigent l’en-tête `X-CSRF-Token` obtenu pour la session. La création d’un repas, d’un message ou d’un signalement accepte `Idempotency-Key` pour rejouer un envoi. Le contrat JSON est consultable dans le [schéma OpenAPI local](http://127.0.0.1:8000/openapi.json).
- Les décisions sur les réservations, les avis automatiques et les notifications associées partagent une transaction SQLite. Chaque décision de modération conserve son motif, sa date et son auteur. Les navigateurs récupèrent les changements lorsqu’on ouvre ou actualise l’écran concerné.

## Tester

```bash
.venv/bin/python -m pytest -q
```

La suite HTTP couvre les scénarios V01 à V14 du cahier des charges avec horloge contrôlée et bases temporaires. La dernière place est disputée par deux clients connectés séparément. Le test navigateur lance son propre serveur local sur un port libre et utilise Chrome ou Chromium installé sur la machine. On peut préciser son exécutable avec `BLABLACOOK_CHROME`. Pytest signale le test navigateur comme ignoré lorsque le navigateur est absent.

La référence métier se trouve dans [le cahier des charges](BlablaCook_Prompt_Codex.md). Les photos de démonstration sont des visuels originaux générés pour BlablaCook, conservés dans le dépôt.
