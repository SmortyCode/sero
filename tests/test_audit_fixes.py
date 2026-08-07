"""Tests für die Befunde aus dem Audit vom 02.08.2026.

Jeder Test hier steht für einen Fehler, der echtes Geld oder echte Daten
gekostet hätte. Sie dürfen nie wieder rot werden.
"""

import datetime
import time

import httpx
import pytest

from bot.main import parse_price


# ── 1. Preis-Eingabe: aus „1.500" wurde 1,50 € ──────────────────────────────

@pytest.mark.parametrize("eingabe,erwartet", [
    # Deutsche Schreibweise — der Fehler, der Sven 1.348 € gekostet hätte
    ("1.500", "1500.00"),
    ("1.500,50", "1500.50"),
    ("12,90", "12.90"),
    ("123.456", "123456.00"),      # Punkt als Tausendertrennung, deutsch
    # Englische Schreibweise
    ("1,234.56", "1234.56"),
    ("1234.56", "1234.56"),
    ("0.99", "0.99"),
    # Mit Währung und Leerzeichen
    ("12,90 €", "12.90"),
    (" 45 EUR ", "45.00"),
    (" 99,99 €", "99.99"),
    # Müll muss None sein, nicht NaN — NaN legt später die ganze Sammlung lahm
    ("nan", None),
    ("NaN", None),
    ("inf", None),
    ("1e99", None),
    ("abc", None),
    ("", None),
    ("0", None),
    ("-5", None),
    ("99999999", None),      # über einer Million: kein Kartenpreis, ein Tippfehler
    ("1.234.567", None),     # dito — 1,2 Mio. für eine Karte ist ein Vertipper
])
def test_parse_price(eingabe, erwartet):
    assert parse_price(eingabe) == erwartet


def test_parse_price_niemals_nan():
    """Der eine Fall, der die Sammlung dauerhaft zerstört hat: ein NaN in der
    Datenbank macht jeden JSON-Abruf zu HTTP 500 — für immer, bis jemand von
    Hand in die Datei greift."""
    import math
    for gift in ("nan", "NaN", "-nan", "inf", "-inf", "Infinity"):
        ergebnis = parse_price(gift)
        assert ergebnis is None, f"{gift!r} kam durch als {ergebnis!r}"
        if ergebnis is not None:
            assert math.isfinite(float(ergebnis))


# ── 2. Portfolio-Kerzen: laufende Summe muss exakt wie die alte Summe rechnen ─

def _ohlc_laufend(rows, qty):
    """Die neue Rechnung aus app_api.portfolio_ohlc, isoliert nachgebaut."""
    current, gesamt_cent, candles = {}, 0, {}
    for r in rows:
        iid = r["item_id"]
        if iid not in qty:
            continue
        cent = int(round(r["value"] * 100))
        gesamt_cent += (cent - current.get(iid, 0)) * qty[iid]
        current[iid] = cent
        total = round(gesamt_cent / 100, 2)
        day = datetime.date.fromtimestamp(r["ts"]).isoformat()
        c = candles.get(day)
        if c is None:
            candles[day] = {"day": day, "o": total, "h": total, "l": total, "c": total}
        else:
            c["h"] = max(c["h"], total)
            c["l"] = min(c["l"], total)
            c["c"] = total
    return [candles[d] for d in sorted(candles)]


def _ohlc_alt(rows, qty):
    """Die alte, langsame Rechnung — als Maßstab für die Richtigkeit."""
    current, candles = {}, {}
    for r in rows:
        if r["item_id"] not in qty:
            continue
        current[r["item_id"]] = r["value"]
        total = round(sum(v * qty[i] for i, v in current.items()), 2)
        day = datetime.date.fromtimestamp(r["ts"]).isoformat()
        c = candles.get(day)
        if c is None:
            candles[day] = {"day": day, "o": total, "h": total, "l": total, "c": total}
        else:
            c["h"] = max(c["h"], total)
            c["l"] = min(c["l"], total)
            c["c"] = total
    return [candles[d] for d in sorted(candles)]


