# SERO 4.1.0 — clean skin + micro-motion (kein Feature-Scope)

Repo: `https://github.com/SmortyCode/sero` (branch `master`, HEAD = Live).
Live-Quelle: `https://app.seromunich.com/app/` ist byte-identisch mit `frontend/index.html` (Cache: `sero.css?v=162`, `sero.js?v=253`, `sero-clean.css?v=41`, `sero-profile.js?v=22`, `SERO_APP_VERSION = "4.1.0"`).

Du implementierst. Du erfindest keine Features, keine neuen Tabs, keine neue IA. Vanilla PWA bleiben (`frontend/index.html` + `sero.js` + `sero-clean.css` + `sero.css` + `sero-dark.css` + `sero-detail.js` / `sero-mobile.js` / `sero-profile.js`). Kein React/Vue, kein GSAP/Framer/Lottie/anime, keine Google Fonts in der PWA, Mascot-Datei nicht nachladen.

Viewport-Referenz: **390×844**. Copy **Deutsch**. Draft-first, eBay.de, nie auto-publish. Wordmark nur als `<img>` (kein Text-Logo, kein CamelCase-Wordmark, kein eBay-Logo). Deploy nicht. Light-Skin nicht zerbrechen: Token-Änderungen in `sero-clean.css` und den Light-Pfaden spiegeln.

Ziel: die App soll sich anfühlen wie iOS 26 (ruhig, schwarz/weiß/grau, Glas nur an Nav/Sheets, Spring-Motion), nicht nach mehr Produkt aussehen.

## Nicht anfassen (gelockte Screens)

- Sammlung: Wertkurve mit **7T / 30T / 1J** + Grid/Liste (Kacheln = 2×2 bleibt als Toggle).
- Scannen, Verkaufen (Entwürfe / Aktiv / Verkauft), Profil vs Einstellungen als getrennte Screens.
- Gast-Scan und Login-Flow nicht umbauen. Kein neues Onboarding, keine Paywall, keine Marketing-Landing in der PWA.

## Ist-Zustand (Live, nicht raten)

Default: `html.skin-clean.force-dark`. Drei Skins liegen übereinander; Clean überdeckt Navy-Liquid-Glass. Nicht drei Paletten weiterbauen — Clean ist die Wahrheit.

Vorhandene Motion in `sero.css` **wiederverwenden**, nicht neu erfinden:
`--spring: cubic-bezier(.32,.72,0,1)`, `pageIn` / `pageInL` / `pageInR`, `itemIn` (Stagger `--i`), `slidein`/`slideout`, `rise`, `#viewApp.recede`, Button `scale(.98)`, `prefers-reduced-motion` + `prefers-reduced-transparency` respektieren.

Was Clean heute kaputtmacht: `animation: none` auf Login-Karte; Deltas/`--green`/`--chart-up` auf `#d1d1d6` abgeflacht; Endlos-Pulse (`splashPulse`, `orbbreathe`); Chrome-3D-Wordmark auf jeder Seite; kein Shared-Element; Verkaufen-Tabs ohne Slide; Kurve morph’t nicht.

## Arbeit (in dieser Reihenfolge)

### 1. Chrome runter, Nav bleibt Glas

- In-App-Wordmark: flache einzeilige PNG-Variante als `<img>`. Chrome-Bevel nur Splash + App-Icon. Kein CSS-Text-Logo.
- Glas (`backdrop-filter`) nur Tab-Bar, Sheets, Login-Dock, Suche. **Keine** Glass-Karten im Content, kein Glas auf dem 2×2-Grid.
- `splashPulse` und Tab-Kamera `orbbreathe` aus. Ein kurzes `logoIn` reicht.
- `#viewApp.recede` (ganzes App-Scale+Blur) nur wenn es sich leicht anfühlt; sonst auf Sheet-Dim reduzieren. 40px-Blur im Clean-Skin nicht erhöhen (Clean hat 18px — da bleiben).

### 2. Eine Primäraktion pro Screen

**Start**
- Ein Primary: weiße Pille „Artikel fotografieren“.
- „Mehrere Produkte scannen“ und „Nur zur Sammlung hinzufügen“ als **eine** Secondary-Zeile, zwei Outlined-Chips, nicht als gleich schwere Text-Links.
- FAQ-Akkordeon aus Start nach **Einstellungen → Hilfe** (oder Hilfe-Screen). Start ist App, kein Marketing.
- Die saturierte **blaue** Wertkarte auf Start auf Near-Black ziehen (gleiche Surface wie restliche Cards). Mint nur als Chart-Linie, Grün nur im Delta-Chip.

**Scannen**
- Gleich: eine weiße Pille „Artikel fotografieren“. Die zwei anderen als Chips.
- Gallery-Icon bekommt sichtbares Label „Aus Fotos“.
- Zeile „Standard für eBay-Entwürfe — Sofortkauf · Marktwert · Schwarz“: bei 390px **nicht überlappen**. Label oben, Werte darunter als truncated muted second line + Chevron.
- Viewfinder-Rahmen darf eine ruhige Idle-Motion haben (kein Pulse). Kein Fake-Kamera-Preview erfinden, wenn die Camera API den Frame erst nach Tap füllt.

