"""Suggestions de repas « Pour toi » d’après le profil : allergies, régime, préférences et adresse.

1. Filtre (jamais de compromis sur la santé) : un repas est écarté s’il contient un allergène du profil, si ses
   allergènes sont incertains alors que le membre a déclaré des allergies, ou s’il ne respecte pas son régime.
2. Score : régime explicitement respecté, ambiance et activité préférées, langue commune, proximité, date proche.
   Chaque point gagné produit une raison lisible, affichée sur la carte.
"""
from .geo import distance_km
from .reference import DIET_NEEDS, DIET_WITHOUT

RADIUS_KM = 10      # au-delà, un repas n’est pas suggéré à un membre qui a renseigné son adresse
SOON = 3 * 86400    # un repas dans les trois jours gagne un point
COUNT = 6


def diet_ok(diet, meal):
    """Le repas respecte-t-il le régime déclaré ? (régime vide, « Aucun » ou « Autre » : pas de contrainte)."""
    if diet in DIET_NEEDS:
        return bool(DIET_NEEDS[diet] & set(meal.diets))
    if diet in DIET_WITHOUT:
        return not meal.uncertain and DIET_WITHOUT[diet] not in meal.allergens
    return True


def safe_for(user, meal):
    """Raison d’exclusion, ou None si le repas convient au profil."""
    risky = set(user.allergens) & set(meal.allergens)
    if risky:
        return "Contient " + ", ".join(sorted(risky))
    if user.allergens and meal.uncertain:
        return "Allergènes incertains"
    if not diet_ok(user.diet, meal):
        return "Régime non respecté"
    return None


def score(user, meal, now, home=None):
    """(points, raisons, distance en km ou None) pour un repas qui a passé le filtre."""
    points, reasons, km = 0.0, [], None
    if user.diet in DIET_WITHOUT or user.diet in meal.diets:
        points += 3
        reasons.append(user.diet)
    elif user.diet in DIET_NEEDS:  # respecté par un régime plus strict (ex. halal → repas végétarien)
        points += 2
        via = next(d for d in meal.diets if d in DIET_NEEDS[user.diet])
        reasons.append(f"{user.diet} (repas {via.lower()})")
    if user.allergens:
        points += 1
        reasons.append("Sans " + ", ".join(a.lower() for a in user.allergens))
    if meal.mood in user.moods:
        points += 2
        reasons.append("Ambiance " + meal.mood.lower())
    if meal.activity and meal.activity in user.activities:
        points += 2
        reasons.append(meal.activity)
    spoken = set(user.languages)
    if spoken:
        common = spoken & set(meal.languages)
        if common - {"Français"}:
            points += 1
            reasons.append("En " + " / ".join(sorted(c.lower() for c in common - {"Français"})))
        elif not common and "Non renseigné" not in meal.languages:
            points -= 2
    if home:
        km = distance_km(home[0], home[1], meal.area_lat, meal.area_lng)
        points += 3 * max(0.0, 1 - km / RADIUS_KM)
        reasons.append(f"{km:.1f} km".replace(".", ",") if km >= 1 else f"{round(km * 10) * 100} m")
    if meal.start - now < SOON:
        points += 1
    return points, reasons, km


def rank(user, meals, now):
    """Repas compatibles triés par score décroissant puis par date : [(meal, points, raisons, km)]."""
    home = (user.home_lat, user.home_lng) if user.home_lat is not None and user.home_lng is not None else None
    out = []
    for meal in meals:
        if safe_for(user, meal):
            continue
        points, reasons, km = score(user, meal, now, home)
        if km is not None and km > RADIUS_KM:
            continue
        out.append((meal, points, reasons, km))
    out.sort(key=lambda r: (-r[1], r[0].start))
    return out


def profile_complete(user):
    """Le profil donne-t-il assez d’indices pour personnaliser ? (sert à inviter à le compléter)."""
    return bool(user.diet or user.allergens or user.moods or user.activities) and user.home_lat is not None
