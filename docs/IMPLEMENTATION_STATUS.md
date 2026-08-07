# SERO — Stand der Umsetzung

**Stand: 7. August 2026 (Abend — Baustellen 1–5 abgearbeitet).** Diese Datei
ist die einzige Wahrheit über den Zustand des Projekts. Wer hier weiterbaut
(Cursor, ein anderes Werkzeug, ein Mensch): erst lesen, dann ändern, danach
diese Datei aktualisieren.

## Go-Live-Checkliste (07.08. abends)

Umgesetzt aus dem Audit-Canvas `sero-golive-audit`:

| Punkt | Stand |
|---|---|
| `kv['dry_run']=true` (Üben) | gesetzt via Store wie `/dryrun on`. Vor echtem Live: `/dryrun off` oder kv zurück auf false. Bot+Web am 07.08. Abend per `launchctl kickstart` neu gestartet (dry_run-Cache frisch). |
| Scanner / Freisteller | Rotation-first (kein Zerren), `kanten_trim` + `tisch_trim` + `untergrund_trim` (Filz/Stoff). KEIN rembg auf Slabs. CGC-Stücke aus Rohfotos neu; beste Variante behalten. Pin `sero.js?v=108`. |
| Alte CGC `_cut` → `slab_recut` | Neugeschnitten aus `00.jpg`/`01.jpg`; Auswahl prev/cur/new nach Score. Case komplett. |
| `label_type` nachziehen | Exeggutor → pristine (+ Name); Garados `fb726042ce4b` → pristine aus Name; Charizard `850420d25072`, Glurak, One Piece → gem_mint |
| 4 Error-Entwürfe | Orphans gelöscht nach `backup.sh`. 0 Error-Entwürfe übrig. |
| Sales-Sync 403 | **Code fertig, Sven muss einmal neu verbinden:** `USER_SCOPES` enthält `sell.fulfillment`. Consent-URL (`/verbinden` + Website `/connect/ebay`) fordert ihn an. Bei Orders-403 setzt Sync `ebay_fulfillment_fehlt_<uid>`; `/api/me` → `ebay_needs_reconnect`; Profil zeigt „Neu verbinden“. Flag fällt nach erfolgreichem OAuth. Token `5694742134` noch ohne Scope bis Sven verbindet. |
| Production-Env | `.env` hat weder `APP_ENV` noch `PUBLIC_BASE_URL` (LAN-HTTP ok). **Nicht** auf production gestellt — Secure-Cookie würde Handy-WLAN brechen. Schritte in `.env.example`. |
| E2E Handy Foto→Listen | Checkliste `docs/E2E_HANDY.md`. API-Smoke: `/app/` 200, Collection/Me 401. Rest: Sven am Handy unter dry_run. |
| GitHub Push | Remote `origin/master` — Push nach diesem Stand. |
| CI | Vorbereitet (pytest-Workflow), Push braucht GitHub-Token mit `workflow`-Scope — lokal noch nicht im Remote. |

Backup vor DB-Aktionen: `backups/data-18.db`.

## Freisteller / Sales-Sync (07.08. spät abends)

- **Slab enger + aufrecht ohne Zerren:** Perspektiv nur wenn Symmetrie-Gates
  greifen UND der Slab schon nahezu aufrecht ist (sonst bleibt Schräge im
  Vision-AABB). Sonst nur `warpAffine`. Neu: `untergrund_trim` für dunklen
  Filz/Stoff (tisch_trim allein reichte nicht). Feinjustierung ≤4,5°.
  Vertrag in `test_render_standard` (+ Tests für `untergrund_trim`).
- **Sales-Sync 403 UX:** kv-Flag + Profil-Hinweis + klarere `/verbinden`-Texte.
  Ein erneutes Verbinden reicht — kein Token-Refresh-Hack.

## Zweiter Durchgang (07.08. nachmittags): Roadmap-Punkte umgesetzt

- **Slab: aufrecht + enger Zuschnitt (07.08. spät):** `slab_recut` richtet
  per Perspektiv-Warp hinter Symmetrie-Gates auf (Parallelogramm → kein Zerren);
  bei asymmetischen Kanten nur `warpAffine`-Rotation. Danach `kanten_trim`
  (je Zeile/Spalte) + `tisch_trim` (warmer Kork/Holz-Rand weg). Klares Case
  bleibt; kein rembg. Sechs CGC-Stücke aus `photos_raw` neu geschnitten;
  `label_type` pristine/gem_mint unverändert. Tests in `test_render_standard`.
