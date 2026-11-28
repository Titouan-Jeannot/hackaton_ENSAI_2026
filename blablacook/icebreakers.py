"""Brise-glace : deux questions pour lancer la discussion, aussi précises que possible.

Sources, de la plus personnelle à la plus générale :
  1. « perso » : la présentation PUBLIQUE des autres participants (études, passions, plats cités) et le menu ;
  2. « contexte » : le moment (ce soir, demain, après le repas), l’activité, l’ambiance, la langue, la tablée,
     et les préférences du membre qui écrit (formulées à la première personne : c’est lui qui les partage) ;
  3. « général » : questions universelles autour de la cuisine.
Confidentialité : les allergies, le régime et les préférences des AUTRES ne sont jamais utilisés.
L’ordre est stable pour une conversation (graine = id du fil) ; « Autres idées » avance d’un cran (`round`).
"""
import random
from datetime import datetime, timezone

from .domain import end

try:
    from zoneinfo import ZoneInfo
    LOCAL = ZoneInfo("Europe/Paris")
except Exception:  # pas de base de fuseaux : l’heure UTC reste une bonne approximation
    LOCAL = timezone.utc

GENERAL = [
    "Quel est le plat de ton enfance que tu pourrais manger tous les jours ?",
    "Tu es plutôt team sucré ou team salé ?",
    "Quelle recette de famille aimerais-tu apprendre ?",
    "Quel plat de ta région ou de ton pays recommanderais-tu à tout le monde ?",
    "Quel est ton plus beau fiasco en cuisine ?",
    "Si tu ouvrais un restaurant, il servirait quoi ?",
    "Le meilleur repas de ta vie, c’était où ?",
    "Un ingrédient que tu mets partout ?",
]

# Menu (titre, menu, ingrédients, description) : mot-clé → question.
MENU = [
    (("carbonara",), "Carbonara : avec ou sans crème ? Attention, sujet sensible !"),
    (("lasagne",), "Lasagnes : la meilleure part, c’est le coin croustillant, non ?"),
    (("risotto",), "Tu as déjà réussi un risotto ? Il paraît qu’il faut remuer sans arrêt…"),
    (("pâtes", "pasta", "rigatoni", "spaghetti", "penne", "tagliatelle"), "Pâtes : team al dente ou bien cuites ?"),
    (("curry",), "Curry : tu le préfères doux ou bien relevé ?"),
    (("taco",), "Tacos : tortilla de maïs ou de blé ?"),
    (("couscous",), "Couscous : avec ou sans raisins secs ? Le grand débat !"),
    (("galette", "crêpe"), "Galette complète ou crêpe au caramel beurre salé ?"),
    (("pizza",), "Ananas sur la pizza : oui ou non ?"),
    (("soupe", "velouté"), "Soupe bien lisse ou avec des morceaux ?"),
    (("cèpe", "champignon"), "Tu sais reconnaître les champignons, ou tu fais confiance au marché ?"),
    (("piment", "harissa", "épice", "épices"), "Ton seuil de piment, sur 10 ?"),
    (("menthe",), "Thé à la menthe : bien sucré ou pas du tout ?"),
    (("tiramisu", "gâteau", "caramel", "mousse", "tarte", "dessert"), "Tu gardes toujours de la place pour le dessert ?"),
    (("parmesan", "mozzarella", "fromage", "comté"), "Si tu ne devais garder qu’un seul fromage ?"),
]

