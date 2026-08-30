# SERO — Stand der Umsetzung

**Stand: 30. August 2026 — aaaa.md Follow-up (Filter/Sheet/Detail/Light nachgezogen); Pins js 257 / css 166 / clean 45. Kein Deploy (Briefing).**
Diese Datei ist die einzige Wahrheit über den Zustand des Projekts. Wer hier
weiterbaut: erst lesen, dann ändern, danach diese Datei aktualisieren.

## Auftrag 30.08. — aaaa.md (Filter, Sheet, Detail-Tabs, Light)

Briefing `docs/sero-ui-aaaa-followup.md` (= Downloads/aaaa.md). Punkte 1–3 waren
schon im Follow-up; Light-Leaks nachgezogen (Profil/Detail-Dock/Scan-Sekundär/
Tab-Bar). Einstellen wechselt immer auf eBay-Tab. Kein Deploy laut Briefing.
Kein Auto-Publish.

## Auftrag 30.08. (siebter Lauf) — Filter, Sheet, Detail-Tabs, Light

Briefing `docs/sero-ui-followup.md`. Baut auf Clean-Motion auf, nichts davon
zurückgebaut. Keine neuen Features, kein Auto-Publish, Filterlogik-Kern bleibt.
`SERO_APP_VERSION` bleibt 4.1.0. `kv['dry_run']` unangetastet. Kein Commit.

| Stück | Stand |
|---|---|
| Filter-Chips | One Piece / Pokémon: Wordmark **oder** Label, nicht beides. `aria-label` bleibt. Reihenfolge über `CAT_CHIP_ORDER` ∩ `INV_CATS`. `INV_CATS` unverändert. |
| Filter Dark/Light | `filter: invert(1)` nur Dark. Light: dunkle Wordmarks. |
| Disclosure | Leer: kein Grading, keine Sprache, keine Region. Grading+Note nur bei Graded. Sprache nur TCG. Region nur Games. Wert/Jahr eine Zeile. |
| Sheet | `max-height` 80vh. Drag an `#sheetHead` (Grip + Titel, ≥44px). Schwelle 90px. Backdrop-Tap bleibt bei `dismissible !== false`. `#sheetBody` scrollt allein. |
| Detail-Tabs | Info \| eBay unter dem Hero. Ein Pane sichtbar. `det.seg` wirklich `overview`/`sell`. Einstellen wechselt auf eBay. CTA-Dock nur Info. `listingPaintKey` / `listingInputBusy` / `opts.ebayOnly` bleiben. |
| Light | Canvas `#fff`, Text `#000`, Fills `#f2f2f7`/`#e5e5ea`. Overrides für Grid, Port-Wert, Login, Chips, eBay-Karten. Splash bleibt schwarz. `color-scheme: light`. Wordmark navy/white. |

Sofortkauf-Tippen, Location/UUID, Gast-Scan, C6 nicht zurückgebaut.

Pins: `sero.js?v=255`, `sero.css?v=164`, `sero-clean.css?v=43`,
`sero-profile.js?v=23`, `manifest.webmanifest?v=7`.
Wache: `tests/test_ui_followup.py`.
Suite: 796 passed, 4 skipped. Smoke grün.
Contabo 30.08. siebter Lauf: `sh scripts/deploy_contabo.sh` (keine `data.db`/`.env`).
Hard-Reload `https://app.seromunich.com/app/`.

## Auftrag 30.08. (sechster Lauf) — clean skin + micro-motion

Briefing `docs/sero-ui-clean-motion.md`. Keine neuen Features, keine 4. Tab,
kein Auto-Publish. Filterlogik unverändert. `SERO_APP_VERSION` bleibt 4.1.0.
`kv['dry_run']` unangetastet. Kein Commit.

| Stück | Stand |
|---|---|
| Wordmark | Chrome nur Splash + App-Icon. In-App (Topbar, Login, Empty, Tour) flach: `wordmark-white.png` / `wordmark-navy.png`. |
| Glas | Tab-Bar, Sheets, Login-Karte, Suche. Kein Glas auf Content-Karten, Grid, `#salesSeg`. Clean-Blur bleibt 18px. `#viewApp.recede` nur Dim. |
| Motion | `splashPulse` / `orbbreathe` aus. `logoIn` am Splash. Login-Karte wieder `pageIn`. Press `scale(.96)`. Sheet-Close `--spring`. Scan-Success `ticpop`. Kurve: Path-Morph 280ms. Verkaufen: Sliding-Underline + 200ms Crossfade. `prefers-reduced-motion` still. |
| Start | Eine weiße Pille, zwei Outlined-Chips. FAQ nach Einstellungen → Hilfe. Wertkarte Near-Black, Mint nur Chart, Grün nur Delta. |
| Scannen | Gleiche Aktions-Hierarchie. Gallery-Label „Aus Fotos“. Defaults-Zeile Label oben, Werte truncated darunter. Viewfinder Idle ohne Pulse. |
| Sammlung | Unter 3 Punkten: „Wert wird ab dem 3. Stück sichtbar“, keine tote Hairline. 7T/30T/1J bleiben. Preis tabular, „Weiteres“ muted Chip. Suche als Icon-Field, Filter/Sort Chips, Kacheln-Toggle. `padding-bottom` 96px. |
| Verkaufen | Underline gleitet. Empty `min-height` 220px. Verkauft: muted „Erlöse erscheinen hier“, keine weiße Pille. |
| Profil | Nicht umgebaut. Stats: Skeleton statt „—“. FAQ in Hilfe. |

Teil-A-Fixes, Sofortkauf-Tippen, Location/UUID, Gast-Scan, C6 nicht zurückgebaut.
`listingPaintKey` / `listingInputBusy` unverändert.

Pins: `sero.js?v=254`, `sero.css?v=163`, `sero-clean.css?v=42`,
`sero-profile.js?v=23`, `manifest.webmanifest?v=7`.
Wache: `tests/test_ui_clean_motion.py`.
Suite: 788 passed, 4 skipped. Smoke grün.
Contabo 30.08. sechster Lauf: `sh scripts/deploy_contabo.sh` (keine `data.db`/`.env`).
Hard-Reload `https://app.seromunich.com/app/`.

Nur mit Mockups/Brand: B 1:1-Pixel, D2 Brand-`icon.png` + iPad-Startup.

## Auftrag 30.08. (fünfter Lauf) — Gast-Sync + offene Zeilen ohne Mockups

Briefing nochmal gegen Code. Mockups/Brand (`/workspace/sero-studio/`,
`/workspace/sero-brand/`) weiter nicht auf dem Mac (Downloads, Desktop/SERO,
Documents, iCloud). Teil B 1:1-Pixel und D2 Brand-`icon.png` deshalb weiter
ohne Pixel-Lock. iPad-Startup nicht im Tree, nicht erfunden.

| Stück | Stand |
|---|---|
| Gast-Sync | Nach Login und bei Rest-Entwürfen im Boot: `flushGuestDrafts()` lädt `sero_guest_drafts_v1` nach `POST /api/app/collection/items` (gleiche Analyse/Cutout-Queue wie ein normaler Scan). Kein Auto-Publish. |
| Sichtbar | Zeile „Entwürfe werden gespeichert …“; Erfolg-Toast „Analyse läuft.“; Fehler + „Erneut versuchen“, nie still. |
| Kein Datenverlust | Nach jedem `await` frisch `guestDraftRows()`; nur die fertige Id entfernen; Rest bleibt lokal. Altes `kept.push`+`break` (Rest weg) raus. |
| D5 | `monogram-*.png` nicht mehr in App- noch Landing-Assets. Landing-CTA und Hero-Maske: `wordmark-white.png`. |
| Teil A / C / D1–D4 | Unverändert aus den vorigen Läufen. |

Teil-A-Fixes, Sofortkauf-Tippen, Location/UUID / Filter nicht zurückgebaut.
`listingPaintKey` / `listingInputBusy` unverändert. `kv['dry_run']` unangetastet.
Kein Commit.

Pins: `sero.js?v=253`, `sero.css?v=162`, `sero-clean.css?v=41`,
`sero-profile.js?v=22`, `manifest.webmanifest?v=7`. Landing `landing.css?v=6`.
Wachen: `tests/test_c6_guest_save.py`, `tests/test_cursor_alles_20260830.py`.
Suite: 784 passed, 4 skipped. Smoke grün.
Contabo 30.08. fünfter Lauf: `sh scripts/deploy_contabo.sh` (keine `data.db`/`.env`).
Hard-Reload `https://app.seromunich.com/app/`.

Nur mit Mockups/Brand: B 1:1-Pixel, D2 Brand-`icon.png` + iPad-Startup.

## Auftrag 30.08. (vierter Lauf) — C6 Login erst beim Speichern

Briefing C6: Login nicht auf Splash/Onboarding, nicht vor dem ersten Foto,
nicht vor dem lokalen Entwurf. Erstes Speichern, das ein Konto braucht:
ein Screen, nur E-Mail, Satzfall, Abbrechen/Später. Abbrechen lässt den
lokalen Entwurf stehen. Kein Google/Apple/eBay/Passwort/Tarif. Schon
eingeloggt: Sheet nicht zeigen. Live-Login bleibt email-only (Admin-Mail
unverändert im Backend).

Gebaut als kleinster sicherer Slice, keine Gast-DB:

| Stück | Stand |
|---|---|
| Boot ohne Session | 401/403/offline ohne Cache → `enterGuestApp()`, nicht die Login-Wand |
| Scan | Kamera/Mediathek/Review wie bisher, ohne Konto |
| Als Entwurf behalten | lokal in `localStorage` (`sero_guest_drafts_v1`), Badge Entwurf, Sammlung |
| Gate | sichtbares „Anmelden zum Speichern“ + E-Mail-Sheet; Später schließt |
| Nach Login | `flushGuestDrafts()` → `POST /api/app/collection/items` |
| Schon Session | unverändert `showApp()`; Admin-Login `adminsero@sero.com` unangetastet |

Kein Auto-Publish. Keine Stücke auf dem Server gelöscht. Teil A / Sofortkauf /
Location/UUID / Filter nicht zurückgebaut. `kv['dry_run']` unangetastet.
Kein Commit.

Pins: `sero.js?v=252`, `sero.css?v=162`, `sero-clean.css?v=40`,
`sero-profile.js?v=22`, `manifest.webmanifest?v=7`.
Wache: `tests/test_c6_guest_save.py`.

Mockups (`/workspace/sero-studio/`, `composite/`, Brand) weiter nicht auf dem
Mac — Teil B 1:1-Pixel und D2 Brand-`icon.png` weiter offen. C6 braucht die
Pixel-Vorlagen nicht.

## Auftrag 30.08. (dritter Lauf) — weiter ohne Mockups

Briefing komplett gegen Code. `/workspace/sero-brand/` und `/workspace/sero-studio/`
weiter nicht auf dem Mac (Downloads, Desktop/SERO, iCloud, Pictures). Teil B 1:1
und D2-Brand-Icon deshalb weiter ohne Pixel-Lock.

| Fix ohne Mockup | Stand |
|---|---|
| 11c Profil-Skeleton | Name/Mail/Einstellungen sofort aus `state.me`; Skeleton nur auf den Stats. |
| B12 Badge | Default „Entwurf“, sonst Aktiv / Verkauft / Wunsch. |
| B12 Hero | `refreshColHubFromSales` schreibt die Sammlungs-Zahl nicht mehr um. Kein +%/Grün. |
| B14 Verkaufen | Keine vier Kreise. Suche/Filter/Sort als Text. Segmente ohne Zähler. Badge Satzfall. Fotografieren-Pille wenn gefüllt (nicht Verkauft). |
| eBay-Logo | Listing-Kicker ohne `ebayMarkHtml`. Tab bleibt Preisschild. |
| Scrub | Zahl über Datum (`col-top-main` Spalte, tabular). |

Teil-A-Fixes, Sofortkauf-Tippen, Location/UUID unverändert.
`listingPaintKey` / `listingInputBusy` unverändert. `kv['dry_run']` unangetastet.
Kein Commit. Kein Live-Listing.

Pins: `sero.js?v=251`, `sero.css?v=162`, `sero-clean.css?v=39`,
`sero-profile.js?v=22`, `manifest.webmanifest?v=7`.
Suite: 777 passed, 4 skipped.

Nur mit Mockups/Brand: B 1:1-Pixel, D2 Brand-`icon.png` + iPad-Startup.
C6 Login erst beim Speichern: kleinster Slice da (vierter Lauf).

## Auftrag 30.08. (zweiter Lauf) — Teil B + D2

Weiter nach Svens „dann mach weiter“. `/workspace/sero-brand/` und
`/workspace/sero-studio/` auf dem Mac nicht gefunden (Downloads, Desktop,
Documents, ebay-bot, sero-*, listo-*). Teil B deshalb aus PDF-Text + Clean-Skin,
ohne erfundene Pixelmaße. D2 aus vorhandener Chrome-Wordmark und `app-icon.png`.

| Schritt | Stand |
|---|---|
| B12 Sammlung | Keine vier Header-Kreise. Große Zahl + Pille „N Stück“. Hairline-Kurve 160 px. Chips 7T/30T/1J (30T an). Scrub: Zahl über Datum. Wenig History: flache Strecke + „Verlauf ab dem ersten Scan“. Kein Grün/+%. 2×2, 16 pt Gutter, Foto ≥60 %, ganzes Objekt. Titel zwei Zeilen ohne Ellipse. Badge Entwurf/Aktiv. Gestricheltes Fotografieren-Tile. Suche/Filter/Sort als Text in der Inv-Leiste. |
| B13 Scannen | No-Cam-Copy „Keine Kamera an diesem Gerät.“ + Mediathek. Review: „Prüfen.“ / „Das Foto wird der Entwurf.“ / „Als Entwurf behalten“ / „Nochmal fotografieren“. Foto als abgerundetes Quadrat. |
| B14 Verkaufen | Labels Entwurfswert / Live / Erlös. Segmente mit Unterstrich. Empty-Copy und 0,00 € unverändert. |
| B15 Profil | Hub: Kugel, Name, Mail, eine Testphase-Zeile, Stats Aktiv/Besitz/Verkauft, genau eine Zeile Einstellungen. Settings-Liste: eBay / Darstellung / Preisalarme / Daten / Hilfe / Rechtliches. Konto und Über SERO weiter erreichbar. Portfolio-Hintergrund und Glas-Zeile raus. |
| D2 Startup | `apple-touch-startup-image` 1170×2532 und 780×1688 (Schwarz + Wordmark). Manifest-Icons ehrlich 192/512/1024 + maskable 512. Brand-`icon.png` fehlt weiter — bestehendes `app-icon.png` genutzt, nicht neu gezeichnet. iPad-Startup nicht im Tree, nicht erfunden. |

Teil-A-Fixes und Sofortkauf-Tippen/Location nicht zurückgebaut.
`listingPaintKey` / `listingInputBusy` unverändert. `kv['dry_run']` unangetastet.
Kein Commit. Kein Live-Listing.

Pins: `sero.js?v=250`, `sero.css?v=162`, `sero-clean.css?v=38`,
`sero-profile.js?v=21`, `manifest.webmanifest?v=7`.
Contabo 30.08. zweiter Lauf: `sh scripts/deploy_contabo.sh`.

## Auftrag 30.08. — Listing-Blocker + SR raus

Auftrag aus `SERO-CURSOR-ALLES-2026-08-30`. Working Tree = Contabo-Live
(Pins 248/160/36 vor diesem Lauf). Git-HEAD ist der Landing-Commit vom 15.08.
(App-Arbeit war uncommitted) — nicht September-Code. Markdown-Briefing war
TCC-gesperrt; PDF gelesen. `/workspace/sero-brand/` und `/workspace/sero-studio/`
fehlen — Teil B 1:1-Mockups und D2-Icon-Export nicht nachgebaut.

| Schritt | Stand |
|---|---|
| A1 Einstellen hängt | eBay-Gate vor dem Lauf; 20 s Timeout; Button „Wird vorbereitet…“; Fehler + Retry; kein stiller Auto-Start; Editor sobald Titel vom Stück da ist. Kein Auto-Publish. |
| A2 Stück entfernen | Confirm-Sheet „Stück entfernen?“ / Abbrechen / Entfernen. Undo unverändert. |
| A3 Profil-Zurück | Erste Ebene `settingsNav.push` statt `openRoot`. Kind → Hub → Sammlung. |
| A4 Favorit | Ein Tap, sofort sichtbar, kein `refreshDetail`. |
| A5 Freistellen | Graue Zeile unter Thumbs + „Nochmal freistellen“. Sheet bleibt offen. |
| A6 Detail-Chips | Bottom-Padding 132 px + Safe-Area. |
| A7 Hell malt | `themeIsDark` + echte Light-Tokens. Haken = gespeicherte Wahl. Auto folgt System. |
| A8 Scannen | Fläche tippbar; ohne Kamera Mediathek (kein Toast); „Alle anzeigen“ bleibt auf Scannen; Batch/Sammlung über `startScanMode`. |
| A9 Toast/Taps | Toast über der Tab-Bar, `pointer-events` nur auf der Aktion. |
| A10 AGB | „SERO erstellt …“ in `listo-website/legal.html`. Skeleton statt nacktem „Wird geladen …“. |
| 11d/11h Verkaufen | Empty-Copy exakt. Bei 0 Entwürfen `0,00 €`, keine vier Kreise. |
| D1/D3/D4/D5 | Splash + Empty: `wordmark-sero-chrome.png`. PTR = Hairline-Ring. `hero::after` weg. Manifest `#000000`. |
| C Onboarding | 3 Screens (Fotografieren / Prüfen / Sammlung), Skip, nur First-Run wenn Sammlung leer. |
| B Design 1:1 | **Nachgezogen** aus PDF + Clean-Skin (Mockups fehlen weiter). |
| D2 Startup-Images | **Da** — Startup aus Chrome-Wordmark; Icons aus vorhandenem `app-icon.png`. Brand-`icon.png` fehlt. |

Trading ohne UUID + Location Pflicht unverändert. `listingPaintKey` /
`listingInputBusy` unverändert. `kv['dry_run']` unangetastet (**false**).
Kein Commit in diesem Lauf. Kein Live-Listing.

Pins (erster Lauf): `sero.js?v=249`, `sero.css?v=161`, `sero-clean.css?v=37`,
`sero-profile.js?v=20`, `manifest.webmanifest?v=6`.
Contabo 30.08. erster Lauf mitdeployt (`sh scripts/deploy_contabo.sh`, keine `data.db`/`.env`).
AGB-Kopie zusätzlich nach `/opt/listo-website/legal.html`.
Hard-Reload `https://app.seromunich.com/app/`.
Wachen: `tests/test_cursor_alles_20260830.py` plus bestehende Listing-/Profil-Wachen.
Suite: 773 passed, 4 skipped.

## Sofortkauf-Einstellen: Tippen hält (29.08.)

Beim Review/Hochladen als Festpreis (Sofortkauf) lag das Problem nicht am
Trading-Pfad (`AddFixedPriceItem`, Location Pflicht, kein UUID — unverändert),
sondern daran, dass die App das Listing-Pane neu gebaut hat, während man
tippt: Poll alle 1,6 s (Analyse/Cutout), Preis-Sheet offen, Mindestpreis
bei jedem Tastendruck. Auf dem iPhone stirbt dann die Tastatur, Taps treffen
tote Knöpfe, „Übernehmen“ wirkt wie ein No-op.

