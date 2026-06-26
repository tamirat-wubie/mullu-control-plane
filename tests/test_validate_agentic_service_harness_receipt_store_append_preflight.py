"""Test Agentic Service Harness receipt-store append preflight validation.

Purpose: verify harness receipt-store append remains blocked until append
authority, audit, idempotency, replay, rollback, and redaction evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_receipt_store_append_preflight.
Invariants:
  - Source task-record UAO and Universal Symbol receipt-store witnesses pass.
  - Receipt-store append is not admitted or performed.
  - Mutation routes, append claims, raw payloads, and secrets fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_receipt_store_append_preflight as validator


def test_receipt_store_append_preflight_passes() -> None:
    validation = validator.validate_agentic_service_harness_receipt_store_append_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_validators_ok is True


def test_receipt_store_append_preflight_rejects_append_authority_drift() -> None:
    payload = validator.build_mutated_preflight(
        scope__receipt_store_append_admitted=True,
        scope__receipt_store_appended=True,
        append_admission__receipt_store_append_admitted=True,
        authority_denials__receipt_store_append_enabled=True,
        authority_denials__receipt_store_append_performed=True,
        authority_denials__receipt_store_write_path_registered=True,
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.receipt_store_append_admitted must be false" in serialized_errors
    assert "scope.receipt_store_appended must be false" in serialized_errors
    assert "append_admission.receipt_store_append_admitted must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_enabled must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_performed must be false" in serialized_errors
    assert "authority_denials.receipt_store_write_path_registered must be false" in serialized_errors


def test_receipt_store_append_preflight_rejects_missing_refs() -> None:
    payload = validator.build_mutated_preflight(
        source_contract_refs=["MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md"],
        append_admission__required_before_append_refs=[
            "approval://operator/harness-receipt-store-append"
        ],
        append_admission__blocked_reason_refs=[
            "blocked://receipt-store-append/operator-approval-missing"
        ],
        append_admission__next_required_evidence_refs=[
            "evidence://executed-test-receipt-admission"
        ],
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "missing source_contract_refs" in serialized_errors
    assert "append_admission.required_before_append_refs missing required ref" in serialized_errors
    assert "append_admission.blocked_reason_refs missing required ref" in serialized_errors
    assert "append_admission.next_required_evidence_refs missing required ref" in serialized_errors


def test_receipt_store_append_preflight_rejects_receipt_contract_drift() -> None:
    payload = validator.build_mutated_preflight(
        receipt_contract__allowed_metadata_refs=["field://receipt/id"],
        receipt_contract__forbidden_inline_fields=["field://receipt/raw-secret"],
        receipt_contract__append_result_claimed=True,
        receipt_contract__stored_receipt_ref="receipt-store://appended",
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "receipt_contract.allowed_metadata_refs incomplete" in serialized_errors
    assert "receipt_contract.forbidden_inline_fields incomplete" in serialized_errors
    assert "receipt_contract.append_result_claimed must be false" in serialized_errors
    assert "stored_receipt_ref must remain not-appended" in serialized_errors


def test_receipt_store_append_preflight_rejects_mutation_route_and_secret() -> None:
    payload = validator.build_mutated_preflight(
        next_action="POST /api/harness/receipts must never be admitted",
    )
    payload["append_admission"]["api_key"] = "sk-test-not-allowed"

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_receipt_store_append_preflight_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "receipt-store-append-preflight-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_validators_ok"] is True
