"""Tests for the default agentic-control capability pack.

Purpose: verify agentic-control capabilities are admitted only with bounded
    schemas, explicit authority policy, approval-gated evidence mutation, and
    production-readiness blocking until live evidence exists.
Governance scope: agentic-control capsule, capability registry entries,
    governed read models, schema contracts, and production gate behavior.
Dependencies: gateway capability fabric loader and schema validation helpers.
Invariants:
  - Agentic-control defaults install governed records, not raw execution tools.
  - Evidence ledger append is world-mutating and approval-gated.
  - Input and output schemas reject unbounded or unknown contract payloads.
  - Production readiness is not claimed without live write, worker, and
    recovery evidence.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from gateway.capability_fabric import build_capability_admission_gate
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry, DomainCapsule
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
AGENTIC_CONTROL_CAPSULE_PATH = ROOT / "capsules" / "agentic_control.json"
AGENTIC_CONTROL_CAPABILITY_PACK_PATH = ROOT / "capabilities" / "agentic_control" / "capability_pack.json"
AGENTIC_CONTROL_INPUT_SCHEMA_PATH = ROOT / "schemas" / "agentic_control" / "control_action.input.schema.json"
AGENTIC_CONTROL_OUTPUT_SCHEMA_PATH = ROOT / "schemas" / "agentic_control" / "control_action.output.schema.json"
CAPABILITY_REGISTRY_SCHEMA_PATH = ROOT / "schemas" / "capability_registry_entry.schema.json"


def test_agentic_control_capability_entries_are_schema_valid() -> None:
    schema = _load_schema(CAPABILITY_REGISTRY_SCHEMA_PATH)
    payload = _load_json(AGENTIC_CONTROL_CAPABILITY_PACK_PATH)
    entries = payload["capabilities"]

    assert len(entries) == 15
    assert all(_validate_schema_instance(schema, entry) == [] for entry in entries)
    assert all(CapabilityRegistryEntry.from_mapping(entry).domain == "agentic_control" for entry in entries)


def test_agentic_control_pack_projects_governed_authority_records() -> None:
    gate = _agentic_control_gate(require_production_ready=False)
    read_model = gate.read_model()
    records = {record["capability_id"]: record for record in read_model["governed_capability_records"]}
    evidence_record = records["agentic_control.evidence.append"]
    mission_decision = gate.admit(command_id="command-agentic-mission", intent_name="agentic_control.mission.define")
    evidence_decision = gate.admit(command_id="command-agentic-evidence", intent_name="agentic_control.evidence.append")

    assert read_model["capsule_count"] == 1
    assert read_model["capability_count"] == 15
    assert read_model["production_ready_count"] == 0
    assert mission_decision.status.value == "accepted"
    assert evidence_decision.status.value == "accepted"
    assert evidence_record["risk_level"] == "high"
    assert evidence_record["world_mutating"] is True
    assert evidence_record["requires_approval"] is True
    assert evidence_record["receipt_required"] is True
    assert evidence_record["rollback_or_compensation_required"] is True


def test_agentic_control_schemas_accept_representative_contracts() -> None:
    input_schema = _load_schema(AGENTIC_CONTROL_INPUT_SCHEMA_PATH)
    output_schema = _load_schema(AGENTIC_CONTROL_OUTPUT_SCHEMA_PATH)
    request_payload = _representative_request()
    receipt_payload = _representative_receipt()

    assert input_schema["additionalProperties"] is False
    assert output_schema["additionalProperties"] is False
    assert _validate_schema_instance(input_schema, request_payload) == []
    assert _validate_schema_instance(output_schema, receipt_payload) == []
    assert request_payload["capability_id"] == receipt_payload["capability_id"]


def test_agentic_control_schemas_reject_unbounded_or_unknown_payloads() -> None:
    input_schema = _load_schema(AGENTIC_CONTROL_INPUT_SCHEMA_PATH)
    output_schema = _load_schema(AGENTIC_CONTROL_OUTPUT_SCHEMA_PATH)
    request_with_unknown = {**_representative_request(), "raw_tool": "shell"}
    request_with_duplicate_constraints = deepcopy(_representative_request())
    request_with_duplicate_constraints["constraints"] = ["halt_on_unknown", "halt_on_unknown"]
    receipt_with_duplicate_evidence = deepcopy(_representative_receipt())
    receipt_with_duplicate_evidence["evidence_refs"] = ["ledger:record-1", "ledger:record-1"]

    assert _validate_schema_instance(input_schema, request_with_unknown)
    assert _validate_schema_instance(input_schema, request_with_duplicate_constraints)
    assert _validate_schema_instance(output_schema, receipt_with_duplicate_evidence)


def test_agentic_control_production_gate_blocks_without_live_evidence() -> None:
    gate = _agentic_control_gate(require_production_ready=True)
    decision = gate.admit(command_id="command-agentic-production", intent_name="agentic_control.evidence.append")

    assert decision.status.value == "rejected"
    assert decision.capability_id == "agentic_control.evidence.append"
    assert "capability is not production-ready" in decision.reason
    assert "effect_bearing_production_requires_live_write" in decision.reason
    assert "worker_deployment_evidence_missing" in decision.reason


def _agentic_control_gate(*, require_production_ready: bool):
    return build_capability_admission_gate(
        capsules=(DomainCapsule.from_mapping(_load_json(AGENTIC_CONTROL_CAPSULE_PATH)),),
        capabilities=tuple(
            CapabilityRegistryEntry.from_mapping(item)
            for item in _load_json(AGENTIC_CONTROL_CAPABILITY_PACK_PATH)["capabilities"]
        ),
        require_certified=True,
        require_production_ready=require_production_ready,
        clock=lambda: "2026-05-31T00:00:00+00:00",
    )


def _representative_request() -> dict:
    return {
        "capability_id": "agentic_control.evidence.append",
        "request_id": "request-agentic-1",
        "mission_ref": "mission/agentic-control-1",
        "objective": "Append the terminal evidence record after verification gates pass.",
        "context": {"tenant_id": "tenant-demo", "case_id": "case-agentic-1"},
        "constraints": ["halt_on_unknown", "require_terminal_certificate"],
        "candidate_actions": ["append_evidence_record"],
        "evidence_refs": ["verification:plan-1"],
        "metadata": {"fixture": "agentic_control_capability_pack"},
    }


def _representative_receipt() -> dict:
    return {
        "capability_id": "agentic_control.evidence.append",
        "request_id": "request-agentic-1",
        "outcome": "SolvedVerified",
        "decision_ref": "decision/agentic-control-1",
        "proof_state": "Pass",
        "evidence_refs": ["ledger:record-1", "closure:certificate-1"],
        "blocked_actions": [],
        "next_actions": ["publish_operator_summary"],
        "metadata": {"fixture": "agentic_control_capability_pack"},
    }


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
