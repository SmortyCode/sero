#!/usr/bin/env python3
"""Apify-Prüfstand: Taugt der eBay-Sold-Actor als Ersatz für 130point?

Fährt Svens ECHTE Stücke gegen beide Quellen und stellt sie nebeneinander.
Beantwortet die Frage vor dem Kauf: erkennt Apify dieselben Stücke, findet es
mehr oder weniger Belege, und kommen plausible Preise heraus?

Die Datenbank wird ausschließlich LESEND geöffnet (mode=ro). Das Skript
schreibt nichts in die App zurück — es ist ein Messgerät, kein Umbau.

Aufruf:
    ./.venv/bin/python tools/apify_probe.py                 # alle Stücke, ebay.de
    ./.venv/bin/python tools/apify_probe.py --site both     # ebay.de UND ebay.com
    ./.venv/bin/python tools/apify_probe.py --limit 3       # nur die ersten drei
    ./.venv/bin/python tools/apify_probe.py --count 20      # Belege je Abfrage
    ./.venv/bin/python tools/apify_probe.py --no-130point   # nur Apify

Kosten: Abgerechnet wird PRO BELEG, nicht pro Abfrage. --count 20 bei 13
Stücken und beiden Marktplätzen sind höchstens 520 Belege, im Gratis-Tarif
also rund 2,08 USD. Das Skript rechnet vorher vor und fragt nach.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import statistics
import sys
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

ACTOR = "caffein.dev~ebay-sold-listings"
PREIS_JE_BELEG = 0.004          # Gratis-Tarif; Gold und höher zahlt 0,0025
START_KOSTEN = 0.00005


class SpeicherStore:
    """Wegwerf-Cache für fetch_sold.

    Der echte Store würde die Treffer in Svens Live-Datenbank schreiben. Ein
    Messgerät darf die Messumgebung nicht verändern — also bekommt 130point
    hier einen eigenen, flüchtigen Zwischenspeicher.
    """

    def __init__(self):
        self._kv: dict = {}

    def kv_get(self, key: str):
        return self._kv.get(key)

    def kv_set(self, key: str, wert) -> None:
        self._kv[key] = wert


def token_holen() -> str:
    t = os.environ.get("APIFY_TOKEN")
    if t:
        return t.strip()
    env = WURZEL / ".env"
    if env.exists():
        for zeile in env.read_text().splitlines():
            if zeile.startswith("APIFY_TOKEN="):
                return zeile.split("=", 1)[1].strip().strip('"').strip("'")
    print(
        "\nKein APIFY_TOKEN gefunden.\n\n"
        "So kommst du dran (dauert zwei Minuten):\n"
        "  1. Auf apify.com registrieren — das musst du selbst machen,\n"
        "     ich lege keine Konten für dich an.\n"
        "  2. In der Konsole: Settings → API & Integrations → Personal API token\n"
        "  3. Den Token hier eintragen:\n"
        f"     echo 'APIFY_TOKEN=apify_api_...' >> {WURZEL}/.env\n\n"
        "Der Gratis-Tarif enthält monatlich 5 USD Guthaben. Dieser Prüflauf\n"
        "kostet je nach Umfang etwa 1 bis 2 USD, passt also hinein.\n",
        file=sys.stderr)
    sys.exit(2)


def stuecke_lesen(limit: int | None) -> list[dict]:
    """Svens echte Stücke — nur lesend, mit Suchanfrage und bisherigem Wert."""
    db = WURZEL / "data.db"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    raus = []
    for r in con.execute("SELECT id, data FROM collection_items ORDER BY created_at DESC"):
        d = json.loads(r["data"])
        if not d.get("name"):
            continue
        analyse = d.get("analysis") or {}
        raus.append({
            "id": r["id"],
            "name": d["name"],
            "query": analyse.get("search_query_for_pricing") or d["name"],
            "graded": d.get("graded"),
            "wert_bisher": d.get("est_value"),
            "quelle_bisher": d.get("price_source"),
        })
    con.close()
    return raus[:limit] if limit else raus


async def apify_fragen(client, token: str, query: str, site: str, count: int,
                       tage: int) -> tuple[list[dict], str | None]:
    """Einen Lauf starten und auf das Ergebnis warten (synchroner Endpunkt)."""
    url = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"
    try:
        r = await client.post(
            url,
            params={"token": token, "timeout": 180},
            json={"keywords": [query], "ebaySite": site, "count": count,
                  "daysToScrape": tage, "includeCompletedListings": False,
                  "sortOrder": "endedRecently"},
            timeout=210.0)
    except Exception as e:  # noqa: BLE001
        return [], f"{type(e).__name__}: {e}"
    if r.status_code >= 400:
        return [], f"HTTP {r.status_code}: {r.text[:200]}"
    try:
        return r.json(), None
    except ValueError:
        return [], f"Antwort war kein JSON: {r.text[:200]}"


def preis_aus(beleg: dict) -> float | None:
    """Der Actor benennt das Preisfeld je nach Version unterschiedlich.

    Das Parsen selbst übernimmt bot.main.parse_price — die Funktion kennt den
    Unterschied zwischen deutschem „1.234,56" und englischem „1,234.56". Ein
    zweiter, selbstgebauter Parser hätte hier genau den Faktor-1000-Fehler
    wiederholt, gegen den parse_price geschrieben wurde.
    """
    from bot.main import parse_price

    for feld in ("soldPrice", "price", "totalPrice", "priceValue", "sold_price",
                 "priceWithShipping", "currentPrice"):
        v = beleg.get(feld)
        if isinstance(v, dict):
            v = v.get("value") or v.get("amount") or v.get("raw")
        if v is None:
            continue
        roh = str(v)
        for waehrung in ("USD", "EUR", "GBP", "$", "£"):
            roh = roh.replace(waehrung, "")
        p = parse_price(roh)
        if p:
            return float(p)
    return None


def titel_aus(beleg: dict) -> str:
    for feld in ("title", "name", "itemTitle", "listingTitle"):
        if beleg.get(feld):
            return str(beleg[feld])
    return ""


async def hauptlauf(args) -> int:
    import httpx

    token = token_holen()
    stuecke = stuecke_lesen(args.limit)
    if not stuecke:
        print("Keine Stücke mit Namen in der Datenbank gefunden.", file=sys.stderr)
        return 1

    sites = ["ebay.de", "ebay.com"] if args.site == "both" else [args.site]
    max_belege = len(stuecke) * len(sites) * args.count
    kosten = max_belege * PREIS_JE_BELEG + len(stuecke) * len(sites) * START_KOSTEN

    print(f"\n{'=' * 78}")
    print(f"APIFY-PRÜFSTAND — {len(stuecke)} Stücke × {len(sites)} Marktplatz(e) "
          f"× max. {args.count} Belege")
    print(f"Zeitfenster: {args.days} Tage zurück")
    print(f"Höchstkosten: {max_belege} Belege × 0,004 USD = {kosten:.2f} USD "
          f"(Gratis-Tarif; Gold zahlt {max_belege * 0.0025:.2f} USD)")
    print(f"{'=' * 78}\n")

    if not args.yes:
        try:
            if input("Lauf starten? [j/N] ").strip().lower() not in ("j", "ja", "y"):
                print("Abgebrochen, nichts abgerechnet.")
                return 0
        except EOFError:
            print("Keine Eingabe möglich — mit --yes starten.", file=sys.stderr)
            return 2

    from web.sold import fits, fetch_sold

    cache = SpeicherStore()
    zeilen = []
    async with httpx.AsyncClient() as client:
        for i, s in enumerate(stuecke, 1):
            print(f"[{i}/{len(stuecke)}] {s['name'][:64]}")
            print(f"          Anfrage: {s['query'][:64]}")
            zeile = {"stueck": s, "apify": {}, "p130": None}

            for site in sites:
                t0 = time.time()
                belege, fehler = await apify_fragen(client, token, s["query"],
                                                    site, args.count, args.days)
                dauer = time.time() - t0
                if fehler:
                    print(f"          {site:9} FEHLER: {fehler[:80]}")
                    zeile["apify"][site] = {"fehler": fehler}
                    continue

                # Durch Svens vorhandenen Relevanz-Filter schicken: nur so ist
                # der Vergleich mit 130point ehrlich.
                passend = [b for b in belege if fits(s["query"], titel_aus(b))]
                preise = [p for p in (preis_aus(b) for b in passend) if p]
                zeile["apify"][site] = {
                    "roh": len(belege), "passend": len(passend),
                    "preise": preise, "dauer": dauer,
                    "median": statistics.median(preise) if preise else None,
                    "beispiele": [titel_aus(b)[:70] for b in belege[:3]],
                }
                med = statistics.median(preise) if preise else None
                print(f"          {site:9} {len(belege):3} roh → {len(passend):3} passend"
                      f"  Median {med if med else '—'}  ({dauer:.1f}s)")

            if not args.no_130point:
                try:
                    p130 = await fetch_sold(cache, s["query"], 1.0)
                    zeile["p130"] = p130
                    if p130:
                        print(f"          130point  {p130.get('n_avg')} Belege"
                              f"  Ø {p130.get('avg3')}")
                    else:
                        print("          130point  nichts gefunden")
                except Exception as e:  # noqa: BLE001
                    print(f"          130point  FEHLER: {type(e).__name__}: {e}")
            zeilen.append(zeile)
            print()

    bericht(zeilen, sites, args)
    ziel = WURZEL / "tools" / "apify_probe_ergebnis.json"
    ziel.write_text(json.dumps(zeilen, indent=2, ensure_ascii=False, default=str))
    print(f"Rohdaten: {ziel}")
    return 0


def bericht(zeilen: list[dict], sites: list[str], args) -> None:
    print(f"\n{'=' * 78}")
    print("ERGEBNIS")
    print(f"{'=' * 78}\n")

    kopf = f"{'Stück':<34}"
    for s in sites:
        kopf += f"{s:>13}"
    if not args.no_130point:
        kopf += f"{'130point':>11}"
    kopf += f"{'bisher':>11}"
    print(kopf)
    print("-" * len(kopf))

    treffer = {s: 0 for s in sites}
    treffer_130 = 0
    for z in zeilen:
        name = z["stueck"]["name"][:32]
        rest = f"{name:<34}"
        for s in sites:
            a = z["apify"].get(s) or {}
            if a.get("fehler"):
                rest += f"{'Fehler':>13}"
            elif a.get("passend"):
                treffer[s] += 1
                rest += f"{a['passend']:>4}×{a['median'] or 0:>8.0f}"
            else:
                rest += f"{'—':>13}"
        if not args.no_130point:
            p = z.get("p130")
            if p and p.get("n_avg"):
                treffer_130 += 1
                rest += f"{p['n_avg']:>3}×{p.get('avg3') or 0:>7.0f}"
            else:
                rest += f"{'—':>11}"
        wb = z["stueck"].get("wert_bisher")
        rest += f"{(f'{wb:.0f}' if wb else '—'):>11}"
        print(rest)

    n = len(zeilen)
    print(f"\n{'Trefferquote:':<34}", end="")
    for s in sites:
        print(f"{f'{treffer[s]}/{n}':>13}", end="")
    if not args.no_130point:
        print(f"{f'{treffer_130}/{n}':>11}", end="")
    print("\n")

    # Das eigentliche Urteil
    for s in sites:
        q = treffer[s] / n if n else 0
        if not args.no_130point:
            q130 = treffer_130 / n if n else 0
            if q > q130:
                urteil = f"BESSER als 130point (+{(q - q130) * 100:.0f} Prozentpunkte)"
            elif q == q130:
                urteil = "gleichauf mit 130point"
            else:
                urteil = f"SCHLECHTER als 130point ({(q - q130) * 100:.0f} Prozentpunkte)"
        else:
            urteil = f"{q * 100:.0f} Prozent der Stücke gefunden"
        print(f"  {s:10} {urteil}")

    echte = sum(len((z['apify'].get(s) or {}).get('preise') or [])
                for z in zeilen for s in sites)
    roh = sum((z['apify'].get(s) or {}).get('roh') or 0 for z in zeilen for s in sites)
    print(f"\n  Abgerechnete Belege: {roh} → {roh * PREIS_JE_BELEG:.2f} USD "
          f"(Gratis-Tarif), davon {echte} nach dem Filter verwertbar")
    if roh:
        print(f"  Kosten je verwertbarem Beleg: "
              f"{roh * PREIS_JE_BELEG / max(echte, 1):.4f} USD")


def main() -> int:
    p = argparse.ArgumentParser(description="Apify gegen 130point messen")
    p.add_argument("--site", default="ebay.de",
                   choices=["ebay.de", "ebay.com", "both"])
    p.add_argument("--count", type=int, default=20, help="Belege je Abfrage")
    p.add_argument("--days", type=int, default=90, help="Zeitfenster in Tagen")
    p.add_argument("--limit", type=int, help="nur die ersten N Stücke")
    p.add_argument("--no-130point", action="store_true")
    p.add_argument("--yes", action="store_true", help="ohne Rückfrage starten")
    args = p.parse_args()
    return asyncio.run(hauptlauf(args))


if __name__ == "__main__":
    sys.exit(main())
