"""Karten-Freisteller + Stapel-Gruppierung für den Scanner.

═══════════════════════════════════════════════════════════════════════════
RENDER-STANDARD (Sven 08.08.2026 — Freistellen wie Collection-Norm):

  Klassifikation VOR dem Cutout (Glance, nicht erst nach 90s Analyse):
    product | card | slab  — siehe web/cutout_v2/routing.py

  Alle Scan-Fotos:
    1) EXIF-Orientierung
    2) Nur flache Karten/Slabs aufrichten (Ecken-Warp / Rotation, KEINE Kosmetik).
       Flasche, Sneaker, Handy, Buch, sonst 3D: KEIN Warp (sonst verbiegt die
       Zylinder-Perspektive das Label).
       - Rohkarte: Warp aufs Karten-Rechteck (alte Rechteck-Technik), dann rembg
       - Slab: Warp aufs Case-Rechteck (nicht die Karte im Fenster entbiegen)
    3) Hintergrund weg mit rembg → echte Alpha-Maske
       - Rohkarte: `birefnet-general` + Rechteck-Vorlage
       - Hülle/Toploader: `birefnet-general` + weiches Alpha (kein Rechteck);
         Außenkanten des Halters, nicht die gedruckte Karte allein
       - Graded/Slab: `isnet-general-use` + weiches Alpha (kein opakes Rechteck)
       - Alltagsstücke: `isnet-general-use` als normaler Background-Remover
         (kein Rechteck, keine Politur, kein Studio)
    4) Bounding-Box aus Alpha, enger Zuschnitt mit ~1,5 % transparentem Rand
    5) PNG mit Alphakanal speichern
    6) bild_ok() — sonst Original behalten

  Warp selbst: KEINE selektive Nachbearbeitung (kein Milchglas, kein Studio-
  Bleichen). rembg liefert die Transparenz; Layout kommt NUR aus der Alpha-
  Maske, nie aus „nahezu weißen Pixeln".

  Referenzfälle (nicht überschreiben): siehe
  `tests/fixtures/cutout_refs.json` und Svens manuelle `edit*.jpg` /
  `00_cut.png` in der Collection.

Wer den Warp selbst anfasst, macht erst tests/test_render_standard.py grün.
═══════════════════════════════════════════════════════════════════════════

- glance_scan: schneller Vision-Blick product|card|slab + grader.
- crop_photos: Klassifikation, dann Warp (Karte/Slab) + rembg-Cutout.
- slab_recut: nur Aufrichten/Zuschnitt; Freistellen danach über _cutout.
- group_photos: Vorder-/Rückseite demselben Objekt zuordnen.
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

import os
import threading
from pathlib import Path

from anthropic import AsyncAnthropic
from PIL import Image, ImageOps

log = logging.getLogger("cardscan")

VISION_MODEL = "claude-sonnet-5"   # Eckpunkte müssen präzise sein — kein Haiku
GLANCE_MODEL = "claude-haiku-4-5-20251001"  # nur product|card|slab, kein Ecken-JSON
GLANCE_TIMEOUT_S = 12.0
MAX_BATCH = 24

_client: AsyncAnthropic | None = None


def _anthropic(api_key: str) -> AsyncAnthropic:
    """EIN Client fürs Modul — vorher entstand pro Aufruf ein frischer
    (Full-Scan-Befund 03.08.): jedes Mal neuer Connection-Pool, kein
    Keep-Alive zwischen den Vision-Blicken desselben Scans."""
    global _client
    if _client is None:
        # Ohne Timeout hing detect_card still — UI blieb auf „Stelle Karte frei".
        _client = AsyncAnthropic(api_key=api_key, timeout=90.0, max_retries=2)
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


DETECT_PROMPT = """Du siehst ein Foto. Es kann eine flache Sammelkarte sein ODER
ein Alltagsgegenstand (Flasche, Schuh, Handy, Dose, Verpackung). Erfinde KEINE
Karten-Ecken, wenn keine flache Karte zu sehen ist. Antworte NUR mit JSON:
{"kind": "...", "corners": [[x,y],[x,y],[x,y],[x,y]], "confidence": "high|low"}

"kind":
- "slab"   = Karte steckt in einem Grading-Case (PSA, CGC, Beckett …) mit Bewertungslabel
- "sleeve" = Karte steckt in einer Schutzhülle, Softsleeve, Semi-Rigid oder Toploader
  (Plastik ohne Bewertungslabel). Auch wenn das Plastik klar/durchsichtig und der
  Rand schmal ist — und auch auf hellem Tisch, wo der Rand kaum sichtbar ist.
- "raw"    = lose Karte OHNE jedes Plastik um die Karte. Ein durchsichtiger Rand,
  Toploader oder Softsleeve = IMMER "sleeve", nie "raw".
- "other"  = keine flache einzelne Sammelkarte. Pflicht bei Flasche, Sneaker,
  Handy, Dose, Display, mehreren Karten, Unscharfem. Dann KEINE corners erfinden.

"corners": die vier Eckpunkte in PROZENT der Bildbreite (x) und Bildhöhe (y),
Reihenfolge [oben-links, oben-rechts, unten-rechts, unten-links].
- Bei "slab": die AUSSENKANTEN des kompletten HARTEN Plastik-Cases inklusive
  Bewertungslabel — der Slab gehört zum Sammlerstück und bleibt im Bild.
  Warp gilt NUR für dieses Case-Rechteck, niemals für die Karte im Sichtfenster
  (die darf im Case schief sitzen). Eine lose Schutzfolie oder Tüte UM den Case
  zählt NICHT: die Punkte liegen auf den harten Case-Kanten, die Folie bleibt draußen.
  KRITISCH: Tisch, Holz, Kork, Stoff, Hände und Schatten gehören NICHT in die
  Ecken. Die vier Punkte liegen ENG auf der harten Case-Außenkante — nach dem
  Zuschnitt soll das Case den Rahmen füllen (höchstens 1–2 % Luft). Lieber
  2 % zu eng am Plastik als 5 % Tischfläche mitnehmen.
- Bei "sleeve": die AUSSENKANTEN der Schutzhülle / des Toploaders (Plastik-Rahmen).
  Die gedruckte Karte liegt INNERHALB — Halter bleibt im Bild und wird NICHT
  weggeschnitten. Lieber 1–2 % Luft am Plastik als die Karte allein.
- Bei "raw": die Kartenkanten (kein Plastik-Rahmen).
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
            if data.get("kind") == "other":
                return {"kind": "other",
                        "confidence": data.get("confidence") or "low"}
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




async def glance_scan(api_key: str, path: str,
                      item: dict | None = None) -> dict | None:
    """Schneller Vision-Blick: product | card | slab + grader.

    Haiku, kleines Bild, wenige Tokens — vor dem Cutout, nicht nach der
    90-Sekunden-Analyse. Bei Fehler None (Aufrufer nimmt Geometrie).
    """
    from web.cutout_v2.routing import GLANCE_PROMPT, normalize_glance, scan_kind_from_item
    known = scan_kind_from_item(item)
    if known in ("product", "card", "slab") and (
            (item or {}).get("graded") or (item or {}).get("canonical_identity")):
        grader = None
        g = (item or {}).get("graded") or (item or {}).get("graded_info") or {}
        if isinstance(g, dict):
            grader = g.get("grader")
        return {"kind": known, "grader": grader, "confidence": "high",
                "source": "item"}
    if not api_key or len(str(api_key).strip()) < 20:
        return None
    try:
        data_b64 = await asyncio.to_thread(_b64, path, 800)
        r = await _anthropic(api_key).messages.create(
            model=GLANCE_MODEL, max_tokens=180,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": "image/jpeg",
                                             "data": data_b64}},
                {"type": "text", "text": GLANCE_PROMPT},
            ]}])
        return normalize_glance(_json_of(_text_of(r)))
    except Exception as e:  # noqa: BLE001
        log.warning("cardscan: Glance fehlgeschlagen für %s: %s", path, e)
        return None


