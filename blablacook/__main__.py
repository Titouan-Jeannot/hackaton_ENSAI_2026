import argparse
import os
import time

import uvicorn

from .app import create_app
from .db import DEMO_DB, ROOT, OutdatedSchema, database
from .demo import seed


def load_env(path=ROOT / ".env"):
    """Charge le fichier .env (clé=valeur) sans écraser les variables déjà définies dans le terminal."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main():
    load_env()
    parser = argparse.ArgumentParser(description="BlablaCook · démonstration locale")
    parser.add_argument("command", choices=["serve", "seed", "reset-demo"], nargs="?", default="serve")
    args = parser.parse_args()
    try:
        run(parser, args)
    except OutdatedSchema as exc:
        parser.exit(1, f"Erreur : {exc}\n")


def run(parser, args):
    if DEMO_DB.is_symlink() or DEMO_DB.parent.is_symlink():
        parser.error("La base de démonstration doit être un fichier local dans var/.")
    if args.command in ("reset-demo", "seed"):
        engine = database(DEMO_DB)
        try:
            created = seed(engine, time.time(), reset=args.command == "reset-demo")
        except ValueError as exc:
            parser.error(str(exc))
        print("Base de démonstration peuplée." if created else "La base contient déjà des comptes.")
        engine.dispose()
        return
    app = create_app()
    seed(app.state.engine, time.time())
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("BLABLACOOK_PORT", "8000")))


if __name__ == "__main__":
    main()
