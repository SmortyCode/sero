"""Der Grader-Kanon (Stufe 3, 03.08.2026) — eine Firma, eine Schreibweise.

Vorher hielt jede Code-Ecke ihre eigene Grader-Liste. Die teuerste Folge:
„BECKETT 9.0" und „BGS 9" waren zwei Katalogzeilen — derselbe Slab bekam
je nach Schreibweise der Analyse zwei verschiedene Preise.
"""

import pytest

from web import slab
from web.catalog import grade_bucket


# ────────────────────── Kanon und Normalisierung ──────────────────────

@pytest.mark.parametrize("roh,kanon", [
    ("Beckett", "BGS"), ("beckett", "BGS"), ("BGS", "BGS"), ("bgc", "BGS"),
    ("PSA", "PSA"), ("psa", "PSA"), ("CGC", "CGC"), ("WATA", "WATA"),
    ("Quatsch", None), ("", None), (None, None),
])
def test_kanon_grader(roh, kanon):
    assert slab.kanon_grader(roh) == kanon


@pytest.mark.parametrize("grader,grade,erwartet", [
    ("Beckett", "9.0", ("BGS", "9")),
    ("BGS", "9", ("BGS", "9")),
    ("BGS", "9.4", ("BGS", "9.4")),
    ("psa", "10", ("PSA", "10")),
    ("CGC", "9,5", ("CGC", "9.5")),     # deutsches Komma
    ("PSA", "Müll", ("PSA", None)),
])
def test_normalize_grade(grader, grade, erwartet):
    assert slab.normalize_grade(grader, grade) == erwartet


# ────────────────────── DIE Prüfvorgabe aus dem Konzept ──────────────────────

def test_beckett_und_bgs_derselbe_eimer():
    """grade_bucket({Beckett, 9.0}) == grade_bucket({BGS, 9}) — sonst zahlt
    derselbe Slab zwei Preise."""
    a = grade_bucket({"grader": "Beckett", "grade": "9.0"})
    b = grade_bucket({"grader": "BGS", "grade": "9"})
    assert a == b == "BGS 9"


def test_bucket_erhaelt_nachkommastellen():
    assert grade_bucket({"grader": "Beckett", "grade": "9.4"}) == "BGS 9.4"
    assert grade_bucket({"grader": "WATA", "grade": "9.8"}) == "WATA 9.8"


def test_bucket_unbekannter_grader_verliert_keinen_preis():
    """Unbekannte Grader teilen nur mit sich selbst — aber sie bekommen
    weiterhin einen Eimer, keinen Absturz und kein raw."""
    assert grade_bucket({"grader": "GradeX", "grade": "9"}) == "GRADEX 9"


def test_bucket_raw():
    assert grade_bucket(None) == "raw"
    assert grade_bucket({"grader": "PSA"}) == "raw"


# ────────────────────── Skalen-Plausibilität ──────────────────────

@pytest.mark.parametrize("grader,grade,ok", [
    ("PSA", "9", True), ("PSA", "9.5", True), ("PSA", "9.4", False),
    ("WATA", "9.4", True), ("WATA", "9.8", True),
    ("BGS", "9.5", True), ("BGS", "11", False),
    ("VGA", "85", True), ("VGA", "9.5", False),
    ("Quatsch", "9", False),
])
def test_scale_ok(grader, grade, ok):
    assert slab.scale_ok(grader, grade) is ok


def test_grade_rank_vga_auf_zehner_skala():
    assert slab.grade_rank("VGA", "85") == 8.5
    assert slab.grade_rank("PSA", "8.5") == 8.5


# ────────────────────── Titel-Korrektur (entschärfte Regex) ──────────────────────

def test_band_wird_nicht_angefasst():
    """DIE Prüfvorgabe: „One Piece Band 9 Beckett 9.0" — das Wort „Band"
    steht vor einer Zahl, ist aber kein Grader-Kürzel. Die alte Regex hätte
    es zu „BGS" gemacht und den Titel zerstört."""
    from bot.claude_client import _grader_im_titel_richtigstellen
    d = {"title": "One Piece Band 9 Manga Japanisch 1st Print",
         "graded_info": {"grader": "beckett"}}
    _grader_im_titel_richtigstellen(d)
    assert d["title"] == "One Piece Band 9 Manga Japanisch 1st Print"


def test_band_frueh_verbraucht_den_treffer_nicht():
    """„Band 9" früh im Titel darf die echte Verschreibung „BGC 8.5" weiter
    hinten nicht schützen."""
    from bot.claude_client import _grader_im_titel_richtigstellen
    d = {"title": "One Piece Band 9 Japanisch BGC 8.5",
         "graded_info": {"grader": "beckett"}}
    _grader_im_titel_richtigstellen(d)
    assert d["title"] == "One Piece Band 9 Japanisch BGS 8.5"


def test_verschreibung_wird_weiter_korrigiert():
    """Der Ur-Fall bleibt gelöst: „BGC 8.5" → „BGS 8.5"."""
    from bot.claude_client import _grader_im_titel_richtigstellen
    d = {"title": "One Piece #1 Manga Shueisha 1997 Japanisch BGC 8.5",
         "graded_info": {"grader": "Beckett"}}
    _grader_im_titel_richtigstellen(d)
    assert "BGS 8.5" in d["title"] and "BGC" not in d["title"]


def test_korrekter_titel_bleibt():
    from bot.claude_client import _grader_im_titel_richtigstellen
    d = {"title": "Pokémon Glurak ex 199/165 CGC 10",
         "graded_info": {"grader": "CGC"}}
    _grader_im_titel_richtigstellen(d)
    assert d["title"] == "Pokémon Glurak ex 199/165 CGC 10"
