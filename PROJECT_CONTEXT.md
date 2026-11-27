# PROJECT_CONTEXT — BlablaCook

Fichier de reprise : il permet à une personne ou à une IA de reprendre le projet sans tout réanalyser.
**À mettre à jour à chaque modification importante** (section « Journal » en bas).

## 1. Objectif et fonctionnalités

BlablaCook est une application web en français qui permet à des étudiants de partager des repas entre inconnus :
un hôte publie une table, des étudiants vérifiés demandent une place, l'hôte choisit ses invités, puis renseigne
les présences après le repas. La référence métier complète est `BlablaCook_Prompt_Codex.md`.

Fonctionnalités en place :
- comptes étudiants : email unique (normalisé en minuscules), domaines étudiants autorisés (fichier + `.env`),
  **mail de confirmation** (code à 6 chiffres + lien, valable 24 h), compte activé seulement après confirmation,
  redirection vers le profil juste après l'inscription ; sessions par cookie + jeton CSRF ;
- profil : prénom, bio, photo/avatar, **régime en liste déroulante**, allergies, âge, genre, **adresse privée**,
  options de confidentialité ;
- catalogue public avec filtres, vue liste / **carte Google Maps** (cercles approximatifs), **suggestions de repas
  proches de l'adresse de l'utilisateur** en haut de l'accueil ;
- publication de repas (immuable) : adresse seule avec **autocomplétion Google**, **photo choisie automatiquement
  d'après le titre** (Openverse, sans clé ; image par défaut sinon) ; adresse exacte dévoilée aux invités acceptés **1 h avant** ;
- demandes, acceptation/refus, annulation, minimum d'invités avec avertissement à l'hôte à la « date limite pour
  atteindre le minimum », présences, avis automatiques 1★ (annulation tardive, absence) ;
