"""Phase 5 - RBAC Default Permission Seeding.

Purpose: Register baseline roles and permission rules in AccessRuntimeEngine
    so RBAC enforcement has a working ruleset from startup.
Governance scope: permission configuration only.
Dependencies: access_runtime contracts.
Invariants:
  - Default rules are additive; they do not override existing rules.
  - Only duplicate role and rule registrations are skipped.
  - ADMIN gets full access, VIEWER gets read-only.
  - Health/docs endpoints are always exempt (handled by middleware).
"""

from __future__ import annotations

from typing import Any

from .invariants import DuplicateRuntimeIdentifierError, RuntimeCoreInvariantError


def _has_role(access_runtime: Any, role_id: str) -> bool:
    checker = getattr(access_runtime, "has_role", None)
    return bool(checker(role_id)) if callable(checker) else False


def _has_permission_rule(access_runtime: Any, rule_id: str) -> bool:
    checker = getattr(access_runtime, "has_permission_rule", None)
    return bool(checker(rule_id)) if callable(checker) else False


def seed_default_permissions(access_runtime: Any) -> int:
    """Seed default RBAC roles and permission rules.

    Returns the number of rules created. Safe to call multiple times -
    duplicate registrations are caught and skipped.
    """
    from mcoi_runtime.contracts.access_runtime import (
        AuthContextKind,
        PermissionEffect,
        RoleKind,
    )

    rules_created = 0

    # Default roles
    roles = [
        ("admin", "Administrator", RoleKind.ADMIN, [
            "*:*",
        ]),
        ("operator", "Operator", RoleKind.OPERATOR, [
            "llm:*", "tenant:*", "ops:*", "audit:*", "agent:*",
            "workflow:*", "data:*",
        ]),
        ("developer", "Developer", RoleKind.DEVELOPER, [
            "llm:GET", "llm:POST",
            "tenant:GET",
            "agent:GET", "agent:POST",
            "workflow:GET", "workflow:POST",
            "data:GET",
        ]),
        ("viewer", "Viewer", RoleKind.VIEWER, [
            "llm:GET", "tenant:GET", "ops:GET", "audit:GET",
            "agent:GET", "workflow:GET", "data:GET",
        ]),
        ("auditor", "Auditor", RoleKind.AUDITOR, [
            "audit:*", "ops:GET", "tenant:GET",
        ]),
        # Financial roles
        ("financial_viewer", "Financial Viewer", RoleKind.VIEWER, [
            "financial:GET",
        ]),
        ("financial_operator", "Financial Operator", RoleKind.OPERATOR, [
            "financial:GET", "financial:POST",
        ]),
        ("financial_approver", "Financial Approver", RoleKind.OPERATOR, [
            "financial:GET", "financial:POST", "financial_approve:POST",
        ]),
        ("financial_admin", "Financial Admin", RoleKind.ADMIN, [
            "financial:*", "financial_approve:*", "financial_config:*",
        ]),
    ]

    for role_id, name, kind, permissions in roles:
        if _has_role(access_runtime, role_id):
            continue
        try:
            access_runtime.register_role(
                role_id,
                name,
                kind=kind,
                permissions=permissions,
                description="Default role",
            )
        except DuplicateRuntimeIdentifierError:
            pass
        except RuntimeCoreInvariantError:
            raise

    # Default permission rules
    rules = [
        # Admin: full access to everything
        ("rule-admin-all", "*", "*", PermissionEffect.ALLOW, AuthContextKind.GLOBAL),
        # Operator: full access to operational endpoints
        ("rule-operator-llm", "llm", "*", PermissionEffect.ALLOW, AuthContextKind.TENANT),
        ("rule-operator-tenant", "tenant", "*", PermissionEffect.ALLOW, AuthContextKind.TENANT),
        ("rule-operator-ops", "ops", "*", PermissionEffect.ALLOW, AuthContextKind.GLOBAL),
        ("rule-operator-audit", "audit", "*", PermissionEffect.ALLOW, AuthContextKind.TENANT),
        # Developer: read + write for LLM, read for tenant
        ("rule-dev-llm", "llm", "POST", PermissionEffect.ALLOW, AuthContextKind.TENANT),
        ("rule-dev-llm-read", "llm", "GET", PermissionEffect.ALLOW, AuthContextKind.TENANT),
        ("rule-dev-tenant-read", "tenant", "GET", PermissionEffect.ALLOW, AuthContextKind.TENANT),
        # Viewer: read-only everywhere
        ("rule-viewer-read", "*", "GET", PermissionEffect.ALLOW, AuthContextKind.TENANT),
        # RBAC admin operations require approval
        ("rule-rbac-approval", "rbac", "POST", PermissionEffect.REQUIRE_APPROVAL, AuthContextKind.GLOBAL),
        # Financial permission rules
        ("rule-fin-read", "financial", "GET", PermissionEffect.ALLOW, AuthContextKind.TENANT),
        ("rule-fin-write", "financial", "POST", PermissionEffect.ALLOW, AuthContextKind.TENANT),
        ("rule-fin-approve", "financial_approve", "POST", PermissionEffect.REQUIRE_APPROVAL, AuthContextKind.TENANT),
        ("rule-fin-config", "financial_config", "POST", PermissionEffect.REQUIRE_APPROVAL, AuthContextKind.GLOBAL),
    ]

    for rule_id, resource, action, effect, scope in rules:
        if _has_permission_rule(access_runtime, rule_id):
            continue
        try:
            access_runtime.add_permission_rule(
                rule_id,
                resource,
                action,
                effect=effect,
                scope_kind=scope,
            )
            rules_created += 1
        except DuplicateRuntimeIdentifierError:
            pass
        except RuntimeCoreInvariantError:
            raise

    return rules_created
