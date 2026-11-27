from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from .photos import local_photo

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2400)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
Stars = Annotated[int, Field(strict=True, ge=1, le=5)]
OPTIONS = {
    "diets": ["Aucun régime particulier", "Végétarien", "Végétalien", "Sans porc"],
    "allergens": ["Gluten", "Crustacés", "Œufs", "Poisson", "Arachides", "Soja", "Lait", "Fruits à coque",
                  "Céleri", "Moutarde", "Sésame", "Sulfites", "Lupin", "Mollusques"],
    "languages": ["Français", "Anglais", "Espagnol", "Italien", "Non renseigné"],
    "moods": ["Conviviale", "Tranquille", "Festive", "Non renseigné"],
    "activities": ["Jeux de société", "Film", "Cuisine ensemble", "Quiz"],
    "reasons": ["Contenu inapproprié", "Comportement préoccupant", "Information erronée", "Autre"],
    "images": ["table", "pasta", "curry", "tacos"],
    "genders": ["Femme", "Homme", "Non-binaire", "Autre"],
    "photos": ["", "citron", "tomate", "olive", "orange"],
}
# Positions fictives en kilomètres depuis le centre du campus.
SECTORS = {"Centre": [0, 0], "Beaulieu": [3, 1], "Villejean": [-3, 2], "Bruz": [-2, -5]}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    email: Name
    password: Annotated[str, Field(min_length=1, max_length=256)]


class Registration(Login):
    name: Name
    password: Annotated[str, Field(min_length=8, max_length=256)]


class Verification(Input):
    token: Name


class Profile(Input):
    name: Name = "Étudiant"
    bio: Short = ""
    photo: str = ""
    public_photo: bool = False
    hidden_guest: bool = False
    diet: Short = ""
    allergies: Short = ""
    age: Annotated[int, Field(strict=True, ge=1, le=120)] | None = None
    gender: Literal["", "Femme", "Homme", "Non-binaire", "Autre"] = ""


    @field_validator("photo")
    @classmethod
    def valid_photo(cls, value):
        return local_photo(value, OPTIONS["photos"], (192, 192))


class MealForm(Input):
    title: Name
    description: Short = ""
    menu: Text
    ingredients: Text
    allergens: list[str] = []
    uncertain: bool = False
    diets: list[str] = ["Aucun régime particulier"]
    languages: list[str] = ["Non renseigné"]
    mood: str = "Non renseigné"
    kind: Literal["Repas seul", "Repas + activité"] = "Repas seul"
    activity: str = ""
    image: str = "table"
    sector: str
    address: Name
    start: AwareDatetime
    duration: Annotated[int, Field(strict=True, gt=0, le=10080)] | None = None
    check_at: AwareDatetime
    minimum: Annotated[int, Field(strict=True, ge=1)]
    maximum: Annotated[int, Field(strict=True, ge=1)]
    women: bool = False

    @field_validator("image")
    @classmethod
    def valid_image(cls, value):
        return local_photo(value, OPTIONS["images"], (960, 640))

    @model_validator(mode="after")
    def validate_offer(self):
        for key in ("allergens", "diets", "languages"):
            if set(getattr(self, key)) - set(OPTIONS[key]):
                raise ValueError("Sélection inconnue.")
        if not self.allergens and not self.uncertain:
            raise ValueError("Indiquez les allergènes connus ou cochez « Information incertaine ».")
        if (not self.languages or not self.diets or self.sector not in SECTORS or
                self.mood not in OPTIONS["moods"]):
            raise ValueError("Vérifiez le secteur, la photo, la langue, le régime et l’ambiance.")
        if self.minimum > self.maximum or self.check_at >= self.start:
            raise ValueError("Vérifiez le minimum, le maximum et l’heure de contrôle.")
        if self.kind == "Repas + activité" and self.activity not in OPTIONS["activities"]:
            raise ValueError("Choisissez une activité.")
        if self.kind == "Repas seul" and self.activity:
            raise ValueError("Une activité nécessite le type « Repas + activité ».")
        return self


class Attendance(Input):
    present: bool


class ReviewForm(Input):
    accueil: Stars | None = None
    ambiance: Stars | None = None
    repas: Stars | None = None
    global_score: Stars | None = None
    comment: Short = ""


class ThreadForm(Input):
    meal: int


class MessageForm(Input):
    body: Text


class ReportForm(Input):
    kind: Literal["meal", "user", "message", "review"]
    target: int
    reason: Name
    comment: Short = ""


class DecisionForm(Input):
    action: Literal["instruire", "classer", "masquer", "suspendre", "neutraliser"]
    reason: Text
