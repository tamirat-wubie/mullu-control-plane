"""Test Agentic Service Harness Receipt projection validation.

Purpose: verify receipt refs are projected by AgentRun id without admitting
append, inline receipt bodies, mutation routes, secrets, or terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_receipt_projection.
Invariants:
  - Receipt refs must come from the source EvidenceBundle projection.
  - Projection is read-only and reference-only.
  - Append, mutation, secret-like payloads, and closure fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_receipt_projection as validator


def test_receipt_projection_passes() -> None:
    validation = validator.validate_agentic_service_harness_receipt_projection()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.projection_count == 1
    assert validation.run_count == 1
    assert validation.evidence_bundle_source_ok is True


def test_receipt_projection_rejects_append_and_route_authority() -> None:
    payload = validator.build_mutated_projection(
        scope__receipt_query_route_admitted=True,
        scope__receipt_store_append_enabled=True,
        scope__inline_receipt_body_allowed=True,
        authority_denials__receipt_query_route_enabled=True,
        authority_denials__receipt_store_append_enabled=True,
        authority_denials__inline_receipt_body_enabled=True,
        authority_denials__runtime_state_write_enabled=True,
    )
    payload["receipt_projections"][0]["append_enabled"] = True
    payload["receipt_projections"][0]["inline_receipt_body_allowed"] = True

    errors: list[str] = []
    validator._validate_projection_semantics(payload, _source_bundles(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.receipt_query_route_admitted must be false" in serialized_errors
    assert "scope.receipt_store_append_enabled must be false" in serialized_errors
    assert "scope.inline_receipt_body_allowed must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_enabled must be false" in serialized_errors
    assert "receipt_projections[0].append_enabled must be false" in serialized_errors
    assert "receipt_projections[0].inline_receipt_body_allowed must be false" in serialized_errors


def test_receipt_projection_rejects_source_ref_drift() -> None:
    payload = validator.build_mutated_projection()
    payload["receipt_projections"][0]["receipt_refs"] = ["receipt://not/source-bound"]
    payload["receipt_projections"][0]["receipt_count"] = 3
    payload["receipt_projections"][0]["source_bundle_ref"] = "agent-run://wrong/evidence-bundle"

    errors: list[str] = []
    validator._validate_projection_semantics(payload, _source_bundles(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "receipt_refs not present in source bundle" in serialized_errors
    assert "receipt_count must equal receipt_refs length" in serialized_errors
    assert "source_bundle_ref must match source run_lookup_ref" in serialized_errors


def test_receipt_projection_rejects_index_and_policy_drift() -> None:
    payload = validator.build_mutated_projection(
        projection_index__projection_count=2,
        projection_index__run_count=2,
        receipt_refs__receipt_projection_schema="schemas/wrong.schema.json",
    )
    payload["receipt_projections"][0]["policy_refs"] = ["gate://harness/no-mutation-endpoints"]

    errors: list[str] = []
    validator._validate_projection_semantics(payload, _source_bundles(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "projection_index.projection_count must equal receipt_projections length" in serialized_errors
    assert "projection_index.run_count must equal unique run id count" in serialized_errors
    assert "policy_refs must include no-receipt-store-append" in serialized_errors
    assert "policy_refs must include terminal-closure-denied" in serialized_errors
    assert "receipt_refs.receipt_projection_schema must be" in serialized_errors


def test_receipt_projection_rejects_secret_and_mutation_route() -> None:
    payload = validator.build_mutated_projection(
        next_action="POST /api/harness/receipts should remain blocked",
    )
    payload["receipt_refs"]["access_token_receipt"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_projection_semantics(payload, _source_bundles(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_receipt_projection_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "receipt-projection-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["projection_count"] == 1


def _source_bundles() -> dict[str, object]:
    payload = json.loads(validator.DEFAULT_EVIDENCE_BUNDLE_EXAMPLES[0].read_text(encoding="utf-8"))
    return validator._source_bundles_by_run_id(payload)