def flat_rectangle_hint(path: str) -> str | None:
    """Konservativer Geometrie-Fallback ohne Netz: flaches Rechteck?

    card/slab wenn die größte Kontur kartenförmig ist, sonst None (Alltag).
    """
    from web.cutout_v2.routing import kind_from_rectangle
    try:
        import cv2
        import numpy as np
        img = np.array(ImageOps.exif_transpose(Image.open(path)).convert("RGB"))
    except Exception:  # noqa: BLE001
        return None
    H, W = img.shape[:2]
    if H < 80 or W < 60:
        return None
    scale = min(1.0, 640 / max(H, W))
    if scale < 1.0:
        img = cv2.resize(img, (max(1, int(W * scale)), max(1, int(H * scale))),
                         interpolation=cv2.INTER_AREA)
        H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 120)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.morphologyEx(cv2.dilate(edges, k, iterations=2),
                             cv2.MORPH_CLOSE, k, iterations=2)
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    area = float(cv2.contourArea(c))
    frac = area / max(H * W, 1)
    if not (0.08 < frac < 0.97):
        return None
    (rw, rh) = cv2.minAreaRect(c)[1]
    if rw < 8 or rh < 8:
        return None
    rectangularity = area / max(rw * rh, 1)
    aspect = max(rw, rh) / min(rw, rh)
    return kind_from_rectangle(aspect, rectangularity)


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


def case_kontur_nachschnitt(warped):
    """Nach dem Aufrichten: Case-Kontur → kleine Rest-Drehung + vorsichtiger Crop.

    Vision-Ecken und Trims lassen oft Schräge/Tisch. Hier die stärkste
    Außenkontur (Canny) — nur Rotation + AABB. Kein Perspektiv-Zerren, kein rembg.

    Schutz: nie das Bewertungslabel abschneiden (Höhe darf nicht unter ~80 %
    schrumpfen; oberer Zuschnitt in die Label-Zone ~12–22 % wird abgelehnt;
    Höhe stark weg bei gleichbleibender Breite = Fenster statt Case).
    """
    import cv2
    import numpy as np

    H, W = warped.shape[:2]
    if H < 100 or W < 80:
        return warped
    gray = cv2.cvtColor(warped, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 120)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.dilate(edges, k, iterations=2)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, k, iterations=3)
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return warped
    # Kontur wählen, die am ehesten ein Slab ist (Fläche + Seitenverhältnis)
    best, best_score = None, -1.0
    for c in cnts:
        area = float(cv2.contourArea(c))
        frac = area / max(H * W, 1)
        if frac < 0.40 or frac > 0.98:
            continue
        rx, ry, rw, rh = cv2.boundingRect(c)
        ar = rh / max(rw, 1)
        if not (1.20 <= ar <= 2.10):
            continue
        # Score: große Fläche, AR nahe typischem Slab (~1.55)
        score = frac - abs(ar - 1.55) * 0.15
        if score > best_score:
            best_score, best = score, c
    if best is None:
        return warped
    c = best
    rect = cv2.minAreaRect(c)
    (_cx, _cy), (rw, rh), ang = rect
    if rw < 40 or rh < 40:
        return warped
    if rw > rh:
        angle = _norm_winkel_45(ang + 90.0)
    else:
        angle = _norm_winkel_45(ang)
    rot = -angle
    if abs(rot) > 18.0:
        rot = 0.0
    out = warped
    if abs(rot) >= 0.45:
        out, M = _affine_drehen(out, rot)
        pts = cv2.transform(c.astype(np.float32), M)
    else:
        pts = c.astype(np.float32)
    xs = pts.reshape(-1, 2)[:, 0]
    ys = pts.reshape(-1, 2)[:, 1]
    Hh, Ww = out.shape[:2]
    pad = 4
    x0 = max(0, int(np.floor(xs.min())) - pad)
    y0 = max(0, int(np.floor(ys.min())) - pad)
    x1 = min(Ww, int(np.ceil(xs.max())) + pad)
    y1 = min(Hh, int(np.ceil(ys.max())) + pad)
    if x1 - x0 < Ww * 0.55 or y1 - y0 < Hh * 0.55:
        return out if abs(rot) >= 0.45 else warped
    crop = out[y0:y1, x0:x1]
    ch, cw = crop.shape[:2]
    ar = ch / max(cw, 1)
    if not (1.20 <= ar <= 2.15):
        return out if abs(rot) >= 0.45 else warped
    # Label-Schutz (A4): Bewertungslabel sitzt oben (~12–22%).
    # Höhe stark weg + Breite kaum → Fenster statt Case.
    if ch < H * 0.82 and cw > W * 0.90:
        return out if abs(rot) >= 0.45 else warped
    if ch * cw < H * W * 0.45:
        return out if abs(rot) >= 0.45 else warped
    # Gesamthöhe darf nicht stark schrumpfen (Case inkl. Label).
    if ch < H * 0.80:
        return out if abs(rot) >= 0.45 else warped
    # Oberer Zuschnitt in die Label-Zone bei spürbarer Höhenreduktion → Label weg.
    top_frac = y0 / max(Hh, 1)
    if top_frac >= 0.12 and ch < Hh * 0.92:
        return out if abs(rot) >= 0.45 else warped
    # Nur croppen, wenn der abgeschnittene Rand überwiegend Untergrund ist
    L2 = out.mean(axis=2)
    strips = []
    if y0 > 2:
        strips.append(L2[:y0, :].mean())
    if Hh - y1 > 2:
        strips.append(L2[y1:, :].mean())
    if x0 > 2:
        strips.append(L2[:, :x0].mean())
    if Ww - x1 > 2:
        strips.append(L2[:, x1:].mean())
    if strips and float(np.mean(strips)) > 110:
        # heller „Rand" = wahrscheinlich Case-Inhalt, nicht Tisch
        return out if abs(rot) >= 0.45 else warped
    return crop


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


def _slab_kontur_winkel(img) -> float:
    """Neigung aus minAreaRect der stärksten Außenkontur (Canny).

    Ergänzt Hough: Holo-Reflexe erzeugen Fantasie-Linien, die Kontur des
    Cases ist oft stabiler. Rückgabe in Grad (Normierung wie Hough).
    """
    import cv2
    import numpy as np

    H, W = img.shape[:2]
    if H < 80 or W < 60:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    # Weichzeichner nur zur Kantenerkennung — keine Kosmetik am Ergebnisbild.
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 120)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.morphologyEx(cv2.dilate(edges, k, iterations=2),
                             cv2.MORPH_CLOSE, k, iterations=3)
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return 0.0
    c = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(c) < 0.35 * H * W:
        return 0.0
    _rw, _rh = cv2.minAreaRect(c)[1]
    _ra = float(cv2.minAreaRect(c)[2])
    if _rw <= 0 or _rh <= 0:
        return 0.0
    if _rw >= _rh:
        _ra = _ra + 90.0
    ang = _norm_winkel_45(_ra)
    if abs(ang) < 0.6 or abs(ang) > 18.0:
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