- **Slab: kein rembg nach Warp (07.08. abends):** PicsArt-rembg nach
  `slab_recut` hat klares Case-Plastik als Hintergrund gefressen — Label und
  Karte schwebten getrennt (Gyarados/Umbreon CGC Pristine). Fix: bei
  `kind=slab` nur Ecken-Warp + Nachschnitt; rembg nur Fallback wenn der Warp
  reißt (`crop_photos` + Graded-Hook in `app_api`). Vier CGC-Stücke aus
  `photos_raw` neu gewarpt (`*_slab.png`), `label_type` unverändert.
  Vertrag in `test_render_standard` / Modul-Docstring.
- **CGC Pristine + PicsArt-Freisteller (07.08.):** `graded.label_type`
  (pristine/perfect/gem_mint) — Gold-Siegel „CGC Pristine 10“, Titel + Verkaufssuche.
  Slab-Pfad siehe Punkt oben (PicsArt-Nachschritt zurückgenommen).
  Pins `sero.css?v=61` / `sero.js?v=108`.
- **Ein Ordner für die App (07.08. abends):** Frontend von `~/sero-app/web`
  nach `~/ebay-bot/frontend/` gezogen. `web/server.py` liefert `/app` jetzt
  aus demselben Repo (Default `SERO_APP_DIR` = `<repo>/frontend`). Website
  bleibt vorerst in `~/listo-website`. GitHub-Backup: `SmortyCode/sero`.
- **Git:** `~/ebay-bot` und `~/sero-app` sind jetzt Git-Repositories mit
  `.gitignore` (Secrets/Daten ausgeschlossen) und Basis-Commit vor den Umbauten.
- **P0.2 — Preise NIE aus dem Sprachmodell (ADR-002, jetzt umgesetzt):**
  `estimated_price_range_eur` ist aus dem Analyse-Prompt entfernt; der Prompt
  verbietet Preisschätzungen jetzt ausdrücklich. `check_price_plausibility`
  wurde zu `comps_verwertbar` (Mindestbeleg-Regel: unter 3 Vergleichsangeboten
  gibt es KEINEN Preisvorschlag — der Nutzer trägt selbst ein). Die
  est_low/est_high-Felder entstehen nicht mehr; Altbestände mit
  `price_source=estimate` werden beim nächsten Refresh verworfen und neu
  bewertet. Der Rohpreis am Slab gilt als „unbekannt" (`ROHPREIS_SLAB`,
  siehe Review-Absatz unten) und ist als Listing-Preisbasis GESPERRT.
  Quelltext-Wachen in `tests/test_pricing.py` schreiben all das fest.
  Verlorene Nebenwirkung (bewusst): der alte „Apfelschorle-Wächter"
  (LLM-Spanne validierte Comps-Median) — Ausreißer fängt jetzt nur noch der
  IQR-Trim in browse.research_price plus die Mindestbeleg-Regel.
- **P0.3 — eBay-Einrichtung ohne Telegram:** Neuer Endpoint
  `POST /api/ebay-setup` (Richtlinien anlegen/übernehmen + Versandstandort,
  `web/server.py`); `/api/me` liefert `setup_ready`/`used_this_month` jetzt
  auch für reine App-Nutzer (synthetische uid). Onboarding-Website: Schritt 3
  ist die Versandadresse (Pflicht), Telegram ist ein optionaler Kasten in
  Schritt 4. In der App öffnet die Setup-Zeile im Profil ein Adress-Sheet.
- **P0.5 — Lizenz-Schalter:** `SERO_QUELLE_130POINT` und
  `SERO_QUELLE_PRICECHARTING`, Code-Default AUS (Tests fixieren das); nur die
  `.env` des Betreiber-Einzelbetriebs schaltet sie ein.
- **P1 — CSRF + CSP:** Origin-Prüfung für alle schreibenden Methoden
  (fremder Origin → 403, live verifiziert; Requests ohne Origin passieren,
  weil die Angriffsklasse browserbasiert ist und Origin immer trägt).
  Content-Security-Policy-Header auf allen Antworten.
