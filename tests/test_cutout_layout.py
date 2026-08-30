"""Regression: Freisteller-Layout und Alpha-Eigenschaften (ohne Live-Modell)."""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from web import cardscan

WURZEL = Path(__file__).resolve().parent.parent
REFS = json.loads((WURZEL / "tests/fixtures/cutout_refs.json").read_text(encoding="utf-8"))


def test_referenzdateien_existieren_und_bleiben_unveraendert():
    for r in REFS["refs"]:
        p = WURZEL / r["photo"]
        assert p.exists(), f"Referenz fehlt: {p}"
        if r.get("raw"):
            assert (WURZEL / r["raw"]).exists()


def test_cutout_booster_hat_alpha_und_transparente_ecken():
    p = WURZEL / "collection_photos/35a64a879d80/00_cut.png"
    im = Image.open(p)
    assert im.mode == "RGBA"
    a = np.array(im)[:, :, 3]
    assert a[0, 0] < 8 and a[0, -1] < 8 and a[-1, 0] < 8 and a[-1, -1] < 8
    assert (a > 10).mean() > 0.5


def test_layout_aus_alpha_laesst_rand():
    im = Image.new("RGBA", (400, 600), (0, 0, 0, 0))
    for y in range(80, 520):
        for x in range(60, 340):
            im.putpixel((x, y), (200, 100, 50, 255))
    out = cardscan.layout_aus_alpha(im, pad_frac=0.015)
    arr = np.array(out)
    a = arr[:, :, 3]
    assert a[0, 0] < 8 and a[-1, -1] < 8
    assert (a > 10).any()
    assert not (a[0, :] > 10).any()
    assert not (a[-1, :] > 10).any()
    assert not (a[:, 0] > 10).any()
    assert not (a[:, -1] > 10).any()
    h, w = a.shape
    ys, xs = np.where(a > 10)
    for v in (ys.min() / h, (h - 1 - ys.max()) / h, xs.min() / w, (w - 1 - xs.max()) / w):
        assert 0.005 <= v <= 0.08, v


def test_cutout_fehler_liefert_false(tmp_path, monkeypatch):
    src = tmp_path / "x.jpg"
    Image.new("RGB", (200, 300), (80, 80, 80)).save(src)
    out = tmp_path / "x_cut.png"

    def boom(*a, **k):
        raise RuntimeError("kein modell")

    import rembg
    monkeypatch.setattr(rembg, "remove", boom)
    monkeypatch.setattr(rembg, "new_session", lambda *a, **k: object())
    cardscan._rembg_session = None
    assert cardscan._cutout(str(src), str(out)) is False


def test_rembg_modell_ist_festgelegt():
    assert cardscan.REMBG_MODEL_SLAB == "isnet-general-use"
    assert cardscan.REMBG_MODEL_CARD == "birefnet-general"
    assert cardscan.REMBG_MODEL_PRODUCT == "isnet-general-use"
    assert cardscan.REMBG_MODEL_CARDS_DEFAULT == "isnet-general-use"
    # Graded/Slab + Alltag → isnet; Roh/Hülle → BiRefNet
    src = inspect.getsource(cardscan._cutout)
    assert "REMBG_MODEL_SLAB if slab" in src
    assert "REMBG_MODEL_CARD if karte" in src
    assert "ensure_rembg_session" in src
    assert "rembg_max_side" in src
    assert "_polish_product_cutout" not in src


