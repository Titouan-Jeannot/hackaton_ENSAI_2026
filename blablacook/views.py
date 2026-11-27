from sqlalchemy import func, select
from pydantic import BaseModel

from .db import Address, Booking, Meal, Review, User
from .domain import ACTIVE, CANCELLATION_LIMIT, DEFAULT_DURATION, REVIEW_WINDOW, average, end, reservations


class PublicProfile(BaseModel):
    id: int
    name: str
    bio: str
    photo: str
    host_average: float | None


class MealCard(BaseModel):
    id: int
    title: str
    description: str
    menu: str
    ingredients: str
    allergens: list[str]
    uncertain: bool
    diets: list[str]
    languages: list[str]
    mood: str
    kind: str
    activity: str
    image: str
    sector: str
    start: float
    end: float
    duration: int | None
    minimum: int
    maximum: int
    women: bool
    status: str
    available: int
    host: PublicProfile


def profile(s, u):
    return dict(id=u.id, name=u.name, bio=u.bio, photo=u.photo if u.public_photo else "", host_average=average(s, u.id, "host"))


def meal_card(s, m):
    fields = ("id", "title", "description", "menu", "ingredients", "allergens", "uncertain", "diets", "languages",
              "mood", "kind", "activity", "image", "sector", "start", "duration", "minimum", "maximum", "women", "status")
    card = {**{k: getattr(m, k) for k in fields}, "end": end(m), "host": profile(s, s.get(User, m.host)),
            "available": m.maximum - len(reservations(s, m, "ACCEPTED"))}
    if m.hidden:
        card.update(title="Annonce masquée", description="", menu="", ingredients="", image="table")
    return card


def review_info(r):
    return {k: getattr(r, k) for k in ("id", "role", "score", "criteria", "comment", "reason", "status")}


def booking_info(c, b):
    s = c.s
    m = s.get(Meal, b.meal)
    mine = s.scalar(select(Review).where(Review.booking == b.id, Review.author == c.user.id))
    other_end = Meal.start + 60 * func.coalesce(Meal.duration, DEFAULT_DURATION)
    overlap = b.status in ACTIVE and bool(s.scalar(
        select(Booking.id).join(Meal, Meal.id == Booking.meal).where(
            Booking.guest == b.guest, Booking.id != b.id, Booking.status.in_(ACTIVE),
            Meal.start < end(m), other_end > m.start
        ).limit(1)
    )) if c.user.id == b.guest else False
    return dict(id=b.id, overlap=overlap, meal=m.id, title="Annonce masquée" if m.hidden else m.title, start=m.start, end=end(m), status=b.status,
                guest=profile(s, s.get(User, b.guest)), host=m.host, meal_status=m.status,
                late=m.start - CANCELLATION_LIMIT < c.now < m.start, before_start=c.now < m.start,
                attendance_open=c.now >= end(m) and m.status == "OPEN" and b.status == "ACCEPTED",
                review_open=b.status == "ATTENDED" and c.now < b.changed + REVIEW_WINDOW and mine is None,
                mine=review_info(mine) if mine else None)


def private_meal(c, m):
    s, uid = c.s, c.user.id
    bookings = reservations(s, m)
    own = next((b for b in reversed(bookings) if b.guest == uid), None)
    is_host = uid == m.host
    confirmed = own is not None and own.status == "ACCEPTED"
    data = dict(meal=meal_card(s, m), booking=booking_info(c, own) if own else None,
                can_request=m.status == "OPEN" and c.now < m.start and not is_host and (not own or own.status not in ACTIVE)
                and (not m.women or c.user.gender == "Femme"),
                can_message=not is_host and not m.hidden and m.status == "OPEN" and c.now < m.start,
                can_cancel=is_host and m.status == "OPEN" and not any(b.status in ("ATTENDED", "NO_SHOW") for b in bookings))
    if is_host or confirmed:
        data["address"] = s.get(Address, m.id).address
        guests = [s.get(User, b.guest) for b in bookings if b.status == "ACCEPTED"]
        data["guests"] = [profile(s, u) for u in guests if is_host or not u.hidden_guest or uid == u.id]
    if is_host:
        data.update(warning=m.threshold_warning, check_at=m.check_at)
    return data


class SessionUser(BaseModel):
    id: int
    name: str
    verified: bool
    admin: bool


class SessionInfo(BaseModel):
    user: SessionUser | None
    csrf: str | None = None
    demo_verification: str | None = None


class ReviewInfo(BaseModel):
    id: int
    role: str
    score: float
    criteria: dict[str, int] | None
    comment: str
    reason: str
    status: str


class ReviewsInfo(BaseModel):
    reviews: list[ReviewInfo]
    host_average: float | None
    guest_average: float | None


class BookingInfo(BaseModel):
    id: int
    meal: int
    title: str
    start: float
    end: float
    status: str
    guest: PublicProfile
    host: int
    meal_status: str
    late: bool
    before_start: bool
    attendance_open: bool
    review_open: bool
    mine: ReviewInfo | None
    overlap: bool = False


class PersonalMeal(BaseModel):
    meal: MealCard
    booking: BookingInfo | None
    can_request: bool
    can_cancel: bool
    can_message: bool
    address: str | None = None
    guests: list[PublicProfile] | None = None
    warning: bool | None = None
    check_at: float | None = None
