from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient

from blablacook.app import create_app
from blablacook.demo import seed
from conftest import accepted, act, book, decide, iso, offer, report


def test_v01_accounts_and_sessions(world):
    w = world
    c = w.client()
    assert c.get("/api/meals").status_code == 200
    m = w.create()
    assert c.post("/api/meals", json=offer(w.clock)).status_code == 401
    assert c.post(f"/api/meals/{m}/bookings").status_code == 401
    assert c.post("/api/conversations", json={"meal": m}).status_code == 401
    payload = dict(email="member@outside.test", password="abcdefgh", name="Élise")
    assert c.post("/api/auth/register", json=payload).status_code == 422
    payload["email"] = " MEMBER@CAMPUS.TEST "
    r = c.post("/api/auth/register", json=payload).json()
    assert w.client().post("/api/auth/register", json=payload).status_code == 409
    assert c.post("/api/auth/verify-email", json={"token":r["demo_verification"]}).status_code == 403
    c.headers["X-CSRF-Token"] = r["csrf"]
    assert c.post(f"/api/meals/{m}/bookings").status_code == 403
    assert c.post("/api/auth/verify-email", json={"token":"invalid"}).status_code == 403
    assert c.post("/api/auth/verify-email", json={"token":r["demo_verification"]}).is_success
    old = c.cookies.get("bc_session")
    assert c.post("/api/auth/logout").is_success
    c.cookies.set("bc_session", old)
    assert c.get("/api/users/me").status_code == 401


def test_v02_private_address(world):
    w = world
    m = w.create()
    guest, other, visitor = w.member("guest"), w.member("other"), w.client()
    p = f"/api/meals/{m}/personal"
    b = book(guest, m)
    for route in ["/", "/api/meals", f"/api/meals/{m}", "/api/users/1"]:
        for c in (visitor, guest, other):
            assert "rue Privée" not in c.get(route).text
    assert "address" not in guest.get(p).json()
    assert "address" not in other.get(p).json()
    assert visitor.get(p).status_code == 401
    assert act(other,b,"accept").status_code == 403
    assert act(w.host,b,"accept").is_success
    assert guest.get(p).json()["address"] == w.host.get(p).json()["address"]
    assert "no-store" in guest.get(p).headers["cache-control"]
    assert "address" not in other.get(p).json()
    assert "address" not in guest.get(f"/api/meals/{m}").json()
    assert act(guest,b,"cancel").is_success
    assert "address" not in guest.get(p).json()
    assert "rue Privée" not in guest.get("/api/notifications/me").text


def test_v03_immutable_publication(world):
    w = world
    m = w.create()
    w.create(kind="Repas + activité", activity="Film")
    for invalid in [dict(minimum=3), dict(check_at=iso(w.clock.now+20*3600)),dict(duration=-1),
                    dict(kind="Repas + activité"),dict(allergens=[]),dict(start=iso(w.clock.now-1))]:
        assert w.host.post("/api/meals",json=offer(w.clock,**invalid)).status_code == 422
    assert w.host.patch(f"/api/meals/{m}",json={"title":"autre"}).status_code == 405
    assert w.host.post(f"/api/meals/{m}/bookings").status_code == 403
    assert w.host.post(f"/api/meals/{m}/cancel").is_success
    assert w.client().get(f"/api/meals/{m}").status_code == 404


