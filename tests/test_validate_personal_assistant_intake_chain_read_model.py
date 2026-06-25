"""Tests for personal-assistant intake-chain read-model validation.

Purpose: prove the intake-chain read model is schema-backed, source-bound, and
unable to grant execution, connector mutation, private payload serialization,
or approval-as-execution authority.
Governance scope: personal-assistant intake, interpretation, WHQR, plan,
approval, receipt, and no-effect evidence boundaries.
Dependencies: scripts.validate_personal_assistant_intake_chain_read_model.
Invariants:
  - Request, interpretation, and plan identifiers stay aligned.
  - P4/P5 effect paths remain approval-gated and non-executing.
  - Raw private payloads and secret-like values are rejected.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_personal_assistant_intake_chain_read_model import (
    DEFAULT_READ_MODEL,
    validate_personal_assistant_intake_chain_read_model,
)


def test_personal_assistant_intake_chain_fixture_validates() -> None:
    result = validate_personal_assistant_intake_chain_read_model()

    assert result.valid is True
    assert result.read_model_path == "examples/personal_assistant_intake_chain_read_model.foundation.json"
    assert result.source_artifact_count == 5
    assert result.receipt_ref_count == 1
    assert result.errors == ()


def test_intake_chain_validator_rejects_execution_authority(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["effect_boundary"]["execution_allowed"] = True
    payload["approval_boundary"]["approval_is_execution"] = True
    payload["plan_preview"]["plan"]["execution_allowed"] = True
    candidate = tmp_path / "unsafe_intake_chain.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_intake_chain_read_model(read_model_path=candidate)

    assert result.valid is False
    assert "effect_boundary.execution_allowed must be false" in result.errors
    assert "approval_boundary.approval_is_execution must be false" in result.errors
    assert "plan_preview.plan.execution_allowed must be false" in result.errors


def test_intake_chain_validator_rejects_interpretation_authority_drift(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["interpretation"]["deterministic_override_allowed"] = True
    payload["interpretation"]["action_authority_granted"] = True
    payload["interpretation"]["execution_allowed"] = True
    candidate = tmp_path / "unsafe_interpretation_chain.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_intake_chain_read_model(read_model_path=candidate)

    assert result.valid is False
    assert "$.interpretation.deterministic_override_allowed: expected const False" in result.errors
    assert "$.interpretation.action_authority_granted: expected const False" in result.errors
    assert "$.interpretation.execution_allowed: expected const False" in result.errors


def test_intake_chain_validator_rejects_raw_payload_and_secret(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["request"]["raw_connector_payload"] = "private mailbox transcript"
    payload["lineage"]["accepted_deltas"][0]["reason"] = "rotate Bearer secret-worker-token"
    payload["private_payload_policy"]["secret_values_serialized"] = True
    candidate = tmp_path / "secret_intake_chain.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_intake_chain_read_model(read_model_path=candidate)

    assert result.valid is False
    assert "$.request.raw_connector_payload: raw private or secret field is forbidden" in result.errors
    assert "$.lineage.accepted_deltas[0].reason: secret-like value must not be serialized" in result.errors
    assert "$.private_payload_policy.secret_values_serialized: expected const False" in result.errors
    assert "private_payload_policy.secret_values_serialized must be false" in result.errors


def test_intake_chain_validator_rejects_request_id_mismatch(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["interpretation"]["personal_assistant_request_id"] = "pa_request_mismatch"
    payload["plan_preview"]["plan"]["request_id"] = "pa_request_plan_mismatch"
    payload["contract_summary"]["missing_binding_count"] = 4
    candidate = tmp_path / "mismatched_intake_chain.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_intake_chain_read_model(read_model_path=candidate)

    assert result.valid is False
    assert "interpretation.personal_assistant_request_id must match request.request_id" in result.errors
    assert "plan_preview.plan.request_id must match request.request_id" in result.errors
    assert "contract_summary.missing_binding_count must match clarification missing binding count" in result.errors


def test_intake_chain_validator_rejects_missing_clarification_questions(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["request"]["missing_binding_count"] = 2
    payload["clarification"]["required"] = True
    payload["clarification"]["missing_binding_count"] = 2
    payload["clarification"]["questions"] = ["Which target should I use?"]
    candidate = tmp_path / "underbound_clarification_chain.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_intake_chain_read_model(read_model_path=candidate)

    assert result.valid is False
    assert "clarification.questions must cover every missing binding when clarification is required" in result.errors
    assert "contract_summary.missing_binding_count must match clarification missing binding count" in result.errors
    assert result.source_artifact_count == 5


def test_intake_chain_validator_rejects_missing_source_ref(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["source_artifacts"][0]["source_ref"] = "examples/does_not_exist.json"
    payload["approval_boundary"]["source_ref"] = "examples/missing_approval.json"
    payload["contract_summary"]["source_artifact_count"] = 99
    candidate = tmp_path / "missing_source_chain.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_intake_chain_read_model(read_model_path=candidate)

    assert result.valid is False
    assert "source_artifacts[0].source_ref does not exist" in result.errors
    assert "approval_boundary.source_ref does not exist" in result.errors
    assert "contract_summary.source_artifact_count must match source_artifacts length" in result.errors


def test_intake_chain_validator_rejects_count_drift(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["contract_summary"]["evidence_ref_count"] = 1
    payload["contract_summary"]["receipt_ref_count"] = 4
    payload["plan_preview"]["step_count"] = 99
    payload["plan_preview"]["actions_not_authorized"] = ["email_send"]
    candidate = tmp_path / "count_drift_intake_chain.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_intake_chain_read_model(read_model_path=candidate)

    assert result.valid is False
    assert "contract_summary.evidence_ref_count must match evidence_refs length" in result.errors
    assert "contract_summary.receipt_ref_count must match receipt_refs length" in result.errors
    assert "plan_preview.step_count must match plan.steps length" in result.errors
    assert "plan_preview.actions_not_authorized must match plan.actions_not_authorized" in result.errors


def _load_fixture() -> dict[str, object]:
    return copy.deepcopy(json.loads(DEFAULT_READ_MODEL.read_text(encoding="utf-8")))
