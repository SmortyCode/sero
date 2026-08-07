# ADR-001: Modularer Monolith mit Workern, PostgreSQL und Objektspeicher

Status: beschlossen 07.08.2026 (Umsetzung offen — Phase „Skalierbarer Betrieb")

## Kontext

SERO läuft als EIN Prozess: FastAPI + alle Hintergrunddienste als
asyncio-Tasks, EINE SQLite-Verbindung hinter einem Lock, Fotos im Dateisystem,
Jobzustand im Speicher. Das ist für den Ein-Betreiber-Betrieb richtig und
robust (Neustart heilt alles, keine verteilten Zustände). Es bricht bei
>≈20 gleichzeitigen Nutzern: Freisteller blockieren einen Prozessorkern,
Belegabfragen sind auf einen 8-s-Takt gedrosselt, SQLite serialisiert alle
Schreiber, ein Deploy unterbricht laufende Scans.

## Entscheidung

Kein Microservice-Zoo. Zielbild ist ein **modularer Monolith** plus
**getrennte Worker-Prozesse**:

- Ein Web-Prozess (mehrere Uvicorn-Worker möglich, weil kein Zustand mehr in
  der Closure lebt) für API + Auth + statische Dateien.
- Worker-Prozesse für: Bildpipeline (CPU-schwer), Preis-Refresh (I/O + Takt),
  eBay-Publish (idempotent, siehe ADR-003).
- **PostgreSQL** statt SQLite (echte Parallelität, Migrationen via Alembic).
- **Objektspeicher** (S3-kompatibel) für Fotos statt `collection_photos/`.
- **Dauerhafte Queue** (z.B. Postgres-basiert: SKIP LOCKED) statt
  `asyncio.create_task` — Jobs überleben Neustarts.

## Konsequenzen

- Erst nötig vor echtem Mehrnutzer-Betrieb. Bis dahin: keine neue Funktion
  bauen, die zusätzlichen Prozess-Zustand einführt.
- Die Router-Closure in `web/app_api.py` muss dafür in Module mit explizite
  Abhängigkeiten zerfallen (store, ebay, cfg als Parameter statt Closure).
- Der Telegram-Bot wird ein weiterer Konsument derselben Module — nicht mehr
  der Ort, an dem Onboarding-Logik exklusiv lebt.

## Verworfen

- Microservices: drei Größenordnungen zu viel Betriebskomplexität.
- SQLite behalten mit Litestream: löst Parallelität nicht.
- Serverless: Bildpipeline (rembg/ONNX, mehrere hundert MB Modelle) passt
  nicht in kurzlebige Funktionen.
