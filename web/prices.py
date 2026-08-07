"""SERO-Preislogik: echte Kartenpreise aus freien TCG-Quellen (wie Collectr & Co.).

Quellen-Kette pro Sammlungsstück:
  1. Pokémon-Einzelkarten  -> TCGdex (deutsch, Cardmarket-Preise: Trend + Ø 1/7/30 Tage)
  2. Magic-Einzelkarten    -> Scryfall (prices.eur = Cardmarket)
  3. Yu-Gi-Oh-Einzelkarten -> YGOPRODeck (cardmarket_price)
  4. Alles andere (Sealed, One Piece, Games, LEGO, ...) -> eBay-Browse-Median (bestehend)

Die Karten-Identifikation (Spiel, Name, Nummer, Set) macht ein günstiger
Haiku-Text-Call auf Basis der schon vorhandenen Claude-Analyse — kein zweiter
Vision-Call nötig.
"""

from __future__ import annotations

import json
import logging
import re

import httpx

log = logging.getLogger("prices")

IDENTIFY_MODEL = "claude-haiku-4-5-20251001"  # billiger Text-Call, kein Vision nötig

_http = httpx.AsyncClient(timeout=12, headers={"User-Agent": "SERO-Collection/1.0"})

_fx: dict = {}


async def usd_eur() -> float | None:
    """USD->EUR (EZB-Kurse via frankfurter.dev, kostenlos, 12 h gecacht)."""
    import time
    if _fx.get("rate") and time.time() - _fx.get("ts", 0) < 12 * 3600:
        return _fx["rate"]
    try:
        r = await _http.get("https://api.frankfurter.dev/v1/latest",
                            params={"base": "USD", "symbols": "EUR"})
        if r.status_code == 200:
            _fx["rate"] = float(r.json()["rates"]["EUR"])
            _fx["ts"] = time.time()
            return _fx["rate"]
    except Exception as e:  # noqa: BLE001
        log.warning("FX-Kurs nicht erreichbar: %s", e)
    return _fx.get("rate")


def _tcgp_fields(usd, rate) -> dict:
    if usd is None:
        return {}
    try:
        usd = float(usd)
    except (TypeError, ValueError):
        return {}
    return {"tcgplayer_usd": round(usd, 2),
            "tcgplayer_eur": round(usd * rate, 2) if rate else None}


# ---------------------------------------------------------------- Identifikation

