# BlablaCook — Prompt Codex pour construire l’application complète

## 1. Mission

Construis **BlablaCook**, une application web en français où des étudiants organisent des repas partagés et choisissent les invités qu’ils accueillent. Implémente le produit de bout en bout dans le dépôt ouvert dans VS Code. Une personne pilote Codex pour une équipe de quatre. Le dépôt peut être presque vide ou contenir une première implémentation. Le livrable est une **application locale, responsive, persistante et utilisable avec des comptes fictifs**. Couvre le catalogue, l’authentification, la publication, la réservation, les avis automatiques et réciproques, les filtres et la carte, la messagerie, le signalement et une interface admin minimale.

**Exécute dans cette session.** Inspecte le dépôt, communique un plan court, puis écris le code, lance l’application, vérifie les parcours et corrige les problèmes sans attendre de validation entre les jalons. Prends les décisions locales et réversibles nécessaires. Demande une décision uniquement si un blocage exige un arbitrage de fond, une autorisation ou une opération destructive. Continue les travaux indépendants quand une commande échoue.

### Sources et périmètre

- **Ce prompt donne les dernières règles métier.** Les documents antérieurs qui décrivent des crédits ou un livrable public pour le jury sont historiques. Mets à jour les références actives du dépôt si elles orientent le code vers l’ancien fonctionnement. Respecte les instructions techniques applicables d’AGENTS.md et préserve les modifications de l’équipe.
- Le projet est **gratuit et collaboratif**. Le périmètre exclut crédits, portefeuille, transactions de crédits, fonds solidaire, pot commun, dons, paiements, charte obligatoire, coorganisation et demandes de repas par quartier. La capacité est le seul compteur de places. Réutilise le code pertinent du dépôt. Si un prototype historique contient des données, préserve-les et documente la migration ou la création d’une base de démo séparée.
- Le rendu demandé est l’application utilisable localement. La présentation, la vidéo, le site vitrine et la mise en ligne relèvent d’un travail distinct. Garde le code dans le dépôt local et laisse les opérations distantes pour une demande explicite.

## 2. Règles actées et conventions de démarrage

Les règles actées sont détaillées ci-dessous. Ce tableau résout les points encore ouverts pour permettre l’implémentation. Inscris ces conventions dans le README ou le document de référence et centralise les délais et les listes communes.

| Point ouvert | Convention pour cette version |
| --- | --- |
| Minimum et heure de contrôle | Le minimum et le maximum comptent les **invités**, hors hôte. À l’heure de contrôle choisie par l’hôte, seules les réservations acceptées et actives comptent. Si le minimum manque, afficher un avertissement à l’hôte. Une baisse sous le minimum après cette heure maintient ou réactive l’avertissement. Le repas reste programmé tant que l’hôte ne l’annule pas. |
| Repas complet | L’annonce indique « Complet · demandes ouvertes » avant le début. Les demandes existantes restent en attente et de nouvelles demandes sont possibles. Une place libérée peut être attribuée manuellement. Toutes les demandes encore en attente expirent à l’heure de début. |
| Annulation et adresse | Le délai de 5 h est inclusif du côté sans sanction. Un invité confirmé peut annuler jusqu’avant le début. Une annulation tardive ou une absence déclarée entraîne un seul avis de 1★ qui compte dans sa moyenne d’invité. Si l’hôte annule l’offre, neutraliser les 1★ automatiques associés à ce repas et garder une trace interne. L’adresse exacte est retirée pour l’invité après annulation ou clôture. |
| Repas entre femmes | Une hôte qui déclare « Femme » peut cocher « Entre femmes ». L’annonce est visible de tous avec une étiquette. Les membres vérifiées déclarant « Femme » peuvent demander une place. Un genre non renseigné permet de consulter l’offre sans demander de place. Vérifier le critère à la demande et à l’acceptation. Aucune preuve de genre n’est collectée. |
| Données du profil | Catalogue public avec prénom de l’hôte, photo si rendue publique, avis d’hôte publiés et lien vers le profil public. Présentation du profil et note d’hôte accessibles à tous. Email, âge, genre, régime personnel et allergies privés par défaut. Les profils réduits des invités confirmés sont visibles par l’hôte et les autres invités confirmés, avec possibilité de se masquer auprès des autres invités. L’hôte voit les demandes pour ses propres repas. |
| Signalement | Un membre vérifié peut signaler une annonce, un profil, un message auquel il a accès ou un avis publié. Un admin peut instruire ou classer, masquer du contenu, suspendre un compte et neutraliser un 1★ automatique erroné. Garder un journal des décisions. |
| Durée et clôture | La durée est facultative. Utiliser 90 min si elle est omise pour calculer la fin effective et afficher un rappel de chevauchement. Une réservation acceptée reste à traiter si l’hôte ne renseigne pas la présence. L’absence exige une action explicite de l’hôte. |

