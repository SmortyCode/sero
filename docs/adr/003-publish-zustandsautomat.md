# ADR-003: Publish als Zustandsautomat mit atomarem Claim

Status: Stufe 1 umgesetzt 07.08.2026; Stufe 2 offen

## Kontext

Veröffentlichen kostet echtes Geld: Ein doppeltes Listing bedeutet doppelte
Gebühren und im schlimmsten Fall zwei Verkäufe desselben Einzelstücks.
Der Upload lief als frei gespawnter asyncio-Task; ein Doppeltipp erzeugte
zwei parallele Läufe, deren `published`-Check nicht atomar war.

## Entscheidung

**Stufe 1 (umgesetzt):** Ein atomarer Status-Claim in SQLite entscheidet,
wer laufen darf. `Store.claim_draft(id, "publishing", verboten=(…))` ist ein
einzelnes UPDATE mit Status-Prüfung im WHERE — genau ein Gewinner, egal wie
viele Tasks starten. Der Lauf hält den Claim über alle Zwischenspeicherungen
(lokaler Status wird mitgezogen) und gibt ihn im `finally` frei, außer ein
Endzustand (`published`, `dry_run_done`) wurde erreicht.
eBay-seitig sichern SKU-Suche (`create_offer` bei Timeout) und
Offer-Nachfrage (`publish_offer` bei Timeout) gegen Doppel-Anlage.

**Stufe 2 (offen):** Vollständiger Zustandsautomat
`draft → ready_for_review → publishing → published | failed | publish_uncertain`
mit `publish_uncertain` für den Fall „Timeout UND Nachfrage bei eBay
gescheitert" — heute endet das als `failed` mit Retry-Hinweis, was im
äußersten Randfall (eBay hat publiziert, antwortet aber zweimal nicht) zu
einem Doppel führen könnte. Außerdem: Idempotency-Key pro Publish-Absicht,
damit auch ein App-Neustart mitten im Lauf kein zweites Listing erzeugen kann.

## Konsequenzen

- `tests/test_publish_claim.py` schreibt den Claim fest (inkl. Quelltext-
  Wache: Claim vor der ersten eBay-Arbeit, Release im finally).
- Der Telegram-Pfad (`bot/main.py: run_upload`) nutzt den Claim noch NICHT —
  dort ist Doppeltipp unwahrscheinlicher (Button verschwindet), aber bei der
  Modularisierung denselben Claim einbauen.
