"""Search governance tests.

Purpose: verify deterministic search classification, freshness, budget, and
retrieval authority receipts before search-backed execution.
Governance scope: search decision receipts, freshness state, budget admission,
and retrieved-content authority boundaries.
Dependencies: gateway.search_governance and schemas/search_decision_receipt.schema.json.
Invariants:
  - Search queries are hash-bound and raw query text is not emitted.
  - Current-information searches record source freshness requirements.
  - Deep search is blocked without sufficient budget.
  - Retrieved content is evidence only, never instruction authority.
"""

from __future__ import annotations

from pathlib import Path

from gateway.command_spine import canonical_hash
from gateway.search_governance import SearchCacheEvidence, SearchDecisionRequest, build_search_decision_receipt
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "search_decision_receipt.schema.json"


def test_search_decision_allows_local_docs_search() -> None:
    receipt = build_search_decision_receipt(
        SearchDecisionRequest(
            tenant_id="tenant-search",
            actor_id="operator",
            query="search knowledge docs for policy",
            budget_limit_units=1.0,
            generated_at="2026-06-16T14:00:00+00:00",
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), receipt.to_dict())

    assert errors == []
    assert receipt.search_classification == "local_search"
    assert receipt.freshness_state == "not_required"
    assert receipt.budget_state == "allowed"
    assert receipt.decision == "allow_search"
    assert receipt.retrieval_instruction_authority_allowed is False


def test_search_decision_records_current_info_freshness_requirement() -> None:
    receipt = build_search_decision_receipt(
        SearchDecisionRequest(
            tenant_id="tenant-search",
            actor_id="operator",
            query="latest release version for dependency",
            budget_limit_units=2.0,
            generated_at="2026-06-16T14:00:00+00:00",
        )
    )

    assert receipt.search_classification == "light_web_search"
    assert receipt.freshness_state == "source_required"
    assert receipt.budget_state == "allowed"
    assert receipt.decision == "allow_search"
    assert receipt.retrieval_authority == "evidence_only"


def test_search_decision_blocks_deep_search_without_budget() -> None:
    receipt = build_search_decision_receipt(
        SearchDecisionRequest(
            tenant_id="tenant-search",
            actor_id="operator",
            query="deep research and compare sources for market policy",
            budget_limit_units=1.0,
            generated_at="2026-06-16T14:00:00+00:00",
        )
    )

    assert receipt.search_classification == "deep_search"
    assert receipt.budget_state == "blocked"
    assert receipt.decision == "block_search"
    assert "search_budget_limit_exceeded" in receipt.blocked_reasons
    assert "market policy" not in receipt.to_dict()["query_hash"]


def test_search_decision_uses_fresh_cache_when_available() -> None:
    query = "what is the stable internal policy?"
    receipt = build_search_decision_receipt(
        SearchDecisionRequest(
            tenant_id="tenant-search",
            actor_id="operator",
            query=query,
            cache_fresh=True,
            cache_evidence=SearchCacheEvidence(
                tenant_id="tenant-search",
                query_hash=canonical_hash({"query": query}),
                cache_key_ref="cache://tenant-search/stable-internal-policy",
                observed_at="2026-06-16T13:55:00+00:00",
                fresh_until="2026-06-16T14:30:00+00:00",
                evidence_refs=("cache-evidence://tenant-search/stable-internal-policy",),
            ),
            generated_at="2026-06-16T14:00:00+00:00",
        )
    )

    assert receipt.search_classification == "cache"
    assert receipt.freshness_state == "cache_fresh"
    assert receipt.budget_state == "not_required"
    assert receipt.decision == "use_cache"
    assert receipt.metadata["raw_query_exposed"] is False
    assert receipt.metadata["cache_admission"]["state"] == "allowed"
    assert receipt.metadata["cache_admission"]["tenant_scoped"] is True
    assert receipt.metadata["cache_admission"]["query_hash_matches"] is True


def test_search_decision_blocks_cache_without_tenant_evidence() -> None:
    receipt = build_search_decision_receipt(
        SearchDecisionRequest(
            tenant_id="tenant-search",
            actor_id="operator",
            query="what is the stable internal policy?",
            cache_fresh=True,
            generated_at="2026-06-16T14:00:00+00:00",
        )
    )

    assert receipt.search_classification == "cache"
    assert receipt.freshness_state == "refresh_required"
    assert receipt.decision == "block_search"
    assert "cache_evidence_required" in receipt.blocked_reasons
    assert receipt.metadata["cache_admission"]["state"] == "blocked"
    assert receipt.metadata["cache_admission"]["tenant_scoped"] is False


def test_search_decision_classifies_greeting_as_no_search() -> None:
    receipt = build_search_decision_receipt(
        SearchDecisionRequest(
            tenant_id="tenant-search",
            actor_id="operator",
            query="hello",
            generated_at="2026-06-16T14:00:00+00:00",
        )
    )

    assert receipt.search_classification == "no_search"
    assert receipt.freshness_state == "not_required"
    assert receipt.budget_state == "not_required"
    assert receipt.decision == "no_search"
