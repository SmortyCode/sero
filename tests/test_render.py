from PIL import Image

from bot.render import (BOX_HEIGHT, BOX_WIDTH, clean_cutout, compute_placement,
                        detect_card_by_edges, segment_card_on_uniform_bg, straighten_card)


def test_detect_card_by_edges_finds_full_rectangle():
    """Karten-förmiges Rechteck auf Grund wird über die Außenkante als Karte erkannt."""
    import numpy as np

    arr = np.full((700, 520, 3), 30, dtype="uint8")        # dunkler Hintergrund
    arr[70:630, 90:430] = [225, 225, 225]                  # helle Karte (AR ~0.61)
    mask = detect_card_by_edges(Image.fromarray(arr, "RGB"))
    assert mask is not None
    assert bool(mask[350, 260]) is True                    # Karte innen erkannt
    assert bool(mask[10, 10]) is False                     # Rand nicht


def test_detect_card_by_edges_ignores_round_object():
    import numpy as np

    arr = np.full((500, 500, 3), 240, dtype="uint8")
    yy, xx = np.ogrid[:500, :500]
    arr[(xx - 250) ** 2 + (yy - 250) ** 2 <= 160 ** 2] = [40, 90, 170]
    assert detect_card_by_edges(Image.fromarray(arr, "RGB")) is None


def test_segment_slab_on_uniform_bg_keeps_full_rectangle():
    """Karten-förmiges Objekt auf einfarbigem Grund wird ohne rembg segmentiert."""
    import numpy as np

    arr = np.full((600, 440, 3), 60, dtype="uint8")        # dunkler einfarbiger Grund
    arr[60:540, 70:370] = [200, 60, 50]                    # karten-förmiges Rechteck (AR 0.625)
    out = segment_card_on_uniform_bg(Image.fromarray(arr, "RGB"))
    assert out is not None and out.mode == "RGBA"
    alpha = np.asarray(out.split()[-1])
    assert alpha[300, 220] == 255                          # Karte innen deckend
    assert alpha[10, 10] == 0                              # Rand transparent


def test_segment_ignores_non_rectangular_object():
    """Runde Form ist keine Karte -> None (rembg übernimmt)."""
    import numpy as np

    arr = np.full((500, 500, 3), 240, dtype="uint8")
    yy, xx = np.ogrid[:500, :500]
    arr[(xx - 250) ** 2 + (yy - 250) ** 2 <= 150 ** 2] = [30, 80, 160]
    assert segment_card_on_uniform_bg(Image.fromarray(arr, "RGB")) is None


def test_straighten_card_deskews_rotated_rectangle():
    """Ein gedrehtes karten-förmiges Rechteck wird als Karte erkannt und gerade gezogen."""
    import numpy as np

    # Karten-förmiges Rechteck (AR ~0.7), um 18° gedreht, auf transparentem Grund
    canvas = Image.new("RGBA", (500, 500), (0, 0, 0, 0))
    card = Image.new("RGBA", (200, 285), (180, 60, 40, 255))
    canvas.paste(card, (150, 110), card)
    rotated = canvas.rotate(18, resample=Image.BICUBIC, expand=False)

    rgb = Image.new("RGB", (500, 500), (255, 255, 255))
    rgb.paste(rotated.convert("RGB"), (0, 0), rotated)

    out = straighten_card(rgb, rotated)
    assert out is not None, "Karte sollte erkannt werden"
    w, h = out.size
    assert h > w, "gerade gezogene Karte ist hochkant"
    assert abs((w / h) - (200 / 285)) < 0.12, "Seitenverhältnis ~ Karte"


def test_straighten_card_ignores_non_card():
    """Eine runde/quadratische Form ist keine Karte -> None (normaler Freisteller)."""
    import numpy as np

    canvas = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    yy, xx = np.ogrid[:400, :400]
    circle = (xx - 200) ** 2 + (yy - 200) ** 2 <= 150 ** 2
    arr = np.zeros((400, 400, 4), dtype="uint8")
    arr[circle] = [50, 120, 200, 255]
    cutout = Image.fromarray(arr, "RGBA")
    assert straighten_card(cutout.convert("RGB"), cutout) is None


