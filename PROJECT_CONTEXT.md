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
- **suggestions « Pour toi »** d'après le profil : jamais un allergène déclaré ni un régime non respecté, classement
  par préférences (ambiance, activité, langues), distance et date, avec les raisons affichées sur chaque carte ;
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
- signalements et modération avec journal des décisions ;
- **version mobile installable (PWA)** : manifeste, icônes, service worker, barre d'onglets en bas sur téléphone
  (Tables · Réservations · ＋ · Messages · Profil), hub « Profil », installation guidée (Android/Chrome et iOS).

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
│   ├── reference.py    # listes de référence (allergènes, régimes, langues, ambiances, activités) et règles de
│   │                   # compatibilité des régimes : source unique pour la base et les formulaires
│   ├── recommend.py    # suggestions « Pour toi » : filtre de sécurité (allergènes, régime) puis score + raisons
│   ├── forms.py        # schémas d'entrée Pydantic + OPTIONS (construites depuis reference.py)
│   ├── views.py        # projections de sortie (publique / personnelle) : MealCard, PersonalMeal…
│   ├── app.py          # (aussi) /manifest.webmanifest et /sw.js servis à la racine de l'appli (portée du SW)
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
| `users` | id, **email (unique)**, password (scrypt `sel:hash`), name, bio, photo, public_photo, hidden_guest, diet_id → `diets`, allergies (précisions libres), age, gender, home_address / home_lat / home_lng (privés), verified, suspended, admin, verification (sha256 du jeton du lien), verification_code (sha256 du code), verification_until, verification_sent, verification_attempts |
| `sessions` | token (sha256 du cookie), user_id, csrf, expires |
| `meals` | id, host, title, description, menu, ingredients, uncertain, mood_id → `moods`, kind, activity_id → `activities` (NULL si aucune), image (nom local ou data URL JPEG, y compris les photos Openverse téléchargées), image_credit, image_credit_url, city, area_lat / area_lng / area_radius (cercle **public** décalé), start, duration, check_at (« date limite pour atteindre le minimum »), minimum, maximum, women, status (OPEN/CANCELLED/COMPLETED), hidden, threshold_warning, warning_seq |
| `allergens`, `diets`, `languages`, `moods`, `activities` | **tables de référence** : id, name (unique) ; `diets` porte aussi for_meal / for_profile. Remplies au démarrage depuis `reference.py` (`db.fill_reference`, idempotent) |
| `meal_allergens`, `meal_diets`, `meal_languages` | **liaisons** repas ↔ référence (clé primaire composée, cascade à la suppression du repas) |
| `user_allergens`, `user_languages`, `user_moods`, `user_activities` | **liaisons** profil ↔ référence : allergies, langues parlées, ambiances et activités préférées (privées) |
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
| `BLABLACOOK_LLM_KEY`, `BLABLACOOK_LLM_URL`, `BLABLACOOK_LLM_MODEL` | brise-glace par IA (facultatif) : API gratuite au format OpenAI, Groq par défaut (`openai/gpt-oss-120b`, `llama-3.3-70b-versatile` ayant été retiré par Groq) ; sans clé, questions par règles |

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

- **Schéma normalisé** (décidé avec l'utilisateur) : les listes JSON et les textes libres (allergènes, régimes,
  langues, ambiance, activité) sont remplacés par des tables de référence et des tables de liaison. L'API garde le
  même contrat (listes de noms) : les modèles exposent des propriétés (`meal.allergens`, `user.diet`…), l'écriture
  passe par `db.label/labels/meal_labels`. Les filtres du catalogue sont résolus en SQL (`any()`/`has()`).
  « Vegan » du profil devient « Végétalien » (même valeur que pour les repas). `reset-demo` ne vide pas les tables
  de référence.
- **Suggestions « Pour toi »** (`recommend.py`, décidé avec l'utilisateur : filtre + score, à la place de « Près de
  chez toi ») : écartés si un allergène du profil est présent, si les allergènes sont incertains alors que le membre
  a des allergies, ou si le régime n'est pas respecté (`reference.DIET_NEEDS` : régime déclaré par le repas, un
  régime plus strict suffit, ex. halal → végétarien ; `DIET_WITHOUT` : sans gluten / sans lactose déduits des
  allergènes certains). Score : régime +3 (+2 via un régime plus strict), allergies respectées +1, ambiance +2,
  activité +2, langue commune autre que le français +1 (aucune langue commune −2), proximité jusqu'à +3 (rayon
  10 km si l'adresse est connue, sinon pas de filtre de distance), repas dans les 3 jours +1. 6 suggestions max.