def test_v04_v05_last_seat(world):
    w = world
    m = w.create()
    gs = [w.member("guest"+str(n)) for n in range(4)]
    first = accepted(w,gs[0],m)
    ids = [book(g,m) for g in gs[1:3]]
    barrier = Barrier(2)

    def accept(bid):
        c = w.client()
        c.cookies.update(w.host.cookies)
        c.headers["X-CSRF-Token"] = w.host.headers["X-CSRF-Token"]
        barrier.wait(timeout=5)
        return act(c,bid,"accept")

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(accept,ids))
    assert sorted(r.status_code for r in results) == [200,409]
    loser = next(i for i,r in zip(ids,results) if r.status_code==409 and r.json()["code"]=="MEAL_FULL")
    assert w.host.get(f"/api/meals/{m}").json()["available"] == 0
    fourth = book(gs[3],m)
    assert gs[3].post(f"/api/meals/{m}/bookings").json()["code"] == "BOOKING_ALREADY_ACTIVE"
    assert act(w.host,loser,"accept").status_code == 409
    assert act(gs[0],first,"cancel").is_success
    assert act(w.host,fourth,"accept").is_success
    assert w.host.get(f"/api/meals/{m}").json()["available"] == 0


def test_v06_overlaps(world):
    w=world
    g=w.member("guest")
    for _ in range(2):
        accepted(w,g,w.create())
    assert all(row["overlap"] and row["status"]=="ACCEPTED" for row in g.get("/api/bookings/me").json())


def test_v07_threshold_reactivates(world):
    w=world
    m=w.create(minimum=3,maximum=3)
    gs=[w.member("p"+str(i)) for i in range(3)]
    accepted(w,gs[0],m)
    accepted(w,gs[1],m)
    b=book(gs[2],m)
    path=f"/api/meals/{m}/personal"
    assert not w.host.get(path).json()["warning"]
    w.clock.now+=3600
    assert w.host.get(path).json()["warning"]
    assert act(w.host,b,"accept").is_success
    assert not w.host.get(path).json()["warning"]
    assert act(gs[2],b,"cancel").is_success
    assert w.host.get(path).json()["warning"]
    assert len([n for n in w.host.get("/api/notifications/me").json() if "minimum" in n["label"]])==2


def test_v08_exact_cutoffs_and_neutralisation(world):
    w=world
    g=w.member("guest")
    m=w.create()
    b=accepted(w,g,m)
    uid=g.get("/api/users/me").json()["id"]
    path=f"/api/users/{uid}/reviews"
    w.clock.now+=5*3600
    assert act(g,b,"cancel").is_success
    assert g.get(path).json()["guest_average"] is None
    b=accepted(w,g,m)
    w.clock.now+=1
    assert act(g,b,"cancel").is_success
    assert act(g,b,"cancel").status_code==409
    assert len(g.get(path).json()["reviews"])==1
    assert g.get(path).json()["guest_average"]==1
    assert act(g,book(g,m),"cancel").is_success
    assert w.host.post(f"/api/meals/{m}/cancel").is_success
    assert g.get(path).json()["guest_average"] is None
    mid=w.create()
    bid=book(g,mid)
    w.clock.now+=10*3600
    assert act(w.host,bid,"accept").status_code==409
    assert g.get("/api/bookings/me").json()[0]["status"]=="EXPIRED"


def test_v09_presence_and_closure(world):
    w=world
    m=w.create()
    g,g2=w.member("guest"),w.member("guest2")
    b,b2=accepted(w,g,m),accepted(w,g2,m)
    w.clock.now+=10*3600+90*60
    assert g.get("/api/users/me").json()["guest_average"] is None
    assert act(w.host,b,"attendance",present=False).is_success
    assert w.host.post(f"/api/meals/{m}/cancel").status_code==409
    assert act(w.host,b,"attendance",present=False).status_code==409
    assert act(g,b,"reviews",accueil=5,ambiance=5,repas=5).status_code==409
    assert g.get("/api/users/me").json()["guest_average"]==1
    assert act(w.host,b2,"attendance",present=True).is_success
    p=g2.get(f"/api/meals/{m}/personal").json()
    assert p["meal"]["status"]=="COMPLETED" and "address" not in p


