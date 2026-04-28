"""v4.38.0 — audit F7 Phase 1: governance package shim verification.

Phase 1 of the audit-F7 reorganization (see
``docs/GOVERNANCE_PACKAGE_REORG_PLAN.md``) introduces a new
``mcoi_runtime.governance`` package whose submodules re-export the
canonical governance API from ``mcoi_runtime.core.*``.

Phase 1 is non-breaking by design: every existing caller continues to
work via ``mcoi_runtime.core.X``; the new ``mcoi_runtime.governance.Y.X``
paths are additive aliases.

These tests verify:

  - Every advertised shim path imports cleanly.
  - Every re-exported symbol resolves to the **same object** as the
    canonical ``core/`` location (identity, not equality).
  - Each shim's ``__all__`` matches the symbols it claims to re-export.

When Phase 4 lands (shim removal + file moves), these tests will pivot
to verify that the implementation is actually at the new location and
the old ``core/`` paths are gone.
"""
from __future__ import annotations

import importlib
from typing import Iterable


# (new_path, old_path, expected_symbols)
SHIM_TABLE: list[tuple[str, str, tuple[str, ...]]] = [
    # auth
    (
        "mcoi_runtime.governance.auth.jwt",
        "mcoi_runtime.core.jwt_auth",
        ("JWKSFetcher", "JWTAlgorithm", "JWTAuthResult",
         "JWTAuthenticator", "OIDCConfig"),
    ),
    (
        "mcoi_runtime.governance.auth.api_key",
        "mcoi_runtime.core.api_key_auth",
        ("APIKey", "APIKeyManager", "AuthResult"),
    ),
    # guards
    (
        "mcoi_runtime.governance.guards.chain",
        "mcoi_runtime.core.governance_guard",
        ("GovernanceGuard", "GovernanceGuardChain", "GuardChainResult",
         "GuardContext", "GuardResult", "create_api_key_guard",
         "create_budget_guard", "create_jwt_guard",
         "create_rate_limit_guard", "create_rbac_guard",
         "create_tenant_guard"),
    ),
    (
        "mcoi_runtime.governance.guards.rate_limit",
        "mcoi_runtime.core.rate_limiter",
        ("RateLimitConfig", "RateLimitResult", "RateLimitStore",
         "RateLimiter", "TokenBucket"),
    ),
    (
        "mcoi_runtime.governance.guards.budget",
        "mcoi_runtime.core.tenant_budget",
        ("BudgetStore", "TenantBudgetManager", "TenantBudgetPolicy",
         "TenantBudgetReport"),
    ),
    (
        "mcoi_runtime.governance.guards.tenant_gating",
        "mcoi_runtime.core.tenant_gating",
        ("InvalidTenantStatusTransitionError",
         "TenantAlreadyRegisteredError", "TenantGate",
         "TenantGatingError", "TenantGatingRegistry",
         "TenantGatingStore", "TenantNotRegisteredError",
         "TenantStatus", "create_tenant_gating_guard"),
    ),
    (
        "mcoi_runtime.governance.guards.access",
        "mcoi_runtime.core.access_runtime",
        ("AccessAuditRecord", "AccessDecision", "AccessEvaluation",
         "AccessRequest", "AccessRuntimeEngine", "AccessSnapshot",
         "AccessViolation", "AuthContextKind", "DelegationRecord",
         "DelegationStatus", "DuplicateRuntimeIdentifierError",
         "EventRecord", "EventSource", "EventSpineEngine", "EventType",
         "IdentityKind", "IdentityRecord", "PermissionEffect",
         "PermissionRule", "RoleBinding", "RoleKind", "RoleRecord",
         "RuntimeCoreInvariantError"),
    ),
    (
        "mcoi_runtime.governance.guards.content_safety",
        "mcoi_runtime.core.content_safety",
        ("ContentSafetyChain", "ContentSafetyFilter", "ContentSafetyResult",
         "LAMBDA_INPUT_SAFETY", "LAMBDA_OUTPUT_SAFETY",
         "OutputSafetyResult", "PROMPT_INJECTION_PATTERNS",
         "SafetyFilterResult", "SafetyPattern", "SafetyVerdict",
         "ThreatCategory", "build_default_safety_chain",
         "create_content_safety_guard", "create_input_safety_guard",
         "create_output_safety_guard", "evaluate_output_safety",
         "normalize_content"),
    ),
    # audit
    (
        "mcoi_runtime.governance.audit.trail",
        "mcoi_runtime.core.audit_trail",
        ("AuditCheckpoint", "AuditEntry", "AuditStore", "AuditTrail",
         "ExternalVerifyResult", "GENESIS_HASH",
         "LEDGER_SCHEMA_VERSION_MAX", "LEDGER_V1_CONTENT_FIELDS",
         "verify_chain_from_entries"),
    ),
    (
        "mcoi_runtime.governance.audit.anchor",
        "mcoi_runtime.core.audit_anchor",
        ("AuditAnchor", "AuditAnchorStore"),
    ),
    (
        "mcoi_runtime.governance.audit.export",
        "mcoi_runtime.core.audit_export",
        ("AuditExportResult", "AuditExporter", "ExportMetadata"),
    ),
    (
        "mcoi_runtime.governance.audit.decision_log",
        "mcoi_runtime.core.governance_decision_log",
        ("GovernanceDecision", "GovernanceDecisionLog",
         "GuardDecisionDetail"),
    ),
    # network
    (
        "mcoi_runtime.governance.network.ssrf",
        "mcoi_runtime.core.ssrf_policy",
        ("is_private_host", "is_private_ip", "is_private_url",
         "resolve_and_check"),
    ),
    (
        "mcoi_runtime.governance.network.webhook",
        "mcoi_runtime.core.webhook_system",
        ("EVENTS", "WebhookDelivery", "WebhookEvent",
         "WebhookManager", "WebhookSubscription"),
    ),
    # policy
    (
        "mcoi_runtime.governance.policy.engine",
        "mcoi_runtime.core.policy_engine",
        ("PolicyDecisionFactory", "PolicyEngine", "PolicyInput",
         "PolicyPackLike", "PolicyPackResolver", "PolicyReason",
         "PolicyRuleLike", "PolicyStatus"),
    ),
    (
        "mcoi_runtime.governance.policy.enforcement",
        "mcoi_runtime.core.policy_enforcement",
        ("EnforcementAuditRecord", "EnforcementDecision",
         "EnforcementEvent", "PolicyEnforcementEngine",
         "PolicySessionBinding", "PrivilegeElevationDecision",
         "PrivilegeElevationRequest", "PrivilegeLevel",
         "RevocationReason", "RevocationRecord",
         "SessionClosureReport", "SessionConstraint",
         "SessionKind", "SessionRecord", "SessionSnapshot",
         "SessionStatus", "StepUpStatus"),
    ),
    (
        "mcoi_runtime.governance.policy.provider",
        "mcoi_runtime.core.provider_policy",
        ("HttpProviderPolicy", "PolicyViolationSeverity",
         "ProcessProviderPolicy", "ProviderInvocationCheck",
         "ProviderPolicyEnforcer", "ProviderPolicyType",
         "ProviderPolicyViolation", "SmtpProviderPolicy"),
    ),
    (
        "mcoi_runtime.governance.policy.sandbox",
        "mcoi_runtime.core.policy_sandbox",
        ("ActionSimResult", "PolicySandbox", "SimulationRequest",
         "SimulationResult", "SimulationScenario"),
    ),
    (
        "mcoi_runtime.governance.policy.simulation",
        "mcoi_runtime.core.policy_simulation",
        ("AdoptionReadiness", "AdoptionRecommendation",
         "DiffDisposition", "PolicyDiffRecord", "PolicyImpactLevel",
         "PolicySimulationEngine", "PolicySimulationRequest",
         "PolicySimulationResult", "PolicySimulationScenario",
         "RuntimeImpactRecord", "SandboxAssessment",
         "SandboxClosureReport", "SandboxScope", "SandboxSnapshot",
         "SandboxViolation", "SimulationMode", "SimulationStatus"),
    ),
    (
        "mcoi_runtime.governance.policy.versioning",
        "mcoi_runtime.core.policy_versioning",
        ("PolicyArtifact", "PolicyChangeKind",
         "PolicyDecisionSnapshot", "PolicyRuleDiff",
         "PolicyVersionDiff", "PolicyVersionRegistry",
         "ShadowGovernanceEvaluator", "ShadowGovernanceResult",
         "VersionedPolicyRule", "VersionedPolicyRuleLike"),
    ),
    (
        "mcoi_runtime.governance.policy.shell",
        "mcoi_runtime.core.shell_policy_engine",
        ("ShellCommandPolicy", "ShellPolicyEngine",
         "ShellPolicyVerdict"),
    ),
    # top-level
    (
        "mcoi_runtime.governance.metrics",
        "mcoi_runtime.core.governance_metrics",
        ("GovernanceMetricsEngine", "MetricSnapshot"),
    ),
]