## 3. Acteurs, accès et comptes

- **Visiteur** : consulter le catalogue, les résultats filtrés, la carte, les fiches repas et les informations publiques des hôtes. L’API publique ne renvoie ni adresse privée, ni email, ni liste de demandes, ni messages, ni données de profil privées.
- **Étudiant vérifié** : publier une annonce, demander une place, gérer ses demandes, écrire à un hôte, déposer un avis quand il est autorisé et signaler un contenu accessible. Les rôles hôte et invité dépendent de l’événement. Un même compte peut jouer les deux rôles.
- **Compte en attente** : accéder à la vérification et quitter sa session. Un email institutionnel normalisé est unique. Configurer une liste de domaines reconnus sans limiter l’architecture à un seul campus. Pour la démo, utiliser des domaines et adresses fictifs avec une vérification locale simulée et clairement indiquée.
- **Profil** : prévoir prénom, photo, présentation, régime alimentaire, allergies, âge et genre. Exiger le prénom. Les autres champs sont facultatifs pour cette version. Afficher les champs privés au titulaire. L’email reste privé. L’adresse de résidence ne fait pas partie du profil. Prévoir un avatar de remplacement et des images de démo fictives ou locales.
- **Admin** : rôle attribué en dehors de l’inscription publique, par exemple lors du peuplement de la base de démo. Protéger les écrans et routes de modération côté serveur. Limiter les données accessibles à celles nécessaires à l’instruction. Enregistrer l’auteur, la date, le motif et l’action de modération.
- **Compte suspendu** : bloque les nouvelles actions métier et révoque l’accès authentifié. Par convention, ferme les demandes actives de l’invité et annule les repas encore ouverts dont il est hôte, sans créer de 1★. Informe les participants concernés et conserve l’historique utile.

## 4. Offres, recherche, carte et publication

### Informations d’une offre

L’hôte vérifié propose un **repas seul** ou un **repas accompagné d’une activité**.

| Champ | Règle |
| --- | --- |
| Titre et description | Titre obligatoire et détails libres dans la description. |
| Menu, ingrédients et allergènes | Menu et liste d’ingrédients obligatoires. L’hôte choisit les allergènes connus ou indique explicitement « Information incertaine ». Rendre cette mention visible. |
| Régimes, langues et ambiance | Sélections parmi des listes communes. Conserver les valeurs dans un référentiel versionné dans le code ou en base. Prévoir une valeur explicite « Aucun régime particulier » ou « Non renseigné » selon le champ. |
| Type et activité | « Repas seul » ou « Repas + activité ». Si ce dernier type est choisi, sélectionner une activité de référence comme film ou jeux de société. |
| Date, heure et durée | Début futur à la publication. Durée facultative, strictement positive si renseignée. Stocker les instants en UTC et afficher les horaires en heure locale. |
| Lieu | Secteur public approximatif. Adresse exacte obligatoire et privée, stockée séparément. |
| Minimum, maximum et contrôle | Entiers, avec 1 ≤ minimum ≤ maximum. Choisir une date et une heure de contrôle avant le début. Compter les invités confirmés hors hôte. |
| Composition du groupe | Offre ouverte aux membres éligibles ou événement « Entre femmes » selon les conventions de la section 2. |
| Image du repas | Facultative. Prévoir des images locales ou un remplacement pour la démo. |