- **Adversarieller Review (3 unabhängige Lese-Agenten) + Fixes:** Der Review
  fand am eigenen P0.2-Umbau zwei kritische Löcher, beide geschlossen:
  (a) Der Katalog-Kanal war offen — `source=estimate` konnte als base/anker/
  Cache-Row zurückkommen; jetzt in `catalog.py` an vier Stellen hart
  ausgeschlossen (Test: `test_estimate_basis_ist_ueberall_tabu`).
  (b) Ein CGC-10-Slab wäre über alte Belege mit einem 0-€-Scheinverkauf für
  4,11 € listbar gewesen — 0-€-Verkäufe fliegen aus dem Schnitt, Slab+alte
  Belege sind als Listing-Basis gesperrt. Außerdem: Scryfall/YGOPRODeck
  zählen jetzt korrekt als „belegt" (sonst hätten Magic/Yu-Gi-Oh ihren
  Listing-Preis verloren), `ROHPREIS_SLAB` ist ehrlich „unbekannt" (Wert nur
  noch als Untergrenze im Detail, nicht mehr in Portfolio/Alarm), alte
  `market`-Dicts aus der KI-Ära werden geleert und im Frontend gefiltert,
  CSRF versteht X-Forwarded-Host/Default-Ports (Proxy-Betrieb), und
  `/api/ebay-setup` ist pro Nutzer serialisiert.
- Suite: **340+ passed, 1 xfailed**; Smoke grün; `sero.js?v=108`.
- Git: Basis-Commit + Umsetzungs-Commit in `~/ebay-bot` und `~/sero-app`;
  `~/listo-website` ebenfalls versioniert. Remote `origin` aktiv.

Hintergrund: Am 04.08. ging ein Dossier an externe Prüfer; der ChatGPT-Audit
kam am 07.08. zurück und wurde teilweise umgesetzt (Details unten). Die
Roadmap in dieser Datei ist der abgestimmte 8-Phasen-Plan aus dem Audit,
reduziert auf das, was für SERO wirklich zutrifft.

---

## Verifizierter Systemzustand (07.08.2026)

| | |
|---|---|
| Tests | **340 passed, 1 xfailed** (`pytest tests/ -q`) plus `tests/smoke.sh` grün |
| Installierbarkeit | Frisches venv + `requirements.txt` → alle Kernmodule importieren (geprüft) |
| Betrieb | launchd `com.listo.web` auf 0.0.0.0:3000, KeepAlive, ohne `SERO_DEV_CODES` |
| Frontend | `sero.js?v=108`, `sero.css?v=61` |
| Datenbestand | Echtdaten von 1 Betreiber (Account 3) + Testkonten. Backup vor dem Umbau: `backups/audit-0708/` |

## Heute umgesetzt (Audit-Punkte)

