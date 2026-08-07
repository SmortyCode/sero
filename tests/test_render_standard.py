"""Der RENDER-STANDARD — Svens Dauer-Entscheid vom 03.08.2026, in Tests gegossen.

Drei Kosmetik-Anläufe an einem Tag (Milchglas, Dunkel-Regeln, Schutzboxen)
erzeugten nacheinander schwarze Fetzen, ausgewaschene Cover und hellgraue
Querstreifen — Sven musste jedes Mal korrigieren. Wörtlich: „Es kann ja
nicht sein, dass ich dich immer korrigieren muss."

Diese Datei ist der Vertrag: slab → Ecken-Warp OHNE Nachbearbeitung ·
sleeve/raw → Segmentierer · unbekannt → Original. Jedes Ergebnis passiert
bild_ok(). Wer den Standard ändern will, macht ERST diese Tests grün —
und holt sich Svens Ja.
"""

import inspect

import pytest
from PIL import Image, ImageDraw

from web import cardscan


# ────────────────── Der Vertrag: keine Kosmetik im Warp ──────────────────

def test_warp_pfad_enthaelt_keine_kosmetik():
    """slab_recut darf NIE wieder Nachbearbeitung enthalten. Der Test liest
    den Quelltext — Wiedereinbau von Milchglas & Co. macht ihn sofort rot."""
    quelle = inspect.getsource(cardscan.slab_recut)
    for verboten in ("_studio_hintergrund", "rembg", "remove(", "milch",
                     "GaussianBlur", "dunkel"):
        assert verboten not in quelle, (
            f"Kosmetik ({verboten}) im Warp-Pfad — Svens Standard vom 03.08. "
            "verbietet Nachbearbeitung. Erst sein Ja holen, dann diesen Test ändern.")


def test_standard_steht_im_modul():
    """Der Standard muss als Vertrag im Modul-Docstring stehen bleiben."""
    doc = cardscan.__doc__ or ""
    assert "RENDER-STANDARD" in doc and "KEINE selektive Nachbearbeitung" in doc


# ────────────────── Pfadwahl: slab→Warp, sonst Segmentierer ──────────────────

@pytest.mark.asyncio
async def test_slab_nimmt_den_warp(tmp_path, monkeypatch):
    foto = tmp_path / "slab.jpg"
    Image.new("RGB", (900, 1300), (120, 120, 130)).save(foto)

    async def fake_detect(client, p):
        return {"kind": "slab", "corners": [[5, 3], [95, 3], [95, 97], [5, 97]],
                "confidence": "high"}

    aufrufe = {"warp": 0, "cutout": 0}

    async def fake_recut(api_key, src, out, min_area_frac=0.0, det=None):
        aufrufe["warp"] += 1
        Image.new("RGB", (800, 1200), (90, 95, 100)).save(out)
        return True

    monkeypatch.setattr(cardscan, "detect_card", fake_detect)
    monkeypatch.setattr(cardscan, "slab_recut", fake_recut)
    monkeypatch.setattr(cardscan, "_cutout", lambda *a, **k: aufrufe.__setitem__("cutout", 1))
    monkeypatch.setattr(cardscan, "bild_ok", lambda p, k=None: True)

    res, info = await cardscan.crop_photos("key", [str(foto)])
    assert aufrufe["warp"] == 1 and aufrufe["cutout"] == 0
    assert res[0].endswith("_cut.png") and info["cropped"] == 1


@pytest.mark.asyncio
async def test_huelle_nimmt_den_segmentierer(tmp_path, monkeypatch):
    foto = tmp_path / "sleeve.jpg"
    Image.new("RGB", (900, 1300), (120, 120, 130)).save(foto)

    async def fake_detect(client, p):
        return {"kind": "sleeve", "corners": [[5, 3], [95, 3], [95, 97], [5, 97]],
                "confidence": "high"}

    aufrufe = {"warp": 0, "cutout": 0}

    async def fake_recut(*a, **k):
        aufrufe["warp"] += 1
        return True

    def fake_cutout(p, out):
        aufrufe["cutout"] += 1
        Image.new("RGB", (700, 980), (90, 95, 100)).save(out)
        return True

    monkeypatch.setattr(cardscan, "detect_card", fake_detect)
    monkeypatch.setattr(cardscan, "slab_recut", fake_recut)
    monkeypatch.setattr(cardscan, "_cutout", fake_cutout)
    monkeypatch.setattr(cardscan, "bild_ok", lambda p, k=None: True)

    res, info = await cardscan.crop_photos("key", [str(foto)])
    assert aufrufe["warp"] == 0 and aufrufe["cutout"] == 1