- Après publication, seules la gestion des demandes, l’annulation et la clôture sont possibles. Pour changer une information, l’hôte annule l’offre puis en crée une nouvelle. L’annulation avant la première décision de présence met fin à l’offre et à ses réservations actives, retire l’adresse aux invités et alimente les notifications. Elle n’entraîne aucune sanction automatique pour l’hôte ni pour les invités de l’offre annulée.
- Les résultats présentent les places confirmées disponibles et l’état des demandes. Prévoir une fiche même quand le repas est complet. Les repas passés ou annulés disparaissent des résultats publics actifs et restent dans l’historique des personnes concernées selon leurs droits.
- Mettre en place les filtres **date ou créneau, secteur et distance approximative, régime, allergènes déclarés, langue, ambiance, type, activité, événement entre femmes et disponibilité**. Utiliser la description en texte libre pour les précisions. Un filtre peut écarter les offres déclarant un allergène précis. Afficher séparément les informations incertaines. L’absence de déclaration n’implique aucune garantie.
- Afficher les mêmes résultats filtrés en liste et sur la carte. Placer des points par secteur. La carte fonctionne en démo sans service de tuiles externe, par exemple avec des secteurs fictifs et un fond schématique local. Prévoir la saisie manuelle du secteur. Si la géolocalisation est ajoutée, elle est déclenchée par une action explicite et utilisée seulement pour le filtrage nécessaire.
- Construire les réponses publiques à partir d’une liste de champs autorisés. Omettre l’adresse privée, les coordonnées exactes et les données réservées aux comptes depuis la recherche, la carte, le préchargement HTML, les emails et les notifications. Dans la fiche privée, renvoyer l’adresse à l’hôte et à l’invité dont la réservation ACCEPTED est encore active. Éviter la mise en cache partagée du contenu personnalisé.

## 5. Réservations, minimum et présence

**Distingue « Demander une place » de « Réservation confirmée » dans les écrans comme dans le code.** Une demande correspond à une place pour son auteur. Interdire l’auto-réservation et plusieurs demandes actives pour le même couple invité–offre. Autoriser des demandes et des réservations confirmées qui se chevauchent sur des offres différentes. L’invité gère lui-même ses annulations. Afficher un rappel informatif en cas de chevauchement, avec accès à « Mes réservations ».

| État avant | Action ou condition | État après et effet |
| --- | --- | --- |
| Aucune demande active | Invité éligible envoie une demande avant le début, même si toutes les places sont confirmées | PENDING. Aucune place occupée. L’hôte voit la demande. |
| PENDING | L’hôte accepte avant le début et une place est disponible | ACCEPTED. Une place occupée. Adresse accessible à l’invité. |
| PENDING | L’hôte accepte alors que la capacité maximale est atteinte | Reste PENDING. Renvoyer un conflit explicite. |
| PENDING | L’hôte refuse avant le début | REJECTED. L’invité voit le statut. |
| PENDING | L’invité retire sa demande avant le début | WITHDRAWN. Aucune sanction. |
| PENDING | L’heure de début est atteinte | EXPIRED. Aucune sanction. |
| ACCEPTED | L’invité annule à 5 h ou plus du début | CANCELLED_BY_GUEST. Place libérée. Aucune sanction. |
| ACCEPTED | L’invité annule à moins de 5 h du début, avant le début | CANCELLED_BY_GUEST. Place libérée. Créer un seul 1★ automatique. |
| PENDING ou ACCEPTED | L’hôte annule l’offre | CANCELLED_BY_HOST. Retirer l’adresse à l’invité et fermer les demandes actives. Aucune sanction. |
| ACCEPTED | Après la fin effective, l’hôte marque l’invité présent | ATTENDED. Avis réciproques ouverts. |
| ACCEPTED | Après la fin effective, l’hôte marque l’invité absent | NO_SHOW. Créer un seul 1★ automatique. |