def test_v10_blind_reviews(world):
    w=world
    m=w.create()
    g,g2=w.member("guest"),w.member("guest2")
    b,b2=accepted(w,g,m),accepted(w,g2,m)
    w.clock.now+=12*3600
    for bid in (b,b2):
        assert act(w.host,bid,"attendance",present=True).is_success
    assert act(g,b,"reviews",global_score=4).status_code==422
    assert act(g,b,"reviews",accueil=5,ambiance=4,repas=3).json()["status"]=="WAITING"
    assert w.host.get("/api/users/1/reviews").json()["host_average"] is None
    assert act(w.host,b,"reviews",global_score=3).json()["status"]=="PUBLISHED"
    assert w.host.get("/api/users/1/reviews").json()["host_average"]==4
    assert act(g2,b2,"reviews",accueil=2,ambiance=2,repas=2).is_success
    w.clock.now+=7*86400-1
    assert w.host.get("/api/users/1/reviews").json()["host_average"]==4
    w.clock.now+=1
    assert w.host.get("/api/users/1/reviews").json()["host_average"]==3
    assert act(w.host,b2,"reviews",global_score=4).json()["code"]=="REVIEW_WINDOW_CLOSED"


def test_v11_filters_eligibility_and_guest_visibility(world):
    w=world
    m=w.create(women=True,sector="Beaulieu",languages=["Anglais"],uncertain=True,allergens=[])
    w.create()
    gs=[w.member("guest"+str(i),gender) for i,gender in enumerate(["Femme","Femme",""])]
    assert gs[2].post(f"/api/meals/{m}/bookings").status_code==403
    b=book(gs[0],m)
    gs[0].patch("/api/users/me",json={"gender":"Homme"})
    assert act(w.host,b,"accept").status_code==403
    gs[0].patch("/api/users/me",json={"gender":"Femme","hidden_guest":True})
    assert act(w.host,b,"accept").is_success
    accepted(w,gs[1],m)
    url=f"/api/meals/{m}/personal"
    assert len(w.host.get(url).json()["guests"])==2
    assert len(gs[1].get(url).json()["guests"])==1
    res=gs[2].get("/api/meals?language=Anglais&women=true&allergen=Lait&sector=Centre&distance=4").json()
    assert len(res)==1 and res[0]["id"]==m and res[0]["uncertain"]
    assert gs[2].get("/api/meals?language=Anglais&available=true").json()==[]


def test_v12_private_threads_and_reports(world):
    w=world
    m=w.create()
    g,x=w.member("guest"),w.member("other")
    t=g.post("/api/conversations",json={"meal":m}).json()["id"]
    path=f"/api/conversations/{t}/messages"
    msg=g.post(path,json={"body":"À quelle heure ?"}).json()["id"]
    assert w.host.get(path).json()["messages"][0]["id"]==msg
    assert x.get(path).status_code==404
    assert x.post("/api/reports",json=dict(kind="message",target=msg,reason="Autre")).status_code==404
    rid=report(w.host,"message",msg)
    assert decide(g,rid,"masquer").status_code==403
    admin=w.member("admin",admin=True)
    assert decide(admin,rid,"masquer").is_success
    assert not g.get(path).json()["messages"]
    assert w.host.post(f"/api/meals/{m}/cancel").is_success
    assert g.get(path).json()["readonly"]
    assert g.post(path,json={"body":"Nouveau"}).status_code==409


def test_v13_moderation_and_audit(world):
    w=world
    m=w.create()
    g,admin=w.member("guest"),w.member("admin",admin=True)
    r=report(g,"meal",m)
    assert decide(admin,r,"instruire").is_success
    assert decide(admin,r,"classer").json()["status"]=="CLOSED"
    assert len(admin.get(f"/api/admin/reports/{r}").json()["audit"])==2
    b=accepted(w,g,m)
    w.clock.now+=6*3600
    assert act(g,b,"cancel").is_success
    uid=g.get("/api/users/me").json()["id"]
    rv=g.get(f"/api/users/{uid}/reviews").json()["reviews"][0]["id"]
    rid=report(g,"review",rv)
    assert decide(admin,rid,"neutraliser").json()["audit"][0]["moderator"]=="admin"
    assert g.get("/api/users/me").json()["guest_average"] is None
    b=accepted(w,g,m)
    r=report(w.host,"user",uid)
    assert decide(admin,r,"suspendre").is_success
    assert g.get("/api/users/me").status_code==401
    assert w.host.get(f"/api/meals/{m}/bookings").json()[-1]["status"]=="ADMIN_CLOSED"
    assert w.host.get(f"/api/meals/{m}").json()["available"]==2


