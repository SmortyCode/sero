# ADR-002: Preisquellen-Politik — keine LLM-Preise, Lizenz-Schalter je Quelle

Status: beschlossen und UMGESETZT 07.08.2026 — Prompt ohne Preisfeld für
Katalogware, `comps_verwertbar` (Mindestbeleg-Regel), Alt-Daten-Entgiftung
beim Refresh, Lizenz-Schalter SERO_QUELLE_130POINT / SERO_QUELLE_PRICECHARTING
(Default AUS). Quelltext-Wachen: tests/test_pricing.py.

**Nachtrag 09.08.2026 — Alltagsprodukte + Spiele:** Für Stücke ohne Domäne
(Sammelkarte/TCG/Manga/Comic) und für Domäne `game` darf die Analyse
`suggested_list_price_eur` liefern und die App zeigt einen KI-Richtwert
(`price_source=estimate`, `price_reason=KI_RICHTWERT`, Zustand `spanne`).
Hinweis in der UI: unsicher, manuell änderbar. Nie Publish-Preisbasis.
Karten & Manga bleiben fail-closed (unter 3 Comps = kein Preis;
estimate beim Refresh verworfen). Spiele: auch `comps_verwertbar(..., min_count=1)`.

## Kontext

Der Marktwert ist das Kernversprechen der App — und die härteste Stelle:
Es gibt keine frei buchbare, legale API für echte eBay-Verkaufspreise
(Marketplace Insights: Antrag abgelehnt; findCompletedItems: abgeschaltet).
Gleichzeitig verlangt der Analyse-Prompt heute noch eine Preisspanne vom
Sprachmodell — im Widerspruch zur Produktregel „keine erfundenen Preise".

## Entscheidung

1. **Preise kommen NIE aus dem Sprachmodell.** Das LLM liefert Beobachtungen
   (was ist auf dem Foto, mit Belegen und Konfidenz), keine Zahlen mit
   Euro-Zeichen. Bis der Prompt-Umbau (P0.2) fertig ist, gilt die heutige
   Abfederung: KI-Spannen werden als `price_state != belegt` ausgewiesen und
   von jeder echten Quelle überschrieben.
2. **Jede Quelle hat einen Herkunfts- und Vertrauensstatus**, der bis in die
   UI durchgereicht wird: `belegt` (echte Verkäufe), `spanne`/`angebote`
   (aktive Angebote, ehrlich beschriftet), `unbekannt` (lieber ehrlich als
   erfunden).
3. **Jede Quelle bekommt einen Lizenz-Schalter** (Feature-Flag, Default AUS
   für alles ohne Vertrag). Für Fremdnutzer-Betrieb dürfen nur eingeschaltet
   sein: TCGdex/Scryfall/YGOPRODeck (rohe Karten, frei), eBay Browse
   (aktive Angebote), eigene über SERO erzeugte Verkäufe (Sell-API,
   vertraglich sauber — braucht noch den Fulfillment-Scope).
   130point und PriceCharting sind Betreiber-Risiko-Quellen für den
   Einzelbetrieb und bleiben für Fremdnutzer AUS.

## Konsequenzen

- Für gegradete Slabs, Retro-Spiele und Manga gibt es damit anfangs oft nur
  „Angebotslage" statt „Marktwert". Das ist gewollt: ehrlich vor vollständig.
- Die langfristig beste Quelle sind die eigenen Verkäufe der Nutzerbasis
  (jedes SERO-Listing, das verkauft wird, ist ein eigener, legaler Beleg).
  Offene Fragen dafür: DSGVO-Basis der Aggregation, eBay-Lizenzbedingungen.
