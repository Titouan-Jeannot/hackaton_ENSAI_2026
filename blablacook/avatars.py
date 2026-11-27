"""Portraits illustrés originaux pour les profils de démonstration (générés localement, sans réseau)."""
import base64
from io import BytesIO

from PIL import Image, ImageDraw

SKINS = ["#f5d0b5", "#e8b896", "#c98e66", "#a86b45", "#7a4a2e", "#f1c7a3"]
HAIRS = ["#2b1d14", "#4a2f1d", "#8a5a2b", "#c99a4e", "#1b1b1b", "#a33b20"]
BACKS = ["#f2d7a6", "#cfe3d4", "#f6c9b8", "#d6d9f2", "#e9dcf0", "#d9ecf2", "#f4e3b2", "#e3efc8"]
SHIRTS = ["#344d38", "#b94427", "#3d5a80", "#7b4b94", "#d08c2f", "#2f6f73", "#5b5b5b", "#a73c24"]


def portrait(skin, hair, back, shirt, style="short", glasses=False, size=192):
    """Dessine un buste stylisé. style : short, long, bun, curly, bald."""
    s = 4 * size  # dessin en grand puis réduction, pour un rendu lissé
    img = Image.new("RGB", (s, s), back)
    d = ImageDraw.Draw(img)
    u = s / 100
    if style == "long":
        d.rounded_rectangle([26*u, 22*u, 74*u, 80*u], radius=22*u, fill=hair)
    d.ellipse([16*u, 74*u, 84*u, 128*u], fill=shirt)                      # épaules
    d.rectangle([43*u, 58*u, 57*u, 78*u], fill=skin)                      # cou
    d.ellipse([30*u, 22*u, 70*u, 66*u], fill=skin)                        # visage
    d.ellipse([27*u, 40*u, 33*u, 50*u], fill=skin)                        # oreilles
    d.ellipse([67*u, 40*u, 73*u, 50*u], fill=skin)
    if style in ("short", "long", "bun"):
        d.chord([29*u, 17*u, 71*u, 52*u], 180, 360, fill=hair)
        d.pieslice([29*u, 20*u, 50*u, 44*u], 180, 270, fill=hair)
    if style == "bun":
        d.ellipse([41*u, 6*u, 59*u, 23*u], fill=hair)
    if style == "curly":
        for x, y in [(32, 30), (40, 22), (50, 19), (60, 22), (68, 30), (36, 25), (64, 25)]:
            d.ellipse([(x-8)*u, (y-8)*u, (x+8)*u, (y+8)*u], fill=hair)
    for x in (42, 58):                                                     # yeux
        d.ellipse([(x-2.2)*u, 42*u, (x+2.2)*u, 46.5*u], fill="#2a211b")
    d.arc([43*u, 49*u, 57*u, 58*u], 20, 160, fill="#8c3b2a", width=int(1.6*u))  # sourire
    for x in (37, 63):                                                     # joues
        d.ellipse([(x-3.5)*u, 49*u, (x+3.5)*u, 54*u], fill="#f0a89a")
    if glasses:
        for x in (42, 58):
            d.ellipse([(x-6)*u, 38.5*u, (x+6)*u, 50*u], outline="#2a211b", width=int(1.2*u))
        d.line([48*u, 44*u, 52*u, 44*u], fill="#2a211b", width=int(1.2*u))
    img = img.resize((size, size), Image.LANCZOS)
    out = BytesIO()
    img.save(out, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii")