# Présentation publique d’un participant : mot-clé → question qui lui est adressée ({name}).
BIO = [
    (("lasagne",), "{name}, tu dis que tes lasagnes sont célèbres : c’est quoi le secret ?"),
    (("carbonara",), "{name}, spécialiste de la carbonara : crème ou pas crème, on veut ton avis d’expert !"),
    (("couscous", "grand-mère"), "{name}, une recette de ta grand-mère que tu pourrais nous raconter ?"),
    (("crêpe", "galette"), "{name}, tu as une technique secrète pour retourner les crêpes ?"),
    (("dessert",), "{name}, tu ramènes le dessert : c’est quoi ta spécialité ?"),
    (("jeux de société", "jeux"), "{name}, c’est quoi ton jeu de société fétiche ?"),
    (("quiz",), "{name}, en quiz tu es plutôt culture G, musique ou cinéma ?"),
    (("playlist", "musique"), "{name}, c’est toi qui gères la playlist ? Tu nous mets quoi ?"),
    (("italien", "italienne"), "{name}, un plat italien que tout le monde devrait savoir cuisiner ?"),
    (("libanais", "libanaise"), "{name}, un plat libanais à nous faire découvrir ?"),
    (("asiatique",), "{name}, ton plat asiatique préféré, et où le manger à Rennes ?"),
    (("végétal", "vegan", "végétarien"), "{name}, une recette végétale qui convertirait n’importe qui ?"),
    (("mijoté", "mijotés"), "{name}, ton plat mijoté réconfort pour l’hiver ?"),
    (("découvre rennes", "première année"), "{name}, tu découvres Rennes : tu as déjà trouvé ton coin préféré ?"),
]
STUDIES = [
    (("statisti", "ensai"), "la statistique"), (("médecine",), "la médecine"), (("psycho",), "la psycho"),
    (("informatique",), "l’informatique"), (("histoire",), "l’histoire"), (("pharmacie",), "la pharmacie"),
    (("musicologie",), "la musicologie"), (("biologie",), "la biologie"), (("économie",), "l’économie"),
    (("ingénieur",), "ton école d’ingé"), (("droit",), "le droit"),
]
ACTIVITY = {
    "Jeux de société": "Quel est ton jeu de société préféré ? On pourrait l’ajouter à la soirée !",
    "Film": "Quel film proposerais-tu pour la soirée ? Comédie, thriller, dessin animé ?",
    "Quiz": "Ton thème de quiz imbattable, c’est quoi ?",
    "Cuisine ensemble": "En cuisine, tu préfères éplucher, couper ou goûter ?",
}
MOOD = {
    "Festive": "Quelle chanson ne doit surtout pas manquer pour mettre l’ambiance ?",
    "Tranquille": "Pour toi, c’est quoi une soirée tranquille réussie ?",
    "Conviviale": "Qu’est-ce qui rend un repas vraiment convivial pour toi ?",
}
SHARE_ACTIVITY = {  # préférences du membre qui écrit, formulées par lui-même
    "Jeux de société": "Ça vous dirait un jeu de société après le repas ? J’en apporte un !",
    "Film": "Et si on lançait un film après le repas ? J’ai quelques idées.",
    "Quiz": "Petit quiz pour le dessert ? Je prépare quelques questions !",
    "Cuisine ensemble": "Je peux venir un peu en avance pour aider en cuisine ?",
}
WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def has(text, words):
    return any(w in text for w in words)


def when(meal, now):
    """« ce soir », « demain soir », « samedi soir »… (heure de Paris)."""
    start, today = datetime.fromtimestamp(meal.start, LOCAL), datetime.fromtimestamp(now, LOCAL)
    days = (start.date() - today.date()).days
    moment = "midi" if start.hour < 16 else "soir"
    if days == 0:
        return "ce midi" if moment == "midi" else "ce soir"
    if days == 1:
        return f"demain {moment}"
    return f"{WEEKDAYS[start.weekday()]} {moment}"


def first_name(user):
    return user.name.split()[0]


def of(name):
    """« de Hugo », « d’Inès » (élision devant une voyelle)."""
    return ("d’" if name[:1].lower() in "aeiouyàâéèêëîïôöùûüh" else "de ") + name