- Vérifier état, droits, délais et capacité dans la transaction qui applique l’action. Deux acceptations concurrentes pour la dernière place ne peuvent pas réussir ensemble. Les demandes en trop peuvent rester PENDING. Rejouer une action déjà appliquée renvoie l’état existant ou un conflit explicite sans nouvel effet.
- À 20 h pour un repas qui débute à 20 h, les demandes PENDING expirent. Pour ce même repas, l’annulation d’une réservation ACCEPTED à **15 h précises** est sans sanction. À **15 h 00 min 01 s**, elle est tardive. Comparer les instants sans arrondi. Traiter l’expiration par un service rejouable, à la lecture ou via un mécanisme interne. Tester avec une horloge injectée.
- À l’heure fixée, calculer le minimum sur les réservations ACCEPTED actives. Avertir l’hôte si le seuil manque, même avec des demandes en attente. Recalculer après une annulation. L’hôte peut laisser le repas ouvert, accepter une nouvelle demande jusqu’au début ou annuler. Le repas ne s’annule pas automatiquement.
- Après la fin, l’hôte traite chaque invité confirmé. Une fois toutes les présences et absences renseignées, clôturer le repas dans l’historique. Un repas sans invité confirmé peut se terminer sans avis. Une clôture oubliée apparaît dans « Mes repas », avec un rappel. Les adresses cessent d’être servies à l’invité quand sa réservation devient terminale.

## 6. Avis, messagerie, notifications et modération

### Avis réciproques et automatiques

- Seuls les participants marqués **ATTENDED** peuvent déposer un avis réciproque. Un avis par auteur et réservation. L’invité évalue l’hôte sur **accueil, ambiance et repas**, avec trois notes entières de 1 à 5 et un commentaire facultatif. L’hôte donne à l’invité **une note globale** de 1 à 5 et un commentaire facultatif. Déduire le destinataire côté serveur.
- Publier les deux avis lors du deuxième dépôt. Si un seul est déposé, le publier après **7 jours** à compter de la validation de présence. Comme convention de démarrage, fermer le dépôt à l’échéance de ces sept jours. Un avis caché est visible de son auteur seul. Calculer les moyennes sur les avis publiés et non masqués, séparément pour les rôles hôte et invité. La note d’un avis sur l’hôte est la moyenne des trois critères.
- L’absence et l’annulation tardive produisent un **1★ automatique côté invité** qui compte dans sa moyenne. Afficher un motif générique « Annulation tardive » ou « Absence déclarée », sans attendre le délai des avis réciproques. Une réservation ne peut recevoir qu’un seul 1★ automatique, même après répétition. Une demande simplement retirée ou expirée ne produit aucun avis. Un invité déclaré absent n’a pas d’avis manuel supplémentaire. Une neutralisation retire le 1★ de la moyenne et garde une trace privée.

### Messagerie et notifications

- Un étudiant vérifié peut écrire à l’hôte d’une offre avant la réservation. Un fil privé par offre et invité. Seuls ses membres peuvent lire et écrire. Texte rendu comme du texte, longueur bornée. Une offre annulée laisse le fil consultable par ses membres en lecture seule. Les pièces jointes sont hors MVP.
- Afficher dans l’application les événements utiles : demande reçue, acceptation, refus, annulation, seuil minimal manquant, rappel de clôture et nouveau message. Générer une seule notification par événement et destinataire. Les notifications n’exposent aucune adresse exacte ni donnée privée. Les emails et notifications mobiles sont hors démo.

### Signalements et interface admin

- Afficher un bouton de signalement sur les annonces, profils, messages accessibles et avis publiés. Demander un motif dans une liste commune et un commentaire libre facultatif. Conserver type, cible, auteur, date et état. Vérifier le droit du membre à consulter la cible. Le signalement reste privé.
- L’admin voit une file, instruit ou classe avec un motif, masque un avis, un message ou une annonce selon la cible, suspend un compte et neutralise une note automatique erronée. Si une décision ferme une offre encore ouverte, réutiliser le service d’annulation pour gérer les réservations, les notifications et la visibilité de l’adresse. Conserver le journal d’administration.

## 7. Écrans, navigation et expérience d’usage

