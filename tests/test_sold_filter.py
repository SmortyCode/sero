"""Der Verkaufs-Beleg-Filter — bis 02.08.2026 unerreichbar in einer Closure.

Drei Fehler steckten jahrelang darin, jeder kostete echte Belege oder brachte
falsche: die Leerzeichen-Blindheit bei Kartennummern, der Kartenname „Ace" als
falscher Grader-Schalter, und „PSA10" ohne Leerzeichen.
"""

import pytest

from web.sold import fits


@pytest.mark.parametrize("query,title,erwartet", [
    # 1. Kartennummer mit Leerzeichen im Titel — muss trotzdem matchen
    ("Iono 199/165 SAR", "Pokemon Iono 199 / 165 SAR Near Mint", True),
    ("Iono 199/165 SAR", "Pokemon Iono 200/165 SAR", False),
    # 2. „Ace" ist hier ein KARTENNAME, kein Grader — ungegradet sucht ungegradet
    ("One Piece Ace OP13-007", "One Piece Ace OP13-007 SR englisch NM", True),
    ("One Piece Ace OP13-007", "One Piece Ace OP13-007 PSA 10 Gem Mint", False),
    # 3. „PSA10" ohne Leerzeichen zählt als PSA-10-Beleg
    ("Glurak PSA 10 4/102", "Glurak 4/102 PSA10 Base Set", True),
    # Grader-Trennung bleibt strikt: PSA-Anfrage nimmt keinen CGC-Beleg
    ("Glurak PSA 10 4/102", "Glurak 4/102 CGC 10 Base Set", False),
    # Ungegradete Anfrage nimmt keinen Slab
    ("Glurak 4/102 Holo", "Glurak 4/102 Holo PSA 9", False),
    ("Glurak 4/102 Holo", "Glurak 4/102 Holo Near Mint", True),
])
def test_fits(query, title, erwartet):
    assert fits(query, title) is erwartet


def test_grader_nur_mit_note():
    """„ace" allein (Kartenname) darf die Grader-Logik nicht scharf schalten,
    „ace 10" (Grading-Firma mit Note) sehr wohl."""
    assert fits("Ace Sabo Luffy OP13-007", "Ace Sabo Luffy OP13-007 NM") is True
    assert fits("Glurak ace 10", "Glurak ACE 10 graded") is True
    assert fits("Glurak ace 10", "Glurak PSA 10") is False


# ── Svens One-Piece-Manga (03.08.): 500 € Schätzung statt 2.745 € Belege ────

def test_beckett_und_bgs_sind_dieselbe_firma():
    """Beckett-Slabs stehen auf eBay fast immer als „BGS" im Titel. Wer nach
    „Beckett 8.5" sucht, muss sie finden — sonst bleibt ein 3.000-€-Manga ohne
    einen einzigen Beleg und fällt auf die KI-Schätzung zurück."""
    q = "One Piece Volume 1 1997 first printing Japanese graded Beckett 8.5"
    assert fits(q, "BGS 8.5 One Piece #1 - 1st Print Graded Manga Japanese")
    assert fits(q, "One Piece Vol 1 BGS 8.5 Japanese 1st Print")
    # Falscher Grader oder falsche Note bleiben draußen
    assert not fits(q, "One Piece Vol 1 PSA 9 Japanese")
    assert not fits(q, "One Piece Vol 1 CGC 8.5 Japanese")
    assert not fits(q, "One Piece Vol 1 BGS 9 Japanese")


def test_bandnummer_entscheidet():
    """Einstellige Zahlen sind Pflicht: ein Beleg von Band 2 taugt nicht für
    Band 1, auch wenn sonst alles passt."""
    q = "One Piece Volume 1 Japanese Beckett 8.5"
    assert fits(q, "One Piece Vol 1 BGS 8.5 Japanese")
    assert not fits(q, "One Piece Vol 2 BGS 8.5 Japanese")


def test_erscheinungsjahr_ist_kein_pflichtwort():
    """Das Jahr steht selten im Verkaufstitel — es darf keine Belege kosten."""
    q = "One Piece Volume 1 1997 Japanese Beckett 8.5"
    assert fits(q, "One Piece Vol 1 BGS 8.5 Japanese 1st Print")


@pytest.mark.parametrize("titel,grader,note", [
    ("wata 9.8 sealed", "wata", "9.8"),
    ("wata 9.6 a++", "wata", "9.6"),
    ("psa 10 mint", "psa", "10"),
    ("bgs 8.5", "bgs", "8.5"),
    ("beckett 9.0", "beckett", "9.0"),
])
def test_noten_mit_beliebiger_nachkommastelle(titel, grader, note):
    """Die alte Regex kannte nur X.5 — „WATA 9.8" wurde als „9" gelesen und
    damit gegen den falschen Grad verglichen."""
    from web.sold import _GRADER_NUM, _canon
    m = _GRADER_NUM.search(_canon(titel))
    assert m and m.group(1) == grader and m.group(2) == note


def test_kurzform_dampft_auf_den_kern_ein():
    """Zu ausführliche Anfragen finden bei der Verkaufsquelle nichts."""
    from web.sold import kurzform
    k = kurzform("One Piece Volume 1 1997 first printing Japanese graded Beckett 8.5")
    assert "bgs" in k and "8.5" in k and "1" in k
    assert "printing" not in k and "graded" not in k and "1997" not in k


def test_grader_kuerzel_im_titel_wird_korrigiert():
    """Die Analyse schrieb „BGC 8.5" — dieses Kürzel gibt es nicht, Käufer
    suchen nach BGS."""
    from bot.claude_client import _grader_im_titel_richtigstellen
    d = {"title": "One Piece #1 Manga Shueisha 1997 Japanisch BGC 8.5",
         "graded_info": {"grader": "Beckett"}}
    _grader_im_titel_richtigstellen(d)
    assert "BGS 8.5" in d["title"] and "BGC" not in d["title"]
    # Korrekte Titel bleiben unangetastet
    d2 = {"title": "Pokémon Glurak ex 199/165 CGC 10", "graded_info": {"grader": "CGC"}}
    _grader_im_titel_richtigstellen(d2)
    assert d2["title"] == "Pokémon Glurak ex 199/165 CGC 10"
