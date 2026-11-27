import os
import shutil
import socket
import threading
import time

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from blablacook.app import create_app
from blablacook.demo import DEMO_PASSWORD, seed


@pytest.fixture
def live(tmp_path):
    app = create_app(tmp_path/"navigateur.sqlite3")
    seed(app.state.engine, time.time())
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port=sock.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread=threading.Thread(target=server.run,kwargs={"sockets":[sock]},daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.05)
            assert server.started
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit=True
            thread.join(5)
            app.state.engine.dispose()


def login(page, url, username):
    page.goto(url+"/#login")
    page.get_by_label("Adresse étudiante").fill(username+"@campus.test")
    page.get_by_label("Mot de passe").fill(DEMO_PASSWORD)
    page.get_by_role("button",name="Se connecter",exact=True).click()
    expect(page.get_by_role("heading",name="Les tables à venir")).to_be_visible()


def test_parcours_chrome(live):
    chrome=os.getenv("BLABLACOOK_CHROME") or shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        pytest.skip("Chrome ou Chromium est nécessaire pour la recette navigateur.")
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=chrome)
        host=browser.new_context(viewport={"width":1280,"height":800}).new_page()
        guest=browser.new_context(viewport={"width":390,"height":844},is_mobile=True).new_page()
        errors=[]
        external=[]
        def local_only(route):
            if route.request.url.startswith(live+"/") or route.request.url.startswith("data:"):
                route.continue_()
            else:
                external.append(route.request.url)
                route.abort()
        for page in (host,guest):
            page.context.route("**/*",local_only)
        host.on("pageerror",lambda e:errors.append(str(e)))
        guest.on("pageerror",lambda e:errors.append(str(e)))
        guest.goto(live)
        expect(guest.get_by_role("heading",name="Les tables à venir")).to_be_visible()
        guest.keyboard.press("Tab")
        expect(guest.locator(".skip")).to_be_focused()
        guest.keyboard.press("Enter")
        expect(guest.locator("main")).to_be_focused()
        cards=guest.locator(".card h3").all_text_contents()
        assert len(cards)>=3
        assert guest.evaluate("document.documentElement.scrollWidth <= innerWidth")
        guest.get_by_role("button",name="Carte",exact=True).click()
        expect(guest.locator(".map")).to_be_visible()
        assert set(cards)=={s.split(" · ")[0] for s in guest.locator(".maplist a").all_text_contents()}
        guest.locator(".filter-area summary").click()
        guest.get_by_label("Activité",exact=True).select_option("Jeux de société")
        guest.get_by_role("button",name="Appliquer les filtres").click()
        expect(guest.locator(".maplist a")).to_have_count(1)
        guest.get_by_role("button",name="Réinitialiser").click()
        guest.get_by_role("button",name="Liste",exact=True).click()
        login(host,live,"camille")
        host.get_by_role("link",name="Proposer un repas",exact=True).click()
        host.get_by_label("Titre",exact=True).fill("La table de la recette")
        host.get_by_label("Menu",exact=True).fill("Soupe au potiron")
        host.get_by_label("Ingrédients",exact=True).fill("Potiron, crème")
        host.get_by_label("Lait",exact=True).check()
        host.get_by_label("Début",exact=True).fill("2090-11-23T20:00")
        host.get_by_label("Contrôle du minimum").fill("2090-11-23T15:00")
        host.get_by_label("Secteur public").select_option("Centre")
        address="22 rue Imaginaire de la Recette"
        host.get_by_label("Adresse exacte").fill(address)
        host.get_by_role("button",name="Publier le repas").click()
        expect(host.get_by_role("heading",name="La table de la recette")).to_be_visible()
        meal_url=host.url
        guest.goto(meal_url)
        expect(guest.get_by_text(address)).to_have_count(0)
        login(guest,live,"ines")
        guest.goto(meal_url)
        guest.get_by_role("button",name="Écrire à l’hôte").click()
        guest.get_by_label("Votre message").fill("Je peux apporter du pain.")
        guest.get_by_role("button",name="Envoyer le message").click()
        expect(guest.get_by_text("Je peux apporter du pain.",exact=True)).to_be_visible()
        guest.goto(meal_url)
        guest.get_by_role("button",name="Demander une place").click()
        expect(guest.get_by_text("Demande en attente",exact=True)).to_be_visible()
        expect(guest.get_by_text(address)).to_have_count(0)
        host.get_by_role("link",name="Gérer les demandes").click()
        host.get_by_role("article").filter(has_text="La table de la recette").get_by_role("button",name="Accepter").click()
        expect(host.get_by_role("article").filter(has_text="La table de la recette").get_by_text("Réservation confirmée")).to_be_visible()
        guest.reload()
        expect(guest.get_by_text(address,exact=True)).to_be_visible()
        guest.get_by_role("link",name="Mes réservations",exact=True).last.click()
        guest.get_by_role("article").filter(has_text="La table de la recette").get_by_role("button",name="Annuler ma réservation").click()
        guest.get_by_role("button",name="Confirmer l’annulation").click()
        expect(guest.get_by_text("Annulée par l’invité")).to_be_visible()
        guest.goto(meal_url)
        expect(guest.get_by_text("Annulée par l’invité")).to_be_visible()
        expect(guest.get_by_text(address)).to_have_count(0)
        guest.get_by_role("button",name="Signaler",exact=True).click()
        guest.get_by_label("Motif",exact=True).select_option("Information erronée")
        guest.get_by_role("button",name="Envoyer le signalement").click()
        expect(guest.get_by_text("Signalement transmis.")).to_be_visible()
        admin=browser.new_page()
        login(admin,live,"admin")
        admin.goto(live+"/#admin")
        admin.get_by_role("link",name="Annonce · Information erronée").click()
        admin.get_by_label("Décision",exact=True).select_option("classer")
        admin.get_by_label("Motif de la décision").fill("Vérifié pour la démonstration")
        admin.get_by_role("button",name="Enregistrer la décision").click()
        expect(admin.get_by_text("classer · Lou")).to_be_visible()
        expect(admin.get_by_text("Vérifié pour la démonstration",exact=False).last).to_be_visible()
        # La réservation du soir est déjà dans la fenêtre des cinq heures.
        guest.goto(live+"/#bookings")
        late=guest.get_by_role("article").filter(has_text="Soupe du soir")
        late.get_by_role("button",name="Annuler ma réservation").click()
        expect(guest.get_by_text("Cette annulation tardive ajoutera",exact=False)).to_be_visible()
        guest.get_by_role("button",name="Confirmer l’annulation").click()
        expect(late.get_by_text("Annulée par l’invité")).to_be_visible()
        host.goto(live+"/#host")
        history=host.get_by_role("article").filter(has_text="Retour de la tablée de la veille")
        history.get_by_role("button",name="Présent",exact=True).click()
        expect(history.get_by_text("Présence confirmée")).to_be_visible()
        guest.reload()
        review=guest.get_by_role("article").filter(has_text="Retour de la tablée de la veille")
        review.locator("summary").click()
        for criterion in ("Accueil","Ambiance","Repas"):
            review.get_by_label(criterion+" (1 à 5)").fill("5")
        review.get_by_role("button",name="Envoyer mon avis").click()
        expect(review.get_by_text("Votre avis · En attente de publication",exact=False)).to_be_visible()
        assert not external
        assert not errors
        browser.close()