| Écran | Fonctions à livrer |
| --- | --- |
| Accueil et catalogue public | Proposition de valeur en une phrase, recherche, filtres, bascule liste/carte, cartes de repas avec horaire, secteur, ambiance, activité et places disponibles. Accès clair à la fiche. |
| Fiche repas | Photo ou illustration, menu, ingrédients, allergènes, langues, ambiance, activité, secteur et profil hôte. Afficher l’état personnel de la demande, le bouton d’action pertinent, les confirmations visibles et l’adresse lorsqu’elle est autorisée. |
| Inscription, connexion et profil | Email reconnu, vérification de démo, session et édition du profil. Expliquer les champs visibles et les champs privés. En consultation publique, inviter à se connecter quand une action exige un compte. |
| Publier un repas | Formulaire progressif ou en sections courtes. Listes communes, minimum, maximum, heure de contrôle, champs du repas et éventuelle activité. Montrer les erreurs près des champs. |
| Mes repas | Offres de l’hôte, compteur minimum/maximum, demandes en attente, décisions, avertissement de seuil, annulation et clôture des présences. |
| Mes réservations | Demandes actives et historique, statuts lisibles, rappel de chevauchement, retrait ou annulation et confirmation explicite si l’annulation ajoute un 1★. |
| Messages et notifications | Fils privés et historique, envoi de texte, indicateurs d’éléments nouveaux et liens vers la fiche ou la réservation concernée. |
| Avis et profil | Avis d’hôte et d’invité distincts, notes par critère ou note globale, formulaire après présence, statut de publication et origine des 1★ automatiques. |
| Administration | File de signalements, détail et actions autorisées, motif de décision, trace consultable. |

Crée une interface originale, lisible sur mobile et ordinateur, orientée vers la recherche de repas et la décision de l’hôte. Utilise le français pour les écrans et les messages. Prévois les états vide, chargement, action en cours, succès, conflit de dernière place et session expirée. Les actions au clavier, les libellés et un focus visible sont requis. Le texte accompagne les états, même lorsque la couleur les distingue. Évite les boutons décoratifs ou désactivés sans explication. Utilise des ressources locales pour que les principaux écrans restent utilisables pendant la démonstration.

## 8. Architecture, données et contrat d’API

### Architecture par défaut

Si le dépôt ne donne aucun choix déjà opérationnel, utilise **Python + FastAPI + Pydantic + SQLAlchemy + SQLite sur fichier**, une interface HTML/CSS/JavaScript en même origine et Pytest. Conserve une autre stack viable si elle existe déjà. Garde une application monolithique et une seule commande de démarrage. Réutilise les modules existants et découpe seulement autour des responsabilités utiles, telles que les routeurs, l’autorisation, les services métier et la persistance. Fournis des dépendances reproductibles et la configuration d’exemple. L’installation peut télécharger les dépendances. Le parcours de démo, une fois installé, se joue sans service réseau externe.

Fais suivre aux formes HTML et aux opérations API les mêmes services métier. Les réponses API sont la source de vérité sur les places, états et autorisations. Hache les mots de passe avec une bibliothèque adaptée. Pour les sessions par cookie, protège les écritures authentifiées, utilise des attributs adaptés à l’environnement, révoque les sessions à la déconnexion et à la suspension, et teste les refus d’accès. Valide les entrées côté serveur et utilise les mécanismes sûrs de l’ORM, avec contraintes et clés étrangères en base. Donne des erreurs lisibles à l’interface sans exposer des données privées.

### Modèle de données de référence

