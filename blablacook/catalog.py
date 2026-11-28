import hmac

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .access import (MAX_CODE_ATTEMPTS, RESEND_DELAY, Ctx, code_matches, create_once, digest, issue_verification,
                     password_hash, session_info, start_session)
from .db import (Activity, Allergen, Booking, Diet, Language, LoginSession, Meal, Mood, Review, User, label,
                 labels)
from . import recommend
from .imagesearch import DEFAULT_IMAGE, PHOTO_TOKEN
from .domains import student_email
from .geo import distance_km
from .domain import (ACTIVE, Problem, allowed, average, cancel_meal, found, publish, request_place,
                     require, reservations, review, transition)
from .forms import (OPTIONS, Attendance, Login, MealForm, Profile, Registration, ReviewForm, Verification,
                    VerificationCode)
from .views import BookingInfo, PersonalMeal, ReviewInfo, ReviewsInfo, SessionInfo, MealCard, PublicProfile, booking_info, meal_card, private_meal, profile, review_info

class PersonalProfile(Profile):
    id: int
    email: str
    verified: bool
    guest_average: float | None


router = APIRouter()


@router.get("/auth/session", response_model=SessionInfo, response_model_exclude_unset=True)
def session(c: Ctx):
    return session_info(c)


@router.post("/auth/register", response_model=SessionInfo, response_model_exclude_unset=True, status_code=201)
def register(data: Registration, response: Response, tasks: BackgroundTasks, c: Ctx):
    email = data.email.strip().lower()
    require(student_email(email, c.request.app.state.domains), 422, "UNKNOWN_DOMAIN",
            "Utilise ton adresse mail étudiante (université ou école reconnue).")
    require(not c.s.scalar(select(User.id).where(User.email == email)), 409, "EMAIL_EXISTS", "Cette adresse est déjà inscrite.")
    u = User(name=data.name, email=email, password=password_hash(data.password))
    c.s.add(u)
    c.s.flush()
    issue_verification(c, u, tasks)
    return start_session(c, u, response)


def activate(c, u):
    u.verified = True
    u.verification = u.verification_code = u.verification_until = None
    u.verification_attempts = 0


@router.post("/auth/verify-email", response_model=SessionInfo, response_model_exclude_unset=True)
def verify(data: Verification, c: Ctx):
    """Lien reçu par mail : fonctionne aussi depuis un navigateur où l’on n’est pas connecté."""
    u = c.s.scalar(select(User).where(User.verification == digest(data.token), User.verified.is_(False)))
    require(u and c.now < u.verification_until, 403, "INVALID_TOKEN", "Ce lien de vérification est invalide ou a expiré.")
    activate(c, u)
    return session_info(c)


@router.post("/auth/verify-code", response_model=SessionInfo, response_model_exclude_unset=True)
def verify_code(data: VerificationCode, c: Ctx):
    u = c.member(False)
    require(not u.verified, 409, "ALREADY_VERIFIED", "Ton adresse est déjà vérifiée.")
    require(u.verification_code and c.now < u.verification_until, 403, "INVALID_TOKEN", "Ce code a expiré. Demande un nouveau mail.")
    require((u.verification_attempts or 0) < MAX_CODE_ATTEMPTS, 429, "TOO_MANY_ATTEMPTS",
            "Trop d’essais. Demande un nouveau mail de confirmation.")
    if not code_matches(u, data.code):
        u.verification_attempts = (u.verification_attempts or 0) + 1
        # On valide la transaction pour conserver le compteur d’essais malgré l’erreur.
        c.s.commit()
        raise Problem(403, "INVALID_TOKEN", "Code incorrect.")
    activate(c, u)
    return session_info(c)


@router.post("/auth/resend-verification")
def resend(tasks: BackgroundTasks, c: Ctx):
    u = c.member(False)
    require(not u.verified, 409, "ALREADY_VERIFIED", "Ton adresse est déjà vérifiée.")
    wait = (u.verification_sent or 0) + RESEND_DELAY - c.now
    require(wait <= 0, 429, "RESEND_TOO_SOON", f"Patiente {int(wait) + 1} s avant de redemander un mail.")
    issue_verification(c, u, tasks)
    return {"sent": True}


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
    u = c.member(verified=False)
    data = {k: getattr(u, k) for k in Profile.model_fields}
    return {**data, "id": u.id, "email": u.email, "verified": u.verified, "guest_average": average(c.s, u.id, "guest")}


@router.patch("/users/me", response_model=PersonalProfile, response_model_exclude_unset=True)
def edit(data: Profile, c: Ctx):
    u = c.member(verified=False)
    lists = {"allergens": ("allergen_refs", Allergen), "languages": ("language_refs", Language),
             "moods": ("mood_refs", Mood), "activities": ("activity_refs", Activity)}
    for k, value in data.model_dump(exclude_unset=True).items():
        if k in lists:
            attr, model = lists[k]
            setattr(u, attr, labels(c.s, model, value))
        elif k == "diet":
            u.diet_ref = label(c.s, Diet, value)
        else:
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
    return {**OPTIONS, "maps_key": c.request.app.state.maps_key}


