"""Das Domänen-Gate (Stufe 2, 03.08.2026) — der strukturelle Fix der 603 €.

Svens Manga Band 103 bekam den Preis der SAMMELKARTE „Nami [Manga] OP01-016",
weil die Fuzzy-Suche von PriceCharting den erstbesten Treffer nahm. Das Gate
vergleicht die Warenart des Stücks (comic/game/tcg) mit der des Treffers
(console-name) und verwirft Fremdes, BEVOR ein Preis entsteht — der
nachgelagerte Wächter fängt dann nur noch Restfälle.
"""

import time

import pytest

from web.pricecharting import domain_of_item, domain_of_pc, lookup_pc


# ────────────────────── Zuordnung PC-Seite ──────────────────────

@pytest.mark.parametrize("console,erwartet", [
    ("Comic Books One Piece", "comic"),
    ("Comics", "comic"),
    ("One Piece Romance Dawn", "tcg"),
    ("Pokemon Base Set", "tcg"),
    ("Baseball Cards 1989 Upper Deck", "tcg"),
    ("Playstation 2", "game"),
    ("JP Playstation 2", "game"),
    ("Nintendo 64", "game"),
    ("Super Nintendo", "game"),
    ("Sega Genesis", "game"),
    ("Amiibo", "other"),
    (None, "other"),
    ("", "other"),
])
def test_domain_of_pc(console, erwartet):
    assert domain_of_pc(console) == erwartet


# ────────────────────── Zuordnung Stück-Seite ──────────────────────

def test_domain_of_item_manga_trotz_tcg_kategorie():
    """Der Kernfall: Svens Manga hat die App-Kategorie „One Piece" (Marke!),
    ist aber ein BUCH. Die Kategorie darf die Domäne nicht stellen."""
    item = {"name": "One Piece #103 Manga Japanisch Beckett BGS 9.4",
            "category": "One Piece",
            "graded": {"grader": "BGS", "grade": "9.4"}}
    assert domain_of_item(item) == "comic"


def test_domain_of_item_wata_ist_immer_spiel():
    item = {"name": "Grand Theft Auto Vice City PS2 USA",
            "graded": {"grader": "WATA", "grade": "9.8"}}
    assert domain_of_item(item) == "game"


def test_domain_of_item_karte():
    item = {"name": "Pokémon Glurak ex 199/165 151 CGC 10",
            "graded": {"grader": "CGC", "grade": "10"}}
    assert domain_of_item(item) == "tcg"


def test_domain_of_item_unklar_bleibt_offen():
    """Kein Urteil heißt None — und None heißt: das Gate lässt alles durch.
    Ein falsch geschlossenes Gate würde v0-Stücken den Preis nehmen."""
    assert domain_of_item({"name": "Azuki Figur limitiert"}) is None
    assert domain_of_item({}) is None


# ────────────────────── Das Gate in lookup_pc ──────────────────────

class FakeStore:
    def __init__(self):
        self._kv = {}

    def kv_get(self, key):
        return self._kv.get(key)

    def kv_set(self, key, value):
        self._kv[key] = value


KARTE = {"id": "111", "product-name": "Nami [Manga] OP01-016",
         "console-name": "One Piece Romance Dawn"}
BUCH = {"id": "222", "product-name": "One Piece #103",
        "console-name": "Comic Books One Piece"}


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("PRICECHARTING_TOKEN", "test-token")
    return FakeStore()


def _kandidaten_cache(store, query, produkte):
    """Stufe A vorbefüllen — die Tests brauchen kein Netz."""
    import hashlib
    qkey = "pcq_" + hashlib.sha1(query.lower().encode()).hexdigest()[:16]
    store.kv_set(qkey, {"ts": time.time(), "v": produkte})


def _produkt_cache(store, prod, preise):
    store.kv_set(f"pcp_{prod['id']}", {"ts": time.time(), "v": {**prod, **preise}})


