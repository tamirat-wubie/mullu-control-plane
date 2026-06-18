"""Search decision receipt validator tests.

Purpose: prove the standalone search decision receipt validator catches schema,
budget, freshness, and authority drift.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: scripts.validate_search_decision_receipt.
Invariants:
  - Raw query text is not serialized in receipts.
  - Retrieval authority is evidence-only.
  - Deep search without sufficient budget is blocked.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts import validate_search_decision_receipt as validator


def _example_payload() -> dict:
    return validator.load_json_object(validator.DEFAULT_EXAMPLE_PATH)


def test_search_decision_receipt_example_passes() -> None:
    payload = _example_payload()
    errors = validator.validate_search_decision_receipt(payload)

    assert errors == []
    assert payload["decision"] == "allow_search"
    assert payload["freshness_state"] == "source_required"
    assert payload["metadata"]["raw_query_exposed"] is False


def test_search_decision_receipt_rejects_raw_query_exposure() -> None:
    payload = _example_payload()
    payload["metadata"] = copy.deepcopy(payload["metadata"])
    payload["metadata"]["raw_query_exposed"] = True
    payload["raw_query"] = validator.RAW_QUERY_FRAGMENT

    errors = validator.validate_search_decision_receipt(payload)

    assert "$: unexpected property 'raw_query'" in errors
    assert "metadata.raw_query_exposed must be false" in errors
    assert "raw query text must not be serialized in the receipt" in errors


def test_search_decision_receipt_rejects_instruction_authority() -> None:
    payload = _example_payload()
    payload["retrieval_authority"] = "instruction"
    payload["retrieval_instruction_authority_allowed"] = True

    errors = validator.validate_search_decision_receipt(payload)

    assert "$.retrieval_authority: expected const 'evidence_only'" in errors
    assert "$.retrieval_instruction_authority_allowed: expected const False" in errors
    assert "retrieval_authority must be evidence_only" in errors
    assert "retrieval instruction authority must be false" in errors


def test_search_decision_receipt_rejects_cache_without_admission() -> None:
    payload = _example_payload()
    payload["search_classification"] = "cache"
    payload["freshness_state"] = "cache_fresh"
    payload["budget_state"] = "not_required"
    payload["decision"] = "use_cache"
    payload["metadata"] = copy.deepcopy(payload["metadata"])
    payload["metadata"]["cache_admission"] = {
        "state": "blocked",
        "tenant_scoped": False,
        "query_hash_matches": False,
        "stale_cache_used": False,
    }

    errors = validator.validate_search_decision_receipt(payload)

    assert "use_cache requires allowed cache_admission" in errors
    assert "use_cache requires tenant-scoped cache evidence" not in errors
    assert payload["decision"] == "use_cache"


def test_search_decision_runtime_scenarios_cover_budget_and_freshness() -> None:
    errors = validator.validate_generated_search_scenarios()

    assert errors == []
    assert validator.SEARCH_CAPABILITY_ID == "enterprise.knowledge_search"
    assert validator.RAW_QUERY_FRAGMENT


def test_search_decision_capability_binding_requires_receipt() -> None:
    errors = validator.validate_capability_passport_binding()

    assert errors == []
    assert "search_decision_receipt" in validator._CAPABILITY_PASSPORTS[
        validator.SEARCH_CAPABILITY_ID
    ].evidence_required
    assert validator._CAPABILITY_PASSPORTS[
        validator.SEARCH_CAPABILITY_ID
    ].cost_model["unit"] == "search_cost_unit"


def test_search_decision_receipt_missing_file_error_is_bounded(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing-search-receipt.json"

    try:
        validator.load_json_object(missing_path)
    except FileNotFoundError as exc:
        message = str(exc)
    else:
        raise AssertionError("missing receipt should fail closed")

    assert "missing search decision receipt artifact" in message
    assert str(missing_path) in message
    assert json.dumps({"path": str(missing_path)})
