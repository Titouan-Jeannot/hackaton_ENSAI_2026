from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from .access import password_hash
from .avatars import BACKS, HAIRS, SHIRTS, SKINS, portrait
from .db import (Activity, Address, Allergen, Base, Booking, DemoBatch, Diet, Language, Meal, Mood, User, label, labels,
                 meal_labels, transaction, REFERENCE)
from .domain import join_group_chat, publish
from .forms import MealForm
from .geo import AREA_RADIUS, approximate_area

DEMO_PASSWORD = "Tablée-Démo-26"
# Coordonnées réelles de quartiers de Rennes et de Bruz ; les numéros et noms de rue sont fictifs.
PLACES = {"Centre": (48.1113, -1.6800, "Rennes"), "Beaulieu": (48.1197, -1.6383, "Rennes"),
          "Villejean": (48.1215, -1.7040, "Rennes"), "Bruz": (48.0466, -1.7428, "Bruz")}

# (identifiant, prénom, genre, âge, régime, allergies, lieu, bio, portrait)
# portrait = (peau, cheveux, fond, haut, coiffure, lunettes) : indices dans les palettes d’avatars.py
PEOPLE = [
    ("camille", "Camille", "Femme", 22, "Végétarien", "", "Centre",
     "Étudiante en M1 de statistique. Je cuisine italien dès que j’ai un moment et j’adore les grandes tablées.", (0, 1, 2, 1, "long", False)),
    ("ines", "Inès", "Femme", 20, "Halal", "Fruits à coque", "Villejean",
     "En L3 de biologie, toujours partante pour goûter de nouvelles recettes et rencontrer du monde.", (2, 0, 1, 2, "bun", False)),
    ("noe", "Noé", "Homme", 23, "Aucun", "", "Beaulieu",
     "Ingénieur en dernière année, spécialiste autoproclamé des pâtes carbonara. Je ramène toujours le dessert.", (1, 1, 3, 0, "short", True)),
    ("lea", "Léa", "Femme", 21, "Végétalien", "Soja", "Villejean",
     "Étudiante en psycho, cuisine végétale et jeux de société. Les soirées tranquilles, c’est mon truc.", (0, 5, 4, 5, "long", False)),
    ("admin", "Lou", "", 27, "", "", "Bruz",
     "Modération BlablaCook.", (3, 4, 5, 6, "short", True)),
    ("hugo", "Hugo", "Homme", 22, "Aucun", "", "Villejean",
     "Étudiant en médecine. Mes lasagnes sont célèbres dans tout l’internat.", (0, 3, 6, 3, "curly", False)),
    ("sarah", "Sarah", "Femme", 24, "Sans gluten", "Gluten", "Centre",
     "Doctorante en économie, cœliaque, donc experte en recettes sans gluten qui ont du goût.", (4, 4, 7, 4, "curly", True)),
    ("yanis", "Yanis", "Homme", 21, "Halal", "", "Bruz",
     "En 2e année à l’ENSAI. Crêpes, quiz et bonne humeur garantis.", (3, 0, 0, 7, "short", False)),
    ("chloe", "Chloé", "Femme", 19, "Végétarien", "Lait", "Beaulieu",
     "Première année d’informatique, je découvre Rennes et cherche des gens avec qui partager des repas.", (5, 2, 1, 6, "bun", True)),
    ("mathis", "Mathis", "Homme", 25, "Sans lactose", "Lait", "Centre",
     "En master d’histoire. J’aime les plats mijotés et les longues discussions.", (1, 2, 3, 1, "bald", False)),
    ("amina", "Amina", "Femme", 23, "Halal", "", "Beaulieu",
     "Étudiante en pharmacie. Je cuisine les recettes de ma grand-mère, couscous en tête.", (2, 4, 2, 3, "long", False)),
    ("lucas", "Lucas", "Homme", 20, "Casher", "Arachides", "Villejean",
     "Licence de musicologie, toujours une playlist prête pour le repas.", (0, 0, 7, 0, "curly", False)),
    ("jade", "Jade", "Femme", 22, "Autre", "Œufs", "Bruz",
     "Statisticienne en herbe à l’ENSAI, flexitarienne, fan de cuisine asiatique.", (1, 3, 4, 2, "short", False)),
]
# Préférences du profil : (langues parlées, ambiances préférées, activités préférées).
PREFERENCES = {
    "camille": (["Français", "Italien"], ["Conviviale", "Festive"], ["Cuisine ensemble"]),
    "ines": (["Français", "Anglais"], ["Conviviale"], ["Jeux de société"]),
    "noe": (["Français", "Anglais"], ["Festive"], ["Quiz", "Film"]),
    "lea": (["Français"], ["Tranquille"], ["Jeux de société"]),
    "hugo": (["Français"], ["Conviviale"], ["Film"]),
    "sarah": (["Français", "Espagnol"], ["Tranquille"], []),
    "yanis": (["Français", "Anglais"], ["Festive"], ["Quiz"]),
    "chloe": (["Français"], ["Conviviale"], ["Jeux de société", "Film"]),
    "mathis": (["Français"], ["Tranquille"], ["Film"]),
    "amina": (["Français", "Anglais"], ["Conviviale"], ["Cuisine ensemble"]),
    "lucas": (["Français", "Anglais"], ["Festive"], ["Quiz"]),
    "jade": (["Français", "Anglais"], ["Conviviale"], ["Cuisine ensemble"]),
}
# Petits décalages pour que les adresses de démo d’un même quartier ne se superposent pas.
JITTER = [(0.002, 0.003), (-0.003, 0.002), (0.001, -0.004), (-0.002, -0.002), (0.004, 0.001)]


