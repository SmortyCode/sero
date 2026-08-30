# SERO — Follow-up: Filter, Sheet, Detail-Tabs, Light

Repo: `https://github.com/SmortyCode/sero`. Live-Quelle: `https://app.seromunich.com/app/` (`sero.js?v=254`, `sero.css?v=163`, `sero-clean.css?v=42`). Clean-Skin bleibt die Wahrheit (`html.skin-clean`).

Du implementierst. Keine neuen Features, keine neue IA außer den zwei Detail-Tabs unten (Info | eBay). Vanilla PWA, kein React/GSAP/Framer. Viewport **390×844**. Copy **Deutsch**. Draft-first, nie auto-publish. Wordmark nur als `<img>`. Kein Deploy. Cache-Bust (`?v=`) der angefassten Assets hochzählen. `SERO_APP_VERSION` nicht erfinden.

Gelockt bleibt: Sammlung Kurve **7T/30T/1J** + 2×2, Scannen, Verkaufen, Profil vs Einstellungen.

## 1. Filter-Sheet: One Piece / Pokémon doppelt + passt nicht

**Ist (Live):** `invCatChipHtml` (`sero.js` ~1028) setzt bei One Piece und Pokémon immer Logo **plus** `<span class="fchip-lab">`. Die SVGs `assets/logo-onepiece.svg` / `assets/logo-pokemon.svg` sind selbst schon der Schriftzug (`<text>ONE PIECE</text>` / `<text>Pokémon</text>`). Sichtbar: Name zweimal auf dem Chip.

`html.skin-clean .fchip-logo { filter: invert(1) }` gilt in beiden Themes — im Light werden die Wordmarks weiß.

`openColFilter` öffnet das Sheet mit `withCats/withLang/withRegion/withYear: true`. `invFilterGroups`: leere Auswahl = `all` → Sprache **und** Region gleichzeitig. `showGrade = cond !== "raw"` → Grading ist da, obwohl Zustand leer ist. Sheet füllt ~88vh, muss scrollen, fühlt sich nicht wie ein Filter an.

**Soll**

- One Piece / Pokémon: **ein** Name. Wordmark-SVG **oder** Label, nicht beides. `aria-label` bleibt. Andere Kategorien (Games, Weiteres, Weitere Karten) nur Text.
- `filter: invert(1)` nur in Dark. Light: dunkle Wordmarks, kein Invert.
- Progressive Disclosure, Default ohne Kategorie:
  - Zustand: Roh / Graded.
  - Grading + Note **nur** wenn Graded aktiv.
  - Sprache **nur** wenn eine TCG-Kategorie aktiv (One Piece, Pokémon, Weitere Karten).
  - Region **nur** wenn Games aktiv.
  - Wert + Jahr kompakt (eine Zeile je Range, nicht das Sheet sprengen).
- Chips wrappen mit 8px Gap, kein Overflow über Sheet-Padding. Breite der Logo-Chips nach dem Duplikat-Fix prüfen (390px).
- `CAT_CHIP_ORDER` nicht still ignorieren, wenn du die Reihenfolge anfasst: One Piece, Pokémon, Games, dann die Rest-Cats aus `INV_CATS`. Nicht mehr Cats erfinden.

Nicht: neue Filter-Dimensionen, keine Suche in diesem Sheet.

## 2. Sheet schließen: Lücke oben + Tap außerhalb + größerer Ziehbereich

**Ist:** `.sheet-grip` ist 36×5px (Padding 12×40, `sero.css` ~2407). Drag-Handler hängt **nur** am Grip (`sero.js` ~11459). `openSheet` setzt `sheetBackdrop.onclick = closeSheet` schon — aber das Filter-Sheet steht so hoch, dass kaum Backdrop sichtbar ist. `max-height: min(88vh, …)`.

**Soll** (alle `openSheet`-Sheets, mindestens Filter und Sortieren)

- Oben eine echte Lücke: Sheet `max-height` ~78–82vh, nicht kantenbündig. Der verdunkelte Backdrop darüber ist tappable und schließt.
- Ziehen: Hit-Target mindestens 44px. Grip **plus** Titelzeile (`#sheetTitle` / Header-Row) sind Drag-Handle, nicht nur der Strich. Schwellwert ~90px darf bleiben.
- Backdrop-Tap schließt, wenn `dismissible !== false` (heute schon so — nicht kaputtmachen, nur sichtbar machen).
- `#sheetBody` bleibt der einzige Scroll-Bereich. Drag auf Body-Inhalt scrollt, schließt nicht.

