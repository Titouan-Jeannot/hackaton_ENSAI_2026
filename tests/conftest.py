import re
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from blablacook.app import create_app
from blablacook.db import User, transaction
from blablacook.mailer import ConsoleMailer


class Clock:
    now = datetime(2026, 2, 1, 10, tzinfo=UTC).timestamp()

    def __call__(self):
        return self.now


def iso(t):
    return datetime.fromtimestamp(t, UTC).isoformat()


def last_mail(app, email):
    """Dernier mail envoyé à cette adresse : (code à 6 chiffres, jeton du lien)."""
    mail = next(m for m in reversed(app.state.mailer.outbox) if m["to"] == email.strip().lower())
    return re.search(r"\b(\d{6})\b", mail["text"]).group(1), re.search(r"#verify/([\w-]+)", mail["text"]).group(1)


def offer(clock, **updates):
    data = dict(title="Table de test", menu="Soupe", ingredients="Pois et crème", allergens=["Lait"],
                lat=48.1113, lng=-1.6800, city="Rennes", address="55 rue Privée fictive, Rennes", start=iso(clock.now+10*3600),
                check_at=iso(clock.now+3600), minimum=1, maximum=2)
    return data | updates


@pytest.fixture
def world(tmp_path):
    clock = Clock()
    path = tmp_path / "recette.sqlite3"
    app = create_app(path, clock, mailer=ConsoleMailer(echo=False), photo_search=False, llm=False)
    clients = []

    def client():
        c = TestClient(app)
        clients.append(c)
        return c

    def member(name, gender="Femme", admin=False):
        c = client()
        r = c.post("/api/auth/register", json={"name": name, "email": name+"@campus.test", "password":"MotDeDémo26"})
        assert r.status_code == 201, r.text
        d = r.json()
        c.headers["X-CSRF-Token"] = d["csrf"]
        code, _ = last_mail(app, name+"@campus.test")
        assert c.post("/api/auth/verify-code", json={"code": code}).is_success
        assert c.patch("/api/users/me", json={"gender":gender}).is_success
        if admin:
            with transaction(app.state.engine) as s:
                s.get(User, d["user"]["id"]).admin = True
                s.commit()
        return c

    h = member("hote")

    def create(**updates):
        r = h.post("/api/meals", json=offer(clock, **updates))
        assert r.status_code == 201, r.text
        return r.json()["id"]

    yield SimpleNamespace(clock=clock, app=app, path=path, host=h, client=client, member=member, create=create)
    for c in clients:
        c.close()
    app.state.engine.dispose()


def book(c, mid):
    r = c.post(f"/api/meals/{mid}/bookings")
    assert r.status_code == 201, r.text
    return r.json()["id"]


def act(c, bid, name, **data):
    return c.post(f"/api/bookings/{bid}/{name}", json=data) if data else c.post(f"/api/bookings/{bid}/{name}")


def accepted(w, guest, mid):
    b = book(guest, mid)
    assert act(w.host, b, "accept").is_success
    return b


def report(c, kind, target):
    r = c.post("/api/reports", json=dict(kind=kind, target=target, reason="Information erronée"))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def decide(c, rid, action):
    return c.post(f"/api/admin/reports/{rid}/decisions", json=dict(action=action, reason="Vérification manuelle"))
