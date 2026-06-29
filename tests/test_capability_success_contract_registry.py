"""Tests for capability proof-of-success contract registry.

Purpose: prove success contracts compile from governed capability entries and
    block false-success claims.
Governance scope: capability success predicates, evidence obligations,
    authority gates, invariant checks, and receipt integrity.
Dependencies: gateway capability fabric fixtures, success-contract registry,
    and registry validator script.
Invariants:
  - Every loaded capability has exactly one success contract.
  - Required capability evidence remains mandatory success proof.
  - High-risk effect claims cannot become clean success without independent
    evidence, authority, causality, invariant, and receipt gates.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
MCOI_PATH = ROOT / "mcoi"
if str(MCOI_PATH) not in sys.path:
    sys.path.insert(0, str(MCOI_PATH))

from gateway.capability_fabric import (  # noqa: E402
    load_default_capability_entries,
    load_software_dev_capability_entries,
)
from mcoi_runtime.contracts.capability_success_contract import (  # noqa: E402
    SuccessProofLevel,
)
from mcoi_runtime.core.capability_success_contract_registry import (  # noqa: E402
    CapabilitySuccessContractRegistry,
    compile_capability_success_contract,
    validate_contract_against_entry,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError  # noqa: E402
from scripts import validate_capability_success_contract_registry as validator  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


REGISTRY_PATH = ROOT / "governance" / "capability_success_contract_registry.foundation.json"
SCHEMA_PATH = ROOT / "schemas" / "capability_success_contract_registry.schema.json"


def _entries() -> tuple:
    return (*load_default_capability_entries(), *load_software_dev_capability_entries())


def _entries_by_id() -> dict[str, object]:
    return {entry.capability_id: entry for entry in _entries()}


def _registry_fixture() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _registry_with_overrides() -> CapabilitySuccessContractRegistry:
    return CapabilitySuccessContractRegistry.from_capability_entries(
        _entries(),
        overrides=tuple(_registry_fixture()["contract_overrides"]),
    )


def test_generated_registry_covers_all_loaded_capabilities() -> None:
    entries = _entries()
    registry = CapabilitySuccessContractRegistry.from_capability_entries(entries)
    read_model = registry.read_model()

    assert len(entries) >= 90
    assert registry.contract_count == len(entries)
    assert set(read_model["capability_ids"]) == {entry.capability_id for entry in entries}
    assert read_model["contract_count"] == len(entries)
    assert read_model["high_risk_independent_contract_count"] >= 1


def test_hardened_financial_override_requires_p5_causal_closure() -> None:
    registry = _registry_with_overrides()
    payment = registry.get_contract("financial.send_payment")

    assert payment.proof_level_required is SuccessProofLevel.P5
    assert payment.independent_evidence_required is True
    assert payment.freshness.max_age_seconds == 60
    assert payment.freshness.durability_window_seconds == 300
    assert {"tx_id", "ledger_hash", "payment_state"} <= set(payment.mandatory_evidence_fields)
    assert payment.verdict_policy.allow_pending_success is False
    assert payment.receipt_requirements.hash_chain_required is True


def test_compiled_contract_preserves_entry_effects_and_evidence() -> None:
    entries = _entries_by_id()
    email_entry = entries["email.send.with_approval"]
    contract = compile_capability_success_contract(email_entry)
    errors = validate_contract_against_entry(contract, email_entry)

    assert errors == ()
    assert set(email_entry.effect_model.expected_effects) <= set(contract.expected_delta.required_changes)
    assert set(email_entry.effect_model.forbidden_effects) <= set(contract.expected_delta.forbidden_changes)
    assert set(email_entry.evidence_model.required_evidence) <= set(contract.mandatory_evidence_fields)
    assert contract.acceptance_predicate.requires_all_success_gates is True
    assert contract.authority.block_on_unknown_authority is True


def test_registry_rejects_duplicate_capability_contracts() -> None:
    entry = _entries_by_id()["computer.code.patch"]
    contract = compile_capability_success_contract(entry)

    with pytest.raises(RuntimeCoreInvariantError, match="duplicate contract ids"):
        CapabilitySuccessContractRegistry((contract, contract))

    assert contract.capability_id == "computer.code.patch"
    assert contract.receipt_requirements.residual_gaps_required is True
    assert "patch_id" in contract.mandatory_evidence_fields


def test_registry_fixture_is_schema_valid_and_validator_clean() -> None:
    record = _registry_fixture()
    schema = _load_schema(SCHEMA_PATH)
    report = validator.build_validation_report(REGISTRY_PATH)

    assert _validate_schema_instance(schema, record) == []
    assert report["valid"] is True
    assert report["loaded_capability_count"] == len(_entries())
    assert report["override_contract_count"] == 4
    assert report["check_count"] == 8
    assert report["error_count"] == 0


def test_validator_rejects_override_missing_mandatory_capability_evidence() -> None:
    record = copy.deepcopy(_registry_fixture())
    payment = record["contract_overrides"][0]
    payment["proof_obligations"][0]["evidence_fields"] = ["payment_state"]

    errors = validator.validate_registry_record(record)

    assert errors
    assert any("financial.send_payment" in error for error in errors)
    assert any("mandatory proof obligations omit capability required evidence" in error for error in errors)
    assert payment["capability_id"] == "financial.send_payment"
    assert "tx_id" not in payment["proof_obligations"][0]["evidence_fields"]


def test_validator_rejects_pending_success_overclaim() -> None:
    record = copy.deepcopy(_registry_fixture())
    email = record["contract_overrides"][1]
    email["verdict_policy"]["allow_pending_success"] = True

    errors = validator.validate_registry_record(record)

    assert errors
    assert any("email.send.with_approval" in error for error in errors)
    assert any("permits pending state to be called success" in error for error in errors)
    assert email["verdict_policy"]["allow_pending_success"] is True
    assert email["capability_id"] == "email.send.with_approval"