@pytest.mark.asyncio
async def test_warp_fehlschlag_faellt_auf_segmentierer(tmp_path, monkeypatch):
    """Reißen die Warp-Schutzchecks, übernimmt der Segmentierer — nie bleibt
    der Scan ohne Versuch."""
    foto = tmp_path / "slab.jpg"
    Image.new("RGB", (900, 1300), (120, 120, 130)).save(foto)

    async def fake_detect(client, p):
        return {"kind": "slab", "corners": [[5, 3], [95, 3], [95, 97], [5, 97]],
                "confidence": "high"}

    async def fake_recut(*a, **k):
        return False

    getroffen = {"cutout": 0}

    def fake_cutout(p, out):
        getroffen["cutout"] += 1
        Image.new("RGB", (700, 980), (90, 95, 100)).save(out)
        return True

    monkeypatch.setattr(cardscan, "detect_card", fake_detect)
    monkeypatch.setattr(cardscan, "slab_recut", fake_recut)
    monkeypatch.setattr(cardscan, "_cutout", fake_cutout)
    monkeypatch.setattr(cardscan, "bild_ok", lambda p, k=None: True)

    res, info = await cardscan.crop_photos("key", [str(foto)])
    assert getroffen["cutout"] == 1 and info["cropped"] == 1


@pytest.mark.asyncio
async def test_schlechtes_bild_erreicht_nie_die_sammlung(tmp_path, monkeypatch):
    """Fällt das Ergebnis bei bild_ok durch, bleibt das ORIGINAL — der Kern
    des Standards: nie ein schlechtes Bild speichern."""
    foto = tmp_path / "slab.jpg"
    Image.new("RGB", (900, 1300), (120, 120, 130)).save(foto)

    async def fake_detect(client, p):
        return {"kind": "slab", "corners": [[5, 3], [95, 3], [95, 97], [5, 97]],
                "confidence": "high"}

    async def fake_recut(api_key, src, out, min_area_frac=0.0, det=None):
        Image.new("RGB", (80, 90), (0, 0, 0)).save(out)   # Müll-Ergebnis
        return True

    def fake_cutout(p, out):
        Image.new("RGB", (60, 60), (0, 0, 0)).save(out)   # auch Müll
        return True

    monkeypatch.setattr(cardscan, "detect_card", fake_detect)
    monkeypatch.setattr(cardscan, "slab_recut", fake_recut)
    monkeypatch.setattr(cardscan, "_cutout", fake_cutout)
    # ECHTES bild_ok — es muss den Müll fangen
    res, info = await cardscan.crop_photos("key", [str(foto)])
    assert res[0] == str(foto), "Müll-Bild wurde gespeichert statt Original behalten"
    assert info["cropped"] == 0


# ────────────────── kanten_trim: exakter Nachschnitt ──────────────────

def test_kanten_trim_entfernt_uebermass():
    """Svens Kachel-Befund (03.08., 21:56): 2-3 % Foto-Untergrund am Rand.
    Der Trim findet die Case-Kante als stärksten Gradienten und schneidet
    exakt — deterministisch, ohne Modell."""
    import numpy as np
    H, W = 1000, 700
    bild = np.full((H, W, 3), 45, dtype=np.uint8)          # Foto-Untergrund
    bild[30:H - 30, 25:W - 25] = 225                        # der Case
    getrimmt = cardscan.kanten_trim(bild)
    th, tw = getrimmt.shape[:2]
    # Übermaß (30/25 px) ist weg, bis auf die kleine Sicherheitsmarge
    assert H - 70 <= th <= H - 52 and W - 60 <= tw <= W - 42
    # und der Rand ist jetzt CASE, nicht Untergrund
    assert getrimmt[0, :, 0].mean() > 150 and getrimmt[-1, :, 0].mean() > 150


