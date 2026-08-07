"""Globales Karten-Register + Preis-Katalog (Svens Skalierungs-Entscheid, Phase 1).

Eine Karte existiert EINMAL (Tabelle cards); ihr Preis pro Grade-Stufe EINMAL
(Tabelle card_prices, 24-h-TTL + manueller Force-Refresh). Alle Items und alle
Nutzer lesen dieselbe Zeile — Konsistenz per Bauart, und jede externe Quelle
(130point, PriceCharting) wird 1× pro Karte statt 1× pro Nutzer befragt.
Bewusst nur Standard-SQL, damit der spätere Postgres-Umzug trivial bleibt.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time

log = logging.getLogger("catalog")

PRICE_TTL = 24 * 3600


_ready = False


def ensure_tables(store) -> None:
    global _ready
    if _ready:
        return
    _ready = True
    store._conn.execute(  # noqa: SLF001
        "CREATE TABLE IF NOT EXISTS cards ("
        "card_key TEXT PRIMARY KEY, game TEXT, name TEXT, set_name TEXT, "
        "number TEXT, total TEXT, rarity TEXT, language TEXT, image TEXT, "
        "ref_id TEXT, updated_at REAL)")
    store._conn.execute(  # noqa: SLF001
        "CREATE TABLE IF NOT EXISTS card_prices ("
        "card_key TEXT NOT NULL, grade TEXT NOT NULL, value_eur REAL, "
        "source TEXT, source_label TEXT, detail TEXT, updated_at REAL, "
        "PRIMARY KEY (card_key, grade))")
    store._conn.commit()  # noqa: SLF001


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def card_passt_zu_info(card: dict | None, card_info: dict | None) -> bool:
    """Ob ein Karten-DB-Treffer zur Identifikation passt (Nummer / Set-Größe).

    Ein alter Fehl-Match (z. B. deutsches Fatale-Flammen-#013 statt japanisch
    Mega-Dream-#223) darf den globalen card_key nicht vergiften — sonst zeigen
    zwei gleiche Stücke verschiedene Preise, obwohl der Katalog geteilt ist.
    Ohne card_info gibt es nichts zum Widersprechen → True.
    Ohne card → False (kein Treffer zum Nutzen).
    """
    if not card:
        return False
    if not card_info:
        return True
    info_num = str(card_info.get("number") or "").lstrip("0")
    card_num = str(card.get("number") or "").lstrip("0")
    if info_num and card_num and info_num != card_num:
        return False
    info_total = str(card_info.get("set_total") or "").lstrip("0")
    card_total = str(card.get("total") or "").lstrip("0")
    if info_total and card_total and info_total != card_total:
        return False
    return True


def card_key_of(card: dict, solo_id: str | None = None) -> str:
    """Stabile globale Identität: Referenz-ID der Quell-Datenbank, sonst
    Inhalts-Hash über Name/Nummer/Set/Sprache/Auflage. Auch Sealed und
    Exoten bekommen so einen teilbaren Schlüssel.

    DETERMINISTISCH — dieselbe Karte ergibt immer denselben Schlüssel. Bis
    zum 03.08. stand hier uuid4: jeder Aufruf ohne Karten-DB-Treffer erzeugte
    eine frische Wegwerf-Identität, 239 von 247 Katalogzeilen waren
    unteilbarer Müll und jede Preisabfrage wurde je Stück neu bezahlt.

    Ohne jede Identität (kein ref_id, kein Name) gibt es weiter KEINEN
    geteilten Schlüssel — sonst kollidierten unidentifizierte Stücke auf
    einer Zeile. Der Solo-Schlüssel ist jetzt aber an die Stück-ID gebunden
    und damit über Aufrufe hinweg stabil.
    """
    game = card.get("game") or "x"
    if card.get("ref_id"):
        return f"{game}:{card['ref_id']}"
    if not card.get("name"):
        return "solo:" + (solo_id or "unbekannt")
    base = _norm("|".join([game] + [str(card.get(k) or "") for k in
                                    ("name", "number", "set_name", "language", "edition")]))
    return "h:" + hashlib.sha1(base.encode()).hexdigest()[:16]


def upsert_card(store, card: dict, solo_id: str | None = None) -> str:
    ensure_tables(store)
    key = card_key_of(card, solo_id=solo_id)
    if key.startswith("solo:"):
        # Wegwerf-Identitäten gehören nicht ins globale Register
        return key
    store._conn.execute(  # noqa: SLF001
        "INSERT INTO cards (card_key, game, name, set_name, number, total, rarity, "
        "language, image, ref_id, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(card_key) DO UPDATE SET "
        "name=COALESCE(excluded.name, name), set_name=COALESCE(excluded.set_name, set_name), "
        "image=COALESCE(excluded.image, image), rarity=COALESCE(excluded.rarity, rarity), "
        "updated_at=excluded.updated_at",
        (key, card.get("game"), card.get("name"), card.get("set_name"),
         str(card.get("number") or "") or None, str(card.get("total") or "") or None,
         card.get("rarity"), card.get("language"), card.get("image"),
         str(card.get("ref_id") or "") or None, time.time()))
    store._conn.commit()  # noqa: SLF001
    return key


def grade_bucket(graded: dict | None) -> str:
    """Delegiert an den Grader-Kanon (Stufe 3): „BECKETT 9.0" und „BGS 9"
    landen in DERSELBEN Katalogzeile — vorher waren es zwei Preise für
    denselben Slab."""
    from web.slab import bucket
    return bucket(graded)


def get_price(store, card_key: str, grade: str) -> dict | None:
    ensure_tables(store)
    row = store._conn.execute(  # noqa: SLF001
        "SELECT * FROM card_prices WHERE card_key = ? AND grade = ?",
        (card_key, grade)).fetchone()
    if not row:
        return None
    out = dict(row)
    try:
        out["detail"] = json.loads(out["detail"]) if out["detail"] else {}
    except (TypeError, ValueError):
        out["detail"] = {}
    return out


def override_price(store, card_key: str, grade: str, value: float,
                   source: str, label: str, detail_patch: dict | None = None) -> None:
    """Wächter-Korrektur in die GETEILTE Katalogzeile zurückschreiben.

    Bis Stufe 4 korrigierte der Wächter in app_api nur das Item — die
    Katalogzeile blieb vergiftet und servierte den Fehlwert jedem weiteren
    Nutzer bis zum TTL-Ablauf. Jetzt wird die Zeile mitkorrigiert und die
    Entgiftung im Detail festgehalten."""
    ensure_tables(store)
    row = get_price(store, card_key, grade)
    detail = dict((row or {}).get("detail") or {})
    detail.update(detail_patch or {})
    detail["poisoned_cleared"] = True
    store._conn.execute(  # noqa: SLF001
        "INSERT INTO card_prices (card_key, grade, value_eur, source, source_label, "
        "detail, updated_at) VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(card_key, grade) DO UPDATE SET value_eur=excluded.value_eur, "
        "source=excluded.source, source_label=excluded.source_label, "
        "detail=excluded.detail, updated_at=excluded.updated_at",
        (card_key, grade, value, source, label, json.dumps(detail), time.time()))
    store._conn.commit()  # noqa: SLF001


async def refresh_price(store, card_key: str, grade: str, query: str,
                        graded: dict | None, usd_rate: float | None,
                        base: dict | None = None, force: bool = False,
                        eu_probe=None, domain: str | None = None) -> dict | None:
    """Katalog-Preis holen; extern nur bei Force oder abgelaufenem TTL.
    Kette: echte eBay-Verkäufe > PriceCharting > Basis (Karten-DB des Aufrufers).
    base = {"value","source","label","detail"} als Fallback-Eintrag."""
    ensure_tables(store)
    row = get_price(store, card_key, grade)
    # Katalogzeilen aus der abgeschafften KI-Schätzung sind tot (Audit P0.2):
    # weder als Cache-Treffer zurückgeben noch als Fallback behalten — die
    # Karte wird komplett neu bewertet.
    if row and row.get("source") == "estimate":
        row = None
    # Selbstheilung: Werte OHNE echte Verkaufs-Belege (PC/Basis, z. B. während
    # einer Drossel-Pause entstanden) gelten nur 1 h — dann wird automatisch
    # erneut nach echten Verkäufen gesucht, bis welche da sind.
    src_now = row.get("source") if row else None
    ttl = PRICE_TTL if src_now == "ebay_sold" else (6 * 3600 if src_now in ("ebay_eu", "pricecharting") else 3600)
    if row and not force and time.time() - (row.get("updated_at") or 0) < ttl:
        return row
    # Grader+Grade gehören IMMER in die Verkaufs-Suche (PSA 9 ≠ CGC 9!)
    # CGC Pristine/Perfect mitführen — sonst mischen die Belege Gem-Mint-10er.
    if graded and graded.get("grade"):
        from web.slab import search_grade_tag
        gtag = search_grade_tag(graded)
        if gtag and gtag.split()[0].lower() not in (query or "").lower():
            query = f"{query} {gtag}"
        elif gtag:
            low = (query or "").lower()
            for w in ("pristine", "perfect", "black label"):
                if w in gtag.lower() and w not in low:
                    query = f"{query} {gtag}"
                    break
    import asyncio as _aio
    from web.pricecharting import lookup_pc
    from web.sold import fetch_sold
    _res = await _aio.gather(fetch_sold(store, query, usd_rate),
                             lookup_pc(store, query, graded, usd_rate, domain=domain),
                             return_exceptions=True)
    sold = _res[0] if not isinstance(_res[0], BaseException) else None
    pc = _res[1] if not isinstance(_res[1], BaseException) else None
    for _i, _r in enumerate(_res):
        if isinstance(_r, BaseException):
            log.warning("catalog: Quelle %d fehlgeschlagen für %s: %s", _i, card_key, _r)

    # EU-Markt (Svens Regional-Logik): offizieller eBay-Browse-Median der
    # deutschen Angebote (Grader-getrennt via Query), konservativ −12 % —
    # skaliert mit eigenen API-Keys, kein Gratis-Dienst nötig.
    eu = None
    if eu_probe:
        try:
            res = await eu_probe(query)
            # Messung 03.08. an Svens Stücken: unter ~5 Angeboten ist der
            # Median Zufall, kein Markt (1 GTA-Angebot zu 380 € gegen 98 €
            # real; 2 Mega-Charizard-Angebote mit Spanne 180–2.339 €).
            _min = 4 if grade != "raw" else 5
            if res and res.get("median") and not res.get("estimated") and (res.get("count") or 0) >= _min:
                eu = round(res["median"] * 0.88, 2)
        except Exception as e:  # noqa: BLE001
            log.warning("catalog: EU-Probe fehlgeschlagen für %s: %s", card_key, e)

    # PC-Relevanz-Prüfung: ein Fuzzy-Suchtreffer ist kein Beweis. Die Hard-Tokens
    # der Anfrage (Kartennummer/Code/Grade) müssen im PC-Produktnamen vorkommen.
    pc_trusted = False
    if pc:
        pcname = _norm(f"{(pc.get('detail') or {}).get('pc_product', '')} "
                       f"{(pc.get('detail') or {}).get('pc_console', '')}")
        gtoks = set()
        if graded and graded.get("grade"):
            g = str(graded["grade"]).replace(",", ".")
            gtoks = {_norm(g), _norm(g).replace(" ", ""), g.replace(".", " ").strip()}
            gtoks |= {t for x in gtoks for t in x.split()}
        # Set-Größen („199/165" → 165) führt PC nie im Namen — nicht verlangen
        denoms = {m.group(2) for m in re.finditer(r"(\d+)\s*/\s*(\d+)", query or "")}
        qhard = [t for t in _norm(query).split()
                 if any(c.isdigit() for c in t) and len(t) > 1
                 and t not in gtoks and t not in denoms]
        # Plattform-Synonyme (PC schreibt „Playstation 2", Verkäufer „PS2")
        SYN = {"ps1": "playstation", "ps2": "playstation 2", "ps3": "playstation 3",
               "ps4": "playstation 4", "ps5": "playstation 5", "n64": "nintendo 64",
               "gba": "game boy advance", "gb": "game boy", "sv": "scarlet violet"}
        def _hit(tok: str) -> bool:
            return tok in pcname or (tok in SYN and SYN[tok] in pcname)
        pc_trusted = bool(qhard) and all(_hit(h) for h in qhard)
        if not pc_trusted:
            log.info("catalog: PC-Treffer %r nicht belegt für %r — nur als Rückfall",
                     (pc.get("detail") or {}).get("pc_product"), query)

    # ── Anker (Stufe 4): jeder Wächter braucht eine Referenz — auch beim
    # Slab. Erste Wahl ist die Basis des Aufrufers, zweite die raw-Zeile
    # DERSELBEN Karte (ein Slab ist nie billiger als grob das Rohexemplar).
    anker = base if (base and base.get("value")
                     and str(base.get("source") or "") != "estimate") else None
    if anker is None and grade != "raw":
        r_raw = get_price(store, card_key, "raw")
        if r_raw and r_raw.get("value_eur") and r_raw.get("source") != "estimate":
            anker = {"value": r_raw["value_eur"], "source": r_raw["source"],
                     "label": r_raw["source_label"], "detail": {}}

    # Roh-Karten-Datenbanken (Cardmarket & Co.) bepreisen UNGEGRADETE Ware —
    # als Kaskaden-Basis für einen Slab sind sie tabu. Werte aus der
    # abgeschafften KI-Schätzung (source=estimate) sind ÜBERALL tabu
    # (Audit P0.2, ADR-002): sie dürfen weder als Basis dienen noch je
    # wieder in die geteilte Katalogzeile geschrieben werden.
    _ROH_QUELLEN = ("cardmarket", "tcgplayer", "tcgdex", "scryfall",
                    "ygoprodeck", "pokemontcg", "tcgcsv")
    base_erlaubt = bool(base and base.get("value") is not None
                        and str(base.get("source") or "").lower() != "estimate"
                        and (grade == "raw"
                             or str(base.get("source") or "").lower() not in _ROH_QUELLEN))

    detail: dict = {}
    if sold:
        detail["sold"] = sold
    if pc:
        detail["pc"] = pc["detail"]
        detail["value_us"] = pc["value"]
    if eu:
        detail["value_eu"] = eu
    if sold:
        value, source = sold["avg3"], "ebay_sold"
        # „stale" heißt: es gab keine zwei Verkäufe der letzten 90 Tage, die
        # Belege sind älter. Das muss dranstehen — die Zahl ist belegt, aber
        # nicht taufrisch (typisch bei seltenen Sammlerstücken).
        label = (f"Ø letzte {sold['n_avg']} eBay-Verkäufe (älter als 90 Tage)"
                 if sold.get("stale") else f"Ø letzte {sold['n_avg']} eBay-Verkäufe")
        # Frischen Katalogeintrag nicht durch eine schlechtere/ältere Abfrage
        # überschreiben (zwei Formulierungen derselben Karte, Charizard 07.08.).
        if (sold.get("stale") and row and row.get("source") == "ebay_sold"
                and row.get("value_eur") is not None
                and not ((row.get("detail") or {}).get("sold") or {}).get("stale")):
            log.info("catalog: frische Belege für %s %s behalten — neue Suche nur alt",
                     card_key, grade)
            return row
    elif eu and not (pc and pc_trusted and eu > pc["value"] * 4):
        value, source = eu, "ebay_eu"
        label = f"eBay-DE-Markt ({grade})" if grade != "raw" else "eBay-DE-Markt"
    elif pc and pc_trusted:
        value, source, label = pc["value"], pc["source"], pc["source_label"]
    elif base_erlaubt:
        value, source, label = base["value"], base["source"], base["label"]
        detail["extra"] = base.get("detail") or {}
    elif pc:
        # Unbelegter Treffer nur als letzter Rückfall — ehrlich markiert,
        # damit die App ihn als unsicher anzeigen kann.
        value, source = pc["value"], "pricecharting_weak"
        label = "PriceCharting (Zuordnung unsicher)"
    elif row and row.get("source") != "estimate":
        return row   # nichts Neues — alte Katalog-Zeile ist besser als gar keine
    else:
        return None

    # ── Wächter T3 (Stufe 4): Verkaufs-Ausreißer. Der alte Auslöser
    # n_avg < 2 war praktisch tot (fetch_sold liefert fast immer ≥2 Belege).
    # Neu zählt auch die STREUUNG: drei Belege, die um mehr als das
    # Sechsfache auseinanderliegen, sind ein Fehl-Match-Gemisch, kein Markt.
    if source == "ebay_sold" and value is not None:
        n_avg = (sold or {}).get("n_avg", 0)
        preise = [s.get("price_eur") for s in (sold or {}).get("sales", [])
                  if s.get("price_eur")][:max(n_avg, 1)]
        streuung = (max(preise) / min(preise)) if len(preise) >= 2 and min(preise) > 0 else 1.0
        wackelig = n_avg < 2 or (n_avg < 4 and streuung > 6)
        if wackelig:
            ref = (((pc or {}).get("value") if pc_trusted else None)
                   or (anker or {}).get("value")
                   or (row or {}).get("value_eur"))
            if ref and ref > 0 and (value > ref * 6 or value < ref / 6):
                detail["outlier_sold"] = value
                detail["streuung"] = round(streuung, 1)
                if pc:
                    value, source = pc["value"], pc["source"]
                    label = pc["source_label"] + " · Verkaufs-Treffer unplausibel"
                elif row and row.get("value_eur"):
                    value, source = row["value_eur"], row["source"]
                    label = (row.get("source_label") or "") + " · neuer Verkaufspreis unplausibel"
                elif anker and anker.get("source"):
                    value, source = anker["value"], anker["source"]
                    label = (anker.get("label") or "Marktwert") + " · Verkaufs-Treffer unplausibel"
                log.warning("catalog: Ausreißer bei %s %s — sold %.2f vs. Referenz %.2f (Streuung %.1f)",
                            card_key, grade, detail["outlier_sold"], ref, streuung)

    # ── Wächter T1 (Stufe 4): Anker-Korridor für ANGEBOTS- und
    # Katalog-Quellen (E4/E5). Was um mehr als das Vierfache neben dem Anker
    # liegt, ist fast immer ein anderes Produkt — echte Verkäufe (E2) dürfen
    # den Anker dagegen schlagen, der Markt hat Recht. Svens Manga Band 103
    # bekam 603 € aus genau so einem Fehl-Match.
    if (source in ("ebay_eu", "pricecharting", "pricecharting_weak")
            and value is not None and anker and (anker.get("value") or 0) > 0):
        ref = anker["value"]
        if value > ref * 4 or value < ref / 4:
            schluessel = "verworfen_pc" if source.startswith("pricecharting") else "verworfen_anker"
            detail[schluessel] = {"wert": value,
                                  "treffer": ((pc or {}).get("detail") or {}).get("pc_product")}
            log.warning("catalog: %s-Wert %.2f verletzt Anker %.2f bei %s %s — verworfen",
                        source, value, ref, card_key, grade)
            if not anker.get("source"):
                return row or None   # keine belastbare Referenzquelle -> lieber alter Stand
            value, source = ref, anker["source"]
            label = anker.get("label") or "Marktwert"

    # ── price_state (Stufe 5): der ehrliche Anzeigezustand. est_value bleibt
    # IMMER gesetzt (die 307,90-€-Lehre vom 02.08. — ohne Zahl recherchiert
    # die Listing-Pipeline blind neu). Die Ehrlichkeit wohnt im Zustand:
    # belegt = echte Verkäufe oder lizenzierter Katalog · spanne = Richtwert
    # aus Angeboten oder alten Belegen · unbekannt = bester Rückfall.
    if source == "ebay_sold":
        zustand = ("spanne", "BELEGE_ALT") if (sold or {}).get("stale") else ("belegt", None)
    elif source in ("cardmarket", "tcgplayer", "pricecharting"):
        zustand = ("belegt", None)
    elif source == "ebay_eu":
        zustand = ("spanne", "NUR_ANGEBOTE")
    elif source == "pricecharting_weak":
        zustand = ("unbekannt", "UNBEKANNT_ZUORDNUNG")
    elif "verworfen_pc" in detail or "verworfen_anker" in detail or "outlier_sold" in detail:
        zustand = ("unbekannt", "UNBEKANNT_WIDERSPRUCH")
    else:
        zustand = ("unbekannt", "UNBEKANNT_KEINE_BELEGE")
    detail["price_state"], detail["price_reason"] = zustand

    store._conn.execute(  # noqa: SLF001
        "INSERT INTO card_prices (card_key, grade, value_eur, source, source_label, "
        "detail, updated_at) VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(card_key, grade) DO UPDATE SET value_eur=excluded.value_eur, "
        "source=excluded.source, source_label=excluded.source_label, "
        "detail=excluded.detail, updated_at=excluded.updated_at",
        (card_key, grade, value, source, label, json.dumps(detail), time.time()))
    store._conn.commit()  # noqa: SLF001
    return get_price(store, card_key, grade)
