"""Identity-Key v2 — ref_id nur Alias, nie alleinige globale Identität."""
from __future__ import annotations

import hashlib
import re
from typing import Any


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _parts_from_card(card: dict[str, Any]) -> dict[str, str]:
    """Extrahiert kanonische Felder aus card_info / canonical dict."""
    edition = _norm(card.get("edition") or card.get("parallel") or card.get("variation"))
    # Parallel explizit markieren
    if card.get("is_parallel") or "parallel" in edition or "alternate" in edition or "alt art" in edition:
        parallel = edition or "parallel"
    else:
        parallel = edition or "base"
    form = "graded" if (card.get("grader") or card.get("grade") or card.get("graded")) else "raw"
    return {
        "domain": _norm(card.get("domain") or card.get("game") or "x"),
        "set": _norm(card.get("set_name") or card.get("set") or card.get("set_total") or ""),
        "year": _norm(card.get("year") or ""),
        "number": _norm(card.get("number") or ""),
        "parallel": parallel,
        "language": _norm(card.get("language") or ""),
        "edition": edition,
        "form": form,
        "name": _norm(card.get("name") or ""),
    }


def identity_key_v2(card: dict[str, Any]) -> str:
    """Key aus Domain+Set/Jahr+Nummer+Parallel+Sprache/Edition+Form (+Name).

    Ohne Name und ohne Nummer: kein geteilter Key (solo bleibt außerhalb).
    """
    p = _parts_from_card(card)
    if not p["name"] and not p["number"]:
        return ""
    base = "|".join([
        p["domain"], p["set"], p["year"], p["number"],
        p["parallel"], p["language"], p["edition"], p["form"], p["name"],
    ])
    return "idv2:" + hashlib.sha1(base.encode()).hexdigest()[:20]


def price_key_v2(card: dict[str, Any], graded: dict[str, Any] | None = None) -> str:
    """Price-Key = Identity + Grader/Grade/Label für Slabs."""
    ik = identity_key_v2(card)
    if not ik:
        return ""
    g = graded or {}
    grader = _norm(g.get("grader") or card.get("grader") or "")
    grade = _norm(g.get("grade") or card.get("grade") or "raw")
    label = _norm(g.get("label_type") or card.get("label_type") or "")
    extra = f"|{grader}|{grade}|{label}"
    return ik + ":p:" + hashlib.sha1(extra.encode()).hexdigest()[:10]


def alias_ref(card: dict[str, Any]) -> str | None:
    """Externe ref_id nur als Alias speichern."""
    rid = card.get("ref_id")
    if not rid:
        return None
    game = _norm(card.get("game") or "x")
    return f"alias:{game}:{rid}"


def hard_number_tokens(query: str) -> list[str]:
    """Hard-Tokens inkl. einstelliger Kartennummer vor dem Slash (4/102 → 4)."""
    q = query or ""
    tokens: list[str] = []
    # Explizit Zähler/Nenner der Kartennummer
    for m in re.finditer(r"\b(\d{1,4})\s*/\s*(\d{2,4})\b", q):
        tokens.append(m.group(1))  # Zähler auch einstellig
        # Nenner (= Set-Größe) bewusst NICHT als Hard-Token
    # Set-Codes OP03-055, P-074
    for m in re.finditer(r"\b([A-Za-z]{1,6}-?\d{2,4})\b", q):
        tokens.append(_norm(m.group(1)))
    # Mehrstellige Zahlen-Tokens
    for t in re.findall(r"[A-Za-z0-9\-]+", q):
        tl = _norm(t)
        if any(c.isdigit() for c in tl) and len(tl) > 1 and tl not in tokens:
            if re.fullmatch(r"\d+", tl) and len(tl) == 1:
                continue
            tokens.append(tl)
    # Dedup stabile Reihenfolge
    seen = set()
    out = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out
