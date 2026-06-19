"""Purpose: verify ReadOnlyWorkerRuntimeAuthorityChainWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime authority chain witness schema, fixture, validator, and
upstream active lease and runtime dispatch admission validators.
Invariants:
  - runtime authority chain admission, worker invocation, receipt emission,
    receipt append, terminal closure, and success claims remain denied.
  - Recovery, replay, failure receipt, and effect reconciliation evidence
    remain mandatory before future runtime admission.
  - Validation remains deterministic and read-only.
  - Mfidel atomicity remains preserved.
"""

from __future__ import annotations

import json
import subprocess
import sys

from scripts.validate_read_only_worker_runtime_authority_chain_witness import (
    DEFAULT_RECEIPT_PATH,
    DEFAULT_SCHEMA_PATH,
    build_mutated_runtime_authority_chain_witness,
    validate_runtime_authority_chain_witness,
    validate_runtime_authority_chain_witness_record,
)
from scripts.validate_schemas import _load_schema


def test_runtime_authority_chain_witness_fixture_passes() -> None:
    errors = validate_runtime_authority_chain_witness()

    assert errors == []
    assert DEFAULT_SCHEMA_PATH.exists()
    assert DEFAULT_RECEIPT_PATH.exists()


def test_runtime_authority_chain_witness_rejects_authority_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_authority_chain_witness(
        authority_scope__active_runtime_lease_admitted=True,
        authority_scope__runtime_dispatch_admitted=True,
        authority_scope__success_claim_allowed=True,
    )

    errors = validate_runtime_authority_chain_witness_record(mutated, schema)

    assert "authority_scope.active_runtime_lease_admitted must be false" in errors
    assert "authority_scope.runtime_dispatch_admitted must be false" in errors
    assert "authority_scope.success_claim_allowed must be false" in errors


def test_runtime_authority_chain_witness_requires_stage_refs() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_authority_chain_witness()
    mutated["chain_stage_refs"]["active_lease_admission"] = "examples/wrong.json"
    mutated["chain_stage_refs"]["phi_gov_dispatch_authorization"] = "examples/wrong.json"
    mutated["required_evidence_refs"] = [
        "evidence://operator-approval/runtime-authority-chain",
    ]

    errors = validate_runtime_authority_chain_witness_record(mutated, schema)

    assert "chain_stage_refs.active_lease_admission is invalid" in errors
    assert "chain_stage_refs.phi_gov_dispatch_authorization is invalid" in errors
    assert any("required_evidence_refs missing required ref" in error for error in errors)


def test_runtime_authority_chain_witness_rejects_chain_evaluation_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_authority_chain_witness(
        chain_evaluation__receipt_store_write_path_required=False,
        chain_evaluation__phi_gov_dispatch_authorized=True,
        chain_evaluation__runtime_receipt_emitted=True,
    )

    errors = validate_runtime_authority_chain_witness_record(mutated, schema)

    assert "chain_evaluation.receipt_store_write_path_required must be true" in errors
    assert "chain_evaluation.phi_gov_dispatch_authorized must be false" in errors
    assert "chain_evaluation.runtime_receipt_emitted must be false" in errors


def test_runtime_authority_chain_witness_rejects_recovery_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_authority_chain_witness(
        recovery_and_replay__worker_failure_receipt_required_on_error=False,
        recovery_and_replay__deterministic_replay_evidence_required=False,
        recovery_and_replay__rollback_completed_claimed=True,
    )

    errors = validate_runtime_authority_chain_witness_record(mutated, schema)

    assert "recovery_and_replay.worker_failure_receipt_required_on_error must be true" in errors
    assert "recovery_and_replay.deterministic_replay_evidence_required must be true" in errors
    assert "recovery_and_replay.rollback_completed_claimed must be false" in errors


def test_runtime_authority_chain_witness_rejects_summary_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_authority_chain_witness(
        contract_summary__stage_ref_count=0,
        contract_summary__chain_denied_check_count=0,
        contract_summary__evidence_ref_count=0,
    )

    errors = validate_runtime_authority_chain_witness_record(mutated, schema)

    assert "contract_summary.stage_ref_count must match observed count" in errors
    assert "contract_summary.chain_denied_check_count must match observed count" in errors
    assert "contract_summary.evidence_ref_count must match observed count" in errors


def test_runtime_authority_chain_witness_cli_json_paths_are_workspace_relative() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_read_only_worker_runtime_authority_chain_witness.py",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "passed"
    assert payload["schema_path"] in {
        "schemas\\read_only_worker_runtime_authority_chain_witness.schema.json",
        "schemas/read_only_worker_runtime_authority_chain_witness.schema.json",
    }
    assert payload["errors"] == []


def test_runtime_authority_chain_witness_rejects_malformed_payload() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)

    errors = validate_runtime_authority_chain_witness_record([], schema)

    assert any("must be object" in error or "must be a JSON object" in error for error in errors)
    assert len(errors) >= 1
    assert schema["$id"] == "urn:mullusi:schema:read-only-worker-runtime-authority-chain-witness:1"
