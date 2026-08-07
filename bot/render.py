"""Produkt-Rendering: Hintergrund entfernen (rembg/u2net, lokal) und das
freigestellte Produkt in einheitlicher Größe auf den SERO-Hintergrund setzen —
damit alle Listings im Profil gleich aussehen.

Der Hintergrund wird per Telegram gesetzt: Bild mit Caption "hintergrund"
an den Bot schicken -> landet in assets/background.png.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageOps

from bot.config import PROJECT_ROOT

log = logging.getLogger("render")

ASSETS_DIR = PROJECT_ROOT / "assets"
BACKGROUND_PATH = ASSETS_DIR / "background.png"

# Produktbox bei DATEI-Hintergrund (mit Logo unten): fast volle Breite, unten
# bis knapp über das Logo (beginnt bei ~78 % Bildhöhe).
BOX_CENTER_X = 0.50
BOX_CENTER_Y = 0.39   # Box von 4 % bis 74 % Bildhöhe
BOX_WIDTH = 0.90
BOX_HEIGHT = 0.70

# Produktbox bei FARB-Hintergrund (kein Logo): maximal, mittig.
FULL_BOX = {"cx": 0.50, "cy": 0.50, "w": 0.92, "h": 0.92}

# Farb-Canvas für Kunden ohne eigenes Template
CANVAS_SIZE = (1600, 1600)
DEFAULT_BG_COLOR = "#FFFFFF"
HEX_COLOR_REGEX = __import__("re").compile(r"^#?[0-9a-fA-F]{6}$")


def normalize_hex_color(text: str) -> str | None:
    text = text.strip()
    if not HEX_COLOR_REGEX.match(text):
        return None
    return "#" + text.lstrip("#").lower()

# Wenn der Freisteller weniger als so viel der Bildfläche übrig lässt,
# hat rembg vermutlich versagt -> Original verwenden.
MIN_CUTOUT_AREA = 0.02

# Pixel mit Alpha darunter zählen nicht zur Produktform — schwache Schatten-/
# Streupixel an einer Seite würden sonst Bounding-Box und Zentrum verschieben.
ALPHA_THRESHOLD = 60

# Slab/Karte auf einfarbigem Hintergrund: rembg frisst durchsichtige Slab-Gehäuse
# an — deshalb hier per Hintergrund-Rand-Trim segmentieren (behält den ganzen Slab).
BG_DIST_THRESH = 45      # Farbabstand vom Rand, ab dem ein Pixel zum Objekt zählt
BG_UNIFORM_MAX = 30      # max. Rand-Abweichung für „einfarbiger Hintergrund“ (Weiß≈0,
                         # unruhige Szene 50+) — schützt vor Mit-Segmentieren des Hintergrunds
BG_MIN_OBJECT_AREA = 0.10  # Objekt muss mind. so viel der Fläche füllen

_session = None


class RenderError(Exception):
    pass


def _get_session():
    global _session
    if _session is None:
        from rembg import new_session  # lazy: Import lädt onnxruntime
        _session = new_session("u2net")
    return _session


def background_available() -> bool:
    return BACKGROUND_PATH.exists()


def save_background(source_path: str | Path) -> tuple[int, int]:
    """Telegram-Foto als neuen Hintergrund übernehmen. Gibt (Breite, Höhe) zurück."""
    ASSETS_DIR.mkdir(exist_ok=True)
    img = Image.open(source_path)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.save(BACKGROUND_PATH, "PNG")
    return img.size


def _has_content_below(bg: Image.Image, band: float = 0.22) -> bool:
    """Hat der Hintergrund im unteren Bereich echten Inhalt (Logo/Grafik)?
    Einfarbige Flächen -> False (Produkt darf das ganze Bild füllen)."""
    try:
        w, h = bg.size
        strip = bg.crop((0, int(h * (1 - band)), w, h)).convert("L")
        lo, hi = strip.getextrema()
        return (hi - lo) > 12          # spürbarer Kontrast = Logo/Motiv vorhanden
    except (ValueError, OSError):
        return True                     # im Zweifel die konservative Logo-Box


def compute_placement(product_size: tuple[int, int], bg_size: tuple[int, int],
                      box: dict | None = None) -> tuple[int, int, int, int]:
    """(neue Breite, neue Höhe, x, y) — Produkt proportional in die Box eingepasst."""
    box = box or {"cx": BOX_CENTER_X, "cy": BOX_CENTER_Y, "w": BOX_WIDTH, "h": BOX_HEIGHT}
    pw, ph = product_size
    bg_w, bg_h = bg_size
    box_w = bg_w * box["w"]
    box_h = bg_h * box["h"]
    scale = min(box_w / pw, box_h / ph)
    new_w = max(1, round(pw * scale))
    new_h = max(1, round(ph * scale))
    x = round(bg_w * box["cx"] - new_w / 2)
    y = round(bg_h * box["cy"] - new_h / 2)
    return new_w, new_h, x, y


def clean_cutout(cutout: Image.Image) -> Image.Image:
    """Freisteller-Alpha säubern: größte Form behalten (Streupixel/Schattenreste weg),
    Löcher füllen, und den dunkel-kontaminierten rembg-Randring wegschneiden, damit
    auf hellem Hintergrund KEIN schwarzer Saum entsteht (z. B. bei Plüsch). Innenkante
    wird sauber gefeathert."""
    import numpy as np
    try:
        from scipy import ndimage
    except Exception:  # noqa: BLE001 — scipy fehlt: ungesäubert weiter
        return cutout

    arr = np.array(cutout)
    if arr.ndim != 3 or arr.shape[2] != 4:
        return cutout
    alpha = arr[:, :, 3]
    mask = alpha >= ALPHA_THRESHOLD
    if not mask.any():
        return cutout

    labels, n = ndimage.label(mask)
    if n > 1:  # nur die größte Form behalten
        sizes = ndimage.sum(mask, labels, range(1, n + 1))
        mask = labels == (int(np.argmax(sizes)) + 1)
    mask = ndimage.binary_fill_holes(mask)

    # Farb-Dekontamination: halbtransparente Randpixel (dunkle rembg-Kante) bekommen
    # die Farbe des nächsten VOLL deckenden Produktpixels -> die Kante blendet zur
    # Produktfarbe statt zu Schwarz, kein dunkler Saum auf hellem Grund mehr.
    solid = (alpha >= 230) & mask
    if solid.any():
        idx = ndimage.distance_transform_edt(~solid, return_distances=False, return_indices=True)
        nearest_rgb = arr[:, :, :3][tuple(idx)]
        edge = mask & ~solid
        rgb = arr[:, :, :3]
        rgb[edge] = nearest_rgb[edge]
        arr[:, :, :3] = rgb

    # Alpha: außerhalb der Form 0, Kante leicht glätten, innen voll deckend
    a = alpha.astype(np.float32)
    a[~mask] = 0.0
    a = ndimage.gaussian_filter(a, sigma=0.6)
    new_alpha = np.clip(a, 0, 255).astype(np.uint8)
    new_alpha[ndimage.binary_erosion(mask, iterations=2)] = 255
    arr[:, :, 3] = new_alpha
    return Image.fromarray(arr, "RGBA")


# --- Karten-/Slab-Erkennung ---
CARD_MIN_RECTANGULARITY = 0.80   # Maske füllt >= 80 % ihres kleinsten Rechtecks
CARD_ASPECT_RANGE = (0.45, 0.88)  # kurze/lange Seite — Karten ~0.71, Slabs ~0.66

# Kanten-Detektor (zuverlässig wie ein Foto-Editor): findet die Karte/den Slab über
# die physische Außenkante — egal ob durchsichtiges Gehäuse oder Illustration.
# Eng auf Karten-Form, damit z. B. ein Game-Boy-Bildschirm nicht als „Karte“ durchgeht.
CARD_EDGE_RECT = 0.85
CARD_EDGE_ASPECT = (0.55, 0.80)


def _min_area_rect(hull_pts):
    """Kleinstes umschließendes (rotiertes) Rechteck per Rotating Calipers.
    Gibt (corners[4,2], (breite, höhe), winkel_grad) zurück."""
    import numpy as np

    pts = np.asarray(hull_pts, dtype=float)
    n = len(pts)
    best = None
    for i in range(n):
        edge = pts[(i + 1) % n] - pts[i]
        norm = float(np.hypot(*edge))
        if norm < 1e-6:
            continue
        ux = edge / norm
        uy = np.array([-ux[1], ux[0]])
        px = pts @ ux
        py = pts @ uy
        minx, maxx, miny, maxy = px.min(), px.max(), py.min(), py.max()
        area = (maxx - minx) * (maxy - miny)
        if best is None or area < best[0]:
            corners = np.array([a * ux + b * uy for a, b in
                                ((minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy))])
            best = (area, corners, (maxx - minx, maxy - miny))
    if best is None:
        return None
    return best[1], best[2]


def _order_corners(c):
    import numpy as np
    c = np.asarray(c, dtype=float)
    s = c.sum(axis=1)
    d = c[:, 0] - c[:, 1]
    return np.array([c[np.argmin(s)], c[np.argmax(d)], c[np.argmax(s)], c[np.argmin(d)]])  # tl,tr,br,bl


def detect_card_by_edges(rgb_img: Image.Image):
    """Karte/Slab über die physische Außenkante erkennen (wie ein Foto-Editor):
    Canny-Kanten → schließen → füllen → größte rechteckige Fläche. Gibt die Maske
    (bool-Array) der KOMPLETTEN Karte/des Slabs zurück, sonst None (-> rembg).
    Funktioniert auch bei durchsichtigem Slab-Gehäuse oder Karten mit Illustration."""
    import numpy as np
    try:
        from scipy import ndimage
        from scipy.spatial import ConvexHull
        from skimage import color, feature
    except Exception:  # noqa: BLE001
        return None

    gray = color.rgb2gray(np.asarray(rgb_img.convert("RGB")))
    edges = feature.canny(gray, sigma=2.5)
    edges = ndimage.binary_dilation(edges, iterations=4)   # Lücken in der Kante schließen
    filled = ndimage.binary_fill_holes(edges)
    filled = ndimage.binary_erosion(filled, iterations=4)  # Dilatation zurücknehmen
    labels, n = ndimage.label(filled)
    if n == 0:
        return None
    sizes = ndimage.sum(filled, labels, range(1, n + 1))
    mask = labels == (int(np.argmax(sizes)) + 1)
    frac = float(mask.mean())
    if not (0.10 < frac < 0.985):   # zu klein / fast ganzes Bild -> keine isolierte Karte
        return None
    mask = ndimage.binary_fill_holes(mask)

    ys, xs = np.nonzero(mask)
    pts = np.column_stack([xs, ys]).astype(float)
    try:
        hull = ConvexHull(pts)
    except Exception:  # noqa: BLE001
        return None
    rect = _min_area_rect(pts[hull.vertices])
    if rect is None:
        return None
    _, (rw, rh) = rect
    if rw < 8 or rh < 8:
        return None
    rectangularity = int(mask.sum()) / (rw * rh)
    aspect = min(rw, rh) / max(rw, rh)
    if rectangularity < CARD_EDGE_RECT:
        return None
    if not (CARD_EDGE_ASPECT[0] <= aspect <= CARD_EDGE_ASPECT[1]):
        return None

    # Saubere Kante: statt der zackigen Kantenmaske das umschließende Rechteck (im
    # Kartenwinkel) füllen -> gerade Ränder, OHNE die Karte zu drehen.
    try:
        from skimage.draw import polygon as sk_polygon
        corners, _ = rect
        clean = np.zeros(mask.shape, dtype=bool)
        rr, cc = sk_polygon(np.asarray(corners)[:, 1], np.asarray(corners)[:, 0], mask.shape)
        clean[rr, cc] = True
        mask = clean
    except Exception:  # noqa: BLE001 — Fallback: ungeglättete Maske
        pass
    log.info("Karte/Slab über Kanten erkannt (Rechteckigkeit %.2f, AR %.2f)",
             rectangularity, aspect)
    return mask


def segment_card_on_uniform_bg(rgb_img: Image.Image) -> Image.Image | None:
    """Slab/Karte auf einfarbigem Hintergrund freistellen, OHNE rembg — der ganze
    Slab (auch durchsichtiges Gehäuse) bleibt erhalten. Nur wenn der Hintergrund
    einigermaßen einfarbig UND das Objekt karten-/slab-förmig ist; sonst None
    (dann übernimmt rembg, z. B. bei unruhigem Hintergrund)."""
    import numpy as np
    try:
        from scipy import ndimage
        from scipy.spatial import ConvexHull
    except Exception:  # noqa: BLE001
        return None

    arr = np.asarray(rgb_img.convert("RGB")).astype(np.int16)
    h, w, _ = arr.shape
    b = max(2, min(h, w) // 100)
    ring = np.concatenate([
        arr[:b, :].reshape(-1, 3), arr[-b:, :].reshape(-1, 3),
        arr[:, :b].reshape(-1, 3), arr[:, -b:].reshape(-1, 3)])
    bg = np.median(ring, axis=0)
    # Rand nicht einfarbig (unruhige Szene)? -> rembg, NICHT den Hintergrund mit-segmentieren
    if float(np.median(np.abs(ring - bg).sum(axis=1))) > BG_UNIFORM_MAX:
        return None

    dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))
    mask = dist > BG_DIST_THRESH
    frac = float(mask.mean())
    if not (BG_MIN_OBJECT_AREA < frac < 0.997):  # zu wenig / komplett gefüllt
        return None

    labels, n = ndimage.label(mask)
    if n == 0:
        return None
    if n > 1:  # größte zusammenhängende Form = der Slab
        sizes = ndimage.sum(mask, labels, range(1, n + 1))
        mask = labels == (int(np.argmax(sizes)) + 1)
    mask = ndimage.binary_fill_holes(mask)  # ganze Slab-Fläche solide

    ys, xs = np.nonzero(mask)
    pts = np.column_stack([xs, ys]).astype(float)
    try:
        hull = ConvexHull(pts)
    except Exception:  # noqa: BLE001
        return None
    rect = _min_area_rect(pts[hull.vertices])
    if rect is None:
        return None
    _, (rw, rh) = rect
    if rw < 8 or rh < 8:
        return None
    rectangularity = int(mask.sum()) / (rw * rh)
    aspect = min(rw, rh) / max(rw, rh)
    if rectangularity < CARD_MIN_RECTANGULARITY:  # Form ist der eigentliche Filter
        return None
    if not (CARD_ASPECT_RANGE[0] <= aspect <= CARD_ASPECT_RANGE[1]):
        return None

    rgba = np.dstack([arr.astype(np.uint8), (mask * 255).astype(np.uint8)])
    log.info("Slab/Karte auf einfarbigem Grund segmentiert (rembg übersprungen, "
             "Rechteckigkeit %.2f, AR %.2f)", rectangularity, aspect)
    return Image.fromarray(rgba, "RGBA")


def straighten_card(rgb_img: Image.Image, cutout: Image.Image) -> Image.Image | None:
    """Wenn das freigestellte Produkt rechteckig & karten-/slab-förmig ist: auf ein
    sauberes, gerades Rechteck ziehen (Schräglage + ausgefranste Kanten weg). Es wird
    minimal nach außen gerundet, damit nichts von der Karte abgeschnitten wird.
    Sonst None -> normaler Freisteller-Pfad."""
    import numpy as np
    try:
        from scipy.spatial import ConvexHull
        from skimage.transform import ProjectiveTransform, warp
    except Exception:  # noqa: BLE001
        return None

    alpha = np.asarray(cutout.split()[-1])
    mask = alpha >= ALPHA_THRESHOLD
    area = int(mask.sum())
    if area < 0.02 * mask.size:
        return None
    ys, xs = np.nonzero(mask)
    pts = np.column_stack([xs, ys]).astype(float)
    try:
        hull = ConvexHull(pts)
    except Exception:  # noqa: BLE001
        return None

    rect = _min_area_rect(pts[hull.vertices])
    if rect is None:
        return None
    corners, (w, h) = rect
    if w < 8 or h < 8:
        return None
    rectangularity = area / (w * h)
    aspect = min(w, h) / max(w, h)
    if rectangularity < CARD_MIN_RECTANGULARITY:
        return None
    if not (CARD_ASPECT_RANGE[0] <= aspect <= CARD_ASPECT_RANGE[1]):
        return None

    # Ecken ordnen + minimal nach außen schieben (Sicherheitsmarge: nichts abschneiden)
    src = _order_corners(corners)           # tl, tr, br, bl
    center = src.mean(axis=0)
    src = center + (src - center) * 1.012

    def _d(a, b):
        return float(np.hypot(*(np.asarray(a) - np.asarray(b))))
    out_w = int(round(max(_d(src[0], src[1]), _d(src[3], src[2]))))
    out_h = int(round(max(_d(src[0], src[3]), _d(src[1], src[2]))))
    if out_w < 8 or out_h < 8:
        return None
    dst = np.array([[0, 0], [out_w, 0], [out_w, out_h], [0, out_h]], dtype=float)

    try:  # skimage >= 0.26
        tform = ProjectiveTransform.from_estimate(dst, src)  # dst -> src (inverse Warp)
        if not tform:  # FailedEstimation ist falsy
            return None
    except AttributeError:
        tform = ProjectiveTransform()
        if not tform.estimate(dst, src):
            return None
    rgb = np.asarray(rgb_img.convert("RGB"))
    warped = warp(rgb, tform, output_shape=(out_h, out_w), order=1, preserve_range=True)
    card = Image.fromarray(warped.astype("uint8"), "RGB").convert("RGBA")
    log.info("Karte/Slab gerade gezogen auf %dx%d (Rechteckigkeit %.2f, AR %.2f)",
             out_w, out_h, rectangularity, aspect)
    return card


def alpha_bbox_and_centroid(cutout: Image.Image) -> tuple[tuple[int, int, int, int], float] | None:
    """Bounding-Box + alpha-gewichteter horizontaler Schwerpunkt der Produktform.

    Nur Pixel mit Alpha >= ALPHA_THRESHOLD zählen — so verschieben Streupixel
    und weiche Schatten an einer Seite das Zentrum nicht mehr.
    """
    import numpy as np

    alpha = np.asarray(cutout.split()[-1], dtype=np.uint32)
    mask = alpha >= ALPHA_THRESHOLD
    if not mask.any():
        return None
    ys, xs = np.nonzero(mask)
    weights = alpha[mask]
    centroid_x = float((xs * weights).sum() / weights.sum())
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    return bbox, centroid_x


def render_product(photo_path: str | Path, out_path: str | Path, *,
                   bg_color: str | None = None, bg_path: str | Path | None = None) -> str:
    """Produkt freistellen und auf den Hintergrund setzen.

    bg_path gesetzt: eigenes Kunden-Hintergrundbild (z.B. Weißton mit Logo) mit Logo-Box.
    bg_color gesetzt: Farb-Canvas, Produkt maximal skaliert.
    beides None: Admin-Template (assets/background.png) mit Logo-Box.
    """
    if bg_path is None and bg_color is None and not background_available():
        raise RenderError("Kein Hintergrund gesetzt (Bild mit Caption 'hintergrund' an den Bot schicken).")
    from rembg import remove  # lazy

    img = Image.open(photo_path)
    _fmt = img.format   # VOR convert() sichern — danach ist es weg
    img = ImageOps.exif_transpose(img).convert("RGBA")

    # 1) Bereits freigestelltes App-Foto (transparentes PNG aus dem Scanner)?
    # Dann NICHT erneut freistellen — das fraß bisher die Kanten an.
    def _has_alpha(im) -> bool:
        try:
            a = im.getchannel("A")
            lo, hi = a.getextrema()
            return lo < 240 and hi >= 250   # echte Transparenz vorhanden
        except (ValueError, OSError):
            return False

    cutout = None
    if (_fmt == "PNG" or str(photo_path).lower().endswith(".png")) and _has_alpha(img):
        cutout = img
        log.info("Render: fertigen Scanner-Cutout übernommen (%s)", Path(photo_path).name)
    if cutout is None:
        # 2) Studio-Freisteller der App (BiRefNet + Rechteck-Vorlage + Aufrichten)
        try:
            from web.cardscan import _cutout as studio_cutout
            tmp_png = Path(out_path).with_name(Path(out_path).stem + "_cut.png")
            if studio_cutout(str(photo_path), str(tmp_png)):
                cutout = Image.open(tmp_png).convert("RGBA")
                log.info("Render: Studio-Freisteller verwendet (%s)", Path(photo_path).name)
        except Exception as e:  # noqa: BLE001 — Fallback unten
            log.warning("Render: Studio-Freisteller nicht verfügbar (%s)", e)
    if cutout is None:
        # 3) Alter Weg als Notnagel
        card_mask = detect_card_by_edges(img)
        if card_mask is not None:
            import numpy as np
            rgba = np.asarray(img.convert("RGBA")).copy()
            rgba[..., 3] = (card_mask * 255).astype(np.uint8)
            cutout = Image.fromarray(rgba, "RGBA")
        else:
            cutout = remove(img, session=_get_session())
        cutout = clean_cutout(cutout)

    stats = alpha_bbox_and_centroid(cutout)
    if not stats:
        raise RenderError("Freisteller hat nichts erkannt (Bild komplett transparent).")
    bbox, centroid_x = stats
    cutout = cutout.crop(bbox)
    centroid_x -= bbox[0]  # Schwerpunkt relativ zum Zuschnitt
    if (cutout.width * cutout.height) < MIN_CUTOUT_AREA * (img.width * img.height):
        raise RenderError("Freisteller-Ergebnis verdächtig klein — Original wird verwendet.")

    if bg_path is not None:
        bg = Image.open(bg_path).convert("RGB")
        # Logo-Box (Produkt sitzt oben, unten bleibt Platz fürs Logo) gilt NUR für
        # echte Template-Bilder. Ein einfarbiger Hintergrund (Weiß/Warmweiß/Schwarz
        # aus der Verkaufs-Vorlage) hat kein Logo — dort füllt das Produkt das Bild,
        # sonst klafft unten eine große leere Fläche (Svens eBay-Listing 02.08.).
        box = None if _has_content_below(bg) else FULL_BOX
    elif bg_color is not None:
        bg = Image.new("RGB", CANVAS_SIZE, bg_color)
        box = FULL_BOX
    else:
        bg = Image.open(BACKGROUND_PATH).convert("RGB")
        box = None  # Logo-Box (Default)
    new_w, new_h, x, y = compute_placement(cutout.size, bg.size, box)
    # Horizontal nicht die Box, sondern den PRODUKT-Schwerpunkt zentrieren —
    # so sitzt das Produkt exakt mittig.
    scale = new_w / cutout.width
    center_x = (box or {"cx": BOX_CENTER_X})["cx"]
    x = round(bg.width * center_x - centroid_x * scale)
    x = max(0, min(x, bg.width - new_w))
    resized = cutout.resize((new_w, new_h), Image.LANCZOS)
    bg.paste(resized, (x, y), resized)
    bg.save(out_path, "JPEG", quality=92)
    log.info("Gerendert: %s -> %s (Produkt %dx%d auf %dx%d)",
             Path(photo_path).name, Path(out_path).name, new_w, new_h, bg.width, bg.height)
    return str(out_path)
