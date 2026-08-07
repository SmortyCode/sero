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

    Label-Varianten (CGC Pristine/Perfect) stecken NICHT im Eimer — PriceCharting
    kennt sie nicht getrennt. Verkaufssuche nutzt search_grade_tag().
    """
    if not graded or not graded.get("grade"):
        return "raw"
    k, n = normalize_grade(graded.get("grader"), graded.get("grade"))
    if n is None:
        return "raw"
    if k is None:
        k = str(graded.get("grader") or "").strip().upper()
    return f"{k} {n}".strip()


# CGC-Label-Programme (und bekannte Geschwister). Schlüssel = kanonisch.
LABEL_TYPES = {
    "pristine": "Pristine",
    "perfect": "Perfect",
    "gem_mint": "Gem Mint",
    "gem mint": "Gem Mint",
    "gemmint": "Gem Mint",
    "black_label": "Black Label",
    "black label": "Black Label",
    "blacklabel": "Black Label",
    "gold_label": "Pristine",   # Umgangssprache für CGC Pristine-Gold
    "gold label": "Pristine",
}


def normalize_label_type(label_type, grader=None, text: str | None = None) -> str | None:
    """Beliebige Schreibweise / Fließtext → kanonischer Schlüssel oder None.

    Erkannt: pristine, perfect, gem_mint, black_label. Zusätzlich aus Fließtext
    (Titel, Label-Aufdruck), falls das Modell das Wort nur dort hingeschrieben hat.
    """
    aliases = {
        "pristine": "pristine", "perfect": "perfect",
        "gem_mint": "gem_mint", "gem mint": "gem_mint", "gemmint": "gem_mint",
        "black_label": "black_label", "black label": "black_label",
        "blacklabel": "black_label",
        "gold_label": "pristine", "gold label": "pristine", "goldlabel": "pristine",
        "gold": "pristine",
    }
    raw = " ".join(str(label_type or "").strip().lower().replace("-", " ").split())
    if raw in aliases:
        return aliases[raw]
    blob = f"{raw} {text or ''}".lower()
    if "pristine" in blob or "gold label" in blob:
        return "pristine"
    if "perfect" in blob:
        return "perfect"
    if "black label" in blob or "blacklabel" in blob:
        return "black_label"
    if "gem mint" in blob or "gemmint" in blob:
        return "gem_mint"
    return None


def label_display(label_type: str | None) -> str | None:
    """pristine → „Pristine" für Siegel und Titel."""
    if not label_type:
        return None
    return LABEL_TYPES.get(label_type) or LABEL_TYPES.get(
        str(label_type).lower().replace("_", " ")) or str(label_type).title()


def grade_display(graded: dict | None) -> str:
    """Anzeigetext: „CGC Pristine 10" bzw. „CGC 10"."""
    if not graded or not graded.get("grade"):
        return ""
    k, n = normalize_grade(graded.get("grader"), graded.get("grade"))
    if n is None:
        return ""
    if k is None:
        k = str(graded.get("grader") or "").strip().upper()
    lab = label_display(normalize_label_type(
        graded.get("label_type"), k,
        f"{graded.get('grader')} {graded.get('grade')}"))
    if lab and lab not in ("Gem Mint",):  # Gem Mint = Standard-CGC-10, nicht extra
        return f"{k} {lab} {n}".strip()
    return f"{k} {n}".strip()


def search_grade_tag(graded: dict | None) -> str:
    """Token für Verkaufssuche — Pristine/Perfect mitführen, sonst grader+note."""
    return grade_display(graded)


def normalize_graded(graded: dict | None) -> dict | None:
    """graded_info säubern: Kanon-Grader, Note, label_type, Cert."""
    if not graded or not graded.get("grade"):
        return graded
    k, n = normalize_grade(graded.get("grader"), graded.get("grade"))
    if n is None:
        return graded
    out = dict(graded)
    if k:
        out["grader"] = k
    out["grade"] = n
    lab = normalize_label_type(
        graded.get("label_type"), k,
        f"{graded.get('label_type') or ''} {graded.get('grader') or ''}")
    if lab:
        out["label_type"] = lab
    elif "label_type" in out:
        out.pop("label_type", None)
    cert = graded.get("cert_number")
    if cert is not None and str(cert).strip():
        out["cert_number"] = str(cert).strip()
    else:
        out["cert_number"] = None
    return out
