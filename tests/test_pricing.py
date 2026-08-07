from pathlib import Path

from bot.main import comps_verwertbar, suggest_fixed_price


# ── Audit P0.2 (07.08.): Preise kommen NIE aus dem Sprachmodell (ADR-002) ────
# Die alte check_price_plausibility ersetzte dünne/unplausible Comps durch die
# Mitte einer KI-Preisspanne. Neu gilt: unter 3 Vergleichsangeboten gibt es
# ehrlich KEINEN Vorschlag — der Nutzer trägt den Preis selbst ein.

def test_genug_comps_bleiben_unveraendert():
    research = {"count": 8, "min": 10.0, "max": 20.0, "median": 15.0, "query": "x"}
    assert comps_verwertbar(research) is research


def test_zu_wenige_comps_geben_keinen_preis():
    """2 Zufallstreffer sind keine Preisbasis — vorher sprang hier die KI-Spanne ein."""
    research = {"count": 2, "min": 5.0, "max": 90.0, "median": 47.5, "query": "x"}
    assert comps_verwertbar(research) is None


def test_keine_comps_geben_keinen_preis():
    assert comps_verwertbar(None) is None


def test_prompt_verlangt_keine_preisschaetzung():
    """Quelltext-Wache: Wer estimated_price_range_eur (oder ein anderes
    Preis-Schätzfeld) wieder in den Analyse-Prompt einbaut, verletzt ADR-002."""
    from bot.claude_client import SYSTEM_PROMPT
    assert "estimated_price_range_eur" not in SYSTEM_PROMPT
    assert "NIEMALS selbst einen Preis" in SYSTEM_PROMPT


def test_analyse_erzeugt_keine_ki_preisfelder():
    """Quelltext-Wache: app_api darf est_low/est_high nicht mehr aus der
    KI-Antwort erzeugen und keinen est_value aus einer Schätzung ableiten."""
    quelle = (Path(__file__).parent.parent / "web" / "app_api.py").read_text()
    # Erlaubt ist nur die eine Abwehr-Zeile (preset.pop), die Alt-Daten filtert.
    assert quelle.count("estimated_price_range_eur") == 1
    assert 'preset.pop("estimated_price_range_eur"' in quelle
    assert 'item["est_low"] = float' not in quelle
    assert '"price_label"] = "KI-Schätzung"' not in quelle


def test_altdaten_estimate_wird_beim_refresh_verworfen():
    """Alt-Werte aus der abgeschafften KI-Spanne (source=estimate) müssen beim
    nächsten Refresh neu bewertet werden, nicht ewig stehen bleiben."""
    quelle = (Path(__file__).parent.parent / "web" / "app_api.py").read_text()
    start = quelle.index("async def refresh_item_price")
    block = quelle[start:start + 1500]
    assert 'price_source") == "estimate"' in block
    assert "ki_schaetzung_verworfen" in block


def test_iqr_trim_removes_fantasy_price():
    """browse.research_price-Trimmen: ein 99-€-Ausreißer verzerrt den Median nicht mehr."""
    import statistics

    prices = [1.5, 1.8, 2.0, 2.2, 2.5, 99.0]
    trimmed = sorted(prices)
    q = statistics.quantiles(trimmed, n=4)
    iqr = q[2] - q[0]
    kept = [p for p in trimmed if q[0] - 1.5 * iqr <= p <= q[2] + 1.5 * iqr]
    assert 99.0 not in kept
    assert statistics.median(kept) < 3


def test_suggest_price_low_value_item():
    assert float(suggest_fixed_price(1.75)) <= 1.75
    assert float(suggest_fixed_price(1.75)) >= 1.0


# ── Svens Manga-Fall (03.08.): BGS 9.4 und BGS 9.0 hatten denselben Preis ────

def test_bessere_note_ist_nie_billiger():
    """PriceCharting kennt nur Grade 9 / 9.5 / 10. Ohne Feinabstufung bekamen
    eine BGS 9.4 und eine BGS 9.0 exakt denselben Wert (603,12 €) — obwohl die
    bessere Erhaltung erkennbar mehr bringt."""
    from web.pricecharting import _grade_fields, _zwischenstufe
    prod = {"graded-price": 10000, "box-only-price": 20000,
            "manual-only-price": 50000, "bgs-10-price": 90000}

    def wert(note):
        g = {"grader": "BGS", "grade": note}
        cents = used = None
        for f in _grade_fields(g):
            if prod.get(f):
                cents, used = prod[f], f
                break
        return _zwischenstufe(prod, g, cents, used)

    stufen = ["9.0", "9.1", "9.2", "9.4", "9.5", "9.6", "9.8", "10"]
    werte = [wert(s) for s in stufen]
    for a, b, na, nb in zip(werte, werte[1:], stufen, stufen[1:]):
        assert b > a, f"BGS {nb} ({b}) ist nicht teurer als BGS {na} ({a})"


def test_keine_erfundene_zwischenstufe_ohne_stuetzstelle():
    """Fehlt der obere Nachbarwert, bleibt es beim Feldwert — lieber grob und
    belegt als fein und geraten."""
    from web.pricecharting import _zwischenstufe
    nur_unten = {"graded-price": 10000}
    assert _zwischenstufe(nur_unten, {"grader": "BGS", "grade": "9.4"},
                          10000, "graded-price") == 10000
    # Unplausible Reihenfolge (oben billiger als unten) wird nicht verrechnet
    verdreht = {"graded-price": 20000, "box-only-price": 10000}
    assert _zwischenstufe(verdreht, {"grader": "BGS", "grade": "9.4"},
                          20000, "graded-price") == 20000


def test_ganze_stufen_bleiben_exakt():
    """Auf einer bekannten Stützstelle darf nicht interpoliert werden."""
    from web.pricecharting import _zwischenstufe
    prod = {"graded-price": 10000, "box-only-price": 20000}
    assert _zwischenstufe(prod, {"grader": "BGS", "grade": "9.0"}, 10000, "graded-price") == 10000
    assert _zwischenstufe(prod, {"grader": "BGS", "grade": "9.5"}, 20000, "box-only-price") == 20000


# ── Audit P0.5: Lizenz-Schalter — riskante Quellen sind im Code-Default AUS ──

def test_130point_default_aus(monkeypatch):
    import asyncio
    monkeypatch.delenv("SERO_QUELLE_130POINT", raising=False)
    from web.sold import fetch_sold
    assert asyncio.run(fetch_sold(None, "Glurak PSA 10", 1.1)) is None


def test_pricecharting_default_aus(monkeypatch):
    import asyncio
    monkeypatch.delenv("SERO_QUELLE_PRICECHARTING", raising=False)
    from web.pricecharting import lookup_pc
    assert asyncio.run(lookup_pc(None, "Zelda NES", None, 1.1)) is None