- **PWA** (décidé avec l'utilisateur : appli web installable plutôt qu'appli native ; onglets en bas, style
  actuel). Le service worker (`static/sw.js`, servi en `/sw.js`) ne met **jamais** `/api/*` en cache (données
  personnelles, état des réservations) ; la page d'accueil est « réseau d'abord » avec copie de secours hors ligne,
  `/static/*` en « stale-while-revalidate ». Changer `VERSION` dans `sw.js` invalide le cache. Tous les chemins
  sont relatifs, l'appli fonctionne donc derrière le proxy SSP Cloud. L'installation exige HTTPS (ou
  `127.0.0.1`/`localhost`) : sur téléphone, passer par l'URL SSP Cloud. Au-delà de 760 px, le menu du haut reste
  et la barre d'onglets est masquée. Icônes générées depuis `icon.svg` (pleines, utilisables en « maskable » et
  pour iOS).

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

### 2026-11-27 — Vidéo de présentation du hackathon
- `presentation/video.py` : lance un serveur sur une base temporaire (`seed`, `ConsoleMailer` : aucun vrai mail),
  pilote Chrome avec Playwright (curseur animé, étiquettes de séquence, fondus, décors « téléphone » avec l’appli en
  iframe), filme par `Page.startScreencast` (CDP) et assemble `presentation/blablacook-presentation.mp4` avec ffmpeg
  (H.264, 1920×1080, 30 i/s, ≈ 2 min 56). Les pages ordinateur sont agrandies de 30 % pendant le tournage.
- Aucune modification du code de l’application. Les changements « style Strava / fil / onglets » restent dans
  `git stash` (non appliqués).

### 2026-11-27 — Base normalisée et suggestions selon le profil (26 tests + recette navigateur réussis)
- Nouvelles tables de référence et de liaison (voir §4) ; colonnes JSON/texte supprimées de `meals` et `users`.
- Profil : allergies en cases à cocher (14 allergènes) + précisions libres, régime en liste déroulante, nouvelles
  préférences (langues parlées, ambiances, activités) ; formulaire de repas : régimes Halal et Casher ajoutés.
- Accueil : section « Pour toi » (raisons affichées en pastilles) et invitation à compléter son profil.
- Démo : préférences pour chaque compte, régimes variés sur les repas. **La base de démo doit être recréée**
  (`check_schema` refuse l'ancienne : supprimer `var/blablacook-demo.sqlite3`).
- Tests : `test_profile_lists_are_normalized`, `test_suggestions_follow_profile` ; tests existants adaptés
  (« Végétalien », format des suggestions).

### 2026-11-27 — Version mobile installable (27 tests + recette navigateur réussis)
- `static/manifest.webmanifest`, `static/sw.js`, `static/icons/` (192, 512, apple-touch-icon 180) ; méta iOS/Android
  dans `index.html`.
- Barre d'onglets mobile, cloche de notifications et pastilles de non-lus, page `#me` (hub Profil + « Installer
  BlablaCook »), dialogues en panneau bas, champs 16 px, zones sûres (encoche), messages hors connexion.
- Vérifié dans Chrome : manifeste sans erreur, service worker actif, aucun critère d'installabilité manquant.
- Test `tests/test_mobile.py`. La vidéo de présentation n'a pas été retournée.

### 2026-11-28 — Finitions visuelles
- En-tête : logo moins serré, menu ordinateur espacé (bug : les liens étaient collés depuis l'ajout du menu
  mobile), menu utilisateur en pastille avec initiale, en-tête collant.
- Accueil connecté : bandeau « Bonjour/Bonsoir, prénom » à la place de la grande bannière (réservée aux visiteurs,
  avec un bouton « Rejoindre ») ; « Pour toi » en carrousel horizontal.
- Cartes : pastilles (ambiance, activité, entre femmes, allergènes incertains), 3 raisons max sans la distance
  (déjà affichée), survol animé. « Mes repas » / « Mes réservations » : date, statut coloré et invités en pastilles.