def seed(engine, timestamp, reset=False):
    with transaction(engine) as s:
        batch = s.get(DemoBatch, 1)
        if reset:
            if not batch and s.scalar(select(User.id).limit(1)):
                raise ValueError("Cette base ne porte pas le marqueur de démonstration.")
            kept = {model.__tablename__ for model in REFERENCE}   # les valeurs de référence restent
            for table in reversed(Base.metadata.sorted_tables):
                if table.name not in kept:
                    s.execute(delete(table))
            s.expunge_all()
            batch = None
        if batch and timestamp <= batch.last_start:
            return False
        if not batch and s.scalar(select(User.id).limit(1)):
            return False
        users = []
        password = None
        for n, (login, name, gender, age, diet, allergies, place, bio, look) in enumerate(PEOPLE):
            email = login + "@campus.test"
            if batch:
                users.append(s.scalar(select(User).where(User.email == email)))
                continue
            password = password or password_hash(DEMO_PASSWORD)
            skin, hair, back, shirt, style, glasses = look
            lat, lng, city = PLACES[place]
            dlat, dlng = JITTER[n % len(JITTER)]
            spoken, moods, activities = PREFERENCES.get(login, ([], [], []))
            u = User(name=name, email=email, gender=gender, age=age, bio=bio, diet_ref=label(s, Diet, diet),
                     allergen_refs=labels(s, Allergen, [allergies] if allergies else []),
                     language_refs=labels(s, Language, spoken), mood_refs=labels(s, Mood, moods),
                     activity_refs=labels(s, Activity, activities),
                     photo=portrait(SKINS[skin], HAIRS[hair], BACKS[back], SHIRTS[shirt], style, glasses),
                     public_photo=True, password=password, verified=True, admin=login == "admin",
                     home_address=f"{10 + n} rue des Tablées fictives, {city}", home_lat=lat + dlat, home_lng=lng + dlng)
            s.add(u)
            users.append(u)
        s.flush()
        now = datetime.fromtimestamp(timestamp, UTC)
        first = (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        recipes = [
            ("Pasta al pomodoro", "Rigatoni, tomates rôties & basilic frais", "Pâtes de blé, tomates, ail, basilic, parmesan", "pasta", "Centre", ["Gluten", "Lait"], "", 0),
            ("Curry de légumes & jeux", "Curry de saison au lait de coco, riz parfumé", "Pois chiches, patate douce, coco, riz", "curry", "Beaulieu", ["Céleri"], "Jeux de société", 1),
            ("Tacos entre étudiantes", "Tacos de haricots noirs, citron vert et salsa", "Tortillas de maïs, haricots, tomate, citron vert", "tacos", "Villejean", [], "", 3),
            ("Lasagnes de l’internat", "Lasagnes aux légumes du marché, salade verte", "Pâtes, courgettes, aubergines, tomates, mozzarella", "pasta", "Villejean", ["Gluten", "Lait"], "Film", 5),
            ("Couscous de grand-mère", "Couscous aux sept légumes, thé à la menthe", "Semoule, carottes, navets, pois chiches, épices", "table", "Beaulieu", ["Gluten", "Céleri"], "", 10),
            ("Soirée crêpes & quiz", "Galettes complètes puis crêpes au caramel", "Farine de sarrasin, œufs, lait, beurre salé", "table", "Bruz", ["Gluten", "Œufs", "Lait"], "Quiz", 7),
        ]
        diets = {"Curry de légumes & jeux": ["Végétalien", "Halal"], "Tacos entre étudiantes": ["Végétalien"],
                 "Couscous de grand-mère": ["Végétarien", "Halal"]}
        for day, (title, menu, ingredients, img, place, allergens, activity, host) in enumerate(recipes):
            start = first + timedelta(days=day % 3, hours=day // 3)
            lat, lng, city = PLACES[place]
            data = MealForm(title=title, description="On partage un repas fait maison autour de la même table.",
                            menu=menu, ingredients=ingredients, image=img, city=city, lat=lat, lng=lng,
                            address=f"{12+day} rue des Marmites fictives, {city}",
                            check_at=start-timedelta(hours=6), start=start, minimum=2, maximum=4+day % 3,
                            allergens=allergens, uncertain=not allergens, diets=diets.get(title, ["Végétarien"]), languages=["Français", "Anglais"] if day==1 else ["Français"],
                            mood="Conviviale" if day != 2 else "Tranquille", activity=activity,
                            kind="Repas + activité" if activity else "Repas seul", women=day==2)
            owner = users[host]
            if owner and not owner.suspended and (not data.women or owner.gender == "Femme"):
                publish(s, owner, data, timestamp)
        # Deux tables à rejouer immédiatement : annulation tardive et présences après la fin.
        for title, offset, image in [("Soupe du soir", 2, "table"), ("Retour de la tablée de la veille", -24, "pasta")]:
            if not users[0] or not users[1] or users[0].suspended or users[1].suspended:
                continue
            start = timestamp + offset*3600
            lat, lng, city = PLACES["Bruz"]
            area_lat, area_lng = approximate_area(lat, lng)
            m = Meal(title=title, host=users[0].id, menu="Repas de saison", ingredients="Légumes, pain", city=city,
                     area_lat=area_lat, area_lng=area_lng, area_radius=AREA_RADIUS,
                     start=start, check_at=start-6*3600, minimum=1, maximum=1, uncertain=False, kind="Repas seul", image=image,
                     **meal_labels(s, allergens=["Gluten"], diets=["Végétarien"], languages=["Français"],
                                   mood="Tranquille", activity=""))
            s.add(m)
            s.flush()
            s.add(Address(meal=m.id, address="8 allée des Cuillères fictives, Bruz", lat=lat, lng=lng))
            s.add(Booking(meal=m.id, guest=users[1].id, status="ACCEPTED", created=start-86400, changed=start-86000))
            join_group_chat(s, m, users[1].id, start-86000)
        if batch is None:
            batch = DemoBatch(id=1)
            s.add(batch)
        batch.last_start = (first + timedelta(days=2, hours=(len(recipes) - 1) // 3)).timestamp()
        s.commit()
    return True
