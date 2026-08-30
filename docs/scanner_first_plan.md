# Scanner-first — Umsetzungsplan (10.08.2026)

Ziel: `Kamera → prüfen → Entwurf → Preflight → bewusste Freigabe → Publish`.
Sammlung bleibt, ist aber kein notwendiger Umweg.
Produktversprechen laut UX-Audit: Foto → editierbarer eBay-Entwurf → Freigabe → Publish.

## Dateien

| Datei | Rolle |
|---|---|
| `frontend/index.html` | Nav-Label Listings, Login-Copy, Scanner-Hero, Scan-Button-Label |
| `frontend/sero.js` | CTA-Semantik, Kamera-Sync, Start-Hero, Tour, Review A–D, Confirm |
| `frontend/sero.css` / `sero-dark.css` | Scan-Button, Start-Hero, Listing-Review |
| `web/preflight.py` | Serverseitige Checkliste vor Publish (inkl. Aspects/Item-Gates) |
| `web/app_api.py` | preflight, aspect/cat-Actions, category-suggest, Revision, Sell-Tpl, ScanSession |
| `web/publish.py` | unverändert (Claim/Intent bleiben Source of Truth) |
| `web/scan_session.py` | P3-Start: Session-Zustände + Batch-Queue (KV) |
| `tests/test_scanner_first_guards.py` | Copy/Nav/CTA/Review-Wachen |
| `tests/test_preflight.py` | Preflight-Regeln ohne eBay |
| `docs/IMPLEMENTATION_STATUS.md` | Stand |

## Phasen

### P0 — Sicherheit + CTA ✅
- Draft öffnen ≠ Publish-Text
- Einziger Publish-Text: `Jetzt bei eBay veröffentlichen`
- Confirm-Dialog vor Upload; PublishIntent nur im bestehenden Upload-Pfad
- Kein Auto-Publish, kein echter eBay-Call in Tests

### P1 — IA / Start / Listings / Scan ✅
- Login: `Scannen. Prüfen. Bei eBay verkaufen.`
- Tab `Listings`, Segmente mit Zählern, Default Entwürfe wenn vorhanden
- Scan-Button: Label, aktiv, synchron Kamera
- Start-Hero + Scanner-Hero + Tour scanner-first
- Leerzustände → Scanner, nicht Sammlungszwang

### P2 — Review + Preflight + Gates ✅ (Kern)
- `preflight_draft()` mit issues-Checkliste + section-Sprungzielen
- Upload blockiert bei offenen Issues (uncertain/analyzing/needs_review/kein Preis/Aspects)
- Confirm zeigt Zusammenfassung; Preflight-UI mit Sprunglinks
- Review A–D in einem Screen: Bilder, Produkt (Identität/Kategorie/Zustand/Pflichtmerkmale), Angebot, Versand & Regeln
- Manuelle Kartensuche erreichbar (Sammlung + Review); Korrektur invalidiert Preisquery/Kategorie/Aspects
- Portfolio/KI/Asking nie automatisch als Listenpreis (`listingTippFromItem`)
- FIXED_PRICE + auction1 serverseitig blockiert

### P3 — ScanSession / Batch / Revision (Kern 10.08. Audit)
- ✅ Draft-Revision + If-Match 409
- ✅ Sell-Template serverseitig (`/sell-template`)
- ✅ ScanSession-Zustände + Batch-Queue-KV (`/scan-session`)
- ✅ Persistente Scan-Warteschlange in Listings (Bereit / Prüfung nötig / Kein Preis / Fehler)
- ✅ Batch: Preview → editierbare Gruppen (teilen/zusammenführen/Hauptbild) → Confirm → Queue
- ✅ Selektiver Bulk-Publish: nur Häkchen, Zusammenfassung + Preflight pro Draft
- ✅ Long-Press am Scan-Button: Ein Artikel / Mehrere / Nur erfassen (iOS Gesture)
- ✅ Foto-Werkzeuge im Review: Strip + Reihenfolge/Hauptbild + Menü (imgorder/imgmain)
- Offen: ScanSession-Worker (Hintergrund-Jobs jenseits Analyse-Enqueue)
- ✅ Mobile Abnahme-Screenshots: `tmp/scanner_first_shots/` (Fake-Auth/Temp-DB, DE, Light+Dark; siehe `tests/test_playwright_mobile.py` `-k shots`). Nicht abgebildet: Review C–D Scroll, Batch-/Bulk-Confirm, echte Kamera
- Pins: `sero.css?v=132`, `sero-dark.css?v=19`, `sero.js?v=195`

## Sicherheit während der Arbeit

- Kein `publishOffer` / kein Live-Enden / kein Credentials-Touch in dieser Session
- Tests nur FakeStore / FakeEbay / Quelltext-Wachen — kein Production-Publish ausgelöst