- avis réciproques « à l'aveugle » (publiés quand les deux sont déposés ou après 7 jours) ;
- repas « Entre femmes » ;
- messagerie : fils privés invité ↔ hôte (avant réservation) et **chat de groupe par repas** (hôte + invités
  acceptés, ajout automatique à l'acceptation) ; notifications internes ;
- signalements et modération avec journal des décisions.

## 2. Stack technique

| Couche | Choix |
| --- | --- |
| Langage | Python 3.12+ (testé en 3.14) |
| Serveur | FastAPI + Uvicorn, API JSON sous `/api` |
| Base de données | SQLite via SQLAlchemy 2 (ORM déclaratif, `create_all` au démarrage, pas de migrations) |
| Validation | Pydantic 2 (`blablacook/forms.py`) |
| Front | Une seule page HTML (`templates/index.html`) + JS vanilla, routage par `#hash`, rendu par chaînes HTML |
| Services externes | Google Maps JS API + Places API (New) (navigateur), API Openverse (serveur, via httpx, sans clé), SMTP (`smtplib`) |
| Images | Pillow (photos importées redimensionnées et réencodées en JPEG, stockées en data URL ; portraits de démo) |
| Tests | pytest + `TestClient` (bases temporaires, horloge injectable, mailer et Openverse simulés) ; Playwright pour le test navigateur (ignoré si Chrome absent) |

## 3. Architecture et dossiers

```
hackaton_ENSAI_2026/
├── blablacook/
│   ├── __main__.py     # CLI : serve (défaut), seed, reset-demo ; charge .env automatiquement
│   ├── app.py          # create_app(path, clock, demo, mailer, photo_search) : moteur, routes, erreurs
│   ├── db.py           # modèles SQLAlchemy + database() + transaction() (BEGIN IMMEDIATE) + check_schema()
│   ├── access.py       # hachage scrypt, sessions, CSRF, Context (ctx.user, ctx.now), idempotence,
│   │                   # émission des jetons/codes de vérification
│   ├── domain.py       # règles métier : publication, demandes, transitions, minimum, annulation, avis, chat de groupe
│   ├── forms.py        # schémas d'entrée Pydantic + listes communes (OPTIONS)
│   ├── views.py        # projections de sortie (publique / personnelle) : MealCard, PersonalMeal…
│   ├── catalog.py      # routes auth, profils, repas, suggestions, photos, réservations, avis
│   ├── community.py    # routes messagerie (privée + groupe), notifications, signalements, administration
│   ├── mailer.py       # envoi des mails (SMTP ou console) + gabarit du mail de confirmation
│   ├── domains.py      # chargement et contrôle des domaines étudiants
│   ├── data/student_domains.txt
│   ├── geo.py          # distances (haversine), zone publique approximative, délai de dévoilement de l'adresse
│   ├── imagesearch.py  # recherche de photo Openverse (glossaire FR→EN, cache 24 h, téléchargement, crédits)
│   ├── photos.py       # nettoyage des photos importées
│   ├── avatars.py      # portraits illustrés générés avec Pillow pour les profils de démo
│   ├── demo.py         # peuplement de la base de démo (13 comptes, mot de passe dans le README)
│   ├── templates/index.html
│   └── static/         # common.js (helpers, api()), maps.js (Google Maps : autocomplétion, cartes),
│                       # meals.js (catalogue, suggestions, fiche, publication, Mes repas…),
│                       # account.js (inscription, vérification, profil, messages, admin),
│                       # app.js (routeur, actions, formulaires, photo auto), app.css, images/*.webp
├── tests/              # conftest.py (fixtures world/member/create, last_mail), test_recette.py, test_navigateur.py
├── var/                # base SQLite de démo (ignorée par git)
├── BlablaCook_Prompt_Codex.md  # cahier des charges initial
├── PROJECT_CONTEXT.md, AGENTS.md, README.md
└── .env.example        # modèle de configuration (le vrai .env est ignoré par git)
```

Principes à respecter :
- toutes les décisions de réservation et leurs effets sont dans `domain.py`, dans la même transaction ;
- les réponses publiques sont construites à partir de listes de champs autorisés (`views.py`) : jamais d'adresse,
  de position exacte, d'email ni de donnée privée dans le catalogue ;
- chaque requête API ouvre une transaction (`access.context`) et lance `maintain()` (échéances : expiration des
  demandes, avertissement du minimum, publication des avis) ;
- aucun appel réseau externe dans une transaction (voir `/api/photos/suggest`, mails envoyés en tâche de fond) ;
- aucune clé ni mot de passe dans le code : tout passe par `.env`.

## 4. Schéma de la base (SQLite)

| Table | Colonnes principales |
| --- | --- |
| `users` | id, **email (unique)**, password (scrypt `sel:hash`), name, bio, photo, public_photo, hidden_guest, diet (liste fermée), allergies, age, gender, home_address / home_lat / home_lng (privés), verified, suspended, admin, verification (sha256 du jeton du lien), verification_code (sha256 du code), verification_until, verification_sent, verification_attempts |
| `sessions` | token (sha256 du cookie), user_id, csrf, expires |
| `meals` | id, host, title, description, menu, ingredients, allergens (JSON), uncertain, diets (JSON), languages (JSON), mood, kind, activity, image (nom local ou data URL JPEG, y compris les photos Openverse téléchargées), image_credit, image_credit_url, city, area_lat / area_lng / area_radius (cercle **public** décalé), start, duration, check_at (« date limite pour atteindre le minimum »), minimum, maximum, women, status (OPEN/CANCELLED/COMPLETED), hidden, threshold_warning, warning_seq |
| `addresses` | meal (PK), address, lat, lng — adresse et position exactes, stockées à part, jamais publiques |
| `bookings` | id, meal, guest, status (PENDING, ACCEPTED, WITHDRAWN, REJECTED, EXPIRED, CANCELLED_BY_HOST, CANCELLED_BY_GUEST, ADMIN_CLOSED, ATTENDED, NO_SHOW), created, changed |
| `reviews` | id, booking, author (NULL = avis automatique), recipient, role (host/guest), score, criteria, comment, reason, status |
| `threads` | id, meal, guest, kind : `private` (un par meal + guest) ou `group` (un par repas, guest NULL) |
| `messages` | thread, author, body, created, hidden, system (message automatique d'arrivée/départ) |
| `notifications` | user, event_key (unique par user), label, link, created, read |
| `reports` / `decisions` | signalements et décisions de modération |
| `meal_cancellations`, `write_receipts`, `demo_batch` | traces d'annulation, idempotence, marqueur de la base de démo |

Les instants sont des timestamps UTC (float). Pas d'outil de migration : `db.check_schema` refuse une base créée
avec un ancien schéma et demande de supprimer `var/blablacook-demo.sqlite3` (recréée au démarrage suivant).

Données d'exemple : `demo.py` crée 13 comptes complets en `@campus.test` (Camille, Inès, Noé, Léa, Lou (admin),
Hugo, Sarah, Yanis, Chloé, Mathis, Amina, Lucas, Jade) avec portrait illustré, bio, âge, régime et adresse fictive
placée dans des quartiers réels de Rennes et Bruz ; 6 repas à venir et 2 repas de rejeu (annulation tardive,
présences), avec leurs chats de groupe.

## 5. Installer et lancer

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env          # puis remplir les valeurs (jamais commitées) ; chargé automatiquement
.venv/bin/python -m blablacook            # http://127.0.0.1:8000/
.venv/bin/python -m blablacook reset-demo # repartir d'une base de démo propre
.venv/bin/python -m pytest -q             # tests
```

Variables d'environnement (voir `.env.example`, ne jamais écrire les vraies valeurs ici ni dans le code) :

| Variable | Rôle |
| --- | --- |
| `BLABLACOOK_PORT` | port du serveur (8000 par défaut) |
| `BLABLACOOK_BASE_URL` | URL publique utilisée dans les liens des mails (défaut : URL de la requête) |
| `BLABLACOOK_DOMAINS` | domaines ajoutés à `data/student_domains.txt` (défaut : `campus.test,etudiants.test`) |
| `BLABLACOOK_SMTP_HOST`, `BLABLACOOK_SMTP_PORT`, `BLABLACOOK_SMTP_SECURITY` (starttls/ssl/none), `BLABLACOOK_SMTP_USER`, `BLABLACOOK_SMTP_PASSWORD`, `BLABLACOOK_MAIL_FROM` | envoi des mails ; sans hôte SMTP, les mails s'affichent dans le terminal du serveur |
| `GOOGLE_MAPS_API_KEY` | clé navigateur (Maps JavaScript API + Places API (New)), à restreindre par référent HTTP |
| `BLABLACOOK_IMAGE_SEARCH` | `on` (défaut) ou `off` : recherche de photos Openverse (aucune clé nécessaire) |

Tests : `create_app(path, clock, mailer=ConsoleMailer(echo=False), photo_search=...)` ; le code de vérification
se lit dans `app.state.mailer.outbox` (voir `tests/conftest.py::last_mail`).

## 6. Décisions techniques importantes

- **SQLite + `BEGIN IMMEDIATE`** : sérialise les écritures, ce qui garantit que deux acceptations concurrentes de la
  dernière place ne réussissent pas ensemble.
- **Adresse dans une table séparée** : on ne peut pas la renvoyer par erreur dans une projection publique.
- **Horloge injectable** (`create_app(clock=…)`) : les tests contrôlent le temps pour les échéances.
- **Échéances traitées à chaque requête** (`maintain`) plutôt que par un planificateur : simple, adapté à une démo.
- **Front sans framework ni build** : facile à lancer sur n'importe quel poste.
- **Photos stockées en data URL réencodées** : supprime les métadonnées EXIF, pas de stockage de fichiers.
- **Vérification d'email** : seules les empreintes sha256 du jeton et du code sont stockées ; 5 essais de code
  maximum, renvoi limité à 1 par minute, validité 24 h. Le lien `#verify/<jeton>` fonctionne même sans être
  connecté (le jeton est dans le fragment d'URL, donc absent des logs serveur). Le mail part après la réponse.
- **Ordre d'inscription** (décidé avec l'utilisateur) : profil accessible tout de suite après l'inscription ; tout le
  reste (publier, réserver, écrire) est bloqué côté serveur par `c.member()` tant que l'adresse n'est pas confirmée.
- **Domaines étudiants** : un domaine accepte ses sous-domaines (`ensai.fr` → `eleve.ensai.fr`). Limite connue :
  un domaine d'université accepte aussi les adresses du personnel.
- **Zone approximative** : le centre du cercle public (500 m) est tiré au hasard à 350 m au plus du lieu, **une
  seule fois** à la publication (sinon on pourrait moyenner plusieurs tirages) ; le lieu exact reste dans le cercle.
  Distances, filtres et suggestions utilisent ce centre public, jamais la position exacte.
- **Adresse dévoilée 1 h avant** (`geo.ADDRESS_REVEAL`) : calculée à la lecture dans `views.private_meal`, sans
  tâche planifiée. L'hôte la voit toujours.
- **Adresse de l'utilisateur** (décidé avec l'utilisateur) : champ privé du profil, utilisé pour les suggestions
  (rayon 10 km) et le filtre de distance.
