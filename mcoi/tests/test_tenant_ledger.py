"""Phase 201D — Tenant-scoped ledger and session isolation tests."""

import pytest

from mcoi_runtime.persistence.tenant_ledger import TenantLedger


def fixed_clock() -> str:
    return "2026-03-26T12:00:00Z"

class TestTenantLedgerEntry:
    def test_append(self):
        ledger = TenantLedger(clock=fixed_clock)
        entry = ledger.append("t1", "llm", "actor-1", {"cost": 0.5})
        assert entry.tenant_id == "t1"
        assert entry.entry_type == "llm"
        assert entry.content["cost"] == 0.5
        assert entry.content_hash

    def test_query_by_tenant(self):
        ledger = TenantLedger(clock=fixed_clock)
        ledger.append("t1", "llm", "a1", {"v": 1})
        ledger.append("t2", "llm", "a2", {"v": 2})
        t1_entries = ledger.query("t1")
        assert len(t1_entries) == 1
        assert t1_entries[0].tenant_id == "t1"

    def test_isolation(self):
        ledger = TenantLedger(clock=fixed_clock)
        ledger.append("t1", "llm", "a1", {"secret": "t1-data"})
        ledger.append("t2", "llm", "a2", {"secret": "t2-data"})
        # t1 cannot see t2's data
        t1_entries = ledger.query("t1")
        assert all(e.tenant_id == "t1" for e in t1_entries)
        t2_entries = ledger.query("t2")
        assert all(e.tenant_id == "t2" for e in t2_entries)

    def test_query_by_type(self):
        ledger = TenantLedger(clock=fixed_clock)
        ledger.append("t1", "llm", "a1", {})
        ledger.append("t1", "execution", "a1", {})
        ledger.append("t1", "llm", "a1", {})
        llm_entries = ledger.query("t1", entry_type="llm")
        assert len(llm_entries) == 2

    def test_query_limit(self):
        ledger = TenantLedger(clock=fixed_clock)
        for i in range(10):
            ledger.append("t1", "llm", "a1", {"i": i})
        entries = ledger.query("t1", limit=3)
        assert len(entries) == 3

    def test_query_limit_boundaries(self):
        ledger = TenantLedger(clock=fixed_clock)
        for i in range(5):
            ledger.append("t1", "llm", "a1", {"i": i})

        limited_entries = ledger.query("t1", limit=2)

        assert ledger.query("t1", limit=0) == []
        assert len(limited_entries) == 2
        assert [entry.content["i"] for entry in limited_entries] == [3, 4]
        with pytest.raises(ValueError, match="must not be negative"):
            ledger.query("t1", limit=-1)
        for invalid_limit in (True, 1.5, "2"):
            with pytest.raises(ValueError, match="must be an integer"):
                ledger.query("t1", limit=invalid_limit)

    def test_count(self):
        ledger = TenantLedger(clock=fixed_clock)
        assert ledger.count("t1") == 0
        ledger.append("t1", "llm", "a1", {})
        ledger.append("t1", "llm", "a1", {})
        assert ledger.count("t1") == 2
        assert ledger.count("t2") == 0

    def test_append_rejects_non_finite_content_before_hash(self):
        ledger = TenantLedger(clock=fixed_clock)

        with pytest.raises(ValueError, match=r"^ledger content must be deterministic JSON$") as excinfo:
            ledger.append("t1", "llm", "a1", {"secret_metric": float("nan")})

        message = str(excinfo.value)
        assert ledger.count("t1") == 0
        assert "secret_metric" not in message
        assert "nan" not in message.lower()


class TestTenantLedgerSummary:
    def test_empty_summary(self):
        ledger = TenantLedger(clock=fixed_clock)
        summary = ledger.summary("t1")
        assert summary.total_entries == 0
        assert summary.total_cost == 0.0

    def test_summary_with_entries(self):
        ledger = TenantLedger(clock=fixed_clock)
        ledger.append("t1", "llm", "a1", {"cost": 1.0})
        ledger.append("t1", "llm", "a1", {"cost": 2.0})
        ledger.append("t1", "execution", "a1", {"cost": 0.5})
        summary = ledger.summary("t1")
        assert summary.total_entries == 3
        assert summary.total_cost == 3.5
        assert summary.entry_types["llm"] == 2
        assert summary.entry_types["execution"] == 1


class TestTenantSessions:
    def test_create_session(self):
        ledger = TenantLedger(clock=fixed_clock)
        session = ledger.create_session("s1", "t1", "actor-1")
        assert session.session_id == "s1"
        assert session.tenant_id == "t1"
        assert session.active is True

    def test_get_session(self):
        ledger = TenantLedger(clock=fixed_clock)
        ledger.create_session("s1", "t1", "a1")
        session = ledger.get_session("s1")
        assert session is not None
        assert session.tenant_id == "t1"

    def test_get_missing_session(self):
        ledger = TenantLedger(clock=fixed_clock)
        assert ledger.get_session("nonexistent") is None

    def test_validate_session_tenant(self):
        ledger = TenantLedger(clock=fixed_clock)
        ledger.create_session("s1", "t1", "a1")
        assert ledger.validate_session_tenant("s1", "t1") is True
        assert ledger.validate_session_tenant("s1", "t2") is False

    def test_validate_missing_session(self):
        ledger = TenantLedger(clock=fixed_clock)
        assert ledger.validate_session_tenant("nonexistent", "t1") is False

    def test_tenant_sessions(self):
        ledger = TenantLedger(clock=fixed_clock)
        ledger.create_session("s1", "t1", "a1")
        ledger.create_session("s2", "t1", "a2")
        ledger.create_session("s3", "t2", "a3")
        t1_sessions = ledger.tenant_sessions("t1")
        assert len(t1_sessions) == 2
        assert all(s.tenant_id == "t1" for s in t1_sessions)

    def test_deactivate_session(self):
        ledger = TenantLedger(clock=fixed_clock)
        ledger.create_session("s1", "t1", "a1")
        assert ledger.deactivate_session("s1") is True
        session = ledger.get_session("s1")
        assert session.active is False

    def test_deactivate_missing(self):
        ledger = TenantLedger(clock=fixed_clock)
        assert ledger.deactivate_session("nonexistent") is False


class TestGlobalStats:
    def test_all_tenant_ids(self):
        ledger = TenantLedger(clock=fixed_clock)
        ledger.append("t2", "llm", "a1", {})
        ledger.append("t1", "llm", "a1", {})
        ids = ledger.all_tenant_ids()
        assert ids == ["t1", "t2"]

    def test_global_stats(self):
        ledger = TenantLedger(clock=fixed_clock)
        ledger.append("t1", "llm", "a1", {})
        ledger.append("t2", "llm", "a2", {})
        ledger.create_session("s1", "t1", "a1")
        stats = ledger.global_stats()
        assert stats["tenant_count"] == 2
        assert stats["total_entries"] == 2
        assert stats["total_sessions"] == 1
        assert stats["active_sessions"] == 1
