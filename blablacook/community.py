from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import delete, select, update

from .access import Ctx, create_once
from .catalog import reviews
from .db import Booking, Decision, LoginSession, Meal, Message, Note, Report, Review, Thread, User
from .domain import ACTIVE, GROUP_MEMBERS, allowed, cancel_meal, found, future, group_members, notify, refresh, require
from .forms import OPTIONS, DecisionForm, MessageForm, ReportForm, ThreadForm

class ThreadInfo(BaseModel):
    id: int
    meal: int
    title: str
    other: str
    readonly: bool
    group: bool = False
    members: list[str] = []


class MessageInfo(BaseModel):
    id: int
    author: str
    mine: bool
    body: str
    created: float
    system: bool = False


class Messages(ThreadInfo):
    messages: list[MessageInfo]


class NotificationInfo(BaseModel):
    id: int
    label: str
    link: str
    read: bool
    created: float


class Created(BaseModel):
    id: int


class NewReport(Created):
    status: str


class ReportInfo(NewReport):
    kind: str
    target: int
    reason: str
    comment: str
    created: float


class AuditInfo(BaseModel):
    moderator: str
    action: str
    reason: str
    created: float


class ReportDetail(ReportInfo):
    content: str
    actions: list[str]
    audit: list[AuditInfo]


router = APIRouter()


def members(c, t):
    m = c.s.get(Meal, t.meal)
    return group_members(c.s, m) if t.kind == "group" else [m.host, t.guest]


def thread_view(c, t):
    m = c.s.get(Meal, t.meal)
    title = "Annonce masquée" if m.hidden else m.title
    if t.kind == "group":
        names = [c.s.get(User, uid).name for uid in members(c, t)]
        return dict(id=t.id, meal=m.id, title=title, other="Chat du repas", readonly=m.status == "CANCELLED",
                    group=True, members=names)
    other = c.s.get(User, t.guest if c.user.id == m.host else m.host)
    return dict(id=t.id, meal=m.id, title=title, other=other.name,
                readonly=m.status == "CANCELLED" or other.suspended)


def access_thread(c, tid):
    uid = c.member().id
    t = found(c.s.get(Thread, tid))
    return found(t if uid in members(c, t) else None)


@router.post("/conversations", response_model=ThreadInfo)
def create_thread(data: ThreadForm, c: Ctx):
    uid = c.member().id
    m = found(c.s.get(Meal, data.meal))
    allowed(uid != m.host)
    t = c.s.scalar(select(Thread).where(Thread.guest == uid, Thread.meal == m.id, Thread.kind == "private"))
    if not t:
        future(m, c.now)
        t = Thread(guest=uid, meal=m.id)
        c.s.add(t)
        c.s.flush()
    return thread_view(c, t)


@router.get("/conversations/me", response_model=list[ThreadInfo])
def threads(c: Ctx):
    uid = c.member().id
    joined = select(Booking.meal).where(Booking.guest == uid, Booking.status.in_(GROUP_MEMBERS))
    mine = (Thread.kind == "private") & ((Thread.guest == uid) | (Meal.host == uid))
    group = (Thread.kind == "group") & ((Meal.host == uid) | Thread.meal.in_(joined))
    return [thread_view(c, t) for t in c.s.scalars(select(Thread).join(Meal, Thread.meal == Meal.id)
            .where(mine | group).order_by(Thread.id.desc()))]


@router.get("/conversations/{tid}/messages", response_model=Messages)
def messages(tid: int, c: Ctx):
    t = access_thread(c, tid)
    return {**thread_view(c, t), "messages": [dict(id=m.id, author=c.s.get(User, m.author).name, mine=m.author == c.user.id,
            body=m.body, created=m.created, system=bool(m.system)) for m in c.s.scalars(select(Message).where(Message.thread == tid,
            Message.hidden.is_(False)).order_by(Message.id))]}


@router.post("/conversations/{tid}/read")
def read_thread(tid: int, c: Ctx) -> dict[str, bool]:
    access_thread(c, tid)
    c.s.execute(update(Note).where(Note.user == c.user.id, Note.link == f"#thread/{tid}").values(read=True))
    return {"read": True}


@router.post("/conversations/{tid}/messages", response_model=Created, status_code=201)
def send(tid: int, data: MessageForm, c: Ctx):
    t = access_thread(c, tid)
    require(not thread_view(c, t)["readonly"], message="Cette conversation est en lecture seule.")
    def create():
        m = Message(thread=tid, author=c.user.id, body=data.body, created=c.now)
        c.s.add(m)
        c.s.flush()
        label = "Nouveau message dans le chat du repas." if t.kind == "group" else "Vous avez reçu un message."
        for uid in members(c, t):
            if uid != c.user.id:
                notify(c.s, uid, f"msg-{m.id}", label, f"#thread/{tid}", c.now)
        return m.id

    return {"id": create_once(c, f"thread/{tid}", data, create)}


