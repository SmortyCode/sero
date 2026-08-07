"""PriceCharting-API — Svens Hauptpreisquelle (Legendary Sub).

Sold-basierte Preise, bepreist Graded-Slabs (PSA/BGS/CGC) SEPARAT, dazu
Sealed, Videospiele (WATA) und Sport. Preise kommen in US-Cent ("pennies").
Feld-Zuordnung bei Karten: loose=ungraded, graded=Grade 9, box-only=Grade 9.5,
manual-only=PSA 10, bgs-10/condition-17/18 = BGS 10 / CGC 10 / CGC 9.5.
"""
from __future__ import annotations

import logging
import os
import time

import httpx

log = logging.getLogger("pricecharting")
_http = httpx.AsyncClient(timeout=20)
TTL = 12 * 3600


# ── Domänen-Gate (Stufe 2, 03.08.2026) ────────────────────────────────────
# Svens Manga Band 103 bekam 603 €, weil die Suche die SAMMELKARTE
# „Nami [Manga] OP01-016" traf statt des Buchs. PriceCharting trägt die
# Warenart im Feld console-name — ein Buch liegt unter „Comic Books One
# Piece", die Karte unter „One Piece Romance Dawn". Das Gate vergleicht die
# Domäne des Stücks mit der des Treffers und verwirft Fremdes.

_PC_GAME_WOERTER = (
    "playstation", "nintendo", "xbox", "sega", "gamecube", "game boy",
    "gameboy", "switch", "wii", "n64", "snes", "nes", "atari", "dreamcast",
    "psp", "vita", "genesis", "saturn", "game gear", "neo geo", "turbografx",
    "3ds", " ds", "pc games", "commodore", "amiga", "intellivision", "jaguar",
)
_PC_TCG_WOERTER = (
    "pokemon", "one piece", "magic", "yugioh", "yu-gi-oh", "lorcana",
    "digimon", "dragon ball", "weiss", "union arena", "metazoo",
    "flesh and blood", "star wars unlimited", "cardfight", "vanguard",
    "cards",   # „Baseball Cards", „Basketball Cards", …
)


def domain_of_pc(console_name: str | None) -> str:
    """PriceCharting-console-name → Warenart: comic / game / tcg / other."""
    c = (console_name or "").lower()
    if not c:
        return "other"
    if c.startswith("comic"):
        return "comic"
    if any(w in c for w in _PC_GAME_WOERTER):
        return "game"
    if any(w in c for w in _PC_TCG_WOERTER):
        return "tcg"
    return "other"


def domain_of_item(item: dict) -> str | None:
    """Warenart eines Stücks — aus Name, Analyse und Grader.

    Die App-Kategorie taugt dafür NICHT: Svens Manga läuft unter „One
    Piece" (Marke), das Gate braucht aber den Stück-Typ. None heißt
    „kein Urteil" — das Gate lässt dann alles durch, bewusst: ein offenes
    Gate liefert schlimmstenfalls den heutigen Stand, ein falsch
    geschlossenes verliert echte Treffer (v0-Datensätze!).
    """
    grader = str((item.get("graded") or {}).get("grader") or "").upper()
    if grader in ("WATA", "VGA", "CGA"):
        return "game"
    import unicodedata
    blob = " ".join(str(x or "") for x in (
        item.get("name"),
        (item.get("analysis") or {}).get("title"),
        (item.get("analysis") or {}).get("search_query_for_pricing"),
    )).lower()
    # Akzente weg: „Pokémon" muss „pokemon" treffen
    blob = unicodedata.normalize("NFKD", blob).encode("ascii", "ignore").decode()
    if not blob.strip():
        return None
    if any(w in blob for w in ("manga", "comic", "tankobon", " band ", "volume", " vol.", " vol ")):
        return "comic"
    if any(w in blob for w in _PC_GAME_WOERTER):
        return "game"
    if any(w in blob for w in ("karte", "card", "tcg", "booster", "display",
                               "etb", "holo", "promo")) \
            or any(w in blob for w in _PC_TCG_WOERTER[:-1]):
        return "tcg"
    return None


def _grade_fields(graded: dict | None) -> list[str]:
    if not graded or not graded.get("grade"):
        return ["loose-price"]
    g = str(graded.get("grade", "")).replace(",", ".")
    grader = str(graded.get("grader", "")).upper()
    # Videospiel-Grader: bei Games heißt "graded-price" = WATA/VGA-graded,
    # "new-price" = sealed, "box-only" = leerer Karton (NICHT Grade 9.5!)
    if grader in ("WATA", "VGA", "CGA"):
        return ["graded-price", "new-price"]
    try:
        val = float(g)
    except ValueError:
        val = 0
    if val >= 10:
        if "BGS" in grader:
            return ["bgs-10-price", "manual-only-price", "graded-price"]
        if "CGC" in grader:
            return ["condition-17-price", "manual-only-price", "graded-price"]
        return ["manual-only-price", "graded-price"]
    if val >= 9.5:
        return ["box-only-price", "graded-price"]
    if val >= 9:
        return ["graded-price", "box-only-price"]
    if val >= 8:
        return ["new-price", "graded-price", "cib-price"]
    return ["cib-price", "loose-price"]


