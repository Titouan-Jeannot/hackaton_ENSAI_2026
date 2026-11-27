# BlablaCook

Application de repas partagés entre étudiants. Un hôte publie une table, choisit les invités et renseigne les présences après le repas. La carte et l’autocomplétion d’adresse utilisent Google Maps, les photos automatiques des repas viennent d’Openverse (sans clé) et les mails de confirmation partent par SMTP. Sans ces clés, l’application tourne quand même en local, avec des replis : mails affichés dans le terminal, image par défaut, carte indisponible. Le fichier `PROJECT_CONTEXT.md` résume l’architecture et l’historique pour reprendre le projet.

## Démarrer sur son ordinateur

Depuis la racine du dépôt avec Python 3.12 et le module `venv` :

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m blablacook
```

Ouvrir [BlablaCook sur cet ordinateur](http://127.0.0.1:8000/). Le premier lancement crée et peuple la base SQLite dans `var/blablacook-demo.sqlite3`. Ctrl+C arrête le serveur. Au lancement suivant les données persistent. Lorsque la dernière table de la série de démo est passée, le démarrage ou la commande `seed` ajoute une nouvelle série en conservant l’historique.

Pour configurer les clés (Google Maps, SMTP), le port ou les domaines acceptés, copier `.env.example` vers `.env` puis remplir les valeurs. Le fichier `.env` est ignoré par git et chargé automatiquement au démarrage. Les variables déjà définies dans le terminal restent prioritaires.

Après une mise à jour du schéma, une ancienne base de démo est refusée avec un message explicite. Il suffit alors de supprimer `var/blablacook-demo.sqlite3`.

## Comptes et parcours de démonstration

Le mot de passe des treize comptes fictifs est **Tablée-Démo-26**. Tous ont un profil complet : portrait illustré, bio, âge, régime et adresse privée fictive. Une nouvelle inscription exige une adresse d’un domaine étudiant (`blablacook/data/student_domains.txt`, plus `BLABLACOOK_DOMAINS`). Un mail contenant un code à 6 chiffres et un lien est alors envoyé. Sans SMTP configuré, ce mail s’affiche dans le terminal du serveur. Après l’inscription, on arrive sur son profil, et le compte n’est activé qu’après la confirmation.

| Compte | Adresse | À essayer |
| --- | --- | --- |
| Camille | `camille@campus.test` | Gérer la table de pâtes et renseigner les présences |
| Inès | `ines@campus.test` | Demander une place, annuler la soupe du soir, évaluer le repas de la veille |
| Noé | `noe@campus.test` | Déposer une demande concurrente |
| Léa | `lea@campus.test` | Organiser la table « Entre femmes » |
| Lou | `admin@campus.test` | Instruire les signalements et consulter le journal des décisions |
| Hugo, Sarah, Yanis, Chloé, Mathis, Amina, Lucas, Jade | `prenom@campus.test` (sans accent : `chloe@…`) | Profils complets supplémentaires ; Hugo, Amina et Yanis proposent une table |

1. En visiteur, rechercher une table, filtrer par activité et passer de la liste à la carte. Chaque cercle est une zone approximative d’environ 500 m, jamais centrée sur l’adresse. Ouvrir la fiche de la table de pâtes.
2. Se connecter comme Inès : les suggestions « Près de chez toi » apparaissent en haut de l’accueil. Écrire à Camille puis demander une place. Dans un autre profil de navigateur, se connecter comme Camille, ouvrir **Mes repas** et accepter Inès. Côté Inès, la fiche affiche la date de dévoilement de l’adresse (une heure avant le repas) et le lien vers le chat du repas, qu’elle a rejoint automatiquement.
3. Dans **Mes réservations**, annuler la table de pâtes plus de cinq heures avant son début. L’adresse disparaît. Annuler ensuite **Soupe du soir**, préconfirmée deux heures avant le repas lors du peuplement. La confirmation annonce le 1★. L’avis est visible sur le profil d’Inès.
4. Camille ouvre **Retour de la tablée de la veille** dans **Mes repas** et marque Inès présente. Chaque personne peut ensuite déposer son avis depuis son espace. Le second dépôt publie les deux avis.
5. Depuis une fiche, un profil, un message accessible ou un avis publié, envoyer un signalement. Avec Lou, ouvrir **Administration**, sélectionner le signalement et enregistrer une décision motivée.

Pour préparer la démo ou la rejouer à partir de zéro, arrêter le serveur puis choisir la commande adaptée. `reset-demo` efface les comptes, sessions et contenus de la base de démonstration désignée et y recrée les treize comptes.

```bash
.venv/bin/python -m blablacook seed
.venv/bin/python -m blablacook reset-demo
```

## Règles et interfaces

- Les places comptent les invités confirmés, hors hôte. Une table complète continue de recevoir des demandes avant son début. L’hôte attribue manuellement chaque place libérée. Un chevauchement produit un rappel. Si le minimum d’invités n’est pas atteint à la « date limite pour atteindre le minimum » (`check_at` dans le code), l’hôte reçoit un avertissement. Celui-ci se réactive si un invité se désiste.
- L’hôte saisit seulement l’adresse, avec l’autocomplétion Google. Le serveur stocke la position exacte à part et publie un cercle de 500 m dont le centre est décalé au hasard (au plus 350 m) une fois pour toutes. L’adresse et la position exactes sont servies à l’hôte, et aux invités acceptés à partir d’une heure avant le début.
- Le profil contient une adresse privée facultative, qui sert aux suggestions de repas proches (10 km) et au filtre de distance.
- Le titre du repas déclenche la recherche d’une photo sous licence Creative Commons sur Openverse (aucune clé nécessaire). Les mots culinaires du titre sont traduits en anglais pour la recherche. L’image est téléchargée et stockée avec le repas, et son auteur et sa licence sont crédités. Si rien n’est trouvé, l’image par défaut est utilisée. L’hôte peut aussi importer sa propre photo.
- Chaque repas a un chat de groupe : l’hôte et les invités acceptés. Un invité y est ajouté automatiquement à l’acceptation et en sort s’il annule. Les fils privés invité ↔ hôte d’avant la réservation sont conservés.
- Les instants de publication ont un fuseau explicite dans l’API. Le serveur les stocke en UTC et le navigateur les affiche en heure locale. La durée par défaut est de 90 minutes. L’heure de début ferme les demandes et les annulations invité. À cinq heures exactement, l’annulation reste sans sanction.
- Le serveur vérifie l’éligibilité « Entre femmes » lors de la demande et de l’acceptation. L’adresse est accessible à l’hôte, et à l’invité dont la réservation est encore confirmée à partir d’une heure avant le début. Le profil peut masquer la photo publique et la participation aux autres invités. Les photos importées sont redimensionnées et réencodées localement.
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
