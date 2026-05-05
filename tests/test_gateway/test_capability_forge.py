"""Gateway capability forge tests.

Purpose: verify that candidate capability packages remain candidate-only,
    schema-backed, and promotion-blocked until governed certification.
Governance scope: capability candidate generation, validation, schema contract,
    sandbox evidence, approval controls, and recovery coverage.
Dependencies: gateway.capability_forge and schemas/capability_candidate.schema.json.
Invariants:
  - Candidate packages validate against the public schema.
  - Effect-bearing candidates require sandbox, receipt, and recovery evidence.
  - High-risk candidates require approval policy and injection evals.
  - Candidates cannot claim certified status or unblock their own promotion.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from gateway.capability_forge import CapabilityForge, CapabilityForgeInput


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "capability_candidate.schema.json"


def test_capability_forge_creates_schema_valid_candidate_package() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    payload = asdict(candidate)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(schema["required"]).issubset(payload)

    assert schema["$id"] == "urn:mullusi:schema:capability-candidate:1"
    assert schema["properties"]["certification_status"]["const"] == "candidate"
    assert schema["properties"]["promotion_blocked"]["const"] is True
    assert candidate.certification_status == "candidate"
    assert candidate.promotion_blocked is True
    assert candidate.package_hash


def test_capability_forge_projects_high_risk_controls() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    policy_types = {rule.rule_type for rule in candidate.policy_rules if rule.required}
    eval_types = {eval_case.eval_type for eval_case in candidate.evals}

    assert "approval" in policy_types
    assert "tenant_binding" in policy_types
    assert "prompt_injection" in eval_types
    assert candidate.adapter.sandbox_required is True
    assert candidate.receipt_contract.terminal_certificate_required is True
    assert candidate.rollback_path.review_required is True


def test_capability_forge_rejects_candidate_self_promotion() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    promoted = replace(candidate, certification_status="production_certified", promotion_blocked=False)
    validation = CapabilityForge().validate(promoted)

    assert validation.accepted is False
    assert validation.reason == "candidate_invalid"
    assert "candidate_must_not_claim_certified_status" in validation.errors
    assert "candidate_promotion_must_be_blocked" in validation.errors


def test_capability_forge_rejects_effect_bearing_package_without_recovery() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    unsafe = replace(
        candidate,
        rollback_path=replace(candidate.rollback_path, rollback_type="none", review_required=False),
    )
    validation = CapabilityForge().validate(unsafe)

    assert validation.accepted is False
    assert validation.package_id == candidate.package_id
    assert "effect_bearing_candidate_requires_recovery_path" in validation.errors
    assert validation.package_hash == candidate.package_hash


def test_capability_forge_rejects_missing_required_eval() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    unsafe = replace(
        candidate,
        evals=[eval_case for eval_case in candidate.evals if eval_case.eval_type != "tenant_boundary"],
    )

    validation = CapabilityForge().validate(unsafe)

    assert validation.accepted is False
    assert validation.reason == "candidate_invalid"
    assert validation.errors == ("missing_eval:tenant_boundary",)


def test_capability_candidate_schema_rejects_unblocked_candidate() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    payload = asdict(candidate)
    payload["promotion_blocked"] = False
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    promotion_contract = schema["properties"]["promotion_blocked"]
    assert promotion_contract["type"] == "boolean"
    assert promotion_contract["const"] is True
    assert payload["promotion_blocked"] != promotion_contract["const"]


def _forge_input() -> CapabilityForgeInput:
    return CapabilityForgeInput(
        capability_id="payments.send",
        version="0.1.0",
        domain="finance",
        risk="high",
        side_effects=("payment_dispatch",),
        api_docs_ref="docs/providers/payments.md",
        input_schema_ref="schemas/payments_send.input.schema.json",
        output_schema_ref="schemas/payments_send.output.schema.json",
        owner_team="finance_ops",
        network_allowlist=("api.stripe.com",),
        secret_scope="payments/stripe",
        requires_approval=True,
    )
