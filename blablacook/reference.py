"""Listes de référence (source unique) : elles remplissent les tables de référence de la base et les formulaires."""

ALLERGENS = ["Gluten", "Crustacés", "Œufs", "Poisson", "Arachides", "Soja", "Lait", "Fruits à coque",
             "Céleri", "Moutarde", "Sésame", "Sulfites", "Lupin", "Mollusques"]

# Régimes qu’un hôte peut déclarer pour un repas, et régimes qu’un membre peut déclarer dans son profil.
MEAL_DIETS = ["Aucun régime particulier", "Végétarien", "Végétalien", "Sans porc", "Halal", "Casher"]
PROFILE_DIETS = ["Aucun", "Végétarien", "Végétalien", "Sans porc", "Halal", "Casher", "Sans gluten", "Sans lactose",
                 "Autre"]
DIETS = list(dict.fromkeys(MEAL_DIETS + PROFILE_DIETS))

LANGUAGES = ["Français", "Anglais", "Espagnol", "Italien", "Non renseigné"]
MOODS = ["Conviviale", "Tranquille", "Festive", "Non renseigné"]
ACTIVITIES = ["Jeux de société", "Film", "Cuisine ensemble", "Quiz"]

# Compatibilité d’un régime du profil avec un repas.
#  - régimes « déclarés » : le repas doit porter l’un des régimes listés ;
#  - régimes « par allergène » : le repas ne doit pas contenir l’allergène et ses allergènes doivent être certains.
DIET_NEEDS = {
    "Végétarien": {"Végétarien", "Végétalien"},
    "Végétalien": {"Végétalien"},
    "Sans porc": {"Sans porc", "Végétarien", "Végétalien", "Halal", "Casher"},
    "Halal": {"Halal", "Végétarien", "Végétalien"},
    "Casher": {"Casher", "Végétarien", "Végétalien"},
}
DIET_WITHOUT = {"Sans gluten": "Gluten", "Sans lactose": "Lait"}
