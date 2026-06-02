#!/usr/bin/env python3
"""Validate the Foundation Mode payment-provider boundary.

Purpose: keep payment-provider preparation local while provider activation,
account binding, merchant onboarding, KYC/tax readiness, payment-method
collection, live charges, refunds, payouts, webhooks, checkout publication,
money movement, customer payment access, external publication, and deployment
claims remain blocked.
Governance scope: Foundation Mode, payment-provider posture, local simulation
questions, provider/private value exclusion, money-movement blocking, and
deployment blocking.
Dependencies: docs/FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md and
examples/foundation_payment_provider_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local payment-provider planning only.
  - No provider activation, live payment, money movement, customer payment
    access, private value, external publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_payment_provider_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_payment_provider_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "payment-provider activation",
    "provider account binding",
    "merchant onboarding completion",
    "KYC readiness",
    "tax readiness",
    "payment-method collection",
    "live charge processing",
    "refund execution",
    "payout settlement",
    "webhook activation",
    "checkout publication",
    "money movement",
    "customer payment access",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("provider_selection_questions", "local_draft", "AwaitingEvidence"),
    ("account_binding_questions", "local_draft", "AwaitingEvidence"),
    ("merchant_onboarding_questions", "local_draft", "AwaitingEvidence"),
    ("kyc_tax_questions", "local_draft", "AwaitingEvidence"),
    ("payment_method_questions", "local_draft", "AwaitingEvidence"),
    ("checkout_flow_questions", "local_draft", "AwaitingEvidence"),
    ("webhook_event_questions", "local_draft", "AwaitingEvidence"),
    ("charge_refund_questions", "local_draft", "AwaitingEvidence"),
    ("payout_settlement_questions", "local_draft", "AwaitingEvidence"),
    ("reconciliation_receipt_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "checkout_publication_allowed",
    "customer_payment_access_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "kyc_readiness_claimed",
    "live_charge_allowed",
    "merchant_onboarding_claimed",
    "money_movement_allowed",
    "next_action",
    "payment_method_collection_allowed",
    "payment_provider_activation_allowed",
    "payment_provider_surfaces",
    "provider_account_binding_allowed",
    "payout_settlement_allowed",
    "refund_execution_allowed",
    "schema_version",
    "solver_outcome",
    "status",
    "tax_readiness_claimed",
    "webhook_activation_allowed",
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
    "Foundation Payment Provider Boundary",
    "Witness packet: [`../examples/foundation_payment_provider_witness.awaiting_evidence.json`]",
    "Rule: Payment-provider preparation is a local planning boundary, not permission",
    "No payment-provider activation, provider-account binding, merchant-onboarding",
    "payment_provider_boundary_state=AwaitingEvidence",
    "payment_provider_activation_allowed=false",
    "provider_account_binding_allowed=false",
    "merchant_onboarding_claimed=false",
    "kyc_readiness_claimed=false",
    "tax_readiness_claimed=false",
    "payment_method_collection_allowed=false",
    "live_charge_allowed=false",
    "refund_execution_allowed=false",
    "payout_settlement_allowed=false",
    "webhook_activation_allowed=false",
    "checkout_publication_allowed=false",
    "money_movement_allowed=false",
    "customer_payment_access_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_payment_provider_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("currency_amount", re.compile(r"(?:[$]\s*\d|\bUSD\s*\d|\b\d+\s*USD\b)", re.IGNORECASE)),
    ("provider_assignment", re.compile(r"\b(?:provider|merchant|processor|stripe|paypal|square)[_ -]?(?:account|id|target|ref|value)\s*=", re.IGNORECASE)),
    ("provider_identifier", re.compile(r"\b(?:acct|pi|ch|cus|pm|evt|whsec)_[A-Za-z0-9]{8,}\b", re.IGNORECASE)),
    ("payment_method_assignment", re.compile(r"\b(?:card|bank|wallet|payment[_ -]?method|token)[_ -]?(?:id|ref|value|target)?\s*=", re.IGNORECASE)),
    ("transaction_assignment", re.compile(r"\b(?:charge|refund|payout|settlement|transaction|payment)[_ -]?(?:id|ref|target|value)?\s*=", re.IGNORECASE)),
    ("customer_assignment", re.compile(r"\b(?:customer|payer|buyer)[_ -]?(?:id|email|target|ref|value)\s*=", re.IGNORECASE)),
    ("webhook_secret_assignment", re.compile(r"\b(?:webhook|signing)[_ -]?(?:secret|token|key)\s*=", re.IGNORECASE)),
    ("live_mode_assignment", re.compile(r"\blive[_ -]?mode\s*=\s*true\b", re.IGNORECASE)),
    ("payment_card_shape", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key|credential)\s*=", re.IGNORECASE)),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("provider_active", re.compile(r"\bpayment[- ]provider\s+(?:is\s+)?(?:active|activated|enabled)\b", re.IGNORECASE)),
    ("account_bound", re.compile(r"\bprovider\s+account\s+(?:is\s+)?(?:bound|linked|active)\b", re.IGNORECASE)),
    ("onboarding_complete", re.compile(r"\bmerchant\s+onboarding\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("kyc_ready", re.compile(r"\bKYC\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("tax_ready", re.compile(r"\btax\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("payment_method_collection_open", re.compile(r"\bpayment[- ]method\s+collection\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("live_charge_processed", re.compile(r"\blive\s+charge\s+(?:is\s+)?processed\b", re.IGNORECASE)),
    ("refund_executed", re.compile(r"\brefund\s+(?:is\s+)?executed\b", re.IGNORECASE)),
    ("payout_settled", re.compile(r"\bpayout\s+(?:is\s+)?settled\b", re.IGNORECASE)),
    ("webhook_active", re.compile(r"\bwebhook\s+(?:is\s+)?(?:active|enabled)\b", re.IGNORECASE)),
    ("checkout_published", re.compile(r"\bcheckout\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("money_movement_allowed", re.compile(r"\bmoney\s+movement\s+(?:is\s+)?(?:allowed|authorized|approved)\b", re.IGNORECASE)),
    ("customer_payment_open", re.compile(r"\bcustomer\s+payment\s+access\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class PaymentProviderFinding:
    """One deterministic payment-provider boundary validation finding."""

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
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_doc_text(text: str) -> list[PaymentProviderFinding]:
    """Return findings for missing payment-provider documentation anchors."""

    findings: list[PaymentProviderFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                PaymentProviderFinding(
                    "foundation_payment_provider_doc_phrase_missing",
                    f"payment-provider boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[PaymentProviderFinding]:
    """Return findings for payment-provider witness drift."""

    findings: list[PaymentProviderFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_payment_provider_surfaces(payload.get("payment_provider_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[PaymentProviderFinding]:
    """Return findings for root-level payment-provider witness drift."""

    findings: list[PaymentProviderFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            PaymentProviderFinding(
                "payment_provider_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "payment_provider_activation_allowed": False,
        "provider_account_binding_allowed": False,
        "merchant_onboarding_claimed": False,
        "kyc_readiness_claimed": False,
        "tax_readiness_claimed": False,
        "payment_method_collection_allowed": False,
        "live_charge_allowed": False,
        "refund_execution_allowed": False,
        "payout_settlement_allowed": False,
        "webhook_activation_allowed": False,
        "checkout_publication_allowed": False,
        "money_movement_allowed": False,
        "customer_payment_access_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                PaymentProviderFinding(
                    "payment_provider_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            PaymentProviderFinding(
                "payment_provider_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local payment-provider question drafting" not in next_action:
        findings.append(
            PaymentProviderFinding(
                "payment_provider_next_action_invalid",
                "next_action must preserve local payment-provider drafting without provider or money-movement claims",
            )
        )
    return findings


def validate_payment_provider_surfaces(payment_provider_surfaces: object) -> list[PaymentProviderFinding]:
    """Return findings for payment-provider surface witness drift."""

    findings: list[PaymentProviderFinding] = []
    if not isinstance(payment_provider_surfaces, list) or not all(
        isinstance(surface, dict) for surface in payment_provider_surfaces
    ):
        return [
            PaymentProviderFinding(
                "payment_provider_surfaces_invalid",
                "payment_provider_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in payment_provider_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            PaymentProviderFinding(
                "payment_provider_surface_inventory_invalid",
                "payment-provider surface inventory does not match the Foundation Mode payment-provider set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in payment_provider_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(PaymentProviderFinding("payment_provider_surface_duplicate", "surface ids must be unique"))
    for surface in payment_provider_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                PaymentProviderFinding(
                    "payment_provider_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                PaymentProviderFinding(
                    "payment_provider_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                PaymentProviderFinding(
                    "payment_provider_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                PaymentProviderFinding(
                    "payment_provider_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[PaymentProviderFinding]:
    """Return findings for provider, payment, customer, live-mode, or secret-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[PaymentProviderFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                PaymentProviderFinding(
                    "payment_provider_forbidden_private_value_pattern",
                    f"payment-provider witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[PaymentProviderFinding]:
    """Return findings if the witness drifts into payment-provider readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[PaymentProviderFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                PaymentProviderFinding(
                    "payment_provider_forbidden_promotion_phrase",
                    f"payment-provider witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_payment_provider_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[PaymentProviderFinding]:
    """Validate the Foundation Mode payment-provider boundary artifacts."""

    doc_text = load_text(doc_path, "payment-provider boundary doc")
    packet_payload = load_json_object(packet_path, "payment-provider witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate payment-provider boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode payment-provider boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_payment_provider_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_payment_provider_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_payment_provider_doc")
    print("[PASS] foundation_payment_provider_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