| Ursache | Fix |
|---|---|
| `refreshDetail`-Poll remountet Review bei jedem JSON-Tick | `listingPaintKey`: nur malen wenn Preis/Titel/Format/Status sich ändern |
| Sheet-Feld verliert Focus durch `innerHTML` | `listingInputBusy` — kein Remount solange Input/Textarea fokusiert; nach Close nachziehen |
| `ebayOnly` hat das Listing-Pane gar nicht aktualisiert | `#detailListingBlock.innerHTML = ebayPane` (Hero bleibt) |
| Mindestpreis `oninput` → `doAction` nach 650 ms | nur noch `change`/`blur` |
| Unsichtbarer Toast mit `pointer-events: auto` | nur bei `.show` klickbar |
| iOS-Zoom auf 15px-Feld | Sheet-Inputs 17px, Mindestpreis 16px, `autocomplete=off` |

Kein Auto-Publish. `kv['dry_run']` unangetastet (**false**). Kein zweiter
Server auf 3000. Contabo: `sh scripts/deploy_contabo.sh`.
Pins: `sero.js?v=248`, `sero.css?v=160`, `sero-clean.css?v=36`.
Hard-Reload `https://app.seromunich.com/app/`.

Wachen: `tests/test_ebay_listing_stability.py`, `test_ebay_payload.py`,
`test_preflight.py`, `test_publish_claim.py`. `node --check frontend/sero.js`.

## Contabo = Testseite (stehende Regel, 27.08.)

`https://app.seromunich.com/app/` auf Contabo ist Svens **Testseite**, nicht
eine Produktion die man nie anfasst. Nach Frontend- oder Backend-App-Änderungen
`sh scripts/deploy_contabo.sh` mitfahren — nicht nur lokal `com.listo.web`.
Skript rsync’t **keine** `data.db` und **keine** `.env`. Landing
`seromunich.com` nur wenn `landing/` geändert. Mac-Port 3000 nicht anfassen.
Details: `docs/DEPLOY_CONTABO.md`.

**Deploy 27.08. (dieser Auftrag):** `sh scripts/deploy_contabo.sh` ok.
`sero-web` neu gestartet, Status `active`. Live-HTML
`https://app.seromunich.com/app/`: `sero.js?v=240`, `sero.css?v=153`.
Backend auf Disk: Admin-Login-Default `adminsero@sero.com` (Server-`.env`
setzt `SERO_ADMIN_EMAIL` nicht → Code-Default), Trading `AddFixedPriceItem`.
Kein Live-Listing, keine `data.db` überschrieben. Hard-Reload der Test-URL.

## Multi-Foto-Kamera Audit (27.08., zweiter Lauf)

Vorheriger Lauf hatte den Trading-Pfad und den Overlay-Rahmen, war aber nicht
vollständig gegen den Master-Prompt. Diesmal nur echte Lücken, kein Umbau
des Fertigen. `kv['dry_run']` bleibt **false**. Kein Live-Listing, keine
`data.db`. Contabo-Deploy: siehe Abschnitt oben (27.08.).

Was fehlte und jetzt da ist:

| Lücke | Fix |
|---|---|
| Overlay ohne Flip/Blitz | `#camFlip` / `#camFlash` (Torch nur wenn das Gerät es kann) |
| Crop/Drehen am 2. Foto schrieb auf Foto 0 | `_camIndex` an `uploadEditedPhoto` |
| Versand nur „Bereit“ | Policy-Name, Art, Kosten, Bearbeitungszeit, Standort, International, Abholung |
| Publish-Review nur 1 Foto | Strip aller Fotos, Hauptfoto, Felder inkl. Versand |
| Kamera-Verweigerung ohne Text | kurze deutsche Meldung, Mediathek bleibt |
| Mediathek-Duplikate | gleiche Datei (Name/Größe/Zeit) wird übersprungen |

Pins: `sero.js?v=240`, `sero.css?v=153`. Hard-Reload lokal `/app/`.
Tests: `test_ebay_payload.py`, `test_frontend_guards.py`, `test_scanner_first_guards.py` (102 in diesem Lauf).

## Admin-Login ohne OTP (27.08.)

`SERO_ADMIN_EMAIL` (Default in `web/social_auth.py`, case-insensitive): POST
`/api/login` und `/api/login-code` legen das Konto an falls fehlend und setzen
`listo_session` ohne Code/PIN. Signup mit derselben Mail ebenso. Andere Mails
unverändert über OTP. Erkennung nur Backend — Frontend reagiert auf `{ok: true}`,
kein Mail-Hardcode. `kv['dry_run']` unangetastet. Pin `sero.js?v=240`.
Tests: `tests/test_admin_login.py`. Lokal: `launchctl kickstart -k gui/501/com.listo.web`.
Contabo 27.08. mitdeployt — Admin-Mail dort über Code-Default (Server-`.env` setzt
`SERO_ADMIN_EMAIL` nicht).

## Multi-Foto-Kamera + eBay Trading API (27.08.)

Scan öffnet sofort die Kamera (kein Menü zuerst). Mediathek ist ein eigener
Button ohne `capture`. Bis zu 12 Fotos lokal, Index 0 = Hauptfoto. KI-Identify
nur auf dem Hauptbild. Neue Festpreis-Listings gehen über Trading
`AddFixedPriceItem` (Auktion: `AddItem`) — **nicht** Inventory `publishOffer`.
Trading-XML sendet keine `UUID` mehr und übernimmt `Item.Location`/`Country`
aus dem beim eBay-Setup angelegten Versandstandort; ein leerer Ort bricht vor eBay verständlich ab.
Alte Inventory-Offers bleiben stehen, kein Auto-Beenden. `kv['dry_run']` bleibt
**false**. Kein Live-Listing in diesem Auftrag, keine `data.db`-Änderung.
Contabo-Deploy 27.08. nachgezogen (siehe Abschnitt oben).

| Was | Jetzt |
|---|---|
| Scan | `#btnCamera` → `openCamCapture` / getUserMedia-Overlay wenn HTTPS |
| Mediathek | `#libraryInput` `multiple`, **ohne** `capture` |
| iOS-Kamera | `#cameraInput` einzeln + `capture="environment"` |
| Limit | `MAX_LISTING_PHOTOS = 12` (JS + `bot/ebay/payload.py`) |
| Reihenfolge | Pfeile, kein HTML5-DnD. Erstes Foto = Hauptfoto |
| Crop/Rotate | nicht-destruktiv (`edited`, Original bleibt) |
| HEIC | Client JPEG; Server pillow-heif + EXIF-Transpose; kein GPS im JPEG |
| Identify | `analyzer.analyze(_orig_photos[:1])`; Glance weiter `[0]`; Cutout alle |
| SKU | intern in der DB, nie im eBay-XML (kein CustomLabel, keine Item Specifics) |
| Versand | nur Business Policies (`SellerProfiles`), keine KI-Shipping-IDs, keine `ShippingDetails` |
| Neue Listings | Trading API, Seller-Hub-editierbar |
| Alte Inventory | Kennzeichen „über Inventory API verwaltet“; GET `/api/app/sales/inventory-managed` |
| Sync | GET vor App-Update; Konflikt wenn eBay ≠ Snapshot und ≠ App |
| App + Telegram | derselbe Publish-Kern (`execute_publish` + `trading_payload`) |

Offizielle eBay-Doku (Inventory API Overview): *„listings created through the
Inventory API cannot be edited through Seller Hub or any other listing
platform. Any revisions must be done through the Inventory API.“*
https://developer.ebay.com/api-docs/sell/inventory/overview.html

Readonly-Bestand lokal (nicht beendet): 13 Entwürfe mit `offer_id` und Status
published/ended (4 live, 9 ended). Kein Auto-End.

Pins: `sero.js?v=240`, `sero.css?v=153`, `sero-detail.js?v=6`,
`sero-mobile.js?v=4`, `sero-clean.css?v=30`, `sero-dark.css?v=22`.
Hard-Reload lokal `/app/` (kein Contabo in diesem Auftrag).

Wachen: `tests/test_ebay_payload.py`, `test_scanner_first_guards.py`,
`test_frontend_guards.py`, `test_publish_claim.py`, `test_sales_live_sync.py`.
Suite 27.08.: **744 passed**, 4 skipped.

Nicht testbar ohne Gerät / Sandbox-Token: iPhone-Kamera-Loop, Seller-Hub-Klick
auf ein frisches Trading-Listing, Live-`AddFixedPriceItem`.

## Mobile-Taps + Scan-Mehrfach (21.08.)

Kein iPhone am Rechner — Repro aus Code. `kv['dry_run']` bleibt **false**.
Kein Live-Listing, keine `data.db`.

| Fehler | Ursache | Fix |
|---|---|---|
| Löschen 4–5 Taps | Fertig-Leiste über „Stück entfernen“, Overlay fängt den nächsten Tipp, Pending nach 8 s weg während DELETE noch läuft | Menü ohne Fertig, Overlay sofort `pointer-events: none`, ein DELETE mit inflight-Lock, Item sofort aus Grid/Cache/Zähler |
| eBay-Leiste hängt | `position: sticky` im Scroll + Glass/Transform als Containing Block | Portal `#detailCtaDock` auf `#detail`, `position: fixed`, `bottom: var(--vv-keyboard)`, Padding am Content |
| Identität blockiert Listing | Confirm-Handler + Preflight-Warnungen | Handler/Texte/Preflight-Identity-Issues raus. Titel jederzeit editierbar. `pricing_ready` für Kartenpreise unverändert |
| Gelb „Bitte prüfen“ am Preis | Validierung las `price_source=estimate` statt gespeichertem Listing-Preis | Quelle ist `draft.price` (Komma/Punkt DE). Gültiger Preis = bestätigt, nur fehlender Preis rot, Tipp öffnet Preis-Sheet |
| Erster Tap tot | Overlay nach Sheet-Close, Handler ohne stopPropagation, Busy-Wire skip | Overlay lockert, 44px, ein click-Handler, Pending unlock bei Fehler |
| Scan nur ein Foto | `commitScanFast` hat das erste File sofort zum Item gemacht, `multiple` an der Kamera war wegen iOS raus | Kamera bleibt einzeln (iOS). Nach dem ersten Foto Sammler-Sheet: Weiteres Foto / Fertig. Tipp aufs Thumb = Hauptbild. Rest in `photos[]`. Galerie (`fileInput`) getrennt für Stapel |

Pins: `sero.js?v=235`, `sero-detail.js?v=6`, `sero-mobile.js?v=4`,
`sero.css?v=151`, `sero-clean.css?v=30`, `sero-dark.css?v=22`.
Hard-Reload `https://app.seromunich.com/app/`.

Wachen: `tests/test_ebay_listing_stability.py`, `test_preflight.py`,
`test_sero_detail.py`, `test_scanner_first_guards.py`.

## eBay-Pane: kein Flackern, keine Identity-Wand (20.08.)

Video-Repro **BLOCKED** (kein iPhone-Clip / Boss-Sakko-Screenshot im Assets-Ordner).
Root Cause aus Code + Screenshot-Texten: nach Preis-Übernehmen hat `doAction` immer
`refreshDetail(true)` → `detailBody.innerHTML` (Galerie + beide Panes neu).
Zusätzlich hat `openSheet` die App mit `recede` (scale 0.945) verkleinert — der
Bildbereich springt, sobald das Preis-Sheet aufgeht. iOS-Tastatur kommt obendrauf.
Oben lag die rote Banner-Wand (`lr-gate` + Preflight-Liste): dieselben Punkte
mehrfach („Noch nicht bereit“, „Identität bestätigen“, „Stück zuerst prüfen“,
„Identität unsicher“, „Preis festlegen“).

| Was | Jetzt |
|---|---|
| Preis/Titel/Format speichern | nur eBay-Pane, Hero bleibt, Scroll/Galerie-Index bleiben |
| Preis-Sheet | gleiche Instanz, kein Recede im Detail, Sheet über `--vv-keyboard` |
| Identity | kein Banner, kein Confirm-Zwang. Unsicher = gelb „Bitte prüfen“ am Feld, nicht blockierend |
| Fehlender Preis | am Preisfeld, nicht als Riesenblock |
| Publish-Knopf | kompakt „Noch n Angaben“ / „Bereit“. Tipp bei Lücken scrollt zum ersten Feld |
| Validierung | eine Quelle (`listingValidation` + Preflight mit field_id/type/severity/blocking/source) |
| Karten-Preise | `pricing_ready` / Katalog-Gates unverändert |
| Requests | `detailWins` Abort + Generation, Preflight-Dedup, `col_get` nach await |
| Publish | bestehender Preflight + Claim, idempotent, kein Auto-Publish |

Pins: `sero.js?v=234`, `sero-detail.js?v=5`, `sero-mobile.js?v=4`,
`sero.css?v=150`, `sero-clean.css?v=29`, `sero-dark.css?v=22`.
Hard-Reload `https://app.seromunich.com/app/`. `kv['dry_run']` bleibt **false**.
Kein Live-Listing in diesem Auftrag. iPhone-Video-Ablauf auf Prod: nicht testbar
ohne Gerät.

Wachen: `tests/test_ebay_listing_stability.py` (18 Fälle), `test_preflight.py`,
`test_sero_detail.py`, `test_scanner_first_guards.py`.

## Scan-Kind vor Cutout (19.08.)

Jeder Scan klassifiziert **vor** dem Freistellen (Haiku-Glance, max. 12 s), nicht
erst nach der 90-s-Analyse. Cutout und volle Erkennung laufen danach parallel.
Kein Publish, keine `data.db`-Änderung, `kv['dry_run']` bleibt **false**.
Deploy `scripts/deploy_contabo.sh` + `systemctl restart sero-web`. Kein
Frontend-Pin (nur Backend). Hard-Reload `https://app.seromunich.com/app/`
für neue Scans.

| Glance | Warp | rembg |
|---|---|---|
| **product** (Flasche, Schuhe, Fernbedienung, Buch) | nein | `isnet-general-use` |
| **card** (Karte roh / Hülle) | ja, alte Rechteck-Technik (`slab_recut` auf die Kartenkanten) | BiRefNet + Rechteck-Vorlage; Hülle bleibt Sleeve-Pfad |
| **slab** (PSA/CGC/BGS/WATA-Case) | ja, Rechteck aufs **Case** (Karte im Fenster nicht entbiegen) | `isnet-general-use`; Warp/QA-Fail → rembg-only, nie Original liegen lassen |

Unsicherer Glance: flaches Rechteck im Bild → card/slab, sonst product.
Felder `domain` / `graded` / Identity stechen den Glance. Analyse kann
nachziehen (Alltag ohne Warp, Rohkarte mit Rechteck, Slab-Case).

Wachen: `tests/test_pipeline_flags.py` (Glance vor `crop_photos`),
`test_render_standard.py` (Karten-Warp bleibt, Slab nicht Innenkarte),
`test_cutout_layout.py` (product skip warp, raw takes rectangle).
Suite: 709 passed, 1 skipped.

## Cutout immer, Warp-Fail → rembg-only (18.08. spät)

Drei neueste Uploads auf Contabo nach Ace/Augustiner/Adidas. Fotos angesehen.
Backup `/opt/sero/backups/data-pre-cutout-fallback-20260818.db`. Kein Publish,
`kv['dry_run']` bleibt **false**. Apple-Remote nicht angefasst. Deploy
`scripts/deploy_contabo.sh` (kein data.db-Wipe), `systemctl restart sero-web`.
Hard-Reload `https://app.seromunich.com/app/` (Pin `sero.js?v=233`).

| ID | Name | Cutout vorher | Jetzt |
|---|---|---|---|
| `03dcd2ddd83a` | Apple TV Siri Remote 2. Gen | perfekt, ohne Warp | unverändert (Referenz) |
| `c03c1e6d80f0` | Bitcoin macht Politik (Buch) | nein (Original auf Karton) | ja, rembg-only, Design `#0B0B0D` |
| `d691623351b6` | One Piece Portgas D. Ace P-074 CGC Pristine 10 | nein (Hand+Raum) | ja, Warp-Fail → rembg-only, Design `#0B0B0D` |

**Warum Buch skipped:** isnet hat nur die Schach-Dame vom Cover genommen
(`00_cut.png` 283×422). `bild_ok` verwirft unter 300 px Breite — Original
blieb in `photos`, Status `error`. Kein Warp-Skip-Bug: Identity war `generic`.

**Warum Karte skipped:** Hand + CGC-Slab. Warp+rembg lief, Slab-QA
(`bbox_touches_canvas`, Objekt am Fotorand) warf das brauchbare rembg weg
und löschte `00_cut.png`. Kein Fallback auf Alltag-QA. Logs:
`Freistellen ohne Ergebnis … (no_cutout)` in 17–21 s, kein OOM.

**Auto jetzt:** Jedes Stück bekommt einen Cutout-Job. Karte: Warp+rembg;
schlägt Warp oder Slab-QA fehl → rembg-only (Alltags-QA), nicht aufgeben.
Buch/Manga/Spiel/Alltag: kein Warp, nur rembg. Nimmt isnet unter 10 % der
Fläche (Cover-Detail), zweiter Versuch `u2netp`. Fehler bleibt `error` mit
Knopf „Nochmal freistellen“, nie still fertig. UI wartet auf
`cutout_status !== running` bevor der Scan-Treffer aufgeht.

**Nachgeschnitten:** Buch 626×977 (ganzes Cover, nicht die Figur), Karte
790×1280 (Case frei, Finger/Kante am Rand bleiben — ohne Warp). Listing-Ecken
`(11,11,13)` = `#0B0B0D`. Fernbedienung 305×730 unverändert.

Tests: `test_cutout_layout.py`, `test_draft_cutout_skip.py`,
`test_pipeline_flags.py`, `test_render_standard.py` (Karten-Standard bleibt:
Warp ohne Kosmetik, Slab-Format-Wache).

## Drei Abend-Uploads (18.08. spät)

Sven hat drei neue Scans auf Contabo (`https://app.seromunich.com`). Fotos
angesehen. Backup `/opt/sero/backups/data-pre-abend-uploads-20260818.db`.
Kein Publish, `kv['dry_run']` bleibt **false**. Hard-Reload
`https://app.seromunich.com/app/` (Pins `sero.js?v=232`, `sero-clean.css?v=28`).

| ID | Name | Preis | Cutout |
|---|---|---|---|
| `5438ea8a5bef` | Augustiner Lagerbier Hell 0,5 l | 2,00 € KI-Richtwert | ja, ohne Warp, Design `#0B0B0D` (Glas-Spiegelung am Fuß bleibt) |
| `8b36c7bb8062` | Adidas Campus Sneaker Used | 30 € KI-Richtwert | ja, unverändert (war schon gut) |
| `4daada957a4c` | One Piece Portgas D. Ace P-074 Best Selection Parallel CGC Pristine 10 | Wert unbekannt (`ROHPREIS_SLAB`) | nein |

**Augustiner:** Analyse hatte schon 2,00 € in `suggested_list_price_eur`, aber
`needs_review` (Kronkorken-Frage) hat den KI-Richtwert nie übernommen.
`00_cut.png` lag auf Disk, `photos` zeigte weiter das Original, Design war
die Küche — `bild_ok` wertete Transparenz als Schwarz. Neu freigestellt auf
dem Mac ohne Warp.

**Adidas:** Render gut. Domain None, gebrauchter Schuh ohne Größe — 30 €
unsicher, bitte prüfen.

**One Piece:** Name stimmt (nicht „Podcast DA“ — das ist Portgas D. Ace).
Hand + CGC-Slab + Blende: Warp+rembg hat das Case zerlegt. Kein LLM-Preis.
TCGplayer-Rohpreis 0,31 € am Slab → ehrlich unbekannt. Cutout-Fehler steht
in der UI; selbst freistellen geht jetzt.

**Pipeline:** Alltag bekommt den KI-Richtwert auch bei `needs_review`.
`bild_ok` rechnet RGBA auf Grau, nicht auf Schwarz. Recrop setzt
`cutout_status=error` statt still „done“ und lässt ein vorhandenes Cutout.
eBay-Pane: Knopf „Bilder bearbeiten“ + Tipp aufs Hero öffnet das
Freistellen-Menü.

## Kategorie-Chips nur im Filter (18.08. Nacht)

