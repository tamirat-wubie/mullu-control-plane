"""Purpose: verify the agentic-control capability pack.

Governance scope: autonomous mission control, governance gating, resource
bounding, verification planning, product planning, swarm coordination, and
interrogation, recursive refinement, memory-admission planning,
incident-recovery planning, and append-only evidence ledger capability boundaries.
Dependencies: gateway capability fabric loader and governed capability contracts.
Invariants:
  - Agentic-control capabilities grant planning and ledger authority only.
  - Planning powers do not execute tools, write files, send messages, or spawn agents.
  - Evidence append is effect-bearing and requires receipt plus recovery evidence.
  - Production-readiness claims fail without live receipts and worker evidence.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from gateway.capability_fabric import (
    build_agentic_control_capability_admission_gate,
    load_agentic_control_capability_entries,
    load_agentic_control_domain_capsule,
)
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry, DomainCapsule
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
AGENTIC_CONTROL_CAPSULE_PATH = ROOT / "capsules" / "agentic_control.json"
AGENTIC_CONTROL_CAPABILITY_PACK_PATH = ROOT / "capabilities" / "agentic_control" / "capability_pack.json"
AGENTIC_CONTROL_SCHEMA_DIR = ROOT / "schemas" / "agentic_control"
CAPABILITY_REGISTRY_SCHEMA_PATH = ROOT / "schemas" / "capability_registry_entry.schema.json"


def test_agentic_control_capability_entries_are_schema_valid() -> None:
    schema = _load_schema(CAPABILITY_REGISTRY_SCHEMA_PATH)
    payload = _load_json(AGENTIC_CONTROL_CAPABILITY_PACK_PATH)
    entries = payload["capabilities"]

    assert len(entries) == 14
    assert all(_validate_schema_instance(schema, entry) == [] for entry in entries)
    assert all(CapabilityRegistryEntry.from_mapping(entry).domain == "agentic_control" for entry in entries)


def test_agentic_control_schema_refs_are_materialized_and_strict() -> None:
    entries = _agentic_control_entries()
    input_refs = {entry.input_schema_ref for entry in entries}
    output_refs = {entry.output_schema_ref for entry in entries}

    assert input_refs == {"schemas/agentic_control/control_action.input.schema.json"}
    assert output_refs == {"schemas/agentic_control/control_action.output.schema.json"}
    for ref in (*input_refs, *output_refs):
        schema = _load_schema(ROOT / ref)
        assert schema["additionalProperties"] is False
        assert schema["$id"].startswith("urn:mullusi:schema:agentic-control:")


def test_agentic_control_input_schema_accepts_representative_requests() -> None:
    schema = _load_schema(AGENTIC_CONTROL_SCHEMA_DIR / "control_action.input.schema.json")
    payloads = _representative_agentic_control_input_payloads()

    assert set(payloads) == {entry.capability_id for entry in _agentic_control_entries()}
    for capability_id, payload in payloads.items():
        assert _validate_schema_instance(schema, payload) == []
        assert payload["capability_id"] == capability_id
        assert payload["metadata"]["fixture"] == "agentic_control_capability_pack"


def test_agentic_control_input_schema_rejects_boundary_violations() -> None:
    schema = _load_schema(AGENTIC_CONTROL_SCHEMA_DIR / "control_action.input.schema.json")
    payload = deepcopy(_representative_agentic_control_input_payloads()["agentic_control.mission.define"])
    unknown_capability = deepcopy(payload)
    missing_objective = deepcopy(payload)
    bad_request_id = deepcopy(payload)

    unknown_capability["capability_id"] = "agentic_control.raw_tool.execute"
    missing_objective["objective"] = ""
    bad_request_id["request_id"] = "../mission"

    assert _validate_schema_instance(schema, unknown_capability)
    assert _validate_schema_instance(schema, missing_objective)
    assert _validate_schema_instance(schema, bad_request_id)


def test_agentic_control_output_schema_accepts_representative_receipts() -> None:
    schema = _load_schema(AGENTIC_CONTROL_SCHEMA_DIR / "control_action.output.schema.json")
    payloads = _representative_agentic_control_output_payloads()

    assert set(payloads) == {entry.capability_id for entry in _agentic_control_entries()}
    for capability_id, payload in payloads.items():
        assert _validate_schema_instance(schema, payload) == []
        assert payload["capability_id"] == capability_id
        assert payload["outcome"] == "SolvedVerified"
        assert payload["metadata"]["fixture"] == "agentic_control_capability_pack"


def test_agentic_control_output_schema_rejects_overclaims() -> None:
    schema = _load_schema(AGENTIC_CONTROL_SCHEMA_DIR / "control_action.output.schema.json")
    payload = deepcopy(_representative_agentic_control_output_payloads()["agentic_control.governance_gate.evaluate"])
    bad_proof = deepcopy(payload)
    no_evidence = deepcopy(payload)
    unknown_outcome = deepcopy(payload)
    unknown_capability = deepcopy(payload)

    bad_proof["proof_state"] = "Maybe"
    no_evidence["evidence_refs"] = []
    unknown_outcome["outcome"] = "success"
    unknown_capability["capability_id"] = "agentic_control.raw_tool.execute"

    assert _validate_schema_instance(schema, bad_proof)
    assert _validate_schema_instance(schema, no_evidence)
    assert _validate_schema_instance(schema, unknown_outcome)
    assert _validate_schema_instance(schema, unknown_capability)


def test_agentic_control_capsule_references_exact_pack_capabilities() -> None:
    capsule = DomainCapsule.from_mapping(_load_json(AGENTIC_CONTROL_CAPSULE_PATH))
    capabilities = _agentic_control_entries()
    capability_ids = tuple(entry.capability_id for entry in capabilities)

    assert capsule.domain == "agentic_control"
    assert capsule.certification_status.value == "certified"
    assert capsule.capability_refs == capability_ids
    assert len(set(capability_ids)) == len(capability_ids)


def test_agentic_control_pack_installs_through_explicit_capability_fabric() -> None:
    capsule = load_agentic_control_domain_capsule()
    entries = load_agentic_control_capability_entries()
    gate = _agentic_control_gate(require_production_ready=False)
    read_model = gate.read_model()
    mission_decision = gate.admit(command_id="cmd-mission", intent_name="agentic_control.mission.define")
    evidence_decision = gate.admit(command_id="cmd-evidence", intent_name="agentic_control.evidence.append")
    raw_tool_decision = gate.admit(command_id="cmd-raw-tool", intent_name="agentic_control.raw_tool.execute")

    assert capsule.domain == "agentic_control"
    assert len(entries) == 14
    assert read_model["capsule_count"] == 1
    assert read_model["capability_count"] == 14
    assert read_model["domains"] == ({"domain": "agentic_control", "capability_ids": tuple(sorted(capsule.capability_refs))},)
    assert mission_decision.status.value == "accepted"
    assert evidence_decision.status.value == "accepted"
    assert raw_tool_decision.status.value == "rejected"


def test_agentic_control_governed_records_bind_planning_and_ledger_boundaries() -> None:
    gate = _agentic_control_gate(require_production_ready=False)
    governed = {item["capability_id"]: item for item in gate.read_model()["governed_capability_records"]}
    mission_record = governed["agentic_control.mission.define"]
    gate_record = governed["agentic_control.governance_gate.evaluate"]
    swarm_record = governed["agentic_control.swarm.coordinate"]
    interrogation_record = governed["agentic_control.interrogation.plan"]
    refinement_record = governed["agentic_control.self_audit.refine"]
    memory_record = governed["agentic_control.memory_admission.plan"]
    incident_record = governed["agentic_control.incident_recovery.plan"]
    evidence_record = governed["agentic_control.evidence.append"]

    assert mission_record["read_only"] is True
    assert mission_record["world_mutating"] is False
    assert mission_record["requires_approval"] is False
    assert mission_record["allowed_tools"] == ["agentic_control.mission.define"]
    assert gate_record["forbidden_effects"] == ["blocked_action_executed", "approval_forged", "policy_bypassed"]
    assert swarm_record["forbidden_effects"] == ["subagent_spawned", "duplicate_work_authorized", "budget_limit_increased"]
    assert interrogation_record["read_only"] is True
    assert interrogation_record["forbidden_effects"] == [
        "hard_unknown_ignored",
        "external_message_sent",
        "workspace_file_written",
    ]
    assert refinement_record["read_only"] is True
    assert refinement_record["forbidden_effects"] == [
        "unbounded_recursion_authorized",
        "action_executed_without_verification",
        "workspace_file_written",
    ]
    assert memory_record["read_only"] is True
    assert memory_record["forbidden_effects"] == [
        "memory_written",
        "raw_logs_admitted",
        "unverified_summary_generalized",
    ]
    assert incident_record["read_only"] is True
    assert incident_record["forbidden_effects"] == [
        "rollback_executed",
        "incident_closed_without_evidence",
        "external_message_sent",
    ]
    assert evidence_record["read_only"] is False
    assert evidence_record["world_mutating"] is True
    assert evidence_record["requires_approval"] is True
    assert evidence_record["receipt_required"] is True
    assert evidence_record["rollback_or_compensation_required"] is True


def test_agentic_control_pack_blocks_production_ready_overclaim() -> None:
    gate = _agentic_control_gate(require_production_ready=True)
    mission_decision = gate.admit(command_id="cmd-mission-prod", intent_name="agentic_control.mission.define")
    evidence_decision = gate.admit(command_id="cmd-evidence-prod", intent_name="agentic_control.evidence.append")

    assert mission_decision.status.value == "rejected"
    assert mission_decision.capability_id == "agentic_control.mission.define"
    assert "capability is not production-ready" in mission_decision.reason
    assert "sandbox_receipt_missing" in mission_decision.reason
    assert evidence_decision.status.value == "rejected"
    assert evidence_decision.capability_id == "agentic_control.evidence.append"
    assert "effect_bearing_production_requires_live_write" in evidence_decision.reason


def _agentic_control_gate(*, require_production_ready: bool):
    return build_agentic_control_capability_admission_gate(
        clock=lambda: "2026-05-31T00:00:00+00:00",
        require_production_ready=require_production_ready,
    )


def _agentic_control_entries() -> tuple[CapabilityRegistryEntry, ...]:
    return tuple(
        CapabilityRegistryEntry.from_mapping(item)
        for item in _load_json(AGENTIC_CONTROL_CAPABILITY_PACK_PATH)["capabilities"]
    )


def _representative_agentic_control_input_payloads() -> dict[str, dict]:
    metadata = {"fixture": "agentic_control_capability_pack"}
    base = {
        "request_id": "req-agentic-control",
        "mission_ref": "mission:autonomous-ops",
        "objective": "Bound and verify autonomous control-plane work",
        "context": {"repository": "repo:mullu-control-plane", "date": "2026-05-31"},
        "constraints": ["no raw tool execution", "no unbounded loops", "append evidence"],
        "candidate_actions": ["plan", "verify", "append-ledger"],
        "evidence_refs": ["proof://agentic-control/input"],
        "metadata": metadata,
    }
    return {
        entry.capability_id: {**base, "capability_id": entry.capability_id}
        for entry in _agentic_control_entries()
    }


def _representative_agentic_control_output_payloads() -> dict[str, dict]:
    metadata = {"fixture": "agentic_control_capability_pack"}
    base = {
        "request_id": "req-agentic-control",
        "outcome": "SolvedVerified",
        "decision_ref": "decision:agentic-control",
        "proof_state": "Pass",
        "evidence_refs": ["proof://agentic-control/output"],
        "blocked_actions": ["agentic_control.raw_tool.execute"],
        "next_actions": ["run verification gates"],
        "metadata": metadata,
    }
    return {
        entry.capability_id: {**base, "capability_id": entry.capability_id}
        for entry in _agentic_control_entries()
    }


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
