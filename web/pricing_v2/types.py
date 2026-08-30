"""Getypte Preis-/Provider-Resultate."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


QUERY_PLAN_VERSION = "pricing-query-v2.0.0"


class ProviderStatus(str, Enum):
    SUCCESS = "SUCCESS"
    NO_MATCH = "NO_MATCH"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    AUTH_ERROR = "AUTH_ERROR"
    PARSER_ERROR = "PARSER_ERROR"
    DISABLED = "DISABLED"


class EvidenceType(str, Enum):
    SOLD_COMP = "SOLD_COMP"
    GUIDE_VALUE = "GUIDE_VALUE"
    RAW_MARKET = "RAW_MARKET"
    ASKING = "ASKING"


class PriceClass(str, Enum):
    EXACT_SOLD = "EXACT_SOLD"
    ESTIMATED_SOLD = "ESTIMATED_SOLD"
    GUIDE_VALUE = "GUIDE_VALUE"
    RAW_MARKET = "RAW_MARKET"
    ASKING_ONLY = "ASKING_ONLY"
    NO_MARKET_DATA = "NO_MARKET_DATA"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    IDENTIFYING = "IDENTIFYING"
    QUERYING = "QUERYING"
    VALIDATING = "VALIDATING"
    COMPLETE = "COMPLETE"
    NO_MARKET_DATA = "NO_MARKET_DATA"
    RETRYABLE_ERROR = "RETRYABLE_ERROR"
    PERMANENT_ERROR = "PERMANENT_ERROR"


@dataclass
class ProviderResult:
    provider: str
    status: ProviderStatus
    evidence_type: EvidenceType | None = None
    query_id: str | None = None
    attempt: int = 1
    match_identity: dict[str, Any] | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    value: float | None = None
    currency: str | None = None
    value_usd: float | None = None
    timestamp: float | None = None
    source_url: str | None = None
    source_id: str | None = None
    error_detail: str | None = None  # ohne Secrets
    confidence: str | None = None  # verified | weak

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status.value,
            "evidence_type": self.evidence_type.value if self.evidence_type else None,
            "query_id": self.query_id,
            "attempt": self.attempt,
            "match_identity": self.match_identity,
            "candidates": self.candidates,
            "value": self.value,
            "currency": self.currency,
            "value_usd": self.value_usd,
            "timestamp": self.timestamp,
            "source_url": self.source_url,
            "source_id": self.source_id,
            "error_detail": self.error_detail,
            "confidence": self.confidence,
        }
