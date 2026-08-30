"""Draft aus Sammlung: fertige Cutouts nicht erneut freistellen."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from bot.render import photo_is_existing_cutout


def test_photo_is_existing_cutout_erkennt_cut_suffix(tmp_path: Path):
    p = tmp_path / "00_cut.png"
    Image.new("RGB", (40, 40), (255, 0, 0)).save(p)
    assert photo_is_existing_cutout(p) is True


def test_photo_is_existing_cutout_erkennt_alpha_png(tmp_path: Path):
    p = tmp_path / "scan.png"
    im = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    im.paste(Image.new("RGBA", (50, 50), (10, 10, 10, 255)), (15, 15))
    im.save(p)
    assert photo_is_existing_cutout(p) is True


def test_photo_is_existing_cutout_lehnt_opakes_jpg_ab(tmp_path: Path):
    p = tmp_path / "photo.jpg"
    Image.new("RGB", (40, 40), (200, 200, 200)).save(p)
    assert photo_is_existing_cutout(p) is False


def test_composite_legt_cutout_auf_farbe_ohne_rembg(tmp_path: Path):
    from bot.render import CANVAS_SIZE, composite_cutout_on_background
    p = tmp_path / "00_cut.png"
    im = Image.new("RGBA", (200, 280), (0, 0, 0, 0))
    im.paste(Image.new("RGBA", (160, 240), (200, 30, 30, 255)), (20, 20))
    im.save(p)
    out = tmp_path / "design.jpg"
    result = composite_cutout_on_background(p, out, bg_color="#F5F9FF")
    rendered = Image.open(result)
    assert rendered.size == CANVAS_SIZE
    r, g, b = rendered.getpixel((10, 10))
    assert r > 230 and b > 230
    cx, cy = CANVAS_SIZE[0] // 2, CANVAS_SIZE[1] // 2
    pr, pg, pb = rendered.getpixel((cx, cy))
    assert pr > 150 and pg < 80


def test_list_collection_item_ueberspringt_render_bei_cutout():
    text = (Path(__file__).resolve().parent.parent / "web" / "app_api.py").read_text(
        encoding="utf-8")
    assert "place_on_listing_bg" in text
    assert "Nie neu freistellen" in text
    start = text.index("Nie neu freistellen")
    block = text[start:start + 800]
    assert "render_product" not in block


def test_place_on_listing_bg_legt_opakes_jpg_ohne_rembg(tmp_path: Path):
    from bot.render import CANVAS_SIZE, place_on_listing_bg
    p = tmp_path / "wata.jpg"
    Image.new("RGB", (200, 280), (30, 80, 200)).save(p, quality=92)
    out = tmp_path / "design.jpg"
    result = place_on_listing_bg(p, out, bg_color="#F5F9FF")
    rendered = Image.open(result)
    assert rendered.size == CANVAS_SIZE
    r, g, b = rendered.getpixel((10, 10))
    assert r > 230 and b > 230
    cx, cy = CANVAS_SIZE[0] // 2, CANVAS_SIZE[1] // 2
    pr, pg, pb = rendered.getpixel((cx, cy))
    assert pb > 150 and pr < 80


def test_offermin_action_im_app_api():
    text = (Path(__file__).resolve().parent.parent / "web" / "app_api.py").read_text(
        encoding="utf-8")
    assert 'elif action == "offermin":' in text
