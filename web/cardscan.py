"""Karten-Freisteller + Stapel-Gruppierung für den Scanner.

═══════════════════════════════════════════════════════════════════════════
RENDER-STANDARD (Svens Dauer-Entscheid, 03.08.2026 — FEST, Änderung nur mit
seinem ausdrücklichen Ja; Referenzbild: Exeggutor CGC 10):

  slab   → Aufrichten per ROTATION (minAreaRect/Hough + warpAffine) + enger
           Zuschnitt (Ecken, kanten_trim, tisch_trim, untergrund_trim,
           ggf. Label/Fenster-Box) + belichtung_normalisieren.
           KEINE Perspektiv-Streckung als Normalfall (Sven: „Don't distort,
           just straighten"). Perspektiv nur wenn Symmetrie-Gates greifen
           UND der Slab schon nahezu aufrecht ist (sonst bleibt die Schräge
           im Vision-AABB stecken). Warp selbst: KEINE selektive Nachbearbeitung.
           KEIN rembg danach: klares Case-Plastik sieht für BiRefNet wie
           Hintergrund aus — Label und Karte schweben getrennt (Sven 07.08.,
           CGC Pristine). Tisch/Kork/Filz weg; hartes Plastik-Case
           (Rahmen + Label + Karte) bleibt.
  sleeve → Segmentierer (_cutout): nur die gedruckte Karte, ohne Hülle.
  raw    → Segmentierer (_cutout): die Karte, eng beschnitten.
  sonst  → ORIGINAL behalten. Nie ein schlechtes Bild speichern.

Jedes Ergebnis läuft vor dem Speichern durch bild_ok() — fällt es durch,
bleibt das Original stehen. Drei gescheiterte Kosmetik-Anläufe an einem Tag
(Milchglas, Dunkel-Regeln, Schutzboxen) sind der Grund: Nachbearbeitung
IM Warp erzeugt Artefakte. rembg ist nur für sleeve/raw und als Fallback,
wenn der Warp bei einem Slab reißt — nie auf einem gelungenen Warp.
Wer den Warp selbst anfasst, macht erst tests/test_render_standard.py grün.
═══════════════════════════════════════════════════════════════════════════

- crop_photos: EIN Vision-Blick je Foto (detect_card), dann der Pfad laut
  Standard oben.
- slab_recut: der Warp über die Case-Ecken; eigenständig auch als Rettung
  nach der Analyse, wenn crop_photos den Slab nicht erkannte.
- group_photos: ordnet einen Foto-Stapel physischen Objekten zu (Vorder- und
  Rückseite derselben Karte = EIN Objekt, Vorderseite zuerst).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()   # iPhone-HEIC lesbar machen
except ImportError:
    import logging as _logging
    _logging.getLogger("cardscan").warning(
        "pillow-heif fehlt — HEIC-Fotos können nicht gelesen werden!")

from pathlib import Path

from anthropic import AsyncAnthropic
from PIL import Image, ImageOps

log = logging.getLogger("cardscan")

VISION_MODEL = "claude-sonnet-5"   # Eckpunkte müssen präzise sein — kein Haiku
MAX_BATCH = 24

_client: AsyncAnthropic | None = None


def _anthropic(api_key: str) -> AsyncAnthropic:
    """EIN Client fürs Modul — vorher entstand pro Aufruf ein frischer
    (Full-Scan-Befund 03.08.): jedes Mal neuer Connection-Pool, kein
    Keep-Alive zwischen den Vision-Blicken desselben Scans."""
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=api_key)
    return _client


def _b64(path: str, max_edge: int = 1400) -> str:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img).convert("RGB")
    if max(img.size) > max_edge:
        img.thumbnail((max_edge, max_edge))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=86)
    return base64.standard_b64encode(buf.getvalue()).decode()


def _text_of(resp) -> str:
    """Ersten Text-Block ziehen — Sonnet kann Thinking-Blöcke voranstellen."""
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def _json_of(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rstrip().removesuffix("```").strip()
    if not cleaned.startswith("{"):
        # Prosa vor dem JSON tolerieren
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError(f"keine JSON-Antwort: {cleaned[:120]!r}")
        cleaned = cleaned[start:end + 1]
    return json.loads(cleaned)


DETECT_PROMPT = """Du siehst das Foto einer Sammelkarte. Antworte NUR mit JSON:
{"kind": "...", "corners": [[x,y],[x,y],[x,y],[x,y]], "confidence": "high|low"}

"kind":
- "slab"   = Karte steckt in einem Grading-Case (PSA, CGC, Beckett …) mit Bewertungslabel
- "sleeve" = Karte steckt in einer Schutzhülle oder einem Toploader (Plastik ohne Label)
- "raw"    = lose Karte ohne Plastik
- "other"  = keine einzelne Karte klar erkennbar (z. B. Display, mehrere Karten, unscharf)

"corners": die vier Eckpunkte in PROZENT der Bildbreite (x) und Bildhöhe (y),
Reihenfolge [oben-links, oben-rechts, unten-rechts, unten-links].
- Bei "slab": die AUSSENKANTEN des kompletten HARTEN Plastik-Cases inklusive
  Bewertungslabel — der Slab gehört zum Sammlerstück und bleibt im Bild.
  Eine lose Schutzfolie oder Tüte UM den Case zählt NICHT: die Punkte liegen
  auf den harten Case-Kanten, die Folie bleibt draußen.
  KRITISCH: Tisch, Holz, Kork, Stoff, Hände und Schatten gehören NICHT in die
  Ecken. Lieber 1–2 % zu eng am Case als Tischfläche mitnehmen. Das Case soll
  nach dem Zuschnitt den Rahmen füllen.
- Bei "sleeve": die Kanten der GEDRUCKTEN KARTE SELBST — Hülle/Toploader-Ränder
  liegen AUSSERHALB der Punkte und werden weggeschnitten.
- Bei "raw": die Kartenkanten.
Die Punkte müssen exakt auf den Kanten liegen (Perspektive einbeziehen — die vier
Punkte dürfen ein schiefes Viereck bilden).

Bei "kind"="slab" ZUSÄTZLICH diese zwei Felder (ebenfalls in Prozent):
"label_box": [x0,y0,x1,y1] — nur der BEDRUCKTE BEWERTUNGSZETTEL oben im Case
  (die Papierkarte mit Firmenname und Note), ohne das Plastik darum.
"window_box": [x0,y0,x1,y1] — die KARTE oder das BUCH im Sichtfenster,
  eng an deren Druckkanten, ohne das transparente Plastik darum.

WICHTIG zu allen Koordinaten: IMMER Prozent von 0 bis 100, NIE Pixel.
x=100 ist der rechte Bildrand, y=100 der untere — auch bei Hochformat.
Beispiel für einen bildfüllenden Slab: "corners": [[6,3],[94,4],[93,97],[7,96]],
"label_box": [14,8,86,22], "window_box": [22,30,78,88].
Kein Wert darf über 100 liegen.

