"""Connexion facultative à un LLM gratuit (API « chat completions » au format OpenAI : Groq, Gemini, Mistral…).

Configuration dans .env (sans clé : aucun appel, les questions par règles sont utilisées) :
  BLABLACOOK_LLM_KEY    clé API du fournisseur
  BLABLACOOK_LLM_URL    point d’accès (défaut : Groq)
  BLABLACOOK_LLM_MODEL  modèle (défaut : openai/gpt-oss-120b)

Confidentialité : seules des informations PUBLIQUES sont envoyées (repas, présentations publiques, prénoms) ;
jamais d’adresse, d’email, d’allergie, de régime ni de préférence privée.
"""
import json
import logging
import os
import re
import threading
import time

import httpx

log = logging.getLogger("blablacook.llm")

DEFAULT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"   # disponible dans l’offre gratuite de Groq (vérifié le 2026-11-28)
TIMEOUT = 6.0          # au-delà, on affiche les questions de secours
CACHE_LIFE = 6 * 3600  # une génération par conversation et par phase, réutilisée quelques heures

SYSTEM = """Tu aides des étudiants qui vont partager un repas fait maison à lancer la discussion dans l’application BlablaCook.
Propose des questions brise-glace en français, du point de vue de la personne qui va les envoyer (si c’est un·e
invité·e, ne parle pas comme l’hôte, et inversement), chaleureuses, courtes (une phrase, 20 mots maximum), au tutoiement
(ou au « vous » pour un groupe), précises et ancrées dans les informations fournies (plat, présentation publique des
personnes, moment, activité, ambiance, langue). Varie les angles. Pas de sujet sensible : santé, allergies, régime,
religion, politique, argent, physique, vie amoureuse. N’invente aucun fait sur les personnes.
Réponds UNIQUEMENT avec un tableau JSON de 6 objets : [{"text": "question", "hint": "source"}], où "hint" est une
courte indication de la source parmi : "Le menu", "D’après la présentation de <prénom>", "Le rendez-vous",
"La tablée", "L’activité", "L’ambiance", "La langue", "Pour lancer"."""


class LLM:
    def __init__(self, key, url=DEFAULT_URL, model=DEFAULT_MODEL, transport=None):
        self.key, self.url, self.model = key, url, model
        self.http = httpx.Client(timeout=TIMEOUT, transport=transport)
        self.cache, self.lock = {}, threading.Lock()

    def complete(self, prompt):
        body = {"model": self.model, "temperature": 0.9, "max_tokens": 2000,
                "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}
        if "gpt-oss" in self.model:
            body["reasoning_effort"] = "low"   # modèles qui « réfléchissent » : réflexion courte, réponse rapide
        r = self.http.post(self.url, headers={"Authorization": f"Bearer {self.key}"}, json=body)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def icebreakers(self, key, facts):
        """Questions générées pour `facts` (mises en cache sous `key`) ; None en cas d’échec."""
        with self.lock:
            hit = self.cache.get(key)
            if hit and hit[0] > time.time():
                return hit[1]
        try:
            questions = parse(self.complete(facts))
        except Exception as exc:  # réseau, quota, réponse illisible : on bascule sur les règles
            log.warning("Brise-glace LLM indisponible : %s", exc)
            return None
        if not questions:
            return None
        with self.lock:
            if len(self.cache) > 500:
                self.cache.clear()
            self.cache[key] = (time.time() + CACHE_LIFE, questions)
        return questions


def parse(text):
    """Extrait le tableau JSON de la réponse et ne garde que des questions propres."""
    match = re.search(r"\[.*\]", text, re.S)
    try:
        items = json.loads(match.group(0)) if match else None
    except ValueError:
        items = None
    if not isinstance(items, list):  # réponse coupée ou mal formée : on récupère les objets complets un par un
        items = []
        for obj in re.findall(r"\{[^{}]*\}", text):
            try:
                items.append(json.loads(obj))
            except ValueError:
                pass
    out, seen = [], set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        q = " ".join(str(item.get("text", "")).split())
        hint = " ".join(str(item.get("hint", "")).split())[:60] or "Pour lancer"
        hint = re.sub(r"\bde (?=[AEIOUYÂÉÈÊÎÔÛHaeiouyâéèêîôûh])", "d’", hint)   # « de Inès » → « d’Inès »
        if 8 <= len(q) <= 220 and q.lower() not in seen:
            seen.add(q.lower())
            out.append({"text": q, "hint": hint})
    return out[:8]


def llm_from_env():
    key = os.getenv("BLABLACOOK_LLM_KEY", "").strip()
    if not key:
        return None
    return LLM(key, os.getenv("BLABLACOOK_LLM_URL", "").strip() or DEFAULT_URL,
               os.getenv("BLABLACOOK_LLM_MODEL", "").strip() or DEFAULT_MODEL)