Sammlung und Verkaufen: keine permanente Chip-Zeile mehr (One Piece / Games /
Pokémon / Sonstiges / TCG Sonstiges). Dieselben Kategorien nur im Filter-Sheet,
Multi-Select, leer = alle. Badge zählt die Kategorie mit. Graph, 30-Tage-Delta,
Suche, Sort, Layout und Applied-Chips der anderen Facets bleiben. Pins:
`sero.js?v=231`, `sero.css?v=149`. Hard-Reload `http://localhost:3000/app/`
und Prod `https://app.seromunich.com/app/` — Filter öffnen, Kategorien liegen
oben im Sheet.

## Alltag ohne Warp + Scan-Tempo (18.08. Nacht, zweiter Anlauf)

Warp für flache Karten (Aufrichten, keine Kosmetik) lief auch auf Flaschen.
Vision (`detect_card`) bekam den Prompt „Du siehst eine Sammelkarte“ und hat
die Augustiner-Flasche als Slab behandelt — Perspektiv-Warp hat das Label
verbogen, rembg hat Stuhl/Tisch-Reste als Rechtecke mitgenommen, Design lag
auf Weiß statt `#0B0B0D`. Scan `352cd0914c37` dauerte **158,7 s**.

Route jetzt:

| Stück | Warp | rembg |
|---|---|---|
| Karte roh / Hülle | nein (nur Sleeve-Vorzuschnitt) | BiRefNet, Kante 1280 Prod / 2000 Mac |
| Graded/Slab | ja, dann rembg | `isnet-general-use`, 1280/2000 |
| Alltag (Flasche, Sneaker, Handy, `generic`) | **nein** | `isnet-general-use` als normaler BG-Remover, 1024 Prod / 1280 Mac, kein Polish/Studio |

Wachen: `should_warp` / `item_is_non_card` in `web/cutout_v2/routing.py`.
Schlanke Silhouette (Höhe/Breite > 2,2) wird nicht gewarpt. Nach der Analyse
wird ein Alltagsstück, das trotzdem als slab/raw schnitt, ohne Warp neu
freigestellt. `identify_card` entfällt bei `ProductKind.generic`.

Cutout und Claude-Erkennung laufen wieder **parallel** — rembg ist auf
Contabo im Kindprozess (`web.cutout_worker`), deshalb kein OOM wie am
Nachmittag (damals BiRefNet im uvicorn-Prozess). Ein Scan-Worker auf
Produktion bleibt. nginx `proxy_read_timeout 300s` war nicht die Bremse.

**Augustiner live:** `352cd0914c37` (neuer Scan, nicht die Trash-ID
`5832db05c3fd`). Neu freigestellt auf dem Mac ohne Warp, Design `#0B0B0D`
(Ecken 11,11,13). Vorher Cutout 354×988 (gewarpt, schmal), danach 654×1176.
Glas-Tisch-Spiegelung am Fuß bleibt — rembg sieht die Spiegelung als Teil
der Flasche; kein Extra-Studio. BOSS-Sneaker und Solana Seeker liegen in
`collection_photos/_trash/` (nicht mehr live), nicht neu gerendert.

Tempo ehrlich auf Contabo (8 GB CPU, kein GPU): Alltag **unter 40 s ist
realistisch** (isnet 1024 + Claude parallel, Messung Mac-Cutout 2,8 s warm).
Karten mit BiRefNet 1280 eher **40–70 s**. Die 158 s kamen vom sequentiellen
Pfad plus Warp. P50 über alle Scans hängt am Karten-Anteil.

Backup Contabo `/opt/sero/backups/data-pre-bottle-recut-20260818.db`.
`kv['dry_run']` bleibt **false**. Deploy `scripts/deploy_contabo.sh` (kein
data.db/.env/photos-Wipe). Kein Frontend-Pin (nur Backend + eine Datei).
Hard-Reload `https://app.seromunich.com/app/` damit die neuen Thumbs kommen.

Tests: `test_render_standard.py` (inkl. `test_non_card_skip_warp`),
`test_cutout_layout.py`, `test_draft_cutout_skip.py`, `test_pipeline_flags.py`.

## Drei Contabo-Alltags-Scans korrigiert (18.08. Nacht)

Die drei hängengebliebenen Scans auf **https://app.seromunich.com** waren falsch
erkannt, falsch bepreist und schlecht freigestellt. Fotos wurden angesehen
(Originale + Cutouts). Backup Contabo
`/opt/sero/backups/data-pre-alltag-fix-20260818.db`. Kein eBay-Publish,
`kv['dry_run']` bleibt **false**. Hard-Reload
`https://app.seromunich.com/app/` (kein Frontend-Pin, nur Daten + Cutouts).

| ID | Jetzt | Preis | Warum |
|---|---|---|---|
| `3325d5ed1470` | **Solana Seeker** (Solana Mobile) | 399 € KI-Richtwert | Seed Vault + Solana-Logo auf dem Foto. Alltags-Elektronik, UVP ca. 500 USD, kein Katalogbeleg — unsicher, bitte prüfen. Nicht „Smartphone 5G Silber“. |
| `5832db05c3fd` | **Augustiner Bräu München Lagerbier Hell 0,5 l** | 1,50 € KI-Richtwert | Normale aktuelle Flasche (MHD 12.26), kein Sammlerstück. Die 25,48 € kamen von PriceCharting „Hell Is Us“ (PS5). Gift-Zeile `h:a22aba260557f9c5` gelöscht. |
| `c3d0f99c9d69` | **BOSS Sneaker Herren Wildleder Beige** | 75 € KI-Richtwert | Logo BOSS auf dem Foto, Größe/exaktes Modell nicht lesbar. Unsicher, bitte prüfen. |

Bilder: gezieltes Re-Freistellen auf dem Mac (`kind=None`, BiRefNet, kein Warp-Kosmetik), dann `place_on_listing_bg` auf `#0B0B0D`. Vorher lagen die Design-JPGs noch auf Küche/Holz (Design vor Cutout wegen OOM). Halo am Rand bleibt bei Glas/Wildleder sichtbar, ist aber enger als zuvor. Nur diese drei, kein Bulk-Recut. *Die IDs liegen inzwischen in `_trash/`; der neue Augustiner-Scan ist `352cd0914c37` (siehe Abschnitt oben).*

Code: Prompt in `bot/claude_client.py` (Solana-Logo/SEED VAULT nicht wegwischen; keine Sammlerflasche bei normalem Bier). Alltagsprodukte (`ProductKind.generic`) gehen nicht mehr in den Preis-Katalog / PriceCharting. Ein bestehender KI-Richtwert wird nicht durch einen einzelnen eBay-Treffer überschrieben. Tests: `test_pricing.py`, `test_identity.py`, `test_identity_gates.py`.

## Onboarding-Tour: Chrome-Wordmark statt blauem Kreis (18.08. Abend)

Tour-Modal „Willkommen“ zeigt den Chrome-Schriftzug (`wordmark-sero-chrome.png`)
statt SR im blauen Kreis; Text Draft-first; Clean-Buttons `--glass-radius` 16px.
Pins: `sero.js?v=230`, `sero.css?v=148`, `sero-clean.css?v=27`. Hard-Reload
`http://localhost:3000/app/` und Prod `https://app.seromunich.com/app/`.

## Testmodus aus der App (18.08. Abend) — Mac + Contabo

Sven will immer live selbst testen. Der Testmodus ist aus der **App** weg:
kein Topbar-Badge „Testmodus“, kein Settings-Toggle, kein Banner „Testmodus
ausschalten“. Publish geht zu eBay und kostet **echte Gebühren**. Publish-
Claim, Preflight und Doppeltipp-Schutz unverändert.

Telegram `/dryrun on|off` bleibt als Notfall im Bot (nicht in der App).

Maßgeblich ist `kv['dry_run']` in der jeweiligen `data.db`, nicht `.env DRY_RUN`.
Beide Seiten **false** (JSON-Boolean). Default für neue Installs: `false`
(`bot/config.py`, `.env.example`). `scripts/deploy_contabo.sh` setzt dry_run
nicht auf true.

| Ort | DB | Wert |
|---|---|---|
| Mac | `~/ebay-bot/data.db` | `false` |
| Contabo | `/opt/sero/data.db` | `false` |

Lokaler Bot nach dem Setzen: `launchctl kickstart -k gui/501/com.listo.bot`.
Contabo-Web liest kv pro Request — kein `systemctl restart sero-web`.
Frontend rsync ohne Deploy-Skript (kein sero-web-Restart). Port 3000 nicht
als Zweit-Server.

Backup: Mac `backups/data-pre-testmodus-off-20260818.db` (und Stunden-Slot
`backups/data-21.db`); Contabo `/opt/sero/backups/data-pre-testmodus-off-20260818.db`.

Pins: `sero.js?v=229`. Hard-Reload lokal `http://localhost:3000/app/` und
Prod `https://app.seromunich.com/app/`.

## Branding: Chrome-Schriftzug + Blob-Icon (18.08. Abend)

Login und Topbar nutzen den **finalen** 3D-Chrome-Schriftzug
(`assets/wordmark-sero-chrome.png`, Original 1:1, kein Umfärben). Die Datei
wurde erneut durch das neue Original überschrieben (`?v=3`). App-Icon /
Favicon / PWA / Manifest unverändert: silbernes Blob-Auge (`app-icon.png`,
`apple-touch-icon.png`, `icon-512.png`, `?v=5`). Kein `filter: grayscale`
auf den Logos.

Login-Hero: groß Wordmark oben, darunter klein App-Icon **neben**
`Available Soon in App Store und Android` (Englisch bleibt, STR_EN-Key =
exakter String). Großes Maskottchen ist nicht mehr Login-Header. Formular
darunter unverändert (Glass 16px). Scan-Pipeline, dry_run, eBay-Publish
unangetastet.

Pins: `sero.js?v=229`, `sero.css?v=147`, `sero-clean.css?v=26`,
`sero-profile.js?v=14`, Icons `?v=5`, Wordmark `?v=3`. Hard-Reload lokal
`http://localhost:3000/app/` und Prod `https://app.seromunich.com/app/`.
Contabo: nur `frontend/` rsync, **kein** `deploy_contabo.sh`, kein
`systemctl restart` (Scan-OOM-Fix unangetastet). `data.db` / dry_run
nicht angefasst.

## Scan hängt auf Contabo (18.08. Abend) — OOM, nicht Claude

Drei Stücke auf **https://app.seromunich.com** blieben auf „Stelle Karte frei“ /
„wird analysiert“. Lokal (Mac) war nichts hängen. Ursache: `sero-web` auf
Contabo (8 GB, kein Swap) wurde beim Freistellen vom **OOM-Killer** beendet
(RSS 7,8 GB; Kills u. a. 20:22, 20:48, 20:57). In-Memory-Scan-Queue danach
leer, Status blieb `analyzing`. Nach Restart 10-Minuten-Schonfrist → Rescue
startet Cutout neu → wieder OOM.

Fix (kein Modellwechsel): Freistellen und Claude-Erkennung **nacheinander**;
auf Produktion ein Scan-Worker, kein Doppel-Warmup beider rembg-Modelle;
rembg-Kante 1280 px; rembg in **eigenem Kindprozess** (`web.cutout_worker`,
schlanke ONNX-Session) — OOM tötet uvicorn nicht; 2 GB Swap auf Contabo.
Nach Start nur `analyzing` sofort wecken, nicht `error` (sonst OOM-Schleife).
Die drei IDs `c3d0f99c9d69`, `5832db05c3fd`, `3325d5ed1470` werden beim
Restart geweckt, ohne Recut fertiger Alphas. `kv['dry_run']` für diesen
Fix auf **true** (Mac + Contabo). Hard-Reload der App-Domain, nicht neu scannen.

## Inventar: Suche, Filter, Sort auf Sammlung und Verkaufen (18.08. Abend) — NUR LOKAL

Auf **Sammlung** und **Verkaufen** (`tabSales`) sind Suche, Filter und Sort
wie ein Sammler-Inventar verdrahtet. Tabbar bleibt **Sammlung | Scannen |
Verkaufen**. Graph, Summe und 30-Tage-Delta unverändert. Kein Auto-Publish,
kein Contabo-Deploy.

- Header-Reihenfolge: Layout, Suche, Filter, Sort. Layout: 2-Spalten-Grid
  oder Liste (lokal gemerkt). Suche inline, Placeholder Sammlung
  `Titel, Set, Cert-Nr.`, Verkaufen `Titel, Artikelnummer`.
- Kategorien One Piece · Games · Pokémon · Sonstiges · TCG Sonstiges nur
  im Filter-Sheet (Multi-Select, leer = alle) — keine Chip-Zeile unter
  Graph oder Verkaufs-Tabs.
- Filter-Sheet (`#sheet`): Kategorie, Roh/Graded, Grader, Note, Sprache
  (TCG), Region (Games), Wert/Jahr. Badge zählt Sheet-Facets inklusive
  Kategorie. Applied-Chips nur für die anderen Facets plus
  `Alles zurücksetzen`.
- Sort Sammlung: Zuletzt hinzugefügt (Default). Verkaufen je Tab: Entwürfe
  Zuletzt bearbeitet, Live Bald endend, Verkauft Zuletzt verkauft.
- Leer: `Noch keine Stücke` / `Keine Treffer für „…“`. CTA
  `Artikel fotografieren`. Zähler `{n} Stück`.

Pins damals: `sero.js?v=227`, `sero.css?v=146`, `sero-clean.css?v=25`
(aktuell siehe Branding oben). Vorschau nach Hard-Reload
`http://localhost:3000/app/`.

## dry_run AUS / Live (18.08. Abend) — Mac + Contabo

Maßgeblich ist `kv['dry_run']` in der jeweiligen `data.db`, nicht `.env DRY_RUN`.
Auf Svens Wunsch beide Seiten **false** (JSON-Boolean). **Publish kostet echte eBay-Gebühren.** Kein Autopilot.

| Ort | DB | Wert |
|---|---|---|
| Mac | `~/ebay-bot/data.db` | `false` |
| Contabo | `/opt/sero/data.db` | `false` |

Lokaler Bot nach dem Setzen per `launchctl kickstart -k gui/501/com.listo.bot` neu gelesen. Contabo-Web liest kv pro Request — kein Restart. Deploy rsync’t keine `data.db`.

Backup: Mac `backups/data-21.db`; Contabo `/opt/sero/backups/data-pre-dryrun-off-20260818.db`.

## Login: Clean-Skin + silbernes Logo (18.08.) — ersetzt

Ersetzt durch Abschnitt **Branding: Chrome-Schriftzug + Blob-Icon**.
Altes Login-Hero war Maskottchen plus `wordmark-white.png` mit Grayscale.
Karte/Feld/Weiter bleiben Glass `--glass-radius` 16px. Login-Funktion
unverändert.

## Sammlung: 30-Tage-Veränderung unter der Summe (18.08.) — NUR LOKAL

Unter der großen Zahl auf der Sammlungsseite (`.ebay-hub-sum` / `#colHubSum`)
steht eine Zeile **Prozent · Euro**, grün bei Plus (`#30d158`), rot bei Minus
(`#ff453a`). Die große Summe selbst bleibt die Live-/Bestandssumme.

Zahlen kommen **nur aus schon geladenen Daten**, kein extra API-Call, kein
Katalog-Recalc, kein Claude:

1. Collection-Verlauf (`history` von `GET /api/app/collection`, schon da)
2. sonst kumulierte, datierte Sales-Punkte (`sold_at` / `ends_at` aus
   `GET /api/app/sales`, schon beim Start geladen)

Fehlt ein Punkt ≥ 30 Tage: ehrlich **„—“**, oder nur der Euro-Delta seit dem
ersten Punkt mit Label **„seit Start“**. Kein erfundenes Prozent. Bei
Ausgangswert 0 entfällt die Prozentzahl. Chart-Scrub ändert nur die große
Summe, das Delta bleibt auf dem Endwert.

Pins: `sero.js?v=226`, `sero.css?v=145`, `sero-clean.css?v=23`.
**Nicht nach Contabo ausgerollt.** Vorschau nach Hard-Reload
`http://localhost:3000/app/`.

## Clean-Skin: Tabbar etwas höher (18.08.) — NUR LOKAL

Glass-Tabbar bleibt content-breit mit `--glass-radius: 16px`; Buttons, Scan-Knopf und eBay-Marke sind leicht größer (ca. 54 px statt ~44 px), Safe-Area und Scroll-Abstand bleiben. Pin: `sero-clean.css?v=22`. **Nicht nach Contabo ausgerollt.** Vorschau nach Hard-Reload `http://localhost:3000/app/`.

## Clean-Skin: Glass-Radius wie App-Icon (18.08.) — NUR LOKAL

Tabbar, Sammlungs-Action-Buttons, Profil-Avatar, Verkaufs-Segmente und
Bulk-Upload-Leiste nutzen denselben Squircle-Radius (`--glass-radius: 16px`,
Innen `--glass-radius-sm: 12px`) statt `999px` / Kreis. Pin:
`sero-clean.css?v=21`. **Nicht nach Contabo ausgerollt.** Vorschau nach
Hard-Reload `http://localhost:3000/app/`.

## Clean-Skin: Frosted Glass (18.08.) — NUR LOKAL

Tabbar, die vier Sammlungs-Action-Chips und auf Verkaufen Segmented Control plus
Bulk-Upload-Leiste nutzen Frosted Glass (`--glass-bg` / `--glass-blur`, feine helle
Kontur, kein Hellblau). Hintergrund bleibt schwarz. Pin: `sero-clean.css?v=20`.
**Nicht nach Contabo ausgerollt.** Vorschau nach Hard-Reload `http://localhost:3000/app/`.

## Verkauf: Auswahl-Einstieg heißt Bulk-Upload (18.08.) — NUR LOKAL

Auf der Verkaufsseite (`tabSales`, Segment Entwürfe) heißt der Button, der
den Auswahlmodus startet, **Bulk-Upload** statt „Auswählen“ / „Select“.
Englisch: „Bulk upload“. „Auf eBay hochladen“ und die Review-Texte bleiben.
Pin: `sero.js?v=225`. **Nicht nach Contabo ausgerollt.** Vorschau nach
Hard-Reload `http://localhost:3000/app/`.

## Tab Verkaufen: eBay-Wortmarke, etwas breiter (18.08.) — NUR LOKAL

Clean-Tabbar bleibt **Sammlung | Scannen | Verkaufen**. HTML-Reihenfolge der
fünf Buttons unverändert; Start und Profil/eBay-Tab weiter hidden. Der
sichtbare **Verkaufen**-Slot (`tabSales`) ist etwas breiter (`flex` +
`min-width`) und zeigt in der Mitte die offizielle eBay-Wortmarke als
Inline-SVG (`tab-ebay-mark`, `currentColor`, `filter: grayscale(1)`) —
kein Dateiname mit `ebay`, kein Bag-Icon. Label darunter bleibt
„Verkaufen“. Pill weiter `width: max-content` für die drei Taps.

Pins: `sero.js?v=224`, `sero.css?v=144`, `sero-clean.css?v=19`.
**Nicht nach Contabo ausgerollt.** Vorschau nach Hard-Reload
`http://localhost:3000/app/`.

## Tab Verkaufen: Entwürfe default, Bulk-Review (18.08.) — NUR LOKAL