@router.get("/meals", response_model=list[MealCard])
def meals(c: Ctx, search: str = "", lat: float | None = Query(None, ge=-90, le=90), lng: float | None = Query(None, ge=-180, le=180),
          distance: float | None = Query(None, ge=0), after: float | None = None,
          before: float | None = None, diet: str = "", allergen: str = "", language: str = "", mood: str = "",
          kind: str = "", activity: str = "", women: bool = False, available: bool = False):
    require(distance is None or (lat is not None and lng is not None), 422, "ORIGIN_REQUIRED",
            "Renseigne ton adresse dans ton profil pour filtrer par distance.")
    q = select(Meal).where(Meal.status == "OPEN", Meal.start > c.now, Meal.hidden.is_(False)).order_by(Meal.start, Meal.id)
    if after is not None:
        q = q.where(Meal.start >= after)
    if before is not None:
        q = q.where(Meal.start < before)
    # Filtres sur les tables de référence, résolus en SQL par les tables de liaison.
    if diet:
        q = q.where(Meal.diet_refs.any(Diet.name == diet))
    if allergen:
        q = q.where(~Meal.allergen_refs.any(Allergen.name == allergen))
    if language:
        q = q.where(Meal.language_refs.any(Language.name == language))
    if mood:
        q = q.where(Meal.mood_ref.has(Mood.name == mood))
    if activity:
        q = q.where(Meal.activity_ref.has(Activity.name == activity))
    if kind:
        q = q.where(Meal.kind == kind)
    if women:
        q = q.where(Meal.women.is_(True))
    out = []
    for m in c.s.scalars(q):
        if distance is not None and distance_km(lat, lng, m.area_lat, m.area_lng) > distance:
            continue
        if search.casefold() not in " ".join([m.title, m.menu, m.description, m.city]).casefold():
            continue
        card = meal_card(c.s, m)
        if not available or card["available"] > 0:
            out.append(card)
    return out


class PhotoSuggestion(BaseModel):
    image: str
    preview: str = ""
    credit: str = ""
    credit_url: str = ""
    found: bool


@router.get("/photos/suggest", response_model=PhotoSuggestion)
def suggest_photo(request: Request, title: str = Query("", max_length=80)):
    """Photo libre de droits pour un titre de repas, ou l’image par défaut.

    Volontairement sans transaction : l’appel réseau à Openverse ne doit pas bloquer la base.
    """
    with Session(request.app.state.engine) as s:
        login = s.get(LoginSession, digest(request.cookies.get("bc_session", "")))
        user = login and login.expires > request.app.state.clock() and s.get(User, login.user_id)
        require(user and user.verified and not user.suspended, 401, "SESSION_REQUIRED", "Connectez-vous pour continuer.")
    search = request.app.state.photo_search
    result = search.search(title) if search else None
    return {**result, "found": True} if result else {"image": DEFAULT_IMAGE, "found": False}


@router.post("/meals", response_model=MealCard, status_code=201)
def create_meal(data: MealForm, c: Ctx):
    u = c.member()
    final, credit = data, ("", "")
    if PHOTO_TOKEN.fullmatch(data.image):
        # Photo déjà téléchargée lors de la suggestion ; si elle a expiré du cache, image par défaut
        # (pas d’appel réseau ici : la transaction est ouverte).
        search = c.request.app.state.photo_search
        photo = search.resolve(data.image) if search else None
        final = data.model_copy(update={"image": photo["preview"] if photo else DEFAULT_IMAGE})
        credit = (photo["credit"], photo["credit_url"]) if photo else ("", "")
    mid = create_once(c, "meal", data, lambda: publish(c.s, u, final, c.now, credit).id)
    return meal_card(c.s, c.s.get(Meal, mid))


class SuggestedMeal(MealCard):
    distance: float | None
    reasons: list[str]


class Suggestions(BaseModel):
    needs_address: bool
    profile_complete: bool
    meals: list[SuggestedMeal]


@router.get("/meals/suggestions", response_model=Suggestions)
def suggestions(c: Ctx):
    """« Pour toi » : repas ouverts compatibles avec le profil (allergies, régime), classés par préférences et distance."""
    u = c.member(verified=False)
    active = select(Booking.meal).where(Booking.guest == u.id, Booking.status.in_(ACTIVE))
    q = select(Meal).where(Meal.status == "OPEN", Meal.start > c.now, Meal.hidden.is_(False), Meal.host != u.id,
                           Meal.id.not_in(active))
    if u.gender != "Femme":
        q = q.where(Meal.women.is_(False))
    out = []
    for m, _, reasons, km in recommend.rank(u, c.s.scalars(q), c.now):
        card = meal_card(c.s, m)
        if card["available"] > 0:
            out.append({**card, "distance": round(km, 1) if km is not None else None, "reasons": reasons})
        if len(out) == recommend.COUNT:
            break
    return {"needs_address": u.home_lat is None, "profile_complete": recommend.profile_complete(u), "meals": out}


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
