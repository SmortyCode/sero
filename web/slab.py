"""Grader-Kanon — die EINE Wahrheit über Bewertungsdienste und Noten.

Bis Stufe 3 (03.08.2026) hielt jede Ecke des Codes ihre eigene Grader-Liste:
claude_client korrigierte Titel, catalog baute Preis-Eimer, sold verglich
Belege. Folge: „BECKETT 9.0" und „BGS 9" waren ZWEI Katalogzeilen — dieselbe
Firma, derselbe Slab, zwei Preise. Dieses Modul ist die gemeinsame Quelle;
wer Grader anfasst, importiert von hier.
"""

from __future__ import annotations

# Aliasse und gängige Verschreibungen → Kanon-Kürzel. „beckett" ist der
# Firmenname (Kürzel BGS), „bgc" war die Verschreibung auf Svens Band 1.
GRADER_KANON = {
    "psa": "PSA",
    "bgs": "BGS", "beckett": "BGS", "becket": "BGS", "bgc": "BGS",
    "cgc": "CGC",
    "sgc": "SGC",
    "wata": "WATA",
    "vga": "VGA",
    "cga": "CGA",
    "ace": "ACE",
    "cbcs": "CBCS",
    "tag": "TAG",
    "mana": "MANA",
}

# Notenskalen: (min, max, feinste Schrittweite). WATA vergibt Zehntel
# (9.4/9.6/9.8), BGS und CGC halbe Noten, PSA ganze (plus 1.5).
SKALEN = {
    "PSA": (1.0, 10.0, 0.5),
    "BGS": (1.0, 10.0, 0.5),
    "CGC": (0.5, 10.0, 0.1),
    "SGC": (1.0, 10.0, 0.5),
    "WATA": (0.5, 10.0, 0.1),
    "VGA": (10.0, 100.0, 5.0),      # VGA nutzt die 100er-Skala
    "CGA": (0.5, 10.0, 0.5),
    "ACE": (1.0, 10.0, 0.5),
    "CBCS": (0.5, 10.0, 0.1),
    "TAG": (1.0, 10.0, 0.5),
    "MANA": (1.0, 10.0, 0.5),
}


def kanon_grader(grader) -> str | None:
    """Beliebige Schreibweise → Kanon-Kürzel, None wenn unbekannt."""
    g = str(grader or "").strip().lower()
    if not g:
        return None
    if g in GRADER_KANON:
        return GRADER_KANON[g]
    gross = g.upper()
    return gross if gross in GRADER_KANON.values() else None


def _note(grade) -> float | None:
    try:
        return float(str(grade).replace(",", "."))
    except (TypeError, ValueError):
        return None


def normalize_grade(grader, grade) -> tuple[str | None, str | None]:
    """(„Beckett", „9.0") → („BGS", „9") — Kanon-Kürzel plus Note in
    kanonischer Schreibweise: ganzzahlig ohne Nachkommastelle, sonst so
    viele Stellen wie nötig (9.4 bleibt 9.4)."""
    k = kanon_grader(grader)
    n = _note(grade)
    if n is None:
        return k, None
    if n == int(n):
        return k, str(int(n))
    return k, f"{n:g}"


def scale_ok(grader, grade) -> bool:
    """Liegt die Note auf der Skala ihres Graders? Eine „PSA 9.4" gibt es
    nicht — solche Kombinationen sind Lesefehler der Analyse."""
    k = kanon_grader(grader)
    n = _note(grade)
    if not k or n is None:
        return False
    lo, hi, schritt = SKALEN.get(k, (0.5, 10.0, 0.1))
    if not (lo <= n <= hi):
        return False
    # auf Schrittweite prüfen, mit Fließkomma-Toleranz
    rest = (n - lo) / schritt
    return abs(rest - round(rest)) < 1e-6


def grade_rank(grader, grade) -> float:
    """Sortierschlüssel über Grader hinweg — VGA-100er wird auf 10er-Skala
    abgebildet, damit „VGA 85" neben „PSA 8.5" einsortiert."""
    k = kanon_grader(grader)
    n = _note(grade)
    if n is None:
        return 0.0
    if k == "VGA" and n > 10:
        return n / 10.0
    return n


def bucket(graded: dict | None) -> str:
    """Katalog-Eimer eines Stücks: „raw" oder „<KANON> <Note>“.

    Die Zusage, an der Svens Katalog hing: bucket({Beckett, 9.0}) und
    bucket({BGS, 9}) ergeben DENSELBEN String — eine Firma, eine Zeile.
    Unbekannte Grader behalten ihre Schreibweise (upper), damit kein
    Preis verloren geht; sie teilen dann eben nur mit sich selbst.
    """
    if not graded or not graded.get("grade"):
        return "raw"
    k, n = normalize_grade(graded.get("grader"), graded.get("grade"))
    if n is None:
        return "raw"
    if k is None:
        k = str(graded.get("grader") or "").strip().upper()
    return f"{k} {n}".strip()
