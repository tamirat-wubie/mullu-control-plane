"""Tests for Phase 225C — Tenant Isolation Verifier."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.tenant_isolation_audit import (
    TenantIsolationAuditor, TenantOperation, IsolationViolationType,
)


@pytest.fixture
def auditor():
    return TenantIsolationAuditor()


class TestTenantIsolationAuditor:
    def test_clean_audit(self, auditor):
        ops = [
            TenantOperation("o1", "t1", "t1", "docs", "read"),
            TenantOperation("o2", "t1", "t1", "docs", "write"),
        ]
        result = auditor.audit(ops)
        assert result.is_clean
        assert result.operations_scanned == 2

    def test_cross_tenant_read(self, auditor):
        ops = [TenantOperation("o1", "t1", "t2", "docs", "read")]
        result = auditor.audit(ops)
        assert not result.is_clean
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == IsolationViolationType.CROSS_TENANT_READ

    def test_cross_tenant_write(self, auditor):
        ops = [TenantOperation("o1", "t1", "t2", "docs", "write")]
        result = auditor.audit(ops)
        assert result.violations[0].violation_type == IsolationViolationType.CROSS_TENANT_WRITE

    def test_cross_tenant_delete(self, auditor):
        ops = [TenantOperation("o1", "t1", "t2", "docs", "delete")]
        result = auditor.audit(ops)
        assert result.violations[0].violation_type == IsolationViolationType.CROSS_TENANT_WRITE

    def test_mixed_operations(self, auditor):
        ops = [
            TenantOperation("o1", "t1", "t1", "docs", "read"),   # ok
            TenantOperation("o2", "t1", "t2", "docs", "read"),   # violation
            TenantOperation("o3", "t2", "t2", "logs", "write"),  # ok
        ]
        result = auditor.audit(ops)
        assert result.operations_scanned == 3
        assert len(result.violations) == 1

    def test_audit_result_to_dict(self, auditor):
        ops = [TenantOperation("o1", "t1", "t1", "docs", "read")]
        result = auditor.audit(ops, audit_id="test-audit")
        d = result.to_dict()
        assert d["audit_id"] == "test-audit"
        assert d["is_clean"] is True
        assert d["operations_scanned"] == 1

    def test_empty_operations(self, auditor):
        result = auditor.audit([])
        assert result.is_clean
        assert result.operations_scanned == 0

    def test_summary(self, auditor):
        ops1 = [TenantOperation("o1", "t1", "t1", "docs", "read")]
        ops2 = [TenantOperation("o2", "t1", "t2", "docs", "read")]
        auditor.audit(ops1)
        auditor.audit(ops2)
        s = auditor.summary()
        assert s["total_audits"] == 2
        assert s["total_operations_scanned"] == 2
        assert s["total_violations"] == 1

    def test_recent_audits(self, auditor):
        for i in range(5):
            auditor.audit([TenantOperation(f"o{i}", "t1", "t1", "r", "read")])
        assert len(auditor.recent_audits(3)) == 3
