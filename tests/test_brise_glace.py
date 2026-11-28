"""Brise-glace : questions précises (menu, présentation publique, moment), sans rien révéler de privé."""
from conftest import accepted


def ice(c, tid, round=0):
    r = c.get(f"/api/conversations/{tid}/icebreakers?round={round}")
    assert r.status_code == 200, r.text
    return r.json()["questions"]


def pool(c, tid, rounds=12):
    return {q["text"]: q["hint"] for r in range(rounds) for q in ice(c, tid, r)}


def test_icebreakers_are_precise(world):
    w = world
    w.host.patch("/api/users/me", json={"bio": "En master de statistique, mes lasagnes sont célèbres."})
    m = w.create(title="Couscous du vendredi", menu="Couscous aux légumes, thé à la menthe",
                 kind="Repas + activité", activity="Quiz", mood="Festive", languages=["Français", "Anglais"])
    guest = w.member("curieuse")
    guest.patch("/api/users/me", json={"bio": "Fan de jeux de société.", "activities": ["Film"]})
    tid = guest.post("/api/conversations", json={"meal": m}).json()["id"]
    first = ice(guest, tid)
    assert len(first) == 2 and first == ice(guest, tid) and ice(guest, tid, 1) != first
    assert first[0]["hint"] in ("Le menu", "D’après la présentation d’hote")   # le plus personnel d’abord
    seen = pool(guest, tid)
    assert seen["Couscous : avec ou sans raisins secs ? Le grand débat !"] == "Le menu"
    assert "hote, tu dis que tes lasagnes sont célèbres : c’est quoi le secret ?" in seen
    assert "hote, tu étudies la statistique : qu’est-ce qui te plaît le plus là-dedans ?" in seen
    assert "Ton thème de quiz imbattable, c’est quoi ?" in seen
    assert any(t.startswith("Rendez-vous ") for t in seen)
    assert "Et si on lançait un film après le repas ? J’ai quelques idées." in seen   # ses propres préférences
    assert "Je peux apporter quelque chose pour le repas ?" in seen
    host_seen = pool(w.host, tid)
    assert "curieuse, c’est quoi ton jeu de société fétiche ?" in host_seen          # bio publique de l’invitée
    assert "Et si on lançait un film après le repas ? J’ai quelques idées." not in host_seen  # préférence privée
    assert "Qu’est-ce qui t’a donné envie de venir à cette table ?" in host_seen
    assert w.member("intrus").get(f"/api/conversations/{tid}/icebreakers").status_code == 404
    assert w.client().get(f"/api/conversations/{tid}/icebreakers").status_code == 401


def test_private_data_never_used(world):
    w = world
    m = w.create(title="Gratin", menu="Gratin de légumes", ingredients="Pommes de terre, crème")
    guest = w.member("discrete")
    guest.patch("/api/users/me", json={"allergens": ["Lait"], "diet": "Halal", "moods": ["Tranquille"],
                                       "allergies": "Kiwi", "activities": ["Quiz"]})
    tid = guest.post("/api/conversations", json={"meal": m}).json()["id"]
    text = " ".join(pool(w.host, tid)).lower()
    for secret in ("lait", "halal", "kiwi", "quiz", "allerg", "tranquille"):
        assert secret not in text


def test_icebreakers_in_group_chat_and_after_meal(world):
    w = world
    m = w.create(title="Pasta al pomodoro", menu="Rigatoni, tomates")
    guest = w.member("invitee")
    accepted(w, guest, m)
    gid = guest.get(f"/api/meals/{m}/personal").json()["group_thread"]
    before = pool(guest, gid)
    assert "On sera 2 à table : qui apporte quoi ? Dessert, boisson, pain… ?" in before
    assert "Pâtes : team al dente ou bien cuites ?" in before
    meal = guest.get(f"/api/meals/{m}/personal").json()["meal"]
    w.clock.now = meal["end"] + 60
    after = pool(guest, gid)
    assert "« Pasta al pomodoro » : verdict ? Tu le referais chez toi ?" in after
    assert "Quel a été ton moment préféré de la soirée ?" in after and not any("Rendez-vous" in t for t in after)
    other = w.create()                                                     # fil en lecture seule : aucune question
    tid = guest.post("/api/conversations", json={"meal": other}).json()["id"]
    assert w.host.post(f"/api/meals/{other}/cancel").is_success
    assert ice(guest, tid) == []


