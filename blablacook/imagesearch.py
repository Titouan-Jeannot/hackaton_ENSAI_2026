"""Recherche d'une photo libre de droits correspondant au titre d'un repas (API Openverse, sans clé).

Openverse (https://api.openverse.org, projet de WordPress.org) indexe des centaines de millions d'images sous
licences Creative Commons (Flickr, Wikimedia…). L'accès anonyme ne demande aucune clé
(limites : 100 requêtes/min et 1 000/jour), largement suffisant grâce au cache de 24 h.

- On ne garde que les licences autorisant l'usage commercial et la modification (l'image est redimensionnée).
- L'image n'est pas affichée en lien direct : la vignette est téléchargée depuis api.openverse.org (seul hôte
  contacté), réencodée en JPEG et stockée avec le repas, comme une photo importée.
- L'attribution exigée par les licences CC (auteur, licence, lien vers la source) est gardée et affichée.
- Openverse indexe surtout en anglais : les mots culinaires du titre sont traduits par un petit glossaire,
  avec repli sur le titre d'origine.

Le navigateur ne manipule qu'un jeton « openverse:<uuid> » : l'image et le crédit sont retrouvés côté serveur,
le client ne peut donc ni falsifier le crédit ni faire télécharger une URL arbitraire.
Désactivable avec BLABLACOOK_IMAGE_SEARCH=off (l'image par défaut est alors toujours utilisée).
"""
import logging
import os
import re
import threading
import time
import unicodedata
from collections import OrderedDict
from urllib.parse import urlsplit

import httpx

from .photos import reencode

