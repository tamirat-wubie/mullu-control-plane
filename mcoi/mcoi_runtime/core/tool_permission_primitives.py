"""Purpose: deterministic tool-call permission primitives.

Governance scope: tenant-scoped tool permissions, bounded argument-schema
matching, budget binding, and audit-required enforcement for agent tool calls.
Dependencies: runtime invariant helpers and standard deterministic hashing.
Invariants: permission checks fail closed; argument hashes are stable; schema
matching is bounded; audit-required permissions cannot execute without audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Literal

from .invariants import ensure_non_empty_text, stable_identifier

PermissionReason = Literal[
    "permission_matched",
    "permission_not_found",
    "tenant_mismatch",
    "tool_mismatch",
    "schema_violation",
    "budget_mismatch",
    "audit_required",
]


@dataclass(frozen=True, slots=True)
class ToolCallPermission:
    """Capability grammar primitive for one tenant/tool/budget boundary."""

    tenant_id: str
    tool_name: str
    argument_schema: dict[str, Any]
    budget_ref: str
    audit_required: bool = True
    permission_id: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", ensure_non_empty_text("tenant_id", self.tenant_id))
        object.__setattr__(self, "tool_name", ensure_non_empty_text("tool_name", self.tool_name))
        object.__setattr__(self, "budget_ref", ensure_non_empty_text("budget_ref", self.budget_ref))
        if not isinstance(self.argument_schema, dict) or not self.argument_schema:
            raise ValueError("argument_schema must be a non-empty object")
        if not isinstance(self.audit_required, bool):
            raise ValueError("audit_required must be a bool")
        if self.permission_id:
            object.__setattr__(self, "permission_id", ensure_non_empty_text("permission_id", self.permission_id))
        else:
            object.__setattr__(
                self,
                "permission_id",
                stable_identifier(
                    "tool-permission",
                    {
                        "tenant_id": self.tenant_id,
                        "tool_name": self.tool_name,
                        "argument_schema": self.argument_schema,
                        "budget_ref": self.budget_ref,
                        "audit_required": self.audit_required,
                    },
                ),
            )

    def grammar(self) -> str:
        """Return the published permission grammar sentence."""
        return (
            f"tenant:{self.tenant_id} may call tool:{self.tool_name} "
            f"with args matching schema:{self.schema_hash()} "
            f"under budget:{self.budget_ref} "
            f"with audit_required:{str(self.audit_required).lower()}"
        )

    def schema_hash(self) -> str:
        encoded = json.dumps(self.argument_schema, sort_keys=True, separators=(",", ":"), default=str)
        return f"schema-{sha256(encoded.encode('utf-8')).hexdigest()[:16]}"


@dataclass(frozen=True, slots=True)
class ToolPermissionRequest:
    """Runtime request checked against tool-call permissions."""

    tenant_id: str
    tool_name: str
    arguments: dict[str, Any]
    budget_ref: str
    audit_present: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", ensure_non_empty_text("tenant_id", self.tenant_id))
        object.__setattr__(self, "tool_name", ensure_non_empty_text("tool_name", self.tool_name))
        object.__setattr__(self, "budget_ref", ensure_non_empty_text("budget_ref", self.budget_ref))
        if not isinstance(self.arguments, dict):
            raise ValueError("arguments must be an object")
        if not isinstance(self.audit_present, bool):
            raise ValueError("audit_present must be a bool")

    def argument_hash(self) -> str:
        encoded = json.dumps(self.arguments, sort_keys=True, separators=(",", ":"), default=str)
        return sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ToolPermissionDecision:
    """Decision emitted by permission evaluation."""

    allowed: bool
    reason_codes: tuple[PermissionReason, ...]
    permission_id: str = ""
    tenant_id: str = ""
    tool_name: str = ""
    budget_ref: str = ""
    argument_hash: str = ""
    schema_hash: str = ""
    grammar: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolPermissionRegistry:
    """Registry and evaluator for tool-call permission primitives."""

    def __init__(self) -> None:
        self._permissions: dict[str, ToolCallPermission] = {}

    def register(self, permission: ToolCallPermission) -> ToolCallPermission:
        if permission.permission_id in self._permissions:
            raise ValueError("tool permission already registered")
        self._permissions[permission.permission_id] = permission
        return permission

    def list_permissions(self, *, tenant_id: str | None = None) -> tuple[ToolCallPermission, ...]:
        permissions = tuple(sorted(self._permissions.values(), key=lambda item: item.permission_id))
        if tenant_id is None:
            return permissions
        return tuple(permission for permission in permissions if permission.tenant_id == tenant_id)

    def evaluate(self, request: ToolPermissionRequest) -> ToolPermissionDecision:
        candidates = [
            permission
            for permission in self._permissions.values()
            if permission.tenant_id == request.tenant_id and permission.tool_name == request.tool_name
        ]
        if not candidates:
            return _decision(request, allowed=False, reason_codes=("permission_not_found",))

        failed_decisions: list[tuple[ToolCallPermission, tuple[PermissionReason, ...]]] = []
        for permission in sorted(candidates, key=lambda item: item.permission_id):
            reason_codes = _evaluate_permission(permission, request)
            if reason_codes == ("permission_matched",):
                return _decision(request, permission=permission, allowed=True, reason_codes=reason_codes)
            failed_decisions.append((permission, reason_codes))

        permission, reason_codes = failed_decisions[0]
        return _decision(request, permission=permission, allowed=False, reason_codes=reason_codes)


def _evaluate_permission(
    permission: ToolCallPermission,
    request: ToolPermissionRequest,
) -> tuple[PermissionReason, ...]:
    reason_codes: list[PermissionReason] = []
    if permission.tenant_id != request.tenant_id:
        reason_codes.append("tenant_mismatch")
    if permission.tool_name != request.tool_name:
        reason_codes.append("tool_mismatch")
    if permission.budget_ref != request.budget_ref:
        reason_codes.append("budget_mismatch")
    if permission.audit_required and not request.audit_present:
        reason_codes.append("audit_required")
    schema_errors = validate_arguments(permission.argument_schema, request.arguments)
    if schema_errors:
        reason_codes.append("schema_violation")
    if reason_codes:
        return tuple(reason_codes)
    return ("permission_matched",)


def _decision(
    request: ToolPermissionRequest,
    *,
    allowed: bool,
    reason_codes: tuple[PermissionReason, ...],
    permission: ToolCallPermission | None = None,
) -> ToolPermissionDecision:
    return ToolPermissionDecision(
        allowed=allowed,
        reason_codes=reason_codes,
        permission_id=permission.permission_id if permission else "",
        tenant_id=request.tenant_id,
        tool_name=request.tool_name,
        budget_ref=request.budget_ref,
        argument_hash=request.argument_hash(),
        schema_hash=permission.schema_hash() if permission else "",
        grammar=permission.grammar() if permission else "",
    )


def validate_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> tuple[str, ...]:
    """Validate arguments against a bounded JSON-schema subset."""
    errors: list[str] = []
    if schema.get("type") != "object":
        return ("schema_root_must_be_object",)
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return ("schema_properties_must_be_object",)
    required = schema.get("required", ())
    if not isinstance(required, (list, tuple)):
        return ("schema_required_must_be_array",)
    for field_name in required:
        if field_name not in arguments:
            errors.append(f"missing:{field_name}")
    if schema.get("additionalProperties") is False:
        for field_name in arguments:
            if field_name not in properties:
                errors.append(f"unexpected:{field_name}")
    for field_name, value in arguments.items():
        field_schema = properties.get(field_name)
        if isinstance(field_schema, dict):
            errors.extend(_validate_value(field_schema, value, field_name))
    return tuple(errors)


def _validate_value(schema: dict[str, Any], value: Any, path: str) -> tuple[str, ...]:
    expected_type = schema.get("type")
    errors: list[str] = []
    if expected_type is not None and not _type_matches(expected_type, value):
        errors.append(f"type:{path}")
    if "const" in schema and value != schema["const"]:
        errors.append(f"const:{path}")
    enum_values = schema.get("enum")
    if enum_values is not None and value not in enum_values:
        errors.append(f"enum:{path}")
    return tuple(errors)


def _type_matches(expected_type: str, value: Any) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "null":
        return value is None
    return False