1. **P0.1 Installierbarkeit:** `requirements.txt` vollständig (27 Pakete mit
   Versionen statt 8), `.env.example`, README neu (beschrieb vorher das
   Vorgänger-Projekt „ListingPunk"). Clean-Install in frischem venv bewiesen.
2. **P0.4 Publish-Doppelstart:** Atomarer Status-Claim in SQLite
   (`Store.claim_draft`/`release_draft_claim` in `bot/drafts.py`), eingebaut in
   `app_run_upload`. 20 parallele Claims → genau ein Gewinner
   (`tests/test_publish_claim.py`, 6 Tests inkl. Quelltext-Wache).
   eBay-seitig waren Timeout-Fälle schon selbstheilend (`publish_offer` fragt
   bei Timeout nach, `create_offer` sucht per SKU).
3. **P1 Stripe fail-open:** `APP_ENV=production` lehnt Checkout ohne
   `STRIPE_SECRET_KEY` mit 503 ab statt den Plan gratis zu aktivieren.
4. **P1 Host-Header:** Alle ausgehenden Links (Login-Mail, Stripe-Redirects,
   OAuth-Callbacks) laufen über `public_base_url()`; in Produktion ist
   `PUBLIC_BASE_URL` Pflicht (Start bricht sonst ab).
5. **P1 Cookie:** Session-Cookie bekommt `secure=True` bei
   `APP_ENV=production` (lokal bleibt HTTP im LAN funktionsfähig).
6. **P1 Token-Leiche:** Kontolöschung räumt jetzt BEIDE Identitäten
   (Telegram-ID und synthetische App-ID) — vorher blieb ein gültiges
   eBay-Refresh-Token zurück.
7. **Streichliste (Teil 1):** Ersatzlos entfernt aus Backend + Frontend + CSS:
   Solana-NFT-Wallet, Markt-Sektion (Release-Kalender + Reddit-News),
   OHLC-Kerzencharts, Gamification (Punkte/Stufen/Set-Fortschritt),
   Zeitspar-Rechner (`time_saved` inkl. Meilenstein-Overlay),
   KI-Grading-Schätzung (`/grade`, `get_grader` — damit ist auch der
   Fremdverzeichnis-Import aus `~/card-grader` weg).
   ~360 Zeilen Backend, ~380 Zeilen JS, ~420 Zeilen CSS.

## Bewusste Abweichungen vom Audit

- **`/graded-market` bleibt.** Der Audit strich „Grading" pauschal; die
  PSA-10/9-Angebotspreise sind aber echte eBay-Daten (kein LLM-Raten) und ein
  ausdrücklicher Produktwunsch des Betreibers. Gestrichen wurde nur die
  KI-Note-Schätzung.
- **Markt-Umschalter EU/USA/Japan bleibt** (Streichkandidat laut Audit).
  Frisch gebaut auf ausdrücklichen Wunsch, klein, nutzt die ohnehin
  vorhandene Browse-Anbindung. Kandidat für später, falls er Pflege kostet.
- **Zweitsprache (i18n) bleibt vorerst.** Das Wörterbuch ist tief in
  `sero.js` verwoben; Entfernen ist ein eigener, riskanter Umbau ohne
  Sicherheitsgewinn. Kandidat für die Frontend-Modularisierung (Phase 7).
- **Preisalarme und Hintergrund-Designer bleiben vorerst** (klein, geringe
  Pflegekosten). Entscheid beim nächsten Schnitt.

## Nicht umgesetzt — die Roadmap für den Nachfolger

In empfohlener Reihenfolge. Nichts davon anfangen, ohne es zu Ende zu bringen —
ein halber Umbau ist schlimmer als keiner.

### 1. P0.6 — Skalierbarer Betrieb (der große Umbau)
Ein Prozess, eine SQLite-Verbindung, In-Memory-Jobs, Fotos auf Platte.
Harte Grenzen: ~1 Freisteller gleichzeitig (≈100 Stücke/h plattformweit),
8-s-Takt bei Belegabfragen (≈450/h), 14–40 MB Bilder pro Stück.
**Zielbild in ADR-001:** modularer Monolith + getrennte Worker, PostgreSQL,
Objektspeicher, dauerhafte Queue. Erst nötig ab >≈20 gleichzeitigen Nutzern —
nicht vorziehen, aber jede neue Funktion so bauen, dass sie den Umbau nicht
schwerer macht.

### 2. Restliche P1
- In-Memory-Rate-Limiter und -Jobzustände überleben keinen Neustart.
- Kein Alembic/Migrationswerkzeug — Schema-Änderungen laufen über
  `_ensure_column` beim Start.
- `app_api.py` (~3.680 Zeilen, eine Closure) und `sero.js` (~3.780 Zeilen)
  modularisieren — erst NACH den fachlichen P0-Punkten.
- CI: Workflow-Vorlage vorbereitet, aber Push braucht Token-Scope `workflow`
  (aktueller `gh`-Login hat ihn nicht). Lokal nachreichen sobald Scope da.

### 3. Git-Remote
Remote `origin` → `SmortyCode/sero`. Push nach Go-Live-Baustellen.

## Was der Nachfolger über die ChatGPT-Befunde wissen muss

Geprüft und **bestätigt**: P0.1, P0.4 (Doppelstart real — Task-Spawn ohne
Claim), Stripe fail-open, Host-Header in 6 Links, Token-Leiche (bei
Telegram-verknüpften Konten), README-Veraltung, fehlende Pakete.
Geprüft und **relativiert**: „Publish nicht idempotent" — die eBay-Seite
(create/publish) war durch SKU-Suche und Timeout-Nachfrage bereits
abgesichert; das Loch war der lokale Doppelstart. „Grading streichen" — nur
zur Hälfte übernommen (siehe Abweichungen).
**Nicht geprüft** (bei Umsetzung selbst verifizieren): die genauen
Zeilenangaben des Audits — sie stammen vom Dossier-Stand 04.08. und stimmen
nach den Streichungen nicht mehr.

## Nicht verhandelbar (Produktregeln des Betreibers)

Duzen; keine Ausrufezeichen/Emojis in UI-Texten; „Stück/listen/Marktwert/
tippen"; die App sagt nie „Wir". Eigenes freigestelltes Foto ist immer das
Hauptbild. Marktwert nur aus echten Belegen, sonst ehrlich „unbekannt".
Nichts geht ohne Freigabe live. Keine Drag-Sortierung. Bild-Standard: Warp
pur ohne Kosmetik (per Quelltext-Test festgeschrieben). Entwürfe mit Status
`published`/`ended`/`dry_run_done` nie anfassen. Vor jedem Löschen: Sicherung
anlegen und unmittelbar davor erneut prüfen. Prüf-/Audit-Agenten bekommen nur
lesende Aufträge — nie Schreibrechte, nie eine Live-Session.