log = logging.getLogger("blablacook.images")
DEFAULT_IMAGE = "table"
PHOTO_TOKEN = re.compile(r"openverse:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
CACHE_LIFE = 24 * 3600
MAX_DOWNLOAD = 5 * 1024 * 1024
MEAL_PHOTO_SIZE = (960, 640)
API_HOST = "api.openverse.org"
USER_AGENT = "BlablaCook/1.0 (application etudiante de repas partages)"

# Mots du titre (sans accents, en minuscules) -> mots-clés anglais. Les expressions sont testées avant les mots.
GLOSSARY = {
    "pois chiches": "chickpeas", "hachis parmentier": "shepherd's pie", "pot au feu": "stew",
    "petit dejeuner": "breakfast", "boeuf bourguignon": "beef stew", "chili con carne": "chili",
    "lasagne": "lasagne", "lasagnes": "lasagne", "pates": "pasta", "pasta": "pasta", "spaghetti": "spaghetti",
    "spaghettis": "spaghetti", "tagliatelles": "tagliatelle", "gnocchi": "gnocchi", "ravioli": "ravioli",
    "raviolis": "ravioli", "bolognaise": "bolognese", "carbonara": "carbonara", "pesto": "pesto",
    "pomodoro": "tomato", "pizza": "pizza", "pizzas": "pizza", "risotto": "risotto", "couscous": "couscous",
    "tajine": "tagine", "crepe": "crepes", "crepes": "crepes", "galette": "galette", "galettes": "galette",
    "gaufre": "waffles", "gaufres": "waffles", "pancakes": "pancakes", "soupe": "soup", "veloute": "soup",
    "potage": "soup", "potiron": "pumpkin", "citrouille": "pumpkin", "courge": "squash", "curry": "curry",
    "dahl": "dal", "dal": "dal", "legumes": "vegetables", "legume": "vegetables", "poulet": "chicken",
    "boeuf": "beef", "porc": "pork", "agneau": "lamb", "poisson": "fish", "saumon": "salmon", "thon": "tuna",
    "crevettes": "shrimp", "riz": "rice", "nouilles": "noodles", "ramen": "ramen", "pho": "pho", "sushi": "sushi",
    "sushis": "sushi", "wok": "stir fry", "tacos": "tacos", "taco": "tacos", "burrito": "burrito",
    "burritos": "burrito", "fajitas": "fajitas", "enchiladas": "enchiladas", "chili": "chili", "salade": "salad",
    "quiche": "quiche", "tarte": "tart", "tartiflette": "tartiflette", "raclette": "raclette", "fondue": "fondue",
    "ratatouille": "ratatouille", "gratin": "gratin", "burger": "burger", "burgers": "burger", "frites": "fries",
    "falafel": "falafel", "falafels": "falafel", "houmous": "hummus", "paella": "paella", "omelette": "omelette",
    "blanquette": "stew", "choucroute": "sauerkraut", "cassoulet": "cassoulet", "moussaka": "moussaka",
    "barbecue": "barbecue", "brunch": "brunch", "gateau": "cake", "gateaux": "cake", "crumble": "crumble",
    "brownie": "brownie", "brownies": "brownie", "cookies": "cookies", "chocolat": "chocolate",
    "dessert": "dessert", "fromage": "cheese", "tomate": "tomato", "tomates": "tomato",
    "champignons": "mushroom", "champignon": "mushroom", "haricots": "beans", "lentilles": "lentils",
    "aubergine": "eggplant", "aubergines": "eggplant", "courgette": "zucchini", "courgettes": "zucchini",
    "epinards": "spinach", "patate": "potato", "pommes de terre": "potatoes", "puree": "mashed potatoes",
    "oeufs": "eggs", "bao": "bao", "dumplings": "dumplings", "raviolis chinois": "dumplings",
}


def plain(text):
    text = unicodedata.normalize("NFKD", text.casefold().replace("œ", "oe"))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def queries(title):
    """Requêtes à essayer dans l'ordre : mots traduits, mot principal traduit, titre d'origine."""
    text = f" {plain(title)} "
    found = []
    for fr in sorted(GLOSSARY, key=len, reverse=True):  # expressions avant mots isolés
        if f" {fr} " in text:
            found.append((text.index(f" {fr} "), GLOSSARY[fr]))
            text = text.replace(f" {fr} ", " " * (len(fr) + 2))
    words = list(dict.fromkeys(en for _, en in sorted(found)))
    candidates = [" ".join(words[:3]), words[0] if words else "", plain(title)[:100]]
    return [q for q in dict.fromkeys(candidates) if q]


def safe_url(url, host=None):
    parts = urlsplit(url or "")
    return parts.scheme == "https" and bool(parts.hostname) and (host is None or parts.hostname == host)


class OpenverseSearch:
    endpoint = f"https://{API_HOST}/v1/images/"

    def __init__(self, client=None, size=100, clock=time.time):
        self.client, self.size, self.clock = client, size, clock
        self.cache = OrderedDict()     # titre normalisé -> (instant, jeton ou None)
        self.photos = OrderedDict()    # jeton -> {"image", "preview", "credit", "credit_url"}
        self.lock = threading.Lock()

    def get(self, url, **kw):
        return (self.client or httpx).get(url, headers={"User-Agent": USER_AGENT}, timeout=8, **kw)

    def hits(self, query):
        params = {"q": query, "license_type": "commercial,modification", "category": "photograph",
                  "mature": "false", "page_size": 10}
        r = self.get(self.endpoint, params=params)
        r.raise_for_status()
        results = r.json().get("results") or []
        # On préfère les images dont le titre ou les tags contiennent un mot de la requête.
        stems = [w[:5] for w in query.split() if len(w) > 2]
        def relevant(hit):
            text = plain(" ".join([hit.get("title") or ""] + [t.get("name", "") for t in hit.get("tags") or []]))
            return any(s in text for s in stems)
        return sorted(results, key=lambda hit: not relevant(hit))

    def download(self, hit):
        url = hit.get("thumbnail")
        if not safe_url(url, API_HOST):
            return None
        r = self.get(url, follow_redirects=False)
        r.raise_for_status()
        if len(r.content) > MAX_DOWNLOAD:
            return None
        try:
            return reencode(r.content, MEAL_PHOTO_SIZE)
        except ValueError:
            log.warning("Image Openverse illisible : %s", hit.get("id"))
            return None

    @staticmethod
    def credit(hit):
        creator = str(hit.get("creator") or "Auteur inconnu")[:60]
        licence = "CC0" if hit.get("license") == "cc0" else (
            "domaine public" if hit.get("license") == "pdm" else
            f"CC {str(hit.get('license', '')).upper()} {hit.get('license_version') or ''}".strip())
        source = hit.get("foreign_landing_url")
        return f"{creator} · {licence}", source if safe_url(source) else "https://openverse.org"

    def fetch(self, title):
        for query in queries(title):
            for hit in self.hits(query)[:3]:
                if not PHOTO_TOKEN.fullmatch(f"openverse:{hit.get('id', '')}"):
                    continue
                image = self.download(hit)
                if image:
                    credit, url = self.credit(hit)
                    return {"image": f"openverse:{hit['id']}", "preview": image, "credit": credit, "credit_url": url}
        return None

    def search(self, title):
        """Renvoie {"image": jeton, "preview": data URL, "credit", "credit_url"} ou None."""
        key = plain(title)[:100]
        if not key:
            return None
        now = self.clock()
        with self.lock:
            cached = self.cache.get(key)
            if cached and now - cached[0] < CACHE_LIFE and (cached[1] is None or cached[1] in self.photos):
                self.cache.move_to_end(key)
                return self.photos[cached[1]] if cached[1] else None
        try:
            result = self.fetch(title)  # hors verrou : un appel réseau lent ne bloque pas les autres
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            log.warning("Recherche Openverse impossible pour « %s »", key)
            return None  # pas de mise en cache : on réessaiera plus tard
        with self.lock:
            self.cache[key] = (now, result["image"] if result else None)
            if result:
                self.photos[result["image"]] = result
            for store in (self.cache, self.photos):
                while len(store) > self.size:
                    store.popitem(last=False)
        return result

    def resolve(self, token):
        """Photo téléchargée correspondant à un jeton déjà proposé, ou None (expirée ou inconnue)."""
        with self.lock:
            return self.photos.get(token)


def search_from_env():
    enabled = os.getenv("BLABLACOOK_IMAGE_SEARCH", "on").strip().lower() not in ("off", "0", "false", "non")
    return OpenverseSearch() if enabled else None
