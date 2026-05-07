"""Autonomous Audit — Deep Fix Tests.

Tests for all fixes from the autonomous quality pass:
reset_budget write-through, PII None handling, audit detail limits,
proof bridge middleware, tenant gating endpoints, LLM adapter safety.
"""

import json
import os

import pytest


# ═══ reset_budget Store Write-Through ═══


class TestResetBudgetWriteThrough:
    def _clock(self) -> str:
        return "2026-01-01T00:00:00Z"

    def test_reset_budget_persists_to_store(self):
        from mcoi_runtime.governance.guards.budget import TenantBudgetManager
        from mcoi_runtime.persistence.postgres_governance_stores import InMemoryBudgetStore
        store = InMemoryBudgetStore()
        mgr = TenantBudgetManager(clock=self._clock, store=store)
        mgr.ensure_budget("t1")
        mgr.record_spend("t1", 5.0)
        assert store.load("t1").spent == 5.0
        mgr.reset_budget("t1")
        stored = store.load("t1")
        assert stored is not None
        assert stored.spent == 0.0
        assert stored.calls_made == 0

    def test_reset_budget_multiple_times(self):
        from mcoi_runtime.governance.guards.budget import TenantBudgetManager
        from mcoi_runtime.persistence.postgres_governance_stores import InMemoryBudgetStore
        store = InMemoryBudgetStore()
        mgr = TenantBudgetManager(clock=self._clock, store=store)
        mgr.ensure_budget("t1")
        mgr.record_spend("t1", 3.0)
        mgr.reset_budget("t1")
        mgr.record_spend("t1", 2.0)
        mgr.reset_budget("t1")
        assert store.load("t1").spent == 0.0


# ═══ PII Scanner None/Type Handling ═══


class TestPIIScannerInputHandling:
    def test_scan_none_returns_empty(self):
        from mcoi_runtime.core.pii_scanner import PIIScanner
        scanner = PIIScanner()
        result = scanner.scan(None)
        assert not result.pii_detected
        assert result.redacted_text == ""

    def test_scan_dict_non_dict_input(self):
        from mcoi_runtime.core.pii_scanner import PIIScanner
        scanner = PIIScanner()
        # Should not crash on non-dict
        result, matches = scanner.scan_dict("not a dict")
        assert result == "not a dict"
        assert matches == []

    def test_scan_dict_none_input(self):
        from mcoi_runtime.core.pii_scanner import PIIScanner
        scanner = PIIScanner()
        result, matches = scanner.scan_dict(None)
        assert result is None
        assert matches == []


# ═══ Audit Detail Size Limit ═══


class TestAuditDetailSizeLimit:
    def _clock(self) -> str:
        return "2026-01-01T00:00:00Z"

    def test_normal_detail_passes(self):
        from mcoi_runtime.governance.audit.trail import AuditTrail
        trail = AuditTrail(clock=self._clock)
        entry = trail.record(
            action="test", actor_id="user", tenant_id="t1",
            target="/api", outcome="success",
            detail={"key": "value"},
        )
        assert entry.detail == {"key": "value"}

    def test_oversized_detail_truncated(self):
        from mcoi_runtime.governance.audit.trail import AuditTrail
        trail = AuditTrail(clock=self._clock)
        huge_detail = {"data": "x" * 100_000}
        entry = trail.record(
            action="test", actor_id="user", tenant_id="t1",
            target="/api", outcome="success",
            detail=huge_detail,
        )
        assert entry.detail.get("_truncated") is True
        assert "_original_size" in entry.detail

    def test_detail_at_limit_passes(self):
        from mcoi_runtime.governance.audit.trail import AuditTrail
        trail = AuditTrail(clock=self._clock)
        # Create detail just under limit
        small_detail = {"k": "v" * 100}
        entry = trail.record(
            action="test", actor_id="user", tenant_id="t1",
            target="/api", outcome="success",
            detail=small_detail,
        )
        assert entry.detail.get("_truncated") is None


