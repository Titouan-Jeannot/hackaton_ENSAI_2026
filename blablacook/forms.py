from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from .imagesearch import PHOTO_TOKEN
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
    "profile_diets": ["Aucun", "Végétarien", "Vegan", "Halal", "Casher", "Sans gluten", "Sans lactose", "Autre"],
    "photos": ["", "citron", "tomate", "olive", "orange"],
}
Place = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Lat = Annotated[float, Field(ge=-90, le=90)]
Lng = Annotated[float, Field(ge=-180, le=180)]


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


class VerificationCode(Input):
    code: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{6}$")]


class Profile(Input):
    name: Name = "Étudiant"
    bio: Short = ""
    photo: str = ""
    public_photo: bool = False
    hidden_guest: bool = False
    diet: Literal[("", *OPTIONS["profile_diets"])] = ""
    allergies: Short = ""
    age: Annotated[int, Field(strict=True, ge=1, le=120)] | None = None
    gender: Literal["", "Femme", "Homme", "Non-binaire", "Autre"] = ""
    home_address: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    home_lat: Lat | None = None
    home_lng: Lng | None = None

    @model_validator(mode="after")
    def coherent_home(self):
        located = self.home_lat is not None and self.home_lng is not None
        if self.home_address and not located:
            raise ValueError("Choisis ton adresse dans la liste de suggestions.")
        if not self.home_address and (self.home_lat is not None or self.home_lng is not None):
            raise ValueError("Adresse manquante.")
        return self


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
    address: Place
    lat: Lat
    lng: Lng
    city: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ""
    start: AwareDatetime
    duration: Annotated[int, Field(strict=True, gt=0, le=10080)] | None = None
    check_at: AwareDatetime
    minimum: Annotated[int, Field(strict=True, ge=1)]
    maximum: Annotated[int, Field(strict=True, ge=1)]
    women: bool = False

    @field_validator("image")
    @classmethod
    def valid_image(cls, value):
        if PHOTO_TOKEN.fullmatch(value):
            return value  # remplacé par la photo téléchargée au moment de la publication
        return local_photo(value or "table", OPTIONS["images"], (960, 640))

    @model_validator(mode="after")
    def validate_offer(self):
        for key in ("allergens", "diets", "languages"):
            if set(getattr(self, key)) - set(OPTIONS[key]):
                raise ValueError("Sélection inconnue.")
        if not self.allergens and not self.uncertain:
            raise ValueError("Indiquez les allergènes connus ou cochez « Information incertaine ».")
        if not self.languages or not self.diets or self.mood not in OPTIONS["moods"]:
            raise ValueError("Vérifiez la langue, le régime et l’ambiance.")
        if self.minimum > self.maximum or self.check_at >= self.start:
            raise ValueError("Vérifiez le minimum, le maximum et la date limite pour atteindre le minimum (avant le début du repas).")
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