def test_ohlc_laufende_summe_ist_identisch():
    import random
    random.seed(42)
    qty = {f"i{n}": random.randint(1, 4) for n in range(80)}
    rows = [{"item_id": f"i{random.randrange(80)}", "ts": 1785000000 + n * 1800,
             "value": round(random.uniform(0.5, 1500), 2)} for n in range(3000)]
    assert _ohlc_laufend(rows, qty) == _ohlc_alt(rows, qty)


def test_ohlc_ignoriert_fremde_items():
    qty = {"a": 2}
    rows = [{"item_id": "a", "ts": 1785000000, "value": 10.0},
            {"item_id": "weg", "ts": 1785000100, "value": 999.0},
            {"item_id": "a", "ts": 1785000200, "value": 12.0}]
    kerzen = _ohlc_laufend(rows, qty)
    assert len(kerzen) == 1
    assert kerzen[0]["o"] == 20.0 and kerzen[0]["c"] == 24.0


# ── 3. eBay: wiederholen ja, doppelt listen nein ────────────────────────────

def _client(cfg_scopes=()):
    from bot.ebay.auth import EbayClient

    class FakeStore:
        def __init__(self):
            self.kv = {}

        def kv_get(self, k):
            return self.kv.get(k)

        def kv_set(self, k, v):
            self.kv[k] = v

    class FakeCfg:
        ebay_client_id = "id"
        ebay_client_secret = "secret"
        ebay_ru_name = "ru"

    c = EbayClient.__new__(EbayClient)
    c.cfg = FakeCfg()
    c.store = FakeStore()
    c.store.kv_set("ebay_user_token_7", {
        "access_token": "tok", "access_expires": time.time() + 9999,
        "refresh_token": "ref", "refresh_expires": time.time() + 99999})
    c._app_token = None
    c._refresh_locks = {}
    return c


@pytest.mark.asyncio
async def test_get_wird_bei_503_wiederholt():
    """5xx geht meist von allein weg — ein GET darf man gefahrlos nachfragen."""
    from bot.ebay import auth as auth_mod

    c = _client()
    versuche = []

    async def handler(request):
        versuche.append(1)
        if len(versuche) < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"ok": True})

    c._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    auth_mod._BACKOFF = (0.01, 0.01, 0.01)
    resp = await c.request("GET", "https://x/test", auth="user", user_id=7)
    assert resp.status_code == 200
    assert len(versuche) == 3
    await c._http.aclose()


@pytest.mark.asyncio
async def test_post_wird_nie_blind_wiederholt():
    """Der teuerste denkbare Fehler: ein zweites Listing derselben Karte.
    Ein POST, dessen Antwort ausbleibt, muss melden statt zu wiederholen."""
    from bot.ebay.auth import EbayTimeout

    c = _client()
    versuche = []

    async def handler(request):
        versuche.append(1)
        raise httpx.ReadTimeout("keine Antwort", request=request)

    c._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(EbayTimeout):
        await c.request("POST", "https://x/offer", auth="user", user_id=7, json_body={})
    assert len(versuche) == 1, "POST wurde wiederholt — das legt Karten doppelt an"
    await c._http.aclose()


@pytest.mark.asyncio
async def test_refresh_schickt_keinen_scope():
    """Mit scope antwortet eBay invalid_scope, sobald wir je ein Recht ergänzen —
    und das Konto ist bis zum manuellen Neuverbinden tot. Genau so passiert am 30.07."""
    c = _client()
    # Access-Token abgelaufen — sonst sagt der Refresh (korrekt): nichts zu tun
    c.store.kv_set("ebay_user_token_7", {
        "access_token": "alt", "access_expires": time.time() - 10,
        "refresh_token": "ref", "refresh_expires": time.time() + 99999})
    gesehen = {}

    async def handler(request):
        gesehen["body"] = request.content.decode()
        return httpx.Response(200, json={"access_token": "neu", "expires_in": 7200})

    c._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await c.refresh_user_token(7)
    assert "scope" not in gesehen["body"]
    assert "grant_type=refresh_token" in gesehen["body"]
    await c._http.aclose()


