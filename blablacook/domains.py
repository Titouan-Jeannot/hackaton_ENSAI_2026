"""Liste des domaines d'email étudiants autorisés."""
import os
import re
from pathlib import Path

DOMAINS_FILE = Path(__file__).parent / "data" / "student_domains.txt"
EMAIL = re.compile(r"[^@\s]+@([a-z0-9-]+(\.[a-z0-9-]+)+)")


def load_domains(extra=None):
    """Domaines du fichier + domaines de BLABLACOOK_DOMAINS (séparés par des virgules)."""
    lines = DOMAINS_FILE.read_text(encoding="utf-8").splitlines()
    domains = {line.strip().lower() for line in lines if line.strip() and not line.lstrip().startswith("#")}
    extra = os.getenv("BLABLACOOK_DOMAINS", "campus.test,etudiants.test") if extra is None else extra
    return domains | {d.strip().lower() for d in extra.split(",") if d.strip()}


def student_email(email, domains):
    """Vrai si l'adresse appartient à un domaine autorisé ou à l'un de ses sous-domaines."""
    match = EMAIL.fullmatch(email)
    if not match:
        return False
    host = match.group(1)
    return any(host == d or host.endswith("." + d) for d in domains)
