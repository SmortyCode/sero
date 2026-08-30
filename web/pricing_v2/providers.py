"""Typed Provider-Hüllen — Fehler nie still zu None kollabieren."""
from __future__ import annotations

import time
from typing import Any

from web.pricing_v2.types import EvidenceType, ProviderResult, ProviderStatus


def disabled(provider: str, reason: str = "flag_off") -> ProviderResult:
    return ProviderResult(
        provider=provider,
        status=ProviderStatus.DISABLED,
        error_detail=reason,
        timestamp=time.time(),
    )


def wrap_exception(provider: str, exc: BaseException) -> ProviderResult:
    msg = str(exc)
    low = msg.lower()
    if "401" in msg or "auth" in low:
        st = ProviderStatus.AUTH_ERROR
    elif "429" in msg or "rate" in low:
        st = ProviderStatus.RATE_LIMITED
    elif "timeout" in low or "timed out" in low:
        st = ProviderStatus.TIMEOUT
    else:
        st = ProviderStatus.PARSER_ERROR
    return ProviderResult(
        provider=provider,
        status=st,
        error_detail=msg[:300],
        timestamp=time.time(),
    )


def from_pc_dict(pc: dict[str, Any] | None, *, weak: bool = False) -> ProviderResult:
    if not pc:
        return ProviderResult(
            provider="pricecharting",
            status=ProviderStatus.NO_MATCH,
            evidence_type=EvidenceType.GUIDE_VALUE,
            timestamp=time.time(),
        )
    return ProviderResult(
        provider="pricecharting",
        status=ProviderStatus.SUCCESS,
        evidence_type=EvidenceType.GUIDE_VALUE,
        value=pc.get("value"),
        currency="EUR",
        value_usd=pc.get("value_usd") or (pc.get("detail") or {}).get("value_us"),
        source_id=str((pc.get("detail") or {}).get("pc_id") or ""),
        match_identity={
            "product": (pc.get("detail") or {}).get("pc_product"),
            "console": (pc.get("detail") or {}).get("pc_console"),
        },
        confidence="weak" if weak else "verified",
        timestamp=time.time(),
    )


def from_sold(sold: dict[str, Any] | None) -> ProviderResult:
    if not sold or sold.get("median") is None:
        return ProviderResult(
            provider="ebay_sold",
            status=ProviderStatus.NO_MATCH,
            evidence_type=EvidenceType.SOLD_COMP,
            timestamp=time.time(),
        )
    return ProviderResult(
        provider="ebay_sold",
        status=ProviderStatus.SUCCESS,
        evidence_type=EvidenceType.SOLD_COMP,
        value=sold.get("median"),
        currency="EUR",
        confidence="verified",
        timestamp=time.time(),
        candidates=sold.get("samples") or [],
    )


def from_asking(res: dict[str, Any] | None) -> ProviderResult:
    """eBay Browse — immer ASKING, niemals Sold."""
    if not res or res.get("median") is None:
        return ProviderResult(
            provider="ebay_browse",
            status=ProviderStatus.NO_MATCH,
            evidence_type=EvidenceType.ASKING,
            timestamp=time.time(),
        )
    return ProviderResult(
        provider="ebay_browse",
        status=ProviderStatus.SUCCESS,
        evidence_type=EvidenceType.ASKING,
        value=res.get("median"),
        currency="EUR",
        confidence="weak",
        timestamp=time.time(),
    )


def from_tcgcsv(row: dict[str, Any] | None) -> ProviderResult:
    if not row or row.get("value") is None:
        return ProviderResult(
            provider="tcgcsv",
            status=ProviderStatus.NO_MATCH,
            evidence_type=EvidenceType.RAW_MARKET,
            timestamp=time.time(),
        )
    return ProviderResult(
        provider="tcgcsv",
        status=ProviderStatus.SUCCESS,
        evidence_type=EvidenceType.RAW_MARKET,
        value=row.get("value"),
        currency="EUR",
        confidence="verified",
        timestamp=time.time(),
        match_identity={"ref_id": row.get("ref_id"), "name": row.get("name")},
    )


def fx_preserve_usd(value_usd: float | None, rate: float | None) -> tuple[float | None, bool]:
    """Bei FX-Ausfall USD behalten und Convert-Retry signalisieren."""
    if value_usd is None:
        return None, False
    if not rate:
        return None, True  # needs_fx_retry
    return round(float(value_usd) * float(rate), 2), False