"confidence": "high" nur, wenn alle vier Kanten klar erkennbar sind."""


def _prozentwerte_ok(data: dict) -> bool:
    """Alle Koordinaten in [0,100]? Das Modell liefert bei Hochformat-Fotos
    gelegentlich y in PIXELN (gemessen 03.08.: y bis 1275) — solche Antworten
    sind wertlos und dürfen nie in einen Zuschnitt fließen."""
    werte = [v for c in (data.get("corners") or []) for v in c]
    for feld in ("label_box", "window_box"):
        if isinstance(data.get(feld), list):
            werte += data[feld]
    return all(isinstance(v, (int, float)) and 0 <= v <= 100 for v in werte)


async def detect_card(client: AsyncAnthropic, path: str) -> dict | None:
    try:
        data_b64 = await asyncio.to_thread(_b64, path)   # Encode blockiert sonst den Loop
        inhalt = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": data_b64}},
            {"type": "text", "text": DETECT_PROMPT},
        ]
        for anlauf in range(2):
            r = await client.messages.create(
                model=VISION_MODEL, max_tokens=2500,
                messages=[{"role": "user", "content": inhalt}])
            data = _json_of(_text_of(r))
            corners = data.get("corners")
            if not (data.get("kind") in ("slab", "sleeve", "raw")
                    and isinstance(corners, list) and len(corners) == 4
                    and all(isinstance(c, list) and len(c) == 2 for c in corners)
                    and data.get("confidence") == "high"):
                return None
            if _prozentwerte_ok(data):
                return data
            if anlauf == 0:
                log.info("cardscan: Koordinaten außerhalb 0-100 für %s — ein neuer Anlauf", path)
                inhalt = inhalt[:2] + [{"type": "text", "text":
                    "Deine letzte Antwort enthielt Werte über 100 — das waren Pixel. "
                    "Antworte erneut, ALLE Koordinaten strikt als Prozent 0-100."}]
        return None
    except Exception as e:  # noqa: BLE001
        log.warning("cardscan: Erkennung fehlgeschlagen für %s: %s", path, e)
        return None




def kanten_trim(warped):
    """Deterministischer Nachschnitt auf die echte Case-Kante.

    Die Vision-Ecken sitzen 2–3 % zu weit außen (Folie, Modell-Toleranz) —
    das Übermaß zeigt den Foto-Untergrund und stand als dunkler Rand auf
    Svens Kacheln (03.08., 21:56). Nach dem Aufrichten ist der Slab
    achsenparallel: seine Kante ist der stärkste durchgehende Gradient im
    Randband. Der wird hier gefunden und exakt geschnitten — reine Geometrie,
    kein Modell, keine Pixel-Manipulation, bei jedem Foto gleich.

    Pro Zeile/Spalte stimmen (Median), damit eine Restneigung von 1–2° die
    Kante nicht „verschmiert" und der Trim an den Seiten leer ausgeht.
    """
    import numpy as np

    H, W = warped.shape[:2]
    L = warped.mean(axis=2).astype(np.float32)
    band_x, band_y = max(10, int(W * 0.22)), max(10, int(H * 0.22))
    marge = 1

    def kante_von_rand(profil_2d, band, von_ende=False):
        """Median der stärksten Kante je Zeile (oder Spalte) im Randband."""
        # profil_2d: Zeilen × Band-Spalten (oder Spalten × Band-Zeilen)
        if profil_2d.shape[1] < 6:
            return None
        grads = np.abs(np.diff(profil_2d.astype(np.float32), axis=1))
        peaks = grads.argmax(axis=1)
        strengths = grads[np.arange(len(peaks)), peaks]
        # Referenz: typische Gradienten-Stärke im Band (nicht der Peak-Median —
        # der wäre ~Peak selbst und 2×Peak filtert alles weg).
        ref = float(np.median(grads)) + 1e-6
        ok = strengths >= max(4.0 * ref, 12.0)
        if ok.sum() < max(12, len(ok) // 4):
            return None
        gewaehlt = peaks[ok]
        # Eine echte Case-Kante liegt in den meisten Zeilen an derselben Stelle.
        # Rauschen streut über das ganze Band — dann nicht schneiden.
        if float(np.std(gewaehlt)) > max(6.0, band * 0.08):
            return None
        i = int(np.median(gewaehlt))
        if i < 2:
            return None
        return i

    # Je Zeile: Gradienten im linken/rechten Band → Case-Seitenkante
    li = kante_von_rand(L[:, :band_x], band_x)
    re = kante_von_rand(L[:, -band_x:][:, ::-1], band_x)
    # Je Spalte: Gradienten im oberen/unteren Band
    ob = kante_von_rand(L[:band_y, :].T, band_y)
    un = kante_von_rand(L[-band_y:, :][::-1, :].T, band_y)

    x0 = (li + 1 + marge) if li is not None else 0
    x1 = W - ((re + 1 + marge) if re is not None else 0)
    y0 = (ob + 1 + marge) if ob is not None else 0
    y1 = H - ((un + 1 + marge) if un is not None else 0)
    if x1 - x0 < W * 0.50 or y1 - y0 < H * 0.50:
        return warped
    return warped[y0:y1, x0:x1]


def tisch_trim(warped):
    """Schneidet warmen Tisch/Kork/Holz am Rand weg — Case-Plastik bleibt.

    Klares Case zeigt den Untergrund DURCH, ist aber an der Außenkante
    kühler/dunkler (Lichtkante). Reiner Tisch ist warm (R−B groß). Vom Rand
    nach innen: solange die Spalte/Zeile überwiegend warm ist, wegschneiden.
    Greift nur, wenn der Lauf klar und nicht zu tief ist.
    """
    import numpy as np

    H, W = warped.shape[:2]
    if H < 80 or W < 60:
        return warped
    rgb = warped.astype(np.float32)
    warm = (rgb[:, :, 0] - rgb[:, :, 2]) > 32.0
    # Mittenband: Label (schwarz) und untere Glanzlichter nicht mitzählen
    y0, y1 = int(H * 0.22), int(H * 0.88)
    x0b, x1b = int(W * 0.12), int(W * 0.88)
    wcol = warm[y0:y1, :].mean(axis=0)
    wrow = warm[:, x0b:x1b].mean(axis=1)

    def lauf(arr, thr=0.52, max_frac=0.20):
        n = 0
        limit = max(4, int(len(arr) * max_frac))
        for v in arr:
            if v >= thr and n < limit:
                n += 1
            else:
                break
        return n if n >= 3 else 0

    left = lauf(wcol)
    right = lauf(wcol[::-1])
    top = lauf(wrow, max_frac=0.12)
    bot = lauf(wrow[::-1], max_frac=0.18)
    nx0, nx1 = left, W - right
    ny0, ny1 = top, H - bot
    if nx1 - nx0 < W * 0.55 or ny1 - ny0 < H * 0.55:
        return warped
    ar = (ny1 - ny0) / max(nx1 - nx0, 1)
    if not (1.15 <= ar <= 2.05):
        return warped
    return warped[ny0:ny1, nx0:nx1]


def untergrund_trim(warped):
    """Schneidet homogenen Foto-Untergrund am Rand (Filz, Stoff, Studio).

    tisch_trim greift nur auf warmen Kork/Holz. Viele CGC-Fotos liegen auf
    schwarzem Mikrofasertuch — dort bleibt ein Streifen stehen und der Slab
    wirkt schief im Kachelrahmen. Hier: Spalte/Zeile fliegt, solange sie
    deutlich dunkler ODER deutlich gleichmäßiger ist als das Case-Innere.
    Kein Weichzeichnen, nur Zuschnitt.
    """
    import numpy as np

    H, W = warped.shape[:2]
    if H < 80 or W < 60:
        return warped
    rgb = warped.astype(np.float32)
    L = rgb.mean(axis=2)
    y0, y1 = int(H * 0.20), int(H * 0.85)
    x0b, x1b = int(W * 0.15), int(W * 0.85)
    innen = L[y0:y1, x0b:x1b]
    if innen.size < 100:
        return warped
    ref_L = float(np.median(innen))
    ref_std = float(innen.std()) + 1e-6

    def spalte_ist_rand(x: int) -> bool:
        col = L[y0:y1, x]
        m, s = float(col.mean()), float(col.std())
        lim = min(ref_L - 15.0, 105.0)
        dark_frac = float((col < lim).mean())
        # Mehrheit der Zeile ist Untergrund ODER Spalte klar dunkler/flacher
        if dark_frac >= 0.55:
            return True
        if m < ref_L - 18 and m < 115:
            return True
        if s < max(10.0, ref_std * 0.55) and abs(m - ref_L) > 12:
            return True
        return False

    def zeile_ist_rand(y: int) -> bool:
        row = L[y, x0b:x1b]
        m, s = float(row.mean()), float(row.std())
        lim = min(ref_L - 15.0, 105.0)
        dark_frac = float((row < lim).mean())
        if dark_frac >= 0.55:
            return True
        if m < ref_L - 18 and m < 115:
            return True
        if s < max(10.0, ref_std * 0.55) and abs(m - ref_L) > 12:
            return True
        return False

    def lauf_x(von_rechts=False, max_frac=0.22):
        limit = max(4, int(W * max_frac))
        xs = range(W - 1, W - 1 - limit, -1) if von_rechts else range(limit)
        n = 0
        for x in xs:
            if spalte_ist_rand(x):
                n += 1
            else:
                break
        return n if n >= 2 else 0

    def lauf_y(von_unten=False, max_frac=0.16):
        limit = max(4, int(H * max_frac))
        ys = range(H - 1, H - 1 - limit, -1) if von_unten else range(limit)
        n = 0
        for y in ys:
            if zeile_ist_rand(y):
                n += 1
            else:
                break
        return n if n >= 2 else 0

    left, right = lauf_x(), lauf_x(von_rechts=True)
    top, bot = lauf_y(max_frac=0.12), lauf_y(von_unten=True, max_frac=0.18)
    nx0, nx1 = left, W - right
    ny0, ny1 = top, H - bot
    if nx1 - nx0 < W * 0.55 or ny1 - ny0 < H * 0.55:
        return warped
    ar = (ny1 - ny0) / max(nx1 - nx0, 1)
    if not (1.12 <= ar <= 2.08):
        return warped
    return warped[ny0:ny1, nx0:nx1]


def _norm_winkel_45(angle: float) -> float:
    """Winkel in (−45, 45] — kleinste Drehung zur Achsenparallelen."""
    a = (angle + 180.0) % 180.0
    if a > 90.0:
        a -= 180.0
    if a > 45.0:
        a -= 90.0
    elif a <= -45.0:
        a += 90.0
    return a


def _slab_inhalt_winkel(img) -> float:
    """Neigung des Slab aus langen Kanten (Hough) — ohne Perspektiv-Stretch.

    Vision liefert oft ein achsenparalleles Eck-Rechteck UM einen schiefen
    Slab; der Top-Kanten-Winkel der Ecken ist dann 0°, der Slab bleibt schief.
    Lange Kanten im Bild verraten die echte Neigung.
    """
    import cv2
    import numpy as np

    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 45, 130)
    min_len = max(40, int(min(H, W) * 0.28))
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=max(50, min(H, W) // 14),
                            minLineLength=min_len, maxLineGap=max(8, min(H, W) // 40))
    if lines is None:
        return 0.0
    gewichte, winkel = [], []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        dx, dy = float(x2 - x1), float(y2 - y1)
        L = float(np.hypot(dx, dy))
        if L < min_len:
            continue
        ang = float(np.degrees(np.arctan2(dy, dx)))
        # Nahe vertikal (±90°) oder horizontal (0°): Abweichung = Aufricht-Winkel
        if abs(abs(ang) - 90.0) <= 22.0 or abs(ang) <= 22.0:
            t = _norm_winkel_45(ang)
            if abs(t) < 0.35:
                continue
            gewichte.append(L)
            winkel.append(t)
    if not winkel:
        return 0.0
    w = np.asarray(gewichte, dtype=np.float64)
    a = np.asarray(winkel, dtype=np.float64)
    # Längen-gewichteter Median
    order = np.argsort(a)
    a, w = a[order], w[order]
    cum = np.cumsum(w)
    mid = cum[-1] * 0.5
    ang = float(a[int(np.searchsorted(cum, mid))])
    if abs(ang) < 0.4 or abs(ang) > 18.0:
        return 0.0
    return ang


def _affine_drehen(img, angle: float):
    """Bild um angle Grad drehen (warpAffine) — nur Rotation, kein Zerren."""
    import cv2
    import numpy as np

    H, W = img.shape[:2]
    if abs(angle) < 0.35:
        M = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float64)
        return img, M
    cx, cy = W / 2.0, H / 2.0
    M = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    cos_a, sin_a = abs(M[0, 0]), abs(M[0, 1])
    nW = int(H * sin_a + W * cos_a)
    nH = int(H * cos_a + W * sin_a)
    M[0, 2] += nW / 2.0 - cx
    M[1, 2] += nH / 2.0 - cy
    # BORDER_REPLICATE: kein schwarzer Keil, der kanten_trim täuscht
    out = cv2.warpAffine(img, M, (nW, nH), flags=cv2.INTER_CUBIC,
                         borderMode=cv2.BORDER_REPLICATE)
    return out, M


def _pts_affine(pts, M):
    import cv2
    import numpy as np
    return cv2.transform(np.asarray(pts, dtype=np.float32).reshape(-1, 1, 2), M).reshape(-1, 2)


def _crop_ecken(img, pts, pad: int = 2):
    import numpy as np
    H, W = img.shape[:2]
    xs, ys = pts[:, 0], pts[:, 1]
    x0 = max(0, int(np.floor(xs.min())) - pad)
    y0 = max(0, int(np.floor(ys.min())) - pad)
    x1 = min(W, int(np.ceil(xs.max())) + pad)
    y1 = min(H, int(np.ceil(ys.max())) + pad)
    if x1 - x0 < 80 or y1 - y0 < 80:
        return img, (0, 0)
    return img[y0:y1, x0:x1], (x0, y0)


def belichtung_normalisieren(warped):
    """Globale Belichtungsangleichung — wie der Auto-Modus jeder Kamera-App.

    Unterbelichtete Fotos (Svens Gavel auf dunklem Fell, 03.08., 21:56)
    werden als GANZES aufgehellt: ein linearer Gain, jedes Pixel gleich.
    Dadurch sind örtliche Artefakte (Streifen, Fetzen, Kanten) physikalisch
    unmöglich — der Unterschied zur verbotenen Masken-Kosmetik. Gut belichtete
    Fotos bleiben unangetastet (Gain 1.0), abgedunkelt wird nie.
    """
    import numpy as np

    L = warped.mean(axis=2)
    p90 = float(np.percentile(L, 90))
    if p90 >= 170 or p90 <= 1:
        return warped                                # gut belichtet — Finger weg
    gain = min(1.6, 185.0 / p90)
    return np.clip(warped.astype(np.float32) * gain, 0, 255).astype(np.uint8)


def bild_ok(path: str, kind: str | None = None) -> bool:
    """Selbstprüfung nach dem Rendern — die Wache vor dem Speichern.

    Svens Auftrag (03.08.): ein festes System statt Korrekturschleifen. Kein
    Ergebnis erreicht die Sammlung, das diese vier Prüfungen nicht besteht;
    fällt es durch, bleibt das Original stehen und der Scan läuft weiter.
    """
    try:
        import numpy as np
        with Image.open(path) as im:
            w, h = im.size
            if w < 300 or h < 300:
                return False                     # Winzling — Zuschnitt verrutscht
            ratio = h / max(w, 1)
            if kind == "slab" and not (1.05 <= ratio <= 2.1):
                return False                     # Slabs sind Hochkant-Rechtecke
            if kind in ("sleeve", "raw") and not (1.15 <= ratio <= 1.65):
                return False                     # Karten haben ~1.39
            klein = np.asarray(im.convert("L").resize((64, 64)), dtype=np.float32)
            if klein.std() < 12:
                return False                     # nahezu einfarbig — leerer Crop
            # Extremwert-Flächen: >85 % fast weiß oder fast schwarz heißt,
            # der Zuschnitt hat das Stück verloren
            if ((klein > 235).mean() > 0.85) or ((klein < 20).mean() > 0.85):
                return False
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("cardscan: bild_ok scheiterte für %s: %s", path, e)
        return False


_rembg_session = None


def _studio_hintergrund(rgb, alpha, form=None, boxen=None):
    """Studio-Look für Slabs: der Untergrund, der durch transparentes
    Case-Plastik scheint (Svens dunkler Tisch, 03.08.), wird zu neutralem
    Hell gemischt — als stünde der Slab im Lichtzelt.

    Die rembg-Alpha trennt sauber: Buch, Label und Karte tragen hohes Alpha
    und bleiben pixelgenau unangetastet; der Durchblick trägt niedriges und
    wird aufgehellt. Reflexe im Plastik liegen dazwischen und bleiben so als
    zarte Zeichnung erhalten — das Case soll sichtbar bleiben, nicht
    weggebügelt werden.

    rgb: np.uint8 HxWx3 · alpha: np.uint8 HxW (rembg) · form: bool-Maske des
    Zuschnitts oder None für ganzflächig. Gibt das gemischte RGB zurück.
    """
    import cv2 as _cv
    import numpy as np

    a = alpha.astype(np.float32) / 255.0
    # Mischgewicht: unter 0.15 voll Studio, ab 0.75 voll Original
    w = np.clip((0.75 - a) / 0.60, 0.0, 1.0)
    # weich machen, damit keine harte Kante zwischen Objekt und Plastik steht
    w = _cv.GaussianBlur(w, (0, 0), 3.0)

    # Schutz-Kerne: die undurchsichtigen Rechtecke im Case (Label, Buch,
    # Karte). Erste Wahl sind die VISION-BOXEN aus detect_card — exakte
    # Semantik statt Masken-Deutung. Ohne Boxen greift die Heuristik über
    # die größte Komponente (Bounding-Box hält auch bei löchriger Alpha,
    # etwa beim hellen Mond des 103er-Covers) plus Label-Zeilen-Trim.
    H_, W_ = alpha.shape
    L = _cv.cvtColor(rgb, _cv.COLOR_RGB2GRAY).astype(np.float32)
    if boxen:
        # Gegenprobe Vision ↔ Segmentierung: das größte Polygon (Sichtfenster)
        # muss die Hauptkomponente der Alpha-Maske treffen. Beim zweiten 103er
        # (03.08.) lagen die Konsens-Boxen versetzt — das Milchglas legte sich
        # ÜBERS Cover. Passen die zwei unabhängigen Quellen nicht zusammen,
        # gibt es keine Kosmetik.
        gross = _cv.morphologyEx((alpha > 200).astype(np.uint8), _cv.MORPH_CLOSE,
                                 np.ones((35, 35), np.uint8))
        ng, lg, sg, _ = _cv.connectedComponentsWithStats(gross)
        if ng > 1:
            gi = 1 + int(sg[1:, _cv.CC_STAT_AREA].argmax())
            hx0, hy0 = sg[gi, _cv.CC_STAT_LEFT], sg[gi, _cv.CC_STAT_TOP]
            hx1 = hx0 + sg[gi, _cv.CC_STAT_WIDTH]
            hy1 = hy0 + sg[gi, _cv.CC_STAT_HEIGHT]
            fenster = max(boxen, key=lambda p: _cv.contourArea(np.float32(p)))
            fx = [p[0] for p in fenster]; fy = [p[1] for p in fenster]
            ix0, iy0 = max(min(fx), hx0), max(min(fy), hy0)
            ix1, iy1 = min(max(fx), hx1), min(max(fy), hy1)
            schnitt = max(0, ix1 - ix0) * max(0, iy1 - iy0)
            verein = ((max(fx) - min(fx)) * (max(fy) - min(fy))
                      + (hx1 - hx0) * (hy1 - hy0) - schnitt)
            if schnitt / max(verein, 1e-6) < 0.5:
                log.info("cardscan: Vision-Boxen passen nicht zur Maske "
                         "(IoU %.2f) — keine Studio-Kosmetik", schnitt / max(verein, 1e-6))
                boxen = None
    if boxen:
        # Vision-Boxen sind die Wahrheit: Label und Sichtfenster bleiben
        # pixelgenau, ALLES andere ist Case-Plastik samt Durchblick — dort
        # täuscht weder Alpha (rembg sagt „Objekt") noch Helligkeit (der
        # Tisch ist braungrau, L≈118, kein Schwarz — gemessen 03.08.).
        # Plastik wird Milchglas: Studio-Grund, die Helligkeitsstruktur der
        # Reflexe und Kanten bleibt als zarte Zeichnung erhalten.
        # Polygone, nicht Bounding-Boxen: nach einem Warp bläht sich die
        # achsenparallele Box auf und schützt fremden Hintergrund mit
        # (der dunkle Balken hinter Svens Band-1-Label).
        schutz = np.zeros((H_, W_), dtype=np.uint8)
        for poly in boxen:
            pts = np.float32(poly)
            mitte = pts.mean(axis=0)
            pts = mitte + (pts - mitte) * 1.02      # 2 % Luft um den Druck
            _cv.fillPoly(schutz, [np.intp(pts)], 1)
        sw = _cv.GaussianBlur(schutz.astype(np.float32), (0, 0), 4.0)[:, :, None]
        hell = np.empty_like(rgb)
        hell[:] = (246, 247, 249)
        verlauf = np.linspace(1.0, 0.94, H_, dtype=np.float32)[:, None, None]
        milch = (hell.astype(np.float32) * verlauf
                 * (0.80 + 0.20 * (L / 255.0))[:, :, None])
        aus = rgb.astype(np.float32) * sw + milch * (1 - sw)
        if form is not None:
            aus[~form] = rgb[~form]
        return np.clip(aus, 0, 255).astype(np.uint8)

    # OHNE verlässliche Boxen keine weitere Kosmetik. Jede Heuristik, die
    # hier stand (Komponenten-Rechtecke, Dunkel-Flächen-Regel), hat im
    # Abnahme-Panel vom 03.08. Artefakte erzeugt — Querbalken über dem
    # Cover, ausgewaschene Ecken. Ein ehrliches dunkleres Bild schlägt ein
    # kaputtes; es bleibt bei der sanften Alpha-Mischung.

    if form is not None:
        w[~form] = 0.0
    hell = np.empty_like(rgb)
    hell[:] = (246, 247, 249)
    # sanfter Verlauf nach unten, damit es nach Licht aussieht, nicht nach Fläche
    H = rgb.shape[0]
    verlauf = np.linspace(1.0, 0.94, H, dtype=np.float32)[:, None, None]
    hell = (hell.astype(np.float32) * verlauf).astype(np.uint8)
    w3 = w[:, :, None]
    return (rgb.astype(np.float32) * (1 - w3) + hell.astype(np.float32) * w3).astype(np.uint8)


def _cutout(path: str, out_path: str) -> bool:
    """PicsArt-Style Hintergrundentferner: KI-Segmentierung (rembg/BiRefNet)
    findet das Objekt (Karte, Slab, Toploader), danach Form-Reparatur — Karten
    sind konvexe Rechtecke, also werden Löcher (dunkle Holo-Flächen) und
    Randbisse per Zeilen-/Spalten-Spannen aufgefüllt. Ergebnis: transparentes
    PNG, eng beschnitten.

    Einsatz: sleeve/raw direkt. Bei Slabs nur Fallback, wenn der Ecken-Warp
    reißt — nie auf einem gelungenen Warp (klares Plastik = „Hintergrund")."""
    global _rembg_session
    try:
        import numpy as np
        from rembg import new_session, remove
        from PIL import Image, ImageFilter, ImageOps
        if _rembg_session is None:
            _rembg_session = new_session("birefnet-general")
        img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        img.thumbnail((2000, 2000))   # 12-MP-Fotos quälen die CPU ohne Sichtgewinn
        out = remove(img, session=_rembg_session, post_process_mask=True)
        a = np.array(out.split()[3])
        # niedrige Schwelle: transparentes Slab-Plastik hat schwaches Alpha;
        # danach morphologisch schließen, damit der Case eine Form wird
        import cv2 as _cv
        m = a > 40
        # CLOSE groß genug, um die transparente Lücke Label<->Karte im Case zu
        # überbrücken (sonst zerfällt der Slab); OPEN klein, nur gegen Fransen.
        m = _cv.morphologyEx(m.astype(np.uint8), _cv.MORPH_CLOSE,
                             np.ones((61, 61), np.uint8))
        m = _cv.morphologyEx(m, _cv.MORPH_OPEN, np.ones((7, 7), np.uint8)).astype(bool)
        if not m.any():
            return False
        # 1) nur die Komponente um die Bildmitte behalten (Finger/Krümel fliegen raus)
        H, W = m.shape
        _rot_M = None                   # gesetzt, falls unten rotiert wird
        small = np.array(Image.fromarray(m.astype(np.uint8) * 255)
                         .resize((240, 240), Image.NEAREST)) > 0
        keep = np.zeros_like(small)
        ys, xs = np.nonzero(small)
        cy, cx = 120, 120
        if not small[cy, cx]:
            i = ((ys - cy) ** 2 + (xs - cx) ** 2).argmin()
            cy, cx = int(ys[i]), int(xs[i])
        stack = [(cy, cx)]
        while stack:
            y, x = stack.pop()
            if 0 <= y < 240 and 0 <= x < 240 and small[y, x] and not keep[y, x]:
                keep[y, x] = True
                stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
        # Slab-Label-Rettung (Svens Band 1, 03.08.): das Beckett-Label liegt
        # ÜBER der Karte, durch transparentes Plastik getrennt — als eigene
        # Komponente flog es hier raus und der Case war „weg". Komponenten,
        # die im selben Spalten-Band wie die Mittel-Komponente liegen, gehören
        # zum Stück; Finger kommen von der Seite und bleiben draußen.
        xs_keep = np.nonzero(keep.any(0))[0]
        if xs_keep.size:
            kx0, kx1 = xs_keep[0], xs_keep[-1]
            n_lbl, lbl = _cv.connectedComponents(small.astype(np.uint8))
            for li in range(1, n_lbl):
                comp = lbl == li
                if (comp & keep).any():
                    continue
                cxs = np.nonzero(comp.any(0))[0]
                ueberlapp = max(0, min(kx1, cxs[-1]) - max(kx0, cxs[0]) + 1)
                if (comp.sum() >= 58                       # ≥ ~0,1 % des Bildes
                        and ueberlapp / max(cxs[-1] - cxs[0] + 1, 1) > 0.6):
                    keep |= comp
        m &= np.array(Image.fromarray(keep.astype(np.uint8) * 255)
                      .resize((W, H), Image.BILINEAR)) > 127
        # 2) Svens Vorlagen-Idee: Slabs/Toploader/Karten SIND Rechtecke — das minimale
        # rotierte Rechteck um die Maske fitten und als Schnittform verwenden.
        # Deckt die Maske das Rechteck gut ab, gewinnt die Vorlage (gerade Kanten,
        # nichts angefressen); sonst konvexe Zeilen-/Spalten-Reparatur als Fallback.
        import cv2
        pts = cv2.findNonZero(m.astype(np.uint8))
        rect = cv2.minAreaRect(pts)
        (rw, rh) = rect[1]
        solid = None
        if rw > 1 and rh > 1 and m.sum() / (rw * rh) > 0.55:
            # NUR ROTIEREN, NIE VERZERREN (Svens iPhone-Test: Perspektiv-Warp
            # zerrte Karten). Rotation macht gerade und kann nichts kaputtziehen.
            angle = rect[2]
            if angle > 45:
                angle -= 90
            if 0.4 < abs(angle) < 20:
                M = cv2.getRotationMatrix2D((W / 2, H / 2), angle, 1.0)
                img = Image.fromarray(cv2.warpAffine(
                    np.array(img), M, (W, H), flags=cv2.INTER_CUBIC,
                    borderValue=(0, 0, 0)))
                m = cv2.warpAffine(m.astype(np.uint8) * 255, M, (W, H)) > 127
                a = cv2.warpAffine(a, M, (W, H))   # Alpha mitdrehen (Studio-Look)
                _rot_M = M                          # Boxen später mitdrehen
                out = img.convert("RGBA")
                pts = cv2.findNonZero(m.astype(np.uint8))
                rect = cv2.minAreaRect(pts)
            box_i = np.intp(cv2.boxPoints(rect))
            tmpl = np.zeros((H, W), dtype=np.uint8)
            cv2.fillPoly(tmpl, [box_i], 255)
            solid = tmpl > 0
        if solid is None:
            rows, cols = m.any(1), m.any(0)
            x0 = m.argmax(1); x1 = W - 1 - m[:, ::-1].argmax(1)
            y0 = m.argmax(0); y1 = H - 1 - m[::-1, :].argmax(0)
            xi, yi = np.arange(W), np.arange(H)
            rowspan = (xi >= x0[:, None]) & (xi <= x1[:, None]) & rows[:, None]
            colspan = (yi[:, None] >= y0[None, :]) & (yi[:, None] <= y1[None, :]) & cols[None, :]
            solid = rowspan & colspan
        frac = solid.mean()
        if frac < 0.05 or frac > 0.98:
            return False   # nichts Brauchbares gefunden bzw. Vollbild — Original behalten
        # 3) weiche, halofreie Kante — auf dem ORIGINALBILD, nicht auf dem
        # rembg-Ergebnis: rembg malt entfernte Pixel schwarz, und was die
        # Rechteck-Vorlage davon wieder sichtbar macht (transparentes
        # Slab-Plastik), wurde zur schwarzen Fläche (Svens Band 103, 03.08.).
        am = Image.fromarray((solid * 255).astype("uint8"))
        am = am.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(1.4))
        rgb = _studio_hintergrund(np.array(img), a, form=solid)
        out = Image.fromarray(rgb).convert("RGBA")
        out.putalpha(am)
        bbox = out.getbbox()
        if not bbox:
            return False
        pad = 8
        out = out.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                        min(W, bbox[2] + pad), min(H, bbox[3] + pad)))
        out.save(out_path, "PNG")
        for muster in ("_w*.jpg", "_w*.webp"):
            for tp in Path(out_path).parent.glob(Path(out_path).stem + muster):
                tp.unlink(missing_ok=True)
        for muster in ("_w*.png", "_w*.webp"):
            for tp in Path(out_path).parent.glob(Path(out_path).stem + muster):
                tp.unlink(missing_ok=True)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("cardscan: Cutout fehlgeschlagen für %s: %s", path, e)
        return False


