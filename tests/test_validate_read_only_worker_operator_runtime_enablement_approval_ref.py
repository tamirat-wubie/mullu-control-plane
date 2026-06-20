"""Tests for read-only worker operator runtime enablement approval refs.

Purpose: prove approval refs bind operator evidence without accepting evidence
or granting runtime authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_operator_runtime_enablement_approval_ref.
Invariants:
  - Approval refs are not evidence acceptance.
  - Approval refs are not runtime authorization.
  - Admission remains a separate gate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_read_only_worker_operator_runtime_enablement_approval_ref import (  # noqa: E402
    DEFAULT_EXAMPLE,
    build_mutated_operator_runtime_enablement_approval_ref,
    main,
    validate_operator_runtime_enablement_approval_ref,
    validate_operator_runtime_enablement_approval_ref_record,
)


def test_operator_runtime_enablement_approval_ref_fixture_is_valid() -> None:
    fixture = json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))
    errors = validate_operator_runtime_enablement_approval_ref_record(fixture)

    assert errors == []
    assert fixture["solver_outcome"] == "AwaitingEvidence"
    assert fixture["proof_state"] == "Unknown"
    assert fixture["approval_ref_bound"] is True
    assert fixture["approval_ref_is_not_authorization"] is True
    assert fixture["approval_ref_is_not_runtime_enablement"] is True
    assert fixture["runtime_enablement_allowed"] is False
    assert fixture["runtime_dispatch_allowed"] is False
    assert fixture["worker_invocation_allowed"] is False
    assert fixture["secret_values_serialized"] is False


def test_operator_runtime_enablement_approval_ref_path_validator_passes() -> None:
    errors = validate_operator_runtime_enablement_approval_ref()
    fixture = json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))

    assert errors == []
    assert fixture["approval_scope"]["required_name"] == "MULLU_READ_ONLY_WORKER_RUNTIME_ENABLEMENT_APPROVAL_REF"
    assert fixture["approval_scope"]["evidence_acceptance_required"] is True
    assert fixture["approval_scope"]["runtime_admission_required"] is True


def test_operator_runtime_enablement_approval_ref_rejects_authority_overclaim() -> None:
    mutated = build_mutated_operator_runtime_enablement_approval_ref(
        approval_ref_is_not_authorization=False,
        runtime_enablement_allowed=True,
        runtime_dispatch_allowed=True,
    )

    errors = validate_operator_runtime_enablement_approval_ref_record(mutated)
    serialized_errors = json.dumps(errors, sort_keys=True)

    assert "approval_ref_is_not_authorization must be true" in serialized_errors
    assert "runtime_enablement_allowed must be false" in serialized_errors
    assert "runtime_dispatch_allowed must be false" in serialized_errors


def test_operator_runtime_enablement_approval_ref_rejects_secret_serialization() -> None:
    mutated = build_mutated_operator_runtime_enablement_approval_ref(
        raw_secret_value_present=True,
        secret_values_serialized=True,
    )

    errors = validate_operator_runtime_enablement_approval_ref_record(mutated)
    serialized_errors = json.dumps(errors, sort_keys=True)

    assert "raw_secret_value_present must be false" in serialized_errors
    assert "secret_values_serialized must be false" in serialized_errors
    assert "$.raw_secret_value_present: expected const False" in serialized_errors


def test_operator_runtime_enablement_approval_ref_rejects_scope_admission_drift() -> None:
    mutated = build_mutated_operator_runtime_enablement_approval_ref()
    mutated["approval_scope"]["evidence_acceptance_required"] = False
    mutated["approval_scope"]["runtime_admission_required"] = False

    errors = validate_operator_runtime_enablement_approval_ref_record(mutated)
    serialized_errors = json.dumps(errors, sort_keys=True)

    assert "approval_scope.evidence_acceptance_required must be true" in serialized_errors
    assert "approval_scope.runtime_admission_required must be true" in serialized_errors
    assert "$.approval_scope.runtime_admission_required: expected const True" in serialized_errors


def test_operator_runtime_enablement_approval_ref_cli_json(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)

    assert exit_code == 0
    assert stdout_payload["status"] == "passed"
    assert stdout_payload["runtime_enablement_allowed"] is False
    assert stdout_payload["errors"] == []
    assert captured.err == ""
