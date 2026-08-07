# Handy-E2E unter dry_run (Checkliste für Sven)

Voraussetzung: `kv['dry_run']=true` (prüfen:
`sqlite3 -readonly data.db "SELECT value FROM kv WHERE key='dry_run'"`).
Kein echtes eBay-Listing — `publishOffer` entfällt.

App: `http://192.168.2.39:3000/app/` (WLAN).

## Ablauf

1. **Login** — E-Mail-Code, Session bleibt.
2. **Sammlung** — Kacheln laden, ein Stück öffnen.
3. **Scan** — 1–2 Fotos (CGC-Slab oder Rohkarte). Warten bis Status `ready`.
4. **Marktwert** — belegt oder „Wert unbekannt“; keine Fantasiezahl.
5. **Listen** — Entwurf erzeugen, Upload starten. Erwartung: Status
   `dry_run_done` (Inventar/Offer bei eBay möglich, aber unveröffentlicht).
6. **Profil / Verkauf** — wenn „Neu verbinden“ (orange) oder Hinweis unter
   Verkauf: Website → Mit eBay verbinden (holt `sell.fulfillment` für
   Sales-Sync). Danach Flag verschwindet.
7. **Nicht** `/dryrun off`, solange geübt wird.

## API-Smoke ohne Handy (lokal)

```
sh tests/smoke.sh
curl -s -o /dev/null -w '%{http_code}\n' localhost:3000/app/               # 200
curl -s -o /dev/null -w '%{http_code}\n' localhost:3000/api/app/collection # 401
curl -s -o /dev/null -w '%{http_code}\n' localhost:3000/api/app/sales      # 401
curl -s -o /dev/null -w '%{http_code}\n' localhost:3000/api/me             # 401
# dry_run muss true bleiben, solange geübt wird:
sqlite3 -readonly data.db "SELECT value FROM kv WHERE key='dry_run'"       # true
# Sales-Sync-Flag (nach Sven-Reconnect leer/weg):
sqlite3 -readonly data.db "SELECT key FROM kv WHERE key LIKE 'ebay_fulfillment_fehlt_%'"
```
