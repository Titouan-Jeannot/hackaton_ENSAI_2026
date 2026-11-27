import hmac
import math
import re

from fastapi import APIRouter, Query, Response
from sqlalchemy import select

from .access import Ctx, create_once, password_hash, session_info, start_session
from .db import Booking, Meal, Review, User
from .domain import (allowed, average, cancel_meal, found, publish, request_place,
                     require, reservations, review, transition)
from .forms import (OPTIONS, SECTORS, Attendance, Login, MealForm, Profile, Registration, ReviewForm, Verification)
from .views import BookingInfo, PersonalMeal, ReviewInfo, ReviewsInfo, SessionInfo, MealCard, PublicProfile, booking_info, meal_card, private_meal, profile, review_info

class PersonalProfile(Profile):
    id: int
    email: str
    guest_average: float | None


router = APIRouter()


@router.get("/auth/session", response_model=SessionInfo, response_model_exclude_unset=True)
def session(c: Ctx):
    return session_info(c)


@router.post("/auth/register", response_model=SessionInfo, response_model_exclude_unset=True, status_code=201)
def register(data: Registration, response: Response, c: Ctx):
    email = data.email.strip().lower()
    require(c.request.app.state.demo, 403, "DEMO_ONLY", "La vérification locale est désactivée.")
    require(re.fullmatch(r"[^@\s]+@[^@\s]+", email) and email.rsplit("@", 1)[1] in c.request.app.state.domains,
            422, "UNKNOWN_DOMAIN", "Utilisez une adresse d’un campus reconnu.")
    require(not c.s.scalar(select(User.id).where(User.email == email)), 409, "EMAIL_EXISTS", "Cette adresse est déjà inscrite.")
    u = User(name=data.name, email=email, password=password_hash(data.password))
    c.s.add(u)
    c.s.flush()
    return start_session(c, u, response)


@router.post("/auth/verify-email", response_model=SessionInfo, response_model_exclude_unset=True)
def verify(data: Verification, c: Ctx):
    u = c.member(False)
    require(c.request.app.state.demo and not u.verified and u.verification and c.now < u.verification_until
            and hmac.compare_digest(data.token.encode(), u.verification.encode()), 403, "INVALID_TOKEN", "Le lien de vérification a expiré.")
    u.verified, u.verification, u.verification_until = True, None, None
    return session_info(c)


@router.post("/auth/login", response_model=SessionInfo, response_model_exclude_unset=True)
def login(data: Login, response: Response, c: Ctx):
    u = c.s.scalar(select(User).where(User.email == data.email.strip().lower()))
    require(u and not u.suspended and hmac.compare_digest(u.password, password_hash(data.password, u.password.split(":")[0])),
            401, "LOGIN_FAILED", "Adresse ou mot de passe incorrect.")
    return start_session(c, u, response)


@router.post("/auth/logout", response_model=SessionInfo, response_model_exclude_unset=True)
def logout(response: Response, c: Ctx):
    c.member(False)
    c.s.delete(c.login)
    response.delete_cookie("bc_session")
    return {"user": None}


@router.get("/users/me", response_model=PersonalProfile, response_model_exclude_unset=True)
def me(c: Ctx):
    u = c.member()
    return {**{k: getattr(u, k) for k in Profile.model_fields}, "id": u.id, "email": u.email, "guest_average": average(c.s, u.id, "guest")}


@router.patch("/users/me", response_model=PersonalProfile, response_model_exclude_unset=True)
def edit(data: Profile, c: Ctx):
    u = c.member()
    for k, value in data.model_dump(exclude_unset=True).items():
        setattr(u, k, value)
    return me(c)


@router.get("/users/{uid}", response_model=PublicProfile)
def public_profile(uid: int, c: Ctx):
    u = found(c.s.get(User, uid))
    found(None if u.suspended else u)
    return profile(c.s, u)


@router.get("/users/{uid}/reviews", response_model=ReviewsInfo, response_model_exclude_unset=True)
def reviews(uid: int, c: Ctx):
    public_profile(uid, c)
    q = select(Review).where(Review.recipient == uid, Review.status == "PUBLISHED")
    # Les évaluations d’invité sont destinées au membre et aux hôtes auprès desquels il a candidaté.
    guest_access = c.user and (uid == c.user.id or c.s.scalar(select(Booking.id).join(Meal, Meal.id == Booking.meal)
                       .where(Meal.host == c.user.id, Booking.guest == uid)))
    if not guest_access:
        q = q.where(Review.role == "host")
    return {"reviews": [review_info(r) for r in c.s.scalars(q.order_by(Review.id.desc()))],
            "host_average": average(c.s, uid, "host"), "guest_average": average(c.s, uid, "guest") if guest_access else None}


@router.get("/catalog/options")
def options(c: Ctx):
    return {**OPTIONS, "sectors": SECTORS, "domains": sorted(c.request.app.state.domains)}


