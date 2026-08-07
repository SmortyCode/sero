"""Bild-Upload über die eBay Media API (NICHT Trading API / UploadSiteHostedPictures —
die ist deprecated und wird am 30.09.2026 abgeschaltet).

Endpoint (gegen Production verifiziert am 11.06.2026):
POST https://apim.ebay.com/commerce/media/v1_beta/image/create_image_from_file
(multipart/form-data, Feld "image", ein Bild pro Call). Antwort 201 mit
imageUrl im Body; Location-Header-Fallback bleibt drin.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image, ImageOps

from bot.config import EBAY_APIM
from bot.ebay.auth import EbayClient

log = logging.getLogger("ebay.media")

MEDIA_IMAGE_URL = f"{EBAY_APIM}/commerce/media/v1_beta/image/create_image_from_file"
MAX_BYTES = 8 * 1024 * 1024  # eBay-Limit ~8 MB
MIN_EDGE = 500  # eBay-Minimum: längste Kante >= 500px


class MediaError(Exception):
    pass


def prepare_image_for_ebay(path: str | Path) -> bytes:
    """JPEG, EXIF-Rotation angewendet, < 8 MB. Wirft MediaError wenn das Bild zu klein ist."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    if max(img.size) < MIN_EDGE:
        raise MediaError(
            f"Bild {Path(path).name} ist zu klein ({img.size[0]}x{img.size[1]}) — "
            f"eBay verlangt mind. {MIN_EDGE}px auf der längsten Kante."
        )
    for quality in (92, 85, 75, 65):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= MAX_BYTES:
            return buf.getvalue()
    raise MediaError(f"Bild {Path(path).name} lässt sich nicht unter 8 MB komprimieren.")


async def upload_image(client: EbayClient, path: str | Path, user_id: int) -> str:
    """Lädt ein Bild hoch und gibt die EPS-imageUrl zurück."""
    data = prepare_image_for_ebay(path)
    resp = await client.request(
        "POST",
        MEDIA_IMAGE_URL,
        auth="user",
        user_id=user_id,
        files={"image": (Path(path).name, data, "image/jpeg")},
    )
    if resp.status_code not in (200, 201):
        raise MediaError(f"Media-Upload fehlgeschlagen ({resp.status_code}): {resp.text[:500]}")

    image_url = None
    try:
        body = resp.json()
        image_url = body.get("imageUrl") or (body.get("image") or {}).get("imageUrl")
    except Exception:
        pass

    if not image_url:
        # Variante 2: Location-Header zeigt auf die Image-Ressource -> getImage
        location = resp.headers.get("Location")
        if not location:
            raise MediaError(f"Media-Upload: weder imageUrl noch Location-Header in Antwort: {resp.text[:300]}")
        if location.startswith("/"):
            location = EBAY_APIM + location
        get_resp = await client.request("GET", location, auth="user", user_id=user_id)
        if get_resp.status_code != 200:
            raise MediaError(f"getImage fehlgeschlagen ({get_resp.status_code}): {get_resp.text[:300]}")
        image_url = get_resp.json().get("imageUrl")

    if not image_url:
        raise MediaError("Media API hat keine imageUrl geliefert.")
    log.info("Bild hochgeladen: %s -> %s", Path(path).name, image_url)
    return image_url
