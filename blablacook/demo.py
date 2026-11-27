from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from .access import password_hash
from .db import Address, Base, Booking, DemoBatch, Meal, User, transaction
from .domain import publish
from .forms import MealForm

DEMO_PASSWORD = "Tablée-Démo-26"
PEOPLE = [("camille", "Camille", "Femme", "tomate"), ("ines", "Inès", "Femme", "citron"),
          ("noe", "Noé", "Homme", "olive"), ("lea", "Léa", "Femme", "orange"), ("admin", "Lou", "", "")]


def seed(engine, timestamp, reset=False):
    with transaction(engine) as s:
        batch = s.get(DemoBatch, 1)
        if reset:
            if not batch and s.scalar(select(User.id).limit(1)):
                raise ValueError("Cette base ne porte pas le marqueur de démonstration.")
            for table in reversed(Base.metadata.sorted_tables):
                s.execute(delete(table))
            s.expunge_all()
            batch = None
        if batch and timestamp <= batch.last_start:
            return False
        if not batch and s.scalar(select(User.id).limit(1)):
            return False
        users = []
        for login, name, gender, photo in PEOPLE:
            email = login + "@campus.test"
            if batch:
                users.append(s.scalar(select(User).where(User.email == email)))
                continue
            u = User(name=name, email=email, gender=gender, photo=photo, public_photo=True,
                     bio="J’aime cuisiner et découvrir de nouvelles recettes.", password=password_hash(DEMO_PASSWORD),
                     verified=True, admin=login == "admin")
            s.add(u)
            users.append(u)
        s.flush()
        now = datetime.fromtimestamp(timestamp, UTC)
        first = (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        recipes = [
            ("Pasta al pomodoro", "Rigatoni, tomates rôties & basilic frais", "Pâtes de blé, tomates, ail, basilic, parmesan", "pasta", "Centre", ["Gluten", "Lait"], "", 0),
            ("Curry de légumes & jeux", "Curry de saison au lait de coco, riz parfumé", "Pois chiches, patate douce, coco, riz", "curry", "Beaulieu", [], "Jeux de société", 1),
            ("Tacos entre étudiantes", "Tacos de haricots noirs, citron vert et salsa", "Tortillas de maïs, haricots, tomate, citron vert", "tacos", "Villejean", [], "", 3),
        ]
        for day, (title, menu, ingredients, img, sector, allergens, activity, host) in enumerate(recipes):
            start = first + timedelta(days=day)
            data = MealForm(title=title, description="On partage un repas fait maison autour de la même table.",
                            menu=menu, ingredients=ingredients, image=img, sector=sector, address=f"{12+day} rue des Marmites fictives",
                            check_at=start-timedelta(hours=6), start=start, minimum=2, maximum=4+day,
                            allergens=allergens, uncertain=not allergens, diets=["Végétarien"], languages=["Français", "Anglais"] if day==1 else ["Français"],
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
            m = Meal(title=title, host=users[0].id, menu="Repas de saison", ingredients="Légumes, pain", sector="Bruz",
                     start=start, check_at=start-6*3600, minimum=1, maximum=1, allergens=["Gluten"], uncertain=False,
                     diets=["Végétarien"], languages=["Français"], mood="Tranquille", kind="Repas seul", activity="", image=image)
            s.add(m)
            s.flush()
            s.add(Address(meal=m.id, address="8 allée des Cuillères fictives"))
            s.add(Booking(meal=m.id, guest=users[1].id, status="ACCEPTED", created=start-86400, changed=start-86000))
        if batch is None:
            batch = DemoBatch(id=1)
            s.add(batch)
        batch.last_start = (first + timedelta(days=2)).timestamp()
        s.commit()
    return True