@router.get("/meals", response_model=list[MealCard])
def meals(c: Ctx, search: str = "", sector: str = "", distance: float | None = Query(None, ge=0), after: float | None = None,
          before: float | None = None, diet: str = "", allergen: str = "", language: str = "", mood: str = "",
          kind: str = "", activity: str = "", women: bool = False, available: bool = False):
    require(not sector or sector in SECTORS, 422, "INVALID_SECTOR", "Secteur inconnu.")
    require(distance is None or sector, 422, "ORIGIN_REQUIRED", "Choisissez le secteur de départ.")
    q = select(Meal).where(Meal.status == "OPEN", Meal.start > c.now, Meal.hidden.is_(False)).order_by(Meal.start, Meal.id)
    if after is not None:
        q = q.where(Meal.start >= after)
    if before is not None:
        q = q.where(Meal.start < before)
    out = []
    for m in c.s.scalars(q):
        if sector and math.dist(SECTORS[sector], SECTORS[m.sector]) > (distance or 0):
            continue
        if search.casefold() not in " ".join([m.title, m.menu, m.description, m.sector]).casefold():
            continue
        if diet and diet not in m.diets or allergen and allergen in m.allergens or language and language not in m.languages:
            continue
        if mood and m.mood != mood or kind and m.kind != kind or activity and m.activity != activity or women and not m.women:
            continue
        card = meal_card(c.s, m)
        if not available or card["available"] > 0:
            out.append(card)
    return out


@router.post("/meals", response_model=MealCard, status_code=201)
def create_meal(data: MealForm, c: Ctx):
    u = c.member()
    mid = create_once(c, "meal", data, lambda: publish(c.s, u, data, c.now).id)
    return meal_card(c.s, c.s.get(Meal, mid))


@router.get("/meals/mine", response_model=list[PersonalMeal], response_model_exclude_unset=True)
def host_meals(c: Ctx):
    u = c.member()
    return [private_meal(c, m) for m in c.s.scalars(select(Meal).where(Meal.host == u.id).order_by(Meal.start.desc()))]


@router.get("/meals/{mid}", response_model=MealCard)
def detail(mid: int, c: Ctx):
    m = found(c.s.get(Meal, mid))
    found(m if m.status == "OPEN" and not m.hidden and c.now < m.start else None)
    return meal_card(c.s, m)


@router.get("/meals/{mid}/personal", response_model=PersonalMeal, response_model_exclude_unset=True)
def personal(mid: int, c: Ctx):
    u = c.member()
    m = found(c.s.get(Meal, mid))
    involved = u.id == m.host or c.s.scalar(select(Booking.id).where(Booking.meal == mid, Booking.guest == u.id))
    found(m if involved or (m.status == "OPEN" and not m.hidden and c.now < m.start) else None)
    return private_meal(c, m)


@router.post("/meals/{mid}/cancel")
def cancel(mid: int, c: Ctx):
    u = c.member()
    m = found(c.s.get(Meal, mid))
    allowed(m.host == u.id)
    cancel_meal(c.s, m, c.now)
    return {"status": m.status}


@router.get("/meals/{mid}/bookings", response_model=list[BookingInfo], response_model_exclude_unset=True)
def candidates(mid: int, c: Ctx):
    u = c.member()
    m = found(c.s.get(Meal, mid))
    allowed(u.id == m.host)
    return [booking_info(c, b) for b in reservations(c.s, m)]


@router.post("/meals/{mid}/bookings", response_model=BookingInfo, response_model_exclude_unset=True, status_code=201)
def book(mid: int, c: Ctx):
    uid = c.member().id
    b = request_place(c.s, found(c.s.get(Meal, mid)), uid, c.now)
    return booking_info(c, b)


@router.get("/bookings/me", response_model=list[BookingInfo], response_model_exclude_unset=True)
def bookings(c: Ctx):
    uid = c.member().id
    return [booking_info(c, b) for b in c.s.scalars(
        select(Booking).where(Booking.guest == uid).order_by(Booking.id.desc())
    )]


def update(c, bid, action):
    uid = c.member().id
    b = found(c.s.get(Booking, bid))
    transition(c.s, b, uid, action, c.now)
    return booking_info(c, b)


@router.post("/bookings/{bid}/accept", response_model=BookingInfo, response_model_exclude_unset=True)
def accept(bid: int, c: Ctx):
    return update(c, bid, "accept")


@router.post("/bookings/{bid}/reject", response_model=BookingInfo, response_model_exclude_unset=True)
def reject(bid: int, c: Ctx):
    return update(c, bid, "reject")


@router.post("/bookings/{bid}/cancel", response_model=BookingInfo, response_model_exclude_unset=True)
def withdraw(bid: int, c: Ctx):
    return update(c, bid, "cancel")


@router.post("/bookings/{bid}/attendance", response_model=BookingInfo, response_model_exclude_unset=True)
def attendance(bid: int, data: Attendance, c: Ctx):
    return update(c, bid, "present" if data.present else "absent")


@router.post("/bookings/{bid}/reviews", response_model=ReviewInfo, response_model_exclude_unset=True, status_code=201)
def post_review(bid: int, data: ReviewForm, c: Ctx):
    uid = c.member().id
    return review_info(review(c.s, found(c.s.get(Booking, bid)), uid, data, c.now))