- **Google Maps côté navigateur uniquement** : la clé est servie par `/api/catalog/options` (une clé Maps JS est
  publique par nature : la protéger par restriction de référent). Utilise `PlaceAutocompleteElement` (Places API
  New), l'ancien `Autocomplete` n'étant plus ouvert aux nouveaux clients Google.
- **Photo Openverse** (après Pexels puis Pixabay, qui n'accordent plus de clé facilement) : Openverse
  (api.openverse.org, WordPress.org) est utilisable **sans clé** (anonyme : 100 req/min, 1 000/jour). Le front
  interroge `/api/photos/suggest` pendant la saisie du titre ; cette route n'ouvre pas de transaction, pour que
  les appels réseau ne bloquent pas SQLite. Openverse indexant surtout en anglais, `imagesearch.queries` traduit
  les mots culinaires du titre avec un glossaire (`GLOSSARY`, à enrichir) puis essaie : mots traduits → mot
  principal → titre d'origine. Licences limitées à « usage commercial + modification », catégorie photo,
  contenus adultes exclus ; les résultats dont le titre/les tags contiennent le mot cherché sont préférés.
  Le serveur **télécharge** la vignette (uniquement depuis `api.openverse.org`, ~600 px), la réencode en JPEG et
  renvoie un jeton `openverse:<uuid>` + un aperçu. À la publication, le jeton est remplacé par l'image et le
  crédit « auteur · licence » (lien vers la page source), retrouvés côté serveur ; jeton inconnu ou expiré →
  image par défaut. Cache 24 h. `BLABLACOOK_IMAGE_SEARCH=off` désactive tout appel ; les tests passent
  `create_app(photo_search=False)`.
- **Chat de groupe** : appartenance dérivée des réservations (ACCEPTED, ATTENDED, et CANCELLED_BY_HOST pour que le
  fil reste lisible en lecture seule après annulation) ; créé à la première acceptation, avec des messages système
  à l'arrivée et au départ. Les fils privés d'avant réservation sont conservés.
- **Renommage** (validé par l'utilisateur) : « Contrôle du minimum » devient « Date limite pour atteindre le
  minimum d'invités » dans l'interface uniquement ; la colonne reste `check_at` pour éviter une migration.

## 7. Journal des modifications

### 2026-11-27 — Reprise du projet
- Analyse complète du projet existant (V1 du hackathon). Suite de tests : 16 réussis, 1 ignoré (Chrome absent).
- Création de ce fichier `PROJECT_CONTEXT.md`.

### 2026-11-27 — Évolutions demandées (livrées ; 24 tests réussis, 1 ignoré)
1. Email : unique en base (déjà en place) ; contrôle par liste de domaines étudiants (`data/student_domains.txt` +
   `BLABLACOOK_DOMAINS`, sous-domaines acceptés).
2. Mail de confirmation par SMTP (code + lien) ; routes `/auth/verify-code`, `/auth/verify-email`,
   `/auth/resend-verification` ; suppression de la vérification simulée (`demo_verification`).
3. Redirection vers `#account` (profil) juste après l'inscription, avec l'encart de confirmation.
4. Régime du profil en liste déroulante : Aucun, Végétarien, Vegan, Halal, Casher, Sans gluten, Sans lactose,
   Autre (ancienne valeur libre affichée comme « Autre »).
5. 13 profils de démo complets avec portraits illustrés générés (`avatars.py`) ; 6 repas à venir.
6. Champ « secteur public » supprimé : adresse seule avec autocomplétion Google (adresse + lat/lng + ville).
7. Carte Google Maps : cercles approximatifs (catalogue et fiche), point exact et adresse pour les acceptés 1 h
   avant le repas ; filtre « Rayon autour de chez moi ».
8. Photo automatique selon le titre avec crédit, image par défaut sinon ; import manuel toujours possible
   (d'abord Pexels, puis Pixabay, finalement Openverse : voir ci-dessous).
9. Suggestions de repas proches de l'utilisateur (« Près de chez toi ») en haut de l'accueil.
10. Ajout automatique au chat de groupe du repas lors de l'acceptation ; notifications à tous les membres.
11. « Contrôle du minimum » renommé « Date limite pour atteindre le minimum d'invités », avec un texte d'aide.
- Divers : `.env` chargé automatiquement, `.env.example` complété, détection d'une base au schéma obsolète,
  README et AGENTS.md mis à jour.

### 2026-11-27 — Remplacement de Pexels par Pixabay
- Pexels n'accordant plus de nouvelles clés, la photo automatique utilise l'API Pixabay (`PIXABAY_API_KEY` dans
  `.env`, `.env.example` mis à jour ; `PEXELS_API_KEY` n'est plus lu).
- `imagesearch.PixabaySearch` : recherche (fr, catégorie food puis toutes), cache 24 h, téléchargement et
  réencodage de l'image (`photos.reencode`), jeton `pixabay:<id>` côté client, crédit « auteur sur Pixabay ».
- Image par défaut conservée si pas de clé, aucun résultat, erreur réseau ou jeton expiré.
- Test `test_automatic_meal_photo` réécrit avec un faux client Pixabay (24 tests réussis, 1 ignoré).

### 2026-11-27 — Remplacement de Pixabay par Openverse
- Pixabay ne délivrant pas de clé API directement, la photo automatique utilise Openverse, sans clé
  (`PIXABAY_API_KEY` supprimée ; nouvelle option `BLABLACOOK_IMAGE_SEARCH=on|off` dans `.env.example`).
- `imagesearch.OpenverseSearch` : glossaire FR→EN, filtres de licence, préférence aux résultats pertinents,
  téléchargement de la vignette depuis api.openverse.org, crédit « auteur · licence CC », cache 24 h.
- Image par défaut conservée si rien n'est trouvé, en cas d'erreur réseau, de jeton expiré ou si désactivé.
- Vérifié en réel sur 10 titres (9 photos pertinentes, titre inconnu → image par défaut) ; test
  `test_automatic_meal_photo` réécrit avec un faux client (24 tests réussis, 1 ignoré).
- Les réglages réels (Google Maps, SMTP) ont été déplacés de `.env.example` vers `.env` (ignoré par git).

**Reste à faire / pistes** :
- Tester en conditions réelles la clé Google Maps et le compte SMTP (renseignés dans `.env` ; non testés ici,
  les tests simulent Openverse et le mailer).
- Faire tourner `tests/test_navigateur.py` sur une machine avec Chrome (mis à jour mais non exécuté : les
  bibliothèques système de Chromium manquaient sur la machine de développement).
- Compléter et vérifier la liste des domaines étudiants avec les établissements visés.
- Option : remplacer les portraits illustrés de démo par de vraies photos libres de droits.
- Option : aligner la liste des régimes des repas (« Végétalien », « Sans porc »…) sur celle du profil.

**Problèmes connus** :
- Pas de migrations : tout changement de schéma impose de supprimer `var/blablacook-demo.sqlite3`.
- Sans `GOOGLE_MAPS_API_KEY`, on ne peut pas publier de repas depuis l'interface (l'adresse doit être localisée par
  l'autocomplétion) et la carte affiche un message de repli.
- Le test navigateur est ignoré si Chrome/Chromium n'est pas installé.