def test_rembg_max_side_production_kleiner(monkeypatch):
    monkeypatch.delenv("SERO_REMBG_MAX_SIDE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    assert cardscan.rembg_max_side() == 1280
    assert cardscan.rembg_max_side("raw") == 2000
    monkeypatch.setenv("APP_ENV", "production")
    assert cardscan.rembg_max_side() == 1024
    assert cardscan.rembg_max_side("slab") == 1280
    monkeypatch.setenv("SERO_REMBG_MAX_SIDE", "1024")
    assert cardscan.rembg_max_side("slab") == 1024


def test_cutout_job_ohne_production_bleibt_inline(monkeypatch, tmp_path):
    monkeypatch.delenv("APP_ENV", raising=False)
    called = {}

    def fake(path, out, kind=None):
        called["kind"] = kind
        Path(out).write_bytes(b"x")
        return True

    monkeypatch.setattr(cardscan, "_cutout", fake)
    monkeypatch.setattr(cardscan, "_cutout_via_child", lambda *a, **k: (_ for _ in ()).throw(AssertionError("child")))
    dest = tmp_path / "o.png"
    assert cardscan._cutout_job(str(tmp_path / "a.jpg"), str(dest), kind="raw") is True
    assert called["kind"] == "raw"


def test_polish_dunkles_produkt_senkt_hellen_rand(tmp_path):
    """Heller Halo am schwarzen Stoff wird eingezogen / umgefärbt."""
    import numpy as np
    from PIL import Image as _Image

    # Schwarzer Kreis mit hellgrauem 4px-Saum (wie Schreibtisch-Fransen)
    im = _Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    pix = im.load()
    cx = cy = 100
    for y in range(200):
        for x in range(200):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 <= 55 * 55:
                pix[x, y] = (20, 20, 20, 255)
            elif d2 <= 60 * 60:
                pix[x, y] = (200, 180, 160, 180)
    out = cardscan._polish_product_cutout(im)
    a = np.array(out)
    # Randring 55–60: nach Polish wenig helles RGB bei Rest-Alpha
    ring = []
    for y in range(200):
        for x in range(200):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if 55 * 55 < d2 <= 60 * 60 and a[y, x, 3] > 40:
                ring.append(float(a[y, x, :3].mean()))
    if ring:
        assert sum(ring) / len(ring) < 80, ring[:5]


def test_polish_macht_weiche_kante():
    """Nach Polish gibt es echte Zwischenwerte — keine reine 0/255-Treppe."""
    import numpy as np
    from PIL import Image as _Image, ImageDraw

    im = _Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((20, 20, 100, 100), fill=(30, 90, 200, 255))
    out = cardscan._polish_product_cutout(im)
    a = np.array(out)[:, :, 3]
    soft = (a > 8) & (a < 248)
    assert soft.any()
    assert len(np.unique(a[soft])) >= 8


def test_polish_glaettet_dosen_treppen():
    """Senkrechte Treppen an einer Dose: Flanke wird gerade und weich."""
    import numpy as np
    from PIL import Image as _Image

    H, W = 400, 120
    im = _Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pix = im.load()
    for y in range(20, 380):
        jag = 2 if (y // 8) % 2 else 0
        for x in range(30 + jag, 90 + jag):
            pix[x, y] = (200, 180, 80, 255)
        if y > 360:
            for x in range(25, 95):  # dunkler Fuß-Schatten außen
                if x < 30 or x > 90:
                    pix[x, y] = (40, 30, 20, 220)
    out = cardscan._polish_product_cutout(im)
    a = np.array(out)[:, :, 3].astype(float)
    # Subpixel-linke Kante in der Mitte: geringe Schrittweite
    prev = None
    steps = []
    for y in range(80, 320):
        row = a[y]
        for x in range(1, W):
            if row[x - 1] < 128 <= row[x]:
                t = (128 - row[x - 1]) / max(row[x] - row[x - 1], 1e-6)
                pos = (x - 1) + t
                if prev is not None:
                    steps.append(abs(pos - prev))
                prev = pos
                break
    assert steps and (sum(steps) / len(steps)) < 0.35, steps[:10]
    # Weiche Kante vorhanden
    soft = (a > 15) & (a < 240)
    assert soft[80:320].any()


def test_produkt_cutout_fuellt_kein_rechteck(tmp_path, monkeypatch):
    """Alltagsstück: Silhouette bleibt — MinAreaRect darf nicht opak werden.

    Pegador-Cap 09.08.: rembg hatte die Kappe, der Rechteck-Nachschritt
    holte Tisch und Monitor zurück."""
    import numpy as np
    from PIL import Image as _Image

    src = tmp_path / "cap.jpg"
    _Image.new("RGB", (400, 400), (40, 40, 40)).save(src)
    out = tmp_path / "cap_cut.png"

    # Fake rembg: undurchsichtiger Kreis in der Mitte, Rest alpha=0
    def fake_remove(img, session=None, post_process_mask=True):
        w, h = img.size
        rgba = _Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pix = rgba.load()
        cx, cy, r = w // 2, h // 2, min(w, h) // 4
        for y in range(h):
            for x in range(w):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    pix[x, y] = (200, 50, 50, 255)
        return rgba

    import rembg
    monkeypatch.setattr(rembg, "remove", fake_remove)
    monkeypatch.setattr(rembg, "new_session", lambda *a, **k: object())
    cardscan._rembg_session = None

    assert cardscan._cutout(str(src), str(out), kind=None) is True
    a = np.array(_Image.open(out))[:, :, 3]
    ys, xs = np.where(a > 40)
    assert ys.size > 0
    fill = (a[ys.min():ys.max() + 1, xs.min():xs.max() + 1] > 40).mean()
    # Kreis im Bounding-Box ≈ π/4 ≈ 0.78; Rechteck-Füllung wäre ≈ 1.0
    assert fill < 0.90, f"Rechteck wurde aufgefüllt (fill={fill:.3f})"
    assert a[0, 0] < 8 and a[-1, -1] < 8


@pytest.mark.asyncio
async def test_cutout_bekommt_kind_none_bei_nicht_karte(tmp_path, monkeypatch):
    """crop_photos reicht kind an _cutout durch (Produkt vs. Karte)."""
    foto = tmp_path / "x.jpg"
    Image.new("RGB", (200, 300), (80, 80, 80)).save(foto)
    gesehen = {"kind": "MISSING"}

    async def fake_detect(client, p):
        return None

    def fake_cutout(p, out, kind=None):
        gesehen["kind"] = kind
        Image.new("RGBA", (180, 260), (90, 95, 100, 255)).save(out)
        return True

    monkeypatch.setattr(cardscan, "detect_card", fake_detect)
    monkeypatch.setattr(cardscan, "_cutout", fake_cutout)
    monkeypatch.setattr(cardscan, "bild_ok", lambda p, k=None: True)
    await cardscan.crop_photos("key", [str(foto)])
    assert gesehen["kind"] is None


def test_should_warp_karte_und_slab_nicht_alltag():
    from web.cutout_v2.routing import should_warp, item_is_non_card
    assert item_is_non_card({"canonical_identity": {"kind": "manga_comic"}}) is True
    assert item_is_non_card({"canonical_identity": {"kind": "video_game"}}) is True
    assert item_is_non_card({"graded": {"grader": "PSA"}}) is False
    assert item_is_non_card({"scan_kind": "product"}) is True
    assert should_warp("slab", {"canonical_identity": {"kind": "generic"}}) is False
    assert should_warp("raw", {}) is True
    assert should_warp("sleeve", {}) is False
    assert should_warp("slab", {"graded": {"grader": "CGC"}}) is True
    # Schlanke Silhouette (Flasche) — kein Case
    tall = [[40, 2], [60, 2], [62, 98], [38, 98]]
    assert should_warp("slab", {}, tall) is False
    assert should_warp("raw", {}, tall) is False
    # Normales Case / Karten-Rechteck
    slab = [[8, 4], [92, 5], [90, 96], [10, 95]]
    assert should_warp("slab", {}, slab) is True
    card = [[12, 10], [88, 11], [87, 90], [13, 89]]
    assert should_warp("raw", {}, card) is True


@pytest.mark.asyncio
async def test_generic_item_skip_warp(tmp_path, monkeypatch):
    """Alltagsstück: kein detect_card, kein Warp — nur rembg."""
    foto = tmp_path / "flasche.jpg"
    Image.new("RGB", (400, 900), (80, 40, 20)).save(foto)
    aufrufe = {"warp": 0, "detect": 0, "cutout": 0}

    async def fake_detect(client, p):
        aufrufe["detect"] += 1
        return {"kind": "slab", "corners": [[5, 3], [95, 3], [95, 97], [5, 97]],
                "confidence": "high"}

    async def fake_recut(*a, **k):
        aufrufe["warp"] += 1
        return True

    def fake_cutout(p, out, kind=None):
        aufrufe["cutout"] += 1
        Image.new("RGBA", (180, 400), (90, 50, 20, 255)).save(out)
        return True

    monkeypatch.setattr(cardscan, "detect_card", fake_detect)
    monkeypatch.setattr(cardscan, "slab_recut", fake_recut)
    monkeypatch.setattr(cardscan, "_cutout", fake_cutout)
    monkeypatch.setattr(cardscan, "bild_ok", lambda p, k=None: True)

    await cardscan.crop_photos(
        "key", [str(foto)], item={"canonical_identity": {"kind": "generic"}})
    assert aufrufe["warp"] == 0
    assert aufrufe["detect"] == 0
    assert aufrufe["cutout"] == 1


@pytest.mark.asyncio
async def test_vision_flasche_als_slab_kein_warp(tmp_path, monkeypatch):
    """Vision sagt slab, aber die Silhouette ist zu schlank für ein Case."""
    foto = tmp_path / "flasche.jpg"
    Image.new("RGB", (400, 900), (80, 40, 20)).save(foto)
    aufrufe = {"warp": 0, "cutout": 0}

    async def fake_detect(client, p):
        return {"kind": "slab", "corners": [[40, 2], [60, 2], [62, 98], [38, 98]],
                "confidence": "high"}

    async def fake_recut(*a, **k):
        aufrufe["warp"] += 1
        return True

    def fake_cutout(p, out, kind=None):
        aufrufe["cutout"] += 1
        Image.new("RGBA", (180, 400), (90, 50, 20, 255)).save(out)
        return True

    monkeypatch.setattr(cardscan, "detect_card", fake_detect)
    monkeypatch.setattr(cardscan, "slab_recut", fake_recut)
    monkeypatch.setattr(cardscan, "_cutout", fake_cutout)
    monkeypatch.setattr(cardscan, "bild_ok", lambda p, k=None: True)

    await cardscan.crop_photos("key", [str(foto)])
    assert aufrufe["warp"] == 0
    assert aufrufe["cutout"] == 1


def test_cutout_usable_schlaegt_slab_qa_mit_alltag(tmp_path):
    from web.cardscan import cutout_usable
    # Ratio 1.375 — kein Slab-Label, aber Alltags-Prüfung ok (Struktur, nicht einfarbig)
    im = Image.new("RGBA", (800, 1100), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([80, 50, 720, 200], fill=(30, 35, 50, 255))
    d.rectangle([120, 280, 680, 720], fill=(90, 140, 90, 255))
    d.rectangle([120, 780, 680, 1020], fill=(60, 60, 70, 255))
    p = tmp_path / "x_cut.png"
    im.save(p)
    assert cardscan.bild_ok(str(p), "slab") is False
    assert cardscan.bild_ok(str(p), "other") is True
    assert cutout_usable(str(p), "slab") is True


def test_product_kleines_isnet_nimmt_u2netp(tmp_path, monkeypatch):
    """isnet hält nur ein Cover-Detail → u2netp liefert die Fläche."""
    src = tmp_path / "buch.jpg"
    Image.new("RGB", (400, 520), (240, 240, 238)).save(src)
    out = tmp_path / "buch_cut.png"
    gesehen = []

    class _Sess:
        def __init__(self, name):
            self.name = name

    def fake_new(name):
        return _Sess(name)

    def fake_remove(img, session=None, post_process_mask=True):
        w, h = img.size
        rgba = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pix = rgba.load()
        name = getattr(session, "name", "")
        gesehen.append(name)
        if name == "u2netp":
            for y in range(h // 8, 7 * h // 8):
                for x in range(w // 8, 7 * w // 8):
                    pix[x, y] = (230, 230, 225, 255)
        else:
            cy, cx = h // 2, w // 2
            for y in range(cy - 12, cy + 12):
                for x in range(cx - 12, cx + 12):
                    pix[x, y] = (20, 20, 20, 255)
        return rgba

    import rembg
    monkeypatch.setattr(rembg, "remove", fake_remove)
    monkeypatch.setattr(rembg, "new_session", fake_new)
    cardscan._rembg_session = None
    cardscan._rembg_session_product = None
    assert cardscan._cutout(str(src), str(out), kind="other") is True
    assert "u2netp" in gesehen
    im = Image.open(out)
    assert im.size[0] >= 200 and im.size[1] >= 250


def test_cutout_quelle_hat_u2netp_fallback():
    src = inspect.getsource(cardscan._cutout)
    assert "u2netp" in src
    assert "isnet nur" in src


def test_scan_kind_routing():
    from web.cutout_v2.routing import (
        resolve_scan_kind, kind_from_rectangle, normalize_glance,
        scan_kind_to_legacy, apply_scan_kind,
    )
    assert kind_from_rectangle(1.39, 0.9) == "card"
    assert kind_from_rectangle(1.70, 0.9) == "slab"
    assert kind_from_rectangle(2.80, 0.9) is None
    assert kind_from_rectangle(1.39, 0.50) is None
    assert normalize_glance({"kind": "other", "confidence": "high"})["kind"] == "product"
    assert normalize_glance({"kind": "raw", "grader": "psa"})["kind"] == "card"
    assert resolve_scan_kind(
        glance={"kind": "product", "confidence": "high"})[0] == "product"
    assert resolve_scan_kind(
        glance={"kind": "card", "confidence": "low"},
        geometry_hint="card")[0] == "card"
    assert resolve_scan_kind(
        glance={"kind": "product", "confidence": "low"})[0] == "product"
    assert resolve_scan_kind(item={"graded": {"grader": "CGC"}})[0] == "slab"
    assert scan_kind_to_legacy("product") == "other"
    assert scan_kind_to_legacy("card") == "raw"
    item, legacy = apply_scan_kind({}, glance={"kind": "slab", "grader": "PSA",
                                               "confidence": "high"})
    assert item["scan_kind"] == "slab" and legacy == "slab"
    assert item.get("scan_grader") == "PSA"


@pytest.mark.asyncio
async def test_product_scan_kind_skip_warp(tmp_path, monkeypatch):
    """Glance product: kein Warp, nur rembg."""
    foto = tmp_path / "remote.jpg"
    Image.new("RGB", (400, 900), (40, 40, 50)).save(foto)
    aufrufe = {"warp": 0, "detect": 0, "cutout": 0}

    async def fake_detect(client, p):
        aufrufe["detect"] += 1
        return {"kind": "slab", "corners": [[5, 3], [95, 3], [95, 97], [5, 97]],
                "confidence": "high"}

    async def fake_recut(*a, **k):
        aufrufe["warp"] += 1
        return True

    def fake_cutout(p, out, kind=None):
        aufrufe["cutout"] += 1
        Image.new("RGBA", (180, 400), (40, 40, 50, 255)).save(out)
        return True

    monkeypatch.setattr(cardscan, "detect_card", fake_detect)
    monkeypatch.setattr(cardscan, "slab_recut", fake_recut)
    monkeypatch.setattr(cardscan, "_cutout", fake_cutout)
    monkeypatch.setattr(cardscan, "bild_ok", lambda p, k=None: True)

    await cardscan.crop_photos(
        "key", [str(foto)], item={"scan_kind": "product", "cutout_kind": "other"})
    assert aufrufe["warp"] == 0
    assert aufrufe["detect"] == 0
    assert aufrufe["cutout"] == 1


@pytest.mark.asyncio
async def test_raw_card_nimmt_rechteck_warp(tmp_path, monkeypatch):
    """Rohkarte: alte Rechteck-Technik — Warp, dann rembg."""
    foto = tmp_path / "card.jpg"
    Image.new("RGB", (900, 1300), (200, 180, 160)).save(foto)
    aufrufe = {"warp": 0, "cutout": 0, "cut_kind": None}

    async def fake_detect(client, p):
        return {"kind": "raw", "corners": [[10, 8], [90, 9], [89, 92], [11, 91]],
                "confidence": "high"}

    async def fake_recut(*a, **k):
        aufrufe["warp"] += 1
        Image.new("RGB", (700, 980), (200, 180, 160)).save(k.get("out") or a[2])
        return True

    def fake_cutout(p, out, kind=None):
        aufrufe["cutout"] += 1
        aufrufe["cut_kind"] = kind
        Image.new("RGBA", (680, 960), (200, 180, 160, 255)).save(out)
        return True

    monkeypatch.setattr(cardscan, "detect_card", fake_detect)
    monkeypatch.setattr(cardscan, "slab_recut", fake_recut)
    monkeypatch.setattr(cardscan, "_cutout", fake_cutout)
    monkeypatch.setattr(cardscan, "bild_ok", lambda p, k=None: True)
    monkeypatch.setattr(cardscan, "cutout_usable", lambda p, k=None: True)

    res, info = await cardscan.crop_photos("key", [str(foto)])
    assert aufrufe["warp"] == 1
    assert aufrufe["cutout"] == 1
    assert aufrufe["cut_kind"] == "raw"
    assert res[0].endswith("_cut.png")