# Der Freisteller (BiRefNet) rechnet auf der CPU und nutzt dabei selbst alle
# Kerne. Laufen zwei gleichzeitig, teilen sie sich dieselbe Rechenzeit und JEDER
# wird langsamer — bei vier Stücken auf einmal reißen dadurch alle den Zeitrahmen.
# Deshalb: immer nur EIN Freisteller. Das ist in Summe schneller, nicht langsamer.
_cut_lock = asyncio.Semaphore(1)


async def crop_photos(api_key: str, paths: list[str]) -> tuple[list[str], dict]:
    """Alle Fotos eines Stücks freistellen (Hintergrund weg, transparentes PNG).
    Läuft lokal (rembg) — bei Misserfolg bleibt das jeweilige Original stehen.

    Vorweg fragt ein Vision-Blick nach Label- und Fenster-Box: bei Slabs
    steuern die den Studio-Look pixelgenau (Svens Manga, 03.08.). Schlägt
    die Erkennung fehl, arbeitet der Freisteller mit seiner Heuristik weiter."""
    def one(p: str, kind: str | None) -> str:
        out = str(Path(p).with_name(Path(p).stem + "_cut.png"))
        if _cutout(p, out) and bild_ok(out, kind):
            return out
        return p                     # Standard: lieber Original als schlechtes Bild

    loop = asyncio.get_running_loop()
    # Nur Vorder- und Rückseite verdienen den teuren Freisteller (~18 s/Foto);
    # weitere Aufnahmen bleiben unbearbeitete Zusatzbilder.
    results = []
    for idx, p in enumerate(paths):
        if idx < 2:
            det1 = None
            try:
                det1 = await detect_card(_anthropic(api_key), p)
            except Exception as e:  # noqa: BLE001
                log.warning("cardscan: Erkennungs-Blick fehlgeschlagen für %s: %s", p, e)
            # Slab? Dann ist der ECKEN-WARP der Normalfall (Svens Referenzbild
            # 03.08., 20:48: begradigt, Schnitt exakt an der Case-Kante, kein
            # Schleier). KEIN rembg danach — klares Plastik wird sonst
            # mitgefressen (Hen-Ei / Case-weg, 07.08.). Segmentierer nur
            # Fallback, wenn die Warp-Schutzchecks reißen.
            if det1 and det1.get("kind") == "slab":
                out = str(Path(p).with_name(Path(p).stem + "_cut.png"))
                try:
                    if await slab_recut(api_key, p, out, det=det1) and bild_ok(out, "slab"):
                        results.append(out)
                        continue
                except Exception as e:  # noqa: BLE001
                    log.warning("cardscan: Slab-Warp fehlgeschlagen für %s: %s", p, e)
            async with _cut_lock:
                results.append(await loop.run_in_executor(
                    None, one, p, det1.get("kind") if det1 else None))
        else:
            results.append(p)
    info = {"cropped": sum(1 for r, p in zip(results, paths) if r != p), "total": len(paths)}
    return results, info


