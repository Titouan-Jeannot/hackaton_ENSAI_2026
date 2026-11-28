from pathlib import Path

from sqlalchemy import (JSON, Boolean, CheckConstraint, Column, Float, ForeignKey, Index, Integer, String, Table,
                        UniqueConstraint, create_engine, event, inspect, select, text)
from sqlalchemy.orm import DeclarativeBase, Session, relationship

from . import reference

ROOT = Path(__file__).resolve().parent.parent
DEMO_DB = ROOT / "var" / "blablacook-demo.sqlite3"


class Base(DeclarativeBase):
    pass


def pk():
    return Column(Integer, primary_key=True)


def ref(target, **kw):
    return Column(Integer, ForeignKey(target), nullable=False, **kw)


# --- Tables de référence ----------------------------------------------------------------------------------------
# Une ligne par valeur possible, remplies au démarrage depuis blablacook/reference.py (fill_reference).
class Label:
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)


class Allergen(Label, Base):
    __tablename__ = "allergens"


class Diet(Label, Base):
    __tablename__ = "diets"
    for_meal = Column(Boolean, nullable=False, default=False)      # proposé dans le formulaire de repas
    for_profile = Column(Boolean, nullable=False, default=False)   # proposé dans le profil


class Language(Label, Base):
    __tablename__ = "languages"


class Mood(Label, Base):
    __tablename__ = "moods"


class Activity(Label, Base):
    __tablename__ = "activities"


def link(name, owner, target):
    """Table de liaison plusieurs-à-plusieurs : (owner, target) = (« table.colonne », « table.colonne »)."""
    (owner_table, owner_col), (target_table, target_col) = owner.split("."), target.split(".")
    return Table(name, Base.metadata,
                 Column(owner_col, Integer, ForeignKey(owner_table + ".id", ondelete="CASCADE"), primary_key=True),
                 Column(target_col, Integer, ForeignKey(target_table + ".id"), primary_key=True, index=True))


meal_allergens = link("meal_allergens", "meals.meal", "allergens.allergen")
meal_diets = link("meal_diets", "meals.meal", "diets.diet")
meal_languages = link("meal_languages", "meals.meal", "languages.language")
user_allergens = link("user_allergens", "users.user", "allergens.allergen")        # allergies déclarées (privé)
user_languages = link("user_languages", "users.user", "languages.language")        # langues parlées
user_moods = link("user_moods", "users.user", "moods.mood")                        # ambiances préférées
user_activities = link("user_activities", "users.user", "activities.activity")     # activités préférées


def names(rows):
    return [r.name for r in rows]


class DemoBatch(Base):
    __tablename__ = "demo_batch"
    id = pk()
    last_start = Column(Float, nullable=False)


class User(Base):
    __tablename__ = "users"
    id = pk()
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    bio = Column(String, default="")
    photo = Column(String, default="")
    public_photo = Column(Boolean, default=False)
    hidden_guest = Column(Boolean, default=False)
    diet_id = Column(Integer, ForeignKey("diets.id"))   # régime déclaré (liste déroulante du profil)
    allergies = Column(String, default="")             # précisions libres en plus des allergènes cochés
    age = Column(Integer)
    gender = Column(String, default="")
    home_address = Column(String, default="")       # adresse privée, sert aux suggestions proches
    home_lat = Column(Float)
    home_lng = Column(Float)
    verified = Column(Boolean, default=False)
    suspended = Column(Boolean, default=False)
    admin = Column(Boolean, default=False)
    verification = Column(String)          # empreinte sha256 du jeton du lien
    verification_code = Column(String)     # empreinte sha256 du code à 6 chiffres
    verification_until = Column(Float)
    verification_sent = Column(Float)
    verification_attempts = Column(Integer, default=0)
    diet_ref = relationship(Diet)
    allergen_refs = relationship(Allergen, secondary=user_allergens, order_by=Allergen.id)
    language_refs = relationship(Language, secondary=user_languages, order_by=Language.id)
    mood_refs = relationship(Mood, secondary=user_moods, order_by=Mood.id)
    activity_refs = relationship(Activity, secondary=user_activities, order_by=Activity.id)

    @property
    def diet(self):
        return self.diet_ref.name if self.diet_ref else ""

    @property
    def allergens(self):
        return names(self.allergen_refs)

    @property
    def languages(self):
        return names(self.language_refs)

    @property
    def moods(self):
        return names(self.mood_refs)

    @property
    def activities(self):
        return names(self.activity_refs)


