"""tcgcsv.com — freier TCGplayer-Daten-Spiegel als Universal-Preisquelle.

Deckt die Spiele ab, die unsere Spezialquellen NICHT haben: One Piece, Lorcana
(Disney), Dragon Ball, Digimon, Star Wars Unlimited, Flesh & Blood.
Pro Spiel wird einmalig ein lokaler Produkt-Index aufgebaut (Gruppen -> Produkte
in SQLite, wöchentlich erneuert); Preise je Gruppe werden 12 h gecacht.
Bewertung: TCGplayer-marketPrice (USD) -> EUR über den EZB-Kurs.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time

import httpx

log = logging.getLogger("tcgcsv")

BASE = "https://tcgcsv.com/tcgplayer"
INDEX_TTL = 7 * 86400
PRICE_TTL = 12 * 3600

_http = httpx.AsyncClient(timeout=15, headers={"User-Agent": "SERO-App/1.0"})
_index_locks: dict[int, asyncio.Lock] = {}

# game-Schlüssel (aus identify_card) -> Kategorie-Namen bei TCGplayer
GAME_CATEGORIES = {
    "onepiece": ["One Piece Card Game"],
    "lorcana": ["Lorcana TCG"],
    "dragonball": ["Dragon Ball Super Fusion World", "Dragon Ball Super CCG"],
    "digimon": ["Digimon Card Game"],
    "starwars": ["Star Wars Unlimited"],
    "fab": ["Flesh & Blood TCG"],
}

GAME_LABELS = {
    "onepiece": "One Piece", "lorcana": "Lorcana", "dragonball": "Dragon Ball",
    "digimon": "Digimon", "starwars": "Star Wars", "fab": "Flesh & Blood",
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _ensure_table(store) -> None:
    store._conn.execute(  # noqa: SLF001
        "CREATE TABLE IF NOT EXISTS tcgcsv_products ("
        "product_id INTEGER PRIMARY KEY, cat INTEGER NOT NULL, group_id INTEGER NOT NULL, "
        "name TEXT NOT NULL, norm TEXT NOT NULL, image TEXT, group_name TEXT, abbr TEXT)")
    store._conn.execute(  # noqa: SLF001
        "CREATE INDEX IF NOT EXISTS idx_tcgcsv_cat ON tcgcsv_products (cat)")
    store._conn.commit()  # noqa: SLF001


async def category_ids(store, game: str) -> list[int]:
    """Kategorie-IDs für ein Spiel (Kategorienliste 7 Tage gecacht)."""
    wanted = GAME_CATEGORIES.get(game)
    if not wanted:
        return []
    cats = store.kv_get("tcgcsv_categories")
    if not cats or time.time() - cats.get("ts", 0) > INDEX_TTL:
        r = await _http.get(f"{BASE}/categories")
        r.raise_for_status()
        cats = {"ts": time.time(),
                "list": [{"id": c["categoryId"], "name": c["name"]} for c in r.json()["results"]]}
        store.kv_set("tcgcsv_categories", cats)
    return [c["id"] for c in cats["list"] if c["name"] in wanted]


async def ensure_index(store, cat: int) -> None:
    """Produkt-Index einer Kategorie aufbauen (einmalig, dann wöchentlich).

    Staging: fehlgeschlagene Gruppen markieren den Lauf als unvollständig —
    der alte Index und der Erfolgs-Zeitstempel bleiben dann unangetastet.
    """
    flag = store.kv_get(f"tcgcsv_indexed_v2_{cat}")
    if flag and time.time() - flag.get("ts", 0) < INDEX_TTL:
        return
    lock = _index_locks.setdefault(cat, asyncio.Lock())
    async with lock:
        flag = store.kv_get(f"tcgcsv_indexed_v2_{cat}")
        if flag and time.time() - flag.get("ts", 0) < INDEX_TTL:
            return
        _ensure_table(store)
        log.info("tcgcsv: baue Index für Kategorie %s …", cat)
        r = await _http.get(f"{BASE}/{cat}/groups")
        r.raise_for_status()
        groups = r.json()["results"]
        rows = []
        failed = 0
        for g in groups:
            try:
                pr = await _http.get(f"{BASE}/{cat}/{g['groupId']}/products")
                if pr.status_code != 200:
                    failed += 1
                    continue
                for p in pr.json()["results"]:
                    rows.append((p["productId"], cat, g["groupId"], p["name"],
                                 norm(p["name"]), p.get("imageUrl"), g["name"],
                                 (g.get("abbreviation") or "").upper()))
            except Exception as e:  # noqa: BLE001
                failed += 1
                log.warning("tcgcsv: Gruppe %s übersprungen: %s", g.get("groupId"), e)
            await asyncio.sleep(0.15)  # höflich zum freien Spiegel
        n_groups = max(len(groups), 1)
        incomplete = failed > 0 and (failed / n_groups) > 0.05
        if incomplete and flag and (flag.get("count") or 0) > len(rows):
            log.warning(
                "tcgcsv: Index-Aufbau unvollständig (%d/%d Gruppen fehlgeschlagen, "
                "%d < alte %d) — Staging verworfen, TTL unverändert",
                failed, n_groups, len(rows), flag.get("count"))
            store.kv_set(f"tcgcsv_index_staging_fail_{cat}", {
                "ts": time.time(), "failed": failed, "rows": len(rows),
            })
            return
        with store._lock:  # noqa: SLF001
            store._conn.execute("DELETE FROM tcgcsv_products WHERE cat = ?", (cat,))  # noqa: SLF001
            store._conn.executemany(  # noqa: SLF001
                "INSERT OR REPLACE INTO tcgcsv_products VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
            store._conn.commit()  # noqa: SLF001
        store.kv_set(f"tcgcsv_indexed_v2_{cat}", {
            "ts": time.time(), "count": len(rows), "failed_groups": failed,
        })
        log.info("tcgcsv: Kategorie %s indexiert (%d Produkte, %d Gruppen fehlgeschlagen)",
                 cat, len(rows), failed)


def search_products(store, cats: list[int], query: str, limit: int = 12) -> list[dict]:
    """Namens-Suche im lokalen Index: alle Wörter müssen vorkommen, Karten zuerst."""
    _ensure_table(store)
    tokens = [t for t in norm(query).split() if t]
    if not tokens or not cats:
        return []
    where = " AND ".join(["norm LIKE ?"] * len(tokens))
    params = [f"%{t}%" for t in tokens]
    marks = ",".join("?" * len(cats))
    rows = store._conn.execute(  # noqa: SLF001
        f"SELECT * FROM tcgcsv_products WHERE cat IN ({marks}) AND {where} "
        f"ORDER BY LENGTH(name) LIMIT ?", (*cats, *params, limit)).fetchall()
    return [dict(r) for r in rows]


async def group_prices(store, cat: int, group_id: int) -> dict:
    """Preise einer Gruppe (productId -> marketPrice USD), 12 h gecacht."""
    key = f"tcgcsv_prices_{cat}_{group_id}"
    cached = store.kv_get(key)
    if cached and time.time() - cached.get("ts", 0) < PRICE_TTL:
        return cached["p"]
    r = await _http.get(f"{BASE}/{cat}/{group_id}/prices")
    r.raise_for_status()
    prices: dict[str, float] = {}
    for row in r.json()["results"]:
        mp = row.get("marketPrice")
        if not mp:
            continue
        pid = str(row["productId"])
        # Normal bevorzugen, Foil nur wenn nichts anderes da ist
        if pid not in prices or row.get("subTypeName") == "Normal":
            prices[pid] = float(mp)
    store.kv_set(key, {"ts": time.time(), "p": prices})
    return prices


async def lookup_tcgcsv(store, card_info: dict, usd_eur_rate: float | None) -> dict | None:
    """Karte in tcgcsv finden und bewerten. card_info.tcgcsv (manuelle Auswahl) hat Vorrang."""
    game = card_info.get("game")
    cats = await category_ids(store, game)
    if not cats:
        return None
    for cat in cats:
        await ensure_index(store, cat)

    candidates: list[dict] = []
    manual = card_info.get("tcgcsv")
    if manual and manual.get("product_id"):
        _ensure_table(store)
        row = store._conn.execute(  # noqa: SLF001
            "SELECT * FROM tcgcsv_products WHERE product_id = ?",
            (manual["product_id"],)).fetchone()
        if row:
            candidates = [dict(row)]
    if not candidates:
        name = card_info.get("name") or ""
        number = str(card_info.get("number") or "").strip()
        hint = str(card_info.get("set_hint") or "")
        # Kartencode wie OP01-003 / EB04-061 — aus Nummer, Hint oder zusammengebaut
        code = None
        m = re.search(r"[A-Z]{1,4}\d{0,2}-\d{2,3}", f"{number} {hint} {name}", re.I)
        if m:
            code = m.group(0).upper()
        elif hint and number.isdigit():
            # identify liefert oft set_hint=EB04 + number=61 statt EB04-061
            hm = re.match(r"^([A-Za-z]{1,4})-?(\d{1,2})$", hint.strip())
            if hm:
                code = f"{hm.group(1).upper()}{int(hm.group(2)):02d}-{int(number):03d}"
        candidates = search_products(store, cats, name)
        if code:
            prefix, _, suffix = code.partition("-")
            # (061) ODER (EB04-061) — TCGplayer mischt beide Schreibweisen
            suffix_re = re.compile(
                rf"\((?:{re.escape(code)}|0*{re.escape(suffix.lstrip('0') or suffix)})\)",
                re.I)
            marks = ",".join("?" * len(cats))
            # Produkte, die den Code wörtlich im Namen führen (Promos wie „Carrot - P-070");
            # NICHT tokenisiert suchen — norm("P-099") = "p 099" träfe z. B. "Captain"
            explicit = [c for c in candidates + search_products(store, cats, code)
                        if code.lower() in c["name"].lower()]
            # Set-Kürzel: EB04 == EB-04 und steckt in OP15-EB04
            pnorm = re.sub(r"[^A-Z0-9]", "", prefix.upper())
            abbrs = {r["abbr"] for r in store._conn.execute(  # noqa: SLF001
                f"SELECT DISTINCT abbr FROM tcgcsv_products WHERE cat IN ({marks})",
                tuple(cats)).fetchall() if r["abbr"]}
            actual = [a for a in abbrs
                      if (an := re.sub(r"[^A-Z0-9]", "", a)) == pnorm or pnorm in an]
            anchored = []
            if actual:
                amarks = ",".join("?" * len(actual))
                first = norm(name).split()[0] if norm(name) else ""
                rows = store._conn.execute(  # noqa: SLF001
                    f"SELECT * FROM tcgcsv_products WHERE cat IN ({marks}) "
                    f"AND abbr IN ({amarks}) AND norm LIKE ?",
                    (*cats, *actual, f"%{first}%")).fetchall()
                anchored = [dict(r) for r in rows if suffix_re.search(r["name"])
                            or code.lower() in r["name"].lower()]
                if not anchored:
                    # Viele Sets führen die Nummer nicht im Namen — Kürzel allein zählt dann
                    anchored = [dict(r) for r in rows]
            merged, seen = [], set()
            for c in anchored + explicit:   # Kürzel-Anker zuerst, dann explizite Codes
                if c["product_id"] not in seen:
                    seen.add(c["product_id"])
                    merged.append(c)
            anchored_ids = {c["product_id"] for c in anchored}
            if merged:
                seen2 = {c["product_id"] for c in merged}
                # Namens-Treffer bleiben als Nachrücker — Sonder-Kollektionen
                # (z. B. „Best Selection") tragen oft ein fremdes Set-Kürzel
                candidates = merged + [c for c in candidates if c["product_id"] not in seen2]
            elif not actual and not explicit:
                # Set (noch) gar nicht bei TCGplayer — lieber KEIN Preis als der einer
                # fremden Version; der Aufrufer fällt dann auf den eBay-Median zurück
                return None
        elif number:
            numbered = [c for c in candidates if re.search(rf"\(0*{re.escape(number)}\)", c["name"])]
            candidates = numbered or candidates
    if not candidates:
        return None

    # Basis vor Parallel/Alt-Art/SP — und Parallel ≠ SP (sonst 270-$-Fehlmatch)
    from web.prices import card_variant_kind, variants_compatible, card_name_is_variant
    want_kind = card_variant_kind(
        card_info.get("name"), card_info.get("set_hint"), card_info.get("edition"),
        card_info.get("rarity"))
    # Code-/Zahl-Tokens (op01, 121, cgc …) zählen NICHT als Hinweis — der Code-Anker
    # ist schon behandelt; sonst gewinnt ein Reprint, nur weil der Code im Namen steht
    hint_tokens = {t for t in norm(
        f"{card_info.get('name') or ''} {card_info.get('set_hint') or ''} "
        f"{card_info.get('edition') or ''}").split()
        if not re.fullmatch(r"\d+|[a-z]{1,4}\d+|cgc|psa|bgs", t)}
    name_tokens = set(norm(card_info.get("name") or "").split())
    STOP = {"one", "piece", "card", "cards", "promo", "promotion", "the", "of", "and", "game"}
    anchored_ids = locals().get("anchored_ids") or set()

    def _score(c):
        extra = set(norm(f"{c['name']} {c.get('group_name') or ''}").split()) - name_tokens - STOP
        overlap = sum(1 for t in extra if t in hint_tokens)
        have_kind = card_variant_kind(c["name"])
        if variants_compatible(want_kind, have_kind):
            mismatch = 0
        elif have_kind is None and want_kind in ("parallel", "alt"):
            mismatch = 1   # Basis als Rückfall
        else:
            mismatch = 2   # falsche Familie (z. B. SP statt Parallel)
        return (-overlap,
                c["product_id"] not in anchored_ids if anchored_ids else False,
                mismatch,
                len(c["name"]))

    candidates.sort(key=_score)

    # Kandidaten durchgehen, bis einer einen Marktpreis hat (Promo-Gruppen sind oft preislos)
    chosen, usd = None, None
    for cand in candidates[:6]:
        prices = await group_prices(store, cand["cat"], cand["group_id"])
        usd = prices.get(str(cand["product_id"]))
        if usd:
            chosen = cand
            break
    if not chosen or not usd:
        return None
    eur = round(usd * usd_eur_rate, 2) if usd_eur_rate else None
    if eur is None:
        return None
    label = GAME_LABELS.get(game, game)
    # Bei „Name (111) (Parallel)" die Zahl, nicht das Varianten-Wort
    num_m = re.search(r"\((\d+[A-Za-z]?)\)", chosen["name"])
    return {
        "source": "tcgplayer", "source_label": "TCGplayer-Markt (US)",
        "value": eur,
        "detail": {"tcgplayer_usd": round(usd, 2), "tcgplayer_eur": eur},
        "card": {
            "game": game, "name": chosen["name"],
            "set_name": chosen["group_name"], "number": num_m.group(1) if num_m else None,
            "total": None, "rarity": None,
            "ref_id": str(chosen["product_id"]), "image": chosen.get("image"),
            "language": "Englisch (TCGplayer)",
            "edition": ("Parallel" if card_name_is_variant(chosen["name"]) else None),
        },
    }
