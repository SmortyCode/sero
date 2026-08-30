# SERO

App für Sammler und kleine Händler von Sammelkarten, Retro-Videospielen, Manga
und Comics. Kernnutzen: **Foto machen → SERO erkennt das Stück, ermittelt den
Marktwert und macht daraus mit einem Tipp ein fertiges eBay-Listing.**

Deutschland zuerst: eBay.de, Preise in Euro, deutsche Texte.

## Aufbau

```
web/            FastAPI-Backend der App
  server.py       Anwendungs-Gerüst: Login, Sessions, Stripe, Sicherheits-Header
  app_api.py      Alle App-Endpunkte, Scan-Ablauf, Preis-Refresh, Listing-Pfad
  cardscan.py     Bildpipeline (RENDER-STANDARD: Warp pur, keine Kosmetik)
  catalog.py      Globaler Preis-Katalog mit Kaskade und Wächtern
  health.py       Gesundheitswächter — Grundlage des selbstheilenden Betriebs
  slab.py         Grader-Kanon (BGS == Beckett usw.)
bot/            Telegram-Bot + geteilte Bausteine (DB, eBay, Claude)
  drafts.py       SQLite-Zugriff (EINE Verbindung, WAL)
  ebay/           OAuth, Inventory→Offer→Publish, Altersfreigaben-Weiche
tests/          20+ Testdateien; tests/smoke.sh prüft das laufende System
docs/           IMPLEMENTATION_STATUS.md (Stand der Wahrheit) + ADRs
```

Das Frontend (Vanilla-JS-PWA, kein Framework) liegt in `frontend/` und wird unter `/app/` ausgeliefert.

## Einrichtung aus frischem Checkout

```
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env        # ausfüllen, mindestens ANTHROPIC_API_KEY
./.venv/bin/python -m uvicorn web.server:app --host 0.0.0.0 --port 3000
```

Die App läuft dann unter `http://localhost:3000/app/`.
Getestet am 07.08.2026: frisches venv + `requirements.txt` genügen.

## Betrieb (Svens Mac)

- EIN launchd-Dauerdienst `com.listo.web` auf 0.0.0.0:3000 (KeepAlive).
  Nach Python-Änderungen: `launchctl kickstart -k gui/501/com.listo.web`
- NIE eigene Server auf Port 3000 starten — die Handy-PWA hängt daran.
- Nach Frontend-Änderungen die Versions-Pins in `index.html` hochzählen.

## Tests

```
./.venv/bin/python -m pytest tests/ -q     # Unit- und Integrationstests
sh tests/smoke.sh                          # Ampel gegen das laufende System
```

Kein Test berührt echte Daten; Integrationstests laufen im Unterprozess gegen
eine Wegwerf-Datenbank. Mehrere Tests sind Quelltext-Wachen, die bewusste
Produktentscheide festschreiben (Bildpipeline ohne Kosmetik, Publish-Claim,
fail-closed-Checkout) — wer sie entfernt, öffnet einen bekannten Fehler wieder.

## Regeln, die nicht verhandelbar sind

- **Ehrliche Preise:** Marktwert aus echten Belegen, sonst „unbekannt". Nie aus
  dem Sprachmodell.
- **Nichts geht ohne Freigabe live.** `kv['dry_run']` ist **false** (Default
  für neue Installs ebenfalls false). Publish geht zu eBay und kostet echte
  Gebühren. Telegram `/dryrun` bleibt als Notfall, in der App gibt es keinen
  Testmodus.
- **Das eigene freigestellte Foto ist das Hauptbild.**
- **Bild-Standard:** Warp pur, keine selektive Nachbearbeitung (siehe
  Docstring in `web/cardscan.py` und `tests/test_render_standard.py`).
- Entwürfe mit Status `published`/`ended`/`dry_run_done` nie anfassen — daran
  hängt echtes Geld.

## Wo stehen wir?

`docs/IMPLEMENTATION_STATUS.md` ist die einzige Wahrheit über Zustand,
bekannte Lücken und nächste Schritte. Bitte dort weiterlesen, bevor du
irgendetwas umbaust.


## Lokale Prüfung

```
./.venv/bin/python -m pytest tests/ -q
node --check frontend/sero.js
sh tests/smoke.sh          # gegen laufenden com.listo.web (Port 3000)
```

Identity-Eval (opt-in, offline Manifest): `python scripts/eval_identity.py docs/eval_identity_manifest.example.json`
Live-Netz nur mit `SERO_EVAL_LIVE=1` (Fotos nicht committen).

Hinter einem Reverse-Proxy: `SERO_TRUST_PROXY=1` setzen, sonst wird `X-Forwarded-Host` ignoriert.