def listing_suggests_sleeve(listing: dict | None) -> bool:
    """Analyse-Text nennt Schutzhülle/Toploader — unabhängig vom Cutout-Blick.

    Der Freisteller läuft VOR der Claude-Analyse. Deshalb kann die Analyse
    „Schutzhülle" schreiben, während der Cutout schon als raw-Rechteck
    gelaufen ist. Dieser Hinweis steuert die Sleeve-Nachbesserung."""
    if not listing:
        return False
    teile = [
        listing.get("condition_description"),
        listing.get("title"),
        listing.get("notes"),
        listing.get("packaging"),
    ]
    aspects = listing.get("aspects") or listing.get("item_specifics") or {}
    if isinstance(aspects, dict):
        teile.extend(f"{k} {v}" for k, v in aspects.items())
    blob = " ".join(str(t) for t in teile if t).lower()
    if not blob:
        return False
    schluessel = (
        "schutzhülle", "schutzhuelle", "schutzfolie", "toploader", "top loader",
        "top-loader", "softsleeve", "soft sleeve", "semi-rigid", "semirigid",
        "kartenhalter", "card holder", "cardholder", "sleeve", "hülle", "huelle",
    )
    return any(k in blob for k in schluessel)


def _sleeve_precrop_path(path: str, det: dict | None) -> str:
    """Eng an die Halter-Außenecken schneiden (mit kleiner Luft nach außen).

    Auf hellem Tisch verschwindet klares Plastik für rembg oft im Hintergrund —
    dann bleibt nur die Karte und raw-minAreaRect macht eckige Kanten. Der
    Vorzuschnitt hält Tisch draußen, damit der Sleeve-Soft-Alpha den Halter sieht."""
    if not det or not isinstance(det.get("corners"), list) or len(det["corners"]) != 4:
        return path
    try:
        import numpy as np
        from PIL import Image, ImageOps
        img = np.array(ImageOps.exif_transpose(Image.open(path)).convert("RGB"))
        H, W = img.shape[:2]
        pts = np.array(
            [[min(max(float(x), 0), 100) / 100 * W,
              min(max(float(y), 0), 100) / 100 * H]
             for x, y in det["corners"]],
            dtype=np.float32,
        )
        # Leicht nach außen, damit der Plastikrand nicht abgeschnitten wird.
        c = pts.mean(axis=0)
        pts = (c + (pts - c) * 1.04).astype(np.float32)
        pad = max(6, int(min(W, H) * 0.012))
        crop, _ = _crop_ecken(img, pts, pad=pad)
        if crop is img or crop.shape[0] < 120 or crop.shape[1] < 80:
            return path
        # Unplausibel eng (= eher Kartenfenster statt Halter) → Original behalten.
        if crop.shape[0] * crop.shape[1] < H * W * 0.18:
            return path
        tmp = str(Path(path).with_name(Path(path).stem + "_sleeve_tmp.jpg"))
        Image.fromarray(crop).save(tmp, quality=94)
        return tmp
    except Exception as e:  # noqa: BLE001
        log.warning("cardscan: Sleeve-Vorzuschnitt fehlgeschlagen für %s: %s", path, e)
        return path


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
    Ergebnis erreicht die Sammlung, das diese Prüfungen nicht besteht;
    fällt es durch, bleibt das Original stehen und der Scan läuft weiter.

    Seit Cutout v2 zusätzlich Alpha-/Rand-Hard-Fails (opak, Canvas-Touch).
    """
    try:
        import numpy as np
        with Image.open(path) as im:
            w, h = im.size
            if w < 300 or h < 300:
                return False                     # Winzling — Zuschnitt verrutscht
            ratio = h / max(w, 1)
            # Slab inkl. Label ist deutlich höher als die Rohkarte (~1.35–1.4).
            # Unter ~1.48 fehlt fast immer das Bewertungslabel (Case „abgeschnitten").
            if kind == "slab" and not (1.48 <= ratio <= 2.1):
                return False
            if kind in ("sleeve", "raw") and not (1.15 <= ratio <= 1.65):
                return False                     # Karten haben ~1.39
            # RGBA: Transparenz nicht als „schwarz" werten — sonst fällt eine
            # schlanke Flasche/ein Schuh mit viel Alpharand durch (Augustiner).
            if im.mode == "RGBA":
                bg = Image.new("RGB", im.size, (128, 128, 128))
                bg.paste(im, mask=im.split()[3])
                work = bg
            else:
                work = im.convert("RGB")
            klein = np.asarray(work.convert("L").resize((64, 64)), dtype=np.float32)
            if klein.std() < 12:
                return False                     # nahezu einfarbig — leerer Crop
            # Extremwert-Flächen: >85 % fast weiß oder fast schwarz heißt,
            # der Zuschnitt hat das Stück verloren
            if ((klein > 235).mean() > 0.85) or ((klein < 20).mean() > 0.85):
                return False
        # Alpha-QA nur für echte Cutout-PNGs (nicht Warp/Original-JPEG).
        if kind in ("slab", "raw", "sleeve") and str(path).endswith("_cut.png"):
            try:
                from web.cutout_v2.qa import evaluate_candidate
                from web.cutout_v2.types import legacy_kind_to_cutout
                ck = legacy_kind_to_cutout(kind)
                if ck is not None:
                    ev = evaluate_candidate(path, ck, require_margin=True)
                    if not ev["ok"]:
                        log.info("cardscan: bild_ok Alpha-QA fail %s %s",
                                 path, ev["hard_fails"])
                        return False
            except Exception as e:  # noqa: BLE001
                log.warning("cardscan: Alpha-QA übersprungen (%s)", e)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("cardscan: bild_ok scheiterte für %s: %s", path, e)
        return False


def cutout_usable(path: str, kind: str | None = None) -> bool:
    """Darf der Freisteller in die Sammlung?

    Karten-QA zuerst (Slab-Format, Alpha-Rand). Fällt die durch — typisch
    Hand+Case, Objekt am Fotorand — reicht die Alltags-Prüfung: lieber
    rembg-only als das Original mit Küche/Hand im Listing.
    """
    if not path or not Path(path).exists():
        return False
    if bild_ok(path, kind):
        return True
    if kind in ("slab", "sleeve", "raw") and bild_ok(path, "other"):
        log.info("cardscan: %s-QA fail, rembg-only bleibt (%s)", kind, path)
        return True
    return False


_rembg_session = None          # isnet — Graded/Slabs + Alltagsstücke
_rembg_session_product = None  # BiRefNet — Rohkarte / Hülle
_rembg_init_lock = threading.Lock()
REMBG_MODEL_SLAB = "isnet-general-use"      # Case + Label bleiben (Sven 09.08.)
REMBG_MODEL_CARD = "birefnet-general"       # Rohkarte / Top-Loader
REMBG_MODEL_PRODUCT = "isnet-general-use"   # Alltag: normaler Background-Remover
# Aliase für ältere Tests / Warmup
REMBG_MODEL_CARDS_DEFAULT = REMBG_MODEL_SLAB
REMBG_MODEL = REMBG_MODEL_CARD


def rembg_max_side(kind: str | None = None) -> int:
    """Längste Kante für rembg.

    12-MP + beide Modelle haben Contabo (8 GB) per OOM erschlagen.
    Karten behalten mehr Kante; Alltag kleiner (Tempo + RAM).
    Override: SERO_REMBG_MAX_SIDE=640…2000."""
    raw = (os.environ.get("SERO_REMBG_MAX_SIDE") or "").strip()
    if raw.isdigit():
        return max(640, min(2000, int(raw)))
    karte = kind in ("slab", "sleeve", "raw")
    if (os.environ.get("APP_ENV") or "").strip() == "production":
        return 1280 if karte else 1024
    return 2000 if karte else 1280


def ensure_rembg_session(slab: bool):
    """Modell einmal laden — Warmup und erster Cutout dürfen sich nicht
    überholen (sonst zwei volle ONNX-Kopien im RAM)."""
    global _rembg_session, _rembg_session_product
    from rembg import new_session
    with _rembg_init_lock:
        if slab:
            if _rembg_session is None:
                _rembg_session = new_session(REMBG_MODEL_SLAB)
            return _rembg_session
        if _rembg_session_product is None:
            _rembg_session_product = new_session(REMBG_MODEL_PRODUCT)
        return _rembg_session_product


# Transparenter Rand nach Alpha-BBox — gemessen an Collection-cut.png (~1 %)
CUTOUT_PAD_FRAC = 0.015


def layout_aus_alpha(out: "Image.Image", pad_frac: float = CUTOUT_PAD_FRAC) -> "Image.Image":
    """Enger Zuschnitt anhand der Alphamaske + gleichmäßiger transparenter Rand."""
    bbox = out.getbbox()
    if not bbox:
        return out
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    pad = max(4, int(pad_frac * max(w, h)))
    W, H = out.size
    return out.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                     min(W, bbox[2] + pad), min(H, bbox[3] + pad)))


def _smooth_column_silhouette(mask):
    """Hochkantige Vollkörper: geglättete L/R-Grenzen + weiches float-Alpha.

    Gibt (bool_mask, float_alpha|None) zurück. Seiten in der Mitte werden
    linearisiert (Dose = gerade Flanke), Deckel/Boden bleiben rund.
    Weiches Alpha ohne int-Runden — sonst neue Treppen."""
    import numpy as np
    from scipy import ndimage

    H, W = mask.shape
    rows = np.flatnonzero(mask.any(1))
    cols = np.flatnonzero(mask.any(0))
    if rows.size < 40 or cols.size < 8:
        return mask, None
    y0, y1 = int(rows[0]), int(rows[-1])
    x0, x1 = int(cols[0]), int(cols[-1])
    h = y1 - y0 + 1
    w = x1 - x0 + 1
    if h / max(w, 1) < 1.55:
        return mask, None
    if float(mask[y0:y1 + 1, x0:x1 + 1].mean()) < 0.72:
        return mask, None

    left = np.full(H, np.nan, dtype=np.float64)
    right = np.full(H, np.nan, dtype=np.float64)
    for y in range(y0, y1 + 1):
        xs = np.flatnonzero(mask[y])
        if xs.size:
            left[y] = float(xs[0])
            right[y] = float(xs[-1])

    def _fill_nan(arr):
        out = arr.copy()
        nans = np.isnan(out)
        if not nans.any() or nans.all():
            return out
        good = ~nans
        out[nans] = np.interp(np.flatnonzero(nans), np.flatnonzero(good), out[good])
        return out

    left = _fill_nan(left)
    right = _fill_nan(right)
    sigma = max(12.0, h * 0.035)
    left_s = ndimage.gaussian_filter1d(left, sigma=sigma, mode="nearest")
    right_s = ndimage.gaussian_filter1d(right, sigma=sigma, mode="nearest")

    cap = max(14, int(h * 0.18))
    y_a, y_b = y0 + cap, y1 - cap
    if y_b > y_a + 20:
        ys = np.arange(y_a, y_b + 1)
        # Gerade Flanke: Linie durch die Mitte (Dose/Flasche)
        left_s[ys] = np.polyval(np.polyfit(ys, left_s[ys], 1), ys)
        right_s[ys] = np.polyval(np.polyfit(ys, right_s[ys], 1), ys)

    # Breite stabil halten
    mid = 0.5 * (left_s + right_s)
    half_src = np.maximum(0.5 * (right - left), 2.0)
    half_src_s = ndimage.gaussian_filter1d(half_src, sigma=sigma, mode="nearest")
    half = np.maximum(0.5 * (right_s - left_s), half_src_s * 0.96)
    left_s = mid - half
    right_s = mid + half

    # Deckel/Boden: stark geglättetes Original (Rundung), nicht die Treppen
    left_cap = ndimage.gaussian_filter1d(left, sigma=max(6.0, h * 0.02), mode="nearest")
    right_cap = ndimage.gaussian_filter1d(right, sigma=max(6.0, h * 0.02), mode="nearest")
    for y in range(y0, y1 + 1):
        if y < y0 + cap or y > y1 - cap:
            dist = (y - y0) if y < y0 + cap else (y1 - y)
            t = dist / max(cap, 1)
            # am Pol: geglättetes Original; zur Mitte: lineare Flanke
            u = min(1.0, max(0.0, (t - 0.1) / 0.75))
            left_s[y] = (1 - u) * left_cap[y] + u * left_s[y]
            right_s[y] = (1 - u) * right_cap[y] + u * right_s[y]

    xs = np.arange(W, dtype=np.float64)
    alpha = np.zeros((H, W), dtype=np.float32)
    feather = 3.6
    for y in range(y0, y1 + 1):
        lo, hi = left_s[y], right_s[y]
        if hi <= lo + 1:
            continue
        dist = np.minimum(xs - lo, hi - xs)
        alpha[y] = np.clip(dist / feather, 0.0, 1.0).astype(np.float32)
    alpha = np.clip(ndimage.gaussian_filter(alpha, sigma=(1.4, 0.7)), 0.0, 1.0)
    return alpha > 0.04, alpha


def _polish_product_cutout(out: "Image.Image") -> "Image.Image":
    """Rand säubern und Silhouette glätten.

    rembg liefert oft harte Treppenkanten und einen hellen Farbsaum. Dagegen:
    1) größte Form behalten
    2) Maske leicht einziehen; Fuß-Schatten nur am äußeren Rand (nicht Motiv)
    3) Hochkant-Vollkörper: L/R-Kante linearisieren + weiches Alpha
    4) sonst: Blur mit stärkerer horizontaler Glättung
    5) Randfarbe vom Inneren holen
    Ohne scipy unverändert zurück."""
    try:
        import numpy as np
        from PIL import Image
        from scipy import ndimage
    except Exception:  # noqa: BLE001
        return out
    arr = np.array(out)
    if arr.ndim != 3 or arr.shape[2] != 4:
        return out
    alpha0 = arr[:, :, 3].astype(np.float32)
    mask = alpha0 >= 40
    if not mask.any():
        return out
    labels, n = ndimage.label(mask)
    if n > 1:
        sizes = ndimage.sum(mask, labels, range(1, n + 1))
        mask = labels == (int(np.argmax(sizes)) + 1)
    mask = ndimage.binary_erosion(mask, iterations=2)
    if not mask.any():
        return out
    rgb = arr[:, :, :3].copy().astype(np.float32)
    solid = ndimage.binary_erosion(mask, iterations=4)
    if not solid.any():
        solid = ndimage.binary_erosion(mask, iterations=2)
    interior_lum = float(rgb[solid].mean()) if solid.any() else 128.0
    rows = np.flatnonzero(mask.any(1))
    if rows.size and solid.any():
        y1 = int(rows[-1])
        foot_h = max(6, int((rows[-1] - rows[0] + 1) * 0.05))
        foot = np.zeros_like(mask)
        foot[max(0, y1 - foot_h):y1 + 1] = True
        # Nur äußerer Rand — dunkles Motiv (Skyline) nicht als Schatten werten
        rim = mask & ~ndimage.binary_erosion(mask, iterations=4)
        lum = rgb.mean(axis=2)
        shadow = foot & rim & (lum < interior_lum - 45)
        if shadow.any():
            mask &= ~ndimage.binary_dilation(shadow, iterations=1)
            if not mask.any():
                return out
            solid = ndimage.binary_erosion(mask, iterations=4)
            if not solid.any():
                solid = ndimage.binary_erosion(mask, iterations=2)
            if solid.any():
                interior_lum = float(rgb[solid].mean())

    mask, column_alpha = _smooth_column_silhouette(mask)
    if not mask.any():
        return out
    solid = ndimage.binary_erosion(mask, iterations=3)
    if not solid.any():
        solid = ndimage.binary_erosion(mask, iterations=2)
    if not solid.any():
        solid = mask

    nearest = None
    if solid.any():
        # Farbquelle tiefer innen — sonst färbt der helle rembg-Saum den Rand
        color_src = ndimage.binary_erosion(mask, iterations=6)
        if not color_src.any():
            color_src = ndimage.binary_erosion(mask, iterations=4)
        if not color_src.any():
            color_src = solid
        idx = ndimage.distance_transform_edt(
            ~color_src, return_distances=False, return_indices=True)
        nearest = rgb[tuple(idx)].copy()
        ring = ndimage.binary_dilation(mask, iterations=3) & ~solid
        rgb[ring] = nearest[ring]
        lum = rgb.mean(axis=2)
        fringe = mask & (lum > interior_lum + 28)
        rgb[fringe] = nearest[fringe]

    if column_alpha is not None:
        a = np.clip(column_alpha * 255.0, 0, 255)
        # Nur leicht horizontal nachfedern — kein erneutes Auf-Treppen-Schwellwerten
        a = ndimage.gaussian_filter(a, sigma=(0.8, 2.2))
        a = np.clip(a, 0, 255)
    else:
        ys, xs = np.nonzero(mask)
        span = float(max(ys.max() - ys.min() + 1, xs.max() - xs.min() + 1))
        sig_y = max(4.0, min(10.0, span * 0.008))
        sig_x = max(6.0, min(14.0, span * 0.014))
        mf = ndimage.gaussian_filter(mask.astype(np.float32), sigma=(sig_y, sig_x))
        rounded = (mf > 0.42).astype(np.float32)
        mf2 = ndimage.gaussian_filter(rounded, sigma=(sig_y * 0.45, sig_x * 0.55))
        a = np.clip(mf2 * 255.0, 0, 255)
        a[mf2 >= 0.88] = 255
        a[mf2 <= 0.05] = 0
    if nearest is not None:
        soft = (a > 6) & (a < 250)
        rgb[soft] = nearest[soft]
    # Heller Farbsaum: auch bei weichem Alpha nachfärben
    if solid.any() and nearest is not None:
        lum = rgb.mean(axis=2)
        fringe2 = (a > 20) & (lum > interior_lum + 24) & ~solid
        rgb[fringe2] = nearest[fringe2]
    out_arr = np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), a.astype(np.uint8)])
    out_arr[out_arr[:, :, 3] == 0, :3] = 0
    return Image.fromarray(out_arr, "RGBA")


def _cutout(path: str, out_path: str, kind: str | None = None) -> bool:
    """Hintergrund entfernen (rembg) → RGBA-PNG, eng beschnitten.

    Rohkarte (raw): BiRefNet → Form-Reparatur → Rechteck-Vorlage (opakes Inneres ok).

    Sleeve/Toploader: BiRefNet, weiches Alpha (Matting) — kein opakes MinAreaRect.

    Slabs/Graded: isnet, weiches Alpha — Case/Label bleiben; kein opakes Rechteck
    (sonst Tisch hinter Plastik eingebrannt; CutoutPipelineV2).

    Alles andere: `isnet-general-use` als normaler Background-Remover.
    Kein Warp, keine Politur, kein Rechteck-Auffüllen (sonst Tisch/Stuhl
    im Freisteller; Sven 18.08.2026 Augustiner-Flasche)."""
    try:
        import numpy as np
        from rembg import remove
        from PIL import Image, ImageFilter, ImageOps
        karte = kind in ("slab", "sleeve", "raw")
        slab = kind == "slab"
        sleeve = kind == "sleeve"
        # Nur Rohkarte: hartes post_process + opakes Rechteck. Slab/Sleeve: Matting.
        rect_fill = kind == "raw"
        # Graded/Slab + Alltag: isnet. Roh/Hülle: BiRefNet.
        model = REMBG_MODEL_SLAB if slab else (
            REMBG_MODEL_CARD if karte else REMBG_MODEL_PRODUCT
        )
        use_isnet = model == REMBG_MODEL_SLAB or model == REMBG_MODEL_PRODUCT
        session = ensure_rembg_session(slab=use_isnet)
        img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        side = rembg_max_side(kind)
        img.thumbnail((side, side))   # 12-MP-Fotos quälen CPU/RAM ohne Sichtgewinn
        # Nur Rohkarte: post_process härtet für Rechteck-Pfad. Slab/Sleeve/Produkt:
        # weiches Alpha behalten — sonst Tisch hinter Plastik eingebrannt.
        rem = remove(img, session=session, post_process_mask=rect_fill)
        a = np.array(rem.split()[3])
        # Weißes Buch / helles Cover: isnet hält oft nur das Cover-Motiv
        # (Schachfigur) und verwirft den Karton. u2netp sieht die Fläche.
        if not karte and float((a > 28).mean()) < 0.10:
            try:
                from rembg import new_session as _ns_fb
                rem_fb = remove(img, session=_ns_fb("u2netp"),
                                post_process_mask=False)
                a_fb = np.array(rem_fb.split()[3])
                frac_fb = float((a_fb > 28).mean())
                if 0.18 <= frac_fb < 0.92:
                    log.info("cardscan: isnet nur %.0f %% — u2netp %.0f %%",
                             float((a > 28).mean()) * 100, frac_fb * 100)
                    rem, a = rem_fb, a_fb
            except Exception as e:  # noqa: BLE001
                log.warning("cardscan: u2netp-Fallback fehlgeschlagen: %s", e)
        import cv2 as _cv
        # Slab/Sleeve: niedrigere Schwelle — durchsichtiges Plastik hat schwaches Alpha
        m = a > (18 if (slab or sleeve) else 40)
        if karte:
            # CLOSE groß genug für Lücke Label<->Karte; OPEN klein gegen Fransen
            close_sz = 81 if slab else (51 if sleeve else 61)
            m = _cv.morphologyEx(m.astype(np.uint8), _cv.MORPH_CLOSE,
                                 np.ones((close_sz, close_sz), np.uint8))
            m = _cv.morphologyEx(m, _cv.MORPH_OPEN,
                                 np.ones((7, 7), np.uint8)).astype(bool)
        else:
            # Produkt: weiches Alpha möglichst erhalten — harte OPEN-Maske
            # erzeugt Treppen an geraden Kanten (Dose).
            m = a > 28
            m = _cv.morphologyEx(m.astype(np.uint8), _cv.MORPH_OPEN,
                                 np.ones((3, 3), np.uint8)).astype(bool)
        if not m.any():
            return False
        # 1) nur die Komponente um die Bildmitte behalten (Finger/Krümel fliegen raus)
        H, W = m.shape
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
        if karte:
            # Slab-Label-Rettung: Label über der Karte als eigene Komponente
            xs_keep = np.nonzero(keep.any(0))[0]
            if xs_keep.size:
                kx0, kx1 = xs_keep[0], xs_keep[-1]
                n_lbl, lbl = _cv.connectedComponents(small.astype(np.uint8))
                for li in range(1, n_lbl):
                    comp = lbl == li
                    if (comp & keep).any():
                        continue
                    cxs = np.nonzero(comp.any(0))[0]
                    if cxs.size == 0:
                        continue
                    ueberlapp = max(0, min(kx1, cxs[-1]) - max(kx0, cxs[0]) + 1)
                    # Slab: auch kleinere Label-Komponenten retten
                    min_px = 40 if slab else 58
                    if (comp.sum() >= min_px
                            and ueberlapp / max(cxs[-1] - cxs[0] + 1, 1) > 0.55):
                        keep |= comp
        keep_full = np.array(Image.fromarray(keep.astype(np.uint8) * 255)
                             .resize((W, H), Image.BILINEAR)) > 127
        m &= keep_full
        if not m.any():
            return False

        if rect_fill:
            # 2) Rechteck-Vorlage NUR für Rohkarte (gerade Kanten)
            import cv2
            pts = cv2.findNonZero(m.astype(np.uint8))
            rect = cv2.minAreaRect(pts)
            (rw, rh) = rect[1]
            solid = None
            if rw > 1 and rh > 1 and m.sum() / (rw * rh) > 0.55:
                angle = rect[2]
                if angle > 45:
                    angle -= 90
                if 0.4 < abs(angle) < 20:
                    M = cv2.getRotationMatrix2D((W / 2, H / 2), angle, 1.0)
                    img = Image.fromarray(cv2.warpAffine(
                        np.array(img), M, (W, H), flags=cv2.INTER_CUBIC,
                        borderValue=(0, 0, 0)))
                    m = cv2.warpAffine(m.astype(np.uint8) * 255, M, (W, H)) > 127
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
                colspan = ((yi[:, None] >= y0[None, :])
                           & (yi[:, None] <= y1[None, :]) & cols[None, :])
                solid = rowspan & colspan
            frac = solid.mean()
            if frac < 0.05 or frac > 0.98:
                return False
            am = Image.fromarray((solid * 255).astype("uint8"))
            am = am.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(1.4))
            out = img.convert("RGBA")
            out.putalpha(am)
        elif slab or sleeve:
            # Weiches Alpha (Matting): kein opakes MinAreaRect — Plastik bleibt
            # durchscheinend, fotografierter Tisch wird nicht eingebrannt.
            soft = a.astype(np.float32)
            keep_soft = _cv.dilate(m.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
            soft[~keep_soft] = 0
            soft[~m] = 0
            soft = np.where(m, np.maximum(soft, 220.0), soft)
            soft = _cv.GaussianBlur(soft, (0, 0), sigmaX=1.2, sigmaY=1.2)
            soft[~keep_soft] = 0
            frac = (soft > 40).mean()
            if frac < 0.02 or frac > 0.98:
                return False
            rgb = np.array(img.convert("RGB"), dtype=np.float32)
            solid_core = soft > 240
            if solid_core.any():
                ys, xs = np.where(solid_core)
                cy, cx = int(ys.mean()), int(xs.mean())
                patch = rgb[max(0, cy - 2):cy + 3, max(0, cx - 2):cx + 3]
                if patch.size:
                    core_rgb = patch.mean(axis=(0, 1))
                    lum = rgb.mean(axis=2)
                    fringe = (soft > 20) & (soft < 250) & (lum > float(core_rgb.mean()) + 28)
                    rgb[fringe] = core_rgb
            out_arr = np.dstack([
                np.clip(rgb, 0, 255).astype(np.uint8),
                np.clip(soft, 0, 255).astype(np.uint8),
            ])
            out_arr[out_arr[:, :, 3] == 0, :3] = 0
            out = Image.fromarray(out_arr, "RGBA")
        else:
            # Produkt: rembg-Alpha × Mittel-Komponente, enger Zuschnitt.
            # Kein Warp, keine Politur (Sven: normaler Background-Remover).
            soft = a.astype(np.float32)
            keep_soft = _cv.dilate(m.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
            soft[~keep_soft] = 0
            soft[~m] = np.minimum(soft[~m], 90)  # Fransen außerhalb nur schwach
            frac = (soft > 40).mean()
            if frac < 0.02 or frac > 0.95:
                return False
            am = Image.fromarray(np.clip(soft, 0, 255).astype("uint8"))
            out = img.convert("RGBA")
            out.putalpha(am)

        out = layout_aus_alpha(out)
        if not out.getbbox():
            return False
        # Slab ohne Label früh verwerfen (gleiche Schwelle wie bild_ok)
        if slab:
            bw, bh = out.size
            if bh / max(bw, 1) < 1.48:
                log.info("cardscan: Slab-Cutout zu flach (%.2f) — Label fehlt vermutlich",
                         bh / max(bw, 1))
                return False
        out.save(out_path, "PNG")
        stem = Path(out_path).stem
        parent = Path(out_path).parent
        for muster in (f"{stem}_w*.jpg", f"{stem}_w*.webp",
                       f"{stem}_w*.png"):
            for tp in parent.glob(muster):
                tp.unlink(missing_ok=True)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("cardscan: Cutout fehlgeschlagen für %s: %s", path, e)
        return False


def _cutout_via_child(path: str, out_path: str, kind: str | None = None) -> bool:
    """rembg in einem frischen Python-Prozess.

    Am 18.08.2026 hat BiRefNet im uvicorn-Prozess Contabo (8 GB) per
    OOM-Killer beendet — RSS immer ~7,8 GB, UI blieb auf „Stelle Karte frei".
    Stirbt nur das Kind, bleibt die App stehen und der Scan geht ohne Alpha
    weiter (fail-open, wie bisher bei Cutout-Fehler)."""
    import subprocess
    import sys
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "1"
    env["SERO_CUTOUT_CHILD"] = "1"
    kind_s = kind or ""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "web.cutout_worker", path, out_path, kind_s],
            env=env,
            timeout=180,
            capture_output=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
    except subprocess.TimeoutExpired:
        log.warning("cardscan: Cutout-Kindprozess Timeout für %s", path)
        return False
    if r.returncode == 0 and Path(out_path).exists():
        return True
    err = (r.stderr or b"").decode("utf-8", "replace")[-400:]
    log.warning("cardscan: Cutout-Kindprozess rc=%s für %s %s",
                r.returncode, path, err)
    return False


def _cutout_job(path: str, out_path: str, kind: str | None = None) -> bool:
    """Produktion: eigenes Kind. Mac/Tests: inline (monkeypatch bleibt)."""
    if (os.environ.get("APP_ENV") or "").strip() == "production":
        if os.environ.get("SERO_CUTOUT_CHILD") == "1":
            return _cutout(path, out_path, kind)
        return _cutout_via_child(path, out_path, kind)
    return _cutout(path, out_path, kind)


# Der Freisteller (BiRefNet) rechnet auf der CPU und nutzt dabei selbst alle
# Kerne. Laufen zwei gleichzeitig, teilen sie sich dieselbe Rechenzeit und JEDER
# wird langsamer — bei vier Stücken auf einmal reißen dadurch alle den Zeitrahmen.
# Deshalb: immer nur EIN Freisteller. Das ist in Summe schneller, nicht langsamer.
_cut_lock = asyncio.Semaphore(1)


async def crop_photos(api_key: str, paths: list[str],
                      confirmed_kind: str | None = None,
                      item: dict | None = None) -> tuple[list[str], dict]:
    """Fotos freistellen. Karten/Slabs: Warp dann rembg. Alltag: nur rembg.

    Klassifikation (Glance/Item/Geometrie) vor dem Cutout. Misserfolg →
    Original bleibt. Vorder-/Rückseite (idx < 2) werden freigestellt;
    weitere Aufnahmen bleiben Zusatzbilder.

    confirmed_kind / item: deterministisches Routing (Graded bleibt Slab) —
    Alltagsstücke (generic) bekommen keinen Warp, auch wenn Vision früher
    fälschlich „slab“ gesagt hat.
    """
    def one(p: str, kind: str | None) -> str:
        out = str(Path(p).with_name(Path(p).stem + "_cut.png"))
        # CutoutPipelineV2 (Flag) — gemeinsamer Kern
        from web.pipeline_flags import cutout_v2_enabled
        _iid = (item or {}).get("id") if item else None
        cut_kind = None if kind in ("other", "product") else kind
        if cut_kind and cutout_v2_enabled(_iid):
            try:
                from web.cutout_v2 import CutoutRequest, run_cutout
                from web.cutout_v2.types import legacy_kind_to_cutout
                ck = legacy_kind_to_cutout(cut_kind)
                if ck is not None:
                    res = run_cutout(CutoutRequest(
                        source_path=Path(p),
                        confirmed_kind=ck,
                        kind_source="confirmed",
                        output_path=Path(out),
                        item_id=_iid,
                    ))
                    if res.status == "SUCCESS" and res.selected_path:
                        return str(res.selected_path)
                    return p
            except Exception as e:  # noqa: BLE001
                log.warning("cardscan: cutout_v2 Fallback auf Legacy (%s)", e)
        if _cutout_job(p, out, cut_kind) and bild_ok(out, cut_kind):
            return out
        return p

    # Routing: bestätigt > persistiert > Glance > Geometrie. Alltag → other.
    forced_kind = confirmed_kind
    try:
        from web.cutout_v2.routing import (
            resolve_kind, should_warp, item_is_non_card,
        )
        from web.cutout_v2.types import cutout_kind_to_legacy
        if item_is_non_card(item):
            forced_kind = "other"
        else:
            rk, _, _, _ = resolve_kind(item=item, persisted_kind=confirmed_kind)
            if rk is not None:
                forced_kind = cutout_kind_to_legacy(rk)
    except Exception:  # noqa: BLE001
        from web.cutout_v2.routing import should_warp  # noqa: F811
        pass

    async def _classify_photo(p: str, kind: str | None) -> tuple[str | None, dict | None]:
        """Glance kurz, sonst Rechteck-Geometrie, sonst detect_card."""
        det = None
        if kind in ("other", "product"):
            return "other", None
        if kind is not None:
            return kind, None
        glance = None
        try:
            glance = await asyncio.wait_for(
                glance_scan(api_key, p, item), timeout=GLANCE_TIMEOUT_S)
        except Exception as e:  # noqa: BLE001
            log.warning("cardscan: Glance übersprungen für %s: %s", p, e)
        geo = None
        try:
            geo = flat_rectangle_hint(p)
        except Exception:  # noqa: BLE001
            geo = None
        try:
            from web.cutout_v2.routing import resolve_scan_kind, scan_kind_to_legacy
            sk, src = resolve_scan_kind(item=item, glance=glance, geometry_hint=geo)
            if sk:
                log.info("cardscan: Scan-Kind %s (%s) für %s", sk, src, p)
                return scan_kind_to_legacy(sk), None
        except Exception:  # noqa: BLE001
            pass
        # Letzter Ausweg (Tests + API-Ausfall): detect_card wie bisher.
        try:
            det = await detect_card(_anthropic(api_key), p)
        except Exception as e:  # noqa: BLE001
            log.warning("cardscan: Erkennungs-Blick fehlgeschlagen für %s: %s", p, e)
        return (det.get("kind") if det else None), det

    loop = asyncio.get_running_loop()
    results = []
    kinds_seen: list[str | None] = []
    for idx, p in enumerate(paths):
        if idx < 2:
            det1 = None
            kind = forced_kind
            if kind in ("other", "product"):
                kind = "other"
            elif kind is None:
                kind, det1 = await _classify_photo(p, None)
            elif forced_kind in ("slab", "sleeve", "raw"):
                # Ecken für Warp (Slab/Raw) bzw. Vorzuschnitt (Sleeve) holen.
                # Slab bleibt bestätigt (nie auf raw zurückstufen).
                try:
                    det1 = await detect_card(_anthropic(api_key), p)
                    if det1 and forced_kind == "slab":
                        det1 = {**det1, "kind": "slab"}
                    elif det1 and forced_kind == "raw" and det1.get("kind") in (
                            "sleeve", "slab"):
                        kind = det1["kind"]
                    elif det1:
                        det1 = {**det1, "kind": forced_kind}
                except Exception as e:  # noqa: BLE001
                    log.warning("cardscan: Erkennungs-Blick fehlgeschlagen für %s: %s", p, e)
            corners = (det1 or {}).get("corners") if det1 else None
            try:
                do_warp = should_warp(kind, item, corners)
            except Exception:  # noqa: BLE001
                do_warp = kind in ("slab", "raw")
            if kind in ("slab", "raw") and not do_warp and corners:
                kind = "other"
            kinds_seen.append(kind)
            out = str(Path(p).with_name(Path(p).stem + "_cut.png"))
            # Karte/Slab: erst aufrichten (Rechteck), dann rembg.
            if do_warp:
                warp_tmp = str(Path(p).with_name(Path(p).stem + "_warp_tmp.png"))
                warped = False
                try:
                    warped = bool(
                        await slab_recut(api_key, p, warp_tmp, det=det1)
                        and Path(warp_tmp).exists()
                    )
                except Exception as e:  # noqa: BLE001
                    log.warning("cardscan: Rechteck-Warp fehlgeschlagen für %s: %s", p, e)
                rembg_kind = "slab" if kind == "slab" else "raw"
                src_for_cut = warp_tmp if warped else p
                async with _cut_lock:
                    ok = await loop.run_in_executor(
                        None, _cutout_job, src_for_cut, out, rembg_kind)
                Path(warp_tmp).unlink(missing_ok=True)
                if ok and cutout_usable(out, rembg_kind):
                    results.append(out)
                    continue
                # Warp/QA schlecht → rembg-only, nicht Original liegen lassen.
                if not (ok and Path(out).exists() and cutout_usable(out, "other")):
                    Path(out).unlink(missing_ok=True)
                    async with _cut_lock:
                        ok = await loop.run_in_executor(
                            None, _cutout_job, p, out, "other")
                if ok and cutout_usable(out, "other"):
                    log.info("cardscan: Warp-Fallback rembg-only für %s", p)
                    results.append(out)
                    continue
                Path(out).unlink(missing_ok=True)
                results.append(p)
                continue
            if kind == "sleeve":
                # Vorzuschnitt auf Halter-Außenkante, dann Soft-Alpha — nie raw-Rect.
                sleeve_tmp = _sleeve_precrop_path(p, det1)
                async with _cut_lock:
                    ok = await loop.run_in_executor(
                        None, _cutout_job, sleeve_tmp, out, "sleeve")
                if sleeve_tmp != p:
                    Path(sleeve_tmp).unlink(missing_ok=True)
                if ok and cutout_usable(out, "sleeve"):
                    results.append(out)
                    continue
                Path(out).unlink(missing_ok=True)
                async with _cut_lock:
                    ok = await loop.run_in_executor(
                        None, _cutout_job, p, out, "other")
                if ok and cutout_usable(out, "other"):
                    log.info("cardscan: Sleeve-Fallback rembg-only für %s", p)
                    results.append(out)
                    continue
                Path(out).unlink(missing_ok=True)
                results.append(p)
                continue
            async with _cut_lock:
                results.append(await loop.run_in_executor(None, one, p, kind))
        else:
            results.append(p)
            kinds_seen.append(None)
    primary = next((k for k in kinds_seen if k in ("slab", "sleeve", "raw", "other")), None)
    cropped_n = sum(1 for r, p in zip(results, paths) if r != p)
    info = {
        "cropped": cropped_n,
        "total": len(paths),
        "kinds": kinds_seen,
        "kind": primary,
        "error": None if cropped_n else "no_cutout",
    }
    return results, info


async def slab_recut(api_key: str, src_path: str, out_path: str,
                     min_area_frac: float = 0.0,
                     det: dict | None = None) -> bool:
    """Rechteck-Warp: Case- oder Karten-Ecken → aufrecht → eng zuschneiden.

    Slab: NUR das Case-Rechteck (Außenkanten). Die Karte im Sichtfenster
    wird nicht extra entzerrt — sie darf im Case schief sitzen.

    Rohkarte: Warp aufs Karten-Rechteck (alte Rechteck-Technik), keine Kosmetik.

    Wenn gegenüberliegende Kanten fast gleich lang sind (Symmetrie-Gates),
    richtet ein Perspektiv-Warp auf die Ecken auf — das ist für ein
    Parallelogramm kein Zerren und schneidet eng. Sonst nur ROTATION
    (warpAffine), nie strecken (Sven: „Don't distort, just straighten").

    min_area_frac: Flächenanteil am Rohbild, den das gefundene Rechteck
    ÜBERTREFFEN muss. Der Aufrufer übergibt den Anteil des bisherigen
    Zuschnitts × Reserve — so ersetzt der Zuschnitt nur dann, wenn der
    Segmentierer wirklich etwas verschluckt hat."""
    if det is None:
        # Eigenständiger Lauf (Rettungspfad nach der Analyse) — sonst reicht
        # der Aufrufer den Blick aus crop_photos durch und spart den Call.
        det = await detect_card(_anthropic(api_key), src_path)
    if not det or det.get("kind") not in ("slab", "raw"):
        return False
    is_slab = det.get("kind") == "slab"
    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageDraw, ImageOps
        img = np.array(ImageOps.exif_transpose(Image.open(src_path)).convert("RGB"))
        H, W = img.shape[:2]
        pts = np.array([[min(max(x, 0), 100) / 100 * W, min(max(y, 0), 100) / 100 * H]
                        for x, y in det["corners"]], dtype=np.float32)
        # 5 % Einzug: Vision-Ecken sitzen oft am Tisch außerhalb der Kante.
        _c = pts.mean(axis=0)
        pts = (_c + (pts - _c) * 0.95).astype(np.float32)
        if min_area_frac > 0:
            frac = float(cv2.contourArea(pts)) / max(W * H, 1)
            if frac < min_area_frac:
                log.info("cardscan: slab_recut — Rechteck (%.0f %%) nicht größer als "
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
        # Plausibilität: Karten/Slabs sind Hochkant-Rechtecke.
        ar_lo, ar_hi = (1.1, 2.0) if is_slab else (1.15, 1.75)
        if not (ar_lo <= H2 / max(W2, 1) <= ar_hi):
            log.warning("cardscan: slab_recut-Ecken unplausibel (%dx%d) — verworfen", W2, H2)
            return False
        _top = np.linalg.norm(tr - tl); _bot = np.linalg.norm(br - bl)
        _lft = np.linalg.norm(bl - tl); _rgt = np.linalg.norm(br - tr)
        asym_tb = abs(_top - _bot) / max(_top, _bot)
        asym_lr = abs(_lft - _rgt) / max(_lft, _rgt)
        # Vorab: steckt das Rechteck schief in einem Vision-AABB? Dann zieht
        # Perspektiv die Schräge NICHT raus — Rotation zuerst.
        rough0, _ = _crop_ecken(img, pts, pad=max(8, int(min(W, H) * 0.01)))
        ang_ecken0 = _norm_winkel_45(float(np.degrees(np.arctan2(
            (tr - tl)[1], (tr - tl)[0]))))
        # Slab: nur Case-Außenkanten — die Karte im Fenster nicht entbiegen.
        ang_inhalt0 = 0.0 if is_slab else _slab_inhalt_winkel(rough0)
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
            # Inhalt gewinnt nur bei Rohkarte. Slab: Case-Kanten, nicht Fensterkarte.
            if (not is_slab and abs(ang_inhalt) >= 0.8
                    and abs(ang_inhalt) > abs(angle) + 0.5):
                angle = -ang_inhalt
            ang_kontur = _slab_kontur_winkel(rough0)
            if abs(ang_kontur) >= 0.6 and abs(ang_kontur) > abs(angle) + 0.3:
                angle = -ang_kontur
            # Kappe: Holo-Reflexe erzeugen Fantasie-Winkel >8°.
            if abs(angle) > 18.0:
                angle = 0.0
            rotated, M_aff = _affine_drehen(img, angle)
            pts_r = _pts_affine(pts, M_aff)
            warped, (cx0, cy0) = _crop_ecken(rotated, pts_r, pad=2)
            M_box = np.eye(3, dtype=np.float64)
            M_box[:2, :] = M_aff
            M_box[0, 2] -= cx0
            M_box[1, 2] -= cy0

        # Slab: Nachschnitt über Label+Fenster (Plastikrand bleibt).
        # Rohkarte: kein Case-Fenster — nur Kanten/Tisch.
        if is_slab:
            warped = _case_nach_boxen(warped, det, pts, M_box, W, H)
        # BEWUSST keine Studio-Kosmetik: Warp/Rotation allein IST der Look —
        # aufrecht, Schnitt an der Case-Kante, Plastik wie fotografiert.
        warped = kanten_trim(warped)     # Gradient an der Case-Kante
        warped = tisch_trim(warped)      # warmen Tisch/Kork am Rand weg
        warped = untergrund_trim(warped)  # Filz/Stoff/Studio-Rand weg
        if is_slab:
            warped = case_kontur_nachschnitt(warped)  # Kontur → aufrecht + eng
        # Restneigung der Karte selbst nur bei Rohkarte, nie Case-Innere.
        if not is_slab:
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
    # CGC-Rim ≈ 5–8 % der Labelbreite je Seite; oben ~0,40 Labelhöhe.
    px = max(4.0, (lx1 - lx0) * 0.055)
    pt = max(4.0, (ly1 - ly0) * 0.40)
    pb = max(4.0, (wy1 - wy0) * 0.055)
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
