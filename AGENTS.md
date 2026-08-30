# SERO — Regeln für KI-Assistenten (Cursor, Claude, Copilot)

Diese Datei wird bei jedem Auftrag mitgelesen. Sie gilt vor allem anderen.
**Antworte immer auf Deutsch.** Der Betreiber heißt Sven, ist gewerblicher
eBay-Händler in München (Shop „seromunich") und kein Berufsentwickler —
erkläre Technisches in normaler Sprache, ohne Fachjargon-Nebel.

## Was SERO ist

App für Sammler und kleine Händler von Sammelkarten, Retro-Videospielen,
Manga und Comics. Kern in einem Satz:
**Foto machen → SERO erkennt das Stück, ermittelt den Marktwert und macht
daraus mit einem Tipp ein fertiges eBay-Listing.**
Deutschland zuerst: eBay.de, Euro, deutsche Texte.

## Wo was liegt

| Pfad | Inhalt |
|---|---|
| `~/ebay-bot` | **Die App** — Backend, Telegram-Bot, Frontend (`frontend/`), Tests |
| `~/ebay-bot/frontend/` | Die PWA: `sero.js`, `sero.css`, `index.html` (kein Framework) |
| `~/listo-website` | Website + Onboarding (noch getrennt; kommt später dazu) |

GitHub-Backup: `SmortyCode/sero` (dieses Repo), `SmortyCode/sero-website`.
Der frühere Ordner `~/sero-app` ist obsolet — Inhalt liegt in `frontend/`.

**`docs/IMPLEMENTATION_STATUS.md` ist die einzige Wahrheit** über Zustand,
Erledigtes und offene Punkte. Vor jeder Änderung lesen, danach aktualisieren.
Architektur-Entscheide in `docs/adr/` (001 Zielarchitektur, 002 Preisquellen,
003 Publish-Zustandsautomat). `STATUS.md` im Wurzelverzeichnis ist VERALTET
(Juni 2026) und nur noch Historie.

### Struktur, die man kennen muss, bevor man Code anfasst

- **Identität/Preis:** `web/identity.py` — Canonical + `pricing_ready`. Freie
  LLM-`search_query_for_pricing` steuert keine Preise. Katalog nur bei Ready.
- **Publish:** `web/publish.py` — Intent + Claim; App und Telegram denselben Kern.
  `publish_uncertain` nie auto-republish.

- **Alle App-Endpunkte stecken in EINER Fabrikfunktion** `build_router(store,
  ebay, cfg)` in `web/app_api.py` (Präfix `/api/app`). Sämtliche Helfer
  (`col_get`, `require_account`, `uid_for` …) sind Closures darin. Neue
  App-Endpunkte gehören in diese Funktion.
- **Pydantic-Body-Klassen müssen auf Modulebene stehen**, nicht in der
  Closure — sonst deutet FastAPI den Body als Query-Parameter (422).
- **Admin-Login ohne OTP:** `SERO_ADMIN_EMAIL` (Default in `web/social_auth.py`)
  auf `/api/login` und `/api/login-code` — Konto wie Signup, normale Session.
  Erkennung nur Backend. Kein zweites Nutzer-System, kein Frontend-Hardcode
  der Mail. Andere Adressen weiter mit Code.
- **`web/server.py` mountet ganz unten `/app` und `/`** (Website) als
  statische Verzeichnisse. Ein Mount auf `/` fängt jeden Pfad ab: neue Routen
  IMMER oberhalb dieser Mounts eintragen, sonst werden sie nie erreicht und
  der Fehler sieht aus wie ein Cache-Problem.
- **Den Listing-Ablauf gibt es zweimal:** `bot/main.py`
  (`run_pipeline`/`run_upload`/`run_update`) für Telegram und `web/app_api.py`
  (`app_run_*`) für die App. Beide arbeiten auf denselben Entwürfen und
  erzeugen echte eBay-Listings. Jede Änderung am Ablauf in BEIDEN prüfen —
  oder bewusst begründen, warum nur einer betroffen ist.

## Unverhandelbare Produktregeln

- **Preise kommen NIE aus einem Sprachmodell** (ADR-002) für Sammelkarten,
  TCG, Manga/Comics. Marktwert nur aus echten Belegen; sonst zeigt die App
  ehrlich „Wert unbekannt". Unter drei Vergleichsangeboten gibt es keinen
  Preisvorschlag. Ausnahme Alltagsprodukte und Retro-/Videospiele (Domäne
  `None` bzw. `game`): dort darf ein KI-Richtwert (`price_source=estimate`,
  `price_reason=KI_RICHTWERT`) erscheinen — klar als unsicher gekennzeichnet,
  manuell änderbar, nie automatische Listing-Preisbasis. Bei Spielen reicht
  auch ein einzelnes eBay-Vergleichsangebot. Wer eine Preisschätzung für
  Katalog-Karten in einen Prompt einbaut, bricht `tests/test_pricing.py`.
- **Der Preis-Katalog ist GLOBAL geteilt.** Eine Karte hat EINEN Preis je
  Grade-Stufe für alle Nutzer (`web/catalog.py`, Tabelle `card_prices`,
  24-h-TTL). Ein Preis, den du nur am einzelnen Stück änderst, wird beim
  nächsten Refresh überschrieben — und ein falscher Katalogwert vergiftet
  alle Konten bis zum TTL-Ablauf. Korrekturen laufen über
  `catalog.override_price()`.
- **Die beiden besten Preisquellen sind aus Lizenzgründen im Code AUS:**
  130point (echte Verkäufe) und PriceCharting laufen nur mit
  `SERO_QUELLE_130POINT=1` bzw. `SERO_QUELLE_PRICECHARTING=1` in der `.env`.
  Svens Betrieb hat beide an. Tests halten den Code-Default fest — das ist
  kein Fehler, den man „repariert". 130point ist zusätzlich auf eine Anfrage
  alle 8 Sekunden gedrosselt: „keine Verkäufe gefunden" heißt oft nur
  „gerade gedrosselt".
- **Nichts geht ohne Freigabe live.** Der Testmodus ist aus der App entfernt
  (kein Banner, kein Settings-Toggle). Maßgeblich ist NICHT `DRY_RUN` in der
  `.env`, sondern `kv['dry_run']` — aktuell **false**. Publish geht zu eBay
  und kostet echte Gebühren. Neue Installs: Default `false` (Config und kv).
  Telegram `/dryrun on|off` bleibt als Notfall im Bot, nicht in der App.
  Stand prüfen mit:
  `sqlite3 -readonly data.db "SELECT value FROM kv WHERE key='dry_run'"`.
  Selbst wenn jemand `/dryrun on` setzt, legt SERO echtes Inventar und ein
  echtes (unveröffentlichtes) Offer bei eBay an — nur `publishOffer` entfällt.
- **Das eigene freigestellte Foto ist immer das Hauptbild**, nie ein
  Katalogbild.
- **Bild-Standard: Warp zum Aufrichten, dann rembg-Freistellen.** Warp selbst
  ohne Kosmetik (kein Weichzeichnen, kein Aufhellen, kein künstlicher
  Studio-Hintergrund). Freistellen lokal mit rembg `isnet-general-use` →
  PNG mit Alphakanal und engem transparentem Rand. Festgeschrieben im
  Docstring von `web/cardscan.py` und in `tests/test_render_standard.py` /
  `tests/test_cutout_layout.py`. Warp-Kosmetik nur nach ausdrücklicher
  Zusage von Sven.
- **Entwürfe mit Status `published`, `ended` oder `dry_run_done` nie
 anfassen** — außer: `dry_run_done` bewusst auf `ready` zurücksetzen, wenn
 der Testmodus aus ist und live gelistet werden soll (`unlock_dry_run_for_live`).
 Daran hängt sonst echtes Geld bzw. die Verkaufshistorie.
- **Vor jedem Löschen sichern:** `sh backup.sh` (legt eine konsistente Kopie
  unter `backups/data-*.db` an). Niemals `cp data.db …` von Hand — die
  Datenbank läuft im WAL-Modus, eine nackte Kopie ohne `-wal`/`-shm` ist
  unvollständig.

## Datenverlust-Falle: nach jedem `await` frisch lesen

Eine Analyse dauert 30–90 Sekunden, ein Preis-Refresh Minuten. Schreibst du
danach das vor dem `await` gelesene Objekt komplett zurück, löschst du alles,
was der Nutzer inzwischen eingetragen hat (Kaufpreis, Notiz, Favorit, Menge).
Deshalb: **erst `col_get()` neu lesen, dann nur die Felder setzen, für die
dein Vorgang zuständig ist** (Feldlisten `PREIS_FELDER`/`ANALYSE_FELDER`,
Vorlage `col_save_analyse`). Kommt `None` zurück, wurde das Stück gelöscht —
abbrechen. Bei Entwürfen gilt dasselbe: ein Rückschreiben mit altem `status`
löst den Publish-Claim und kann ein zweites eBay-Listing erzeugen.

## „Wert unbekannt" richtig bauen

Der Anzeigezustand steckt in `price_state` (belegt / spanne / unbekannt) und
`price_reason` (geschlossenes Enum: ROHPREIS_SLAB, BELEGE_ALT, NUR_ANGEBOTE,
UNBEKANNT_ZUORDNUNG, UNBEKANNT_WIDERSPRUCH, UNBEKANNT_KEINE_BELEGE), gesetzt
in `setze_preiszustand()`. Wer einen Preis anzeigt, prüft immer beides. Ein
neuer `price_reason` braucht zusätzlich einen Text in `PREIS_GRUENDE` in
`sero.js` und einen Eintrag im englischen Wörterbuch.

## UI-Sprache

Duzen. Keine Ausrufezeichen, keine Emojis in App-Texten. Die App sagt nie
„Wir". Vokabular: „Stück", „listen", „Marktwert", „tippen".

Das englische Wörterbuch heißt `STR_EN` in `sero.js`; **der deutsche Text IST
der Schlüssel**, nachgeschlagen über `L()`. Fehlt ein Schlüssel, fällt die
Ausgabe still auf Deutsch zurück — kein Fehler, kein roter Test. Wer einen
deutschen Text ÄNDERT, muss den Schlüssel dort mitändern, nicht nur neue
Texte eintragen. Schlüssel zeichengenau kopieren.

## Betrieb (wichtig, sonst geht die Handy-App aus)

**Es laufen ZWEI launchd-Dauerdienste aus diesem Repo:**

| Dienst | Was | Neustart |
|---|---|---|
| `com.listo.web` | uvicorn `web.server:app` auf `0.0.0.0:3000` — App, Website, API | `launchctl kickstart -k gui/501/com.listo.web` |
| `com.listo.bot` | `python -m bot.main` — der Telegram-Bot | `launchctl kickstart -k gui/501/com.listo.bot` |

Beide arbeiten gleichzeitig auf derselben `data.db`. Nach Änderungen unter
`web/` den Web-Dienst neu starten, nach Änderungen unter `bot/` den Bot —
`bot/drafts.py` gehört zu beiden, dann beide. Wer das vergisst, testet gegen
alten Code, während der Bot echte Listings mit der alten Logik veröffentlicht.

- Sven benutzt die App über WLAN unter `http://192.168.2.39:3000/app/`.
- **Niemals einen eigenen Server auf Port 3000 starten** und die Dienste nicht
  stoppen — dabei ist schon eine Vorführung geplatzt.
- Nach Frontend-Änderungen den passenden Versions-Pin in
  `frontend/index.html` hochzählen. Es sind **drei unabhängige**:
  `sero.css?v=`, `sero-dark.css?v=`, `sero.js?v=`. CSS-Änderung → CSS-Pin.

**Contabo ist Svens Testseite**, nicht „Produktion die man nie anfasst“.
Öffentliche App: `https://app.seromunich.com/app/` (`/opt/sero`, systemd
`sero-web`). Nach Frontend- oder Backend-App-Änderungen **mitdeployen**:
`sh scripts/deploy_contabo.sh` — nicht nur lokal `com.listo.web` neu starten.
Das Skript rsync’t **keine** `data.db`, **keine** `.env` und meist **keine**
`collection_photos/` (Mac-Port 3000 bleibt unangetastet). Landing
`https://seromunich.com` nur mitdeployen, wenn sich `landing/` geändert hat
(`--landing-only` reicht dann). Details: `docs/DEPLOY_CONTABO.md`.

## Prüfen vor jeder Übergabe

```
./.venv/bin/python -m pytest tests/ -q     # aktuell 330 passed, 1 xfailed
sh tests/smoke.sh                          # Ampel gegen das laufende System
```

**Kein Test und kein Ausprobier-Skript darf die echte `data.db` anfassen.**
Ohne die Umgebungsvariable `SERO_DB` nimmt `bot/config.py` die Live-Datei,
und schon `import web.server` legt einen Store darauf an. Es gibt keine
`conftest.py`: Tests, die einen Store oder `web.server` brauchen, laufen wie
`tests/test_api_integration.py` in einem Subprozess mit `SERO_DB=<Tempdatei>`;
alles andere benutzt die FakeStore-Attrappe aus `tests/test_catalog.py`.

Mehrere Tests sind **Quelltext-Wachen**: Sie lesen den Code und schlagen an,
wenn jemand einen bewussten Produktentscheid zurückbaut (Bildpipeline ohne
Kosmetik, Publish-Doppeltipp-Schutz, fail-closed-Checkout, keine LLM-Preise).
Schlägt so ein Test an, ist das kein Testfehler — dann ist die Änderung falsch.

## Bitte NICHT vorschlagen

- Drag-and-Drop zum Sortieren (war gebaut, auf dem Handy unbrauchbar).
- Einen Marktplatz oder Zwischenhandel — SERO kauft nichts an.
- Einen Autopiloten, der ohne Freigabe listet.
- Ein Frontend-Framework, ohne den konkreten Nutzen zu begründen.
- Den großen Datenbank-/Worker-Umbau vorzuziehen (ADR-001): erst ab etwa
  20 gleichzeitigen Nutzern nötig.

## Arbeitsweise

- Erst lesen, dann ändern. Kleine, abgeschlossene Schritte, jeder Schritt mit
  laufenden Tests.
- Kein halber Umbau: lieber gar nicht anfangen als eine Baustelle hinterlassen.
- Bei Unsicherheit über eine Produktregel: nachfragen statt raten.
