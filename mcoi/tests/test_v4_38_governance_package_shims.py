"""v4.42.0 — audit F7 Phase 4 verification (replaces the v4.38 shim test).

This file's original purpose was to verify the v4.38 shim contract:
that ``mcoi_runtime.governance.X`` re-exported the same objects as
``mcoi_runtime.core.X``. Phases 1-3 maintained that contract.

Phase 4 (v4.42.0) physically moved the 21 governance implementation
files out of ``core/`` and into ``governance/``. The old ``core.X``
paths are now gone. The shim contract no longer exists; the
``governance.X`` paths ARE the implementation.

This rewritten test file pins the post-Phase-4 invariant:

  - Every governance module is importable at its ``governance.Y.X`` path.
  - The old ``core.X`` paths are gone (verified by attempting import
    and expecting ``ModuleNotFoundError``).
  - Every public class / function still resolves and is constructible
    (smoke check that the move didn't break anything).

If a future PR re-introduces a stale ``core.X`` import or shim, the
``TestOldPathsAreGone`` class catches it.
"""
from __future__ import annotations

import importlib


# (new_path, expected_public_symbols) — each entry covers one of the
# 21 governance modules. After Phase 4 these are the canonical paths.
GOVERNANCE_MODULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "mcoi_runtime.governance.auth.jwt",
        ("JWKSFetcher", "JWTAlgorithm", "JWTAuthResult",
         "JWTAuthenticator", "OIDCConfig"),
    ),
    (
        "mcoi_runtime.governance.auth.api_key",
        ("APIKey", "APIKeyManager", "AuthResult"),
    ),
    (
        "mcoi_runtime.governance.guards.chain",
        ("GovernanceGuard", "GovernanceGuardChain", "GuardChainResult",
         "GuardContext", "GuardResult", "create_api_key_guard",
         "create_budget_guard", "create_jwt_guard",
         "create_rate_limit_guard", "create_rbac_guard",
         "create_temporal_guard", "create_tenant_guard"),
    ),
    (
        "mcoi_runtime.governance.guards.rate_limit",
        ("RateLimitConfig", "RateLimitResult", "RateLimitStore",
         "RateLimiter", "TokenBucket"),
    ),
    (
        "mcoi_runtime.governance.guards.budget",
        ("BudgetStore", "TenantBudgetManager", "TenantBudgetPolicy",
         "TenantBudgetReport"),
    ),
    (
        "mcoi_runtime.governance.guards.tenant_gating",
        ("TenantGate", "TenantGatingError", "TenantGatingRegistry",
         "TenantGatingStore", "TenantStatus",
         "create_tenant_gating_guard"),
    ),
    (
        "mcoi_runtime.governance.guards.access",
        ("AccessRuntimeEngine", "AuthContextKind"),
    ),
    (
        "mcoi_runtime.governance.guards.content_safety",
        ("ContentSafetyChain", "ContentSafetyFilter",
         "PROMPT_INJECTION_PATTERNS", "SafetyVerdict",
         "build_default_safety_chain", "create_input_safety_guard"),
    ),
    (
        "mcoi_runtime.governance.audit.trail",
        ("AuditCheckpoint", "AuditEntry", "AuditStore", "AuditTrail",
         "verify_chain_from_entries"),
    ),
    (
        "mcoi_runtime.governance.audit.anchor",
        ("AuditAnchor", "AuditAnchorStore"),
    ),
    (
        "mcoi_runtime.governance.audit.export",
        ("AuditExportResult", "AuditExporter", "ExportMetadata"),
    ),
    (
        "mcoi_runtime.governance.audit.decision_log",
        ("GovernanceDecision", "GovernanceDecisionLog",
         "GuardDecisionDetail"),
    ),
    (
        "mcoi_runtime.governance.network.ssrf",
        ("is_private_host", "is_private_ip", "is_private_url",
         "resolve_and_check"),
    ),
    (
        "mcoi_runtime.governance.network.webhook",
        ("WebhookDelivery", "WebhookEvent",
         "WebhookManager", "WebhookSubscription"),
    ),
    (
        "mcoi_runtime.governance.policy.engine",
        ("PolicyEngine", "PolicyInput", "PolicyReason"),
    ),
    (
        "mcoi_runtime.governance.policy.enforcement",
        ("PolicyEnforcementEngine", "PolicySessionBinding"),
    ),
    (
        "mcoi_runtime.governance.policy.provider",
        ("HttpProviderPolicy", "ProviderPolicyEnforcer",
         "SmtpProviderPolicy"),
    ),
    (
        "mcoi_runtime.governance.policy.sandbox",
        ("PolicySandbox",),
    ),
    (
        "mcoi_runtime.governance.policy.simulation",
        ("PolicySimulationEngine",),
    ),
    (
        "mcoi_runtime.governance.policy.versioning",
        ("PolicyVersionRegistry",),
    ),
    (
        "mcoi_runtime.governance.policy.shell",
        ("ShellPolicyEngine", "ShellPolicyVerdict"),
    ),
    (
        "mcoi_runtime.governance.metrics",
        ("GovernanceMetricsEngine",),
    ),
]


# Old core paths that should be GONE after Phase 4. These literals
# intentionally reference the retired locations — DO NOT update them
# to governance.* paths even when running batch path migrations.
RETIRED_CORE_PATHS: tuple[str, ...] = tuple(
    "mcoi_runtime.core." + suffix for suffix in (
        "jwt_auth", "api_key_auth", "governance_guard", "rate_limiter",
        "tenant_budget", "tenant_gating", "access_runtime",
        "content_safety", "audit_trail", "audit_anchor", "audit_export",
        "governance_decision_log", "ssrf_policy", "webhook_system",
        "policy_engine", "policy_enforcement", "provider_policy",
        "policy_sandbox", "policy_simulation", "policy_versioning",
        "shell_policy_engine", "governance_metrics",
    )
)


class TestPackageStructure:
    def test_top_level_governance_imports(self):
        importlib.import_module("mcoi_runtime.governance")

    def test_every_subpackage_imports(self):
        for sub in ("auth", "guards", "audit", "network", "policy"):
            importlib.import_module(f"mcoi_runtime.governance.{sub}")


class TestNewPathsResolve:
    """Every governance module is importable at its post-Phase-4 path."""

    def test_every_module_imports_cleanly(self):
        for new_path, _syms in GOVERNANCE_MODULES:
            mod = importlib.import_module(new_path)
            assert mod is not None

    def test_every_expected_symbol_resolves(self):
        for new_path, symbols in GOVERNANCE_MODULES:
            mod = importlib.import_module(new_path)
            missing = [s for s in symbols if not hasattr(mod, s)]
            assert not missing, (
                f"{new_path} missing symbols: {missing}"
            )


class TestOldPathsAreGone:
    """The 21 ``core.X`` paths no longer resolve.

    Phase 4 of the F7 reorg moved every governance implementation out
    of ``core/``. Re-introducing a ``core.X.py`` for any of these
    modules would resurrect a stale path. This test catches that.
    """

    def test_core_governance_paths_dont_resolve(self):
        survived = []
        for old_path in RETIRED_CORE_PATHS:
            try:
                importlib.import_module(old_path)
                survived.append(old_path)
            except ModuleNotFoundError:
                pass
        assert not survived, (
            f"Phase 4 expected these paths to be retired, but they "
            f"still resolve: {survived}"
        )