@router.get("/notifications/me", response_model=list[NotificationInfo])
def notes(c: Ctx):
    uid = c.member().id
    return [dict(id=n.id, label=n.label, link=n.link, read=n.read, created=n.created) for n in
            c.s.scalars(select(Note).where(Note.user == uid).order_by(Note.id.desc()))]


@router.post("/notifications/{nid}/read")
def read(nid: int, c: Ctx):
    uid = c.member().id
    n = found(c.s.scalar(select(Note).where(Note.user == uid, Note.id == nid)))
    n.read = True
    return {"read": True}


TARGETS = {"meal": Meal, "user": User, "message": Message, "review": Review}


def visible_target(c, kind, tid):
    target = found(c.s.get(TARGETS[kind], tid))
    if kind == "meal":
        related = target.host == c.user.id or c.s.scalar(select(Booking.id).where(Booking.meal == tid, Booking.guest == c.user.id))
        found(target if not target.hidden and (related or target.status == "OPEN" and c.now < target.start) else None)
    elif kind == "user":
        found(None if target.suspended else target)
    elif kind == "message":
        access_thread(c, target.thread)
        found(None if target.hidden else target)
    elif kind == "review":
        found(next((r for r in reviews(target.recipient, c)["reviews"] if r["id"] == tid), None))
    return target


@router.post("/reports", response_model=NewReport, status_code=201)
def report(data: ReportForm, c: Ctx):
    uid = c.member().id
    visible_target(c, data.kind, data.target)
    require(data.reason in OPTIONS["reasons"], 422, "INVALID_REASON", "Choisissez un motif.")
    def create():
        r = Report(author=uid, created=c.now, **data.model_dump())
        c.s.add(r)
        c.s.flush()
        return r.id

    rid = create_once(c, "report", data, create)
    return {"id": rid, "status": c.s.get(Report, rid).status}


def report_info(r):
    return {k: getattr(r, k) for k in ("id", "kind", "target", "reason", "comment", "created", "status")}


@router.get("/admin/reports", response_model=list[ReportInfo])
def queue(c: Ctx):
    c.admin()
    return [report_info(r) for r in c.s.scalars(select(Report).order_by(Report.id.desc()))]


@router.get("/admin/reports/{rid}", response_model=ReportDetail)
def case(rid: int, c: Ctx):
    c.admin()
    r = found(c.s.get(Report, rid))
    t = c.s.get(TARGETS[r.kind], r.target)
    actions = ["instruire", "classer"]
    if r.kind == "user":
        content = t.name + " · " + t.bio
        if not t.admin and not t.suspended:
            actions.append("suspendre")
    elif r.kind == "meal":
        content = " · ".join([t.title, t.description, t.menu, t.ingredients])
        if not t.hidden:
            actions.append("masquer")
    elif r.kind == "message":
        content = t.body
        if not t.hidden:
            actions.append("masquer")
    else:
        content = f"{t.score:g} ★ · {t.reason or t.comment}"
        if t.status == "PUBLISHED":
            actions.append("masquer")
        if t.author is None and t.status != "NEUTRALIZED":
            actions.append("neutraliser")
    return {**report_info(r), "content": content, "actions": actions if r.status != "CLOSED" else [],
            "audit": [dict(moderator=c.s.get(User, d.moderator).name, action=d.action, reason=d.reason, created=d.created)
                      for d in c.s.scalars(select(Decision).where(Decision.report == rid).order_by(Decision.id))]}


def suspend(c, u):
    u.suspended = True
    c.s.execute(delete(LoginSession).where(LoginSession.user_id == u.id))
    for m in c.s.scalars(select(Meal).where(Meal.host == u.id, Meal.status == "OPEN")).all():
        cancel_meal(c.s, m, c.now, moderator=c.user.id)
    for b in c.s.scalars(select(Booking).where(Booking.guest == u.id, Booking.status.in_(ACTIVE))).all():
        b.status, b.changed = "ADMIN_CLOSED", c.now
        m = c.s.get(Meal, b.meal)
        notify(c.s, m.host, f"suspended-{b.id}", "Une participation a été fermée par la modération.", "#host", c.now)
        refresh(c.s, m, c.now)


@router.post("/admin/reports/{rid}/decisions", response_model=ReportDetail)
def decide(rid: int, data: DecisionForm, c: Ctx):
    admin = c.admin()
    current = case(rid, c)
    require(data.action in current["actions"] and not (data.action == "instruire" and current["status"] == "IN_PROGRESS"))
    r = c.s.get(Report, rid)
    target = c.s.get(TARGETS[r.kind], r.target)
    if data.action == "masquer":
        if r.kind == "review":
            target.status = "HIDDEN"
        else:
            target.hidden = True
            if r.kind == "meal" and target.status == "OPEN":
                cancel_meal(c.s, target, c.now, moderator=c.user.id)
    elif data.action == "neutraliser":
        target.status = "NEUTRALIZED"
    elif data.action == "suspendre":
        suspend(c, target)
    r.status = "IN_PROGRESS" if data.action == "instruire" else "CLOSED"
    c.s.add(Decision(report=rid, moderator=admin.id, action=data.action, reason=data.reason, created=c.now))
    return case(rid, c)