## 3. Artikel-Detail: Info | eBay, nicht stapeln

**Ist:** `showDetailSeg` (`sero.js` ~9067) setzt `det.showListing = true`, **`det.seg = "overview"` immer**, `renderDetail`, dann `scrollIntoView(#detailListingBlock)`. `renderDetail` (~9631) packt `overviewPane + listingHtml` **in dieselbe** `[data-pane="overview"]`. CTA „Einstellen“ (`syncDetailCtaDock` ~9121) ruft `showDetailSeg(det, "sell")` — der eBay-Block erscheint **unter** der Info. Genau der zweite Textblock.

Swipe overview ↔ sell existiert in `bindDetailPaneSwipe`, die UI hat aber keine Tabs und nur ein Pane.

**Soll**

- Zwei Tabs im Detail, unter dem bestehenden Hero (gelocktes Detail-Chrome nicht neu erfinden): **Info** | **eBay**.
- Ein Pane sichtbar. Info = heutiges Overview (Preis, Daten). eBay = heutiges Listing (`ebayPane` / `#detailListingBlock`).
- „Einstellen“ wechselt auf den Tab eBay. Inhalt **ersetzt** Info, hängt nicht darunter. `det.seg` wirklich `"overview"` | `"sell"` (oder `"ebay"`), nicht hart auf overview zurücksetzen.
- CTA-Dock (Als Entwurf behalten / Einstellen) nur auf Info. Auf eBay die bestehenden Listing-Actions, nicht ein zweites Info-Duplikat.
- Zurück / Tab Info zeigt wieder nur Overview, Listing-DOM nicht unter dem Preis lassen.
- Shared-Element / Hero bleibt. Kein dritter Tab, kein neuer Listing-Flow, kein Auto-Publish.

## 4. Light-Modus komplett

**Ist:** Tokens in `html.skin-clean.force-light` (`sero-clean.css` ~1562) sind angelegt. Daneben liegen Dark-Hardcodes ohne Light-Override, u. a.:

- `.inv-tool` / `.inv-chip` → `#1c1c1e` + weiße Border (`~1673`); Light-Override existiert nur teilweise.
- `.fchip-logo { filter: invert(1) }` (Clean ~822) nicht Dark-scoped.
- `#splash { background: #000 }` bleibt in Light (ok, Splash darf schwarz bleiben).
- Sheets, Detail, Filter-Chips, Tab-Bar, Count-Pill, Scan-Chips, eBay-CTA: Stückwerk, nicht ein Theme.

**Soll:** Light ist Canvas `#fff`, Text `#000`, Fills `#f2f2f7` / `#e5e5ea`, Primary schwarz auf weißem Canvas (wie die Tokens schon sagen). Jeder Screen:

Sammlung, Filter-Sheet, Sort-Sheet, Item-Detail (beide Tabs), Scannen, Verkaufen, Profil, Einstellungen, Tab-Bar, Topbar, Toast, Login.

Kein Rest-Schwarz als Karten-Fill, keine weißen Glyphs auf weiß, keine `force-dark`-Inseln. `color-scheme: light`. Wordmark: vorhandene Light-PNG (`wordmark-navy` / Split), nicht die Chrome-3D. Splash darf schwarz bleiben.

Delta/Chart: Grün/Rot nur dort, Rest monochrom.

## Nicht tun

- Keine neuen Dependencies, keine dritte Skin-Datei, Navy-Glass nicht reaktivieren.
- Kein Deploy.
- Keine Copy-Erfindung außer wo ein Label durch den Duplikat-Fix wegfällt (`aria-label` reicht).
- Kommentar-Kampagne / X nicht anfassen.

## Done (390px)

1. Filter: One Piece und Pokémon je **einmal**. Kein Logo+Text-Double. Light: Wordmarks lesbar.
2. Filter ohne Auswahl: kein Grading, keine Sprache, keine Region. Sheet ohne Pflicht-Scroll für die Default-Höhe.
3. Sheet: sichtbare Lücke oben, Backdrop-Tap schließt, Ziehen an Grip **oder** Titel.
4. Detail: Tabs Info | eBay. Einstellen öffnet eBay-Pane, kein zweiter Textblock unter Info.
5. Light: alle sechs Screens plus Filter/Detail ohne Dark-Leaks.

PR mit Before/After: Filter (Dark+Light), Sheet-Lücke, Detail Info vs eBay, Sammlung Light.