| Entité | Données et invariants |
| --- | --- |
| Comptes, profils, vérifications et sessions | Email normalisé unique, état de vérification, état actif ou suspendu, rôle, données publiques et privées. Jetons de vérification et sessions avec échéance et contrôle de révocation. |
| Secteurs et référentiels | Identifiant, libellé et coordonnées approximatives du secteur. Identifiants stables pour régimes, allergènes, langues, ambiances, activités et motifs de signalement. |
| Repas | Hôte, description et champs de l’offre, instant de début, durée éventuelle, secteur, adresse privée séparée, minimum, maximum, heure de contrôle, composition du groupe, état et horodatages. |
| Réservations | Repas, invité, état, date de création et de transition, date de validation de présence le cas échéant. Au plus un enregistrement actif par couple invité–repas. Indexer les états par repas et par invité. |
| Avis | Réservation, rôle évalué, auteur si manuel, destinataire, notes et commentaire éventuel, source manuelle ou automatique, motif, statut de publication/masquage. Un avis manuel par auteur et réservation. Au plus un avis automatique par réservation. |
| Fils et messages | Fil unique par offre et invité, hôte dérivé de l’offre. Messages avec auteur, texte et date. Les messages masqués restent consultables uniquement par l’admin habilité pour l’instruction. |
| Notifications | Membre, clé d’événement, date, type et état lu/non lu. Clé unique par destinataire et événement pour empêcher les doublons. |
| Signalements et audit | Cible, auteur, motif, commentaire, état, décision, modérateur et horodatages. Référence à la ressource traitée et au 1★ neutralisé si pertinent. |

Pour les repas, proposer OPEN, CANCELLED et COMPLETED. Un repas OPEN après son début peut encore attendre sa clôture. Réutiliser les états de réservation de la section 5. Pour un retrait dû uniquement à une intervention administrative, garder un motif et un état terminal identifiables, sans créer de sanction automatique. Définir et valider les transitions dans une seule source côté serveur. Les dispositions sur l’heure de contrôle et le maximum doivent fonctionner à partir des données de la base même après redémarrage.

### API de référence

Si le dépôt possède un contrat compatible, le réutiliser. Sinon, partir de ces routes, documenter les schémas réels dans OpenAPI et tenir les pages d’interface alignées dessus.

| Zone | Routes et contrôles |
| --- | --- |
| Authentification | POST /auth/register, /auth/verify-email, /auth/login, /auth/logout. Vérification simulée limitée à la démo locale. |
| Comptes | GET et PATCH /users/me pour le titulaire, GET /users/{id} pour la projection publique. Les champs privés ne figurent jamais dans cette projection. |
| Référentiels | GET /catalog/options ou équivalent. Les filtres et la publication lisent les mêmes valeurs. |
| Repas | GET /meals et /meals/{id} publics, avec champs autorisés. POST /meals réservé aux membres vérifiés. Vue « Mes repas » par filtre ou route distincte. POST /meals/{id}/cancel réservé à l’hôte et au flux admin autorisé. |
| Demandes | POST /meals/{id}/bookings, GET /bookings/me, GET /meals/{id}/bookings pour l’hôte. POST /bookings/{id}/accept, /reject, /cancel et /attendance. Le serveur vérifie le rôle, notamment invité pour cancel et hôte pour les décisions. |
| Avis | POST /bookings/{id}/reviews et GET /users/{id}/reviews. Renvoyer les avis publiés selon les droits et au titulaire son propre avis caché, via une réponse privée. |
| Messagerie | POST /conversations avec le repas, GET /conversations/me, GET et POST /conversations/{id}/messages. Restreindre aux personnes du fil. |
| Notifications | GET /notifications/me et POST /notifications/{id}/read ou équivalent. |
| Signalement et admin | POST /reports. GET /admin/reports et /admin/reports/{id}. Actions admin pour classer, masquer, suspendre et neutraliser un avis automatique, avec motif. |

Retourner des erreurs contrôlées et stables, par exemple `{"code":"MEAL_FULL","message":"Toutes les places de ce repas sont confirmées."}`. Utiliser 401 pour une session requise, 403 pour une action interdite, 404 pour une ressource absente ou privée, 409 pour un conflit d’état ou de capacité et 422 pour une entrée invalide. Autres codes utiles : `MEAL_CLOSED`, `BOOKING_ALREADY_ACTIVE`, `NOT_ELIGIBLE`, `INVALID_STATE`, `REVIEW_WINDOW_CLOSED`. Le serveur déduit qui agit à partir de la session et qui est évalué à partir de la réservation.

### Concurrence et effets de bord

