from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient

from blablacook.app import create_app
from blablacook.demo import seed
from conftest import accepted, act, book, decide, iso, last_mail, offer, report


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
    assert "demo_verification" not in r and not r["user"]["verified"]
    assert w.client().post("/api/auth/register", json=payload).status_code == 409
    code, token = last_mail(w.app, "member@campus.test")
    assert c.post("/api/auth/verify-code", json={"code": code}).status_code == 403  # sans jeton CSRF
    c.headers["X-CSRF-Token"] = r["csrf"]
    assert c.post(f"/api/meals/{m}/bookings").status_code == 403
    assert c.get("/api/users/me").json()["verified"] is False  # le profil reste accessible
    assert c.post("/api/auth/verify-email", json={"token":"invalid"}).status_code == 403
    assert c.post("/api/auth/verify-code", json={"code": code}).is_success
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
    view = guest.get(p).json()
    assert "address" not in view and "location" not in view
    assert view["address_at"] == view["meal"]["start"] - 3600
    assert w.host.get(p).json()["address"] == "55 rue Privée fictive, Rennes"
    w.clock.now = view["address_at"] - 1
    assert "address" not in guest.get(p).json()
    w.clock.now += 1
    assert guest.get(p).json()["address"] == w.host.get(p).json()["address"]
    assert guest.get(p).json()["location"] == {"lat": 48.1113, "lng": -1.68}
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
    m=w.create(women=True,lat=48.1197,lng=-1.6383,languages=["Anglais"],uncertain=True,allergens=[])
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
    res=gs[2].get("/api/meals?language=Anglais&women=true&allergen=Lait&lat=48.1113&lng=-1.68&distance=4").json()
    assert gs[2].get("/api/meals?lat=48.1113&lng=-1.68&distance=1").json()[0]["id"]!=m
    assert gs[2].get("/api/meals?distance=4").json()["code"]=="ORIGIN_REQUIRED"
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
    other=create_app(w.path,w.clock,photo_search=False)
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
        assert conn.scalar(text("select count(*) from meals"))==16
    assert seed(other,t+11*86400,reset=True)
    with other.connect() as conn:
        assert conn.scalar(text("select count(*) from meals"))==8
        assert conn.scalar(text("select count(*) from users where photo like 'data:image/jpeg%' and bio != '' and home_lat is not null"))==13
    with pytest.raises(ValueError):
        seed(world.app.state.engine,t,reset=True)
    assert world.host.get("/api/users/me").is_success
    other.dispose()


def test_student_domains_and_subdomains(world):
    from blablacook.domains import load_domains, student_email
    domains = load_domains("campus.test")
    assert student_email("alice@ensai.fr", domains) and student_email("alice@eleve.ensai.fr", domains)
    assert student_email("bob@etudiant.univ-rennes.fr", domains)
    for bad in ("bob@gmail.com", "bob@fakeensai.fr", "bob@ensai.fr.evil.com", "pas-une-adresse", "a@b@ensai.fr"):
        assert not student_email(bad, domains), bad
    c = world.client()
    r = c.post("/api/auth/register", json=dict(email="x@gmail.com", password="abcdefgh", name="X"))
    assert r.status_code == 422 and r.json()["code"] == "UNKNOWN_DOMAIN"


def test_email_confirmation_link_code_attempts_and_resend(world):
    w = world
    c = w.client()
    r = c.post("/api/auth/register", json=dict(email="Zoe@Campus.test", password="abcdefgh", name="Zoé"))
    assert r.status_code == 201
    c.headers["X-CSRF-Token"] = r.json()["csrf"]
    mail = w.app.state.mailer.outbox[-1]
    assert mail["to"] == "zoe@campus.test" and "Zoé" in mail["text"]
    code, token = last_mail(w.app, "zoe@campus.test")
    wrong = "000000" if code != "000000" else "111111"
    # Un renvoi trop rapide est refusé.
    assert c.post("/api/auth/resend-verification").status_code == 429
    for _ in range(5):
        assert c.post("/api/auth/verify-code", json={"code": wrong}).status_code == 403
    assert c.post("/api/auth/verify-code", json={"code": code}).json()["code"] == "TOO_MANY_ATTEMPTS"
    w.clock.now += 61
    assert c.post("/api/auth/resend-verification").is_success
    new_code, new_token = last_mail(w.app, "zoe@campus.test")
    assert new_token != token
    # L’ancien lien ne fonctionne plus ; le nouveau marche même depuis un navigateur non connecté.
    other = w.client()
    assert other.post("/api/auth/verify-email", json={"token": token}).status_code == 403
    assert other.post("/api/auth/verify-email", json={"token": new_token}).json()["user"] is None
    assert c.get("/api/auth/session").json()["user"]["verified"]
    assert other.post("/api/auth/verify-email", json={"token": new_token}).status_code == 403
    # Le lien expire après 24 h.
    c2 = w.client()
    r = c2.post("/api/auth/register", json=dict(email="late@campus.test", password="abcdefgh", name="Late"))
    _, token = last_mail(w.app, "late@campus.test")
    w.clock.now += 24*3600
    assert c2.post("/api/auth/verify-email", json={"token": token}).status_code == 403
    with w.app.state.engine.connect() as conn:
        from sqlalchemy import text
        stored = conn.execute(text("select verification from users where email='late@campus.test'")).scalar()
    assert stored and stored != token  # seule l’empreinte est stockée