async def slab_recut(api_key: str, src_path: str, out_path: str,
                     min_area_frac: float = 0.0,
                     det: dict | None = None) -> bool:
    """Slab-Garantie: Case-Ecken → aufrecht → eng zuschneiden.

    Wenn gegenüberliegende Kanten fast gleich lang sind (Symmetrie-Gates),
    richtet ein Perspektiv-Warp auf die Ecken auf — das ist für ein
    Parallelogramm kein Zerren und schneidet eng. Sonst nur ROTATION
    (warpAffine), nie strecken (Sven: „Don't distort, just straighten").

    min_area_frac: Flächenanteil am Rohbild, den das gefundene Case ÜBERTREFFEN
    muss. Der Aufrufer übergibt den Anteil des bisherigen Zuschnitts × Reserve —
    so ersetzt der Zuschnitt nur dann, wenn der Segmentierer wirklich etwas
    verschluckt hat, und lässt einen korrekten Studio-Freisteller in Ruhe."""
    if det is None:
        # Eigenständiger Lauf (Rettungspfad nach der Analyse) — sonst reicht
        # der Aufrufer den Blick aus crop_photos durch und spart den Call.
        det = await detect_card(_anthropic(api_key), src_path)
    if not det or det.get("kind") != "slab":
        return False
    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageDraw, ImageOps
        img = np.array(ImageOps.exif_transpose(Image.open(src_path)).convert("RGB"))
        H, W = img.shape[:2]
        pts = np.array([[min(max(x, 0), 100) / 100 * W, min(max(y, 0), 100) / 100 * H]
                        for x, y in det["corners"]], dtype=np.float32)
        # 4 % Einzug: Vision-Ecken sitzen oft am Tisch außerhalb der Case-Kante.
        _c = pts.mean(axis=0)
        pts = (_c + (pts - _c) * 0.96).astype(np.float32)
        if min_area_frac > 0:
            frac = float(cv2.contourArea(pts)) / max(W * H, 1)
            if frac < min_area_frac:
                log.info("cardscan: slab_recut — Case (%.0f %%) nicht größer als "
                         "Zuschnitt, Studio-Bild bleibt", frac * 100)
                return False
        tl, tr, br, bl = pts
        W2 = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
        H2 = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
        if W2 < 100 or H2 < 100:
            return False
        # Deckel: 48-MP-iPhone-Fotos erzeugten Gigapixel-Warps (Thumbnail-Bombe!)
        _sc = min(1.0, 2000 / max(W2, H2))
        W2, H2 = max(1, int(W2 * _sc)), max(1, int(H2 * _sc))
        # Plausibilität: Slabs sind Hochkant-Rechtecke. Entartete Ecken (2000×196!)
        # -> lieber beim Studio-Freisteller bleiben als ein kaputtes Bild liefern.
        if not (1.1 <= H2 / max(W2, 1) <= 2.0):
            log.warning("cardscan: slab_recut-Ecken unplausibel (%dx%d) — verworfen", W2, H2)
            return False
        _top = np.linalg.norm(tr - tl); _bot = np.linalg.norm(br - bl)
        _lft = np.linalg.norm(bl - tl); _rgt = np.linalg.norm(br - tr)
        asym_tb = abs(_top - _bot) / max(_top, _bot)
        asym_lr = abs(_lft - _rgt) / max(_lft, _rgt)
        # Vorab: steckt der Slab schief in einem Vision-AABB? Dann zieht
        # Perspektiv die Schräge NICHT raus — Rotation zuerst.
        rough0, _ = _crop_ecken(img, pts, pad=max(8, int(min(W, H) * 0.01)))
        ang_ecken0 = _norm_winkel_45(float(np.degrees(np.arctan2(
            (tr - tl)[1], (tr - tl)[0]))))
        ang_inhalt0 = _slab_inhalt_winkel(rough0)
        # Perspektiv nur hinter engen Symmetrie-Gates UND wenn schon nahezu
        # aufrecht (sonst: Vision-Rechteck um schiefen Slab → Schräge bleibt).
        # Sven: „Don't distort, just straighten" → Rotation ist der Normalfall.
        use_persp = (asym_tb <= 0.08 and asym_lr <= 0.08
                     and abs(ang_ecken0) < 1.2 and abs(ang_inhalt0) < 1.2)

        M_box = None  # 3×3 für perspectiveTransform der Label-/Fenster-Boxen
        if use_persp:
            M = cv2.getPerspectiveTransform(
                pts, np.float32([[0, 0], [W2, 0], [W2, H2], [0, H2]]))
            warped = cv2.warpPerspective(img, M, (W2, H2), flags=cv2.INTER_CUBIC)
            M_box = M
        else:
            log.info("cardscan: slab_recut — nur Rotation "
                     "(tb=%.0f%% lr=%.0f%% ecken=%.1f° inhalt=%.1f°)",
                     asym_tb * 100, asym_lr * 100, ang_ecken0, ang_inhalt0)
            # ROTATION-ONLY: Winkel → drehen → Ecken-Crop. Kein Zerren.
            # Vorzeichen: Top-Kante mit +θ (rechts höher) → Bild um −θ drehen.
            ang_ecken = ang_ecken0
            ang_inhalt = ang_inhalt0
            if abs(ang_ecken) >= 0.5:
                angle = -ang_ecken
            elif abs(ang_inhalt) >= 0.4:
                angle = -ang_inhalt
            else:
                angle = 0.0
            _rect = cv2.minAreaRect(pts.reshape(-1, 1, 2))
            _ra = float(_rect[2])
            _rw, _rh = _rect[1]
            if _rw > 0 and _rh > 0:
                if _rw >= _rh:
                    _ra = _ra + 90.0
                _ra = _norm_winkel_45(_ra)
                if abs(_ra) >= 0.5 and abs(angle) < 0.5:
                    angle = -_ra
            # Inhalt gewinnt, wenn Hough klar schiefer als Vision-Ecken
            # (Vision liefert oft ein leicht geneigtes AABB um den Slab).
            if abs(ang_inhalt) >= 0.8 and abs(ang_inhalt) > abs(angle) + 0.5:
                angle = -ang_inhalt
            # Kappe: Holo-Reflexe erzeugen Fantasie-Winkel >8°.
            if abs(angle) > 8.0:
                angle = 0.0
            rotated, M_aff = _affine_drehen(img, angle)
            pts_r = _pts_affine(pts, M_aff)
            warped, (cx0, cy0) = _crop_ecken(rotated, pts_r, pad=2)
            M_box = np.eye(3, dtype=np.float64)
            M_box[:2, :] = M_aff
            M_box[0, 2] -= cx0
            M_box[1, 2] -= cy0

        # Nachschnitt über Label- + Fenster-Box (eng am Case, Plastikrand bleibt).
        warped = _case_nach_boxen(warped, det, pts, M_box, W, H)
        # BEWUSST keine Studio-Kosmetik: Warp/Rotation allein IST der Look —
        # aufrecht, Schnitt an der Case-Kante, Plastik wie fotografiert.
        warped = kanten_trim(warped)     # Gradient an der Case-Kante
        warped = tisch_trim(warped)      # warmen Tisch/Kork am Rand weg
        warped = untergrund_trim(warped)  # Filz/Stoff/Studio-Rand weg
        # Restneigung (≤4,5°): ein Pass. Darüber = oft Holo-Artefakt.
        _fein = _slab_inhalt_winkel(warped)
        if 0.5 <= abs(_fein) <= 4.5:
            warped, _ = _affine_drehen(warped, -_fein)
            warped = kanten_trim(warped)
            warped = tisch_trim(warped)
            warped = untergrund_trim(warped)
        warped = belichtung_normalisieren(warped)
        W2, H2 = warped.shape[1], warped.shape[0]
        if W2 < 100 or H2 < 100 or not (1.05 <= H2 / max(W2, 1) <= 2.1):
            log.warning("cardscan: slab_recut-Ergebnis unplausibel (%dx%d)", W2, H2)
            return False
        res = Image.fromarray(warped).convert("RGBA")
        rad = max(6, int(min(W2, H2) * 0.03))
        mask = Image.new("L", (W2, H2), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, W2 - 1, H2 - 1], radius=rad, fill=255)
        res.putalpha(mask)
        res.save(out_path, "PNG")
        for muster in ("_w*.png", "_w*.webp"):
            for tp in Path(out_path).parent.glob(Path(out_path).stem + muster):
                tp.unlink(missing_ok=True)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("cardscan: slab_recut fehlgeschlagen für %s: %s", src_path, e)
        return False