def test_v14_restart_and_idempotent_seed(world):
    w=world
    g=w.member("guest")
    mid=w.create()
    accepted(w,g,mid)
    other=create_app(w.path,w.clock)
    with TestClient(other) as c:
        c.cookies.update(g.cookies)
        assert c.get("/api/users/me").json()["name"]=="guest"
        assert c.get(f"/api/meals/{mid}/personal").json()["booking"]["status"]=="ACCEPTED"
    assert seed(other.state.engine,w.clock.now) is False
    other.state.engine.dispose()


def test_admin_hides_review_and_suspends_host(world):
    w=world
    guest,admin=w.member("guest"),w.member("admin",admin=True)
    past=w.create()
    bid=accepted(w,guest,past)
    w.clock.now+=12*3600
    assert act(w.host,bid,"attendance",present=True).is_success
    rid=act(guest,bid,"reviews",accueil=5,ambiance=5,repas=5).json()["id"]
    assert act(w.host,bid,"reviews",global_score=5).is_success
    assert decide(admin,report(guest,"review",rid),"masquer").is_success
    assert guest.get("/api/users/1/reviews").json()["host_average"] is None
    m=w.create()
    accepted(w,guest,m)
    assert decide(admin,report(guest,"user",1),"suspendre").is_success
    assert w.host.get("/api/users/me").status_code==401
    view=guest.get(f"/api/meals/{m}/personal").json()
    assert view["meal"]["status"]=="CANCELLED" and "address" not in view
    assert view["booking"]["status"]=="ADMIN_CLOSED"


def test_report_replay_photo_privacy_and_hidden_meal(world):
    import base64
    from io import BytesIO
    from PIL import Image

    w=world
    guest,admin=w.member("guest"),w.member("admin",admin=True)
    img=BytesIO()
    Image.new("RGB",(256,256),"red").save(img,"PNG")
    upload="data:image/png;base64,"+base64.b64encode(img.getvalue()).decode()
    assert w.host.patch("/api/users/me",json={"photo":upload}).is_success
    assert guest.get("/api/users/1").json()["photo"]==""
    assert w.host.patch("/api/users/me",json={"public_photo":True}).is_success
    assert guest.get("/api/users/1").json()["photo"].startswith("data:image/jpeg;base64,")
    assert w.host.patch("/api/users/me",json={"photo":"data:image/png;base64,xxxx"}).status_code==422
    m=w.create(image=upload)
    accepted(w,guest,m)
    guest.headers["Idempotency-Key"]="meme-formulaire"
    r=report(guest,"meal",m)
    assert report(guest,"meal",m)==r
    assert decide(admin,r,"masquer").is_success
    assert guest.get(f"/api/meals/{m}").status_code==404
    assert guest.get(f"/api/meals/{m}/personal").json()["meal"]["title"]=="Annonce masquée"


def test_demo_refresh_and_safe_reset(tmp_path,world):
    import pytest
    from blablacook.db import database
    from sqlalchemy import text

    other=database(tmp_path/"demo.sqlite3")
    t=world.clock.now
    assert seed(other,t)
    assert not seed(other,t)
    assert seed(other,t+10*86400)
    with other.connect() as conn:
        assert conn.scalar(text("select count(*) from meals"))==10
    assert seed(other,t+11*86400,reset=True)
    with other.connect() as conn:
        assert conn.scalar(text("select count(*) from meals"))==5
    with pytest.raises(ValueError):
        seed(world.app.state.engine,t,reset=True)
    assert world.host.get("/api/users/me").is_success
    other.dispose()
