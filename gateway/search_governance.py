"""Search governance decision receipts.

Purpose: classify search need, freshness requirements, budget admission, and
retrieval authority before search-backed synthesis or execution.
Governance scope: search freshness, search budget, retrieval safety, and
non-authoritative retrieved content handling.
Dependencies: dataclasses, re, datetime, and command-spine hashing.
Invariants:
  - Retrieved content is evidence only and never instruction authority.
  - Deep search requires an explicit positive budget window.
  - Current-information search records source freshness requirements.
  - Query text is represented by hash in receipts.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from gateway.command_spine import canonical_hash


SEARCH_DECISION_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:search-decision-receipt:1"
SEARCH_CAPABILITY_ID = "enterprise.knowledge_search"
_CURRENT_INFO_RE = re.compile(
    r"\b(latest|current|today|yesterday|tomorrow|news|price|weather|schedule|version|release|ceo|president)\b",
    re.IGNORECASE,
)
_SEARCH_RE = re.compile(r"\b(search|find|lookup|look up|docs|policy|document|knowledge)\b", re.IGNORECASE)
_DEEP_RE = re.compile(r"\b(deep|research|comprehensive|literature|survey|compare sources)\b", re.IGNORECASE)
_GREETING_RE = re.compile(r"^(hi|hello|hey|thanks|thank you)[.! ]*$", re.IGNORECASE)
_CLASSIFICATION_COST = {
    "no_search": 0.0,
    "cache": 0.0,
    "local_search": 0.1,
    "light_web_search": 1.0,
    "deep_search": 5.0,
}


@dataclass(frozen=True, slots=True)
class SearchCacheEvidence:
    """Tenant-scoped cache evidence required before cache reuse."""

    tenant_id: str
    query_hash: str
    cache_key_ref: str
    observed_at: str
    fresh_until: str
    stale_cache_used: bool = False
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, str) or not self.tenant_id.strip():
            raise ValueError("cache_tenant_id_required")
        if not isinstance(self.query_hash, str) or not self.query_hash.strip():
            raise ValueError("cache_query_hash_required")
        if not isinstance(self.cache_key_ref, str) or not self.cache_key_ref.startswith("cache://"):
            raise ValueError("cache_key_ref_required")
        if not isinstance(self.observed_at, str) or not self.observed_at.strip():
            raise ValueError("cache_observed_at_required")
        if not isinstance(self.fresh_until, str) or not self.fresh_until.strip():
            raise ValueError("cache_fresh_until_required")
        if self.stale_cache_used is not False:
            raise ValueError("stale_cache_reuse_forbidden")
        object.__setattr__(self, "evidence_refs", tuple(_normalized_text_list(self.evidence_refs, "cache_evidence_refs")))

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-compatible cache evidence metadata."""
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        return payload


@dataclass(frozen=True, slots=True)
class SearchDecisionRequest:
    """Input to the deterministic search governance classifier."""

    tenant_id: str
    actor_id: str
    query: str
    generated_at: str
    budget_limit_units: float = 0.0
    max_result_count: int = 5
    cache_fresh: bool = False
    cache_evidence: SearchCacheEvidence | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, str) or not self.tenant_id.strip():
            raise ValueError("search_tenant_id_required")
        if not isinstance(self.actor_id, str) or not self.actor_id.strip():
            raise ValueError("search_actor_id_required")
        if not isinstance(self.query, str):
            raise ValueError("search_query_string_required")
        if not isinstance(self.generated_at, str):
            raise ValueError("search_generated_at_string_required")
        if self.budget_limit_units < 0:
            raise ValueError("search_budget_limit_nonnegative_required")
        if self.max_result_count < 0:
            raise ValueError("search_max_result_count_nonnegative_required")
        if self.cache_evidence is not None and not isinstance(self.cache_evidence, SearchCacheEvidence):
            raise ValueError("search_cache_evidence_invalid")