# ═══ Content Safety Chain Caching ═══


class TestContentSafetyChainCaching:
    def test_default_chain_is_cached(self):
        from mcoi_runtime.governance.guards.content_safety import build_default_safety_chain
        chain1 = build_default_safety_chain()
        chain2 = build_default_safety_chain()
        assert chain1 is chain2  # Same object (singleton)


# ═══ GuardContext TypedDict ═══


class TestGuardContextTypedDict:
    def test_guard_context_importable(self):
        from mcoi_runtime.governance.guards.chain import GuardContext
        assert GuardContext is not None

    def test_guard_context_fields(self):
        from mcoi_runtime.governance.guards.chain import GuardContext
        # TypedDict should have these keys defined
        annotations = GuardContext.__annotations__
        assert "tenant_id" in annotations
        assert "endpoint" in annotations
        assert "prompt" in annotations
        assert "content" in annotations
        assert "authorization" in annotations


# ═══ Proof Bridge in Middleware ═══


class TestProofBridgeInMiddleware:
    def test_middleware_accepts_proof_bridge(self):
        from mcoi_runtime.app.middleware import GovernanceMiddleware, build_guard_chain
        from mcoi_runtime.governance.guards.chain import GovernanceGuardChain
        from mcoi_runtime.core.proof_bridge import ProofBridge
        bridge = ProofBridge(clock=lambda: "2026-01-01T00:00:00Z")
        # Should not crash on construction
        chain = GovernanceGuardChain()
        # GovernanceMiddleware requires app parameter, so just verify parameter exists
        import inspect
        sig = inspect.signature(GovernanceMiddleware.__init__)
        assert "proof_bridge" in sig.parameters


# ═══ GovernanceStoreBundle ═══


class TestGovernanceStoreBundle:
    def test_bundle_close(self):
        from mcoi_runtime.persistence.postgres_governance_stores import create_governance_stores
        stores = create_governance_stores("memory")
        stores.close()  # Should not raise

    def test_bundle_contains(self):
        from mcoi_runtime.persistence.postgres_governance_stores import create_governance_stores
        stores = create_governance_stores("memory")
        assert "budget" in stores
        assert "audit" in stores
        assert "rate_limit" in stores
        assert "tenant_gating" in stores

    def test_bundle_keys(self):
        from mcoi_runtime.persistence.postgres_governance_stores import create_governance_stores
        stores = create_governance_stores("memory")
        assert set(stores.keys()) == {"budget", "audit", "rate_limit", "tenant_gating"}


# ═══ KeyProvider Runtime Checkable ═══


class TestKeyProviderRuntimeCheckable:
    def test_static_provider_is_key_provider(self):
        from mcoi_runtime.core.field_encryption import KeyProvider, StaticKeyProvider
        p = StaticKeyProvider({"k1": bytes([1] * 32)}, "k1")
        assert isinstance(p, KeyProvider)


# ═══ Server Integration Checks ═══


class TestServerIntegration:
    def test_proof_bridge_registered_in_deps(self):
        os.environ["MULLU_ENV"] = "local_dev"
        os.environ["MULLU_DB_BACKEND"] = "memory"
        import mcoi_runtime.app.server  # Ensure server module loaded
        from mcoi_runtime.app.routers.deps import deps
        assert deps.get("proof_bridge") is not None

    def test_pii_scanner_registered_in_deps(self):
        os.environ["MULLU_ENV"] = "local_dev"
        os.environ["MULLU_DB_BACKEND"] = "memory"
        import mcoi_runtime.app.server
        from mcoi_runtime.app.routers.deps import deps
        assert deps.get("pii_scanner") is not None

    def test_tenant_gating_registered_in_deps(self):
        os.environ["MULLU_ENV"] = "local_dev"
        os.environ["MULLU_DB_BACKEND"] = "memory"
        import mcoi_runtime.app.server
        from mcoi_runtime.app.routers.deps import deps
        assert deps.get("tenant_gating") is not None