def test_kanten_trim_laesst_sauberes_bild_in_ruhe():
    """Keine klare Kante im Randband → nichts schneiden. Der Trim darf ein
    korrekt gewarptes Bild nicht anfressen."""
    import numpy as np
    rng = np.random.default_rng(7)
    bild = rng.integers(80, 180, (1000, 700, 3), dtype=np.uint8).astype(np.uint8)
    getrimmt = cardscan.kanten_trim(bild)
    assert getrimmt.shape[0] >= 990 and getrimmt.shape[1] >= 690


# ────────────────── Belichtung: global oder gar nicht ──────────────────

def test_belichtung_hellt_unterbelichtetes_global_auf():
    import numpy as np
    dunkel_foto = np.full((400, 300, 3), 60, dtype=np.uint8)
    dunkel_foto[100:300, 80:220] = 110
    hell = cardscan.belichtung_normalisieren(dunkel_foto)
    assert hell.mean() > dunkel_foto.mean() * 1.3
    # GLOBAL heißt: das Verhältnis zweier Flächen bleibt erhalten (linear)
    v_vorher = dunkel_foto[150, 150, 0] / dunkel_foto[10, 10, 0]
    v_nachher = hell[150, 150, 0] / max(int(hell[10, 10, 0]), 1)
    assert abs(v_vorher - v_nachher) < 0.15


def test_belichtung_laesst_gute_fotos_in_ruhe():
    import numpy as np
    gut = np.full((400, 300, 3), 190, dtype=np.uint8)
    gut[100:300, 80:220] = 90
    raus = cardscan.belichtung_normalisieren(gut)
    assert (raus == gut).all(), "Gut belichtetes Foto wurde angefasst"


# ────────────────── bild_ok: die Wache selbst ──────────────────

def _strukturbild(w, h):
    """Grobe Blöcke wie ein echtes Kartenfoto (Label, Artwork, Textfeld) —
    feine Muster verschmelzen beim 64er-Downscale von bild_ok zu Einheitsgrau."""
    im = Image.new("RGB", (w, h), (200, 200, 205))
    d = ImageDraw.Draw(im)
    d.rectangle([int(w * .1), int(h * .05), int(w * .9), int(h * .2)], fill=(30, 35, 50))
    d.rectangle([int(w * .15), int(h * .3), int(w * .85), int(h * .7)], fill=(90, 140, 90))
    d.rectangle([int(w * .15), int(h * .75), int(w * .85), int(h * .92)], fill=(60, 60, 70))
    return im


def test_bild_ok_gutes_slab_format(tmp_path):
    p = tmp_path / "gut.png"
    _strukturbild(800, 1150).save(p)
    assert cardscan.bild_ok(str(p), "slab") is True


@pytest.mark.parametrize("w,h,kind", [
    (200, 280, "slab"),        # zu klein — Zuschnitt verrutscht
    (1200, 900, "slab"),       # quer — kein Slab
    (900, 2400, "slab"),       # absurd gestreckt
    (900, 900, "sleeve"),      # quadratisch — keine Karte
])
def test_bild_ok_faengt_kaputte_formate(tmp_path, w, h, kind):
    p = tmp_path / "schlecht.png"
    _strukturbild(w, h).save(p)
    assert cardscan.bild_ok(str(p), kind) is False


def test_bild_ok_faengt_leere_crops(tmp_path):
    p = tmp_path / "leer.png"
    Image.new("RGB", (800, 1150), (250, 250, 250)).save(p)
    assert cardscan.bild_ok(str(p), "slab") is False


def test_bild_ok_ohne_kind_prueft_nur_generisch(tmp_path):
    """Displays und Unbekanntes (detect=None) dürfen quer sein — nur die
    generischen Checks (Größe, Struktur) gelten."""
    p = tmp_path / "display.png"
    _strukturbild(1400, 900).save(p)
    assert cardscan.bild_ok(str(p), None) is True
