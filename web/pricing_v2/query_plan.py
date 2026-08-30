"""Versionierter QueryPlan — deterministische Leiter."""
from __future__ import annotations

from typing import Any

from web.pricing_v2.types import QUERY_PLAN_VERSION


def build_query_plan(identity: dict[str, Any], graded: dict[str, Any] | None = None) -> dict[str, Any]:
    """Erzeugt immer dieselbe endliche Leiter aus der kanonischen Identität."""
    g = graded or {}
    name = (identity.get("name") or "").strip()
    number = (identity.get("number") or "").strip()
    set_name = (identity.get("set_name") or identity.get("set") or "").strip()
    parallel = (identity.get("edition") or identity.get("parallel") or "").strip()
    lang = (identity.get("language") or "").strip()
    grader = (g.get("grader") or identity.get("grader") or "").strip()
    grade = (g.get("grade") or identity.get("grade") or "").strip()
    cert = (g.get("cert_number") or identity.get("cert_number") or "").strip()
    game = (identity.get("game") or identity.get("domain") or "").strip()

    def q(*parts: str) -> str:
        return " ".join(p for p in parts if p).strip()

    steps = [
        {"id": "exact_cert", "query": q(name, number, set_name, parallel, grader, grade, cert, lang),
         "includes_cert": True},
        {"id": "exact_no_cert", "query": q(name, number, set_name, parallel, grader, grade, lang),
         "includes_cert": False},
        {"id": "alias_normalized", "query": q(name, number, set_name, parallel, grader, grade),
         "aliases": True},
        {"id": "card_parallel_grade", "query": q(name, number, parallel, grader, grade),
         "includes_cert": False},
        {"id": "adjacent_grade_estimate", "query": q(name, number, parallel, grader),
         "estimated": True, "note": "Nachbar-Grade nur als markierte Schätzung"},
        {"id": "raw_market", "query": q(name, number, set_name, parallel, lang),
         "raw_only": True},
        {"id": "asking_fallback", "query": q(name, number, set_name, parallel, grader, grade),
         "asking_only": True},
    ]
    # Leere Queries streichen
    steps = [s for s in steps if s.get("query")]
    return {
        "version": QUERY_PLAN_VERSION,
        "game": game,
        "steps": steps,
    }
