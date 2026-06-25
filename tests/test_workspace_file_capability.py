"""Purpose: verify canonical governed workspace file operation preflight.
Governance scope: workspace read, patch, destructive mutation, protected path,
    schema, capability-pack, and dispatcher preflight boundaries.
Dependencies: pytest, schema validator helper, capability dispatcher, and
    workspace file contracts.
Invariants:
  - Preflight never grants raw destructive file authority.
  - Protected governance paths require elevated authority.
  - Read-only preflight cannot mutate workspace state.
  - Dispatcher output validates against the strict output schema.
"""

from __future__ import annotations

import json
from pathlib import Path

from gateway.capability_dispatch import (
    CapabilityDispatcher,
    CapabilityIntent,
    register_computer_capabilities,
)
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry
from mcoi_runtime.contracts.workspace_file_capability import (
    WorkspaceFileDecision,
    WorkspaceFileOperation,
    WorkspaceFilePreflightRequest,
    WorkspaceFileRiskLevel,
    workspace_file_capability_levels,
)
from mcoi_runtime.core.governed_workspace_io import preflight_workspace_file_operation
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
COMPUTER_PACK = ROOT / "capabilities" / "computer" / "capability_pack.json"
INPUT_SCHEMA = ROOT / "schemas" / "computer" / "workspace_file_preflight.input.schema.json"
OUTPUT_SCHEMA = ROOT / "schemas" / "computer" / "workspace_file_preflight.output.schema.json"
CAPABILITY_SCHEMA = ROOT / "schemas" / "capability_registry_entry.schema.json"


def _request(**overrides: object) -> WorkspaceFilePreflightRequest:
    values = {
        "request_id": "req-workspace-file",
        "operation": WorkspaceFileOperation.READ,
        "target_path": "src/app.py",
        "actor_id": "developer:local",
        "purpose": "inspect source file",
        "metadata": {"fixture": "workspace_file_capability"},
    }
    values.update(overrides)
    return WorkspaceFilePreflightRequest(**values)


def test_workspace_file_levels_are_canonical_and_json_safe() -> None:
    levels = workspace_file_capability_levels()

    assert len(levels) == 5
    assert levels[0]["level"] == "level_0_readonly_inspect"
    assert "delete" in levels[3]["operations"]
    assert "governance_artifact_mutation" in levels[4]["operations"]


def test_preflight_allows_read_without_mutation_authority() -> None:
    result = preflight_workspace_file_operation(_request())

    assert result.decision is WorkspaceFileDecision.ALLOW
    assert result.risk_level is WorkspaceFileRiskLevel.LEVEL_0_READONLY_INSPECT
    assert result.world_mutating is False
    assert result.approval_required is False
    assert result.rollback_required is False
    assert result.allowed_capability_ids == ("computer.filesystem.observe",)


def test_preflight_routes_patch_to_guarded_capabilities() -> None:
    result = preflight_workspace_file_operation(
        _request(operation="apply_patch", purpose="repair test", target_path="tests/test_app.py")
    )

    assert result.decision is WorkspaceFileDecision.ALLOW
    assert result.autonomy_mode == "autonomous_local"
    assert result.risk_level is WorkspaceFileRiskLevel.LEVEL_2_EDIT_EXISTING_FILE
    assert result.world_mutating is True
    assert result.approval_required is False
    assert result.rollback_required is True
    assert "computer.code.patch" in result.allowed_capability_ids
    assert "software_dev.change.run" in result.allowed_capability_ids
    assert "before_hash" in result.required_evidence
    assert "after_hash" in result.required_evidence


def test_preflight_approval_required_mode_gates_reversible_local_patch() -> None:
    result = preflight_workspace_file_operation(
        _request(
            operation="apply_patch",
            purpose="repair test",
            target_path="tests/test_app.py",
            autonomy_mode="approval_required",
        )
    )

    assert result.decision is WorkspaceFileDecision.REQUIRE_APPROVAL
    assert result.autonomy_mode == "approval_required"
    assert result.risk_level is WorkspaceFileRiskLevel.LEVEL_2_EDIT_EXISTING_FILE
    assert result.approval_required is True
    assert result.allowed_capability_ids == ()
    assert "approval_ref" in result.required_evidence
    assert "autonomy_mode:approval_required" in result.reasons


def test_preflight_requires_approval_for_protected_governance_paths() -> None:
    result = preflight_workspace_file_operation(
        _request(operation="edit", target_path=".github/workflows/ci.yml", purpose="change CI")
    )

    assert result.decision is WorkspaceFileDecision.REQUIRE_APPROVAL
    assert result.risk_level is WorkspaceFileRiskLevel.LEVEL_4_GOVERNANCE_ARTIFACT_MUTATION
    assert result.protected_path is True
    assert result.approval_required is True
    assert result.allowed_capability_ids == ()
    assert "approval_ref" in result.required_evidence