@pytest.mark.asyncio
async def test_refresh_behaelt_altes_refresh_token():
    """eBay schickt beim Refresh kein neues Refresh-Token. Wer es dann leert,
    sperrt sich selbst aus."""
    c = _client()
    c.store.kv_set("ebay_user_token_7", {
        "access_token": "alt", "access_expires": time.time() - 10,
        "refresh_token": "ref", "refresh_expires": time.time() + 99999})

    async def handler(request):
        return httpx.Response(200, json={"access_token": "neu", "expires_in": 7200})

    c._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await c.refresh_user_token(7)
    assert c.store.kv_get("ebay_user_token_7")["refresh_token"] == "ref"
    await c._http.aclose()


# ── 4. Kaputte Werte dürfen die Sammlung nicht lahmlegen ────────────────────

def _num(v, default=0.0):
    """Gegenstück zu app_api._num — hier isoliert getestet."""
    import math
    try:
        f = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


@pytest.mark.parametrize("roh,erwartet", [
    ("12,90", 12.90), ("12.90", 12.90), (5, 5.0), (None, 0.0),
    ("", 0.0), ("abc", 0.0), ("nan", 0.0), ("inf", 0.0), ("-inf", 0.0),
    (float("nan"), 0.0), (float("inf"), 0.0),
])
def test_num_faengt_alles_ab(roh, erwartet):
    assert _num(roh) == erwartet


def test_num_summe_bleibt_serialisierbar():
    """Der eigentliche Zweck: das Ergebnis muss durch json.dumps passen."""
    import json
    summe = sum(_num(v) * 2 for v in ["10,50", "nan", None, float("inf"), "3"])
    json.dumps({"invested": summe})     # wirft bei NaN einen ValueError
    assert summe == 27.0


# ── 5. Payload-Validierung: nichts Kaputtes erreicht eBay ───────────────────

def test_norm_price_faengt_muell():
    from bot.ebay.inventory import InventoryError, norm_price
    assert norm_price("8,50") == "8.50"
    assert norm_price("1.234,50") == "1234.50"
    assert norm_price("1234.50") == "1234.50"
    for schlecht in (None, "", "None", "abc", "0", "-5", "nan"):
        with pytest.raises(InventoryError):
            norm_price(schlecht)


def test_build_offer_payload_verweigert_unvollstaendiges():
    from bot.ebay.inventory import InventoryError, build_offer_payload
    policies = {"merchant_location_key": "L", "fulfillment_policy_id": "F",
                "payment_policy_id": "P", "return_policy_id": "R"}
    ok = build_offer_payload(policies, "SKU1", category_id="183454",
                             price_eur="12,90", listing_description="x")
    assert ok["pricingSummary"]["price"]["value"] == "12.90"
    with pytest.raises(InventoryError):        # Preis None → früher Listing mit "None"
        build_offer_payload(policies, "SKU1", category_id="183454",
                            price_eur=None, listing_description="x")
    with pytest.raises(InventoryError):        # Kategorie fehlt
        build_offer_payload(policies, "SKU1", category_id=None,
                            price_eur="5.00", listing_description="x")
    with pytest.raises(InventoryError):        # Policies unvollständig
        build_offer_payload({"merchant_location_key": "L"}, "SKU1",
                            category_id="183454", price_eur="5.00",
                            listing_description="x")
    with pytest.raises(InventoryError):        # Mindestpreis >= Angebotspreis
        build_offer_payload(policies, "SKU1", category_id="183454",
                            price_eur="5.00", listing_description="x",
                            best_offer={"enabled": True, "min_price": "6,00"})


def test_kurz_titel_kappt_an_wortgrenze():
    from bot.ebay.inventory import kurz_titel
    lang = "Pokémon Glurak ex 199/165 151 Special Illustration Rare CGC 10 Deutsch Near Mint Holo"
    gekappt = kurz_titel(lang)
    assert len(gekappt) <= 80
    assert not gekappt.endswith(" ")
    assert lang.startswith(gekappt)            # nur hinten gekürzt
    assert gekappt == lang[:len(gekappt)] and lang[len(gekappt)] == " "  # Wortgrenze


