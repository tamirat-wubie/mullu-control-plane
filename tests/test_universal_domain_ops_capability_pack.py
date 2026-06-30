"""Purpose: verify the Universal Domain Operating Pack capability capsule.

Governance scope: UDOP schema, executable linter, capsule admission, claim
boundary, false-success blocking, and production-readiness overclaim blocking.
Dependencies: gateway capability fabric loader, governed capability contracts,
shared schema validator, and domain-pack validator.
Invariants:
  - UDOP capabilities are not loaded by default.
  - UDOP grants validation, linting, simulation, and claim-boundary authority only.
  - Domain packs cannot grant authority above the core system.
  - Output claims cannot exceed the verified workflow state.
  - Production readiness remains blocked without live witness evidence.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from gateway.capability_fabric import (
    build_universal_domain_ops_capability_admission_gate,
    load_default_capability_entries,
    load_default_domain_capsules,
    load_universal_domain_ops_capability_entries,
    load_universal_domain_ops_domain_capsule,
)
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry, DomainCapsule
from scripts.validate_domain_pack import validate_domain_pack
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
UNIVERSAL_DOMAIN_OPS_CAPSULE_PATH = ROOT / "capsules" / "universal_domain_ops.json"
UNIVERSAL_DOMAIN_OPS_CAPABILITY_PACK_PATH = ROOT / "capabilities" / "universal_domain_ops" / "capability_pack.json"
UNIVERSAL_DOMAIN_OPS_SCHEMA_DIR = ROOT / "schemas" / "universal_domain_ops"
INVOICE_DOMAIN_PACK_FIXTURE = ROOT / "tests" / "fixtures" / "universal_domain_ops" / "invoice_domain_pack.json"
CAPABILITY_REGISTRY_SCHEMA_PATH = ROOT / "schemas" / "capability_registry_entry.schema.json"


def test_universal_domain_ops_pack_is_not_loaded_by_default() -> None:
    default_capsules = load_default_domain_capsules()
    default_capabilities = load_default_capability_entries()

    assert all(capsule.domain != "universal_domain_ops" for capsule in default_capsules)
    assert all(entry.domain != "universal_domain_ops" for entry in default_capabilities)
    assert UNIVERSAL_DOMAIN_OPS_CAPSULE_PATH.exists()
    assert UNIVERSAL_DOMAIN_OPS_CAPABILITY_PACK_PATH.exists()


def test_universal_domain_ops_capability_entries_are_schema_valid() -> None:
    schema = _load_schema(CAPABILITY_REGISTRY_SCHEMA_PATH)
    payload = _load_json(UNIVERSAL_DOMAIN_OPS_CAPABILITY_PACK_PATH)
    entries = payload["capabilities"]

    assert len(entries) == 4
    assert all(_validate_schema_instance(schema, entry) == [] for entry in entries)
    assert all(CapabilityRegistryEntry.from_mapping(entry).domain == "universal_domain_ops" for entry in entries)
    assert {entry["input_schema_ref"] for entry in entries} == {
        "schemas/universal_domain_ops/domain_operation.input.schema.json"
    }
    assert {entry["output_schema_ref"] for entry in entries} == {
        "schemas/universal_domain_ops/domain_operation.output.schema.json"
    }


def test_universal_domain_ops_domain_pack_schema_accepts_invoice_fixture() -> None:
    schema = _load_schema(UNIVERSAL_DOMAIN_OPS_SCHEMA_DIR / "domain_pack.schema.json")
    payload = _load_json(INVOICE_DOMAIN_PACK_FIXTURE)
    errors = validate_domain_pack(INVOICE_DOMAIN_PACK_FIXTURE)

    assert _validate_schema_instance(schema, payload) == []
    assert errors == []
    assert payload["governance"]["core_authority_ceiling"] is True
    assert "execute_payment" in payload["actions"]["forbidden"]


def test_universal_domain_ops_linter_rejects_authority_and_receipt_gaps(tmp_path: Path) -> None:
    payload = _load_json(INVOICE_DOMAIN_PACK_FIXTURE)
    payload["governance"]["core_authority_ceiling"] = False
    payload["actions"]["allowed"].append("execute_payment")
    payload["tests"]["required"].remove("false_success_test")
    payload["receipts"]["required_for"].remove("blocked_action")
    mutated_path = tmp_path / "unsafe_invoice_domain_pack.json"
    mutated_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    errors = validate_domain_pack(mutated_path)

    assert any(error == "governance.core_authority_ceiling_must_be_true" for error in errors)
    assert any(error == "actions.allowed_escalates_core_authority:execute_payment" for error in errors)
    assert any(error == "tests.required_missing:false_success_test" for error in errors)
    assert any(error == "receipts.required_for_missing:blocked_action" for error in errors)


def test_universal_domain_ops_input_schema_accepts_bounded_requests() -> None:
    schema = _load_schema(UNIVERSAL_DOMAIN_OPS_SCHEMA_DIR / "domain_operation.input.schema.json")
    payloads = _representative_universal_domain_ops_input_payloads()

    assert set(payloads) == {entry.capability_id for entry in _universal_domain_ops_entries()}
    for capability_id, payload in payloads.items():
        assert _validate_schema_instance(schema, payload) == []
        assert payload["capability_id"] == capability_id
        assert payload["external_effect_requested"] is False


def test_universal_domain_ops_input_schema_rejects_external_effects() -> None:
    schema = _load_schema(UNIVERSAL_DOMAIN_OPS_SCHEMA_DIR / "domain_operation.input.schema.json")
    payload = deepcopy(_representative_universal_domain_ops_input_payloads()["universal_domain_ops.episode.simulate"])
    external_effect_payload = deepcopy(payload)
    missing_evidence_payload = deepcopy(payload)
    unknown_capability_payload = deepcopy(payload)

    external_effect_payload["external_effect_requested"] = True
    missing_evidence_payload["evidence_refs"] = []
    unknown_capability_payload["capability_id"] = "universal_domain_ops.execute.live_action"

    assert _validate_schema_instance(schema, external_effect_payload)
    assert _validate_schema_instance(schema, missing_evidence_payload)
    assert _validate_schema_instance(schema, unknown_capability_payload)


def test_universal_domain_ops_output_schema_accepts_bounded_receipts() -> None:
    schema = _load_schema(UNIVERSAL_DOMAIN_OPS_SCHEMA_DIR / "domain_operation.output.schema.json")
    payloads = _representative_universal_domain_ops_output_payloads()

    assert set(payloads) == {entry.capability_id for entry in _universal_domain_ops_entries()}
    for capability_id, payload in payloads.items():
        assert _validate_schema_instance(schema, payload) == []
        assert payload["capability_id"] == capability_id
        assert payload["metadata"]["external_effect_executed"] is False
        assert payload["metadata"]["claim_bounded_by_state"] is True


def test_universal_domain_ops_output_schema_rejects_overclaims() -> None:
    schema = _load_schema(UNIVERSAL_DOMAIN_OPS_SCHEMA_DIR / "domain_operation.output.schema.json")
    payload = deepcopy(_representative_universal_domain_ops_output_payloads()["universal_domain_ops.claim.bound"])
    generic_success_payload = deepcopy(payload)
    external_effect_payload = deepcopy(payload)
    empty_claim_payload = deepcopy(payload)

    generic_success_payload["outcome"] = "success"
    external_effect_payload["metadata"]["external_effect_executed"] = True
    empty_claim_payload["allowed_claims"] = []

    assert _validate_schema_instance(schema, generic_success_payload)
    assert _validate_schema_instance(schema, external_effect_payload)
    assert _validate_schema_instance(schema, empty_claim_payload)


def test_universal_domain_ops_capsule_references_exact_pack_capabilities() -> None:
    capsule = DomainCapsule.from_mapping(_load_json(UNIVERSAL_DOMAIN_OPS_CAPSULE_PATH))
    capabilities = _universal_domain_ops_entries()
    capability_ids = tuple(entry.capability_id for entry in capabilities)

    assert capsule.domain == "universal_domain_ops"
    assert capsule.certification_status.value == "certified"
    assert capsule.capability_refs == capability_ids
    assert len(set(capability_ids)) == len(capability_ids)


def test_universal_domain_ops_pack_installs_through_explicit_capability_fabric() -> None:
    capsule = load_universal_domain_ops_domain_capsule()
    entries = load_universal_domain_ops_capability_entries()
    gate = _universal_domain_ops_gate(require_production_ready=False)
    read_model = gate.read_model()
    lint_decision = gate.admit(command_id="cmd-udop-lint", intent_name="universal_domain_ops.pack.lint")
    simulate_decision = gate.admit(command_id="cmd-udop-sim", intent_name="universal_domain_ops.episode.simulate")
    raw_action_decision = gate.admit(command_id="cmd-udop-raw", intent_name="universal_domain_ops.execute.live_action")

    assert capsule.domain == "universal_domain_ops"
    assert len(entries) == 4
    assert read_model["capsule_count"] == 1
    assert read_model["capability_count"] == 4
    assert read_model["domains"] == ({"domain": "universal_domain_ops", "capability_ids": tuple(sorted(capsule.capability_refs))},)
    assert lint_decision.status.value == "accepted"
    assert simulate_decision.status.value == "accepted"
    assert raw_action_decision.status.value == "rejected"


def test_universal_domain_ops_governed_records_are_local_and_read_only() -> None:
    gate = _universal_domain_ops_gate(require_production_ready=False)
    read_model = gate.read_model()
    governed = {item["capability_id"]: item for item in read_model["governed_capability_records"]}

    assert set(governed) == {entry.capability_id for entry in _universal_domain_ops_entries()}
    assert all(record["read_only"] is True for record in governed.values())
    assert all(record["world_mutating"] is False for record in governed.values())
    assert all(record["requires_approval"] is False for record in governed.values())
    assert all(record["requires_sandbox"] is False for record in governed.values())
    assert governed["universal_domain_ops.claim.bound"]["forbidden_effects"] == [
        "external_action_executed",
        "claim_beyond_verified_state",
        "false_success_claim_emitted",
    ]


def test_universal_domain_ops_pack_blocks_production_ready_overclaim() -> None:
    gate = _universal_domain_ops_gate(require_production_ready=True)
    decision = gate.admit(command_id="cmd-udop-prod", intent_name="universal_domain_ops.registry.validate")

    assert decision.status.value == "rejected"
    assert decision.capability_id == "universal_domain_ops.registry.validate"
    assert "capability is not production-ready" in decision.reason
    assert "sandbox_receipt_missing" in decision.reason


def _universal_domain_ops_gate(*, require_production_ready: bool):
    return build_universal_domain_ops_capability_admission_gate(
        clock=lambda: "2026-06-30T00:00:00+00:00",
        require_production_ready=require_production_ready,
    )


def _universal_domain_ops_entries() -> tuple[CapabilityRegistryEntry, ...]:
    return tuple(
        CapabilityRegistryEntry.from_mapping(item)
        for item in _load_json(UNIVERSAL_DOMAIN_OPS_CAPABILITY_PACK_PATH)["capabilities"]
    )


def _representative_universal_domain_ops_input_payloads() -> dict[str, dict]:
    base = {
        "request_id": "req-udop",
        "episode_id": "episode-udop",
        "domain_pack_refs": ["tests/fixtures/universal_domain_ops/invoice_domain_pack.json"],
        "request_summary": "Validate and simulate invoice domain pack gates",
        "workflow_state": "approval_drafted",
        "candidate_actions": ["prepare_approval_draft", "record_receipt"],
        "claim_text": "Approval draft prepared. Approval has not been granted.",
        "evidence_refs": ["proof://udop/invoice-pack"],
        "risk_class": "R1",
        "external_effect_requested": False,
        "metadata": {"fixture": "universal_domain_ops_capability_pack"},
    }
    return {
        entry.capability_id: {**base, "capability_id": entry.capability_id}
        for entry in _universal_domain_ops_entries()
    }


def _representative_universal_domain_ops_output_payloads() -> dict[str, dict]:
    base = {
        "request_id": "req-udop",
        "episode_id": "episode-udop",
        "outcome": "SolvedVerified",
        "proof_state": "Pass",
        "verified_state": "claim_bounded",
        "allowed_claims": ["Approval draft prepared. Approval has not been granted."],
        "blocked_actions": ["claim_invoice_approved", "claim_invoice_paid"],
        "receipts": ["receipt://udop/claim-boundary"],
        "evidence_refs": ["proof://udop/invoice-pack"],
        "next_actions": ["collect approval evidence before approval claim"],
        "metadata": {
            "fixture": "universal_domain_ops_capability_pack",
            "external_effect_executed": False,
            "claim_bounded_by_state": True,
        },
    }
    states_by_capability = {
        "universal_domain_ops.registry.validate": "pack_validated",
        "universal_domain_ops.pack.lint": "lint_passed",
        "universal_domain_ops.episode.simulate": "simulation_passed",
        "universal_domain_ops.claim.bound": "claim_bounded",
    }
    return {
        entry.capability_id: {
            **base,
            "capability_id": entry.capability_id,
            "verified_state": states_by_capability[entry.capability_id],
        }
        for entry in _universal_domain_ops_entries()
    }


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
