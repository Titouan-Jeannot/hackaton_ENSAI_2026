from pathlib import Path

from sqlalchemy import (Boolean, CheckConstraint, Column, Float, ForeignKey, Index, Integer,
                        JSON, String, UniqueConstraint, create_engine, event, inspect, text)
from sqlalchemy.orm import DeclarativeBase, Session

ROOT = Path(__file__).resolve().parent.parent
DEMO_DB = ROOT / "var" / "blablacook-demo.sqlite3"


class Base(DeclarativeBase):
    pass


def pk():
    return Column(Integer, primary_key=True)


def ref(target, **kw):
    return Column(Integer, ForeignKey(target), nullable=False, **kw)


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
    diet = Column(String, default="")
    allergies = Column(String, default="")
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
    allergens = Column(JSON, nullable=False)
    uncertain = Column(Boolean, nullable=False)
    diets = Column(JSON, nullable=False)
    languages = Column(JSON, nullable=False)
    mood = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    activity = Column(String, nullable=False)
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
    return engine


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
