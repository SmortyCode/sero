# ADR-003: Publish als Zustandsautomat mit atomarem Claim

Status: Stufe 1 umgesetzt 07.08.2026; Stufe 2 umgesetzt 08.08.2026

## Kontext

Veröffentlichen kostet echtes Geld: Ein doppeltes Listing bedeutet doppelte
Gebühren und im schlimmsten Fall zwei Verkäufe desselben Einzelstücks.
Der Upload lief als frei gespawnter asyncio-Task; ein Doppeltipp erzeugte
zwei parallele Läufe, deren `published`-Check nicht atomar war.

## Entscheidung

**Stufe 1:** Atomarer Status-Claim in SQLite
(`Store.claim_draft(..., "publishing", verboten=(…))`). Genau ein Gewinner.

**Stufe 2 (08.08.2026):** Gemeinsamer Publish-Kern in `web/publish.py`:

- Tabelle `publish_intents` mit Intent-ID, Draft, Account, SKU, Zustand,
  Offer-/Listing-ID, Versuchen, Fehler, Fingerprint, Zeitstempeln.
- Zustände: `ready_for_review → publishing → published | failed |
  publish_uncertain | dry_run_done` (danach `ended`).
- `claim_or_create_intent` + Draft-Claim: höchstens eine aktive Absicht
  pro Draft; App und Telegram nutzen denselben Einstieg.
- `execute_publish` + `LiveEbayAdapter` / `FakeEbay`: bei Timeout zuerst
  eBay-Abgleich; scheitert der, wird `publish_uncertain` gesetzt — **kein**
  automatischer Zweit-Publish.
- `published`, `ended`, `dry_run_done`, `publish_uncertain` sind geschützt.
- Ausnahme: `dry_run_done` → `ready` nur wenn Dry-Run **aus** ist
  (`unlock_dry_run_for_live`), damit der bestehende Offer live published
  werden kann — kein Auto-Publish, kein zweiter Claim bei Dry-Run an.
- Fremde Drafts (Telegram-ID ≠ Aufrufer) werden nicht geclaimt.

UI-/Telegram-Texte bleiben Adapter; Inventory/Offer-Anlage bleibt in den
Pfad-Funktionen, der geldrelevante `publishOffer`-Schritt läuft über den Kern.

## Konsequenzen

- Tests: `tests/test_publish_claim.py`, `tests/test_publish_intent.py`.
- Quelltext-Wachen: App und Telegram rufen `claim_or_create_intent` und
  `execute_publish` auf.