def _case_nach_boxen(warped, det: dict, pts, M, W: int, H: int):
    """Warped-Bild auf Label+Fenster (+ Plastikrand des Cases) nachschneiden.

    Fällt zurück aufs unveränderte Bild, wenn Boxen fehlen oder der Zuschnitt
    unplausibel klein wäre. M ist 3×3 (Perspektive oder Affine+Crop).
    """
    import cv2
    import numpy as np

    lb, wb = det.get("label_box"), det.get("window_box")
    if not (isinstance(lb, (list, tuple)) and len(lb) == 4
            and isinstance(wb, (list, tuple)) and len(wb) == 4):
        return warped
    if M is None:
        return warped
    M = np.asarray(M, dtype=np.float64)
    if M.shape == (2, 3):
        M3 = np.eye(3, dtype=np.float64)
        M3[:2, :] = M
        M = M3
    elif M.shape != (3, 3):
        return warped

    def _map_box(b):
        src = np.array([[b[0] / 100 * W, b[1] / 100 * H],
                        [b[2] / 100 * W, b[1] / 100 * H],
                        [b[2] / 100 * W, b[3] / 100 * H],
                        [b[0] / 100 * W, b[3] / 100 * H]], dtype=np.float32)
        t = cv2.perspectiveTransform(src.reshape(-1, 1, 2), M).reshape(-1, 2)
        return float(t[:, 0].min()), float(t[:, 1].min()), float(t[:, 0].max()), float(t[:, 1].max())

    try:
        L, Win = _map_box(lb), _map_box(wb)
    except Exception:  # noqa: BLE001
        return warped
    lx0, ly0, lx1, ly1 = L
    wx0, wy0, wx1, wy1 = Win
    Hh, Ww = warped.shape[:2]
    # Plastik-Lippe um Label+Fenster: eng genug gegen Tisch, weit genug für Case.
    # CGC-Rim ≈ 6–9 % der Labelbreite je Seite; oben ~0,45 Labelhöhe.
    px = max(4.0, (lx1 - lx0) * 0.07)
    pt = max(4.0, (ly1 - ly0) * 0.45)
    pb = max(4.0, (wy1 - wy0) * 0.07)
    cx0 = max(0, int(min(lx0, wx0) - px))
    cx1 = min(Ww, int(max(lx1, wx1) + px))
    cy0 = max(0, int(ly0 - pt))
    cy1 = min(Hh, int(wy1 + pb))
    if cx1 - cx0 < Ww * 0.50 or cy1 - cy0 < Hh * 0.50:
        return warped
    ar = (cy1 - cy0) / max(cx1 - cx0, 1)
    if not (1.10 <= ar <= 2.10):
        return warped
    return warped[cy0:cy1, cx0:cx1]