- La lecture de la dernière place et la création d’une confirmation sont indissociables. Sous SQLite, utiliser un mécanisme de sérialisation d’écriture qui couvre la lecture de capacité, ou une opération atomique équivalente. Tester avec deux sessions ou connexions distinctes sur une base fichier.
- Mettre dans la même transaction l’état de réservation et ses effets applicatifs indispensables, dont l’avis automatique et la notification associée. L’annulation d’une offre ferme les réservations actives et écarte les sanctions automatiques liées à cette offre en une opération cohérente.
- Ne pas masquer un échec derrière un résultat vide ou un faux succès. Les traitements d’expiration, de rappel, d’avis et de file admin peuvent être rejoués. Les écritures sont protégées contre les répétitions. Les données déjà traitées restent consultables par les personnes autorisées.
- Injecter l’horloge dans les services et les tests. Les mécanismes de simulation de temps et de peuplement sont réservés au mode local de démo. Servir sur l’interface locale par défaut. Utiliser une base de démo distincte et limiter une éventuelle remise à zéro à cette base explicitement désignée.

## 9. Déroulement de la session

| Jalon | Mettre en œuvre | Vérification avant de poursuivre |
| --- | --- | --- |
| 0 · Socle | Inspecter instructions, git, code, runtimes et tests existants. Configurer le démarrage, la base, le jeu fictif et le mode de démo. | Une base neuve s’initialise et le serveur répond. |
| 1 · Réserver | Comptes, catalogue public, annonces immuables, demandes, acceptation, adresse privée, minimum et annulations. Relier les vrais écrans à l’API. | Un visiteur consulte. Un invité se connecte et demande. L’hôte accepte et seul l’invité autorisé voit l’adresse. |
| 2 · Terminer le produit | Présence, 1★, avis réciproques, filtres et carte, événements entre femmes, messages, notifications et administration. | Chaque parcours est accessible dans l’application et vérifié par un test ciblé ou une recette opérée. |
| 3 · Recette | Installer et lancer depuis une base vierge, peupler, lancer les tests, essayer l’interface sur une largeur mobile, corriger les problèmes et finaliser le README. | Un équipier peut démarrer, tester et rejouer les scénarios avec les seules commandes documentées. |

Poursuis vers le jalon suivant dans la même session. Si un blocage terminal empêche l’exécution d’une partie, indique la commande, l’erreur observée, ce que tu as tenté, la fonctionnalité affectée et le travail restant. Vérifie les parcours indépendants. Garde une note de reprise seulement si elle est utile à la session ou à l’équipe.

## 10. Validation de bout en bout

Teste les règles via leurs points d’entrée habituels, avec une base isolée et une horloge contrôlée. Réutilise les tests déjà présents. Une preuve de fonctionnement peut être un test d’intégration ciblé, un parcours navigateur exécuté ou un contrôle HTTP explicite. Les tests navigateur couvrent au minimum publication, demande, décision, adresse et annulation si l’environnement le permet. Si le navigateur est inaccessible, utilise les tests API et précise les parcours d’interface qui restent à vérifier.

