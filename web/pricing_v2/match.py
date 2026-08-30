"""Hard Matching vor Fuzzy-Ranking."""
from __future__ import annotations

import re
from typing import Any

from web.pricing_v2.keys import _norm


_FALSE_POSITIVE = re.compile(
    r"\b(lot|bundle|proxy|custom|digital|reprint|lose|box\s*set|booster\s*box)\b",
    re.I,
)


def hard_conflict(identity: dict[str, Any], candidate: dict[str, Any]) -> str | None:
    """Gibt Konfliktgrund zurück oder None wenn hart ok."""
    blob = _norm(
        f"{candidate.get('title') or ''} {candidate.get('name') or ''} "
        f"{candidate.get('product') or ''} {candidate.get('set') or ''} "
        f"{candidate.get('console') or ''}"
    )
    if _FALSE_POSITIVE.search(blob):
        # Nur verwerfen wenn Identity kein Bundle ist
        if not identity.get("allow_bundle"):
            return "false_positive_lot_proxy"

    id_game = _norm(identity.get("game") or identity.get("domain"))
    cand_game = _norm(candidate.get("game") or candidate.get("domain") or "")
    if id_game and cand_game and id_game != cand_game and cand_game not in ("other", "x", ""):
        return "domain_conflict"

    num = _norm(identity.get("number") or "")
    if num:
        # Nummer muss als Token vorkommen (OP03-055 oder 055)
        compact = num.replace("-", "")
        if num not in blob and compact not in blob.replace("-", ""):
            # erlaube 055 vs 55
            m = re.search(r"(\d+)$", num.replace("-", " "))
            if m:
                n = m.group(1).lstrip("0") or "0"
                if not re.search(rf"\b0*{re.escape(n)}\b", blob):
                    return "number_conflict"

    # Parallel vs Base
    want_par = bool(re.search(r"parallel|alternate|alt art", _norm(identity.get("edition") or ""), re.I))
    has_par = bool(re.search(r"parallel|alternate|alt art", blob, re.I))
    if want_par and not has_par:
        return "parallel_conflict"
    if (not want_par) and has_par and identity.get("strict_base"):
        return "base_vs_parallel"

    id_set = _norm(identity.get("set_name") or identity.get("set") or "")
    if id_set and len(id_set) >= 4:
        # Weiches Set: nur Konflikt wenn Kandidat klares anderes Set-Code hat
        cand_set = _norm(candidate.get("set") or candidate.get("console") or "")
        # OP09 vs OP03
        id_codes = set(re.findall(r"\bop\d{2}\b", id_set + " " + _norm(identity.get("number"))))
        cand_codes = set(re.findall(r"\bop\d{2}\b", cand_set + " " + blob))
        if id_codes and cand_codes and id_codes.isdisjoint(cand_codes):
            return "set_conflict"

    want_graded = bool(identity.get("grader") or identity.get("grade") or identity.get("form") == "graded")
    cand_graded = bool(candidate.get("grader") or candidate.get("grade") or
                       re.search(r"\b(psa|cgc|bgs|sgc|wata)\b", blob))
    if want_graded and candidate.get("evidence_raw_only"):
        return "raw_vs_graded"
    if want_graded and identity.get("grader"):
        g = _norm(identity.get("grader"))
        if g and g not in blob and _norm(candidate.get("grader") or "") not in ("", g):
            if candidate.get("grader") and _norm(candidate.get("grader")) != g:
                return "grader_conflict"

    return None


def filter_candidates(identity: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for c in candidates:
        if hard_conflict(identity, c) is None:
            out.append(c)
    return out
