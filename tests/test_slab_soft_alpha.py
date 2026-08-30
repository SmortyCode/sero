"""Slab/Sleeve: kein opakes MinAreaRect (CutoutPipelineV2)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image as _Image

from web import cardscan


def test_detect_prompt_haelt_halter_im_bild():
    """Sleeve-Prompt: Außenkanten des Halters — nicht die gedruckte Karte allein."""
    p = cardscan.DETECT_PROMPT
    assert "AUSSENKANTEN der Schutzhülle" in p
    assert "GEDRUCKTEN KARTE SELBST" not in p
    assert "IMMER \"sleeve\"" in p
    assert "Halter bleibt im Bild" in p


def test_listing_suggests_sleeve_aus_zustandsbeschreibung():
    assert cardscan.listing_suggests_sleeve({
        "condition_description":
            "Karte selbst einwandfrei. Schutzhülle zeigt leichte Kratzer.",
    })
    assert cardscan.listing_suggests_sleeve({
        "condition_description": "In Toploader, Near Mint.",
    })
    assert not cardscan.listing_suggests_sleeve({
        "condition_description": "Lose Karte, nicht gegradet.",
    })


def test_slab_cutout_fuellt_kein_rechteck(tmp_path, monkeypatch):
    src = tmp_path / "slab.jpg"
    _Image.new("RGB", (400, 700), (30, 30, 30)).save(src)
    out = tmp_path / "slab_cut.png"

    def fake_remove(img, session=None, post_process_mask=True):
        assert post_process_mask is False  # Slab: weiches Alpha
        w, h = img.size
        rgba = _Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pix = rgba.load()
        # Abgerundetes Case + Label (nicht volle BBox)
        for y in range(h):
            for x in range(w):
                cx, cy = w // 2, int(h * 0.55)
                rx, ry = w // 3, int(h * 0.38)
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    pix[x, y] = (80, 90, 100, 230)
                # Label oben
                if 40 <= y <= 110 and 80 <= x <= w - 80:
                    pix[x, y] = (200, 200, 210, 255)
        return rgba

    class Sess:
        pass

    monkeypatch.setattr(cardscan, "_rembg_session", Sess())
    monkeypatch.setattr("rembg.remove", fake_remove)
    monkeypatch.setattr("rembg.new_session", lambda *a, **k: Sess())

    assert cardscan._cutout(str(src), str(out), kind="slab") is True
    a = np.array(_Image.open(out))[:, :, 3]
    ys, xs = np.where(a > 40)
    assert ys.size > 0
    fill = (a[ys.min():ys.max() + 1, xs.min():xs.max() + 1] > 40).mean()
    assert fill < 0.97, f"Slab wurde als Vollrechteck gefüllt (fill={fill:.3f})"
    # transparenter Rand nach layout_aus_alpha
    assert a[0, 0] < 8 and a[-1, -1] < 8


def test_sleeve_kein_post_process(tmp_path, monkeypatch):
    src = tmp_path / "sl.jpg"
    _Image.new("RGB", (300, 420), (20, 20, 20)).save(src)
    out = tmp_path / "sl_cut.png"
    seen = {}

    def fake_remove(img, session=None, post_process_mask=True):
        seen["ppm"] = post_process_mask
        w, h = img.size
        rgba = _Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pix = rgba.load()
        for y in range(40, h - 40):
            for x in range(50, w - 50):
                pix[x, y] = (90, 40, 40, 200)
        return rgba

    class Sess:
        pass

    monkeypatch.setattr(cardscan, "_rembg_session_product", Sess())
    monkeypatch.setattr("rembg.remove", fake_remove)
    assert cardscan._cutout(str(src), str(out), kind="sleeve") is True
    assert seen.get("ppm") is False


def test_raw_noch_rechteck_erlaubt(tmp_path, monkeypatch):
    src = tmp_path / "raw.jpg"
    _Image.new("RGB", (300, 420), (20, 20, 20)).save(src)
    out = tmp_path / "raw_cut.png"
    seen = {}

    def fake_remove(img, session=None, post_process_mask=True):
        seen["ppm"] = post_process_mask
        w, h = img.size
        rgba = _Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pix = rgba.load()
        for y in range(30, h - 30):
            for x in range(40, w - 40):
                pix[x, y] = (90, 40, 40, 255)
        return rgba

    class Sess:
        pass

    monkeypatch.setattr(cardscan, "_rembg_session_product", Sess())
    monkeypatch.setattr("rembg.remove", fake_remove)
    assert cardscan._cutout(str(src), str(out), kind="raw") is True
    assert seen.get("ppm") is True


@pytest.mark.asyncio
async def test_sleeve_confirmed_nie_raw_rechteck(tmp_path, monkeypatch):
    """Erkannter/bestätigter Halter darf nicht den raw-minAreaRect-Pfad nehmen."""
    foto = tmp_path / "holder.jpg"
    _Image.new("RGB", (900, 1300), (200, 200, 200)).save(foto)
    seen = {"kinds": []}

    async def fake_detect(client, p):
        # Vision sagt fälschlich raw — confirmed_kind muss gewinnen.
        return {"kind": "raw", "corners": [[8, 6], [92, 6], [92, 94], [8, 94]],
                "confidence": "high"}

    def fake_cutout(p, out, kind=None):
        seen["kinds"].append(kind)
        _Image.new("RGBA", (700, 980), (90, 40, 40, 220)).save(out)
        return True

    monkeypatch.setattr(cardscan, "detect_card", fake_detect)
    monkeypatch.setattr(cardscan, "_cutout", fake_cutout)
    monkeypatch.setattr(cardscan, "bild_ok", lambda p, k=None: True)

    res, info = await cardscan.crop_photos(
        "key", [str(foto)], confirmed_kind="sleeve",
        item={"cutout_kind": "sleeve"})
    assert info.get("kind") == "sleeve"
    assert seen["kinds"] == ["sleeve"]
    assert res[0].endswith("_cut.png")
    assert not Path(str(foto).replace(".jpg", "_sleeve_tmp.jpg")).exists()
