import base64
import binascii
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


def local_photo(value, choices, size):
    if value in choices:
        return value
    header, separator, encoded = value.partition(",")
    if not separator or header not in {"data:image/jpeg;base64", "data:image/png;base64", "data:image/webp;base64"} or len(encoded) > 4*1024*1024:
        raise ValueError("Choisissez une photo JPEG, PNG ou WebP de 3 Mio maximum.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except binascii.Error as exc:
        raise ValueError("Impossible de lire cette photo.") from exc
    return reencode(raw, size)


def reencode(raw, size):
    """Réduit l’image et la réencode en JPEG sans métadonnées ; renvoie une data URL."""
    try:
        with Image.open(BytesIO(raw), formats=("JPEG", "PNG", "WEBP")) as image:
            if image.width * image.height > 16_000_000:
                raise ValueError("La photo dépasse 16 mégapixels.")
            image.thumbnail(size)
            clean = ImageOps.exif_transpose(image).convert("RGB")
            output = BytesIO()
            clean.save(output, format="JPEG", quality=82, exif=b"", icc_profile=None)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Impossible de lire cette photo.") from exc
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
