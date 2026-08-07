#!/usr/bin/env python3
"""Messung: Taugt der GÜNSTIGSTE aktive eBay-Preis als Marktwert?

Svens Vorschlag (03.08.): statt echter Verkäufe einfach das nehmen, was gerade
am Markt ist — und zwar den günstigsten Preis. Diese Messung prüft an seinen
echten Stücken, was das für Zahlen ergibt und wie weit sie vom Median und vom
bisher gezeigten Wert abweichen.

Die Frage dahinter ist nicht „geht das technisch" (es geht, der Code steht),
sondern „wie gut ist die Zahl". Der günstigste Treffer ist bei Sammlerware
häufig ein beschädigtes Exemplar, ein Fehl-Match oder eine andere Auflage.

Nur lesend, verändert nichts.

    ./.venv/bin/python tools/browse_probe.py
    ./.venv/bin/python tools/browse_probe.py --limit 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import statistics
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))


def stuecke_lesen(limit: int | None) -> list[dict]:
    con = sqlite3.connect(f"file:{WURZEL / 'data.db'}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    raus = []
    for r in con.execute("SELECT id, data FROM collection_items ORDER BY created_at DESC"):
        d = json.loads(r["data"])
        if not d.get("name"):
            continue
        raus.append({
            "name": d["name"],
            "query": (d.get("analysis") or {}).get("search_query_for_pricing") or d["name"],
            "wert": d.get("est_value"),
            "quelle": d.get("price_source"),
        })
    con.close()
    return raus[:limit] if limit else raus


async def hauptlauf(args) -> int:
    from bot.config import load_config
    from bot.ebay.auth import EbayClient
    from bot.ebay.browse import research_price
    from bot.drafts import Store

    cfg = load_config()
    store = Store(WURZEL / "data.db")
    ebay = EbayClient(cfg, store)

    stuecke = stuecke_lesen(args.limit)
    print(f"\n{'=' * 96}")
    print("AKTIVE EBAY-ANGEBOTE — was liefert die Browse-API für Svens Stücke?")
    print(f"{'=' * 96}\n")

    zeilen = []
    for i, s in enumerate(stuecke, 1):
        print(f"[{i}/{len(stuecke)}] {s['name'][:70]}")
        try:
            res = await research_price(ebay, s["query"], limit=50)
        except Exception as e:  # noqa: BLE001
            print(f"          FEHLER: {type(e).__name__}: {e}\n")
            continue
        if not res:
            print("          keine aktiven Angebote gefunden\n")
            zeilen.append({"s": s, "res": None})
            continue

        proben = res.get("samples") or []
        preise = sorted(p["price"] for p in proben) if proben else []
        guenstigster = res.get("min")
        median = res.get("median")
        print(f"          {res.get('count')} Angebote | günstigster {guenstigster} | "
              f"Median {median} | teuerster {res.get('max')}")
        for p in proben[:3]:
            print(f"            {p['price']:>8.2f}  {(p.get('title') or '')[:64]}")
        if median and guenstigster:
            abstand = (1 - guenstigster / median) * 100
            print(f"          → günstigster liegt {abstand:.0f} % unter dem Median")
        print()
        zeilen.append({"s": s, "res": res, "preise": preise})

    bericht(zeilen)
    ziel = WURZEL / "tools" / "browse_probe_ergebnis.json"
    ziel.write_text(json.dumps(zeilen, indent=2, ensure_ascii=False, default=str))
    print(f"\nRohdaten: {ziel}")
    return 0


def bericht(zeilen: list[dict]) -> None:
    print(f"\n{'=' * 96}")
    print("VERGLEICH")
    print(f"{'=' * 96}\n")
    print(f"{'Stück':<38}{'Angebote':>9}{'günstigst':>11}{'Median':>10}"
          f"{'−12%':>10}{'bisher':>10}{'Quelle':>16}")
    print("-" * 96)

    abstaende = []
    for z in zeilen:
        s, res = z["s"], z.get("res")
        name = s["name"][:36]
        bisher = f"{s['wert']:.0f}" if s.get("wert") else "—"
        quelle = (s.get("quelle") or "—")[:15]
        if not res:
            print(f"{name:<38}{'—':>9}{'—':>11}{'—':>10}{'—':>10}{bisher:>10}{quelle:>16}")
            continue
        g, m = res.get("min"), res.get("median")
        if g and m:
            abstaende.append((1 - g / m) * 100)
        minus12 = f"{m * 0.88:.0f}" if m else "—"
        print(f"{name:<38}{res.get('count', 0):>9}{g or 0:>11.0f}{m or 0:>10.0f}"
              f"{minus12:>10}{bisher:>10}{quelle:>16}")

    if abstaende:
        print(f"\nGünstigster liegt im Schnitt {statistics.mean(abstaende):.0f} % unter dem Median "
              f"(Spanne {min(abstaende):.0f} bis {max(abstaende):.0f} %).")
        print("Je größer dieser Abstand, desto riskanter ist der günstigste Preis als "
              "Marktwert: dahinter stecken beschädigte Exemplare, Fehl-Matches "
              "und andere Auflagen.")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int)
    args = p.parse_args()
    return asyncio.run(hauptlauf(args))


if __name__ == "__main__":
    sys.exit(main())
