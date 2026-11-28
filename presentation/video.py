"""Tourne la vidéo de présentation de BlablaCook (≈ 3 min, sans son, 1920×1080).

Lance un serveur de démonstration sur une base temporaire (aucun vrai mail envoyé), pilote Chrome avec Playwright
et filme l'écran image par image (CDP Page.startScreencast), puis assemble le MP4 avec ffmpeg.

    PYTHONPATH=. .venv/bin/python presentation/video.py

Variables utiles : BLABLACOOK_CHROME (chemin de Chrome), FFMPEG (chemin de ffmpeg).
"""
import asyncio
import base64
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import uvicorn
from playwright.async_api import async_playwright

from blablacook.__main__ import load_env
from blablacook.app import create_app
from blablacook.demo import DEMO_PASSWORD, seed
from blablacook.mailer import ConsoleMailer

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "blablacook-presentation.mp4"
CHROME = os.getenv("BLABLACOOK_CHROME") or next(
    (p for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", shutil.which("google-chrome"),
                 shutil.which("chromium")) if p and Path(p).exists()), None)
FFMPEG = os.getenv("FFMPEG") or shutil.which("ffmpeg")
W, H = 1920, 1080
TYPE = 30          # délai entre deux caractères saisis (ms)
MOVE = 520         # durée d'un déplacement du curseur (ms)

# --- Effets injectés dans chaque page : curseur animé, onde de clic, étiquette de séquence, fondu ---------------
FX = r"""
(() => {
 if (window.top !== window || window.__fx) return;
 const css = `
 #fx-cursor{position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483646;pointer-events:none;
   transition:transform var(--d,650ms) cubic-bezier(.45,.05,.2,1);filter:drop-shadow(0 3px 5px #0006)}
 #fx-cursor svg{width:26px;height:26px}
 .fx-ring{position:fixed;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;border:3px solid #b94427;
   z-index:2147483645;pointer-events:none;animation:fx-ring .6s ease-out forwards}
 @keyframes fx-ring{from{transform:scale(.4);opacity:1}to{transform:scale(3.4);opacity:0}}
 #fx-chapter{position:fixed;left:36px;bottom:36px;z-index:2147483644;display:flex;align-items:center;gap:14px;
   background:#302f27;color:#fff;border-radius:40px;padding:12px 26px 12px 12px;font:600 22px/1.2 "DM Sans",
   "Segoe UI",Arial,sans-serif;box-shadow:0 10px 30px #0004;transform:translateX(-130%);transition:transform .7s
   cubic-bezier(.2,.9,.25,1.15)}
 #fx-chapter.on{transform:none}
 #fx-chapter b{display:grid;place-items:center;width:40px;height:40px;border-radius:50%;background:#b94427;font-size:19px}
 #fx-fade{position:fixed;inset:0;background:#302f27;z-index:2147483647;pointer-events:none;opacity:0;
   transition:opacity .45s ease}
 html{scroll-behavior:smooth}`;
 const boot = () => {
  const st = document.createElement("style"); st.textContent = css; document.head.append(st);
  const cur = document.createElement("div"); cur.id = "fx-cursor";
  cur.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 2l16 9.5-7 1.6-3.6 6.9z" fill="#fff" stroke="#302f27" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  const pos = JSON.parse(sessionStorage.fxPos || "[960,600]");
  cur.style.transform = `translate(${pos[0]}px,${pos[1]}px)`;
  const chap = document.createElement("div"); chap.id = "fx-chapter";
  const fade = document.createElement("div"); fade.id = "fx-fade";
  if (sessionStorage.fxFade === "1") { fade.style.transition = "none"; fade.style.opacity = 1; }
  document.documentElement.append(cur, chap, fade);
  // Vue ordinateur de l’application : agrandie pour être lisible en projection (pas les décors ni l’iframe).
  if (location.pathname === "/") document.body.style.zoom = "1.3";
 };
 if (document.body) boot(); else document.addEventListener("DOMContentLoaded", boot);
 window.__fx = {
  move(x, y, ms) { const c = document.querySelector("#fx-cursor"); c.style.setProperty("--d", ms + "ms");
    c.style.transform = `translate(${x}px,${y}px)`; sessionStorage.fxPos = JSON.stringify([x, y]); },
  ring(x, y) { const r = document.createElement("div"); r.className = "fx-ring"; r.style.left = x + "px";
    r.style.top = y + "px"; document.documentElement.append(r); setTimeout(() => r.remove(), 700); },
  chapter(n, t) { const c = document.querySelector("#fx-chapter");
    if (!t) { c.classList.remove("on"); return; }
    c.innerHTML = `<b>${n}</b>${t}`; c.classList.add("on"); },
  fade(on) { const f = document.querySelector("#fx-fade"); f.style.transition = "opacity .45s ease";
    f.style.opacity = on ? 1 : 0; sessionStorage.fxFade = on ? "1" : "0"; },
 };
})();
"""