def test_profile_diet_dropdown(world):
    h = world.host
    assert "Halal" in world.client().get("/api/catalog/options").json()["profile_diets"]
    assert h.patch("/api/users/me", json={"diet": "Végétalien"}).json()["diet"] == "Végétalien"
    assert h.patch("/api/users/me", json={"diet": "végé"}).status_code == 422
    assert h.patch("/api/users/me", json={"diet": ""}).json()["diet"] == ""


def test_public_area_hides_exact_location(world):
    from blablacook.geo import distance_km
    w = world
    ids = [w.create() for _ in range(5)]
    visitor = w.client()
    centers = set()
    for mid in ids:
        card = visitor.get(f"/api/meals/{mid}").json()
        area = card["area"]
        assert area["radius"] == 500 and card["city"] == "Rennes"
        # Le lieu exact est dans le cercle, mais n’en est pas le centre.
        assert distance_km(48.1113, -1.68, area["lat"], area["lng"]) * 1000 <= 0.7 * 500 + 1
        centers.add((area["lat"], area["lng"]))
    assert (48.1113, -1.68) not in centers and len(centers) == 5
    for route in ["/api/meals", f"/api/meals/{ids[0]}"]:
        assert "48.1113" not in visitor.get(route).text and "-1.68," not in visitor.get(route).text
    assert w.host.post("/api/meals", json=offer(w.clock, lat=None)).status_code == 422


def test_home_address_is_private(world):
    w = world
    h = w.host
    assert h.patch("/api/users/me", json={"home_address": "1 rue X, Rennes"}).status_code == 422
    r = h.patch("/api/users/me", json={"home_address": "1 rue X, Rennes", "home_lat": 48.11, "home_lng": -1.67})
    assert r.json()["home_address"] == "1 rue X, Rennes"
    assert "rue X" not in w.client().get("/api/users/1").text


UUID = "9dbcbca1-a7e6-4437-8621-4a7e7c05248c"


class FakeOpenverse:
    """Client HTTP factice : répond comme l’API Openverse et sert les vignettes, sans appel réseau."""
    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, timeout=None, params=None, follow_redirects=True):
        import httpx
        from io import BytesIO
        from PIL import Image
        assert headers["User-Agent"].startswith("BlablaCook")
        request = httpx.Request("GET", url)
        if params is None:  # téléchargement d’une vignette
            self.calls.append(url)
            buffer = BytesIO()
            Image.new("RGB", (600, 449), "orange").save(buffer, "JPEG")
            return httpx.Response(200, content=buffer.getvalue(), request=request)
        self.calls.append(params["q"])
        assert params["license_type"] == "commercial,modification" and params["mature"] == "false"
        if params["q"] == "panne":
            raise httpx.ConnectError("hors ligne")
        hit = {"id": UUID, "title": "Lasagne FTW", "tags": [], "creator": "Ada Cuisine", "license": "by",
               "license_version": "2.0", "foreign_landing_url": "https://www.flickr.com/photos/ada/1",
               "thumbnail": f"https://api.openverse.org/v1/images/{UUID}/thumb/"}
        results = {"lasagne": [{**hit, "id": "11111111-1111-1111-1111-111111111111", "title": "Hors sujet"}, hit],
                   "piege": [{**hit, "thumbnail": "https://evil.example/x.jpg"}]}.get(params["q"], [])
        return httpx.Response(200, json={"results": results}, request=request)