class LoginSession(Base):
    __tablename__ = "sessions"
    token = Column(String, primary_key=True)
    user_id = ref("users.id", index=True)
    csrf = Column(String, nullable=False)
    expires = Column(Float, nullable=False)


class Meal(Base):
    __tablename__ = "meals"
    id = pk()
    host = ref("users.id", index=True)
    title = Column(String, nullable=False)
    description = Column(String, default="")
    menu = Column(String, nullable=False)
    ingredients = Column(String, nullable=False)
    uncertain = Column(Boolean, nullable=False)        # allergènes incertains
    mood_id = Column(Integer, ForeignKey("moods.id"), nullable=False)
    kind = Column(String, nullable=False)
    activity_id = Column(Integer, ForeignKey("activities.id"))
    image = Column(String, nullable=False)
    image_credit = Column(String, default="")       # auteur et licence de la photo (photos Openverse)
    image_credit_url = Column(String, default="")
    city = Column(String, default="")              # localité publique (ex. « Rennes »)
    area_lat = Column(Float, nullable=False)        # centre PUBLIC du cercle, décalé du lieu exact
    area_lng = Column(Float, nullable=False)
    area_radius = Column(Integer, nullable=False)   # rayon du cercle public, en mètres
    start = Column(Float, nullable=False, index=True)
    duration = Column(Integer)
    check_at = Column(Float, nullable=False)
    minimum = Column(Integer, nullable=False)
    maximum = Column(Integer, nullable=False)
    women = Column(Boolean, default=False)
    status = Column(String, default="OPEN")
    hidden = Column(Boolean, default=False)
    threshold_warning = Column(Boolean, default=False)
    warning_seq = Column(Integer, default=0)
    __table_args__ = (CheckConstraint("minimum >= 1 AND maximum >= minimum AND check_at < start"),)
    allergen_refs = relationship(Allergen, secondary=meal_allergens, order_by=Allergen.id)
    diet_refs = relationship(Diet, secondary=meal_diets, order_by=Diet.id)
    language_refs = relationship(Language, secondary=meal_languages, order_by=Language.id)
    mood_ref = relationship(Mood)
    activity_ref = relationship(Activity)

    @property
    def allergens(self):
        return names(self.allergen_refs)

    @property
    def diets(self):
        return names(self.diet_refs)

    @property
    def languages(self):
        return names(self.language_refs)

    @property
    def mood(self):
        return self.mood_ref.name

    @property
    def activity(self):
        return self.activity_ref.name if self.activity_ref else ""


class MealCancellation(Base):
    __tablename__ = "meal_cancellations"
    meal = ref("meals.id", primary_key=True)
    actor = ref("users.id")
    created = Column(Float, nullable=False)
    administrative = Column(Boolean, nullable=False)


class WriteReceipt(Base):
    __tablename__ = "write_receipts"
    id = pk()
    actor = ref("users.id")
    key = Column(String, nullable=False)
    resource = Column(String, nullable=False)
    fingerprint = Column(String, nullable=False)
    target = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint("actor", "key"),)


class Address(Base):
    __tablename__ = "addresses"
    meal = ref("meals.id", primary_key=True)
    address = Column(String, nullable=False)
    lat = Column(Float, nullable=False)             # position exacte, jamais publique
    lng = Column(Float, nullable=False)


class Booking(Base):
    __tablename__ = "bookings"
    id = pk()
    meal = ref("meals.id")
    guest = ref("users.id")
    status = Column(String, nullable=False)
    created = Column(Float, nullable=False)
    changed = Column(Float, nullable=False)
    __table_args__ = (
        Index("active_guest_meal", "meal", "guest", unique=True,
              sqlite_where=text("status IN ('PENDING','ACCEPTED')")),
        Index("meal_status", "meal", "status"), Index("guest_status", "guest", "status"))


class Review(Base):
    __tablename__ = "reviews"
    id = pk()
    booking = ref("bookings.id")
    author = Column(Integer, ForeignKey("users.id"))
    recipient = ref("users.id")
    role = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    criteria = Column(JSON)
    comment = Column(String, default="")
    reason = Column(String, default="")
    status = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint("booking", "author"),
                      Index("one_automatic", "booking", unique=True, sqlite_where=text("author IS NULL")))