def candidates(meal, viewer, others, group, now):
    """Trois listes (perso, contexte, général) de (indication, question)."""
    perso, context = [], []
    after = now >= end(meal)
    dish = " ".join([meal.title, meal.menu, meal.ingredients, meal.description]).lower()
    if after:
        perso.append(("Le menu", f"« {meal.title} » : verdict ? Tu le referais chez toi ?"))
    else:
        for words, q in MENU:
            if has(dish, words):
                perso.append(("Le menu", q))
                break
    for other in others:
        bio, name = (other.bio or "").lower(), first_name(other)
        hint = f"D’après la présentation {of(name)}"
        for words, q in BIO:
            if has(bio, words):
                perso.append((hint, q.format(name=name)))
                break
        for words, field in STUDIES:
            if has(bio, words):
                perso.append((hint, f"{name}, tu étudies {field} : qu’est-ce qui te plaît le plus là-dedans ?"))
                break
    if after:
        context += [("Après le repas", "Quel a été ton moment préféré de la soirée ?"),
                    ("Après le repas", "On remet ça ? Qui propose la prochaine table ?")]
    else:
        moment = when(meal, now)
        context.append(("Le rendez-vous", f"Rendez-vous {moment} : tu viens à pied, à vélo ou en transports ?"))
        if group:
            size = len(others) + 1
            context += [("La tablée", f"On sera {size} à table : qui apporte quoi ? Dessert, boisson, pain… ?"),
                        ("La tablée", "Chacun raconte d’où il vient en une phrase ?")]
        elif viewer.id == meal.host:
            context += [("Ton invité", "Qu’est-ce qui t’a donné envie de venir à cette table ?"),
                        ("Ton invité", "Il y a un plat ou un ingrédient que tu n’aimes vraiment pas ?")]
        else:
            context += [("L’hôte", f"Qu’est-ce qui t’a donné envie de cuisiner « {meal.title} » ?"),
                        ("L’hôte", "Je peux apporter quelque chose pour le repas ?")]
        if meal.activity in ACTIVITY:
            context.append(("L’activité", ACTIVITY[meal.activity]))
        mine = [a for a in viewer.activities if a != meal.activity and a in SHARE_ACTIVITY]
        if mine:
            context.append(("Tes préférences", SHARE_ACTIVITY[mine[0]]))
    if meal.mood in MOOD:
        context.append(("L’ambiance", MOOD[meal.mood]))
    for lang in meal.languages:
        if lang not in ("Français", "Non renseigné"):
            context.append(("La langue", f"On pratique un peu l’{lang.lower()} pendant le repas ? "
                                         "Ton mot préféré dans cette langue ?"))
    general = [("Pour lancer", q) for q in GENERAL]
    return perso, context, general


def questions(thread, meal, viewer, others, now, round=0, count=2):
    """`count` questions [{text, hint}] : les plus personnelles d’abord, en variant les sources."""
    rng = random.Random(thread.id)
    perso, context, general = candidates(meal, viewer, others, thread.kind == "group", now)
    for pool in (perso, context, general):
        rng.shuffle(pool)
    queues = {"p": perso, "c": context, "g": general}
    ordered, pattern = [], "pcpcgcpg"
    while any(queues.values()):
        for key in pattern:
            if queues[key]:
                ordered.append(queues[key].pop(0))
    seen, unique = set(), []
    for hint, text in ordered:
        if text not in seen:
            seen.add(text)
            unique.append({"hint": hint, "text": text})
    start = (round * count) % len(unique)
    return [unique[(start + k) % len(unique)] for k in range(min(count, len(unique)))]


def facts(thread, meal, viewer, others, now):
    """Description PUBLIQUE de la situation pour le LLM, et clé de cache. Ni adresse, ni email, ni allergie,
    ni régime, ni préférence privée : seulement le repas, les prénoms et les présentations publiques."""
    after = now >= end(meal)
    group = thread.kind == "group"
    role = "l’hôte" if viewer.id == meal.host else "un·e invité·e"
    lines = [
        f"Conversation : {'chat de groupe du repas, ' + str(len(others) + 1) + ' personnes' if group else 'privée entre l’hôte et un·e invité·e'}.",
        f"Les questions seront proposées à {first_name(viewer)}, qui est {role}.",
        f"Repas : « {meal.title} ». Menu : {meal.menu}.",
        f"Moment : {'le repas a déjà eu lieu' if after else 'repas à venir, ' + when(meal, now)}.",
    ]
    if meal.description:
        lines.append(f"Description de l’hôte : {meal.description[:300]}")
    if meal.city:
        lines.append(f"Ville : {meal.city}.")
    if meal.activity:
        lines.append(f"Activité prévue : {meal.activity}.")
    if meal.mood and meal.mood != "Non renseigné":
        lines.append(f"Ambiance : {meal.mood}.")
    langs = [lang for lang in meal.languages if lang != "Non renseigné"]
    if langs:
        lines.append("Langues de la table : " + ", ".join(langs) + ".")
    if others:
        lines.append("Autres participants (présentation publique) :")
        lines += [f"- {first_name(u)} : « {(u.bio or 'pas de présentation')[:300]} »" for u in others]
    today = datetime.fromtimestamp(now, LOCAL).date().isoformat()
    key = f"{thread.id}:{viewer.id}:{'after' if after else 'before'}:{today}"
    return "\n".join(lines), key