@dataclass(frozen=True, slots=True)
class SearchDecisionReceipt:
    """Schema-backed receipt for search classification and admission."""

    schema_ref: str
    receipt_id: str
    tenant_id: str
    actor_id: str
    capability_id: str
    query_hash: str
    search_classification: str
    freshness_state: str
    budget_state: str
    retrieval_authority: str
    retrieval_instruction_authority_allowed: bool
    decision: str
    blocked_reasons: tuple[str, ...]
    estimated_cost_units: float
    budget_limit_units: float
    max_result_count: int
    generated_at: str
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_ref != SEARCH_DECISION_RECEIPT_SCHEMA_REF:
            raise ValueError("search_decision_schema_ref_invalid")
        if self.capability_id != SEARCH_CAPABILITY_ID:
            raise ValueError("search_decision_capability_invalid")
        if self.retrieval_authority != "evidence_only":
            raise ValueError("search_retrieval_authority_must_be_evidence_only")
        if self.retrieval_instruction_authority_allowed is not False:
            raise ValueError("search_retrieval_instruction_authority_forbidden")
        if self.estimated_cost_units < 0 or self.budget_limit_units < 0:
            raise ValueError("search_cost_units_nonnegative_required")
        if self.max_result_count < 0:
            raise ValueError("search_max_result_count_nonnegative_required")
        object.__setattr__(self, "blocked_reasons", tuple(self.blocked_reasons))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible search decision receipt."""
        payload = asdict(self)
        payload["blocked_reasons"] = list(self.blocked_reasons)
        return payload


def build_search_decision_receipt(request: SearchDecisionRequest) -> SearchDecisionReceipt:
    """Build a deterministic search decision receipt."""
    initial_classification = classify_search_need(request.query)
    query_hash = canonical_hash({"query": request.query})
    cache_admission = (
        _cache_admission(request, query_hash=query_hash)
        if initial_classification != "no_search"
        else _cache_not_requested_admission()
    )
    classification = "cache" if _cache_path_requested(request, initial_classification) else initial_classification
    estimated_cost = _CLASSIFICATION_COST[classification]
    freshness_state = _freshness_state(classification, cache_admission_state=cache_admission["state"])
    budget_state, budget_blockers = _budget_state(
        classification=classification,
        estimated_cost_units=estimated_cost,
        budget_limit_units=request.budget_limit_units,
    )
    blocked_reasons = tuple(dict.fromkeys((*budget_blockers, *_cache_blockers(classification, cache_admission))))
    decision = _decision(
        classification=classification,
        freshness_state=freshness_state,
        budget_state=budget_state,
        blocked_reasons=blocked_reasons,
    )
    receipt = SearchDecisionReceipt(
        schema_ref=SEARCH_DECISION_RECEIPT_SCHEMA_REF,
        receipt_id="pending",
        tenant_id=request.tenant_id.strip(),
        actor_id=request.actor_id.strip(),
        capability_id=SEARCH_CAPABILITY_ID,
        query_hash=query_hash,
        search_classification=classification,
        freshness_state=freshness_state,
        budget_state=budget_state,
        retrieval_authority="evidence_only",
        retrieval_instruction_authority_allowed=False,
        decision=decision,
        blocked_reasons=blocked_reasons,
        estimated_cost_units=estimated_cost,
        budget_limit_units=float(request.budget_limit_units),
        max_result_count=int(request.max_result_count),
        generated_at=request.generated_at or _utc_timestamp(),
        metadata={
            "raw_query_exposed": False,
            "search_budget_checked": True,
            "search_freshness_checked": True,
            "cache_admission": cache_admission,
        },
    )
    receipt_hash = canonical_hash(asdict(receipt))
    return replace(
        receipt,
        receipt_id=f"search-decision-receipt-{receipt_hash[:16]}",
        receipt_hash=receipt_hash,
    )


def classify_search_need(text: str) -> str:
    """Classify a user text into bounded search need states."""
    query = text.strip()
    if not query or _GREETING_RE.search(query):
        return "no_search"
    if _DEEP_RE.search(query):
        return "deep_search"
    if _CURRENT_INFO_RE.search(query):
        return "light_web_search"
    if _SEARCH_RE.search(query):
        return "local_search"
    return "cache" if query.endswith("?") else "no_search"


def _freshness_state(classification: str, *, cache_admission_state: str) -> str:
    if classification == "no_search":
        return "not_required"
    if classification == "cache" and cache_admission_state == "allowed":
        return "cache_fresh"
    if classification == "cache":
        return "refresh_required"
    if classification in {"light_web_search", "deep_search"}:
        return "source_required"
    return "not_required"


def _budget_state(
    *,
    classification: str,
    estimated_cost_units: float,
    budget_limit_units: float,
) -> tuple[str, tuple[str, ...]]:
    if classification in {"no_search", "cache"}:
        return "not_required", ()
    if classification == "deep_search" and budget_limit_units <= 0:
        return "blocked", ("deep_search_budget_required",)
    if budget_limit_units > 0 and estimated_cost_units > budget_limit_units:
        return "blocked", ("search_budget_limit_exceeded",)
    return "allowed", ()


def _decision(
    *,
    classification: str,
    freshness_state: str,
    budget_state: str,
    blocked_reasons: tuple[str, ...],
) -> str:
    if classification == "no_search":
        return "no_search"
    if blocked_reasons or budget_state == "blocked":
        return "block_search"
    if freshness_state == "cache_fresh":
        return "use_cache"
    return "allow_search"


def _cache_path_requested(request: SearchDecisionRequest, initial_classification: str) -> bool:
    return initial_classification == "cache" or (
        (request.cache_fresh or request.cache_evidence is not None) and initial_classification != "no_search"
    )


def _cache_admission(request: SearchDecisionRequest, *, query_hash: str) -> dict[str, Any]:
    if not request.cache_fresh and request.cache_evidence is None:
        return _cache_not_requested_admission()
    if request.cache_evidence is None:
        return _blocked_cache_admission("cache_evidence_required")

    evidence = request.cache_evidence
    blocked_reasons = []
    if evidence.tenant_id.strip() != request.tenant_id.strip():
        blocked_reasons.append("cache_tenant_mismatch")
    if evidence.query_hash.strip() != query_hash:
        blocked_reasons.append("cache_query_hash_mismatch")
    if evidence.stale_cache_used is not False:
        blocked_reasons.append("stale_cache_reuse_forbidden")
    if not evidence.evidence_refs:
        blocked_reasons.append("cache_evidence_refs_required")

    return {
        "state": "blocked" if blocked_reasons else "allowed",
        "cache_key_ref": evidence.cache_key_ref,
        "tenant_scoped": evidence.tenant_id.strip() == request.tenant_id.strip(),
        "query_hash_matches": evidence.query_hash.strip() == query_hash,
        "freshness_proved": not blocked_reasons,
        "stale_cache_used": evidence.stale_cache_used,
        "blocked_reasons": blocked_reasons,
        "evidence_refs": list(evidence.evidence_refs),
        "observed_at": evidence.observed_at,
        "fresh_until": evidence.fresh_until,
    }


def _blocked_cache_admission(reason: str) -> dict[str, Any]:
    return {
        "state": "blocked",
        "cache_key_ref": None,
        "tenant_scoped": False,
        "query_hash_matches": False,
        "freshness_proved": False,
        "stale_cache_used": False,
        "blocked_reasons": [reason],
        "evidence_refs": [],
    }


def _cache_not_requested_admission() -> dict[str, Any]:
    return {
        "state": "not_requested",
        "cache_key_ref": None,
        "tenant_scoped": True,
        "query_hash_matches": False,
        "freshness_proved": False,
        "stale_cache_used": False,
        "blocked_reasons": [],
        "evidence_refs": [],
    }


def _cache_blockers(classification: str, cache_admission: dict[str, Any]) -> tuple[str, ...]:
    blockers = tuple(cache_admission["blocked_reasons"])
    if classification == "cache" and cache_admission["state"] != "allowed" and not blockers:
        return ("cache_evidence_required",)
    return blockers


def _normalized_text_list(values: tuple[str, ...], field_name: str) -> list[str]:
    normalized = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name}_{index}_required")
        normalized.append(value.strip())
    return normalized


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