@pytest.mark.asyncio
async def test_gate_verwirft_fremde_domaene_und_nimmt_die_richtige(store):
    """DIE Prüfvorgabe aus dem Umsetzungsplan: comic_manga gegen „One Piece
    Romance Dawn" → verworfen; gegen „Comic Books One Piece" → akzeptiert.
    Die Karte steht VORNE in der Trefferliste — genau wie am 02.08."""
    q = "One Piece 103 Manga Japanese Beckett 9.4"
    _kandidaten_cache(store, q, [KARTE, BUCH])
    _produkt_cache(store, BUCH, {"graded-price": 9000, "box-only-price": 12000,
                                 "manual-only-price": 20000})
    res = await lookup_pc(store, q, {"grader": "BGS", "grade": "9.0"}, 1.0,
                          domain="comic")
    assert res is not None, "Das Buch wurde mitverworfen"
    assert res["detail"]["pc_product"] == "One Piece #103"
    assert res["detail"]["pc_console"] == "Comic Books One Piece"
    assert res["value"] == 90.0


@pytest.mark.asyncio
async def test_gate_ohne_domaene_altverhalten(store):
    """domain=None: erster Treffer gewinnt wie bisher — v0-Stücke ohne
    Typ-Wissen verlieren keinen Preis."""
    q = "One Piece 103"
    _kandidaten_cache(store, q, [KARTE, BUCH])
    _produkt_cache(store, KARTE, {"loose-price": 500})
    res = await lookup_pc(store, q, None, 1.0, domain=None)
    assert res is not None and res["detail"]["pc_id"] == "111"


@pytest.mark.asyncio
async def test_gate_alles_fremd_liefert_nichts(store):
    """Nur fremde Treffer → lieber KEIN Preis als der falsche. Genau das
    verhindert die 603 €: kein Wert schlägt einen erfundenen."""
    q = "One Piece 103 Manga"
    _kandidaten_cache(store, q, [KARTE])
    res = await lookup_pc(store, q, None, 1.0, domain="comic")
    assert res is None


@pytest.mark.asyncio
async def test_pc_other_bleibt_durchlaessig(store):
    """„other" auf PC-Seite ist kein Urteil — durchlassen, sonst verlieren
    Exoten (Amiibo & Co.) grundlos ihren Preis."""
    exot = {"id": "333", "product-name": "Azuki Booster Box",
            "console-name": "Amiibo"}
    q = "Azuki Booster Box"
    _kandidaten_cache(store, q, [exot])
    _produkt_cache(store, exot, {"loose-price": 4000})
    res = await lookup_pc(store, q, None, 1.0, domain="tcg")
    assert res is not None and res["value"] == 40.0


@pytest.mark.asyncio
async def test_produkt_cache_verhindert_zweiten_call(store, monkeypatch):
    """Stufe B cached je Produkt-ID: zwei Anfragen, die auf denselben
    Gewinner zeigen, kosten nur einen Preis-Abruf (1-Call/s-Kontolimit)."""
    import web.pricecharting as pc

    aufrufe = {"n": 0}

    class FakeResp:
        status_code = 200

        def __init__(self, data):
            self._d = data

        def raise_for_status(self):
            pass

        def json(self):
            return self._d

    async def fake_get(url, params=None):
        aufrufe["n"] += 1
        if url.endswith("/products"):
            return FakeResp({"products": [BUCH]})
        return FakeResp({**BUCH, "loose-price": 1500})

    monkeypatch.setattr(pc._http, "get", fake_get)
    q1 = "One Piece 103 Manga Japanese"
    q2 = "One Piece Band 103 Manga"
    r1 = await lookup_pc(store, q1, None, 1.0, domain="comic")
    zwischen = aufrufe["n"]
    r2 = await lookup_pc(store, q2, None, 1.0, domain="comic")
    assert r1 and r2
    assert aufrufe["n"] == zwischen + 1, "zweite Anfrage hätte nur die Kandidatenliste holen dürfen"