@pytest.mark.asyncio
async def test_gueltiges_token_wird_nicht_refresht():
    """Der Gewinn des Refresh-Locks: wer beim Warten überholt wurde, refresht
    nicht noch einmal — eBay sieht nur einen POST statt N."""
    c = _client()
    aufrufe = []

    async def handler(request):
        aufrufe.append(1)
        return httpx.Response(200, json={"access_token": "neu", "expires_in": 7200})

    c._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tok = await c.refresh_user_token(7)      # Token ist noch 9999 s gültig
    assert tok == "tok" and not aufrufe      # kein einziger POST
    await c._http.aclose()


@pytest.mark.asyncio
async def test_refresh_fehlschlag_macht_10min_pause():
    """Widerrufenes Token: der erste 400 setzt eine Ruhephase — weitere Versuche
    schlagen sofort fehl, statt eBay mit vergeblichen POSTs zu fluten."""
    from bot.ebay.auth import EbayAuthError
    c = _client()
    c.store.kv_set("ebay_user_token_7", {
        "access_token": "alt", "access_expires": time.time() - 10,
        "refresh_token": "tot", "refresh_expires": time.time() + 99999})
    aufrufe = []

    async def handler(request):
        aufrufe.append(1)
        return httpx.Response(400, json={"error": "invalid_grant"})

    c._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(EbayAuthError):
        await c.refresh_user_token(7)
    with pytest.raises(EbayAuthError):
        await c.refresh_user_token(7)        # innerhalb der Ruhe: kein neuer POST
    assert len(aufrufe) == 1
    await c._http.aclose()


# ---------------------------------------------------------------- Audit 07.08. (ChatGPT-Befunde P1)

def _server_quelle():
    from pathlib import Path
    return (Path(__file__).parent.parent / "web" / "server.py").read_text()


def test_checkout_fail_closed_in_produktion():
    """Ohne STRIPE_SECRET_KEY darf Produktion NIE gratis freischalten. Der
    Dev-Pfad (Plan sofort aktivieren) muss hinter einer IS_PROD-Ablehnung liegen."""
    q = _server_quelle()
    start = q.index('@app.post("/api/checkout")')
    ende = q.index("class CheckoutConfirmBody")
    checkout = q[start:ende]
    assert "if IS_PROD:" in checkout
    assert checkout.index("if IS_PROD:") < checkout.index("store.update_account"), \
        "Die Produktions-Ablehnung muss VOR der Gratis-Aktivierung stehen"


def test_cookie_secure_flag_haengt_an_app_env():
    assert "secure=IS_PROD" in _server_quelle()


def test_keine_hostheader_links():
    """Ausgehende Links (Login-Mail, Stripe, OAuth) nur über public_base_url —
    request.base_url ist Angreifer-kontrolliert (Host-Header)."""
    import re
    q = _server_quelle()
    treffer = [z for z in q.splitlines()
               if re.search(r"request\.base_url", z)
               and "def public_base_url" not in z
               and not z.lstrip().startswith("#")
               and "PUBLIC_BASE_URL or" not in z]
    assert treffer == [], f"Host-Header-Links gefunden: {treffer}"


def test_produktions_start_verlangt_basis_url():
    q = _server_quelle()
    assert 'if IS_PROD and not PUBLIC_BASE_URL' in q


def test_kontoloeschung_raeumt_beide_token_schluessel():
    """Der eBay-Token liegt nach dem Verbinden unter Telegram-ID UND synthetischer
    App-ID — die Löschung muss beide Identitäten räumen (Token-Leiche)."""
    from pathlib import Path
    q = (Path(__file__).parent.parent / "web" / "app_api.py").read_text()
    start = q.index("async def delete_account")
    block = q[start:start + 3000]
    assert "ACCOUNT_UID_OFFSET + aid" in block
    assert "for u in uids" in block
