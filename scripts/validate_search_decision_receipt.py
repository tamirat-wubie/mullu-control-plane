#!/usr/bin/env python3
"""Validate the search decision receipt contract.

Purpose: verify search classification, freshness, budget, and retrieval
authority receipts before search-backed synthesis or execution.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS, Foundation Mode, and
retrieval authority boundaries.
Dependencies: gateway/search_governance.py,
schemas/search_decision_receipt.schema.json,
examples/search_decision_receipt.foundation.json, and scripts/validate_schemas.py.
Invariants:
  - Search receipts expose a query hash, not raw query text.
  - Retrieved content has evidence-only authority.
  - Current-information searches require source freshness.
  - Deep search is blocked without explicit sufficient budget.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
for import_root in (WORKSPACE_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from gateway.command_spine import _CAPABILITY_PASSPORTS  # noqa: E402
from gateway.search_governance import (  # noqa: E402
    SEARCH_CAPABILITY_ID,
    SEARCH_DECISION_RECEIPT_SCHEMA_REF,
    SearchDecisionRequest,
    build_search_decision_receipt,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "search_decision_receipt.schema.json"
DEFAULT_EXAMPLE_PATH = WORKSPACE_ROOT / "examples" / "search_decision_receipt.foundation.json"
RAW_QUERY_FRAGMENT = "latest release version for dependency"


def load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object or raise a path-specific validation error."""
    if not path.exists():
        raise FileNotFoundError(f"missing search decision receipt artifact: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"search decision receipt artifact must be an object: {path}")
    return payload


def validate_search_decision_receipt(
    payload: dict[str, Any],
    *,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> list[str]:
    """Return deterministic validation errors for a search decision receipt."""
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, payload)

    if payload.get("schema_ref") != SEARCH_DECISION_RECEIPT_SCHEMA_REF:
        errors.append("schema_ref must remain search-decision-receipt v1")
    if payload.get("capability_id") != SEARCH_CAPABILITY_ID:
        errors.append("capability_id must remain enterprise.knowledge_search")
    if payload.get("retrieval_authority") != "evidence_only":
        errors.append("retrieval_authority must be evidence_only")
    if payload.get("retrieval_instruction_authority_allowed") is not False:
        errors.append("retrieval instruction authority must be false")
    if payload.get("metadata", {}).get("raw_query_exposed") is not False:
        errors.append("metadata.raw_query_exposed must be false")
    if RAW_QUERY_FRAGMENT in json.dumps(payload, sort_keys=True):
        errors.append("raw query text must not be serialized in the receipt")
    if payload.get("search_classification") in {"light_web_search", "deep_search"}:
        if payload.get("freshness_state") != "source_required":
            errors.append("current or deep search must require source freshness")
    if payload.get("decision") == "allow_search" and payload.get("budget_state") != "allowed":
        errors.append("allow_search requires allowed budget_state")

    return errors


def validate_generated_search_scenarios() -> list[str]:
    """Return errors for runtime-built search governance boundary scenarios."""
    errors: list[str] = []
    current_info = build_search_decision_receipt(
        SearchDecisionRequest(
            tenant_id="foundation-tenant",
            actor_id="operator",
            query=RAW_QUERY_FRAGMENT,
            budget_limit_units=2.0,
            generated_at="2026-06-16T14:00:00+00:00",
        )
    )
    deep_blocked = build_search_decision_receipt(
        SearchDecisionRequest(
            tenant_id="foundation-tenant",
            actor_id="operator",
            query="deep research and compare sources for market policy",
            budget_limit_units=1.0,
            generated_at="2026-06-16T14:00:00+00:00",
        )
    )

    if current_info.search_classification != "light_web_search":
        errors.append("current information query must classify as light_web_search")
    if current_info.freshness_state != "source_required":
        errors.append("current information query must require source freshness")
    if current_info.decision != "allow_search":
        errors.append("current information query with budget must be allowed")
    if RAW_QUERY_FRAGMENT in current_info.to_dict()["query_hash"]:
        errors.append("query_hash must not contain raw query text")

    if deep_blocked.search_classification != "deep_search":
        errors.append("deep research query must classify as deep_search")
    if deep_blocked.decision != "block_search":
        errors.append("under-budgeted deep search must be blocked")
    if "search_budget_limit_exceeded" not in deep_blocked.blocked_reasons:
        errors.append("under-budgeted deep search must record budget blocker")

    return errors


def validate_capability_passport_binding() -> list[str]:
    """Return errors if the command-spine passport drifts from search governance."""
    passport = _CAPABILITY_PASSPORTS.get(SEARCH_CAPABILITY_ID)
    if passport is None:
        return ["enterprise.knowledge_search passport missing"]

    errors: list[str] = []
    required_terms = {
        "budget_reserved",
        "search_budget_checked",
        "search_freshness_checked",
        "retrieval_evidence_only",
    }
    missing_terms = sorted(required_terms - set(passport.requires))
    if missing_terms:
        errors.append(f"knowledge search passport missing requires terms: {missing_terms}")
    if "search_decision_receipt" not in passport.evidence_required:
        errors.append("knowledge search passport must require search_decision_receipt evidence")
    if passport.cost_model.get("unit") != "search_cost_unit":
        errors.append("knowledge search passport cost unit must be search_cost_unit")
    if passport.mutates_world is not False:
        errors.append("knowledge search passport must remain non-mutating")
    return errors


def main() -> int:
    """Validate the foundation search decision receipt artifact and runtime builder."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--receipt",
        type=Path,
        default=DEFAULT_EXAMPLE_PATH,
        help="Path to a search decision receipt JSON artifact.",
    )
    args = parser.parse_args()

    try:
        payload = load_json_object(args.receipt)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] search_decision_receipt_load: {exc}")
        return 1

    checks = {
        "search_decision_receipt_schema": validate_search_decision_receipt(payload),
        "search_decision_runtime_scenarios": validate_generated_search_scenarios(),
        "search_decision_capability_binding": validate_capability_passport_binding(),
    }
    failed = False
    for check_name, errors in checks.items():
        if errors:
            failed = True
            for error in errors:
                print(f"[FAIL] {check_name}: {error}")
        else:
            print(f"[PASS] {check_name}")

    if failed:
        print("STATUS: failed")
        return 1
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