def test_automatic_meal_photo(world):
    from blablacook.imagesearch import OpenverseSearch, queries
    w = world
    assert queries("Soupe au potiron & quiz") == ["soup pumpkin", "soup", "soupe au potiron quiz"]
    assert queries("Lasagnes de l’internat")[0] == "lasagne" and queries("Pois chiches rôtis")[0] == "chickpeas"
    fake = FakeOpenverse()
    clock = [0]
    none = {"image": "table", "preview": "", "credit": "", "credit_url": "", "found": False}
    assert w.host.get("/api/photos/suggest?title=Lasagnes").json() == none   # recherche désactivée
    w.app.state.photo_search = OpenverseSearch(client=fake, clock=lambda: clock[0])
    assert w.client().get("/api/photos/suggest?title=Lasagnes").status_code == 401
    r = w.host.get("/api/photos/suggest?title=  Lasagnes !").json()
    assert r["found"] and r["image"] == f"openverse:{UUID}"                 # le résultat pertinent est préféré
    assert r["credit"] == "Ada Cuisine · CC BY 2.0" and r["credit_url"] == "https://www.flickr.com/photos/ada/1"
    assert r["preview"].startswith("data:image/jpeg;base64,")             # vignette téléchargée et réencodée
    assert all(c.startswith("https://api.openverse.org/") for c in fake.calls if c.startswith("http"))
    calls = len(fake.calls)
    w.host.get("/api/photos/suggest?title=lasagnes")
    assert len(fake.calls) == calls                                        # cache de 24 h
    clock[0] += 24*3600
    w.host.get("/api/photos/suggest?title=lasagnes")
    assert len(fake.calls) > calls                                         # cache expiré
    assert w.host.get("/api/photos/suggest?title=plat introuvable").json()["image"] == "table"
    assert w.host.get("/api/photos/suggest?title=panne").json()["image"] == "table"
    assert w.host.get("/api/photos/suggest?title=piege").json()["image"] == "table"  # hôte non autorisé refusé
    # Publication : l’image stockée est la copie locale, avec son attribution.
    card = w.client().get(f"/api/meals/{w.create(title='Lasagnes', image=r['image'])}").json()
    assert card["image"] == r["preview"] and card["image_credit"] == "Ada Cuisine · CC BY 2.0"
    assert "openverse.org" not in w.client().get("/api/meals").text
    unknown = "openverse:00000000-0000-0000-0000-000000000000"
    assert w.client().get(f"/api/meals/{w.create(image=unknown)}").json()["image"] == "table"  # jeton inconnu
    assert w.client().get(f"/api/meals/{w.create(image='')}").json()["image"] == "table"
    assert w.host.post("/api/meals", json=offer(w.clock, image="https://api.openverse.org/x.jpg")).status_code == 422


def test_suggestions_near_home(world):
    w = world
    near = w.create(title="Tout près")                                   # Rennes centre
    far = w.create(title="Bruz", lat=48.0466, lng=-1.7428)             # ~8 km
    w.create(title="Paris", lat=48.8566, lng=2.3522)                    # hors rayon
    women = w.create(title="Entre femmes", women=True)
    full = w.create(title="Complet", maximum=1)
    g = w.member("guest", gender="Homme")
    accepted(w, w.member("other"), full)
    first = g.get("/api/meals/suggestions").json()
    assert first["needs_address"] and not first["profile_complete"]
    assert {m["title"] for m in first["meals"]} == {"Tout près", "Bruz", "Paris"}  # sans adresse : pas de distance
    g.patch("/api/users/me", json={"home_address": "Place de la Mairie, Rennes", "home_lat": 48.1115, "home_lng": -1.6795})
    titles = [m["title"] for m in g.get("/api/meals/suggestions").json()["meals"]]
    assert titles == ["Tout près", "Bruz"]  # triées par distance, sans repas inaccessible, complet ou lointain
    book(g, near)
    assert [m["id"] for m in g.get("/api/meals/suggestions").json()["meals"]] == [far]
    assert w.client().get("/api/meals/suggestions").status_code == 401


def test_accepted_guests_join_meal_group_chat(world):
    w = world
    m = w.create(maximum=3)
    g1, g2, outsider = w.member("guest1"), w.member("guest2"), w.member("outsider")
    b1 = book(g1, m)
    assert w.host.get(f"/api/meals/{m}/personal").json()["group_thread"] is None
    assert act(w.host, b1, "accept").is_success
    chat = g1.get(f"/api/meals/{m}/personal").json()["group_thread"]
    assert chat and w.host.get(f"/api/meals/{m}/personal").json()["group_thread"] == chat
    assert any(n["link"] == f"#thread/{chat}" for n in g1.get("/api/notifications/me").json())
    path = f"/api/conversations/{chat}/messages"
    view = g1.get(path).json()
    assert view["group"] and view["members"] == ["hote", "guest1"]
    assert view["messages"][0]["system"] and "guest1 a rejoint" in view["messages"][0]["body"]
    b2 = book(g2, m)
    assert g2.get(path).status_code == 404               # demande en attente : pas encore dans le chat
    assert act(w.host, b2, "accept").is_success
    assert g2.post(path, json={"body": "Salut tout le monde !"}).status_code == 201
    for c in (w.host, g1):
        assert any(n["label"].startswith("Nouveau message") for n in c.get("/api/notifications/me").json())
        assert any(t["id"] == chat and t["group"] for t in c.get("/api/conversations/me").json())
    assert outsider.get(path).status_code == 404 and outsider.post(path, json={"body": "x"}).status_code == 404
    assert act(g1, b1, "cancel").is_success                # un invité qui annule quitte le chat
    assert g1.get(path).status_code == 404
    assert "guest1 a quitté" in g2.get(path).json()["messages"][-1]["body"]
    # Un fil privé et le chat de groupe coexistent pour le même repas.
    private = g2.post("/api/conversations", json={"meal": m}).json()
    assert not private["group"] and private["id"] != chat
    assert w.host.post(f"/api/meals/{m}/cancel").is_success
    assert g2.get(path).json()["readonly"]