def _all_symbols_with_paths() -> Iterable[tuple[str, str, str]]:
    """Yield (new_path, old_path, symbol_name) for parametrization."""
    for new_path, old_path, symbols in SHIM_TABLE:
        for sym in symbols:
            yield new_path, old_path, sym


class TestPackageStructure:
    """The new governance/ package and its submodules import cleanly."""

    def test_top_level_governance_imports(self):
        """The package itself imports without error."""
        importlib.import_module("mcoi_runtime.governance")

    def test_every_subpackage_imports(self):
        for sub in ("auth", "guards", "audit", "network", "policy"):
            importlib.import_module(f"mcoi_runtime.governance.{sub}")


class TestShimsImportCleanly:
    """Every advertised shim module imports without error."""

    def test_every_shim_resolves(self):
        for new_path, _old, _syms in SHIM_TABLE:
            mod = importlib.import_module(new_path)
            assert mod is not None


class TestIdentityPreservation:
    """Every re-exported symbol is the SAME OBJECT as in core/.

    This is what makes Phase 1 non-breaking: a caller using either path
    gets the exact same class/function, so isinstance checks, identity
    comparisons, and frame-based introspection all keep working across
    the import boundary.
    """

    def test_every_symbol_resolves_to_same_object(self):
        for new_path, old_path, symbols in SHIM_TABLE:
            new_mod = importlib.import_module(new_path)
            old_mod = importlib.import_module(old_path)
            for sym in symbols:
                new_obj = getattr(new_mod, sym)
                old_obj = getattr(old_mod, sym)
                assert new_obj is old_obj, (
                    f"{new_path}.{sym} is {new_obj!r}, "
                    f"but {old_path}.{sym} is {old_obj!r}"
                )