FONTS = '"DM Serif Text",Georgia,serif'
BASE_CSS = """*{box-sizing:border-box}html,body{margin:0;height:100%;overflow:hidden}
body{font-family:"DM Sans","Segoe UI",Arial,sans-serif;color:#302f27;background:#faf8f2}"""

INTRO = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>{BASE_CSS}
.wall{{position:absolute;inset:0;display:grid;grid-template-columns:repeat(4,1fr);gap:0}}
.wall img{{width:100%;height:100%;object-fit:cover;animation:kb 9s ease-out both;filter:saturate(1.1)}}
.wall img:nth-child(2){{animation-delay:.15s}}.wall img:nth-child(3){{animation-delay:.3s}}.wall img:nth-child(4){{animation-delay:.45s}}
@keyframes kb{{from{{transform:scale(1.25);opacity:0}}to{{transform:scale(1);opacity:1}}}}
.veil{{position:absolute;inset:0;background:radial-gradient(ellipse at center,#302f27dd 0%,#302f27aa 55%,#302f2766 100%)}}
.box{{position:absolute;inset:0;display:grid;place-content:center;justify-items:center;text-align:center;color:#fff}}
.logo{{display:flex;align-items:center;gap:26px;font:bold 150px/1 {FONTS};letter-spacing:-.07em;
  animation:up 1s .5s cubic-bezier(.2,.9,.25,1.1) both}}
.logo img{{width:150px;height:150px;animation:pop 1s .3s cubic-bezier(.2,.9,.3,1.4) both}}
.logo span{{color:#e9704f}}
.tag{{margin-top:34px;font:500 44px/1.3 {FONTS};animation:up 1s 1.4s ease both;color:#f7edd6}}
.tag em{{color:#e9704f}}
.sub{{margin-top:26px;font-size:26px;letter-spacing:.2em;text-transform:uppercase;opacity:.85;animation:up 1s 2.2s ease both}}
@keyframes up{{from{{transform:translateY(40px);opacity:0}}to{{transform:none;opacity:1}}}}
@keyframes pop{{from{{transform:scale(0) rotate(-30deg)}}to{{transform:none}}}}
</style></head><body><div class="wall"><img src="/static/images/pasta.webp"><img src="/static/images/curry.webp">
<img src="/static/images/tacos.webp"><img src="/static/images/table.webp"></div><div class="veil"></div>
<div class="box"><div class="logo"><img src="/static/icon.svg" alt="">Blabla<span>Cook</span></div>
<p class="tag">Des repas faits maison, <em>partagés entre étudiants.</em></p>
<p class="sub">Hackathon ENSAI 2026</p></div></body></html>"""

OUTRO = INTRO.replace("Des repas faits maison, <em>partagés entre étudiants.</em>", "À table, <em>ensemble.</em>") \
             .replace("Hackathon ENSAI 2026", "Inscription vérifiée · Carte · Réservation · Chat · Avis · Modération")


def stage(n, title, line, src):
    """Décor de séquence mobile : téléphone (iframe de l’application) sur fond aux couleurs de BlablaCook."""
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>{BASE_CSS}
body{{background:linear-gradient(125deg,#f7edd6 0%,#faf8f2 45%,#f0d4ca 100%)}}
.blob{{position:absolute;border-radius:50%;filter:blur(8px);opacity:.55}}
.b1{{width:620px;height:620px;background:#e2e6da;left:-160px;bottom:-220px;animation:fl 12s ease-in-out infinite alternate}}
.b2{{width:420px;height:420px;background:#f2d9b6;right:120px;top:-160px;animation:fl 10s ease-in-out infinite alternate-reverse}}
@keyframes fl{{to{{transform:translate(60px,-40px)}}}}
.text{{position:absolute;left:180px;top:50%;transform:translateY(-50%);width:720px;animation:in .9s .2s cubic-bezier(.2,.9,.25,1) both}}
.num{{display:inline-grid;place-items:center;width:74px;height:74px;border-radius:50%;background:#b94427;color:#fff;font:700 34px/1 "DM Sans",Arial}}
h1{{font:500 92px/1.02 {FONTS};letter-spacing:-.045em;margin:34px 0 26px}}
p{{font-size:32px;line-height:1.4;color:#635f54;margin:0}}
.brand{{position:absolute;left:180px;top:70px;display:flex;align-items:center;gap:14px;font:bold 40px/1 {FONTS};letter-spacing:-.07em}}
.brand img{{width:46px}}.brand span{{color:#b94427}}
.phone{{position:absolute;right:230px;top:50%;width:426px;height:880px;margin-top:-440px;border-radius:58px;background:#1d1c18;
  padding:18px;box-shadow:0 40px 80px #302f2755,0 0 0 2px #4a4840 inset;animation:ph 1s cubic-bezier(.2,.9,.25,1) both}}
@keyframes ph{{from{{transform:translateY(120px) rotate(4deg);opacity:0}}to{{transform:none;opacity:1}}}}
@keyframes in{{from{{transform:translate(-60px,-50%);opacity:0}}to{{transform:translateY(-50%);opacity:1}}}}
.phone:before{{content:"";position:absolute;left:50%;top:26px;width:120px;height:30px;margin-left:-60px;border-radius:20px;background:#1d1c18;z-index:2}}
iframe{{width:390px;height:844px;border:0;border-radius:42px;background:#faf8f2;display:block}}
</style></head><body><div class="blob b1"></div><div class="blob b2"></div>
<div class="brand"><img src="/static/icon.svg" alt="">Blabla<span>Cook</span></div>
<div class="text"><span class="num">{n}</span><h1>{title}</h1><p>{line}</p></div>
<div class="phone"><iframe name="app" id="app" src="{src}"></iframe></div></body></html>"""


class Director:
    def __init__(self, page, url, app):
        self.page, self.url, self.app, self.ctx = page, url, app, page.context

    async def pause(self, s):
        await self.page.wait_for_timeout(int(s * 1000))

    async def fx(self, script, *args):
        await self.page.evaluate(script, list(args))

    async def chapter(self, n, title):
        await self.fx("([n,t])=>window.__fx.chapter(n,t)", n, title)

    async def fade(self, on):
        await self.fx("([o])=>window.__fx.fade(o)", on)
        await self.pause(0.5)

    async def goto(self, path):
        # Un simple changement de #fragment ne recharge pas la page : on force un vrai chargement pour que
        # l’application relise la session après un changement de compte.
        self.loads = getattr(self, "loads", 0) + 1
        if path.startswith("/#"):
            path = f"/?scene={self.loads}" + path[1:]
        await self.page.goto(self.url + path)
        await self.page.wait_for_load_state("networkidle")

    async def scene(self, path):
        """Change de décor derrière un fondu."""
        await self.fade(True)
        await self.goto(path)
        await self.pause(0.6)
        await self.fade(False)

    async def login(self, who):
        """Change de compte hors champ (le contexte partage ses cookies avec l’API Playwright)."""
        await self.ctx.clear_cookies()
        if who:
            r = await self.ctx.request.post(self.url + "/api/auth/login",
                                            data={"email": who + "@campus.test", "password": DEMO_PASSWORD})
            assert r.ok, await r.text()

    async def point(self, loc, click=True):
        await loc.wait_for(state="visible")
        await loc.evaluate("e=>e.scrollIntoView({behavior:'smooth',block:'center'})")
        await self.pause(0.55)
        box = await loc.bounding_box()
        x, y = box["x"] + min(box["width"] / 2, 60), box["y"] + box["height"] / 2
        await self.fx("([x,y,ms])=>window.__fx.move(x,y,ms)", x, y, MOVE)
        await self.page.mouse.move(x, y, steps=8)
        await self.pause(MOVE / 1000 + 0.1)
        if click:
            await self.fx("([x,y])=>window.__fx.ring(x,y)", x, y)
            await loc.click()
            await self.pause(0.35)

    async def type(self, loc, text, delay=TYPE):
        await self.point(loc)
        await loc.press_sequentially(text, delay=delay)
        await self.pause(0.25)

    async def scroll(self, frame, dy, s=1.4):
        await frame.evaluate("dy=>window.scrollBy({top:dy,behavior:'smooth'})", dy)
        await self.pause(s)


async def record(url, app, frames_dir):
    meta = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=CHROME, args=["--hide-scrollbars"])
        ctx = await browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1, locale="fr-FR")
        await ctx.add_init_script(FX)
        page = await ctx.new_page()
        pages = {"/__intro": INTRO, "/__outro": OUTRO}

        async def serve(route):
            path = route.request.url[len(url):]
            await route.fulfill(content_type="text/html; charset=utf-8", body=pages[path.split("?")[0]])

        await page.route(url + "/__*", serve)
        d = Director(page, url, app)

        def set_stage(n, title, line, src):
            pages["/__stage"] = stage(n, title, line, src)
            return d.scene("/__stage")

        def app_frame():
            return page.frame(name="app")

        # Préparation hors champ : page blanche aux couleurs de l’appli.
        await page.goto(url + "/__intro")
        await page.evaluate("sessionStorage.fxFade='0'")
        cdp = await ctx.new_cdp_session(page)

        def on_frame(ev):
            n = len(meta)
            (frames_dir / f"{n:05d}.jpg").write_bytes(base64.b64decode(ev["data"]))
            meta.append(ev["metadata"]["timestamp"])
            asyncio.ensure_future(cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]}))

        cdp.on("Page.screencastFrame", on_frame)
        await page.reload()
        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 88, "maxWidth": W, "maxHeight": H})
        started = time.time()

        # 1 · Ouverture
        await d.pause(5.0)

        # 2 · Découvrir les tables (visiteur, ordinateur)
        await d.scene("/#catalogue")
        await d.chapter(1, "Découvrir les tables")
        await d.pause(1.2)
        await d.scroll(page, 520, 1.5)
        await d.type(page.get_by_label("Recherche"), "curry")
        await d.point(page.get_by_role("button", name="Rechercher"))
        await d.pause(1.4)
        await d.point(page.get_by_label("Recherche"))
        await page.get_by_label("Recherche").fill("")
        await d.point(page.get_by_role("button", name="Rechercher"))
        await d.pause(0.6)
        await d.chapter(2, "Une carte qui protège l’adresse")
        await d.point(page.get_by_role("button", name="Carte", exact=True))
        await d.pause(3.2)

        # 3 · Fiche d’un repas
        await d.chapter(3, "Menu, allergènes, zone approximative")
        await d.point(page.locator(".maplist a").filter(has_text="Pasta al pomodoro"))
        await d.pause(1.8)
        await d.scroll(page, 450, 1.8)
        await d.chapter(3, "")

        # 4 · Inscription étudiante (mobile)
        await d.login(None)
        await set_stage(4, "Inscription vérifiée", "Adresse étudiante obligatoire,<br>confirmée par un code envoyé par mail.", "/#register")
        f = page.frame_locator("#app")
        await d.pause(1.2)
        await d.type(f.get_by_label("Prénom"), "Zoé")
        await d.type(f.get_by_label("Adresse étudiante"), "zoe.martin@ensai.fr")
        await d.type(f.get_by_label("Mot de passe"), "MonRepas2026", delay=25)
        await d.point(f.get_by_role("button", name="Créer mon compte"))
        await d.pause(2.0)
        code = next(m for m in reversed(app.state.mailer.outbox) if m["to"] == "zoe.martin@ensai.fr")
        code = next(w for w in code["text"].split() if w.isdigit() and len(w) == 6)
        await d.type(f.get_by_label("Code reçu par mail"), code, delay=120)
        await d.point(f.get_by_role("button", name="Valider mon adresse"))
        await d.pause(1.6)
        await d.pause(0.6)

        # 5 · Publier un repas (Camille, ordinateur)
        await d.login("camille")
        await d.scene("/#publish")
        await d.chapter(5, "Proposer un repas en 1 minute")
        await d.type(page.get_by_label("Titre", exact=True), "Risotto aux champignons")
        await d.pause(2.6)  # la photo automatique apparaît (Openverse)
        await d.type(page.get_by_label("Menu", exact=True), "Risotto aux cèpes, tiramisu", delay=26)
        await d.type(page.get_by_label("Ingrédients", exact=True), "Riz arborio, cèpes, parmesan", delay=22)
        await d.point(page.get_by_label("Lait", exact=True))
        await d.point(page.get_by_label("Œufs", exact=True))
        day = (datetime.now() + timedelta(days=3)).replace(hour=19, minute=30)
        await d.point(page.get_by_label("Début", exact=True), click=False)
        await page.get_by_label("Début", exact=True).fill(day.strftime("%Y-%m-%dT%H:%M"))
        await d.pause(0.5)
        place = page.locator("gmp-place-autocomplete")
        published_address = False
        if await place.count():
            try:
                await d.point(place)
                await page.keyboard.type("Place Sainte-Anne, Rennes", delay=TYPE)
                await d.pause(2.0)
                await page.keyboard.press("ArrowDown")
                await d.pause(0.4)
                await page.keyboard.press("Enter")
                await d.pause(1.8)
                published_address = bool(await page.locator('[name="lat"]').input_value())
            except Exception as exc:  # repli : la séquence continue sans publication
                print("Autocomplétion indisponible :", exc)
        await d.point(page.get_by_label("Minimum d’invités", exact=True), click=False)
        await page.get_by_label("Minimum d’invités", exact=True).fill("2")
        await page.get_by_label("Maximum d’invités", exact=True).fill("4")
        await d.point(page.get_by_label("Date limite pour atteindre le minimum d’invités"), click=False)
        await page.get_by_label("Date limite pour atteindre le minimum d’invités").fill(
            (day - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"))
        await d.pause(0.4)
        meal_id, meal_title = None, "Risotto aux champignons"
        if published_address:
            await d.point(page.get_by_role("button", name="Publier le repas"))
            await page.get_by_role("heading", name="Risotto aux champignons").wait_for()
            meal_id = page.url.rsplit("/", 1)[-1]
            await d.pause(1.0)
            await d.scroll(page, 380, 2.0)
        else:
            print("Repli : repas de démo « Pasta al pomodoro » utilisé pour la suite.")
        await d.chapter(5, "")

        if not meal_id:
            meal_title = "Pasta al pomodoro"
            r = await ctx.request.get(url + "/api/meals?search=Pasta")
            meal_id = str((await r.json())[0]["id"])

        # 6 · Demander une place (Inès, mobile)
        await d.login("ines")
        await set_stage(6, "Réserver une place", "Suggestions près de chez soi,<br>message à l’hôte, demande en un clic.", "/#catalogue")
        f = page.frame_locator("#app")
        await d.pause(1.2)
        await app_frame().evaluate(f"location.hash='meal/{meal_id}'")
        await d.pause(1.6)
        await d.scroll(app_frame(), 700, 1.8)
        await d.point(f.get_by_role("button", name="Écrire à l’hôte"))
        await d.pause(1.0)
        await d.type(f.get_by_label("Votre message"), "Bonjour ! Je suis végétarienne, ton menu me tente beaucoup.", delay=26)
        await d.point(f.get_by_role("button", name="Envoyer le message"))
        await d.pause(1.2)
        await app_frame().evaluate(f"location.hash='meal/{meal_id}'")
        await d.pause(1.2)
        await d.point(f.get_by_role("button", name="Demander une place"))
        await d.pause(1.8)

        # 7 · L’hôte choisit ses invités (Camille, ordinateur)
        await d.login("camille")
        await d.scene("/#host")
        await d.chapter(7, "L’hôte choisit ses invités")
        await d.pause(1.0)
        art = page.get_by_role("article").filter(has_text=meal_title)
        await d.point(art.get_by_role("button", name="Accepter").first)
        await d.pause(2.2)
        await d.chapter(7, "")

        # 8 · Chat de groupe (Inès, mobile)
        await d.login("ines")
        await set_stage(8, "Le chat du repas", "Les invités acceptés rejoignent le groupe.<br>L’adresse exacte arrive 1 h avant.", f"/#meal/{meal_id}")
        f = page.frame_locator("#app")
        await d.pause(1.4)
        await d.scroll(app_frame(), 640, 1.8)
        await d.point(f.get_by_role("link", name="Ouvrir le chat du repas"))
        await d.pause(1.0)
        await d.type(f.get_by_label("Votre message"), "Trop hâte ! J’apporte le pain et une playlist.", delay=26)
        await d.point(f.get_by_role("button", name="Envoyer le message"))
        await d.pause(1.8)

        # 9 · Après le repas : présences et avis (Camille, ordinateur)
        await d.login("camille")
        await d.scene("/#host")
        await d.chapter(9, "Présences et avis après le repas")
        art = page.get_by_role("article").filter(has_text="Retour de la tablée de la veille")
        await d.point(art.get_by_role("button", name="Présent", exact=True))
        await d.pause(1.4)
        art = page.get_by_role("article").filter(has_text="Retour de la tablée de la veille")
        await d.point(art.locator("summary"))
        await d.type(art.get_by_label("Note globale (1 à 5)"), "5")
        await d.type(art.get_by_label("Commentaire facultatif"), "Invitée adorable, à refaire très vite !", delay=24)
        await d.point(art.get_by_role("button", name="Envoyer mon avis"))
        await d.pause(1.6)
        await d.chapter(9, "")

        # 10 · Signalement et modération
        await d.login("noe")
        await d.scene(f"/#meal/{meal_id}")
        await d.chapter(10, "Signaler un contenu")
        await d.point(page.get_by_role("button", name="Signaler", exact=True))
        await d.point(page.get_by_label("Motif", exact=True), click=False)
        await page.get_by_label("Motif", exact=True).select_option("Information erronée")
        await d.pause(0.6)
        await d.point(page.get_by_role("button", name="Envoyer le signalement"))
        await d.pause(1.0)
        if os.getenv("VIDEO_DEBUG"):
            await page.screenshot(path=os.environ["VIDEO_DEBUG"] + "/report.png")
        await d.login("admin")
        await d.scene("/#admin")
        await d.chapter(10, "La modération tranche et garde une trace")
        await d.point(page.get_by_role("link", name="Annonce · Information erronée").first)
        await d.pause(0.8)
        await d.point(page.get_by_label("Décision", exact=True), click=False)
        await page.get_by_label("Décision", exact=True).select_option("classer")
        await d.type(page.get_by_label("Motif de la décision"), "Informations vérifiées avec l’hôte.", delay=24)
        await d.point(page.get_by_role("button", name="Enregistrer la décision"))
        await d.pause(2.0)
        await d.chapter(10, "")

        # 11 · Fin
        await d.scene("/__outro")
        await d.pause(5.5)
        await cdp.send("Page.stopScreencast")
        await d.pause(0.3)
        print(f"Tournage : {time.time() - started:.0f} s, {len(meta)} images")
        await browser.close()
    return meta


def assemble(meta, frames_dir):
    """Images à cadence variable → MP4 H.264 à 30 i/s, avec fondus d’entrée et de sortie."""
    lines = []
    for n, t in enumerate(meta):
        nxt = meta[n + 1] if n + 1 < len(meta) else t + 0.5
        lines.append(f"file '{frames_dir / f'{n:05d}.jpg'}'\nduration {max(nxt - t, 0.001):.4f}")
    lines.append(f"file '{frames_dir / f'{len(meta) - 1:05d}.jpg'}'")
    listing = frames_dir / "frames.txt"
    listing.write_text("\n".join(lines))
    total = meta[-1] - meta[0] + 0.5
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-vf", f"fps=30,scale={W}:{H}:flags=lanczos,fade=t=in:st=0:d=0.8,fade=t=out:st={total - 1.2:.2f}:d=1.2",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(OUTPUT)], check=True)
    return total


def main():
    if not CHROME or not FFMPEG:
        sys.exit("Chrome et ffmpeg sont nécessaires (BLABLACOOK_CHROME, FFMPEG).")
    load_env()
    work = Path(tempfile.mkdtemp(prefix="blablacook-video-"))
    frames = work / "frames"
    frames.mkdir()
    app = create_app(work / "demo.sqlite3", mailer=ConsoleMailer(echo=False))
    seed(app.state.engine, time.time())
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True).start()
        while not server.started:
            time.sleep(0.05)
        try:
            meta = asyncio.run(record(f"http://127.0.0.1:{port}", app, frames))
        finally:
            server.should_exit = True
    total = assemble(meta, frames)
    shutil.rmtree(work, ignore_errors=True)
    print(f"Vidéo : {OUTPUT} ({total:.0f} s)")


if __name__ == "__main__":
    main()
