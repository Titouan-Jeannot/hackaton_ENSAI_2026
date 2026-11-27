from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert

from .db import Address, Booking, Meal, MealCancellation, Note, Review, User

ACTIVE = ("PENDING", "ACCEPTED")
HOUR = 3600
CANCELLATION_LIMIT = 5 * HOUR
REVIEW_WINDOW = 7 * 24 * HOUR
DEFAULT_DURATION = 90


class Problem(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def require(condition, status=409, code="INVALID_STATE", message="Cette action est indisponible dans cet état."):
    if not condition:
        raise Problem(status, code, message)


def found(value):
    require(value is not None, 404, "NOT_FOUND", "Cet élément est introuvable.")
    return value


def allowed(condition):
    require(condition, 403, "FORBIDDEN", "Vous ne pouvez pas effectuer cette action.")


def end(meal):
    return meal.start + (meal.duration or DEFAULT_DURATION) * 60


def reservations(s, meal, *states):
    q = select(Booking).where(Booking.meal == meal.id)
    if states:
        q = q.where(Booking.status.in_(states))
    return s.scalars(q.order_by(Booking.id)).all()


def notify(s, user, key, label, link, now):
    s.execute(insert(Note).values(user=user, event_key=key, label=label, link=link, created=now)
              .on_conflict_do_nothing(index_elements=["user", "event_key"]))


def refresh(s, meal, now):
    if meal.status != "OPEN":
        return
    if now >= meal.start:
        for b in reservations(s, meal, "PENDING"):
            b.status, b.changed = "EXPIRED", now
    count = len(reservations(s, meal, "ACCEPTED"))
    short = meal.check_at <= now < meal.start and count < meal.minimum
    if short and not meal.threshold_warning:
        meal.warning_seq += 1
        notify(s, meal.host, f"min-{meal.id}-{meal.warning_seq}", "Le minimum d’invités reste à atteindre.", "#host", now)
    meal.threshold_warning = short
    if now >= end(meal):
        if count:
            notify(s, meal.host, f"close-{meal.id}", "Les présences d’un repas sont à renseigner.", "#host", now)
        else:
            meal.status = "COMPLETED"


def maintain(s, now):
    for meal in s.scalars(select(Meal).where(Meal.status == "OPEN")).all():
        refresh(s, meal, now)
    due = select(Booking.id).where(Booking.status == "ATTENDED", Booking.changed <= now - REVIEW_WINDOW)
    for rev in s.scalars(select(Review).where(Review.status == "WAITING", Review.booking.in_(due))):
        rev.status = "PUBLISHED"


def eligible(s, meal, guest):
    member = s.get(User, guest)
    require(member.verified and not member.suspended and (not meal.women or member.gender == "Femme"),
            403, "NOT_ELIGIBLE", "Ce compte ne remplit pas les conditions de ce repas.")


def future(meal, now):
    require(meal.status == "OPEN" and not meal.hidden and now < meal.start, 409, "MEAL_CLOSED", "Ce repas est fermé aux demandes.")


def publish(s, user, data, now):
    require(data.start.timestamp() > now, 422, "INVALID_DATE", "Choisissez un début dans le futur.")
    allowed(not data.women or user.gender == "Femme")
    meal = Meal(host=user.id, **data.model_dump(exclude={"start", "check_at", "address"}),
                start=data.start.timestamp(), check_at=data.check_at.timestamp())
    s.add(meal)
    s.flush()
    s.add(Address(meal=meal.id, address=data.address))
    refresh(s, meal, now)
    return meal


def request_place(s, meal, guest, now):
    future(meal, now)
    allowed(meal.host != guest)
    eligible(s, meal, guest)
    duplicate = s.scalar(select(Booking.id).where(Booking.meal == meal.id, Booking.guest == guest, Booking.status.in_(ACTIVE)))
    require(not duplicate, 409, "BOOKING_ALREADY_ACTIVE", "Vous avez déjà une demande active pour ce repas.")
    b = Booking(meal=meal.id, guest=guest, status="PENDING", created=now, changed=now)
    s.add(b)
    s.flush()
    notify(s, meal.host, f"request-{b.id}", "Une nouvelle demande de place est arrivée.", "#host", now)
    return b


def penalty(s, booking, reason):
    s.add(Review(booking=booking.id, recipient=booking.guest, role="guest", score=1,
                 reason=reason, status="PUBLISHED"))


def transition(s, b, actor, action, now):
    m = s.get(Meal, b.meal)
    allowed(actor == (b.guest if action == "cancel" else m.host))
    if action in ("accept", "reject"):
        future(m, now)
        require(b.status == "PENDING")
        if action == "accept":
            eligible(s, m, b.guest)
            require(len(reservations(s, m, "ACCEPTED")) < m.maximum, 409, "MEAL_FULL", "Toutes les places de ce repas sont confirmées.")
        state = "ACCEPTED" if action == "accept" else "REJECTED"
        label = "Votre réservation est confirmée." if action == "accept" else "Votre demande a été refusée."
        notify(s, b.guest, f"{action}-{b.id}", label, "#bookings", now)
    elif action == "cancel":
        future(m, now)
        require(b.status in ACTIVE)
        state = "WITHDRAWN" if b.status == "PENDING" else "CANCELLED_BY_GUEST"
        if state == "CANCELLED_BY_GUEST" and m.start - now < CANCELLATION_LIMIT:
            penalty(s, b, "Annulation tardive")
        notify(s, m.host, f"cancel-{b.id}", "Un invité a annulé sa participation.", "#host", now)
    else:
        require(m.status == "OPEN" and now >= end(m) and b.status == "ACCEPTED")
        state = "ATTENDED" if action == "present" else "NO_SHOW"
        if state == "NO_SHOW":
            penalty(s, b, "Absence déclarée")
        notify(s, b.guest, f"presence-{b.id}", "Votre présence a été renseignée.", "#bookings", now)
    b.status, b.changed = state, now
    refresh(s, m, now)


def cancel_meal(s, meal, now, moderator=None):
    require(meal.status == "OPEN")
    if moderator is None:
        require(not reservations(s, meal, "ATTENDED", "NO_SHOW"), message="Les présences ont déjà commencé.")
    s.add(MealCancellation(meal=meal.id, actor=moderator or meal.host, created=now, administrative=moderator is not None))
    meal.status, meal.threshold_warning = "CANCELLED", False
    for b in reservations(s, meal):
        if b.status in ACTIVE:
            b.status, b.changed = ("ADMIN_CLOSED" if moderator is not None else "CANCELLED_BY_HOST"), now
            notify(s, b.guest, f"meal-cancel-{b.id}", "Le repas a été annulé.", "#bookings", now)
        for rev in s.scalars(select(Review).where(Review.booking == b.id, Review.author.is_(None))):
            rev.status = "NEUTRALIZED"


def review(s, b, actor, data, now):
    meal = s.get(Meal, b.meal)
    allowed(actor in (meal.host, b.guest))
    require(b.status == "ATTENDED")
    require(now < b.changed + REVIEW_WINDOW, 409, "REVIEW_WINDOW_CLOSED", "La période de dépôt des avis est terminée.")
    existing = s.scalars(select(Review).where(Review.booking == b.id)).all()
    require(all(r.author != actor for r in existing), message="Vous avez déjà déposé un avis.")
    scores = {key: getattr(data, key) for key in ("accueil", "ambiance", "repas")}
    about_host = actor == b.guest
    valid = (all(scores.values()) and data.global_score is None) if about_host else (not any(scores.values()) and data.global_score is not None)
    require(valid, 422, "INVALID_RATING", "Vérifiez les critères de l’avis.")
    new = Review(booking=b.id, author=actor, recipient=meal.host if about_host else b.guest,
                 role="host" if about_host else "guest", score=sum(scores.values()) / 3 if about_host else data.global_score,
                 criteria=scores if about_host else None, comment=data.comment, status="PUBLISHED" if existing else "WAITING")
    for r in existing:
        if r.status == "WAITING":
            r.status = "PUBLISHED"
    s.add(new)
    s.flush()
    return new


def average(s, user, role):
    score = s.scalar(select(func.avg(Review.score)).where(Review.recipient == user, Review.role == role, Review.status == "PUBLISHED"))
    return round(score, 2) if score is not None else None