class Thread(Base):
    """Fil privé (un invité ↔ l’hôte, avant réservation) ou chat de groupe du repas (hôte + invités acceptés)."""
    __tablename__ = "threads"
    id = pk()
    meal = ref("meals.id")
    guest = Column(Integer, ForeignKey("users.id"))  # NULL pour le chat de groupe
    kind = Column(String, nullable=False, default="private")  # private | group
    __table_args__ = (UniqueConstraint("meal", "guest"),
                      Index("one_group_chat", "meal", unique=True, sqlite_where=text("kind = 'group'")),
                      CheckConstraint("(kind = 'group') = (guest IS NULL)"))


class Message(Base):
    __tablename__ = "messages"
    id = pk()
    thread = ref("threads.id")
    author = ref("users.id")
    body = Column(String, nullable=False)
    created = Column(Float, nullable=False)
    hidden = Column(Boolean, default=False)
    system = Column(Boolean, default=False)  # message automatique (arrivée ou départ d’un participant)


class Note(Base):
    __tablename__ = "notifications"
    id = pk()
    user = ref("users.id")
    event_key = Column(String, nullable=False)
    label = Column(String, nullable=False)
    link = Column(String, nullable=False)
    created = Column(Float, nullable=False)
    read = Column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("user", "event_key"),)


class Report(Base):
    __tablename__ = "reports"
    id = pk()
    author = ref("users.id")
    kind = Column(String, nullable=False)
    target = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    comment = Column(String, nullable=False)
    created = Column(Float, nullable=False)
    status = Column(String, default="OPEN")


class Decision(Base):
    __tablename__ = "decisions"
    id = pk()
    report = ref("reports.id")
    moderator = ref("users.id")
    action = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    created = Column(Float, nullable=False)


def database(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine("sqlite:///" + str(path.absolute()), connect_args={"timeout": 10, "check_same_thread": False})

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    check_schema(engine, path)
    fill_reference(engine)
    return engine


REFERENCE = {Allergen: reference.ALLERGENS, Diet: reference.DIETS, Language: reference.LANGUAGES,
             Mood: reference.MOODS, Activity: reference.ACTIVITIES}


def fill_reference(engine):
    """Ajoute les valeurs de référence manquantes (idempotent) et met à jour les drapeaux des régimes."""
    with Session(engine) as s:
        for model, values in REFERENCE.items():
            known = {r.name: r for r in s.scalars(select(model))}
            for name in values:
                row = known.get(name) or model(name=name)
                if model is Diet:
                    row.for_meal, row.for_profile = name in reference.MEAL_DIETS, name in reference.PROFILE_DIETS
                s.add(row)
        s.commit()


def label(s, model, name):
    """Ligne de référence d’après son nom (None pour une valeur vide)."""
    if not name:
        return None
    row = s.scalar(select(model).where(model.name == name))
    if row is None:
        raise ValueError(f"Valeur inconnue : {name}")
    return row


def labels(s, model, values):
    """Lignes de référence, sans doublon, dans l’ordre de la liste de référence."""
    return sorted((label(s, model, v) for v in dict.fromkeys(values)), key=lambda r: r.id)


def meal_labels(s, allergens, diets, languages, mood, activity):
    """Relations d’un repas à partir des noms reçus par l’API."""
    return dict(allergen_refs=labels(s, Allergen, allergens), diet_refs=labels(s, Diet, diets),
                language_refs=labels(s, Language, languages), mood_ref=label(s, Mood, mood),
                activity_ref=label(s, Activity, activity))


class OutdatedSchema(RuntimeError):
    pass


def check_schema(engine, path):
    """Pas d’outil de migration : on refuse clairement une base créée avec une ancienne version du schéma."""
    found = inspect(engine)
    for table in Base.metadata.sorted_tables:
        missing = {c.name for c in table.columns} - {c["name"] for c in found.get_columns(table.name)}
        if missing:
            engine.dispose()
            raise OutdatedSchema(f"La base {path} date d’une ancienne version (colonnes manquantes dans "
                                 f"« {table.name} » : {', '.join(sorted(missing))}). Supprimez ce fichier : "
                                 "il sera recréé et repeuplé au prochain démarrage.")


def transaction(engine):
    session = Session(engine)
    try:
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    except BaseException:
        session.close()
        raise
    return session
