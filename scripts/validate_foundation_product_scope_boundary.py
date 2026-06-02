#!/usr/bin/env python3
"""Validate the Foundation Mode product-scope boundary.

Purpose: keep one selected local learning lane from becoming a pilot, customer,
market, launch, deployment, or legal-readiness claim.
Governance scope: Foundation Mode, product-scope posture, local learning lane,
platform non-restriction, pilot blocking, customer blocking, and launch blocking.
Dependencies: docs/FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md and
examples/foundation_product_scope_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The selected lane is local proof, not a platform restriction.
  - Pilot access, customer access, market validation, paid launch, deployment
    dependency, and legal readiness remain blocked.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_product_scope_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_product_scope_witness.awaiting_evidence.v1"
EXPECTED_SELECTED_LEARNING_LANE = "local_governed_task_receipt"
EXPECTED_LANES = (
    ("local_governed_task_receipt", "selected_local_proof", "AwaitingEvidence"),
    ("finance_approval_simulation", "future_candidate", "AwaitingEvidence"),
    ("document_packet_simulation", "future_candidate", "AwaitingEvidence"),
)
EXPECTED_BLOCKED_CLAIMS = (
    "pilot readiness",
    "customer access",
    "market validation",
    "deployment readiness",
    "paid launch",
    "legal readiness",
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "customer_access_allowed",
    "deployment_dependency_allowed",
    "learning_lanes",
    "long_term_platform_restricted",
    "market_validation_claimed",
    "next_action",
    "paid_launch_allowed",
    "pilot_access_allowed",
    "schema_version",
    "scope_mode",
    "selected_learning_lane",
    "solver_outcome",
    "status",
    "witness_id",
}
EXPECTED_LANE_KEYS = {
    "lane_id",
    "lane_type",
    "state",
    "tests",
    "what_it_does_not_claim",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Product Scope Boundary",
    "Witness packet: [`../examples/foundation_product_scope_witness.awaiting_evidence.json`]",
    "Rule: One narrow learning lane is a local proof lane, not a permanent platform restriction.",
    "No pilot access, customer access, market-validation, paid-launch, deployment-readiness,",
    "product_scope_boundary_state=AwaitingEvidence",
    "selected_learning_lane=local_governed_task_receipt",
    "long_term_platform_restricted=false",
    "pilot_access_allowed=false",
    "market_validation_claimed=false",
    "python scripts/validate_foundation_product_scope_boundary.py",
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("pilot_ready", re.compile(r"\bpilot[- ]ready\b", re.IGNORECASE)),
    ("customer_ready", re.compile(r"\bcustomer[- ]ready\b", re.IGNORECASE)),
    ("market_validated", re.compile(r"\bmarket\s+validated\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment[- ]ready\b", re.IGNORECASE)),
    ("production_ready", re.compile(r"\bproduction[- ]ready\b", re.IGNORECASE)),
    ("paid_launch_ready", re.compile(r"\bpaid\s+launch\s+ready\b", re.IGNORECASE)),
    ("open_access", re.compile(r"\bopen\s+access\b", re.IGNORECASE)),
    ("accepting_customers", re.compile(r"\baccepting\s+customers\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class ProductScopeFinding:
    """One deterministic product-scope boundary validation finding."""

    rule_id: str
    message: str


def load_text(path: Path, label: str) -> str:
    """Load one text artifact with explicit path errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit path and type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_doc_text(text: str) -> list[ProductScopeFinding]:
    """Return findings for missing product-scope documentation anchors."""

    findings: list[ProductScopeFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                ProductScopeFinding(
                    "foundation_product_scope_doc_phrase_missing",
                    f"product-scope boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[ProductScopeFinding]:
    """Return findings for product-scope witness drift."""

    findings: list[ProductScopeFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_learning_lanes(payload.get("learning_lanes")))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[ProductScopeFinding]:
    """Return findings for root-level product-scope witness drift."""

    findings: list[ProductScopeFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            ProductScopeFinding(
                "product_scope_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "scope_mode": "foundation_learning_lane",
        "selected_learning_lane": EXPECTED_SELECTED_LEARNING_LANE,
        "long_term_platform_restricted": False,
        "pilot_access_allowed": False,
        "customer_access_allowed": False,
        "market_validation_claimed": False,
        "paid_launch_allowed": False,
        "deployment_dependency_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                ProductScopeFinding(
                    "product_scope_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            ProductScopeFinding(
                "product_scope_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not convert it into pilot" not in next_action:
        findings.append(
            ProductScopeFinding(
                "product_scope_next_action_invalid",
                "next_action must preserve the local-only selected lane boundary",
            )
        )
    return findings


def validate_learning_lanes(learning_lanes: object) -> list[ProductScopeFinding]:
    """Return findings for learning-lane witness drift."""

    findings: list[ProductScopeFinding] = []
    if not isinstance(learning_lanes, list) or not all(isinstance(lane, dict) for lane in learning_lanes):
        return [ProductScopeFinding("product_scope_lanes_invalid", "learning_lanes must be a list of objects")]
    observed_lanes = tuple((lane.get("lane_id"), lane.get("lane_type"), lane.get("state")) for lane in learning_lanes)
    if observed_lanes != EXPECTED_LANES:
        findings.append(
            ProductScopeFinding(
                "product_scope_lane_inventory_invalid",
                "learning lane inventory does not match the Foundation Mode selected-lane set",
            )
        )
    lane_ids = [lane.get("lane_id") for lane in learning_lanes]
    if len(set(lane_ids)) != len(lane_ids):
        findings.append(ProductScopeFinding("product_scope_lane_duplicate", "lane ids must be unique"))
    for lane in learning_lanes:
        lane_id = str(lane.get("lane_id", "<missing>"))
        if set(lane) != EXPECTED_LANE_KEYS:
            findings.append(
                ProductScopeFinding(
                    "product_scope_lane_keys_invalid",
                    f"{lane_id} lane keys must be: {', '.join(sorted(EXPECTED_LANE_KEYS))}",
                )
            )
        if lane.get("state") != "AwaitingEvidence":
            findings.append(
                ProductScopeFinding(
                    "product_scope_lane_state_invalid",
                    f"{lane_id} state must be AwaitingEvidence",
                )
            )
        tests = lane.get("tests")
        if not isinstance(tests, list) or len(tests) < 3 or not all(isinstance(test, str) and test for test in tests):
            findings.append(
                ProductScopeFinding(
                    "product_scope_lane_tests_invalid",
                    f"{lane_id} tests must contain at least three non-empty strings",
                )
            )
        blocked = lane.get("what_it_does_not_claim")
        if not isinstance(blocked, list) or len(blocked) < 3 or not all(isinstance(claim, str) and claim for claim in blocked):
            findings.append(
                ProductScopeFinding(
                    "product_scope_lane_blocked_claims_invalid",
                    f"{lane_id} what_it_does_not_claim must contain at least three non-empty strings",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[ProductScopeFinding]:
    """Return findings if the witness drifts into readiness-promotion language."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ProductScopeFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ProductScopeFinding(
                    "product_scope_forbidden_promotion_phrase",
                    f"product-scope witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_product_scope_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[ProductScopeFinding]:
    """Validate the Foundation Mode product-scope boundary artifacts."""

    doc_text = load_text(doc_path, "product-scope boundary doc")
    packet_payload = load_json_object(packet_path, "product-scope witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate product-scope boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode product-scope boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_product_scope_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_product_scope_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_product_scope_doc")
    print("[PASS] foundation_product_scope_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
