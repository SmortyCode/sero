"""Echte eBay-VERKAUFSPREISE über 130point.com (Sold-Suche der Sammler-Szene).

eBay blockt die eigene Sold-Suche für Server (403) und gibt die Daten offiziell
nur über die zugangsbeschränkte Marketplace-Insights-API heraus. 130point
spiegelt verkaufte eBay-Angebote frei abfragbar (inkl. Titel, Preis, Währung,
Datum, Link, Bild). Bewertungsregel: Durchschnitt der letzten drei Verkäufe.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import os
import re
import time

import httpx

log = logging.getLogger("sold")

TTL = 12 * 3600
# 25 s reichten für kurze Anfragen, aber lange (viele Wörter) liefen ins
# Zeitlimit — das Ergebnis war stumm „keine Verkäufe" und eine KI-Schätzung
# statt echter Belege. Svens 3.000-€-Manga hing genau daran.
_http = httpx.AsyncClient(
    timeout=httpx.Timeout(45.0, connect=10.0), follow_redirects=True,
    headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"})

ROW = re.compile(r'<tr id="dRow".*?</tr>', re.S)

# Höflichkeits-Drossel: 130point ist ein freier Dienst und limitiert Bursts (429).
# Global max. eine Anfrage alle paar Sekunden; bei 429 einmal warten und wiederholen.
_gate = asyncio.Lock()
_last_req = 0.0
MIN_GAP = 8.0
_cooldown_until = 0.0   # nach hartem 429: 10 min Pause, statt den Bann zu verlängern


async def _post(query: str) -> httpx.Response:
    global _last_req, _cooldown_until
    if time.time() < _cooldown_until:
        raise RuntimeError("sold: Cooldown nach 429 — Abfrage übersprungen")
    async with _gate:
        wait = _last_req + MIN_GAP - time.time()
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            r = await _http.post(
                "https://back.130point.com/sales/",
                data={"query": query, "type": "2", "subcat": "-1"},
                headers={"Content-Type": "application/x-www-form-urlencoded"})
        except httpx.TimeoutException:
            # Einmal nachfassen: die Quelle ist gelegentlich träge, und ohne
            # Wiederholung fällt das Stück ohne Not auf die KI-Schätzung zurück.
            log.info("sold: Zeitüberschreitung bei %r — ein zweiter Versuch", query[:60])
            await asyncio.sleep(2)
            r = await _http.post(
                "https://back.130point.com/sales/",
                data={"query": query, "type": "2", "subcat": "-1"},
                headers={"Content-Type": "application/x-www-form-urlencoded"})
        _last_req = time.time()
    if r.status_code == 429:
        # SOFORT Cooldown und weiter — der Scan darf hier nie warten
        _cooldown_until = time.time() + 600
    return r


def _parse_rows(text: str) -> list[dict]:
    out = []
    for m in ROW.finditer(text):
        r = m.group(0)
        price = re.search(r'data-price="([\d.]+)"', r)
        cur = re.search(r'data-currency="([A-Z]{3})"', r)
        title = (re.search(r"titleText['\"]?[^>]*>([^<]{5,})", r)
                 or re.search(r">([^<>]{25,140})</", r))
        date = re.search(r"Date:</b>\s*\w+\s+(\d+\s+\w+\s+\d{4})", r)
        url = re.search(r"href='(https://www\.ebay\.[^']+)'", r)
        img = re.search(r"src='(https://i\.ebayimg[^']+)'", r)
        if not (price and cur):
            continue
        try:
            out.append({
                "price": float(price.group(1)),
                "currency": cur.group(1),
                "title": html.unescape(title.group(1)).strip() if title else "",
                "date": date.group(1) if date else "",
                "url": url.group(1) if url else None,
                "image": img.group(1) if img else None,
            })
        except ValueError:
            continue
    return out


# ── Relevanz-Filter (Svens Regel: es MUSS derselbe Artikel sein) ────────────
# Auf Modulebene, damit er endlich testbar ist — drei belegte Fehler steckten
# jahrelang unerreichbar in einer Closure:
#   1. „199 / 165" im Titel matchte „199/165" aus der Anfrage nie (Leerzeichen).
#   2. „Ace" als KARTENNAME (One Piece!) schaltete die Grader-Logik scharf —
#      eine ungegradete Ace-Karte fand nur noch Slab-Verkäufe.
#   3. „PSA10" ohne Leerzeichen wurde weder als Grader noch als Note erkannt.
GRADERS = ("psa", "cgc", "bgs", "sgc", "beckett", "wata", "vga", "cga", "ace")
# Note: WATA und VGA vergeben 9.8, 9.6, 9.4 — nicht nur ganze und halbe Stufen.
# Die alte Regex las „WATA 9.8" als „9" und verglich damit den falschen Grad.
_GRADER_NUM = re.compile(r"\b(psa|cgc|bgs|sgc|beckett|wata|vga|cga|ace)\s*(10(?:\.0)?|\d(?:\.\d)?)\b")
# Dieselbe Firma, zwei Schreibweisen: Beckett Grading Services heißt auf eBay
# fast immer „BGS". Wer nach „Beckett 8.5" sucht, muss BGS-Slabs finden —
# sonst bleibt ein 3.000-€-Manga ohne einen einzigen Beleg (Svens Fall 03.08.).
_GRADER_GLEICH = {"beckett": "bgs", "bgs": "bgs"}


def _grader_norm(g: str) -> str:
    return _GRADER_GLEICH.get(g, g)


def _canon(s: str) -> str:
    """Schreibweisen vereinheitlichen: '199 / 165' -> '199/165', 'PSA10' -> 'psa 10'."""
    s = s.lower()
    s = re.sub(r"(?<=\d)\s*/\s*(?=\d)", "/", s)
    s = re.sub(r"\b(psa|cgc|bgs|sgc|beckett|wata|vga|cga)\s*(?=\d)", r"\1 ", s)
    return s


def _word(tok: str, tl: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])", tl) is not None


# Wörter, die in Verkaufstiteln beliebig anders stehen („1st Print" statt
# „first printing") oder gar nicht. Sie dürfen die Trefferquote nicht drücken.
_FUELLWOERTER = frozenset((
    "graded", "grade", "first", "1st", "printing", "print", "edition", "ed",
    "original", "authentic", "rare", "mint", "near", "condition", "vintage",
    "manga", "comic", "book", "vol", "volume", "band", "nr", "no", "the",
))


def kurzform(query: str) -> str:
    """Die Anfrage auf ihren Kern eindampfen: Produktname, die entscheidende
    Zahl, Grader und Note.

    „One Piece Volume 1 1997 first printing Japanese graded Beckett 8.5" findet
    bei der Verkaufsquelle NICHTS — zu viele Wörter, die kein Verkäufer so in
    den Titel schreibt. „One Piece 1 bgs 8.5" findet dieselbe Ware sofort
    (Svens Manga, Belege zwischen 1.500 und 5.000 €).
    """
    ql = _canon(query)
    tok = re.findall(r"[a-z0-9./-]+", ql)
    g = _GRADER_NUM.search(ql)
    note = g.group(2) if g else None
    grader = _grader_norm(g.group(1)) if g else None

    def jahr(t: str) -> bool:
        return t.isdigit() and len(t) == 4 and 1900 <= int(t) <= 2099

    zahlen = [t for t in tok
              if any(c.isdigit() for c in t) and not jahr(t) and t != note]
    namen = [t for t in tok
             if t.isalpha() and t not in _FUELLWOERTER and t not in GRADERS][:3]
    teile = namen + zahlen[:2]
    if grader and note:
        teile += [grader, note]
    return " ".join(teile)


def _soft_treffer(tok: str, tworte: set) -> bool:
    """Weiches Wort gilt als getroffen, wenn ein Titelwort damit beginnt —
    „vol" trifft „volume", „print" trifft „printing"."""
    if tok in tworte:
        return True
    return any(len(w) >= 3 and (w.startswith(tok) or tok.startswith(w)) for w in tworte)


def fits(query: str, title: str) -> bool:
    """Zählt dieser Verkaufs-Titel als Beleg für genau diese Karte?"""
    ql, tl = _canon(query), _canon(title)
    qtok = re.findall(r"[a-z0-9./-]+", ql)
    # Grader zählt nur MIT Note ("psa 10") — sonst ist „Ace" ein Kartenname
    qg = _GRADER_NUM.search(ql)
    qgrader = _grader_norm(qg.group(1)) if qg else None
    def ist_jahr(t: str) -> bool:
        return t.isdigit() and len(t) == 4 and 1900 <= int(t) <= 2099

    # Zahlen sind der Sicherungsstift (Kartennummer!) — aber ein Erscheinungsjahr
    # steht selten im Verkaufstitel. Es zählt deshalb als weiches Wort.
    # Zahlen sind IMMER Pflicht — auch einstellige. Bei Manga-Bänden entscheidet
    # genau sie („Vol 1" vs „Vol 2"), und ein Beleg vom falschen Band ist wertlos.
    # Einzige Ausnahme: das Erscheinungsjahr, das steht selten im Verkaufstitel.
    hard = [t for t in qtok if (any(ch.isdigit() for ch in t) and not ist_jahr(t))
            or t in ("sealed", "holo", "promo")]
    soft = [t for t in qtok if t not in hard and len(t) > 1 and t not in GRADERS]
    if not all(_word(h, tl) for h in hard):
        return False
    # GRADER-TRENNUNG (Svens Regel): PSA nur gegen PSA, CGC nur gegen CGC —
    # und ungegradete Karten NIE gegen irgendeinen Slab.
    tgraders = {_grader_norm(m.group(1)) for m in _GRADER_NUM.finditer(tl)}
    if qgrader:
        # Gleicher Grader Pflicht (Beckett==BGS bereits normalisiert). Ein Titel
        # ganz ohne Grader-Angabe zählt NICHT als Beleg für einen Slab.
        if qgrader not in tgraders:
            return False
    elif tgraders or _word("graded", tl) or _word("gem", tl):
        return False
    soft = [t for t in soft if t not in _FUELLWOERTER]
    if soft:
        tworte = set(re.findall(r"[a-z0-9./-]+", tl))
        if sum(1 for t in soft if _soft_treffer(t, tworte)) < max(1, len(soft) // 2):
            return False
    return True


async def fetch_sold(store, query: str, usd_rate: float | None) -> dict | None:
    """Letzte eBay-Verkäufe zu einer Suchanfrage. 12 h gecacht (auch Misserfolge).

    Lizenz-Schalter (Audit P0.5, ADR-002): 130point ist ein gescrapter,
    undokumentierter Endpunkt — das eBay-Nutzerabkommen verbietet das. Für den
    Einzelbetrieb des Betreibers per SERO_QUELLE_130POINT=1 bewusst aktivierbar
    (eigenes Risiko); im Code ist der Default AUS, damit ein Deploy für fremde
    Nutzer die Quelle NIE stillschweigend mitbringt."""
    if os.environ.get("SERO_QUELLE_130POINT", "0") != "1":
        return None
    query = (query or "").strip()
    if not query:
        return None
    key = "sold9_" + hashlib.sha1(query.lower().encode()).hexdigest()[:16]
    cached = store.kv_get(key)
    if cached and time.time() - cached.get("ts", 0) < TTL:
        return cached.get("v")
    result = None
    try:
        # 1) OFFIZIELLE eBay-Verkaufsdaten (sobald freigeschaltet) — Svens Regel: nur eBay
        from web.ebay_insights import insights_rows
        rows = await insights_rows(query)
        if not rows:
            r = await _post(query)
            r.raise_for_status()
            rows = _parse_rows(r.text)
        rows = [x for x in rows if (x.get("title") or "").strip() and fits(query, x["title"])]
        # Nichts gefunden? Dann war die Anfrage vermutlich zu ausführlich.
        # Ein zweiter Anlauf mit dem Kern — der Filter bleibt streng, es kommt
        # also nichts Fremdes durch, nur mehr echte Belege.
        kurz = kurzform(query)
        if not rows and kurz and kurz != _canon(query):
            log.info("sold: nichts zu %r — zweiter Anlauf mit %r", query[:50], kurz)
            r2 = await _post(kurz)
            if r2.status_code == 200:
                rows = [x for x in _parse_rows(r2.text)
                        if (x.get("title") or "").strip() and fits(kurz, x["title"])]

        # Svens 90-Tage-Regel: ältere Verkäufe werden angezeigt (markiert),
        # zählen aber NICHT in den Durchschnitt — Karten-Märkte drehen schnell.
        MON = {m: i + 1 for i, m in enumerate(
            ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
        MON.update({"mär": 3, "mai": 5, "okt": 10, "dez": 12, "jul": 7, "jun": 6})

        def _age_days(ds: str) -> float | None:
            m = re.search(r"(\d{1,2})\.?\s*([A-Za-zäöü]{3})\w*\.?\s*(\d{4})", ds or "")
            if not m:
                m2 = re.match(r"(\d{4})-(\d{2})-(\d{2})", ds or "")
                if not m2:
                    return None
                y, mo, d = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
            else:
                d, y = int(m.group(1)), int(m.group(3))
                mo = MON.get(m.group(2).lower()[:3])
                if not mo:
                    return None
            try:
                return (time.time() - time.mktime((y, mo, d, 12, 0, 0, 0, 0, -1))) / 86400
            except (ValueError, OverflowError):
                return None

        for x in rows:
            age = _age_days(x.get("date") or "")
            x["old"] = age is None or age > 90
        sales = []
        for row in rows:
            if row["currency"] == "EUR":
                eur = row["price"]
            elif row["currency"] == "USD" and usd_rate:
                eur = row["price"] * usd_rate
            else:
                continue   # exotische Währungen verzerren den Schnitt
            if eur <= 0:
                # eBay blendet manche Verkaufspreise aus — die kommen als 0,00
                # an und halbieren den Schnitt (Review-Fund: CGC-10-Slab stand
                # auf 4,33 € aus einem 8,65-€- und einem 0,00-€-„Verkauf").
                continue
            sales.append({**row, "price_eur": round(eur, 2)})
            if len(sales) >= 6:
                break
        fresh = [s for s in sales if not s.get("old")]
        if len(fresh) >= 2:
            top = fresh[:3]
            result = {
                "avg3": round(sum(s["price_eur"] for s in top) / len(top), 2),
                "n_avg": len(top),
                "sales": sales,
            }
        elif len(sales) >= 2:
            # Seltene Stücke wechseln nur ein paar Mal im Jahr den Besitzer.
            # Svens One-Piece-Band-1 (BGS 8.5) hatte acht Belege zwischen 595
            # und 5.000 € — alle älter als 90 Tage. Die Regel warf sie komplett
            # weg und die App zeigte eine KI-Schätzung von 500 € statt rund
            # 3.000 €. Belegte ältere Verkäufe sind besser als geraten; sie
            # werden als älter gekennzeichnet, damit die Zahl einordbar bleibt.
            top = sales[:3]
            result = {
                "avg3": round(sum(s["price_eur"] for s in top) / len(top), 2),
                "n_avg": len(top),
                "sales": sales,
                "stale": True,
            }
    except Exception as e:  # noqa: BLE001 — Sold-Quelle darf nie einen Scan brechen
        log.warning("sold: Abfrage fehlgeschlagen für %r: %s%s", query,
                    type(e).__name__, f" ({e})" if str(e) else "")
        return None   # Fehler NICHT cachen — nächster Versuch darf klappen
    store.kv_set(key, {"ts": time.time(), "v": result})
    return result