class TestExplicitDunderAll:
    """Each shim's ``__all__`` matches what it claims to re-export.

    This catches drift between the shim's documented API and the
    actual re-exported symbols.
    """

    def test_every_shim_declares_dunder_all(self):
        for new_path, _old, expected_symbols in SHIM_TABLE:
            mod = importlib.import_module(new_path)
            declared = getattr(mod, "__all__", None)
            assert declared is not None, f"{new_path} missing __all__"
            assert set(declared) == set(expected_symbols), (
                f"{new_path}.__all__ ({sorted(declared)}) does not match "
                f"expected ({sorted(expected_symbols)})"
            )


class TestNoBackwardBreakage:
    """The original ``core/`` paths still work — Phase 1 is additive."""

    def test_core_jwt_auth_still_imports(self):
        from mcoi_runtime.core.jwt_auth import JWTAuthenticator
        assert JWTAuthenticator is not None

    def test_core_audit_trail_still_imports(self):
        from mcoi_runtime.core.audit_trail import AuditTrail
        assert AuditTrail is not None

    def test_core_governance_guard_still_imports(self):
        from mcoi_runtime.core.governance_guard import GovernanceGuardChain
        assert GovernanceGuardChain is not None

    def test_core_ssrf_policy_still_imports(self):
        from mcoi_runtime.core.ssrf_policy import is_private_url
        assert is_private_url is not None
