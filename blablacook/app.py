import hashlib
import os
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import catalog, community
from .db import DEMO_DB, database
from .domains import load_domains
from .imagesearch import search_from_env
from .llm import llm_from_env
from .mailer import mailer_from_env
from .domain import Problem

PACKAGE = Path(__file__).parent
templates = Jinja2Templates(directory=str(PACKAGE / "templates"))


def asset_version():
    """Empreinte des fichiers CSS/JS : ajoutée à leur URL (?v=…), elle change dès qu’un fichier change, ce qui
    empêche le navigateur ou le service worker de servir une ancienne version après une mise à jour."""
    h = hashlib.sha1()
    for f in sorted((PACKAGE / "static").glob("*.[cj]s*")):
        h.update(f.name.encode() + str(f.stat().st_mtime_ns).encode())
    return h.hexdigest()[:10]


def create_app(path=DEMO_DB, clock=time.time, demo=True, mailer=None, photo_search=None, llm=None):
    app = FastAPI(title="BlablaCook", version="1.0", docs_url=None, redoc_url=None)
    app.state.engine = database(path)
    app.state.clock = clock
    app.state.demo = demo
    app.state.domains = load_domains()
    app.state.mailer = mailer or mailer_from_env()
    # Clé navigateur Google Maps : elle est publique par nature, la restreindre au domaine dans la console Google.
    app.state.maps_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    # photo_search=False désactive la recherche (tests hors ligne) ; None = configuration de l’environnement.
    app.state.photo_search = search_from_env() if photo_search is None else (photo_search or None)
    # llm=False désactive le LLM (tests) ; None = configuration de l’environnement (BLABLACOOK_LLM_KEY).
    app.state.llm = llm_from_env() if llm is None else (llm or None)
    app.include_router(catalog.router, prefix="/api")
    app.include_router(community.router, prefix="/api")
    app.mount("/static", StaticFiles(directory=str(PACKAGE / "static")), name="static")

    @app.middleware("http")
    async def private_cache(request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.exception_handler(Problem)
    async def problem(request, exc):
        return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        errors = [{"field": str(e["loc"][-1]), "message": str(e.get("ctx", {}).get("error") or "Valeur invalide.")} for e in exc.errors()]
        return JSONResponse({"code": "INVALID_INPUT", "message": errors[0]["message"], "fields": errors}, status_code=422)

    # Appli installable (PWA) : manifeste et service worker servis à la racine de l’application, pour que leur
    # portée couvre toute l’appli (y compris derrière un proxy comme celui de SSP Cloud).
    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest():
        return FileResponse(PACKAGE / "static" / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/sw.js", include_in_schema=False)
    def service_worker():
        return FileResponse(PACKAGE / "static" / "sw.js", media_type="text/javascript")

    @app.get("/", include_in_schema=False)
    def home(request: Request):
        return templates.TemplateResponse(request=request, name="index.html", context={"v": asset_version()})

    return app
