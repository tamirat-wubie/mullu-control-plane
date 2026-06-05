"""Purpose: verify deterministic tool-call permission primitives.

Governance scope: tenant/tool permission grammar, argument-schema checks,
budget binding, and governed tool invocation denial paths.
Dependencies: tool permission primitives and governed tool registry.
Invariants: permission checks fail closed; audit-required permissions require
audit presence; argument hashes and schema hashes are deterministic.
"""

from __future__ import annotations

import json

import pytest

from mcoi_runtime.app.tool_permission_integration import (
    TOOL_PERMISSION_REGISTRY_PATH_ENV,
    select_tool_permission_registry,
    validate_tool_permission_registry_path,
)
from mcoi_runtime.core.governed_tool_use import GovernedToolRegistry, ToolDefinition
from mcoi_runtime.core.tool_permission_primitives import (
    FileToolPermissionRegistry,
    ToolCallPermission,
    ToolPermissionRegistry,
    ToolPermissionRequest,
    validate_arguments,
)


def _schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "account_id": {"type": "string"},
            "amount": {"type": "number"},
        },
        "required": ["account_id", "amount"],
        "additionalProperties": False,
    }


def _permission(*, audit_required: bool = True) -> ToolCallPermission:
    return ToolCallPermission(
        tenant_id="tenant-1",
        tool_name="send_payment",
        argument_schema=_schema(),
        budget_ref="budget-finance",
        audit_required=audit_required,
        description="Permit governed payment dispatch",
    )


def _request(**overrides: object) -> ToolPermissionRequest:
    values: dict[str, object] = {
        "tenant_id": "tenant-1",
        "tool_name": "send_payment",
        "arguments": {"account_id": "acct-1", "amount": 25.0},
        "budget_ref": "budget-finance",
        "audit_present": True,
    }
    values.update(overrides)
    return ToolPermissionRequest(**values)  # type: ignore[arg-type]


def test_permission_match_emits_stable_grammar_and_hashes() -> None:
    registry = ToolPermissionRegistry()
    permission = registry.register(_permission())

    first = registry.evaluate(_request())
    second = registry.evaluate(_request())

    assert first.allowed is True
    assert first.reason_codes == ("permission_matched",)
    assert first.permission_id == permission.permission_id
    assert first.schema_hash == second.schema_hash
    assert "tenant:tenant-1 may call tool:send_payment" in first.grammar


def test_permission_denies_missing_audit_without_executing() -> None:
    registry = ToolPermissionRegistry()
    permission = registry.register(_permission(audit_required=True))

    decision = registry.evaluate(_request(audit_present=False))

    assert decision.allowed is False
    assert decision.reason_codes == ("audit_required",)
    assert decision.permission_id == permission.permission_id
    assert decision.argument_hash == _request(audit_present=False).argument_hash()


def test_permission_denies_schema_violations_fail_closed() -> None:
    registry = ToolPermissionRegistry()
    registry.register(_permission())

    decision = registry.evaluate(_request(arguments={"account_id": "acct-1", "extra": True}))
    schema_errors = validate_arguments(_schema(), {"account_id": "acct-1", "extra": True})

    assert decision.allowed is False
    assert decision.reason_codes == ("schema_violation",)
    assert "missing:amount" in schema_errors
    assert "unexpected:extra" in schema_errors


def test_governed_tool_registry_applies_bound_permission_registry() -> None:
    permission_registry = ToolPermissionRegistry()
    permission_registry.register(_permission())
    governed_registry = GovernedToolRegistry(clock=lambda: "2026-04-25T12:00:00Z")
    governed_registry.bind_permission_registry(permission_registry)
    governed_registry.register(ToolDefinition(name="send_payment", description="Send payment"))

    denied = governed_registry.invoke(
        "send_payment",
        {"account_id": "acct-1", "amount": 25.0},
        tenant_id="tenant-1",
        budget_ref="wrong-budget",
        executor=lambda _name, _args: {"sent": True},
    )
    allowed = governed_registry.invoke(
        "send_payment",
        {"account_id": "acct-1", "amount": 25.0},
        tenant_id="tenant-1",
        budget_ref="budget-finance",
        executor=lambda _name, _args: {"sent": True},
    )

    assert denied.allowed is False
    assert denied.permission_decision is not None
    assert denied.permission_decision.reason_codes == ("budget_mismatch",)
    assert allowed.allowed is True
    assert allowed.result == {"sent": True}


def test_file_tool_permission_registry_persists_and_reloads_permissions(tmp_path) -> None:
    path = tmp_path / "tool-permissions.json"
    registry = FileToolPermissionRegistry(path)
    permission = registry.register(_permission())

    reloaded = FileToolPermissionRegistry(path)
    permissions = reloaded.list_permissions(tenant_id="tenant-1")
    decision = reloaded.evaluate(_request())

    assert path.exists()
    assert len(permissions) == 1
    assert permissions[0].permission_id == permission.permission_id
    assert permissions[0].schema_hash() == permission.schema_hash()
    assert decision.allowed is True
    assert decision.reason_codes == ("permission_matched",)
    assert decision.grammar == permission.grammar()


def test_file_tool_permission_registry_rejects_tampered_permission_identity(tmp_path) -> None:
    path = tmp_path / "tool-permissions.json"
    registry = FileToolPermissionRegistry(path)
    permission = registry.register(_permission())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["permissions"][0]["budget_ref"] = "budget-tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="tool permission identity mismatch"):
        FileToolPermissionRegistry(path)

    assert permission.permission_id
    assert payload["permissions"][0]["permission_id"] == permission.permission_id
    assert payload["permissions"][0]["budget_ref"] == "budget-tampered"


def test_tool_permission_registry_integration_selects_memory_or_file(tmp_path) -> None:
    path = tmp_path / "tool-permissions.json"

    memory_bootstrap = select_tool_permission_registry({})
    file_bootstrap = select_tool_permission_registry({TOOL_PERMISSION_REGISTRY_PATH_ENV: str(path)})

    assert isinstance(memory_bootstrap.registry, ToolPermissionRegistry)
    assert memory_bootstrap.persistent is False
    assert memory_bootstrap.path == ""
    assert isinstance(file_bootstrap.registry, FileToolPermissionRegistry)
    assert file_bootstrap.persistent is True
    assert file_bootstrap.path == str(path)


def test_tool_permission_registry_path_validation_requires_absolute_json_path(tmp_path) -> None:
    valid_path = tmp_path / "tool-permissions.json"

    assert validate_tool_permission_registry_path(valid_path) == valid_path
    with pytest.raises(RuntimeError, match="absolute file path"):
        validate_tool_permission_registry_path("relative/tool-permissions.json")
    with pytest.raises(RuntimeError, match="json file extension"):
        validate_tool_permission_registry_path(tmp_path / "tool-permissions.txt")