def test_llm_icebreakers_with_fallback(tmp_path):
    """LLM simulé (aucun appel réseau) : questions générées, cache, secours si panne, rien de privé envoyé."""
    import json

    import httpx
    from fastapi.testclient import TestClient

    from blablacook.app import create_app
    from blablacook.llm import LLM, parse
    from blablacook.mailer import ConsoleMailer
    from conftest import Clock, last_mail, offer

    sent, state = [], {"down": False}

    def provider(request):
        sent.append(json.loads(request.content))
        assert request.headers["authorization"] == "Bearer cle-de-test"
        if state["down"]:
            return httpx.Response(429, json={"error": "quota"})
        answer = 'Voici : [{"text": "Hugo, ton secret pour des lasagnes fondantes ?", "hint": "D’après la présentation de Hugo"},' \
                 ' {"text": "Gratin ou purée en accompagnement ?", "hint": "Le menu"}, {"text": "x", "hint": ""},' \
                 ' {"text": "On commence par un tour de table des plats préférés ?", "hint": ""}]'
        return httpx.Response(200, json={"choices": [{"message": {"content": answer}}]})

    llm = LLM("cle-de-test", transport=httpx.MockTransport(provider))
    clock = Clock()
    app = create_app(tmp_path / "llm.sqlite3", clock, mailer=ConsoleMailer(echo=False), photo_search=False, llm=llm)

    def member(name):
        c = TestClient(app)
        d = c.post("/api/auth/register", json={"name": name, "email": name + "@campus.test", "password": "MotDeDémo26"}).json()
        c.headers["X-CSRF-Token"] = d["csrf"]
        c.post("/api/auth/verify-code", json={"code": last_mail(app, name + "@campus.test")[0]})
        return c

    host, guest = member("Hugo"), member("Zoe")
    host.patch("/api/users/me", json={"bio": "Mes lasagnes sont célèbres.", "allergens": ["Soja"], "diet": "Halal"})
    guest.patch("/api/users/me", json={"bio": "Fan de quiz.", "allergens": ["Lait"], "diet": "Végétalien",
                                       "allergies": "Kiwi", "moods": ["Festive"]})
    mid = host.post("/api/meals", json=offer(clock, title="Lasagnes", menu="Lasagnes, salade")).json()["id"]
    tid = guest.post("/api/conversations", json={"meal": mid}).json()["id"]

    r = guest.get(f"/api/conversations/{tid}/icebreakers").json()
    assert r["source"] == "llm" and [q["text"] for q in r["questions"]] == [
        "Hugo, ton secret pour des lasagnes fondantes ?", "Gratin ou purée en accompagnement ?"]
    nxt = guest.get(f"/api/conversations/{tid}/icebreakers?round=1").json()["questions"]
    assert nxt[0]["text"] == "On commence par un tour de table des plats préférés ?" and nxt[0]["hint"] == "Pour lancer"
    assert len(sent) == 1                                                 # cache : un seul appel pour ce fil
    prompt = sent[0]["messages"][1]["content"]
    assert "Lasagnes" in prompt and "Mes lasagnes sont célèbres." in prompt
    for secret in ("Soja", "Lait", "Kiwi", "Halal", "Végétalien", "Festive", "@campus.test", "rue Privée"):
        assert secret not in prompt

    state["down"] = True                                                  # panne / quota : questions par règles
    fallback = host.get(f"/api/conversations/{tid}/icebreakers").json()
    assert fallback["source"] == "rules" and len(fallback["questions"]) == 2
    assert parse("pas de JSON") == [] and parse('[{"text": 3}]') == []