def test_preflight_can_run_with_explicit_empty_path_policy() -> None:
    result = preflight_workspace_file_operation(
        _request(operation="edit", target_path=".github/workflows/ci.yml", purpose="isolated policy test"),
        protected_paths=None,
    )

    assert result.decision is WorkspaceFileDecision.ALLOW
    assert result.risk_level is WorkspaceFileRiskLevel.LEVEL_2_EDIT_EXISTING_FILE
    assert result.protected_path is False
    assert result.allowed_capability_ids == ("computer.code.patch", "software_dev.change.run")


def test_preflight_keeps_destructive_operations_proposal_only() -> None:
    result = preflight_workspace_file_operation(
        _request(operation="delete", target_path="src/old.py", purpose="remove obsolete module")
    )

    assert result.decision is WorkspaceFileDecision.PROPOSAL_ONLY
    assert result.risk_level is WorkspaceFileRiskLevel.LEVEL_3_DESTRUCTIVE_MUTATION
    assert result.approval_required is True
    assert result.rollback_required is True
    assert result.allowed_capability_ids == ()
    assert "destructive_mutation_executed_by_preflight" in result.forbidden_effects


def test_preflight_blocks_unanchorable_paths() -> None:
    result = preflight_workspace_file_operation(
        _request(operation="read", target_path="../secrets.env", purpose="bad path")
    )

    assert result.decision is WorkspaceFileDecision.BLOCK
    assert result.protected_path is True
    assert result.allowed_capability_ids == ()
    assert any("workspace-relative" in reason for reason in result.reasons)


def test_workspace_file_preflight_schemas_accept_representative_payloads() -> None:
    input_payload = {
        "capability_id": "computer.workspace_file.preflight",
        "request_id": "req-workspace-file",
        "operation": "apply_patch",
        "target_path": "tests/test_app.py",
        "actor_id": "developer:local",
        "purpose": "repair test",
        "autonomy_mode": "autonomous_local",
        "metadata": {"fixture": "workspace_file_capability"},
    }
    output_payload = preflight_workspace_file_operation(
        _request(operation="apply_patch", target_path="tests/test_app.py", purpose="repair test")
    ).to_json_dict()

    assert _validate_schema_instance(_load_schema(INPUT_SCHEMA), input_payload) == []
    assert _validate_schema_instance(_load_schema(OUTPUT_SCHEMA), output_payload) == []
    assert output_payload["autonomy_mode"] == "autonomous_local"
    assert output_payload["metadata"]["preflight_is_not_execution_authority"] is True


def test_workspace_file_preflight_schema_rejects_path_escape() -> None:
    payload = {
        "capability_id": "computer.workspace_file.preflight",
        "request_id": "req-workspace-file",
        "operation": "read",
        "target_path": "../secrets.env",
        "actor_id": "developer:local",
        "purpose": "bad path",
        "metadata": {},
    }

    assert _validate_schema_instance(_load_schema(INPUT_SCHEMA), payload)


def test_workspace_file_preflight_schema_rejects_unknown_autonomy_mode() -> None:
    payload = {
        "capability_id": "computer.workspace_file.preflight",
        "request_id": "req-workspace-file",
        "operation": "apply_patch",
        "target_path": "tests/test_app.py",
        "actor_id": "developer:local",
        "purpose": "repair test",
        "autonomy_mode": "unguarded",
        "metadata": {},
    }

    assert _validate_schema_instance(_load_schema(INPUT_SCHEMA), payload)


def test_computer_pack_declares_canonical_preflight_capability() -> None:
    pack = json.loads(COMPUTER_PACK.read_text(encoding="utf-8"))
    entries = {
        item["capability_id"]: item
        for item in pack["capabilities"]
    }
    entry = entries["computer.workspace_file.preflight"]

    assert _validate_schema_instance(_load_schema(CAPABILITY_SCHEMA), entry) == []
    assert CapabilityRegistryEntry.from_mapping(entry).capability_id == "computer.workspace_file.preflight"
    assert entry["extensions"]["governed_record"]["read_only"] is True
    assert entry["extensions"]["governed_record"]["world_mutating"] is False
    assert "autonomy_mode" in entry["evidence_model"]["required_evidence"]
    assert "workspace_file_written" in entry["effect_model"]["forbidden_effects"]
    assert "delete" in entry["extensions"]["governed_record"]["canonical_workspace_operations"]
    assert "autonomous_local" in entry["extensions"]["governed_record"]["accepted_autonomy_modes"]


def test_dispatcher_exposes_preflight_without_file_executor() -> None:
    dispatcher = CapabilityDispatcher()
    register_computer_capabilities(dispatcher)

    result = dispatcher.dispatch(
        CapabilityIntent(
            domain="computer",
            action="workspace_file.preflight",
            params={
                "operation": "delete",
                "target_path": "src/old.py",
                "purpose": "remove obsolete module",
            },
        ),
        tenant_id="tenant-a",
        identity_id="developer:local",
        command_id="cmd-workspace-preflight",
    )

    assert result is not None
    assert result["capability_id"] == "computer.workspace_file.preflight"
    assert result["decision"] == "proposal_only"
    assert result["receipt_status"] == "preflighted"
    assert result["workspace_file_preflight"]["allowed_capability_ids"] == []
    assert result["workspace_file_preflight"]["autonomy_mode"] == "autonomous_local"
