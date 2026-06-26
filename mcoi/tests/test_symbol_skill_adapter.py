"""Purpose: verify Foundation Mode UniversalSymbol skill projection.
Governance scope: digest-only symbol adapter tests for receipts, traces, and
component entries.
Dependencies: jsonschema, software change receipt contracts, and the symbol
skill adapter.
Invariants:
  - Adapter output satisfies the UniversalSymbol schema.
  - Projection remains read-only and denies runtime authority.
  - Raw payload or secret retention fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from mcoi_runtime.contracts.software_dev_loop import (
    SoftwareChangeReceipt,
    SoftwareChangeReceiptStage,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.symbol_skill_adapter import (
    AUTHORITY_DENIAL_FIELDS,
    SymbolAdapterSurface,
    universal_symbol_from_record,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
NOW = "2026-06-18T00:00:00+00:00"


def _validator() -> Draft202012Validator:
    schema = json.loads((REPO_ROOT / "schemas" / "universal_symbol.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _assert_schema_valid(symbol: dict[str, object]) -> None:
    _validator().validate(symbol)


def _assert_foundation_authority_denied(symbol: dict[str, object]) -> None:
    boundary = symbol["symbol_authority_boundary"]
    assert isinstance(boundary, dict)
    assert set(boundary) == set(AUTHORITY_DENIAL_FIELDS)
    assert all(value is False for value in boundary.values())


def test_software_change_receipt_projects_to_schema_valid_symbol() -> None:
    receipt = SoftwareChangeReceipt(
        receipt_id="receipt-symbol-adapter-0001",
        request_id="request-symbol-adapter-0001",
        stage=SoftwareChangeReceiptStage.PLAN_VALIDATED,
        cause="plan validated",
        outcome="accepted",
        target_refs=("file://main.py",),
        constraint_refs=("constraint://software-change-lifecycle",),
        evidence_refs=("receipt://software-change/plan-validated",),
        created_at=NOW,
        metadata={"plan_id": "plan-symbol-adapter"},
    )

    symbol = universal_symbol_from_record(
        receipt,
        SymbolAdapterSurface.SOFTWARE_DEV_RECEIPT,
        generated_at=NOW,
    )

    _assert_schema_valid(symbol)
    _assert_foundation_authority_denied(symbol)
    assert symbol["symbol_identity"]["symbol_kind"] == "receipt"
    assert symbol["symbol_governance"]["governance_mode"] == "foundation"
    assert symbol["symbol_proof"]["proof_state"] == "awaiting_evidence"
    assert symbol["symbol_causality"]["pre_state_ref"] == "state://software_dev_receipt/receipt-symbol-adapter-0001/pre"
    assert "receipt://software-change/plan-validated" in symbol["evidence_refs"]


def test_teamops_receipt_projection_is_ref_only() -> None:
    teamops_receipt = {
        "receipt_id": "teamops-shared-inbox-provider-observation-receipt-0000000000000001",
        "workflow_id": "team_ops.shared_inbox_triage",
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "provider_receipt_ref": "provider://gmail/search/receipt-1",
        "raw_provider_payload_serialized": False,
        "no_secret_values_serialized": True,
        "private_message_subject": "do not include this raw subject",
    }

    symbol = universal_symbol_from_record(
        teamops_receipt,
        SymbolAdapterSurface.TEAMOPS_RECEIPT,
        generated_at=NOW,
    )
    encoded = json.dumps(symbol, sort_keys=True)

    _assert_schema_valid(symbol)
    _assert_foundation_authority_denied(symbol)
    assert symbol["symbol_identity"]["domain"] == "team_ops"
    assert "provider://gmail/search/receipt-1" in symbol["evidence_refs"]
    assert "do not include this raw subject" not in encoded
    assert "private_message_subject" not in encoded


def test_sccml_trace_witness_projects_trace_state_refs() -> None:
    witness = {
        "witness_id": "sccml-trace-witness-0001",
        "trace_scope": {
            "instruction_trace_ref": "trace://sccml/instruction/0001",
            "pre_state_hash_ref": "state://sccml/pre/sha256-0001",
            "post_state_hash_ref": "state://sccml/post/sha256-0001",
            "proof_ref": "proof://sccml/0001",
            "unsupported_op_gap_ref": "gap://sccml/unsupported-op",
        },
        "evidence_refs": ("witness://sccml/trace-adapter/0001",),
    }

    symbol = universal_symbol_from_record(
        witness,
        SymbolAdapterSurface.SCCML_TRACE,
        generated_at=NOW,
    )

    _assert_schema_valid(symbol)
    _assert_foundation_authority_denied(symbol)
    assert symbol["symbol_identity"]["symbol_kind"] == "trace"
    assert symbol["symbol_causality"]["pre_state_ref"] == "state://sccml/pre/sha256-0001"
    assert symbol["symbol_causality"]["post_state_ref"] == "state://sccml/post/sha256-0001"
    assert symbol["symbol_causality"]["causal_trace_ref"] == "trace://sccml/instruction/0001"
    assert "proof://sccml/0001" in symbol["evidence_refs"]


def test_component_registry_entry_projects_component_symbol() -> None:
    component = {
        "component_id": "component-symbol-adapter-0001",
        "route_family": "symbol",
        "name": "symbol adapter",
        "evidence_refs": ("component://registry/component-symbol-adapter-0001",),
    }

    symbol = universal_symbol_from_record(
        component,
        SymbolAdapterSurface.COMPONENT_REGISTRY_ENTRY,
        generated_at=NOW,
    )

    _assert_schema_valid(symbol)
    _assert_foundation_authority_denied(symbol)
    assert symbol["symbol_identity"]["symbol_kind"] == "component"
    assert symbol["symbol_identity"]["domain"] == "component"
    assert symbol["symbol_lineage"]["origin_ref"] == "component_registry_entry://component-symbol-adapter-0001"
    assert symbol["contract_summary"]["symbolizable_surface_count"] == 16


def test_projection_rejects_raw_payload_storage() -> None:
    record = {
        "receipt_id": "receipt-raw-payload-0001",
        "evidence_refs": ("receipt://raw-payload/0001",),
        "raw_private_payload_stored": True,
    }

    with pytest.raises(RuntimeCoreInvariantError, match="digest-only symbol projection") as exc_info:
        universal_symbol_from_record(
            record,
            SymbolAdapterSurface.GENERIC_RECEIPT,
            generated_at=NOW,
        )

    assert "raw_private_payload_stored" in str(exc_info.value)
    assert "receipt-raw-payload-0001" not in str(exc_info.value)
    assert "digest-only" in str(exc_info.value)


def test_projection_symbol_id_is_deterministic() -> None:
    record = {
        "receipt_id": "receipt-deterministic-0001",
        "evidence_refs": ("receipt://deterministic/0001",),
    }

    first = universal_symbol_from_record(record, SymbolAdapterSurface.GENERIC_RECEIPT, generated_at=NOW)
    second = universal_symbol_from_record(record, SymbolAdapterSurface.GENERIC_RECEIPT, generated_at=NOW)

    assert first["symbol_id"] == second["symbol_id"]
    assert first["symbol_version"] == "universal_symbol.v1"
    assert first["contract_summary"]["authority_denial_count"] == 9


def test_projection_normalizes_refs_and_preserves_relation_constraints() -> None:
    record = {
        "receipt_id": "receipt-ref-normalization-0001",
        "evidence_refs": (" receipt://normalized/0001 ",),
        "target_refs": (" target://normalized/0001 ",),
        "constraint_refs": (" policy://normalized/0001 ",),
    }

    symbol = universal_symbol_from_record(
        record,
        SymbolAdapterSurface.GENERIC_RECEIPT,
        generated_at=NOW,
    )

    assert "receipt://normalized/0001" in symbol["evidence_refs"]
    assert " receipt://normalized/0001 " not in symbol["evidence_refs"]
    assert "target://normalized/0001" in symbol["symbol_relations"]["downstream_refs"]
    assert " target://normalized/0001 " not in symbol["symbol_relations"]["downstream_refs"]
    assert "policy://normalized/0001" in symbol["symbol_governance"]["policy_refs"]
    assert " policy://normalized/0001 " not in symbol["symbol_governance"]["policy_refs"]

    duplicate_record = {
        "receipt_id": "receipt-ref-normalization-0002",
        "evidence_refs": ("receipt://duplicate/0001", " receipt://duplicate/0001 "),
    }

    with pytest.raises(RuntimeCoreInvariantError, match="evidence_refs must not contain duplicate refs"):
        universal_symbol_from_record(
            duplicate_record,
            SymbolAdapterSurface.GENERIC_RECEIPT,
            generated_at=NOW,
        )