### 2026-11-28 — Nouvelle identité visuelle (inspirée d'apple.com)
- `app.css` réécrit : typographie système (SF Pro sur Apple), fond #fbfbfd / #f5f5f7, texte #1d1d1f, boutons en
  pilule, cartes blanches très arrondies avec ombres douces, barres translucides floutées, dégradé signature
  safran → paprika → framboise (`--grad`, classe `.grad`). Ancienne palette crème/serif abandonnée.
- Nouveau logo `icon.svg` : bulle de conversation (« Blabla ») contenant un bol fumant (« Cook ») en dégradé ;
  icônes PWA régénérées, couleur de thème #fbfbfd, cache du service worker passé en `blablacook-v2`.
- Accueil visiteur façon page produit : grand titre centré, bannière qui s'élargit au défilement (`heroZoom`),
  grille « bento » de 4 arguments. Accueil connecté : « Bonsoir, prénom. Qu'est-ce qu'on mange ? ».
- Animations (`common.js`) : apparition au défilement (`animateIn`, IntersectionObserver, décalage en cascade),
  transition à chaque changement de page, survol des cartes (zoom photo, flèche), pastilles qui pulsent, onglet
  actif qui rebondit, dialogues en fondu / panneau bas. Tout est désactivé si l'utilisateur demande moins
  d'animations (`prefers-reduced-motion`).

### 2026-11-28 — Brise-glace dans les conversations
- `blablacook/icebreakers.py` : banque de questions (générales + liées au repas : activité, ambiance, langue
  autre que le français, titre du plat ; avant le repas : « qui apporte quoi » en groupe, questions différentes
  côté invité et côté hôte en privé ; après le repas : souvenirs et prochaine table). Deux questions par
  proposition, en alternant contexte et général ; ordre stable par conversation (graine = id du fil),
  `round` pour « Autres idées ».
- Route `GET /api/conversations/{id}/icebreakers?round=n` (membres du fil seulement ; liste vide si lecture seule).
- Interface : encart « Brise-glace » au-dessus du message (ouvert si personne n'a encore écrit, replié en
  « Besoin d'une idée pour relancer ? » sinon) ; un clic ajoute la question au message, sans l'envoyer.
- Tests `tests/test_brise_glace.py`. `test_navigateur.py` tourne désormais avec « réduire les animations »
  (12 s au lieu de 45 s, plus d'attente des transitions).

### 2026-11-28 — Brise-glace plus précis
- Questions construites à partir : du menu (mot-clé → question dédiée : pâtes, carbonara, couscous, galettes…),
  de la présentation PUBLIQUE des autres participants (plats cités, passions, études → question à leur prénom),
  du moment (« Rendez-vous ce soir/demain soir/samedi soir… », heure de Paris), de la taille de la tablée, de
  l'activité, de l'ambiance, de la langue, et des préférences du membre qui écrit, formulées à la 1re personne.
- Les plus personnelles d'abord, en variant les sources ; chaque question porte une indication (`hint`) :
  « Le menu », « D'après la présentation de Hugo », « Le rendez-vous »… La réponse de l'API devient
  `[{text, hint}]`.
- Confidentialité : allergies, régime et préférences des autres participants ne sont jamais utilisés (testé).

### 2026-11-28 — Brise-glace par LLM gratuit + correctif de cache
- Bug « [object Object] » : le navigateur (service worker) servait l'ancien JS. Les CSS/JS sont maintenant
  appelés avec une empreinte (`?v=…`, `app.asset_version()`) qui change à chaque modification ; cache SW `v3`.
- `blablacook/llm.py` : client « chat completions » au format OpenAI (Groq par défaut, `openai/gpt-oss-120b` avec `reasoning_effort: low` ; Gemini, Mistral
  possibles), délai 6 s, cache 6 h par fil/personne/phase/jour, réponse JSON filtrée (`parse`). Décision avec
  l'utilisateur : API gratuite en ligne, LLM + secours par règles.
- Route `/conversations/{id}/icebreakers` sans `Ctx` : lecture en base puis libération du verrou SQLite AVANT
  l'appel réseau ; renvoie `source: "llm" | "rules"` (mention « Idées proposées par une IA » dans l'interface).
- Seules les données publiques sont envoyées (`icebreakers.facts`) : repas, prénoms, présentations publiques.
- Tests : fournisseur simulé (`httpx.MockTransport`) ; `create_app(llm=False)` dans les tests.

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
