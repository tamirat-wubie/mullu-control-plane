"""Purpose: verify governed action contract validation and passport projection.
Governance scope: capability passport authority, evidence, isolation, recovery,
    cost, and deterministic serialization.
Dependencies: governed action and governed capability fabric contracts.
Invariants:
  - Capability passports preserve execution-facing registry obligations.
  - Passport costs are finite and non-negative.
  - Malformed passport lists fail closed before dispatch admission.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.contracts.governed_action import (
    AuthorityProofRecord,
    CapabilityPassportRecord,
    build_capability_passport,
)
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "integration" / "governed_capability_fabric" / "fixtures"


def _passport(**overrides: object) -> CapabilityPassportRecord:
    values = {
        "capability_id": "crm.update_customer_address",
        "version": "1.0.0",
        "passport_hash": "capability-passport-fixture",
        "risk_level": "high",
        "input_schema_ref": "schemas/customer_ops/update_customer_address.input.schema.json",
        "output_schema_ref": "schemas/customer_ops/update_customer_address.output.schema.json",
        "required_roles": ("customer_ops_manager",),
        "approval_chain": ("customer_ops_manager",),
        "separation_of_duty": True,
        "evidence_required": ("crm_update_receipt", "before_after_record_hash"),
        "terminal_certificate_required": True,
        "expected_effects": ("customer_address_updated", "crm_audit_record_created"),
        "forbidden_effects": ("billing_account_modified",),
        "execution_plane": "connector_worker",
        "network_allowlist": ("crm.internal.mullusi.com",),
        "secret_scope": "tenant:customer_ops:crm",
        "rollback_capability": "crm.restore_customer_address",
        "compensation_capability": "customer_ops.notify_address_update_review",
        "review_required_on_failure": True,
        "budget_class": "customer_ops_mutation",
        "max_estimated_cost": 0.25,
        "world_mutating": True,
        "reconciliation_required": True,
    }
    values.update(overrides)
    return CapabilityPassportRecord(**values)  # type: ignore[arg-type]


def _registry_entry() -> CapabilityRegistryEntry:
    with open(FIXTURE_DIR / "capability_registry_entry.json", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert isinstance(payload, dict)
    return CapabilityRegistryEntry.from_mapping(payload)


def test_capability_passport_preserves_governed_execution_fields() -> None:
    passport = _passport()

    assert passport.approval_chain == ("customer_ops_manager",)
    assert passport.network_allowlist == ("crm.internal.mullusi.com",)
    assert passport.secret_scope == "tenant:customer_ops:crm"
    assert passport.budget_class == "customer_ops_mutation"
    assert passport.max_estimated_cost == 0.25


def test_capability_passport_rejects_non_finite_cost() -> None:
    with pytest.raises(ValueError, match=r"must be finite") as excinfo:
        _passport(max_estimated_cost=float("inf"))

    assert "Infinity" not in str(excinfo.value)
    assert "capability-passport-fixture" not in str(excinfo.value)
    assert "must be finite" in str(excinfo.value)


def test_capability_passport_rejects_malformed_optional_tuple_values() -> None:
    with pytest.raises(ValueError, match=r"must be a non-empty string") as excinfo:
        _passport(approval_chain=(" ",))

    assert "customer_ops_manager" not in str(excinfo.value)
    assert "crm.internal.mullusi.com" not in str(excinfo.value)
    assert "non-empty string" in str(excinfo.value)


def test_capability_passport_rejects_scalar_optional_tuple_values() -> None:
    with pytest.raises(ValueError, match=r"must be an array") as excinfo:
        _passport(network_allowlist="crm.internal.mullusi.com")

    assert "crm.internal.mullusi.com" not in str(excinfo.value)
    assert "capability-passport-fixture" not in str(excinfo.value)
    assert "must be an array" in str(excinfo.value)


def test_build_capability_passport_projects_registry_obligations() -> None:
    passport = build_capability_passport(
        _registry_entry(),
        passport_hash="capability-passport-fixture",
    )

    assert passport.input_schema_ref.endswith(".input.schema.json")
    assert passport.output_schema_ref.endswith(".output.schema.json")
    assert passport.terminal_certificate_required is True
    assert passport.review_required_on_failure is True
    assert passport.reconciliation_required is True


def test_capability_passport_json_includes_hardened_fields() -> None:
    payload = _passport().to_json_dict()

    assert payload["approval_chain"] == ["customer_ops_manager"]
    assert payload["network_allowlist"] == ["crm.internal.mullusi.com"]
    assert payload["max_estimated_cost"] == 0.25
    assert payload["terminal_certificate_required"] is True
    assert payload["review_required_on_failure"] is True


def test_authority_proof_accepts_approval_chain_and_separation_of_duty() -> None:
    proof = AuthorityProofRecord(
        actor_id="actor-1",
        tenant_id="tenant-1",
        required_roles=("customer_ops_manager",),
        actor_roles=("customer_ops_manager",),
        approval_chain=("customer_ops_manager",),
        approval_refs=("approval-1",),
        approval_actor_ids=("manager-1",),
        separation_of_duty=True,
    )

    assert proof.approval_chain == ("customer_ops_manager",)
    assert proof.approval_refs == ("approval-1",)
    assert proof.approval_actor_ids == ("manager-1",)
    assert proof.separation_of_duty is True


def test_authority_proof_rejects_missing_approval_refs() -> None:
    with pytest.raises(ValueError, match=r"missing approval refs") as excinfo:
        AuthorityProofRecord(
            actor_id="actor-1",
            tenant_id="tenant-1",
            required_roles=("customer_ops_manager",),
            actor_roles=("customer_ops_manager",),
            approval_chain=("customer_ops_manager",),
        )

    assert "customer_ops_manager" not in str(excinfo.value)
    assert "actor-1" not in str(excinfo.value)
    assert "missing approval refs" in str(excinfo.value)


def test_authority_proof_rejects_scalar_approval_refs() -> None:
    with pytest.raises(ValueError, match=r"must be an array") as excinfo:
        AuthorityProofRecord(
            actor_id="actor-1",
            tenant_id="tenant-1",
            required_roles=("customer_ops_manager",),
            actor_roles=("customer_ops_manager",),
            approval_chain=("customer_ops_manager",),
            approval_refs="approval-1",  # type: ignore[arg-type]
        )

    assert "approval-1" not in str(excinfo.value)
    assert "actor-1" not in str(excinfo.value)
    assert "must be an array" in str(excinfo.value)


def test_authority_proof_rejects_self_approval() -> None:
    with pytest.raises(ValueError, match=r"forbids self approval") as excinfo:
        AuthorityProofRecord(
            actor_id="actor-1",
            tenant_id="tenant-1",
            required_roles=("customer_ops_manager",),
            actor_roles=("customer_ops_manager",),
            approval_chain=("customer_ops_manager",),
            approval_refs=("approval-1",),
            approval_actor_ids=("actor-1",),
            separation_of_duty=True,
        )

    assert "approval-1" not in str(excinfo.value)
    assert "actor-1" not in str(excinfo.value)
    assert "forbids self approval" in str(excinfo.value)