def test_profile_lists_are_normalized(world):
    from sqlalchemy import text
    h = world.host
    r = h.patch("/api/users/me", json={"allergens": ["Lait", "Gluten", "Lait"], "languages": ["Anglais"],
                                       "moods": ["Festive"], "activities": ["Quiz"], "allergies": "Kiwi"}).json()
    assert r["allergens"] == ["Gluten", "Lait"] and r["moods"] == ["Festive"] and r["allergies"] == "Kiwi"
    assert h.patch("/api/users/me", json={"allergens": ["Chocolat"]}).status_code == 422
    assert h.patch("/api/users/me", json={"moods": ["Bruyante"]}).status_code == 422
    m = world.create(allergens=["Lait", "Soja"], diets=["Végétarien", "Halal"], languages=["Français", "Anglais"],
                     kind="Repas + activité", activity="Quiz", mood="Festive")
    card = h.get(f"/api/meals/{m}").json()
    assert card["allergens"] == ["Soja", "Lait"] and card["diets"] == ["Végétarien", "Halal"]
    assert card["activity"] == "Quiz" and card["mood"] == "Festive"
    with world.app.state.engine.connect() as c:
        assert c.execute(text("select count(*) from meal_allergens where meal = :m"), {"m": m}).scalar() == 2
        assert c.execute(text("select count(*) from user_allergens")).scalar() == 2
        assert c.execute(text("select count(*) from allergens")).scalar() == 14
    # Les filtres du catalogue passent par les tables de liaison.
    assert [x["id"] for x in h.get("/api/meals?diet=Halal").json()] == [m]
    assert m not in [x["id"] for x in h.get("/api/meals?allergen=Soja").json()]
    assert [x["id"] for x in h.get("/api/meals?activity=Quiz&mood=Festive&language=Anglais").json()] == [m]


def test_suggestions_follow_profile(world):
    w = world
    plain = w.create(title="Soupe", allergens=["Céleri"], diets=["Végétarien"])
    nuts = w.create(title="Gâteau aux noix", allergens=["Fruits à coque"], diets=["Végétarien"])
    unsure = w.create(title="Mystère", allergens=[], uncertain=True, diets=["Végétalien"])
    meat = w.create(title="Bœuf bourguignon", allergens=["Sulfites"], diets=["Aucun régime particulier"])
    games = w.create(title="Curry & jeux", allergens=["Moutarde"], diets=["Végétalien", "Halal"],
                     kind="Repas + activité", activity="Jeux de société", mood="Conviviale")
    g = w.member("gourmande")

    def titles():
        return [m["title"] for m in g.get("/api/meals/suggestions").json()["meals"]]

    assert set(titles()) == {"Soupe", "Gâteau aux noix", "Mystère", "Bœuf bourguignon", "Curry & jeux"}
    g.patch("/api/users/me", json={"allergens": ["Fruits à coque"]})
    assert set(titles()) == {"Soupe", "Bœuf bourguignon", "Curry & jeux"}     # allergène et incertain écartés
    g.patch("/api/users/me", json={"diet": "Végétarien"})
    assert set(titles()) == {"Soupe", "Curry & jeux"}                         # régime respecté (végétalien inclus)
    g.patch("/api/users/me", json={"diet": "Halal", "activities": ["Jeux de société"], "moods": ["Conviviale"]})
    data = g.get("/api/meals/suggestions").json()
    assert [m["title"] for m in data["meals"]][0] == "Curry & jeux"           # préférences : en tête
    assert {"Halal", "Jeux de société", "Ambiance conviviale"} <= set(data["meals"][0]["reasons"])
    g.patch("/api/users/me", json={"diet": "Sans gluten", "allergens": [], "activities": [], "moods": []})
    assert "Mystère" not in titles()                                           # sans gluten : allergènes certains
    g.patch("/api/users/me", json={"home_address": "Rennes", "home_lat": 48.1113, "home_lng": -1.68})
    assert g.get("/api/meals/suggestions").json()["profile_complete"]
    assert {plain, nuts, meat, games} >= {m["id"] for m in g.get("/api/meals/suggestions").json()["meals"]}
    assert unsure not in [m["id"] for m in g.get("/api/meals/suggestions").json()["meals"]]