async def identify_card(anthropic_key: str, listing: dict, notes: str | None) -> dict | None:
    """Aus der vorhandenen Listing-Analyse die Karten-Stammdaten ziehen.

    Rückgabe: {game, name, number, set_total, set_hint, single} oder None.
    single=False bedeutet: Sealed-Produkt/Display/Sonstiges -> keine Karten-DB.
    """
    import anthropic
    blob = json.dumps({
        "titel": listing.get("title"),
        "merkmale": listing.get("aspects"),
        "kategorie_suche": listing.get("category_query"),
        "notiz": notes,
    }, ensure_ascii=False)
    client = anthropic.AsyncAnthropic(api_key=anthropic_key)
    try:
        msg = await client.messages.create(
            model=IDENTIFY_MODEL, max_tokens=300,
            system=(
                "Du extrahierst Sammelkarten-Stammdaten aus eBay-Listing-Daten. "
                "Antworte NUR mit einem JSON-Objekt:\n"
                '{"single": bool,  // true NUR bei einer EINZELKARTE (auch graded). '
                "Displays, Booster, Boxen, Bundles, Videospiele, Figuren etc. -> false\n"
                ' "game": "pokemon"|"magic"|"yugioh"|"onepiece"|"lorcana"|"dragonball"|"digimon"|"starwars"|"fab"|"sport"|"other",  // sport = Basketball/Fußball/Panini/Topps\n'
                ' "name": "Kartenname OHNE Zusätze wie Sprache/Zustand (z.B. Mega-Quajutsu-ex)",\n'
                ' "number": "Kartennummer im Set ohne führende Nullen, z.B. 100 (aus 100/086), sonst null",\n'
                ' "set_total": "Zahl hinter dem Schrägstrich, z.B. 086 -> 86, sonst null",\n'
                ' "set_hint": "Set-Name oder Set-Code falls erkennbar, sonst null}'
            ),
            messages=[{"role": "user", "content": blob}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`").lstrip("json").strip()
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return data
    except Exception as e:  # noqa: BLE001 — Identifikation ist optional
        log.warning("identify_card fehlgeschlagen: %s", e)
        return None


# ---------------------------------------------------------------- Quellen

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9äöüß]+", "", (s or "").lower())


async def price_pokemon_tcgdex(card: dict) -> dict | None:
    """TCGdex: deutsche Namen, Cardmarket-EUR-Preise (Trend, Ø 1/7/30 Tage)."""
    name = card.get("name")
    if not name:
        return None
    # PRÄZISESTER WEG: Set-Hinweis + Kartennummer -> Karte direkt adressieren.
    # Die Namenssuche findet moderne Karten oft nicht (offiziell „Glurak-ex" mit
    # Bindestrich) und lieferte dann irgendeine gleichnamige Altkarte.
    hits = []
    _sh = _norm(str(card.get("set_hint") or ""))
    _num = str(card.get("number") or "").lstrip("0")
    if _sh and _num:
        try:
            rs = await _http.get("https://api.tcgdex.net/v2/de/sets")
            for s in (rs.json() if rs.status_code == 200 else []):
                sn = _norm(s.get("name") or "")
                if not sn or sn not in _sh:
                    continue
                rc = await _http.get(f"https://api.tcgdex.net/v2/de/sets/{s['id']}/{_num}")
                if rc.status_code != 200:
                    continue
                d0 = rc.json()
                cc = ((d0.get("set") or {}).get("cardCount") or {})
                sizes = {str(cc.get("official") or ""), str(cc.get("total") or "")} - {""}
                # „199/165" nennt die OFFIZIELLE Set-Größe — total zählt Secret Rares mit
                if card.get("set_total") and sizes and str(card["set_total"]) not in sizes:
                    continue
                hits = [{"id": d0["id"], "localId": d0.get("localId"), "name": d0.get("name")}]
                log.info("Karten-Match über Set %s + Nr. %s -> %s", s["id"], _num, d0.get("id"))
                break
        except Exception as e:  # noqa: BLE001 — Namenssuche bleibt als Weg
            log.info("Set-Weg fehlgeschlagen (%s) — weiter über die Namenssuche", e)

    if not hits:
        resp = await _http.get("https://api.tcgdex.net/v2/de/cards", params={"name": name})
        if resp.status_code != 200:
            return None
        hits = resp.json()
    if not hits:
        # deutscher Name nicht gefunden? Englisch probieren
        resp = await _http.get("https://api.tcgdex.net/v2/en/cards", params={"name": name})
        if resp.status_code != 200 or not resp.json():
            return None
        hits = resp.json()

    number = str(card.get("number") or "").lstrip("0")
    exact = [h for h in hits if str(h.get("localId") or "").lstrip("0") == number] if number else []
    # HARTE REGEL: Ist die Kartennummer erkannt, MUSS sie passen. Früher fiel die
    # Suche sonst auf irgendeinen Namenstreffer zurück — so wurde aus „Glurak ex
    # 199/165 (151)" die alte „Glurak EX 11/106 (Flammenmeer)" (Svens Fall 02.08.).
    if number and not exact:
        log.info("Karten-Match: Nummer %s nicht gefunden für %r — keine Zuordnung", number, name)
        return None
    candidates = exact or [h for h in hits if _norm(h.get("name")) == _norm(name)] or hits
    # Bei mehreren Kandidaten: Set-Gesamtzahl als Tiebreaker (aus 100/086 -> 86)
    best = None
    for h in candidates[:6]:
        detail_resp = await _http.get(f"https://api.tcgdex.net/v2/de/cards/{h['id']}")
        if detail_resp.status_code != 200:
            continue
        detail = detail_resp.json()
        pricing = (detail.get("pricing") or {}).get("cardmarket") or {}
        if not pricing.get("trend") and not pricing.get("avg30"):
            continue
        _cc = (detail.get("set") or {}).get("cardCount") or {}
        _sizes = {str(_cc.get("official") or ""), str(_cc.get("total") or "")} - {""}
        total = str(_cc.get("total") or "")
        # Widersprüchliche Set-Größe = anderes Set -> niemals als Treffer zulassen
        if card.get("set_total") and _sizes and str(card["set_total"]) not in _sizes:
            continue
        entry = {"detail": detail, "pricing": pricing,
                 "total_match": bool(card.get("set_total") and str(card["set_total"]) in _sizes)}
        if entry["total_match"]:
            best = entry
            break
        best = best or entry
    if not best:
        return None
    d, p = best["detail"], best["pricing"]
    # Englischen Kartennamen mitholen — Graded-Karten (PSA) werden auf eBay
    # fast immer unter dem englischen Namen gelistet.
    name_en = None
    try:
        en = await _http.get(f"https://api.tcgdex.net/v2/en/cards/{d['id']}")
        if en.status_code == 200:
            name_en = (en.json() or {}).get("name")
    except Exception:  # noqa: BLE001
        pass
    value = p.get("trend") or p.get("avg7") or p.get("avg30") or p.get("avg")
    if not value:
        return None
    # TCGplayer (US) als Zweitreferenz — steckt in derselben TCGdex-Antwort
    tp = (best["detail"].get("pricing") or {}).get("tcgplayer") or {}
    tp_usd = None
    for variant in tp.values():
        if isinstance(variant, dict) and variant.get("marketPrice"):
            tp_usd = variant["marketPrice"]
            break
    rate = await usd_eur() if tp_usd else None
    return {
        "source": "cardmarket", "source_label": "Cardmarket-Trend",
        "value": round(float(value), 2),
        "detail": {"trend": p.get("trend"), "avg1": p.get("avg1"), "avg7": p.get("avg7"),
                   "avg30": p.get("avg30"), "low": p.get("low"), "updated": p.get("updated"),
                   **_tcgp_fields(tp_usd, rate)},
        "card": {
            "game": "pokemon", "name": d.get("name"), "name_en": name_en,
            "set_name": (d.get("set") or {}).get("name"),
            "number": d.get("localId"),
            "total": (d.get("set") or {}).get("cardCount", {}).get("total"),
            "rarity": d.get("rarity"), "ref_id": d.get("id"),
            "image": f"{d['image']}/high.webp" if d.get("image") else None,
            "illustrator": d.get("illustrator"),
            "language": "Deutsch",
            "variants": [k for k, v in (d.get("variants") or {}).items() if v] or None,
            "hp": d.get("hp"), "types": d.get("types"),
        },
    }


async def price_magic_scryfall(card: dict) -> dict | None:
    name = card.get("name")
    if not name:
        return None
    resp = await _http.get("https://api.scryfall.com/cards/named", params={"fuzzy": name})
    if resp.status_code != 200:
        return None
    d = resp.json()
    eurv = (d.get("prices") or {}).get("eur") or (d.get("prices") or {}).get("eur_foil")
    if not eurv:
        return None
    usd = d["prices"].get("usd") or d["prices"].get("usd_foil")
    rate = await usd_eur() if usd else None
    return {
        "source": "scryfall", "source_label": "Cardmarket (Scryfall)",
        "value": round(float(eurv), 2),
        "detail": {"eur": d["prices"].get("eur"), "eur_foil": d["prices"].get("eur_foil"),
                   **_tcgp_fields(usd, rate)},
        "card": {
            "game": "magic", "name": d.get("printed_name") or d.get("name"),
            "set_name": d.get("set_name"), "number": d.get("collector_number"),
            "total": None, "rarity": d.get("rarity"), "ref_id": d.get("id"),
            "image": ((d.get("image_uris") or {}).get("normal")),
        },
    }


async def price_yugioh_ygoprodeck(card: dict) -> dict | None:
    name = card.get("name")
    if not name:
        return None
    resp = await _http.get("https://db.ygoprodeck.com/api/v7/cardinfo.php",
                           params={"fname": name, "language": "de"})
    if resp.status_code != 200:
        return None
    hits = (resp.json() or {}).get("data") or []
    if not hits:
        return None
    d = min(hits, key=lambda h: len(h.get("name", "")))  # kürzester Treffer = bester Match
    prices = (d.get("card_prices") or [{}])[0]
    val = prices.get("cardmarket_price")
    try:
        value = round(float(val), 2)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    images = d.get("card_images") or [{}]
    return {
        "source": "ygoprodeck", "source_label": "Cardmarket (YGOPRODeck)",
        "value": value,
        "detail": {"cardmarket": value,
                   **_tcgp_fields(prices.get("tcgplayer_price"), await usd_eur())},
        "card": {
            "game": "yugioh", "name": d.get("name"), "set_name": None,
            "number": None, "total": None, "rarity": None,
            "ref_id": str(d.get("id")), "image": images[0].get("image_url"),
        },
    }


SOURCES = {
    "pokemon": price_pokemon_tcgdex,
    "magic": price_magic_scryfall,
    "yugioh": price_yugioh_ygoprodeck,
}

# Spiele ohne Spezialquelle laufen über den freien TCGplayer-Spiegel (tcgcsv.com)
TCGCSV_GAMES = {"onepiece", "lorcana", "dragonball", "digimon", "starwars", "fab"}


async def lookup_card_price(card_info: dict, store=None) -> dict | None:
    """Karten-DB-Preis für eine identifizierte Einzelkarte — None, wenn keine Quelle greift."""
    if not card_info or not card_info.get("single"):
        return None
    game = card_info.get("game")
    try:
        if game in TCGCSV_GAMES and store is not None:
            from web.tcgcsv import lookup_tcgcsv  # noqa: PLC0415
            return await lookup_tcgcsv(store, card_info, await usd_eur())
        fn = SOURCES.get(game)
        if not fn:
            return None
        return await fn(card_info)
    except Exception as e:  # noqa: BLE001 — Preisquelle darf nie die Analyse killen
        log.warning("Preisquelle %s fehlgeschlagen: %s", game, e)
        return None