| Cas | Résultat attendu |
| --- | --- |
| V01 · Accès | Le catalogue fonctionne sans compte. Publier, écrire et demander une place requièrent un étudiant vérifié. Un domaine inconnu et un email en double sont traités. |
| V02 · Fiche publique | Un visiteur, un invité PENDING et un tiers vérifié n’obtiennent jamais l’adresse exacte. Une réservation ACCEPTED la révèle. Une annulation ou une clôture la retire pour l’invité. |
| V03 · Publication | Un repas simple et un repas avec activité sont publiables. Un minimum supérieur au maximum, un contrôle après le début ou une durée négative sont refusés. Une publication immuable se remplace en annulant puis republiant. |
| V04 · Maximum | Quatre candidats peuvent demander deux places. Deux acceptations réussissent. Une troisième échoue et laisse la demande en attente. Deux décisions simultanées sur la dernière place ne peuvent pas dépasser le maximum. |
| V05 · Place libérée | Une annulation libère une place. L’hôte peut l’attribuer à une demande encore en attente. Une demande déposée sur une offre complète avant le début peut être traitée ensuite. |
| V06 · Chevauchement | Deux demandes sur des offres différentes au même horaire sont possibles. Les deux peuvent être confirmées. Un avertissement informe l’invité, sans annuler de demande automatiquement. |
| V07 · Minimum | À l’heure de contrôle avec minimum 3, deux ACCEPTED et une PENDING, afficher l’avertissement à l’hôte et garder le repas ouvert. La troisième acceptation résout l’avertissement. Si elle est annulée ensuite, l’avertissement revient. |
| V08 · Borne des 5 h | À exactement 5 h, aucun 1★. À moins de 5 h, une réservation confirmée annulée produit un seul 1★. Le retrait d’une demande PENDING n’en produit aucun. Le début empêche l’acceptation et fait expirer les demandes restantes. |
| V09 · Absence et annulation hôte | Après la fin, la déclaration d’absence crée un seul 1★, même sur répétition. Une clôture oubliée n’en crée pas. L’annulation volontaire de l’offre par l’hôte ferme les réservations actives et neutralise les 1★ automatiques de ce repas selon la convention. |
| V10 · Avis | Après présence, un avis d’hôte et un avis d’invité sont possibles. Les critères sont validés. Un avis seul reste caché avant le délai. Deux avis se dévoilent immédiatement, ou un seul est publié à la borne de 7 jours. Les notes privées, masquées ou neutralisées n’entrent pas dans la moyenne. |
| V11 · Filtres et carte | Les deux affichages partagent les mêmes résultats. Les listes communes sont cohérentes entre formulaire et recherche. Les allergènes incertains sont identifiables. Le filtre entre femmes fonctionne et une personne non éligible ne peut pas envoyer une demande via l’API. |
| V12 · Messages et signalements | Une invitée peut écrire avant de demander une place. Un tiers ne peut pas lire le fil. Un membre ne peut signaler que du contenu accessible. Un non-admin ne peut prendre aucune décision de modération. |
| V13 · Administration | Classer un signalement, masquer un avis, suspendre un compte et neutraliser un 1★. Les changements de moyenne et de visibilité se reflètent dans l’interface. Un motif et le modérateur sont enregistrés. |
| V14 · Persistance et lancement | Après redémarrage, les comptes, repas et réservations subsistent. La base de démo peut être recréée explicitement sans effacer une autre base. Le parcours local a besoin uniquement des dépendances déjà installées. |

## 11. Jeu de données, livrables et compte rendu

Fournis un peuplement de démo reproductible et des identifiants fictifs sûrs. Inclure une hôte, trois invités et un admin. Prévoir un repas simple, un repas avec activité et un repas entre femmes, ainsi que plusieurs secteurs et étiquettes. Documenter le mode d’avance du temps de démo ou proposer des repas historiques préremplis pour tester la présence et les avis. Éviter que toutes les offres soient échues si l’équipe relance la démo un autre jour.

**Parcours principal à vérifier.** Une personne découvre un repas dans le catalogue, parcourt la fiche, se connecte et demande une place. L’hôte reçoit plusieurs demandes, en confirme une et l’invité voit l’adresse. Jouer ensuite une annulation avant la limite, une annulation tardive sur une autre réservation et un repas terminé dont un invité laisse un avis. Vérifier aussi un filtre de langue ou d’activité, un message et le traitement d’un signalement avec le compte admin.

**Livrables.** Code réellement exécuté, configuration d’exemple, schéma reproductible, peuplement local, tests, README avec les commandes exactes d’installation, de démarrage, de test et de démo, les identifiants fictifs et les conventions restantes. Si le dépôt n’a pas d’AGENTS.md, ajouter un fichier court indiquant les commandes du projet et l’emplacement de la référence métier. Les données réelles, secrets et bases locales sont exclus de Git.

**Réponse finale attendue.** Mets en premier l’URL locale et les commandes exactes. Résume les écrans et scénarios vérifiés, le résultat des tests et les décisions provisoires. Indique les limites factuelles et les fonctionnalités incomplètes. Déclare une fonctionnalité terminée seulement si elle est reliée au parcours utilisateur et qu’une vérification identifiable a été effectuée.
