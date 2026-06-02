#!/usr/bin/env python3
"""Validate the Foundation Mode cost/budget boundary.

Purpose: keep cost and budget preparation local while spending, paid
infrastructure, provider billing, payment-method binding, subscription
creation, purchase approval, invoice payment, vendor commitment, and deployment
claims remain blocked.
Governance scope: Foundation Mode, cost posture, budget posture, public-safe
planning witness, payment-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_COST_BUDGET_BOUNDARY.md and
examples/foundation_cost_budget_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local cost/budget planning only.
  - No spending, paid infrastructure, billing activation, payment method,
    purchase, invoice payment, vendor commitment, private value, or deployment
    claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_COST_BUDGET_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_cost_budget_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_cost_budget_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "spending authorization",
    "paid infrastructure activation",
    "provider billing activation",
    "payment method binding",
    "subscription creation",
    "purchase approval",
    "invoice payment",
    "budget limit approval",
    "cost forecast approval",
    "external vendor commitment",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("expense_category_draft", "local_draft", "AwaitingEvidence"),
    ("budget_limit_questions", "local_draft", "AwaitingEvidence"),
    ("paid_infrastructure_questions", "local_draft", "AwaitingEvidence"),
    ("provider_billing_questions", "local_draft", "AwaitingEvidence"),
    ("payment_method_questions", "local_draft", "AwaitingEvidence"),
    ("subscription_purchase_questions", "local_draft", "AwaitingEvidence"),
    ("invoice_payment_questions", "local_draft", "AwaitingEvidence"),
    ("cost_monitoring_checklist", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "budget_limit_approved",
    "cost_budget_surfaces",
    "cost_forecast_approved",
    "deployment_allowed",
    "external_vendor_commitment_allowed",
    "invoice_payment_allowed",
    "next_action",
    "paid_infrastructure_allowed",
    "payment_method_binding_allowed",
    "provider_billing_allowed",
    "purchase_approval_allowed",
    "schema_version",
    "solver_outcome",
    "spending_allowed",
    "status",
    "subscription_creation_allowed",
    "witness_id",
}
EXPECTED_SURFACE_KEYS = {
    "evidence_ref",
    "public_safe_note",
    "state",
    "surface_id",
    "surface_type",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Cost Budget Boundary",
    "Witness packet: [`../examples/foundation_cost_budget_witness.awaiting_evidence.json`]",
    "Rule: Cost/budget preparation is a local planning boundary, not permission to spend money.",
    "No spending authorization, paid infrastructure activation, provider billing",
    "cost_budget_boundary_state=AwaitingEvidence",
    "spending_allowed=false",
    "paid_infrastructure_allowed=false",
    "provider_billing_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_cost_budget_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("currency_amount", re.compile(r"(?:[$]\s*\d|\bUSD\s*\d|\b\d+\s*USD\b)", re.IGNORECASE)),
    ("amount_assignment", re.compile(r"\b(?:amount|price|quote|cost|budget|limit|spend)[_ -]?(?:value|amount|usd)?\s*=", re.IGNORECASE)),
    ("payment_method_assignment", re.compile(r"\b(?:card|bank|wallet|payment[_ -]?method)[_ -]?(?:id|ref|value|target)?\s*=", re.IGNORECASE)),
    ("provider_account_assignment", re.compile(r"\b(?:provider|vendor|billing|subscription)[_ -]?(?:account|id|target|ref)\s*=", re.IGNORECASE)),
    ("invoice_assignment", re.compile(r"\b(?:invoice|receipt|settlement)[_ -]?(?:id|ref|number|target)?\s*=", re.IGNORECASE)),
    ("payment_card_shape", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("budget_approved", re.compile(r"\bbudget\s+(?:limit\s+)?(?:is\s+)?approved\b", re.IGNORECASE)),
    ("spending_allowed", re.compile(r"\bspending\s+(?:is\s+)?(?:allowed|authorized|approved)\b", re.IGNORECASE)),
    ("paid_infrastructure_active", re.compile(r"\bpaid\s+infrastructure\s+(?:is\s+)?(?:active|enabled|approved)\b", re.IGNORECASE)),
    ("billing_enabled", re.compile(r"\bbilling\s+(?:is\s+)?(?:enabled|active|approved)\b", re.IGNORECASE)),
    ("payment_method_bound", re.compile(r"\bpayment\s+method\s+(?:is\s+)?(?:bound|linked|active)\b", re.IGNORECASE)),
    ("subscription_active", re.compile(r"\bsubscription\s+(?:is\s+)?(?:active|created|enabled)\b", re.IGNORECASE)),
    ("purchase_approved", re.compile(r"\bpurchase\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("invoice_paid", re.compile(r"\binvoice\s+(?:is\s+)?paid\b", re.IGNORECASE)),
    ("cost_forecast_approved", re.compile(r"\bcost\s+forecast\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("vendor_committed", re.compile(r"\bvendor\s+(?:is\s+)?(?:committed|approved|active)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class CostBudgetFinding:
    """One deterministic cost/budget boundary validation finding."""

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


def validate_doc_text(text: str) -> list[CostBudgetFinding]:
    """Return findings for missing cost/budget documentation anchors."""

    findings: list[CostBudgetFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                CostBudgetFinding(
                    "foundation_cost_budget_doc_phrase_missing",
                    f"cost/budget boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[CostBudgetFinding]:
    """Return findings for cost/budget witness drift."""

    findings: list[CostBudgetFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_cost_budget_surfaces(payload.get("cost_budget_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[CostBudgetFinding]:
    """Return findings for root-level cost/budget witness drift."""

    findings: list[CostBudgetFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            CostBudgetFinding(
                "cost_budget_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "spending_allowed": False,
        "paid_infrastructure_allowed": False,
        "provider_billing_allowed": False,
        "payment_method_binding_allowed": False,
        "subscription_creation_allowed": False,
        "purchase_approval_allowed": False,
        "invoice_payment_allowed": False,
        "budget_limit_approved": False,
        "cost_forecast_approved": False,
        "external_vendor_commitment_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                CostBudgetFinding(
                    "cost_budget_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            CostBudgetFinding(
                "cost_budget_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not spend" not in next_action:
        findings.append(
            CostBudgetFinding(
                "cost_budget_next_action_invalid",
                "next_action must preserve the closed spending boundary",
            )
        )
    return findings


def validate_cost_budget_surfaces(cost_budget_surfaces: object) -> list[CostBudgetFinding]:
    """Return findings for cost/budget surface witness drift."""

    findings: list[CostBudgetFinding] = []
    if not isinstance(cost_budget_surfaces, list) or not all(
        isinstance(surface, dict) for surface in cost_budget_surfaces
    ):
        return [CostBudgetFinding("cost_budget_surfaces_invalid", "cost_budget_surfaces must be a list of objects")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in cost_budget_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            CostBudgetFinding(
                "cost_budget_surface_inventory_invalid",
                "cost/budget surface inventory does not match the Foundation Mode cost set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in cost_budget_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(CostBudgetFinding("cost_budget_surface_duplicate", "surface ids must be unique"))
    for surface in cost_budget_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                CostBudgetFinding(
                    "cost_budget_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                CostBudgetFinding(
                    "cost_budget_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                CostBudgetFinding(
                    "cost_budget_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                CostBudgetFinding(
                    "cost_budget_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[CostBudgetFinding]:
    """Return findings for monetary, payment, account, invoice, path, or secret-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[CostBudgetFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                CostBudgetFinding(
                    "cost_budget_forbidden_private_value_pattern",
                    f"cost/budget witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[CostBudgetFinding]:
    """Return findings if the witness drifts into cost/budget readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[CostBudgetFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                CostBudgetFinding(
                    "cost_budget_forbidden_promotion_phrase",
                    f"cost/budget witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_cost_budget_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[CostBudgetFinding]:
    """Validate the Foundation Mode cost/budget boundary artifacts."""

    doc_text = load_text(doc_path, "cost/budget boundary doc")
    packet_payload = load_json_object(packet_path, "cost/budget witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate cost/budget boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode cost/budget boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_cost_budget_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_cost_budget_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_cost_budget_doc")
    print("[PASS] foundation_cost_budget_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
