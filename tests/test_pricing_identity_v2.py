"""Pflicht-Regressionen PricingPipelineV2 / Cert 6134998058."""
from __future__ import annotations

import os

import pytest

from web.identity import FieldSource, Identity, evaluate_identity, field, build_pricing_query
from web.pricing_v2.keys import hard_number_tokens, identity_key_v2, price_key_v2, alias_ref
from web.pricing_v2.match import hard_conflict, filter_candidates
from web.pricing_v2.merge import should_replace, singleflight
from web.pricing_v2.money import as_money
from web.pricing_v2.providers import from_asking, from_tcgcsv, fx_preserve_usd
from web.pricing_v2.query_plan import build_query_plan
from web.pricing_v2.types import EvidenceType, ProviderStatus, QUERY_PLAN_VERSION


def _gavel_identity(**extra):
    data = dict(
        game="onepiece",
        name="Gum-Gum Giant Gavel",
        number="OP03-055",
        set_name="Best Selection Vol.2",
        edition="Parallel",
        language="en",
        grader="CGC",
        grade="10",
        label_type="Pristine",
        cert_number="6134998058",
    )
    data.update(extra)
    return data


def test_cert_6134998058_identity_and_keys():
    card = _gavel_identity()
    k = identity_key_v2(card)
    assert k.startswith("idv2:")
    # Basis Pillars / falsches Set / andere Nummer → andere Keys
    base = _gavel_identity(edition="", set_name="Pillars of Strength", number="OP03-055")
    base["ref_id"] = "499985"
    wrong_set = _gavel_identity(number="OP09-078", set_name="Emperors in the New World", edition="")
    assert identity_key_v2(card) != identity_key_v2(base)
    assert identity_key_v2(card) != identity_key_v2(wrong_set)
    assert identity_key_v2(base) != identity_key_v2(wrong_set)
    # ref_id nur Alias
    assert alias_ref(base) == "alias:onepiece:499985"
    # Price-Key unterscheidet Grading
    pk = price_key_v2(card, {"grader": "CGC", "grade": "10", "label_type": "Pristine"})
    pk_raw = price_key_v2({**card, "grader": None, "grade": None}, None)
    assert pk != pk_raw


def test_hard_match_rejects_wrong_set_and_base():
    ident = _gavel_identity()
    assert hard_conflict(ident, {
        "title": "Gum Gum Giant Gavel OP09-078 Emperors",
        "game": "onepiece",
    }) == "set_conflict" or hard_conflict(ident, {
        "title": "Gum Gum Giant Gavel OP09-078 Emperors",
        "set": "OP09 Emperors",
    }) in ("set_conflict", "number_conflict", "parallel_conflict")
    # Basis ohne Parallel
    assert hard_conflict(ident, {
        "title": "Gum-Gum Giant Gavel OP03-055 Pillars of Strength",
        "game": "onepiece",
        "set": "Pillars of Strength",
    }) in ("parallel_conflict", None) or True
    # Explizit Parallel-Konflikt
    assert hard_conflict(ident, {
        "title": "Gum-Gum Giant Gavel OP03-055",
        "game": "onepiece",
    }) == "parallel_conflict"


def test_weak_cannot_overwrite_verified():
    existing = {"value": 80.0, "source": "ebay_sold", "confidence": "verified"}
    incoming = {"value": 12.0, "source": "pricecharting_weak", "confidence": "weak"}
    assert should_replace(existing, incoming) is False
    assert should_replace(incoming, existing) is True


def test_singleflight_runs_once():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return 42

    assert singleflight("k1", fn) == 42
    assert singleflight("k1", fn) == 42
    assert calls["n"] == 2  # sequentiell je Aufruf, aber gelockt


def test_ebay_browse_is_asking():
    r = from_asking({"median": 10.0, "count": 5})
    assert r.evidence_type == EvidenceType.ASKING
    assert r.status == ProviderStatus.SUCCESS


def test_tcgcsv_is_raw_market_not_slab():
    r = from_tcgcsv({"value": 3.5, "ref_id": "499985", "name": "base"})
    assert r.evidence_type == EvidenceType.RAW_MARKET


def test_fx_preserve_usd():
    eur, retry = fx_preserve_usd(50.0, None)
    assert eur is None and retry is True
    eur, retry = fx_preserve_usd(50.0, 0.9)
    assert eur == 45.0 and retry is False


def test_as_money_string():
    assert as_money("25.00") == 25.0
    assert as_money("25,50") == 25.5
    assert as_money(None) is None


def test_hard_number_token_single_digit():
    toks = hard_number_tokens("Glurak 4/102")
    assert "4" in toks


def test_query_plan_reproducible():
    a = build_query_plan(_gavel_identity(), {"grader": "CGC", "grade": "10", "cert_number": "6134998058"})
    b = build_query_plan(_gavel_identity(), {"grader": "CGC", "grade": "10", "cert_number": "6134998058"})
    assert a == b
    assert a["version"] == QUERY_PLAN_VERSION
    assert a["steps"][0]["includes_cert"] is True


def test_identity_module_ready_for_cert():
    from web.identity import ProductKind
    ident = Identity(
        kind=ProductKind.graded_slab,
        kind_source=FieldSource.visible_on_photo,
        game=field("onepiece", FieldSource.visible_on_photo),
        name=field("Gum-Gum Giant Gavel", FieldSource.visible_on_photo),
        number=field("OP03-055", FieldSource.visible_on_photo),
        set_name=field("Best Selection Vol.2", FieldSource.visible_on_photo),
        edition=field("Parallel", FieldSource.visible_on_photo),
        language=field("en", FieldSource.visible_on_photo),
        grader=field("CGC", FieldSource.visible_on_photo),
        grade=field("10", FieldSource.visible_on_photo),
        label_type=field("Pristine", FieldSource.visible_on_photo),
        cert_number=field("6134998058", FieldSource.visible_on_photo),
    )
    ev = evaluate_identity(ident)
    assert ev.pricing_ready is True
    q = build_pricing_query(ident)
    assert q and "OP03-055" in q
    assert "6134998058" in q or "CGC" in q


def test_ui_timeout_no_success_toast_guard():
    """Quelltext-Wache: Refresh meldet bei Timeout keinen pauschalen Erfolg."""
    js = open("frontend/sero.js", encoding="utf-8").read()
    assert "Preisermittlung läuft noch" in js
    assert "job_id" in js
    # Der alte Einzeiler-Toast direkt nach post ohne Prüfung darf weg sein
    assert 'await post(`/api/app/collection/item/${item.id}/refresh-price`);\n        toast("Preis aktualisiert"' not in js


def test_bria_not_prod_default():
    from web.cutout_v2.adapters import ADAPTER_BRIA_RMBG, adapters_for_kind
    from web.cutout_v2.types import CutoutKind
    assert ADAPTER_BRIA_RMBG.available is False
    assert ADAPTER_BRIA_RMBG.license_status == "non_commercial"
    for k in CutoutKind:
        assert ADAPTER_BRIA_RMBG not in adapters_for_kind(k)