### 3. Sammlung: ehrlich, lesbar, lebendig

- Unter ~3 Datenpunkten: keine tote Hairline in 200px Schwarz. Kompaktes Empty: „Wert wird ab dem 3. Stück sichtbar“. Pills 7T/30T/1J bleiben.
- Range-Wechsel: 250–300ms Path-Morph der Kurve + Crossfade der Achsen, `--spring`. Hero-€ count-up (tabular nums) beim Range-Switch und beim ersten Paint.
- Delta nicht grau. Ein Akzent: Plus grün, Minus rot. Rest der UI bleibt monochrom. Tokens `--green` / `--orange` / `--chart-up` im Clean-Skin dafür wieder sichtbar machen — **nur** für Delta/Chart, nicht für Buttons.
- Item-Karten: Preis rechts als Tabular-Numeral neben/unter dem Titel, sichtbar. Kategorie „Weiteres“ als kleines muted Chip, nicht als Hauptzeile.
- „Suchen · Filtern · Sortieren · Kacheln“ sind keine Links. Daraus eine echte Control-Row: Suche als Icon-Field, Filter/Sort als Chips mit Active-State, Kacheln als List/Grid-Toggle (2×2 bleibt).
- Grid/Liste: `itemIn`-Stagger behalten. Shared-Element vom Thumbnail ins Detail (Foto morph’t, Rest slide/fade). Fallback: bestehendes `slidein`, wenn Shared-Element zu riskant für den Monolithen — dann trotzdem Thumbnail-Hero im Detail ohne Sprung.
- Floating Tab-Bar: `padding-bottom` ~96px auf allen Scroll-Views, letzte Karte nie abschneiden.

### 4. Verkaufen

- Tabs Entwürfe / Aktiv / Verkauft: Sliding-Underline + 200ms horizontaler Crossfade, `--spring`. Empty-Card feste `min-height`, kein Jump zwischen Tabs.
- Verkauft ohne leere weiße Pille: muted „Erlöse erscheinen hier“, kein zweites Primary.
- Unterline-Tabs im Clean-Skin, kein Segmented-Glass auf `#salesSeg`.

### 5. Motion-Kit (CSS/WAAPI, kein Library)

Überall Press: `transform: scale(.96)` ~120ms `--spring` auf Tab-Items, Cards, Chips, Primary. Active schon auf Buttons vorhanden — auf die Text-Controls und Nav ausweiten.
- Tab-Wechsel: vorhandene `pageInL/R` anlassen, nicht hart cutten.
- Sheets: `rise` + Dim, Spring, nicht Linear.
- Login-Karte: `animation: none` im Clean-Skin **weg**, `pageIn` wieder an.
- Profil-Stats und Listen: „—“-Platzhalter durch Skeleton-Shimmer ersetzen, dann Inhalt. `prefers-reduced-motion: reduce` → keine Shimmer, kein Morph, nur Opacity.
- Scan-Success / „Entwurf fertig“: kurzer Scale-Pop (`ticpop` existiert), kein Confetti, kein Party-Loop.

### 6. Profil / Einstellungen

Nicht umbauen. Loop Profil → Einstellungen → „Konto & Profil“ nicht doppelt. Back aus Einstellungen landet auf Profil über dem darunterliegenden Tab. Settings-Liste ist der visuelle Maßstab (gruppierte Rows, Icon-Tiles) — Collection-Controls in diese Sprache ziehen, nicht umgekehrt.

## Explizit nicht tun

- Keine neuen Dependencies, keine Font-Dateien, Landing-Figtree/Unbounded nicht in die PWA.
- Keine dritte Skin-Datei, Navy-Glass nicht reaktivieren.
- Start-Tab nicht löschen, Scannen nicht hinter Login verstecken.
- Keine Copy-Änderungen außer wo Labels fehlen (Gallery) oder Empty-States (Kurve, Verkauft).
- Kein Deploy, keine Versionsnummer-Show außer Cache-Bust der angefassten Assets (`?v=` hochzählen).

## Done

Bei 390px, Dark-Clean:

1. Wordmark flach in der App, Chrome nur Splash.
2. Start: 1 Primary, FAQ weg, Chart-Karte nicht blau.
3. Scannen: Gallery gelabelt, Defaults-Zeile ohne Overlap.
4. Sammlung: Empty-Kurve unter 3 Punkten, Preis sichtbar, Controls als Chips, 7T/30T/1J morph’t, Tab-Bar clippt nicht.
5. Verkaufen: Underline gleitet, Empty-Höhe stabil.
6. Press-Feedback + Skeleton + Count-up, `prefers-reduced-motion` still.
7. Light-Skin nicht regressiv. Kein Auto-Publish. `SERO_APP_VERSION` bleibt 4.1.0 (Patch-Notes im PR, nicht die Semver erfinden).

PR mit Before/After-Screenshots der sechs Screens (Login, Start, Sammlung, Scannen, Verkaufen, Einstellungen).