Clean-Tabbar zeigt **Sammlung | Scannen | Verkaufen**. HTML-Reihenfolge der
fünf Buttons unverändert (`tabHome | tabCollection | btnCamera | tabSales |
tabProfile`); Start und eBay/Profil bleiben per CSS hidden. Profil weiter
über den Avatar oben rechts. `tabSales` ist der bestehende Verkauf-Tab
(Label „Verkaufen"), kein zweites Sales-System.

Beim Öffnen immer Segment **Entwürfe** (`switchTab("tabSales")` setzt
`salesBucket` auf `draft`). Segmente Entwürfe / Aktiv / Verkauft mit echten
Zählern aus `GET /api/app/sales`. Draft-Zeilen: Foto, Titel, Zustand,
Format, Preis, Pflicht-Hinweis, Status. Tap öffnet den bestehenden Editor
(`openItemDetail(…, "ebay")`). Auswahlmodus, Review-Sheet mit Preflight,
Upload nur der gültigen über `POST /sales/publish-drafts` (Publish-Claim
unverändert, kein Auto-Publish, `publish_uncertain` nicht auto). Aktiv zeigt
`current_price` aus dem Sales-Sync. Verkauft neueste zuerst.

Pins: `sero.js?v=223`, `sero.css?v=144`, `sero-clean.css?v=18`,
`sero-profile.js?v=13`. **Nicht nach Contabo ausgerollt.** Vorschau nach
Hard-Reload `http://localhost:3000/app/`.

## eBay-Knopf öffnet Listing-Design als Hero (18.08.) — NUR LOKAL

Tipp auf den eBay-Knopf in der Preiszeile öffnet weiter das eBay-Pane
(`openItemDetail(id, "ebay")`). Die Galerie oben zeigt jetzt das **Design-Foto**
(`design_photo`, Listing-Bild auf Studio-Hintergrund) als erstes/aktives Bild;
ohne Design bleibt das Scan-Foto. Übersicht behält das Original-Scan-Foto als
Hero. Wechsel Übersicht | eBay tauscht nur die Hero-Reihenfolge, kein Recut,
kein `place_on_listing_bg` beim Öffnen, kein Auto-Publish. Tipp aufs Design
öffnet weiter die bestehenden Foto-Werkzeuge. Thumbs und Zoom bleiben.

Pins: `sero.js?v=222`, `sero-detail.js?v=4`, `sero.css?v=143`,
`sero-clean.css?v=17`. **Nicht nach Contabo ausgerollt.** Vorschau nach
Hard-Reload `http://localhost:3000/app/`.

## eBay-Knopf in der Preiszeile etwas größer (18.08.) — NUR LOKAL

SVG-Marke in der Karten-Preiszeile 18px hoch (Knopf 20px), im 4er-Raster
14px / 16px. Weiter in der Zeile: `flex-shrink: 0`, Preis kürzt mit
Ellipsis, kein Überstand über Preis oder Kartenrand. Hit-Area 44px über
`::after`. Tipp öffnet das eBay-Pane, kein Auto-Publish.

Pins: `sero.js?v=221`, `sero.css?v=143`, `sero-clean.css?v=17`.
**Nicht nach Contabo ausgerollt.** Vorschau nach Hard-Reload
`http://localhost:3000/app/`.

## eBay-Knopf passt in die Preiszeile (17.08. 23:30) — NUR LOKAL

Logo und Knopf sind an die Preis-Schrift gekoppelt (damals Marke 14px /
16px Knopfhöhe, in der 4er-Raster 11px / 14px). Preiszeile (`gfoot`) und
Karte haben `overflow: hidden`; der Betrag kürzt mit Ellipsis
(`min-width: 0`), der Knopf `flex-shrink: 0` ohne negativen Rand. SVG mit
`max-height` und `object-fit: contain`. Unsichtbare Hit-Area über `::after`
(44px), visuell nicht überstehend. Tipp öffnet weiter das eBay-Pane, kein
Auto-Publish.

Pins damals: `sero.js?v=221`, `sero.css?v=142`, `sero-clean.css?v=16`.
**Nicht nach Contabo ausgerollt.**

## eBay-Knopf in der Karten-Preiszeile (17.08. 23:24) — NUR LOKAL

Auf den Sammlungskacheln sitzt der eBay-Logo-Knopf nicht mehr auf dem Foto,
sondern in der unteren Meta-Zeile: links Betrag (`gval`), rechts der Knopf
(`g-ebay`), vertikal mittig. Tipp öffnet weiter das eBay-Pane
(`openItemDetail(id, "ebay")`), kein Auto-Publish. Live-Badge „auf eBay“
bleibt auf dem Foto (`g-ebay-live`).

Pins damals: `sero.js?v=221`, `sero.css?v=141`, `sero-clean.css?v=15`.
**Nicht nach Contabo ausgerollt.** Vorschau nach Hard-Reload
`http://localhost:3000/app/`.

## Sammlungskarten: kein Zustand, Live = eBay-Marke (17.08. 23:20) — NUR LOKAL

Auf den Kacheln (Grid und Liste) steht kein Zustand mehr: kein „used",
„Gebraucht", „excellent", „sehr gut". Das eBay-Formular behält Zustand.
Kein Design-Punkt / Badge für `design_photo` — automatisches Design bleibt
Standard, die Pipeline läuft weiter.

Live auf eBay (`draft_status === published`, sonst `item_url` / Listing-Id):
statt grünem Punkt „Live" steht **„auf eBay"** mit dem offiziellen
eBay-Wortmarken-SVG (Inline wie die Tabbar, `currentColor`, Clean-Skin
grau/weiss). Kein Dateiname `*ebay*`.

Unten rechts auf der Karte (Preiszeile, nicht Foto): kleiner eBay-Knopf
(~36px). Tipp öffnet die bestehende Detailseite direkt auf dem eBay-Pane
(`openItemDetail(id, "ebay")` → Segment sell). Listing-Formular unter dem
Hero, Kopf bleibt. Listen weiter nur über den bestehenden Preflight-Knopf —
kein stilles `publishOffer`, kein Autopilot.

Pins: `sero.js?v=221`, `sero.css?v=141`, `sero-clean.css?v=15`.
**Nicht nach Contabo ausgerollt.** Vorschau nach Hard-Reload
`http://localhost:3000/app/`.

## Listing-Studio dunkelgrau = Hintergrund 3 (17.08. 23:10) — NUR LOKAL

Wo hinter Freistellern Weiß oder Kaltweiß lag, gilt jetzt **Hintergrund 3**
der Listing-Wahl (Verkaufsvorlage Weiß / Warmweiß / **Schwarz**): `#0B0B0D`.
Cutout bleibt PNG mit Alpha; nur die Studiofläche dahinter. Kein Recut,
kein rembg, kein Warp, kein Batch über gespeicherte weiße Designs.

UI (Clean-Skin): Galerie, Thumbs, Collection-Kacheln, eBay-Studio —
`--listing-bg` / `--thumb-bg` Default `#0B0B0D`. Render-Default
`DEFAULT_LISTING_BG` / `DEFAULT_BG_COLOR` dieselbe Farbe; Verkaufsvorlage
`bg: black`. Weiß bleibt wählbar. Neue Designs / neue Wahl; bestehende
gespeicherte `listing_bg` und gerenderte JPEGs unverändert.

Pins: `sero.js?v=219`, `sero-clean.css?v=13`. **Nicht nach Contabo
ausgerollt.** Vorschau nach Hard-Reload `http://localhost:3000/app/`.

## eBay-Knopf + klappbare Beschreibung (17.08. 23:00) — NUR LOKAL

Übersicht-Knopf: zuerst das offizielle eBay-Wortmarken-SVG (Inline), rechts nur
„einstellen“. `aria-label="Auf eBay einstellen"` für Screenreader. Flex-Richtung
`row`, Logo `order: 0`, Text `order: 1` — nichts schiebt das Logo nach hinten.

eBay-Pane: Beschreibung wie ein Listing-Text (Absätze, Leerzeilen, nummerierte
Blöcke; vorhandene `\n` bleiben). Ohne Breaks lokal umgebrochen, keine neuen
Sätze, kein Zustand in der Beschreibung. Vorschau mit `<p>`/`<ol>`, standardmäßig
auf etwa 5 Zeilen mit „Mehr“ / „Weniger“. Tipp auf die Vorschau oder „Bearbeiten“
öffnet den bestehenden Text-Editor (echte Zeilenumbrüche, Sell-Editor unverändert).

Pins: `sero.js?v=218`, `sero-detail.js?v=3`, `sero-clean.css?v=12`.
**Nicht nach Contabo ausgerollt.** Vorschau nach Hard-Reload
`http://localhost:3000/app/`.

## Detailkopf bleibt, nur unten wechselt (17.08. 22:50) — NUR LOKAL

Ein Overlay, zwei Panes unter dem Hero (`data-pane=overview|ebay`). Navigation,
voller Titel und grosse Galerie inkl. Thumbs bleiben beim Wechsel Übersicht | eBay
stehen. Horizontaler Swipe tauscht nur die Fläche unter Bild+Titel; iOS-edge-swipe
und Galerie-Wischen bleiben ausgenommen.

Übersicht darunter: SERO-Preis (nur Belege, sonst ehrlich „Wert unbekannt"),
reichere SERO-Notes aus gespeicherten Feldern (Set, Nummer, Jahr, Variante, Grade,
Scan-Text — keine Lore, keine KI, kein Preis-API), Details-Chips ohne Zustand/
Kaufpreis/Bestand. Bestand als Pill oben („3 Stück"). Button: eBay-Wortmarke
(Inline-SVG) plus „einstellen". Block „Mein Exemplar" ist aus der Übersicht raus.

eBay darunter: bestehender Listing-Editor in Clean-Karten (Titel, Beschreibung
aus Notes/Scan, Preis nur wenn belegt, Kaufart, Stückzahl, Zustand, Kategorie,
Pflichtmerkmale, Versand). Hero-Bild auf diesem Segment tippbar zum Bearbeiten
(Zuschnitt, Drehen, Hintergrund, Freistellen). Kein Recut beim Öffnen, kein
Auto-Publish, unsichere Entwürfe nicht auto-republish.

Pins: `sero.js?v=217`, `sero-detail.js?v=2`, `sero-clean.css?v=11`,
`sero-mobile.js?v=3`. **Nicht nach Contabo ausgerollt.** Vorschau nach
Hard-Reload `http://localhost:3000/app/`.

## Detailseite SERO-Look (17.08. 22:40) — NUR LOKAL

Stück-Detail (`#detail`) im Clean-Skin: Zurück, Scroll-Titel in der Bar,
Teilen / Favorit / Mehr. Grosse Galerie mit Thumbs und Zoom (bestehendes
Lightbox + Pinch). Segment **Übersicht | eBay**. Übersicht: SERO-Preis-Card
(nur gespeicherte `price_state` / `price_reason` / Comps, nie LLM), klappbare
SERO-Notes (nur vorhandene Felder, keine erfundenen Sätze), Details-Chips,
fester Knopf „Auf eBay einstellen“ wechselt nur das Pane. eBay-Pane bleibt
der bestehende Verkaufs-Editor / Preflight. Keine neuen APIs, kein Recut beim
Öffnen, kein Auto-Publish, kein Courtyard-Name, keine Dollar-Defaults.
Logik in `frontend/sero-detail.js` (lokal, deterministisch).

Pins: `sero.js?v=216`, `sero-detail.js?v=1`, `sero-clean.css?v=10`,
`sero-mobile.js?v=3`. **Nicht nach Contabo ausgerollt.** Vorschau nach
Hard-Reload `http://localhost:3000/app/`.

## Chart-Scrub + Filter-Kategorien + Detail + Tabbar durchlaufend (17.08. 22:00) — NUR LOKAL

Sammlung oben: große Summe und Revolut-Linie (~240px, vollbreit) aus
`GET /api/app/sales` (`ebayHubChartValues` / kumulierte ended prices). Finger
oder Maus auf der Linie setzt die Summe auf den Punkt darunter; Loslassen
zurück auf Live-Summe `stats.value_active` bzw. letzten Chartpunkt. Kein
Chart.js. Unbekannte Werte bleiben „—“.

Kategorie-Chips (One Piece, Pokémon, Games, …) nicht mehr oben auf der
Sammlung — dieselben Kategorien liegen im Filter-Sheet. Leere Kategorien
werden nicht gezeigt. UI-Label „Weitere Karten“ statt „TCG Sonstiges“.

Stück-Detail: **Übersicht** = eigenes Foto, Name, Marktwert
(`price_state` / `price_reason`), kurze Meta (Zustand, Menge, Notiz).
**eBay** = Listing-Design (Studio-Foto, `listing_bg`), Titel/Preis, bestehender
Verkaufs-Editor. Kleine eBay-Wortmarke nur als Abschnittsmarke. Kein Recut,
kein Auto-Publish, kein iFrame.

Tabbar: keine Mask-Fade, kein extra `padding-bottom` auf `.tab-page`. Content
läuft hinter der Pill durch; nur so viel Scroll-Padding, dass das letzte Stück
über der Pill tippbar bleibt. Sichtbar weiter nur **Sammlung | Scan**.
HTML-Reihenfolge der 5 Buttons unverändert. Kein Maskottchen, kein eBay-Tab.

Pins: `sero.js?v=215`, `sero-profile.js?v=12`, `sero-clean.css?v=9`.
**Nicht nach Contabo ausgerollt.** Vorschau nach Hard-Reload
`http://localhost:3000/app/`.

## Maskottchen weg + Tabbar nur so breit wie die Taps (17.08. 21:40) — NUR LOKAL

Silbernes Maskottchen komplett aus der App: `sero-mascot.js` wird nicht mehr
geladen, kein Dock, kein Blob hinter der Tabbar. CSS für `.sero-mascot` /
Motion-Blur / Dock-z-index ist raus. Datei `frontend/sero-mascot.js` und
Asset `frontend/assets/sero-mascot.png` liegen ungenutzt.

Tabbar bleibt unten (safe-area), sichtbar weiter nur **Sammlung | Scan**.
HTML-Reihenfolge der 5 Buttons unverändert; Home/Sales/eBay per CSS hidden.
Pill ist `width: max-content` — nur so breit wie die zwei Taps, zentriert,
kein 340px-Balken mit Leerraum. Tabs `flex: 0 0 auto`, etwas flacher
(min-height 36px). Scan bleibt der Mitte-Knopf, der die Kamera öffnet.

Sammlung: eigene Stücke oben. Keine Live-/Verkauft-Listen über dem Grid.

Pins: `sero.js?v=214`, `sero-profile.js?v=12`, `sero-clean.css?v=8`.
**Nicht nach Contabo ausgerollt.** Vorschau nach Hard-Reload
`http://localhost:3000/app/`.

## Maskottchen + flache Tabbar + Sammlung-Grid (17.08. 21:40, vorher) — NUR LOKAL

Silbernes SERO-Blob gleitet hinter der Pill-Tabbar (obere Hälfte sichtbar,
Augen über der Kante). Drei Positionen: Sammlung / Scan / rechtes Drittel
der Pill — ohne den eBay-Tab wieder einzublenden. Modul
`frontend/sero-mascot.js`, Asset `frontend/assets/sero-mascot.png`.

Tabbar flacher (min-height 44px). Sichtbar weiter nur **Sammlung | Scan**.
HTML-Reihenfolge der 5 Buttons unverändert.

Sammlung: eigene Stücke wieder oben. Kleine Summe + kurze Linie + Kategorie-
Chips, danach das Grid. Keine Live-/Verkauft-Listen mehr über den Stücken.

Pins: `sero.js?v=214`, `sero-profile.js?v=12`, `sero-clean.css?v=7`,
`sero-mascot.js?v=1`.
**Nicht nach Contabo ausgerollt.** Vorschau nach Hard-Reload
`http://localhost:3000/app/`.

## Sammlung-Hub + Scan-Fix (17.08. 21:18) — NUR LOKAL

**Scan war ein Bug plus Absicht:** Der Scan-Knopf öffnet absichtlich die Kamera
(kein leerer Scan-Tab). Danach kam oft nichts Sichtbares, weil andere Wege
(`emptyAdd`, Home, Tour, Stapel) auf die versteckte Scan-Seite `tabScan`
wechselten — Titel im Clean-Skin unsichtbar, grauer Kasten, kein Sheet.
Zusätzlich hatte `#cameraInput` `multiple`, das auf iOS den Kamera-Rückweg
stören kann. `watchNew` überschreibt das Fertig-Sheet nicht, wenn
`scanChoiceShown` gesetzt ist.

Fix: Kamera bleibt Mitte-Tipp. Nach Einzelfoto → Sammlung + Sheet
(Weiter scannen / Entwurf / Sammlung). `emptyAdd` und die anderen Scan-Wege
öffnen die Kamera, ohne `tabScan`. `multiple` nur noch bei der Galerie.
Tab-Wischen landet nicht mehr auf versteckten Seiten.

Tabbar sichtbar nur **Sammlung | Scan**. HTML-Reihenfolge der 5 Buttons
unverändert. Start, Listings und eBay-Tab per CSS `display:none`
(`tabHome`, `tabSales`, `tabProfile` / `.tab-ebay`). SERO-Profil weiter über
den Avatar (`openSeroProfile`).

Sammlung oben: eBay-Wortmarke (Inline-SVG), Live-Summe und Linie aus
`GET /api/app/sales` (`stats.value_active` / sonst Verkaufserlös, sonst „—“),
darunter kompakte Live-/Verkauft-Zeilen. Kategorie-Chips mit Pokémon- und
One-Piece-Wortmarke (`frontend/assets/logo-pokemon.svg`,
`logo-onepiece.svg`), Games und weitere echte Kategorien. UI-Label
„Weitere Karten“ statt „TCG Sonstiges“. Grid darunter.

Stück-Detail: Segment **Übersicht | eBay**. eBay = Listing-Design
(Studio-Foto, Preis/Titel, bestehender Verkaufs-Editor). Kein Recut, kein
Auto-Publish, kein iFrame.

Pins: `sero.js?v=213`, `sero-profile.js?v=12`, `sero-clean.css?v=6`.
**Nicht nach Contabo ausgerollt.** Vorschau nach Hard-Reload
`http://localhost:3000/app/`.

## eBay-Hub Revolut (17.08. Abend) — NUR LOKAL

Tabbar sichtbar **Sammlung | Scan | eBay**. Scan bleibt der große Knopf in der
Mitte (`#btnCamera`, CSS `order: 2`). eBay rechts (Inline-SVG, Label „eBay“,
`order: 3`). HTML-Reihenfolge der 5 Buttons unverändert
(`tabHome | tabCollection | btnCamera | tabSales | tabProfile`); Start und
Listings bleiben im DOM, per CSS `display:none`.

Tipp auf eBay öffnet **kein SERO-Profil** mehr, sondern den eBay-Hub in
`tabProfile`: große Live-Summe, SVG-Linie aus Sales-Daten, darunter Designs /
Live / Verkauft. Zeilen öffnen das bestehende Detail. Kein iFrame, kein
Scraping, kein Link „öffne eBay-Profil“. Daten nur aus `/api/app/sales`,
Sammlung (`design_photo`) und `me.ebay_shop`. Summe = `stats.value_active`
(sonst Verkaufserlös `stats.value_sold`, sonst „—“). Linie = kumulierte
`ended.sold_price` nach `sold_at`/`ends_at`; bei wenigen Punkten 0 → vorhandene
Live-/Sold-Werte, nicht random.

SERO-Profil (Konto, Einstellungen, Tarif) nur noch über den Avatar oben rechts
(`openSeroProfile` → Overlay `settingsView` / `renderProfile`).

Pins: `sero.js?v=212`, `sero-profile.js?v=11`, `sero-clean.css?v=5`.
Tipp auf eine Zeile öffnet das Stück zum Bearbeiten (Live/Verkauft: Verkauf-Ansicht,
Design: Sammlungsdetail). Linie grün wenn die Summe steigt, sonst rot.
**Nicht nach Contabo ausgerollt.** Vorschau `http://localhost:3000/app/`
(Hard-Reload).

## Clean Overlay Tabbar eBay-Hub (17.08. Nacht) — NUR LOKAL

Logo links, Wordmark grau/weiss (`grayscale` + `brightness(1.8)`). Tabbar
sichtbar **Sammlung | eBay | Scan** (HTML-Reihenfolge der 5 Buttons unverändert:
Start/Listings bleiben im DOM, per CSS hidden). eBay-Marke als Inline-SVG
(`tab-ebay-mark`, `filter: grayscale(1)`, currentColor), öffnet `tabProfile`.
Profil-Hub: Live / Entwürfe / Verkauft / Portfolio / Sammlung, darunter
Einstellungen. Pins: `sero.js?v=210`, `sero-profile.js?v=10`, `sero-clean.css?v=3`.
**Nicht nach Contabo ausgerollt.**

## Clean Overlay schwarz/weiss (17.08. Abend) — NUR LOKAL

Backup vorher:
- Mac: `backups/data-pre-clean-ui-20260817.db`
- Contabo: `/opt/sero/backups/data-pre-clean-ui-20260817.db` und
  `app-pre-clean-ui-20260817.tgz`

Look wie Strike/Revolut: reines Schwarz, weisse Primaerknöpfe, graue Karten,
unten nur **Sammlung + Scan**, Profil oben rechts. Start/Listings bleiben
im Profil erreichbar. Skin: `frontend/sero-clean.css`, Klasse `skin-clean`.
Pins: `sero.js?v=209`, `sero-profile.js?v=9`, `sero-clean.css?v=2`.
**Nicht nach Contabo ausgerollt** — Vorschau `http://localhost:3000/app/`.

**Feinschliff 17.08. (Nacht) — Logo, Login, Scan-Tempo:**
- Header: weißes Wordmark zentriert (kein Text, kein Brightness-Filter).
- Login: Wordmark oben, E-Mail-Feld als ein grauer Block, weißer Knopf darunter.
- Einzelfoto nach Scan: Upload + Sammlungsstück sofort, dann Sheet mit
  Weiter scannen / Mit dem Entwurf fortsetzen / In der Sammlung anschauen.
  Kein eBay-Listing dabei. `sero.js?v=209`, `sero-clean.css?v=2`.

## Sammlungsfotos Contabo (15.08.) — KRITISCH

Beim Contabo-Deploy wurde `collection_photos/` bewusst ausgeschlossen
(`scripts/deploy_contabo.sh`). Zusätzlich speichert die DB **absolute
Mac-Pfade** (`/Users/smorty/ebay-bot/collection_photos/…`). Auf dem Server
fehlen die Dateien und/oder `Path.exists()` schlägt fehl → Sammlung ohne
bzw. mit „neuen“ Bildern.

- Mac-Originale liegen unter `collection_photos/` (~52 Items, ~500 MB ohne
  `_trash`) und sind Source of Truth für Bilder.
- Restore: `scripts/restore_photos_contabo.sh` (rsync Fotos + Symlink
  `/Users/smorty/ebay-bot` → `/opt/sero`, Contabo-DB-Backup remote, Mac-DB
  unberührt, kein Recutout). Braucht `ssh-add ~/.ssh/id_ed25519`.
- Stand Agent: SSH BatchMode ohne Passphrase blockiert — Restore noch nicht
  ausgeführt.

## Landing Sitewerk-Stil + Listo-Texte (15.08. Nachmittag)

- **Sitewerk-Vorlage:** `~/Downloads/sitewerk-logo-galerie.html` (Unbounded,
  warmes Dunkel `#151310` / `#F2EFE9`) — daraus neuer Look in `landing/`
- **Texte:** Nutzen/FAQ/Rechnung aus `~/listo-website` auf SERO umgeschrieben
  (Scanner-first: Scannen → Prüfen → Bei eBay verkaufen; kein Listo, kein „Wir“,
  keine Ausrufezeichen/Emojis im Fließtext)
- **CTAs:** App-Store-Badge „Available Soon“ (kein Store-Link); Button
  „Direkt zur App“ → `https://app.seromunich.com/app/`; Abschnitt
  **Zum Home-Screen hinzufügen** (iOS Safari / Android Chrome)
- Logos frisch aus `frontend/assets/` nach `landing/assets/`
- CSS-Pin: `landing.css?v=2`
- **DNS noch Shopify** (Apex `23.227.38.32`) — Contabo-Landing bereit, Apex
  zeigt erst nach DNS-Umstellung die neue Seite (`docs/DEPLOY_CONTABO.md`)
- Deploy: `sh scripts/deploy_contabo.sh --landing-only` (SSH-Key muss geladen
  sein: `ssh-add ~/.ssh/id_ed25519`)

## Landing + DNS + Auth (15.08.)

Produktentscheid: **seromunich.com (Apex)** = SERO-Landing auf Contabo
(`169.58.182.35`), **kein Shopify-Shop** mehr unter dieser Domain — DNS
noch umzustellen (siehe Abschnitt darüber).
**app.seromunich.com** bleibt die App.

- Landing: `landing/` (statisch) → Deploy nach `/opt/sero-landing`, nginx-Vorlage
  `deploy/nginx-seromunich-landing.conf`, Skript `scripts/deploy_contabo.sh`
- DNS-Anleitung (Shopify A/AAAA/www, MX/TXT Google nicht anfassen) in
  `docs/DEPLOY_CONTABO.md`
- Auth parallel zum bestehenden E-Mail-Code-Login:
  - Google OAuth (fertig, braucht `GOOGLE_CLIENT_ID/SECRET`)
  - Telegram Login Widget (`POST /api/auth/telegram`, BotFather `/setdomain`)
  - Telefon: Stub + Twilio-Pfad (`docs/AUTH_SETUP.md`)
- Login-UI: Google / Telegram / Telefon-Buttons; Pins `sero.js?v=202`,
  `sero.css?v=135`
- **Kein eBay-Publish / dry_run-Warnung unverändert**

## Contabo-Deploy (15.08.)

Öffentlicher Test unter https://app.seromunich.com (`/opt/sero`, systemd `sero-web`, nginx+Let’s Encrypt). Mac-launchd unverändert. Details: `docs/DEPLOY_CONTABO.md`. **dry_run in DB prüfen** vor Publish-Tests.

## Listing-Review UX (14.08.)

- **Preisvorschlag:** Toggle + Mindestpreis-Feld in Block C (Sofortkauf); Backend
  `offermin`-Action; Preflight prüft `best_offer.enabled` korrekt.
- **Draft-Fotos:** Fertige Alpha-Cutouts beim Listen aus der Sammlung werden nicht
  mehr durch `render_product` neu freigestellt (`photo_is_existing_cutout`).
- **Bildbearbeitung im Entwurf:** Tipp auf Foto im Strip oder „Bilder bearbeiten“
  öffnet volle Werkzeugleiste (Zuschnitt, Drehen, Hintergrund, Freistellen,
  Original/Freisteller) wie in der Übersicht.
- Pin: `sero.js?v=200`, `sero.css?v=133`. Web-Dienst neu gestartet.

## Publish: WATA-Spiele / stale needs_review (14.08.)

Bug: GTA Vice City PS2 WATA blieb beim Publish mit „Noch nicht bereit“ hängen
(`item_status` + `identity_eval` needs_review / MISSING_REGION), obwohl Region
in der Beschreibung stand und der Entwurf `ready` war. Ursache: Karten-Gates
griffen auf Games; Identity-Sync lief nur beim Upload/Preflight, nicht beim
Draft-Laden; alter uvicorn-Prozess (seit 10.08.) ohne Fix-Code.

Fix: `sync_linked_item_identity` bei Draft-GET, Preflight, Upload, Bulk und
Sammlungs-Detail; Games nach Confirm/`listing_ready` blockieren Preflight nicht;
Frontend-Gate respektiert `identity_user_confirmed`/`item_listing_ready`.
Pin: `sero.js?v=199`. Web-Dienst neu gestartet. **Kein eBay-Publish.**

---
## Cutout Sleeve/Halter (10.08. Nachmittag)

Bug: Toploader auf hellem Tisch wurde als **raw-Rechteck** freigestellt
(eckige Kanten, Halter abgeschnitten), obwohl die Analyse „Schutzhülle“
erkannte. Zwei vorherige Scans auf dunklem Untergrund hatten den Halter
behalten — derselbe raw-Pfad, aber rembg sah das Plastik gegen Schwarz.

Ursache: Freisteller und Claude-Analyse laufen getrennt; `cutout_kind` wurde
nicht persistiert; Vision-Prompt forderte früher die **gedruckte Karte** bei
sleeve; raw = `minAreaRect`.

Fix: Prompt hält Halter-Außenkanten; Sleeve-Vorzuschnitt + Soft-Alpha; Kind
persistiert; Nachbesserung wenn Analyse Schutzhülle/Toploader nennt und Kind
≠ sleeve; Recrop nutzt denselben Hinweis. Guards in
`tests/test_slab_soft_alpha.py`. Cutout v2 Flags weiter default aus.
Pin: `sero.js?v=196`. **Kein eBay-Listing angefasst.**

---
## Scanner-first (10.08.)

Plan: `docs/scanner_first_plan.md`. Spez: UX-Audit Scanner-first (10.08.) + Codex-Prompt.

**Erledigt P0/P1/P2 + P3-Kern (Audit):**
- CTA getrennt: `Entwurf prüfen` / `eBay-Entwurf vorbereiten` ≠
  `Jetzt bei eBay veröffentlichen` (nur Confirm + Upload)
- Listing-Review A–D in einem Screen (Bilder / Produkt / Angebot / Versand)
- Kategorie + Pflichtmerkmale editierbar (`cat`/`aspect`); category-suggest API
- Manuelle Kartensuche sichtbar (Sammlung + Review); Match invalidiert
  Preisquery, Kategorie, Aspects und startet Pipeline neu (kein Publish)
- Preflight-Checkliste mit Sprunglinks; Gates für needs_review/uncertain/
  error/analyzing (Draft + Item + identity_eval)
- `listingTippFromItem`: Portfolio/KI/Asking nie automatisch Listenpreis
- FIXED_PRICE+auction1 und Auktion-Inkompatibilitäten in `preflight.py`
- Draft-Revision/If-Match 409, `/sell-template`, `/scan-session`
- **P3 Audit:** persistente Scan-Warteschlange in Listings; Batch-Preview +
  editierbare Gruppen (`/scan-batch-preview` → Confirm); selektiver Bulk nur
  Auswahl + Zusammenfassung/Preflight; Long-Press Scan-Modi; Foto-Strip mit
  `imgorder`/`imgmain` im Review
- Pins: `sero.css?v=132`, `sero-dark.css?v=19`, `sero.js?v=196`
- Tests: `tests/test_scanner_first_guards.py` (inkl. 16–21),
  `tests/test_scan_session.py`, `tests/test_preflight.py`
- **Kein echtes eBay-Listing** angefasst / kein Production-Publish ausgelöst
- Mobile Abnahme-Screenshots: Chromium installiert; Fake-Auth + Temp-DB
  unter `tmp/scanner_first_shots/` (26 PNGs + MANIFEST). Befehl:
  `PLAYWRIGHT_BROWSERS_PATH=~/Library/Caches/ms-playwright \\
   ./.venv/bin/python -m pytest tests/test_playwright_mobile.py -q -k shots`
  (Port ≠ 3000, kein Publish). Abgedeckt: Login, Start-Hero, Scanner,
  Scan-Modus, Listings leer/mit Entwurf, Listing-Review A–B (C/D unterhalb
  Viewport). Light+Dark; 390×844 voll, 320×568 + 844×390 Kernzustände.

**Offen / Rest:**
- ScanSession-Hintergrund-Worker (über Analyse-Enqueue hinaus)

**Fix 17.08. — Graded Manga/Comic (Contabo-Scanner):**
- Beckett/CGC-Manga wurde fälschlich als Karten-Slab klassifiziert → UI
  „Kartennummer fehlt" / hängender Review-Flow. `web/identity.py`: `as_manga`
  vor `graded_slab`; Serie/Band/Auflage aus Titel+Aspects; graded Manga ohne
  Label-Typ-Gate. `app_api.py`: stale `needs_review` beim Laden reparieren.
- One-Piece-Band-1 (`0ec7d2734dc4`) auf Contabo re-evaluiert → `ready`.
- Test: `test_bgs_manga_ist_manga_comic_nicht_karten_slab` in `test_identity.py`.

**Fix 17.08. (Abend) — Freisteller/Design im Hintergrund:**
- Recrop und „Alle neu rendern“ hingen am offenen HTTP-Request: App
  verlassen = Abbruch, zweiter Tipp = ewiges Laden. Jetzt Queue + Spawn
  (`enqueue_recrop` / `run_recrop_item`), Antwort sofort.
- Neue Fotos und Stücke ohne Freisteller laufen automatisch nach
  (`/collection/recrop-missing` nach dem ersten Sammlungs-Load).
- Listing-Foto-Kopie vor dem Spawn, damit Entwurf-Start die App nicht hält.

**Fix 17.08. (Abend, danach) — Automatische Listing-Fotos, ohne extra Tab:**
- Extra-Zeile „Designs“ unter Listings ist weg (war dasselbe wie das
  Listing-Foto). Entwürfe / Live / Verkauft wie zuvor.
- Freisteller wird im Hintergrund auf den Studio-Grund gelegt (`composite_cutout_on_background`,
  nur PIL, kein rembg). Beim Listen liegt das Foto schon bereit.
- `GET /sales` stößt keine Render-Jobs mehr an — das hat den Server
  (502 Bad Gateway) lahmgelegt, wenn man Designs einzeln angetippt hat.
- „Alle neu rendern“ legt vorhandene Freisteller nur noch auf den Grund.
- Pins: `sero.js?v=206`, `sero.css?v=139`. **Kein eBay-Listing angefasst.**

**Fix 17.08. (Abend, 2) — Design ohne zweites Freistellen, automatisch:**
- Beim Design/Listen wird **nicht mehr neu freigestellt**. Das Sammlungsfoto
  (egal ob PNG mit Alpha oder JPEG) kommt mit `place_on_listing_bg` auf den
  Studio-Grund — nur PIL, nie rembg.
- Nach dem ersten Sammlungs-Load: `POST /collection/designs-missing` statt
  `recrop-missing`. Manuelles Freistellen bleibt über den Foto-Knopf.
- Scan: Foto → Sammlung → Design läuft von selbst. Kein extra Tipp, kein
  extra Tab, kein eBay-Listing dabei.
- Pins: `sero.js?v=207`, `sero.css?v=139`.

**Fix 17.08. (Abend) — Toter Entwurf ohne Knopf:**
- Fehler-Entwurf zeigte „fehlgeschlagen“ und gleichzeitig „wird vorbereitet“,
  ohne den versprochenen Knopf. `/list` gab denselben toten Entwurf zurück.
- Jetzt: klarer Text + **Erneut versuchen**; `/list` stößt einen Error-Draft
  neu an. Rettung schreibt `error_text`.

- Feinschliff Batch-UI (z. B. Foto zwischen Gruppen verschieben per Drag — bewusst
  nicht; Pfeile/Teilen/Zusammenführen reichen)
- Optional: Review C–D (Angebot/Versand) als Scroll-Shots; Batch-/Bulk-Confirm
  ohne Kamerafixture nicht abgebildet

---
## Cutout / Pricing Pipeline v2 (09.08. Nacht)

Fundament laut Plan, **Flags default aus** (Canary erst nach Freigabe):

| Flag | Wirkung |
|---|---|
| `SERO_CUTOUT_V2` | Produktionspfad `web.cutout_v2.run_cutout` |
| `SERO_CUTOUT_V2_SHADOW` | Parallel nach `tmp/cutout_shadow/` |
| `SERO_PRICING_V2` | Async Preisjobs + Identity-Key v2 |
| `SERO_PRICING_V2_SHADOW` | Jobs parallel, Legacy-Refresh bleibt |

**Cutout:** gemeinsame API, Routing (graded bestätigt → nie Produkt), Alpha-QA
Hard-Fails (opak / Canvas-Touch), Warp/Original nie SUCCESS, atomare Speicherung
+ `.prev.png`. Baseline: `scripts/cutout_baseline_metrics.py` → u. a. 24/73
nahezu opak, Anker `376e7889dd81` opak, `446ad78526af` Canvas-Touch. Gold:
`tests/fixtures/cutout_gold/manifest.json`. Eval: `scripts/eval_cutout_refs.py`.
BRIA-RMBG-2.0 bewusst blockiert (NC). Doku: `docs/cutout_pricing_v2.md`,
`docs/cutout_model_benchmark.md`.

**Pricing:** `web/pricing_v2/` Keys/QueryPlan/typed Provider/Jobs/Merge/Money.
Cert `6134998058` Regressionstests. `card_key_of` mit Flag ohne reines
`game:ref_id`. PC prüft bis 8 Kandidaten. TCGCSV Staging bei unvollständigem
Index. `snapshot_price` via `as_money`. UI: kein Erfolgstoast bei Timeout;
Polling `price-job` (Pin `sero.js?v=191`). Migration dry-run:
`scripts/migrate_identity_keys_v2.py`.

**Weiter (10.08.):** Slab/Sleeve ohne opakes `minAreaRect` (weiches Alpha);
`price_class` in API+UI; `canonical_identity` persistiert; Canary über
`SERO_*_CANARY` (Allowlist oder Prozent), default weiter aus.
Pin: `sero.js?v=192`.

**Noch offen / Freigabe nötig:** Canary-Anteil, Human-GT-Alphas, Modell-Weights
für HR-Matting/BEN2/SAM2, Picsart/PhotoRoom-Keys, Default-Umschaltung.

---
## TCGplayer-Lücken bei One Piece (09.08. Nacht)

- **EB04-061 SEC:** Nummer war als 051 gelesen → Funko-POP-Preis 6,73 €
  (`pricecharting_weak`). Funko/Amiibo = Domäne `merch`, nicht TCG. Setcode
  wird aus `EB04`+`61` gebaut; Abbr `OP15-EB04` matcht. Korrekt ~9,90 € PC /
  ~8,40 € TCGplayer.
- **Luffy-Tarou ST18-005:** Erkennung ok, aber Rückfrage nur zur Seltenheit
  (`uncertain`) brach vor TCGplayer ab. Weiche Seltenheits-Fragen blockieren
  den Preis nicht mehr. Parallel ≠ SP (kein 270-$-Fehlmatch).

---

## Parallel vs. Basis-Rare (09.08. spät)

OP10-111 Luffy: Basis-Rare (~1 $) und Parallel/Alt Art (~19 $ / Cardmarket
~9–11 €) teilen die Nummer. Erkennung: Claude-Titel + `edition` in
`identify_card`; Preissuche mit „Parallel/Alternate Art"; PriceCharting und
TCGplayer wählen die Variante; `card_passt_zu_info` lehnt Basis ab, wenn
Parallel gewünscht ist. TCGplayer-Nummer aus `(111) (Parallel)` korrekt.

---

## Live-Listingpreis + Preis editieren (09.08. spät)

- **Sammlung:** Ist ein Stück live auf eBay, zeigt die App den Listingpreis
  (`ebay_price`/`price`), nicht irrelevante Marktvergleiche (Azuki-Box vs.
  Einzelkarten 1,87 €).
- **Verkauf:** Festpreis live — Preis tippen, dann „Änderungen speichern“
  (geht zu eBay). Auktion mit Geboten bleibt gesperrt. Format weiter fest.
- **TCG-Falle:** „Trading Card Game" / „Card Game Box" zählt nicht mehr als
  Videospiel (`_category_suggests_video_game`). Pin: `sero.js?v=190`.

---

## Produkt-Freisteller ohne Treppen (09.08.)

Dosen/Flaschen: L/R-Flanke wird linearisiert, Alpha weich aus Distanz
(kein int-Runden). Fuß-Schatten nur am äußeren Rand (Motiv bleibt). Heller
rembg-Saum holt Farbe aus dem tiefen Inneren. Allgemein: stärker horizontal
glätten. Test: `test_polish_glaettet_dosen_treppen`.

---

## Freisteller-Standard (09.08., fest)

- **Rohkarte / Hülle:** `birefnet-general` + Rechteck-Vorlage
- **Graded / Slab:** `isnet-general-use` + Rechteck-Vorlage (Case + Label);
  `bild_ok` verlangt Höhe/Breite ≥ 1,48
- **Alltagsstücke:** `birefnet-general` + Rand-Politur
- Sprache für Preise aus Titel (`infer_language_from_text`); „Card Game“
  zählt nicht als Videospiel

---

## Default-Hintergrund Scan-Cam-Kaltweiß (09.08.)

Ohne eigene Wahl: App-Vorschau und eBay-Render nutzen `#F5F9FF`
(`DEFAULT_LISTING_BG` / `DEFAULT_BG_COLOR`). Gilt für neue und bestehende
Stücke (API liefert die Farbe auch ohne gespeichertes `listing_bg`). Im
Foto-Menü weiter änderbar; Konto-Logo bleibt Ausnahme vor dem Farb-Default.
Pin: `sero.js?v=189`.

---

## Hintergrundfarbe im Foto-Menü (09.08.)

Drei Punkte → **Hintergrund**: Palette (Weiß-Töne, Dunkel, SERO-Eisblau).
Pro Stück `listing_bg` (#Hex Whitelist in `web/listing_bg.py`); Vorschau
sofort hinter dem Freisteller; beim Listen Override vor Konto-Vorlage.
Pins: `sero.css?v=129`, `sero.js?v=188`.

---

## Freisteller-Grund eisblau (09.08.)

`--thumb-bg` Light: `#f5f9ff` (wie Scan-Cam/Tabbar), nicht Reinweiß.
Pin: `sero.css?v=128`.

---

Auge und Neu-laden in der Topbar auf 34×34 wie das Profilbild (vorher 44).
Home-Karte heißt „Deine Sammlung“ statt „Deine Stücke“.
Pins: `sero.css?v=125`, `sero.js?v=183`. Built-by-Signatur größer und mit
Luft gegen die Tabbar-Ausblendung.

## Audit-Aufräumen (09.08. Abend)

Nach Voll-Scan: `publish_uncertain` wieder im Verkauf-Tab (Entwürfe), FAQ auch
auf leerer Startseite, Sales-Liste mit `thumb()`, SSE lädt Verkauf mit,
Dashboard-Fotos eigenes zuerst, Attention/Movers-UI-Reste und tote Imports
entfernt. Pins: `sero.css?v=122`, `sero-dark.css?v=17`, `sero.js?v=180`.

## Löschen zuverlässig + Endzeit (09.08.)

Sammlung löschen: sofort Server-DELETE (Papierkorb), nicht erst nach 6 s —
sonst holte SSE das Stück zurück trotz Toast „entfernt“. Undo via
`POST …/restore`. Entwurf verwerfen: kein Auto-Neu anlegen
(`_skipEnsureDraft`). Verkaufsliste + Listing-Detail zeigen Endzeit
(`ends_at` / „Endet in …“). Pins: `sero.css?v=119`, `sero.js?v=177`.
Verkaufsliste: nur Preis + Endzeit. Detail: Ende, Gebote, Merkliste, Aufrufe
(GetItem). Verkauf-Tab: Pull-to-Refresh synct per `?refresh=1` mit eBay.

Freunde-Zugang: `https://additions-kyle-particularly-cfr.trycloudflare.com/app/`
Lokal: `http://192.168.2.39:3000/app/`

## Verkauf Sortierung + Kopfwerte + Verkaufspreis (09.08.)

Verkauf-Kopf: Aktiv → Listing-Wert, Entwürfe → Entwurfswert, Verkauft →
Verkaufserlös (Summe echter Verkaufspreise). Sortier-Knopf neben Ansicht:
Endet bald / zuletzt, Preis hoch / niedrig. Sales-Sync liest Orders-API und
setzt `sold_price` (nicht Auktions-Start 1 €). Anzeige „Verkauft für …“.
Pins: `sero.css?v=117`, `sero-dark.css?v=15`, `sero.js?v=174`.

Freunde-Zugang (Quick-Tunnel, 09.08. neu):
`https://additions-kyle-particularly-cfr.trycloudflare.com/app/`
Lokal: `http://192.168.2.39:3000/app/`

## Live-Listing nur änderbare Felder + Verkauft-Tab (09.08. Abend)

Live auf eBay: Preis, Sofortkauf/Auktion, Zustand, Stückzahl, USK und Neu-
Erstellen sind gesperrt (Backend + UI). Speichern gilt für Titel/Beschreibung/
Bilder; Beenden bleibt. Detail aus dem Verkauf-Tab ohne Übersicht|Verkaufen-
Umschalter. Verkauf-Segment „Verkauft“ statt „Beendet“ — API liefert nur
`ended_reason == "Verkauft"`. Dark-Tabbar: hellblauer Rand wie Scan-Cam
(`#7eb6ff`), transparenter (`rgba(6,12,24,.38)`), aktive Tabs `#b8d6ff`.
Pins damals: `sero.css?v=116`, `sero-dark.css?v=15`, `sero.js?v=173`.

## UI-Qualitätsrunde Kern (09.08. Abend)

Bild-Selektor vor `.ph-strip` geschlossen. `--card`-Token, Kontrast `--label-2/3`
+ Button-Gradient. Sammlungsgrid `minmax(0,1fr)`, Topbar-Budget, Login scrollbar,
irow Label/Wert, Detail-Hero ohne starre 560px, Chips umbrechen, Querformat-Chart.
Titel: ein Theme-`<img>` (`titleSrc`), keine Default-900×340, DE-ARIA-Namen.
Login-Labels `for`/`id`, `:focus-visible`, Tabs `aria-current`. Light-Monogramm
abgedunkelt. Pins damals: `sero.css?v=115`, `sero-dark.css?v=14`, `sero.js?v=172`,
`sero-profile.js?v=8`, `TITLE_V=10`.

**Offen / manuell:** Light-Titel `*-dark.png` Alpha neu exportieren; deutsche
Schriftzug-Quellen; maskable PWA-Icon; Dialog-Fokusfallen; Typografie-Rollen;
Freistell-Pipeline für Altbilder; Viewport-Screenshot-Matrix.

## Tutorial + Verkaufs-Kopf + Auktionsgebot (09.08. Abend)

Onboarding als 5-Schritt-Tutorial (nicht mehr „Erstes Stück scannen“-Zwang).
Pro Konto; nach Abmelden wieder. Verkauf-Tab: Listing-Wert wie Sammlungskopf
(Summe der aktuellen eBay-Preise), Ansichts-Knopf rechts daneben (38px, etwas
kleiner als Sammlung). Auktionen: Sales-Sync behält das aktuelle Gebot nach
GetBestOffers-Reload (`pending_price` / `live_auction_state`); Anzeige
„Gebot … · n Gebote“ statt Startpreis 1 €. Pins: `sero.css?v=114`, `sero.js?v=171`.

## Dark-Mode HR-Assets + Homescreen-Icon (09.08. Abend)

Neue Hochauflösung für Dark-Mode: Script-Titel Portfolio/Collection/Scan/Sell/Profile
(`titles/*.png`), weiches SR-Monogramm (`monogram-navy.png`), Scan-Cam hell/dunkel
für den Tab-Button (`scan-cam-light.png` / `scan-cam-dark.png`). Homescreen-Icon
dunkles Navy mit neon-SR + Scan-Rahmen (`app-icon.png` / `icon-512.png` /
`apple-touch-icon.png`, Manifest `v=4`). Pins: `TITLE_V=9`, Cams `?v=3`,
Icons `?v=4`, `sero.js?v=169`, `sero-profile.js?v=7`, Logos `?v=6`.

## Portfolio-Hintergrund + Sammlung ohne Verkaufs-Chips (09.08.)

Hero-Reset zeichnet sofort neu (Bug: Dashboard blieb auf altem Verlauf).
Default/SERO-Navy = Brand-Blau; altes Rot-Preset entfernt. Chart-Default `Max`
(ab erstem Tag). Chips „auf eBay“/„Verkauft“ aus der Sammlung raus.
Pin: `sero.js?v=168`.

## Portfolio-Kopf kompakt (09.08.)

Mini-Wert-Pille in der Topbar entfernt. 7T/1M/Max links neben dem Preis;
Auge + Neu laden oben rechts neben dem Profilbild (34px). Hintergrund hell/dunkel
an Brand-Blau der Schriftzüge. Pins: `sero.css?v=112`, `sero-dark.css?v=13`, `sero.js?v=167`.

## Topbar-Titel gleiche Größe + kein Abschneiden (09.08.)

Section-Titel so hoch wie SERO-Wortmarke (34px). Soft-Titel für Dark-Mode:
dunkle Konturen aufgehellt, großer Rand, kein falsches Aspect-Ratio.
Pins: `TITLE_V=8`, Logos `?v=9`, `sero.css?v=110`, `sero.js?v=166`.
Hell-Mode behält die kräftigen/dunklen Titel; nur die Topbar-Größe ist angeglichen.

## Topbar mit Sektionstitel (09.08.)

SERO-Logo größer, Topbar breiter. Dünne Linie in Brand-Blau, daneben Script-Titel
je Tab (Portfolio/Collection/Scan/Sell/Profile). Seiten-Titel ausgeblendet.
Dark-Assets ohne schwarze Ränder neu gerendert. Pins: `TITLE_V=6`, Logos `?v=7`,
`sero.css?v=108`, `sero.js?v=162`.

## HR-Titel + SERO-Wortmarke (09.08. nachmittag)

Neue Hochauflösungs-Assets (transparent, 2× Retina): Portfolio/Collection/Scan/Sell/Profile
je hell+kräftig, plus zwei SERO-Wortmarken. Kontrast-Tausch bleibt (kräftig im Light-Mode).
Pins: `TITLE_V=5`, Logos `?v=6`, `sero.js?v=161`.

## Kontrast-Tausch Logos/Titel (09.08.)

Light-Mode zeigt die kräftigen Dark-Blues (`*-dark` / `*-white`), Dark-Mode die
weichen Light-Blues (`*.png` / `*-navy`). Portfolio eigene Zeile wie die anderen
Tabs; Sammlung + Verkauf bündig am linken Rand (`tab-title-flush`).
Pins: `TITLE_V=4`, `sero.css?v=107`, `sero.js?v=160`, Logos `?v=5`.

## Script-Titel hell/dunkel (09.08.)

Sheet → einzelne PNGs (3× hochskaliert, transparent):
Portfolio, Collection→`sammlung`, Scan→`scanner`, Sell→`verkauf`, Profile→`profil`
je `*.png` (hell) + `*-dark.png`. Kein Invert mehr (nur noch Einstellungen).
Pins: `TITLE_V=3`, `sero.css?v=106`, `sero.js?v=159`, `sero-profile.js?v=4`.

## Logos hell/dunkel (09.08. nachmittag)

Neue Schriftzüge mit transparentem Hintergrund:
- Topbar: `wordmark-navy.png` / `wordmark-white.png` (SERO-Lettering)
- Login + Splash + Leerzustand: `monogram-navy.png` / `monogram-white.png` (SR)
Kein Invert-Filter mehr — echte Dark-Assets. Pins: `sero.css?v=105`, `sero.js?v=158`.

## Startseite hängt nicht mehr (09.08.)

Ursache: `closeDetail` setzte `state.dash = null` → beim Zurück zur Startseite
Skeleton + voller `/dashboard`-Reload. Zusätzlich lud das Dashboard pro Stück
`get_draft()`. Fix: Cache behalten + Hintergrund-Refresh; Entwürfe einmal
laden und an `item_public(..., drafts_by_id=)` durchreichen.

Kleine Kacheln: Auswahl-Kreis entfernt; Grading kompakt (`CGC P10`) und
schmaler, damit es auf die Kachel passt.

Pins: `sero.css?v=103`, `sero.js?v=157`.

## UI: kleine Kacheln, Verkauf-Schalter, Direktverkauf (09.08.)

1. Sammlung `g4`: gleiche Kachelhöhe, kein Zustand, Grading unter dem Namen
   (Auswahl-Kreis später wieder entfernt).
2. Verkauf: Ansichtsschalter rechts neben dem Titel „Verkauf“ (`sales-title-row`).
3. Detail → Verkaufen: kein Zwischen-Sheet „Entwurf erstellen“. Beim Öffnen
   wird der Listing-Entwurf automatisch angelegt (`ensureItemDraft`); Preis,
   Titel, Kategorie, Beschreibung, Zustand, Sofortkauf/Auktion, Stückzahl,
   Preisvorschlag sind direkt bearbeitbar → „Auf eBay listen“.

Pins: `sero.css?v=102`, `sero.js?v=156`.

## Sammlung: Statistik bleibt bei Kategorie-Filter (09.08.)

Vorher: Chip Pokémon/One Piece → Verlaufs-Chart verschwand (`histSeries = []`).
Jetzt: `history_by_cat` vom Server; Chart bleibt und zeigt den Kategorie-Verlauf.
Andere Filter (eBay/Suche/…): Kurzverlauf aus Δ7 oder skaliert. Immer sichtbar.

Zusatz: Retro-/Videospiele dürfen wie Alltag einen Richtwert
(`erlaubt_ki_richtwert` auch bei Domäne `game`).

Pins: `sero.js?v=155`.

## Login/Scanner-Texte + KI-Richtwert für Alltagsprodukte (09.08.)

- Login: „Sammeln. Scannen. Listen.“ / „Stück scannen“
- Scanner: „SERO erkennt jedes Stück deiner Sammlung.“
- ADR-002 Ausnahme: Nicht-Karten (Domäne `None`, z. B. Schuhe, Deko) dürfen
  einen KI-Richtwert zeigen (`suggested_list_price_eur` → `price_source=estimate`,
  `KI_RICHTWERT`). UI: „bitte prüfen, Preis ist änderbar“. Nie Listing-Basis.
  Karten/Manga unverändert fail-closed. Spiele seit späterem Nachtrag ebenfalls
  Richtwert. `comps_verwertbar(..., min_count=1)` nur für Alltag/Spiele.
  Helfer: `erlaubt_ki_richtwert`.

Pins: `sero.js?v=154`.

## UI: Splash, Sammlung-Wert, Scanner, Ansichten (09.08.)

- Splash: wieder `stacked-navy` (SE/RO), größer
- Sammlungswert folgt Filtern (Kategorie, auf eBay → Listingpreis, Verkauft)
- Chips „Aufmerksamkeit“ und Start-Karte „Im Blick“ entfernt; Scanner ohne
  Sammlung/Verkauf-Umschalter
- „Auf eBay listen“ öffnet den Entwurf direkt (`openDraftDetail`)
- Sammlungs-Ansicht: große/kleine Kacheln / Liste (wie Verkauf)

Pins: `sero.css?v=101`, `sero.js?v=151`.

## Live-Listen nach Testlauf (09.08.)

Ursache: Während Dry-Run angelegte Entwürfe blieben auf `dry_run_done`.
`app_run_upload` brach dort still ab — „Auf eBay listen“ tat nichts, obwohl
Testmodus inzwischen aus (`kv dry_run=false`) war.

Fix: `unlock_dry_run_for_live` in `web/publish.py` — bei Dry-Run aus wird
`dry_run_done` → `ready` (SKU/Offer bleiben), dann normaler Claim +
`publishOffer`. Solange Dry-Run an ist, bleibt der Entwurf gesperrt.
App und Telegram nutzen denselben Helfer. UI: Hinweis + „Jetzt live listen“.

### Upload-UI + Android-Zurück (09.08. später)
- Festpreis/Auktion sendet expliziten Wert (kein Blind-Toggle-Race)
- Während `publishing`/Busy: UI gesperrt, Poll aktiv, Server antwortet 409
  auf parallele Feld-Edits
- Android-Zurück: Sheet → Party → Einstellungen → Detail → Home →
  Nachfrage „App verlassen?“

Pins: `sero.css?v=100`, `sero-mobile.js?v=2`, `sero.js?v=150`.

## Portfolio-Wahrheit & Revision (09.08. Nachmittag)

Zentrale Berechnung in `web/portfolio.py` (Cent/Decimal). Collection,
Dashboard, Historie und Profil nutzen dieselbe Besitz-/Wertlogik.

### Definitionen (Produktregel unverändert)
- **portfolio_owned:** nicht Wunschliste, nicht verkauft, Draft nicht
  `published`/`ended`
- **physical_inventory:** nicht Wunschliste, nicht verkauft (inkl. Live-eBay)
- **value_basis:** `market` | `own_value` | `none`
- Manueller Wert → `price_state=eigener_wert`, nie „belegt“, nie Auto-eBay-Preis
- Historie: Backend setzt heutigen Punkt (`Europe/Berlin`); Frontend erfindet
  keinen UTC-Tag mehr

### Revision
- `rev` hängt an Items **und** Draft-Status-Fingerprint
- Draft `dry_run_done` → `published` ändert `rev` und Totals (Integrationstest)

### Identität
- `set_hint` → kanonisches Set; Sprache auch aus Vision-Aspects
- Unsicherheit nicht vor Statusbestimmung wegwerfen → `needs_review`
- `scripts/preview_identity_price_inconsistencies.py` (read-only): Live-Stand
  11 Widersprüche belegt/spanne + !pricing_ready (keine Migration ohne Freigabe)

### Aktivität
- `activity_published_7d` über `published_at` / listings, nicht `updated_at`

### Pins
`sero.css?v=97`, `sero.js?v=145`, `sero-profile.js?v=2`

### Tests (verifiziert)
- Suite: **511+ passed**, 1 xfailed; Playwright Chromium = externer Blocker
  (skip ohne Binary)
- Neue Tests: `test_portfolio.py`, `test_identity_contract.py`,
  `test_portfolio_revision.py`

## Portfolio, Foto→Entwurf, WATA-Spiele (09.08.)

Drei zusammenhängende Betriebsfehler behoben:

### Portfolio 610 € vs. 4.461 €
- Sammlungswert im Frontend zählte **Live-Listings** mit (`draft_status=published`).
- Portfolio-API lieferte korrekt nur Besitz (~610 €).
- Fix: Sammlung nutzt Server-`stats.total_value` / schließt `published` aus.
- `portfolio_history` schließt jetzt ebenfalls Wunsch, `sold_ts`, published und
  ended aus — Verlauf und große Zahl passen zusammen.

### Foto bearbeiten → eBay
- Geänderte Sammlungsfotos wurden nicht in den verknüpften Entwurf gespiegelt;
  Publish/Update lud weiter alte Draft-Dateien.
- Fix: nach photos/recrop/rotate/replace/restore → `mirror_item_photos_to_draft`
  (kopiert Dateien, leert `image_urls`). Kein Auto-Publish.
- Drei-Punkte-Menü öffnet Foto-Sheet direkt (kein Detail-Umweg, der hing).

### GTA Vice City „Wert unbekannt“
- WATA-Spiele liefen als `graded_slab` und scheiterten an Kartennummer/Set/Sprache.
- Fix: WATA/VGA/CGA + Spiel-Kategorie → `video_game`; Plattform/Region/Sealed
  aus dem Titel; Preis-Query inkl. Grade.
- Nach Deploy: am Stück „Preis aktualisieren“ tippen.

Pins: `sero.css?v=96`, `sero.js?v=144`.

## Startseite: SERO-Effekt, Aktivität, FAQ (09.08.)

Transparenter Zeitgewinn ohne Gamification, ohne LLM und ohne neue
Preis-/eBay-Abfragen. Reihenfolge auf der Startseite: Portfolio → Deine
Stücke → Dein SERO-Effekt → Letzte 7 Tage → Häufige Fragen.

### Datenhaltung `scan_metrics`
- Tabelle `(account_id, item_id PRIMARY KEY), completed_at, scan_seconds`
- Schreiben im Scan-Worker nur bei `status == "ready"` (idempotent
  `INSERT OR IGNORE`)
- Retry desselben Stücks zählt nicht doppelt
- Löschen/Verkaufen senkt den Allzeit-Zähler nicht
- Kontolöschung löscht auch `scan_metrics`
- Backfill beim Router-Start aus Stücken mit gültigem `scan_seconds`,
  `completed_at = NULL` → zählt Allzeit, nicht „Letzte 7 Tage“

### Berechnung (aktive Nutzerzeit)
- Manuell 15 Min / SERO 2 Min / Ersparnis 13 Min pro erfolgreichem Scan
- `manual_seconds = N×900`, `sero_seconds = N×120`, `saved_seconds = N×780`
- Technische `scan_seconds` steuern die Ersparnis **nicht**; ab ≥3 Messungen
  optional `avg_analysis_seconds` in der Erklärung („läuft im Hintergrund“)

### Dashboard `GET /api/app/dashboard`
- `impact`: successful_scans, manual/sero/saved_seconds, avg_analysis_seconds
- `activity_7d`: scanned (Metriken 7d), published (Drafts `published` 7d),
  sold (`ended` + `ended_reason=Verkauft` + `sold_at`/`updated_at` 7d),
  active_listings (aktuell live)
- `attention.count`: Fehler, `price_state=unbekannt`, `BELEGE_ALT`,
  `identity_eval.pricing_ready=false` (Wunsch/Verkauft ausgenommen)

### Frontend
- `HOME_SECS`: `effekt`, `aktivitaet`, `faq` nach `stuecke`
- Zeitkarte bei 0 Scans ausgeblendet; Aktivitätsreihe bei allen Nullen weg;
  FAQ immer sichtbar
- Tipp „So wird gerechnet“ → Sheet mit 15/2-Minuten-Erklärung
- FAQ wie Website (`<details>`): Developer-Account, Freigabe, PSA-Label,
  Daten/Fotos, beste Stücke, Kündigung

Pins: `sero.css?v=122`, `sero-dark.css?v=17`, `sero.js?v=180`.

### Signatur unten
- Kleines „Built by a seller who was sick of typing.“ unter FAQ
  (`assets/built-by-seller-light.png` / `-dark.png`, Theme-Umschaltung)
- FAQ auch bei leerem Portfolio sichtbar

### Tests
- `tests/test_scan_metrics.py` (Zählen, Retry, Backfill, Math 15/2,
  sold_7d, Attention-Helfer, STR_EN inkl. FAQ, kein LLM)
- Dashboard-Felder in `tests/test_api_integration.py` (ohne `attention`)

## Startseite: SERO-Effekt (08.08. Nacht) — Historie

Frühere Fassung: 8 Min von Hand / 1 Min mit SERO, „Im Blick“-Karte.
Abgelöst durch Abschnitt oben (15/2, verkauft-7d, FAQ).

## Profil & Einstellungen (08.08. Abend)

Vollständige Überarbeitung von Profil-Tab, Tarifkarte und Einstellungen.

### Profilaufbau
- Eine Profilkarte als einziges Klickziel (Avatar, Name, @user/E-Mail, Tarif-Badge).
- Kennzahlen serverseitig: `GET /api/app/profile-summary`
  - **Aktiv auf eBay** = Drafts `published`
  - **In Sammlung** = Summe `quantity` ohne wishlist und ohne `sold_ts`
  - **Verkauft** = Items mit `sold_ts` (ended ohne Sold-Markierung zählt nicht)
- Bei Ladefehler: `—`, keine geratenen Nullen aus `state.items`.

### Tarif & Billing
- Volle Breite, korrekte Listing-Kontingent-Texte, Scans separat „ohne Limit“.
- Bezahlte Pläne → `POST /api/billing-portal` (Return-URL `/app/`).
- Testphase → Tarifwahl / Premium-Seite — **nicht** die Gratis-Scan-Paywall.
- `openPaywall()` bleibt nur für echte Scan-Limit-Fälle (402).

### Settings-Navigation
- Vollhohe `settingsView` mit Stack (`settingsNav`), Zurück über Ebenen.
- Gruppen: Konto, Tarif, eBay/Telegram, Darstellung/Sprache/Preisalarme,
  Daten & Backup, Sammlung warten, Hilfe, Rechtliches, Über.
- Preisalarme: `price_alerts_enabled` (Alias `notifications`); `check_alert()`
  respektiert die Pause; SSE bleibt aktiv.
- Rechtslinks: `/guide.html`, `/legal.html#impressum|datenschutz|agb`.
- Konto löschen: Export-Hinweis, eBay-Hinweis, Eingabe `LÖSCHEN`.
- App-Version zentral: `SERO_APP_VERSION` in `sero-profile.js`.
- Favicon: `assets/sero-slab.svg` wieder vorhanden.
- Tabbar ≤350 px: sichtbares Label `Start` (ARIA weiter „Übersicht“).

### Tests (dieser Auftrag)
- `tests/test_profile_summary.py`, `tests/test_profile_frontend_guards.py`
- Gesamtsuite: **472 passed**, 1 xfailed; 5 Failures nur Umgebung
  (numba/pymatting-Cache, Playwright-Browser nicht installiert) — kein
  fachlicher Rückschritt.
- Playwright Chromium/WebKit und echtes iPhone: **nicht** in dieser Session
  ausgeführt (Browser-Binary fehlte in der Sandbox).

### Fix: Sheet über Settings (08.08.)
Options-Sheets (Erscheinungsbild, Sprache, …) lagen unter der Settings-View
(`z-index` 21 vs. 25) und wirkten tot, bis man zurückging. Sheet/Backdrop
jetzt `41`/`40`. Pin `sero.css?v=94`.

### Offen / Folge
- Marke auf `/legal.html` lautet teilweise noch „Listo“ (`~/listo-website/legal.html`)
  — bewusst nicht still geändert; eigener Website-Auftrag nötig.
- Echtes iPhone-PWA-Rendering der neuen Settings-View.

| Pin | Stand |
|---|---|
| `sero.css` | **v=95** |
| `sero-dark.css` | **v=12** |
| `sero.js` | **v=143** |
| `sero-profile.js` | **v=1** |
| `sero-mobile.js` | **v=1** |

## Dunkles App-Icon (08.08. Abend)
## Dunkles App-Icon (08.08. Abend)

Navy-SR-Monogramm ist offizielles Home-Screen-Icon: `app-icon.png`, `icon-512.png`, `apple-touch-icon.png` (Cache `?v=2`). Splash + Topbar-Fallback ohne eigenes Profilfoto nutzen dasselbe Icon.

## Scan-Cam Design-System (08.08. Abend)

Tab-Kamera nutzt die neuen Glas-Icons (`assets/scan-cam-light.png` /
`scan-cam-dark.png`). Gesamte UI-Farbwelt und Rundungen daran ausgerichtet:

- Light: Eisblau (`#eef3fb`, Tint `#2f6fd0`, Glow `#7eb6ff`)
- Dark: Neon-Cyan-Blau auf Schwarz (Tint `#6aa8ff`, blaue Glas-Kanten/Glow)
- Rundungen wie App-Icon / Scan-Cam-Squircle (~22%), **keine Pillen-Tabbar**:
  `--radius-bar` 20, `--radius-card` 18, `--radius-sheet` 24, `--radius-control` 12

| Pin | Stand |
|---|---|
| `sero.css` | **v=89** |
| `sero-dark.css` | **v=11** |
| `sero.js` | **v=140** |

## Mobile-Stabilität (08.08. Nacht)

Umgesetzt gegen den Audit „Mobile-Stabilität, Scrollen und Abstürze":

| Punkt | Stand |
|---|---|
| P0 Gesten / Tab-Swipe vs. Chips | **DONE** — `SeroMobile.gestures`, Pointer-Events, `.chips`/Streifen ausgenommen |
| P0 Sheet-Höhe / sheet-fit | **DONE** — immer `max-height` + scrollbarer Body; fit nur optisch |
| P0 visualViewport | **DONE** — CSS `--vv-height` / `--app-height` |
| P0 Kamera sync (kein 250ms-Timer) | **DONE** |
| P0 Latest-Request-Wins | **DONE** — Dashboard/Collection/Sales |
| P1 Storage-Adapter | **DONE** — `SeroMobile.store` / `storeSafe` |
| P1 Collection-Chunks | **DONE** — 60er Chargen + Sentinel/IO |
| P1 Holo/Blur | **DONE** — rAF-Holo, Backdrop ohne Extra-Blur, reduced-motion |
| P1 Zoom meta | **DONE** — `user-scalable=no` entfernt |
| P1 Fehler-Ring | **DONE** — `SeroMobile.errors` (max. 20, bereinigt) |
| P2 Offline-Foto-Text | **DONE** — ehrlich (nur solange App offen) |
| P2 Title-Asset-Pins | **DONE** — `?v=` / `TITLE_V` |
| P2 `_spawn`-Logging + Sales-KV | **DONE** |
| P2 FastAPI-Lifespan statt on_event | **OFFEN** — bewusst, Doppelstart-Risiko; Deprecation-Warnung bleibt |
| Playwright Chromium/WebKit CI | **TEILWEISE** — Datei da, skip ohne Paket; WebKit lokal nach `playwright install` |
| Echtes iPhone PWA | **OFFEN** — nicht in dieser Session getestet |

**Automatisiert:** `tests/test_sero_mobile_core.py`, `tests/test_mobile_stability_guards.py`,
`tests/test_spawn_and_sales_kv.py`, optional `tests/test_playwright_mobile.py`.

| Pin | Stand |
|---|---|
| `sero-mobile.js` | **v=1** |
| `sero.css` | **v=89** (Design-System Scan-Cam / Squircle) |
| `sero-dark.css` | **v=11** |
| `sero.js` | **v=140** |

Externe Plattformgrenze: [WebKit Bug 318572](https://bugs.webkit.org/show_bug.cgi?id=318572) —
iOS-Fotowähler-Speicherverlust; SERO gibt eigene Blob-URLs frei, Workaround unnötig.

---


## Dark Mode Leiste + weiße Titel (08.08.)

Top-/Tabbar in Dark Mode schwarz statt grau. Script-Titelbilder weiß wie SERO-Wortmarke. Titel bleiben links (wie Logo).

## Sammlung-Chips, Titel-Glas, Auto-Entwurf (08.08. Nacht)

- Kategorie-Chip erneut tippen setzt Filter auf „Alle".
- Titelbilder Sammlung/Scanner/Verkauf/Profil/Einstellungen in Glas-Box (wie Portfolio).
- Jeder Scan legt nach Analyse automatisch einen eBay-Entwurf an (Verkauf → Entwürfe).
  Preis aus Verkaufs-Vorlage bzw. Marktwert — kein stiller 1-€-Default mehr bei Auktion
  (1 € nur bei Vorlage „1 € Start").

| Pin | Stand |
|---|---|
| `sero.css` | **v=84** |
| `sero.js` | **v=137** |

## Script-Titelbilder (08.08. Abend)

Statt Text-Titel (`large-title` / „Portfolio SERO“ / „Scannen“) stehen Svens
handgeschriebene Titelbilder oben auf jedem Tab:

| Tab | Bild |
|---|---|
| Übersicht | `assets/titles/portfolio.png` |
| Sammlung | `assets/titles/sammlung.png` |
| Scanner | `assets/titles/scanner.png` |
| Verkauf | `assets/titles/verkauf.png` |
| Profil | `assets/titles/profil.png` oben, `einstellungen.png` vor den Einstellungs-Zeilen |

Schwarzer Hintergrund der Vorlagen ist transparent gemacht (navy Schrift).
Dark-Mode: leichte Aufhellung per CSS-Filter. Titelbilder Sammlung/Scanner/
Verkauf/Profil sowie Portfolio nochmals ~20 % kleiner (v78).

**Übersicht-Hero (v80):** Hintergrund (Foto/Verlauf) auf dem Block Portfolio +
Wert + Chart. Portfolio-Titel in kleinem, durchsichtigem Glas. Chart flacher
(140 px). Grünes Plus unter dem Euro-Betrag; Auge/Reload links unten auf
Höhe von 7T/1M/Max. Hintergrund ändern unter Profil → Darstellung →
Portfolio-Hintergrund.

| Pin | Stand |
|---|---|
| `sero.css` | **v=81** |
| `sero-dark.css` | **v=8** |
| `sero.js` | **v=135** |

---

## UX-Runde (08.08. Abend)

**Übersicht „Deine Stücke“:** Beendete Listings (`draft_status=ended`) erschienen
noch in der Übersicht (z. B. Glurak 199 CGC 10 / 381 €), während die Sammlung
sie unter „Verkauft“ ausblendet. Besitz-Filter jetzt identisch: kein Wunsch,
kein live, kein ended/sold. Nur noch Wert-Liste (kein Bewegungs-Umschalter).
Graded-Siegel in der Zeile, wenn vorhanden.

**Topbar:** abgerundetes Profilbild rechts → Profil-Tab (Testmodus-Badge bleibt
klein daneben, wenn aktiv).

**Sheets:** Suche/Filter/Sort/Long-Press kompakter (`sheet-fit`, kein Riesen-Leerraum).

**Marktwert:** Stift-Knopf neben Glocke/Refresh → manueller Portfolio-Wert
(`price_source=manual`); Auto-Refresh überschreibt nicht, manueller Refresh holt
Marktdaten wieder.

**Scanner:** Titel „Scanner“ weg, Headline „Scannen“, allgemeinere Texte
(Stück statt nur Karte).

**Verkauf:** Sync bei `refresh=1` wartet auf eBay; Auktionen holen aktuelles
Gebot via Trading GetItem (`live_auction_bid`).

**Profil:** Einstellungen in Kategorien (Verbindungen, Darstellung, Daten & Sync,
Hilfe & Rechtliches) mit Unter-Sheets.

**Fotos:** Crop/Drehen ohne closeSheet-davor (zweites Bearbeiten hing); Long-Press
→ „Foto bearbeiten“.

| Pin | Stand |
|---|---|
| `sero.css` | **v=73** |
| `sero-dark.css` | **v=8** |
| `sero.js` | **v=129** |

---

## Graded-Falschmeldung + Schnell-Listen (08.08. Abend)

**Problem:** Rohkarte wurde beim Listen wie Graded behandelt (Zertifikat/PSA-Frage),
u. a. wegen leerem `graded_info`, UI-Label „Neuwertig“ (= LIKE_NEW) und
Frontend zeigte die Graded-Eingabe bei jedem `pending`.

**Fix:**
- `has_real_graded_info` / `ensure_card_condition` / `normalize_condition_input`
  in `bot/ebay/metadata.py` — Graded nur mit Bewerter+Note oder klarem Marker
- App-Upload, Bot-Upload und Listen-Preset nutzen das; halbe `graded`-Dicts
  werden beim Listen verworfen
- UI: Zustand bei Karten = Graded/Ungraded (kein Freitext „Neuwertig“);
  Graded-Frage nur bei `pending === graded|graded_update`
- Nach Scan: Knopf „Auf eBay listen“ → Sheet Format/Preis → Entwurf

**Tests:** `test_ensure_card_condition_raw_card_not_graded`,
`test_graded_frage_nur_bei_graded_pending`

| Pin | Stand |
|---|---|
| `sero.css` | **v=73** |
| `sero-dark.css` | **v=8** |
| `sero.js` | **v=129** |

---

## Scanner-Freistellen = Collection-Norm (08.08. Nachmittag)

**Problem:** Automatischer Scan ließ Tisch/Holz im Bild; Svens manuelle
`edit*.jpg` und gute `*_cut.png` zeigten die gewünschte enge Darstellung.
Warp-only (ohne rembg) bei Slabs ließ den Untergrund sichtbar.

**Referenz-IDs (nicht überschreiben):** siehe
`tests/fixtures/cutout_refs.json` — u. a. `35a64a879d80` (Booster cut.png),
`9c030ec7f846` / `17b27e96af84` (GTA), `c9ae19782791` (Exeggutor),
`fb726042ce4b` / `850420d25072` / `18f01dca776b` / `a4c192e0a6a5` (CGC).

**Fix (einfach):**
- Modelle: Roh/Hülle `birefnet-general`, Graded/Slab `isnet-general-use`
- Pipeline: EXIF → (Slab: Warp aufrichten) → rembg → Layout aus Alpha
  (`layout_aus_alpha`, ~1,5 % transparenter Rand) → PNG
- Kein Studio-Bleichen mehr im Cutout
- Analyse-Pfad schreibt wieder `_cut.png` (Warp+rembg), nicht nur `_slab.png`
- UI: Sammlung nutzt bereits `object-fit: contain` (kein Zweit-Zuschnitt)

**Produkt / Sonstiges (09.08.):** rembg isoliert Alltagsstücke (z. B. Kappe)
bereits gut. Der Nachschritt „MinAreaRect auffüllen“ war nur für Karten
gedacht und holte Tisch/Monitor zurück. Ab jetzt: Karte/Slab behalten die
Rechteck-Vorlage; alles andere behält die rembg-Silhouette. Warmup lädt
BiRefNet + isnet.

**Produkt-Qualität (09.08. abends):** Sonstiges nutzt `birefnet-general`
plus `_polish_product_cutout`. Kanten: kein hartes `post_process_mask`;
Fransen abschneiden; Silhouette stark runden (Blur→Schwellwert); weiches
Alpha; hellen Farbsaum durch Innenfarbe ersetzen (sonst Zacken auf Dunkel).
Roh/Hülle: BiRefNet + Rechteck; Graded: isnet + Rechteck (Case-Schutz).
**Vergleiche:** `tmp/cutout_eval/<id>/compare.jpg` + `on_checker.jpg`
**Skript:** `scripts/eval_cutout_refs.py`
**Tests:** `tests/test_cutout_layout.py`, `tests/test_render_standard.py`

**MANUELL:** Hard-Reload App → Pegador-Cap / neues Sonstiges scannen →
Freisteller ohne Tisch prüfen.
Bestehende manuelle `edit*.jpg` bleiben unangetastet.

| Pin | Stand |
|---|---|
| `sero.css` | **v=72** |
| `sero-dark.css` | **v=6** |
| `sero.js` | **v=128** |

---

## eBay-Connect in der App (08.08.)

**Problem:** OAuth „erfolgreich“, aber App übernahm den Stand nicht; Verkauf und
Profil starteten unterschiedliche Flows (Vollnavigation vs. Sheet).

**Fix (vereinheitlicht, Pin js v=127):**
- `/callback/ebay` setzt `listo_session` nach Token-Austausch
- `/api/me` liefert `ebay_token_at` — Poll erkennt Reconnect (Token war schon da)
- Verkauf **und** Profil öffnen dasselbe Connect-Sheet
- eBay in neuem Tab; App bleibt offen; Poll + Knopf „Verbindung prüfen“; Paste-Fallback
- Setup ohne Website-Zwang

**MANUELL:** Hard-Reload (Pin 127) → Verkauf oder Profil → eBay neu verbinden →
Freigabe → zurück zur App / „Verbindung prüfen“ / Paste. Live-Orders 403 bleibt
bis Scope bestätigt + Orders klappen. „Neu verbinden“ im Profil kann bleiben,
solange `ebay_fulfillment_fehlt_*` gesetzt ist — das heißt Token da, Orders noch
nicht ok.

| Pin | Stand |
|---|---|
| `sero.css` | **v=72** |
| `sero-dark.css` | **v=6** |
| `sero.js` | **v=127** |

---

## Abnahme Produktionsreife A–F (08.08. Vormittag)

**Kein „production ready“:** Pflichtpunkte manuell offen (eBay-Reconnect live,
Handy-E2E, echtes Listing, Commit/Push). `dry_run` unberührt. Port 3000 /
launchd unberührt. Nicht committed/gepusht.

| Pin | Stand |
|---|---|
| `sero.css` | **v=72** |
| `sero-dark.css` | **v=6** |
| `sero.js` | **v=125** (siehe oben: inzwischen **126**) |

### Phase A — UI (DONE Code)
- Icon `grid` + `ICON_PATHS`; Fallback `question`, Warn nur mit `?debug=1`
- aria-label `#eyeBtn` / `#dashRefresh` (+ STR_EN); Icon-Buttons geprüft
- Touch ≥44×44: `.info-i`, `.fchip`, `.seg`, `.icon-btn.sm` Hit-Ringe
- Desktop ≥720px: Grid auto-fill, Tabbar max 430px zentriert, Content 720px
- Tests: `tests/test_frontend_guards.py`

### Phase B — Onboarding SERO (DONE Code)
- Magic-Link → `/app/?logged_in=1` (safe redirects)
- eBay callback → `/app/?ebay=ok|failed|invalid` (optional `?next=` allowlist)
- FastAPI-Titel `SERO`; Onboarding öffnet connect mit `next=/onboarding.html`
- Tests: `tests/test_auth_redirects.py` (Temp-DB)

### Phase C — eBay Reconnect (CODE DONE / LIVE MANUELL OFFEN)
- `sell.fulfillment` in `USER_SCOPES` (unverändert vorhanden)
- UI: klarer Button „eBay neu verbinden“ → `/connect/ebay?next=/app/`
- Flag `ebay_fulfillment_fehlt_*` **nur** nach Orders-Erfolg löschen
  (nicht mehr in `_store_ebay_token` / Telegram-Connect)
- **MANUELL OFFEN für Sven:** Token kann live noch 403 liefern, bis neu
  verbunden + Orders klappen

### Phase D — Wegwerf-E2E (DONE automatisiert / HANDY MANUELL)
- `tests/test_e2e_offline.py` — Fake recognize/price/ebay, Claim, uncertain
  ohne Auto-Retry, dry_run ohne publishOffer
- `docs/E2E_HANDY.md` Abnahmeliste: AUTOMATISIERTER E2E / HANDY MANUELL /
  LISTING MANUELL / eBay Reconnect

### Phase E — CI (DONE Datei, nicht gepusht)
- `.github/workflows/ci.yml`: Py3.13, NUMBA_DISABLE_JIT, pytest, node --check,
  manifest+Pins

### Phase F — Skalierung ADR-001 (teilweise)
- F1: `web/ports.py` Schnittstellen ohne Verhaltensänderung
- F2–F5 Postgres/S3/Worker: **zurückgestellt** (nur `.env.production.example`)
- F6 Modularisierung: **zurückgestellt** per ADR-001
- F7: `scripts/micro_load_kv.py` — isolierte Messung, kein Kapazitätsclaim

### Vorgeschlagene Commit-Aufteilung (nicht ausgeführt)
1. `ui: Icons, a11y, Touch-Targets, Desktop-Layout + Guards`
2. `auth: Magic-Link/eBay → /app, SERO-Branding, Reconnect-Flag erst nach Orders`
3. `test: Offline-E2E, Auth-Redirects, Ports/ADR-001`
4. `chore: CI Workflow, .env.production.example, Status/E2E-Doku`

---

## Liquid-Glass-Theme umgesetzt (08.08. ~01:20)

Frontend-only visueller Umbau der PWA (Aufteilung/Funktionen unverändert):

| Pin | Stand |
|---|---|
| `sero.css` | **v=71** (Glas verstärkt, literal blur für Safari) — später v=72 |
| `sero-dark.css` | **v=6** |
| `sero.js` | **v=123** — später v=125 |

- **Tokens:** `--glass*`, `--surface`, Specular (`--glass-spec`), Blur nur auf Chrom
  (Topbar, Tabbar, Sheet, Toast, Detail-Bar, Login-Card, PTR).
- **Theme:** Light weicher Studio-Grund; Dark reines Schwarz + Glas in
  `sero-dark.css` (Media + `force-dark`). `@supports`-Fallback ohne
  `backdrop-filter` → opake `--surface-solid`.
- **Tabbar:** schwebend, 5 Tabs, aktive Linse (`.tic` / `.lens-go`), zentrale
  Kamera; `prefers-reduced-motion` dämpft Glow/Linse.
- **Grid/Karten:** leichte Transparenz, **kein** Backdrop-Blur auf Kacheln;
  Chart/Fotos ohne Blur.
- **WCAG:** Icon-Hits 44px (`.icon-btn`, `.col-act`), Safe Areas, AA-Kontrast
  über bestehende Label-Tokens.
- Kein Backend, keine Text-/Produktregel-Änderung, keine IDs/Handler gebrochen.
- Tests: **415 passed, 1 xfailed**; `node --check frontend/sero.js` OK;
  `git diff --check` OK; `sh tests/smoke.sh` grün. Port 3000 / launchd
  unberührt. Nicht committed.

---

## Exit Phase A–C — Verifikation 08.08. 01:10

Nachweise: `NUMBA_DISABLE_JIT=1 ./.venv/bin/python -m pytest tests/ -q`
→ **415 passed, 1 xfailed**; Smoke grün; `dry_run=true` in `kv`.

### Phase A (Exit erfüllt)
| Kriterium | Nachweis |
|---|---|
| Keine LLM-Preise | `tests/test_pricing.py` Prompt-/Analyse-Wächter |
| LLM-Query ignoriert im Live-Pfad | `resolve_pricing_query` in `app_api`/`main`; kein `search_query_for_pricing`-Read für Preise |
| Katalog nur bei `pricing_ready` | Gate `if _ready` + `tests/test_identity_gates.py` |
| Angebote kein Auto-Listenpreis | `apply_price_rule` + `test_angebote_kein_auto_listingpreis` |
| UI blocking_reasons | `identity_eval.blocking_texts` in `sero.js`, Pin `v=122`, STR_EN |
| A8 Tests | `test_identity.py`, `test_pricing.py`, `test_identity_gates.py` |
| Eval-Runner | `scripts/eval_identity.py` (offline Default; `SERO_EVAL_LIVE=1` → Exit 3, kein Netz) |

### Phase B (Exit erfüllt)
| Kriterium | Nachweis |
|---|---|
| App+Telegram gleicher Service | `claim_or_create_intent` + `execute_publish` in beiden Pfaden |
| Parallele Claims | `test_parallele_claims_ein_gewinner`, App/Telegram-Doppel |
| `publish_uncertain` nie auto | `execute_publish` Early-Return + Tests |
| ADR-003 Stufe 2 | `docs/adr/003-publish-zustandsautomat.md` |

### Phase C (Exit erfüllt)
| Kriterium | Nachweis |
|---|---|
| README/AGENTS sync | Frontend `frontend/`, Identity/Publish erwähnt |
| CI im Diff | `.github/workflows/ci.yml` (untracked/unpushed) |
| `bot.log` untracked | aus Index entfernt, `.gitignore` |
| Origin/Proxy | `SERO_TRUST_PROXY`, `tests/test_origin_proxy.py` |

Nicht gepusht, nicht committed auf Wunsch. Port 3000 / launchd unberührt.

---

## TradingView-UI: Chart + Profil (07.08. Nacht)

Frontend-only (kein Backend-Umbau):

- **Übersicht + Sammlung:** Statistik-Blöcke / Mini-Spark durch frameless
  TradingView-Linienchart ersetzt (`tvLineChart` in `sero.js`). Neon-grüne
  Linie (`--chart-up`), Y-Achse rechts (`2,86 K` / Euro), Daten unten an den
  Rändern, dünne Horizontal-Grids. Datenquelle: vorhandene
  `portfolio_history` / `state.history` (+ heutiger Live-Wert), keine
  LLM-Preise. Unter 2 Punkten: ehrlicher Leerzustand.
- **Profil:** Layout wie TradingView — Profil-Karte (Avatar, Name, Plan-Badge,
  Stats Veröffentlicht/Stück/Verkäufe), zwei Kacheln (Abonnement + Empfehlen
  via Web Share), Menüliste, Abmelden in Rot. Alle bisherigen Einstellungen
  bleiben erreichbar.
- **Feedback-Runde:** Titel Übersicht/Sammlung/Profil entfernt; Sammlung-Chart
  kompakt, Meta-Zeile weg; Filter ohne Wunsch/Duplikate, dafür Kategorien;
  Avatar mit Kamera-Overlay + fester Preview (kein Riesenfoto), Upload über
  „Sichern“.
- **Sammlung-Toolbar:** Keine Title-Row mehr. Zeile auf Preis-Höhe: Lupe links,
  Filter-Chips rechts horizontal scrollbar; Suche nur noch als Bottom-Sheet.
  Permanente `#colSearchBox` entfernt.
- Pins: `sero.css?v=69` / `sero-dark.css?v=4` / `sero.js?v=118`.
  Sammlung: Wert+Chart, rechts 3 Icon-Buttons (Suche/Filter/**Sortieren**),
  Chips darunter nur **auf eBay** + **Verkauft** + Kategorie-Chips.
  Foto-Menü kompakt (`sheet-fit`); Crop/Rotate ohne Schwarz (Cover im Rahmen,
  PNG bei Alpha). Endpunkte `photo-replace` / `photo-restore`.
  Freistellen getrennt (`/recrop`).
- **Stück-Detail:** Aktuelle eBay-Angebote, Katalog-Zuordnung und PSA-
  graded-market-Blöcke entfernt. Marktwert + letzte Verkäufe bleiben.
  „Mein Exemplar“ ist die Stammdaten-Zentrale (Herkunft / Karte / Zustand /
  Bestand), tippbar wo `patchItem` greift. Flache Liste Name→Nummer→Set→Sprache→
  Kategorie, dann Zustand, dann Bestand (ohne Notiz/Tags). Anzeige merged
  `card` + `card_info` (+ Heuristik); API liefert `card_info`/`analysis_title`.
- **Sammlung neu erkennen:** `POST /api/app/collection/rescan-all` reiht alle
  Stücke mit Foto in die Scan-Queue (Profil-Button). Pins `sero.js?v=121`.
  Backup vor Massenlauf: `sh backup.sh`.

## Claude-Review-Fixes A1–B4 (07.08. Nacht)

Paket aus dem Claude-Code-Review, fertiggestellt und getestet:

| ID | Thema | Stand |
|---|---|---|
| A1 | Sales-Sync: frisch lesen nach await, `price_dirty` schützt Listenpreis, Best-Offer ohne min_price nicht erfinden, `get_active_buyer_offers` → None bei Fehler | DONE |
| A2 | `card_passt_zu_info`: set_total gegen total ODER official (Secret Rare 199/165) | DONE |
| A3/B1 | `kurzform` hält Sprache/Auflage; `_GRADER_NUM`/`fits` trennen CGC Pristine ≠ Gem Mint | DONE |
| A4 | Slab: 18°-Cap; `case_kontur_nachschnitt` Label-Schutz (Höhe ≥80 %, Top-Zone ≥12 %) | DONE |
| B2 | Reconnect-Flag: Orders-Erfolg löscht Flag; `/api/me` prüft auch `ACCOUNT_UID_OFFSET+id` | DONE |
| B4 | Foto-Endpunkte → 409 während `analyzing`; „Neues Foto“ hängt an (`replace=0`); `photoIdxNow` robuster | DONE |

Pins `sero.js?v=111` (danach Chart/Profil → v112). Suite: **362 passed, 1 xfailed**; Smoke grün. `dry_run=true`.
Noch manuell (Sven): eBay neu verbinden (Scope `sell.fulfillment`), Handy-E2E.

## Verkauf Live-Preis + Preisvorschläge / Foto-Menü (07.08. Abend)

- **Verkauf-Tab:** Sync zieht den echten Listenpreis aus dem eBay-Offer
  (`pricingSummary`) und aktive Käufer-Preisvorschläge (Trading API
  `GetBestOffers`). Anzeige als Chip in der Liste und Block im Listing-Detail.
  Poll alle 60 s solange der Verkauf-Tab offen ist; Server-Throttle 90 s
  (mit `?refresh=1` 30 s); Hintergrundjob alle 30 Min. Reconnect-Hinweis
  bleibt, wenn `sell.fulfillment` fehlt — Preise synct trotzdem über Inventory.
- **Sammlung Detail:** Fotos deutlich größer (`d-photos large`); ⋯-Menü oben
  rechts mit Zuschneiden (`/recrop`), Drehen 90° (`/rotate`), Neues Foto,
  Vollbild. Endpunkte `POST .../photos`, `/recrop`, `/rotate`.
- Pins `sero.css?v=62` / `sero.js?v=111` (JS-Pin nach Review-Fixes). Tests: siehe
  Abschnitt oben. `dry_run=true`.

## Preis-Divergenz gleiche Karte (07.08. Abend)

Zwei Mega Charizard X ex JP #223 CGC 10 zeigten 101,95 € vs. 151,62 €.
Ursache zweistufig: (1) Sticky TCGdex-Fehl-Match (deutsches Fatale-Flammen
`me02-013` statt JP #223) erzeugte einen anderen `card_key` als der Hash aus
`card_info`. (2) Verkaufs-Cache war an die freie Suchformulierung gebunden —
zwei gleichwertige Queries → zwei Caches → Katalog-Überschreiben mit alten
Belegen. Fix: `catalog.card_passt_zu_info` entsorgt Fehl-Matches in Scan und
Refresh; Sold-Cache-Schlüssel = `kurzform` (`sold10_`). Beide Charizards und
das parallele Gyarados-Paar auf denselben Schlüssel/Preis gebracht
(~102 € belegt). Backup: `backups/data-20.db`.

## Go-Live-Checkliste (07.08. abends)

Umgesetzt aus dem Audit-Canvas `sero-golive-audit`:

| Punkt | Stand |
|---|---|
| `kv['dry_run']=true` (Üben) | **DONE** — `true`. Vor echtem Live: `/dryrun off` + Bot-Kickstart. |
| Scanner / Freisteller | **DONE 09.08.** — Roh/Hülle: BiRefNet; Graded/Slab: isnet (Case); Sonstiges: BiRefNet + Politur. |
| Graded vs Rohkarte | **DONE 08.08.** — `ensure_card_condition` / `has_real_graded_info`; UI nur Graded/Ungraded; Scan→Schnell-Listen (js v=129). |
| UX-Runde Übersicht/Profil | **DONE 08.08.** — Besitz-Filter, Profil-Ava, manueller Preis, Auktions-Sync GetItem, Profil-Kategorien. |
| Alte CGC `_cut` → `slab_recut` | **DONE** — Case komplett, Label geschützt. |
| `label_type` nachziehen | **DONE** — pristine/gem_mint gesetzt. |
| 4 Error-Entwürfe | **DONE** — 0 übrig. |
| Sales-Sync 403 | **CODE DONE / BLOCKED Sven** — Flag `ebay_fulfillment_fehlt_*` gesetzt; UX Reconnect; OAuth-URL enthält `sell.fulfillment` in `USER_SCOPES`. Token `5694742134` noch ohne Scope → einmal eBay neu verbinden. |
| Production-Env | **bewusst offen** — kein `APP_ENV=production` (LAN-HTTP). |
| E2E Handy Foto→Listen | **BLOCKED Sven** — Checkliste `docs/E2E_HANDY.md`. API-E2E (Login-Session testkunde, `/api/me`+collection+dashboard+sales, dry_run) **DONE**, kein Publish. |
| GitHub Push | **DONE** — `origin/master` = `a362ccd` (Reconnect-UX + Doku). |
| CI | **LOKAL READY / BLOCKED Push** — `.github/workflows/ci.yml` untracked lokal. Push braucht `workflow`-Scope. Befehl unten. |

Backup vor DB-Aktionen: `backups/data-20.db`.

### CI-Push (nur Sven, einmalig)

```
gh auth refresh -h github.com -s repo,workflow,gist,read:org
# Browser: Device-Code bestätigen, dann:
cd ~/ebay-bot && git add .github/workflows/ci.yml && \
  git commit -m "CI: pytest + node --check auf Push/PR" && git push
```

## CI + Reconnect-UX (07.08. Nacht)

- `.github/workflows/ci.yml`: pytest auf Python 3.13 + `node --check frontend/sero.js`.
  Datei lokal vorhanden; Push blockiert ohne Scope `workflow` (Auth-Refresh braucht Browser).
- Verkauf-Tab zeigt Reconnect-Hinweis (`ebay_needs_reconnect`); Profil-Wert orange.
  Pin `sero.js?v=110`. Consent-URL baut `USER_SCOPES` inkl. `sell.fulfillment`.
- Verifikation 07.08. Nacht: dry_run=true; web+bot running; 353 passed / 1 xfailed;
  Smoke folgt; API-E2E mit Testkonto grün (kein eBay-Publish).

## Freisteller / Sales-Sync (07.08. spät abends)

- **Slab enger + aufrecht ohne Zerren:** Perspektiv nur wenn Symmetrie-Gates
  greifen UND der Slab schon nahezu aufrecht ist. Sonst nur `warpAffine`.
  Neu: `untergrund_trim` (Filz), `case_kontur_nachschnitt` (Kontur-Drehung/
  Crop mit Label-Schutz), `_slab_kontur_winkel` als dritte Stimme neben
  Vision-Ecken und Hough. Feinjustierung ≤4,5°. Vertrag in
  `test_render_standard`.
- **Sales-Sync 403 UX:** kv-Flag + Profil-Hinweis + klarere `/verbinden`-Texte.
  Ein erneutes Verbinden reicht — kein Token-Refresh-Hack.

## Zweiter Durchgang (07.08. nachmittags): Roadmap-Punkte umgesetzt

- **Slab: aufrecht + enger Zuschnitt (07.08. spät):** `slab_recut` richtet
  per Perspektiv-Warp hinter Symmetrie-Gates auf (Parallelogramm → kein Zerren);
  bei asymmetischen Kanten nur `warpAffine`-Rotation. Danach `kanten_trim`
  (je Zeile/Spalte) + `tisch_trim` (warmer Kork/Holz-Rand weg). Klares Case
  bleibt; kein rembg. Sechs CGC-Stücke aus `photos_raw` neu geschnitten;
  `label_type` pristine/gem_mint unverändert. Tests in `test_render_standard`.
- **Slab: rembg nach Warp (08.08., ersetzt 07.08.-Regel):** Svens Collection-
  Norm braucht echte Transparenz. Warp bleibt kosmetikfrei; danach
  `isnet-general-use`. Frühere BiRefNet-Probleme (Case-weg) mit isnet +
  Morph-CLOSE/Label-Rettung abgefangen. Siehe `tmp/cutout_eval/`.
- **Historie 07.08. abends (überholt):** Rembg nach Warp war wegen BiRefNet
  an klarem Plastik abgeschaltet (Label/Karte schwebten getrennt). 08.08.
  ersetzt das durch isnet + Form-Reparatur; Vertrag in
  `test_render_standard` / `test_cutout_layout`.
- **CGC Pristine + PicsArt-Freisteller (07.08.):** `graded.label_type`
  (pristine/perfect/gem_mint) — Gold-Siegel „CGC Pristine 10“, Titel + Verkaufssuche.
  Slab-Pfad siehe Punkt oben (PicsArt-Nachschritt zurückgenommen).
  Pins `sero.css?v=61` / `sero.js?v=109`.
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
- Suite: **340+ passed, 1 xfailed**; Smoke grün; `sero.js?v=109`.
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
| Tests | **353 passed, 1 xfailed** (`pytest tests/ -q`) plus `tests/smoke.sh` |
| Installierbarkeit | Frisches venv + `requirements.txt` → alle Kernmodule importieren (geprüft) |
| Betrieb | launchd `com.listo.web` auf 0.0.0.0:3000, KeepAlive, ohne `SERO_DEV_CODES` |
| Frontend | `sero.js?v=110`, `sero.css?v=62` |
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
- CI: `.github/workflows/ci.yml` liegt im Repo. Push der Workflow-Datei
  braucht Token-Scope `workflow` (aktueller `gh`-Login hat ihn nicht).

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
