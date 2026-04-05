"""Tests for Phase 195D — Adapter & Connector Governance."""
import pytest
from mcoi_runtime.core.adapter_governance import (
    AdapterAuthority,
    AdapterAuthorityError,
    AdapterGovernanceGuard,
    EFFECTFUL_ADAPTERS,
    is_effectful,
)


class TestAdapterGovernance:
    def test_authorize_creates_authority(self):
        guard = AdapterGovernanceGuard()
        auth = guard.authorize("shell_executor", "run", "actor-1")
        assert isinstance(auth, AdapterAuthority)
        assert auth.actor_id == "actor-1"
        assert auth.adapter_type == "shell_executor"
        assert auth.operation == "run"
        assert auth.authority_id == "auth-1"
        assert auth.issued_at  # non-empty

    def test_require_authority_passes(self):
        guard = AdapterGovernanceGuard()
        auth = guard.authorize("http_connector", "get", "actor-2")
        # Should not raise
        guard.require_authority(auth, "http_connector", "get")

    def test_require_authority_none_raises(self):
        guard = AdapterGovernanceGuard()
        with pytest.raises(AdapterAuthorityError, match="No authority") as exc_info:
            guard.require_authority(None, "shell_executor", "run")
        assert "shell_executor" not in str(exc_info.value)
        assert "run" not in str(exc_info.value)

    def test_require_authority_type_mismatch_raises(self):
        guard = AdapterGovernanceGuard()
        auth = guard.authorize("http_connector", "get", "actor-3")
        with pytest.raises(AdapterAuthorityError, match="type mismatch") as exc_info:
            guard.require_authority(auth, "shell_executor", "run")
        assert "http_connector" not in str(exc_info.value)
        assert "shell_executor" not in str(exc_info.value)

    def test_deny_increments_blocked(self):
        guard = AdapterGovernanceGuard()
        assert guard.blocked_calls == 0
        guard.deny("shell_executor", "run")
        assert guard.blocked_calls == 1
        guard.deny("http_connector", "post")
        assert guard.blocked_calls == 2

    def test_audit_report_structure(self):
        guard = AdapterGovernanceGuard()
        guard.authorize("shell_executor", "run", "a")
        report = guard.audit_report()
        assert set(report.keys()) == {"total", "authorized", "blocked", "ratio", "adapters_used"}

    def test_governance_ratio_all_authorized(self):
        guard = AdapterGovernanceGuard()
        guard.authorize("shell_executor", "run", "a")
        guard.authorize("http_connector", "get", "b")
        assert guard.governance_ratio() == 1.0

    def test_governance_ratio_mixed(self):
        guard = AdapterGovernanceGuard()
        guard.authorize("shell_executor", "run", "a")
        guard.deny("http_connector", "post")
        # 1 authorized out of 2 total
        assert guard.governance_ratio() == 0.5

    def test_effectful_adapters_registered(self):
        expected = {
            "shell_executor",
            "http_connector",
            "smtp_communication",
            "browser_adapter",
            "stub_model",
            "filesystem_observer",
            "process_observer",
            "external_connector",
        }
        assert EFFECTFUL_ADAPTERS == expected
        assert len(EFFECTFUL_ADAPTERS) == 8

    def test_is_effectful_true(self):
        assert is_effectful("shell_executor") is True

    def test_is_effectful_false(self):
        assert is_effectful("unknown_adapter") is False

    def test_golden_lifecycle(self):
        guard = AdapterGovernanceGuard()
        # Step 1: authorize
        auth = guard.authorize("browser_adapter", "navigate", "op-1")
        assert isinstance(auth, AdapterAuthority)
        # Step 2: require (passes)
        guard.require_authority(auth, "browser_adapter", "navigate")
        # Step 3: audit state
        assert guard.total_calls == 1
        assert guard.authorized_calls == 1
        assert guard.blocked_calls == 0
        # Step 4: report
        report = guard.audit_report()
        assert report["total"] == 1
        assert report["authorized"] == 1
        assert report["blocked"] == 0
        assert report["ratio"] == 1.0
        assert "browser_adapter" in report["adapters_used"]
