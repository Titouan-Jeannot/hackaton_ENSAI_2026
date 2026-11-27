"""Calculs géographiques : distances et zone approximative publique d'un repas."""
import math
import secrets

EARTH_KM = 6371.0088
AREA_RADIUS = 500          # rayon du cercle public, en mètres
AREA_MAX_SHIFT = 0.7       # le centre public est décalé d'au plus 70 % du rayon : le lieu reste dans le cercle
ADDRESS_REVEAL = 3600      # l'adresse exacte est dévoilée aux invités acceptés 1 h avant le début

_random = secrets.SystemRandom()


def distance_km(lat1, lng1, lat2, lng2):
    """Distance à vol d'oiseau (formule de haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(h))


def approximate_area(lat, lng, radius=AREA_RADIUS, rng=_random):
    """Centre public tiré au hasard autour du lieu exact.

    Sans ce décalage, le centre du cercle affiché révélerait l'adresse. Le tirage est uniforme dans un disque
    de rayon AREA_MAX_SHIFT × radius ; il est fait une seule fois à la publication puis stocké, pour qu'on ne
    puisse pas retrouver le point exact en moyennant plusieurs affichages.
    """
    shift = radius * AREA_MAX_SHIFT * math.sqrt(rng.random())
    angle = rng.uniform(0, 2 * math.pi)
    dlat = shift * math.cos(angle) / 111_320
    dlng = shift * math.sin(angle) / (111_320 * max(math.cos(math.radians(lat)), 1e-6))
    return round(lat + dlat, 6), round(lng + dlng, 6)
