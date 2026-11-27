import os
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import catalog, community
from .db import DEMO_DB, database
from .domain import Problem

PACKAGE = Path(__file__).parent
templates = Jinja2Templates(directory=str(PACKAGE / "templates"))


def create_app(path=DEMO_DB, clock=time.time, demo=True):
    app = FastAPI(title="BlablaCook", version="1.0", docs_url=None, redoc_url=None)
    app.state.engine = database(path)
    app.state.clock = clock
    app.state.demo = demo
    app.state.domains = {d.strip().lower() for d in os.getenv("BLABLACOOK_DOMAINS", "campus.test,etudiants.test").split(",") if d.strip()}
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

    @app.get("/", include_in_schema=False)
    def home(request: Request):
        return templates.TemplateResponse(request=request, name="index.html", context={})

    return app