GROUP_PROMPT = """Du siehst {n} nummerierte Fotos (Foto 0 bis Foto {last}) aus einem
Karten-Scan-Stapel. Ordne sie physischen Sammlerstücken zu:
- Vorder- und Rückseite DERSELBEN Karte gehören in EINE Gruppe (Vorderseite zuerst).
- Achte auf Übereinstimmung: gleiches Case/Label, gleiche Hülle, gleiche Abnutzung,
  gleicher Hintergrund und typischerweise direkt aufeinanderfolgende Aufnahmen.
- Eine Rückseite ohne klar zuordenbare Vorderseite bleibt eine eigene Gruppe.
- Verschiedene Karten NIEMALS mischen — im Zweifel lieber trennen.
Antworte NUR mit JSON: {{"groups": [[0,1],[2],[3,4]]}} — jede Fotonummer genau einmal."""


async def group_photos(api_key: str, paths: list[str]) -> list[list[int]]:
    """Foto-Stapel in Objekte gruppieren. Fallback: jedes Foto ein eigenes Objekt."""
    fallback = [[i] for i in range(len(paths))]
    if len(paths) < 2:
        return fallback
    client = _anthropic(api_key)
    try:
        # Bis zu 24 Fotos synchron zu kodieren hielt den ganzen Server an —
        # SSE-Pings, Logins, alles. Jetzt parallel im Thread-Pool.
        b64s = await asyncio.gather(*(asyncio.to_thread(_b64, p, 900) for p in paths))
        content = []
        for i, (p, daten) in enumerate(zip(paths, b64s)):
            content.append({"type": "text", "text": f"Foto {i}:"})
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg", "data": daten}})
        content.append({"type": "text",
                        "text": GROUP_PROMPT.format(n=len(paths), last=len(paths) - 1)})
        r = await client.messages.create(model=VISION_MODEL, max_tokens=6000,
                                         messages=[{"role": "user", "content": content}])
        groups = _json_of(_text_of(r)).get("groups")
        seen: list[int] = sorted(i for g in groups for i in g)
        if seen != list(range(len(paths))):
            log.warning("cardscan: Gruppierung unvollständig (%s) — Fallback einzeln", groups)
            return fallback
        return [list(g) for g in groups]
    except Exception as e:  # noqa: BLE001
        log.warning("cardscan: Gruppierung fehlgeschlagen: %s — Fallback einzeln", e)
        return fallback
