# Handy-E2E unter dry_run (Checkliste für Sven)

Voraussetzung: `kv['dry_run']=true` (prüfen:
`sqlite3 -readonly data.db "SELECT value FROM kv WHERE key='dry_run'"`).
Kein echtes eBay-Listing — `publishOffer` entfällt.

App: `http://192.168.2.39:3000/app/` (WLAN). Hard-Reload nach Frontend-Pins.

## eBay verbinden (App, Stand 08.08. — einheitlich Verkauf + Profil)

1. **Verkauf** (Reconnect-Banner) oder **Profil → eBay** — gleiches Sheet.
2. Tippe **eBay verbinden / neu verbinden** — eBay öffnet sich im neuen Tab;
   die App bleibt offen und prüft im Hintergrund.
3. Nach Freigabe: zurück zur App, oder tippe **Verbindung prüfen**. Toast
   „eBay verbunden“.
4. Fehlt der automatische Rücksprung (häufig lokal / RuName nur HTTPS):
   Adresse aus der Browser-Zeile kopieren → **Verbindung speichern** (Paste).
5. RuName **Auth Accepted URL** sollte auf erreichbares
   `…/callback/ebay` zeigen (öffentlich HTTPS oder LAN, wie deployed).
6. Flag `ebay_fulfillment_fehlt_*` verschwindet erst nach erfolgreicher
   Orders-Abfrage, nicht schon beim Speichern des Tokens. Solange das Flag
   steht, zeigt die App weiter „Neu verbinden“ — auch wenn der Token frisch ist.

## Abnahmeliste (Stand 08.08.2026)

| Spur | Was | Status |
|---|---|---|
| **AUTOMATISIERTER E2E** | `tests/test_e2e_offline.py` — Temp-DB, Fake recognize/price/ebay, Claim, `publish_uncertain` ohne Auto-Retry, dry_run ohne publishOffer | Code grün; ersetzt kein Handy |
| **HANDY MANUELL** | Login, Scan, Marktwert, Listen bis `dry_run_done`, Tabs, Reconnect-Hinweis | Offen für Sven |
| **LISTING MANUELL** | Echtes Veröffentlichen mit `dry_run=false` | Offen — bewusst nicht in dieser Abnahme |
| **eBay Reconnect** | Scope `sell.fulfillment`, Orders ohne 403, Flag weg | **MANUELL OFFEN** — Code bereit, Live kann noch 403 sein |

## Ablauf Handy

1. **Login** — E-Mail-Code oder Magic-Link → landet in `/app/?logged_in=1`. Session bleibt.
2. **Sammlung** — Kacheln laden, ein Stück öffnen.
3. **Scan** — 1–2 Fotos (CGC-Slab oder Rohkarte). Warten bis Status `ready`.
4. **Marktwert** — belegt oder „Wert unbekannt"; keine Fantasiezahl.
5. **Listen** — Entwurf erzeugen, Upload starten. Erwartung: Status
   `dry_run_done` (Inventar/Offer bei eBay möglich, aber unveröffentlicht).
6. **Profil / Verkauf** — wenn „eBay neu verbinden" (orange): Button tippen
   → Consent mit `sell.fulfillment` → zurück `/app/?ebay=ok`. Flag verschwindet
   erst, wenn Orders-API wirklich klappt (nicht schon beim Token-Speichern).
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
# Sales-Sync-Flag (nach Sven-Reconnect + erfolgreichen Orders leer/weg):
sqlite3 -readonly data.db "SELECT key FROM kv WHERE key LIKE 'ebay_fulfillment_fehlt_%'"
```

## Offline-E2E (automatisch)

```
NUMBA_DISABLE_JIT=1 ./.venv/bin/python -m pytest tests/test_e2e_offline.py -q
```


## Mobile-Stabilität (Checkliste echtes iPhone)

Nach Hard-Reload (`sero.css?v=82`, `sero.js?v=136`, `sero-mobile.js?v=1`):

1. Sammlung: Filter-Chips horizontal wischen — Tab darf nicht wechseln.
2. Freier Hintergrund horizontal wischen — genau ein Tab-Wechsel.
3. Langes Options-Sheet (z. B. viele Filter): Inhalt und „Fertig“ erreichbar.
4. Suche öffnen, Tastatur: Feld und Aktionen bleiben sichtbar; nach Schließen kein Leerraum.
5. Scan → „Weiteres Foto“: Kamera/Galerie öffnet sofort.
6. Sammlung mit vielen Stücken: flüssiges Nachladen beim Scrollen.
7. Reduced Motion (System): weniger Blur/Holo, Bedienung unverändert.

WebKit-Fotowähler-Speicher (Bug 318572): beobachten, nicht „reparieren“.