def test_placement_fits_box_and_centers():
    bg = (1600, 1600)
    box_w, box_h = bg[0] * BOX_WIDTH, bg[1] * BOX_HEIGHT
    for product in [(4000, 3000), (500, 2000), (1000, 1000), (123, 4567)]:
        w, h, x, y = compute_placement(product, bg)
        assert w <= box_w + 1 and h <= box_h + 1
        # Seitenverhältnis bleibt erhalten
        assert abs(w / h - product[0] / product[1]) < 0.02
        # horizontal zentriert
        assert abs((x + w / 2) - bg[0] * 0.50) <= 1


def test_placement_uniform_size():
    # Zwei Produkte mit gleichem Seitenverhältnis aber anderer Auflösung
    # landen in identischer Grösse -> einheitlicher Look
    bg = (1600, 1600)
    a = compute_placement((3000, 2000), bg)
    b = compute_placement((600, 400), bg)
    assert (a[0], a[1]) == (b[0], b[1])


def test_render_product_end_to_end(tmp_path, monkeypatch):
    import bot.render as render

    # Hintergrund + "Produkt" (rotes Quadrat auf weiss) synthetisch erzeugen
    bg_path = tmp_path / "background.png"
    Image.new("RGB", (800, 800), (255, 255, 255)).save(bg_path)
    monkeypatch.setattr(render, "BACKGROUND_PATH", bg_path)

    product_path = tmp_path / "produkt.jpg"
    img = Image.new("RGB", (600, 600), (255, 255, 255))
    for px in range(150, 450):
        for py in range(150, 450):
            img.putpixel((px, py), (200, 30, 30))
    img.save(product_path)

    out = tmp_path / "out.jpg"
    result = render.render_product(product_path, out)
    rendered = Image.open(result)
    assert rendered.size == (800, 800)
    # Im Box-Zentrum muss das (rote) Produkt liegen
    cx, cy = int(800 * 0.50), int(800 * 0.40)
    r, g, b = rendered.getpixel((cx, cy))
    assert r > 120 and g < 110 and b < 110


def test_render_centers_product_centroid(tmp_path, monkeypatch):
    """Produkt sitzt außermittig im Foto -> im Render trotzdem exakt mittig."""
    import bot.render as render

    bg_path = tmp_path / "background.png"
    Image.new("RGB", (800, 800), (255, 255, 255)).save(bg_path)
    monkeypatch.setattr(render, "BACKGROUND_PATH", bg_path)

    # Rotes Quadrat weit links im Foto
    product_path = tmp_path / "links.jpg"
    img = Image.new("RGB", (800, 600), (255, 255, 255))
    for px in range(40, 280):
        for py in range(180, 420):
            img.putpixel((px, py), (190, 25, 25))
    img.save(product_path)

    out = tmp_path / "out.jpg"
    rendered = Image.open(render.render_product(product_path, out))

    # Horizontale Masse-Schwerpunkt der roten Pixel muss bei ~Bildmitte liegen
    xs = [x for x in range(800) for y in range(0, 800, 4)
          if rendered.getpixel((x, y))[0] > 150 and rendered.getpixel((x, y))[1] < 100]
    assert xs, "kein Produkt im Render gefunden"
    center = sum(xs) / len(xs)
    assert abs(center - 400) < 12, f"Produktmitte bei {center}, erwartet ~400"


def test_render_color_background(tmp_path):
    """Farbmodus: kein Template nötig, Canvas 1600er, Ecken in Wunschfarbe, Produkt maximal."""
    import bot.render as render

    product_path = tmp_path / "produkt.jpg"
    img = Image.new("RGB", (400, 400), (255, 255, 255))
    for px in range(100, 300):
        for py in range(100, 300):
            img.putpixel((px, py), (20, 120, 40))
    img.save(product_path)

    out = tmp_path / "out.jpg"
    rendered = Image.open(render.render_product(product_path, out, bg_color="#75aae7"))
    assert rendered.size == render.CANVAS_SIZE
    r, g, b = rendered.getpixel((10, 10))
    assert abs(r - 0x75) < 12 and abs(g - 0xAA) < 12 and abs(b - 0xE7) < 12
    # Produkt füllt die Maximal-Box (~92%) statt der Logo-Box (~70% Höhe)
    center = rendered.getpixel((800, 800))
    assert center[1] > 80 and center[0] < 100, "Produkt nicht mittig/maximal platziert"


def test_normalize_hex_color():
    from bot.render import normalize_hex_color
    assert normalize_hex_color("#75AAE7") == "#75aae7"
    assert normalize_hex_color("75aae7") == "#75aae7"
    assert normalize_hex_color("#fff") is None
    assert normalize_hex_color("blau") is None