def _zwischenstufe(prod: dict, graded: dict | None, cents: int, used: str) -> int:
    """Feinabstufung zwischen zwei bekannten PriceCharting-Stufen.

    Die Quelle liefert Preise für Grade 9 („graded-price"), 9.5 („box-only")
    und 10 („manual-only"). Eine 9.4 ist erkennbar mehr wert als eine 9.0 —
    ohne diese Einordnung bekämen beide denselben Betrag (Svens Manga-Fall).
    """
    if not graded:
        return cents
    try:
        note = float(str(graded.get("grade", "")).replace(",", "."))
    except ValueError:
        return cents
    # Nur im Bereich zwischen zwei bekannten Stützstellen interpolieren
    paare = ((9.0, 9.5, "graded-price", "box-only-price"),
             (9.5, 10.0, "box-only-price", "manual-only-price"))
    for unten, oben, f_unten, f_oben in paare:
        if not (unten < note < oben):
            continue
        c_u, c_o = prod.get(f_unten), prod.get(f_oben)
        if not c_u or not c_o or c_o <= c_u:
            return cents            # ohne beide Stützstellen bleibt es beim Feldwert
        anteil = (note - unten) / (oben - unten)
        return int(round(c_u + (c_o - c_u) * anteil))
    return cents


async def lookup_pc(store, query: str, graded: dict | None, usd_rate: float | None,
                    domain: str | None = None) -> dict | None:
    """Preis von PriceCharting — seit Stufe 2 (03.08.) mit Domänen-Gate.

    Statt des einen Fuzzy-Treffers (/api/product?q=) holt die Suche bis zu
    20 Kandidaten (/api/products) und verwirft alle, deren console-name
    einer FREMDEN Warenart angehört. Erst der Gewinner kostet den zweiten
    Call auf die Preisfelder. domain=None lässt alles durch (Altverhalten,
    v0-Datensätze ohne Typ-Wissen).
    """
    # Lizenz-Schalter (Audit P0.5): PriceCharting-ToS beschränken die Daten auf
    # "Internal Business Purposes" und verbieten die Weitergabe an Dritte. Für
    # ein öffentliches Produkt muss die Quelle AUS sein — Default ist deshalb
    # aus; nur der Einzelbetrieb des Betreibers schaltet sie per Env ein.
    if os.environ.get("SERO_QUELLE_PRICECHARTING", "0") != "1":
        return None

    token = os.environ.get("PRICECHARTING_TOKEN")
    if not token or not query or not usd_rate:
        return None
    import hashlib

    # Stufe A: Kandidatenliste (gecacht je Anfrage)
    qkey = "pcq_" + hashlib.sha1(query.lower().encode()).hexdigest()[:16]
    cached = store.kv_get(qkey)
    if cached and time.time() - cached.get("ts", 0) < TTL:
        kandidaten = cached.get("v") or []
    else:
        try:
            r = await _http.get("https://www.pricecharting.com/api/products",
                                params={"t": token, "q": query})
            r.raise_for_status()
            kandidaten = (r.json().get("products") or [])[:20]
        except Exception as e:  # noqa: BLE001
            log.warning("pricecharting: %s", e)
            return None
        store.kv_set(qkey, {"ts": time.time(), "v": kandidaten})

    # Gate: erster Kandidat, dessen Warenart zum Stück passt. „other" auf
    # PC-Seite bleibt durchlässig — dort ist kein Urteil möglich.
    gewinner = None
    for k in kandidaten:
        if not k.get("id"):
            continue
        if domain:
            pc_dom = domain_of_pc(k.get("console-name"))
            if pc_dom != "other" and pc_dom != domain:
                continue
        gewinner = k
        break
    if not gewinner:
        if kandidaten and domain:
            log.info("pricecharting: alle %d Treffer zu %r fremder Domäne (%s) — verworfen",
                     len(kandidaten), query[:50], domain)
        return None

    # Stufe B: Preisfelder des Gewinners (gecacht je Produkt-ID)
    pkey = f"pcp_{gewinner['id']}"
    cached = store.kv_get(pkey)
    if cached and time.time() - cached.get("ts", 0) < TTL:
        prod = cached.get("v")
    else:
        try:
            r = await _http.get("https://www.pricecharting.com/api/product",
                                params={"t": token, "id": gewinner["id"]})
            r.raise_for_status()
            prod = r.json()
            if not prod.get("id"):
                prod = None
        except Exception as e:  # noqa: BLE001
            log.warning("pricecharting: %s", e)
            return None
        store.kv_set(pkey, {"ts": time.time(), "v": prod})
    if not prod:
        return None
    cents = None
    used = None
    for f in _grade_fields(graded):
        if prod.get(f):
            cents, used = prod[f], f
            break
    if not cents:
        return None
    # PriceCharting kennt nur grobe Stufen (9 / 9.5 / 10). Eine BGS 9.4 und eine
    # BGS 9.0 landen dadurch im selben Feld und bekommen denselben Preis —
    # obwohl die bessere Erhaltung deutlich mehr bringt. Zwischen den bekannten
    # Stufen wird deshalb linear eingeordnet, sofern beide Nachbarwerte
    # vorliegen. Nur eine Feinabstufung, keine erfundene Zahl.
    cents = _zwischenstufe(prod, graded, cents, used)
    eur = round(cents / 100 * usd_rate, 2)
    grade_note = "" if used == "loose-price" else f" ({(graded or {}).get('grader', '')} {(graded or {}).get('grade', '')})".rstrip()
    return {
        "value": eur, "source": "pricecharting",
        "source_label": f"PriceCharting-Verkäufe{grade_note}",
        "detail": {"pc_usd": round(cents / 100, 2), "pc_field": used,
                   "pc_product": prod.get("product-name"),
                   "pc_console": prod.get("console-name"), "pc_id": prod.get("id")},
    }
