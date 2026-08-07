from bot.main import check_price_plausibility, suggest_fixed_price


def test_implausible_comps_fall_back_to_estimate():
    """17-€-Apfelschorle: Comps-Median weit über Claudes Marktwert -> Schätzung."""
    research = {"count": 8, "min": 9.0, "max": 25.0, "median": 17.0, "query": "Apfelschorle"}
    listing = {"estimated_price_range_eur": {"low": 1.0, "high": 2.5}}
    out = check_price_plausibility(research, listing)
    assert out["estimated"] is True
    assert out["median"] == 1.75


def test_plausible_comps_are_kept():
    research = {"count": 12, "min": 3200.0, "max": 4900.0, "median": 3800.0, "query": "Luffy PSA 10"}
    listing = {"estimated_price_range_eur": {"low": 3000.0, "high": 5000.0}}
    out = check_price_plausibility(research, listing)
    assert "estimated" not in out
    assert out["median"] == 3800.0


def test_too_few_comps_fall_back_to_estimate():
    research = {"count": 2, "min": 5.0, "max": 90.0, "median": 47.5, "query": "x"}
    listing = {"estimated_price_range_eur": {"low": 40.0, "high": 60.0}}
    out = check_price_plausibility(research, listing)
    assert out["estimated"] is True


def test_missing_estimate_keeps_comps():
    research = {"count": 8, "min": 10.0, "max": 20.0, "median": 15.0, "query": "x"}
    assert check_price_plausibility(research, {}) is research


def test_no_comps_and_estimate_gives_estimate():
    listing = {"estimated_price_range_eur": {"low": 10.0, "high": 20.0}}
    out = check_price_plausibility(None, listing)
    assert out["estimated"] is True and out["median"] == 15.0


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
