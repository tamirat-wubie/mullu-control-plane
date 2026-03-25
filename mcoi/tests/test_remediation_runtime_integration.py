"""Comprehensive tests for RemediationRuntimeIntegration bridge."""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.remediation_runtime import RemediationRuntimeEngine
from mcoi_runtime.core.remediation_runtime_integration import (
    RemediationRuntimeIntegration,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def engines():
    """Return (event_spine, remediation_engine, memory_engine, integration)."""
    es = EventSpineEngine()
    re = RemediationRuntimeEngine(es)
    me = MemoryMeshEngine()
    integration = RemediationRuntimeIntegration(re, es, me)
    return es, re, me, integration


# ── Constructor validation (3 tests) ────────────────────────────────


class TestConstructorValidation:
    def test_rejects_wrong_remediation_engine(self):
        es = EventSpineEngine()
        me = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="remediation_engine"):
            RemediationRuntimeIntegration("not-an-engine", es, me)

    def test_rejects_wrong_event_spine(self):
        es = EventSpineEngine()
        re = RemediationRuntimeEngine(es)
        me = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            RemediationRuntimeIntegration(re, "not-an-engine", me)

    def test_rejects_wrong_memory_engine(self):
        es = EventSpineEngine()
        re = RemediationRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            RemediationRuntimeIntegration(re, es, "not-an-engine")


# ── Remediation from case (2 tests) ─────────────────────────────────


class TestRemediationFromCase:
    def test_returns_correct_dict_shape(self, engines):
        _es, _re, _me, integration = engines
        result = integration.remediation_from_case("rem-1", "t1", "case-1")
        assert result["remediation_id"] == "rem-1"
        assert result["tenant_id"] == "t1"
        assert result["type"] == "corrective"
        assert result["priority"] == "medium"
        assert result["source_type"] == "case"
        assert result["source_id"] == "case-1"

    def test_increments_remediation_count(self, engines):
        _es, re, _me, integration = engines
        assert re.remediation_count == 0
        integration.remediation_from_case("rem-1", "t1", "case-1")
        assert re.remediation_count == 1
        integration.remediation_from_case("rem-2", "t1", "case-2")
        assert re.remediation_count == 2


# ── Remediation from finding (2 tests) ──────────────────────────────


class TestRemediationFromFinding:
    def test_returns_correct_dict_shape(self, engines):
        _es, _re, _me, integration = engines
        result = integration.remediation_from_finding("rem-f1", "t1", "find-1")
        assert result["remediation_id"] == "rem-f1"
        assert result["tenant_id"] == "t1"
        assert result["type"] == "corrective"
        assert result["priority"] == "high"
        assert result["source_type"] == "finding"
        assert result["source_id"] == "find-1"

    def test_increments_remediation_count(self, engines):
        _es, re, _me, integration = engines
        assert re.remediation_count == 0
        integration.remediation_from_finding("rem-f1", "t1", "find-1")
        assert re.remediation_count == 1


# ── Remediation from control failure (2 tests) ──────────────────────


class TestRemediationFromControlFailure:
    def test_returns_correct_dict_shape(self, engines):
        _es, _re, _me, integration = engines
        result = integration.remediation_from_control_failure("rem-c1", "t1", "ctrl-1")
        assert result["remediation_id"] == "rem-c1"
        assert result["tenant_id"] == "t1"
        assert result["type"] == "corrective"
        assert result["priority"] == "high"
        assert result["source_type"] == "control_failure"
        assert result["source_id"] == "ctrl-1"

    def test_increments_remediation_count(self, engines):
        _es, re, _me, integration = engines
        integration.remediation_from_control_failure("rem-c1", "t1", "ctrl-1")
        assert re.remediation_count == 1
        integration.remediation_from_control_failure("rem-c2", "t1", "ctrl-2")
        assert re.remediation_count == 2


# ── Remediation from fault campaign (2 tests) ───────────────────────


class TestRemediationFromFaultCampaign:
    def test_returns_correct_dict_shape(self, engines):
        _es, _re, _me, integration = engines
        result = integration.remediation_from_fault_campaign("rem-fc1", "t1", "fc-1")
        assert result["remediation_id"] == "rem-fc1"
        assert result["tenant_id"] == "t1"
        assert result["type"] == "preventive"
        assert result["priority"] == "medium"
        assert result["source_type"] == "fault_campaign"
        assert result["source_id"] == "fc-1"

    def test_increments_remediation_count(self, engines):
        _es, re, _me, integration = engines
        integration.remediation_from_fault_campaign("rem-fc1", "t1", "fc-1")
        assert re.remediation_count == 1


# ── Cross-domain attachment (4 tests) ───────────────────────────────


class TestCrossDomainAttachment:
    def test_attach_to_campaigns_returns_status(self, engines):
        _es, _re, _me, integration = engines
        integration.remediation_from_case("rem-1", "t1", "case-1")
        result = integration.attach_remediation_to_campaigns("rem-1", "camp-1")
        assert result["remediation_id"] == "rem-1"
        assert result["campaign_id"] == "camp-1"
        assert "status" in result
        assert result["status"] == "open"

    def test_attach_to_campaigns_dict_keys(self, engines):
        _es, _re, _me, integration = engines
        integration.remediation_from_finding("rem-f1", "t1", "find-1")
        result = integration.attach_remediation_to_campaigns("rem-f1", "camp-2")
        assert set(result.keys()) == {"remediation_id", "campaign_id", "status"}

    def test_attach_to_portfolio_returns_status_and_priority(self, engines):
        _es, _re, _me, integration = engines
        integration.remediation_from_finding("rem-f1", "t1", "find-1")
        result = integration.attach_remediation_to_portfolio("rem-f1", "port-1")
        assert result["remediation_id"] == "rem-f1"
        assert result["portfolio_id"] == "port-1"
        assert result["status"] == "open"
        assert result["priority"] == "high"

    def test_attach_to_portfolio_dict_keys(self, engines):
        _es, _re, _me, integration = engines
        integration.remediation_from_case("rem-1", "t1", "case-1")
        result = integration.attach_remediation_to_portfolio("rem-1", "port-1")
        assert set(result.keys()) == {
            "remediation_id",
            "portfolio_id",
            "status",
            "priority",
        }


# ── Memory mesh and graph (3 tests) ─────────────────────────────────


class TestMemoryMeshAndGraph:
    def test_attach_to_memory_mesh_creates_record_with_tags(self, engines):
        _es, _re, _me, integration = engines
        integration.remediation_from_case("rem-1", "t1", "case-1")
        mem = integration.attach_remediation_to_memory_mesh("scope-1")
        assert mem.memory_id  # non-empty
        assert mem.title == "Remediation state: scope-1"
        assert "remediation" in mem.tags
        assert "corrective" in mem.tags
        assert "preventive" in mem.tags

    def test_attach_to_graph_returns_all_expected_keys(self, engines):
        _es, _re, _me, integration = engines
        integration.remediation_from_case("rem-1", "t1", "case-1")
        result = integration.attach_remediation_to_graph("scope-1")
        expected_keys = {
            "scope_ref_id",
            "total_remediations",
            "open_remediations",
            "total_corrective",
            "total_preventive",
            "total_verifications",
            "total_reopens",
            "total_decisions",
            "total_violations",
        }
        assert set(result.keys()) == expected_keys

    def test_graph_data_matches_engine_state(self, engines):
        _es, re, _me, integration = engines
        integration.remediation_from_case("rem-1", "t1", "case-1")
        integration.remediation_from_finding("rem-2", "t1", "find-1")
        integration.remediation_from_fault_campaign("rem-3", "t1", "fc-1")

        result = integration.attach_remediation_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"
        assert result["total_remediations"] == re.remediation_count
        assert result["open_remediations"] == re.open_remediation_count
        assert result["total_corrective"] == re.corrective_count
        assert result["total_preventive"] == re.preventive_count
        assert result["total_verifications"] == re.verification_count
        assert result["total_reopens"] == re.reopen_count
        assert result["total_decisions"] == re.decision_count
        assert result["total_violations"] == re.violation_count


# ── Events (1 test) ─────────────────────────────────────────────────


class TestEvents:
    def test_event_count_increases_after_operations(self, engines):
        es, _re, _me, integration = engines
        initial = es.event_count
        integration.remediation_from_case("rem-1", "t1", "case-1")
        after_one = es.event_count
        assert after_one > initial
        integration.remediation_from_finding("rem-2", "t1", "find-1")
        after_two = es.event_count
        assert after_two > after_one


# ── Golden path (1 test) ────────────────────────────────────────────


class TestGoldenPath:
    def test_end_to_end_full_lifecycle(self, engines):
        es, re, _me, integration = engines

        # Create remediations from all four sources
        r1 = integration.remediation_from_case("rem-1", "t1", "case-1")
        assert r1["type"] == "corrective"
        assert r1["priority"] == "medium"
        assert r1["source_type"] == "case"

        r2 = integration.remediation_from_finding("rem-2", "t1", "find-1")
        assert r2["type"] == "corrective"
        assert r2["priority"] == "high"
        assert r2["source_type"] == "finding"

        r3 = integration.remediation_from_control_failure("rem-3", "t1", "ctrl-1")
        assert r3["type"] == "corrective"
        assert r3["priority"] == "high"
        assert r3["source_type"] == "control_failure"

        r4 = integration.remediation_from_fault_campaign("rem-4", "t1", "fc-1")
        assert r4["type"] == "preventive"
        assert r4["priority"] == "medium"
        assert r4["source_type"] == "fault_campaign"

        assert re.remediation_count == 4

        # Attach to campaign and portfolio
        camp = integration.attach_remediation_to_campaigns("rem-1", "camp-1")
        assert camp["status"] == "open"
        assert camp["campaign_id"] == "camp-1"

        port = integration.attach_remediation_to_portfolio("rem-2", "port-1")
        assert port["status"] == "open"
        assert port["priority"] == "high"
        assert port["portfolio_id"] == "port-1"

        # Attach to memory mesh
        mem = integration.attach_remediation_to_memory_mesh("scope-golden")
        assert "remediation" in mem.tags
        assert mem.content["total_remediations"] == 4

        # Attach to graph
        graph = integration.attach_remediation_to_graph("scope-golden")
        assert graph["total_remediations"] == 4
        assert graph["open_remediations"] == 4
        assert graph["total_corrective"] == 0  # no corrective *actions* added
        assert graph["total_preventive"] == 0  # no preventive *actions* added

        # Events were emitted throughout
        assert es.event_count > 0


# ── Additional edge-case tests to reach ~30 ──────────────────────────


class TestEdgeCases:
    def test_remediation_from_case_custom_title(self, engines):
        _es, _re, _me, integration = engines
        result = integration.remediation_from_case(
            "rem-ct", "t1", "case-ct", title="Custom title"
        )
        assert result["remediation_id"] == "rem-ct"
        assert result["source_type"] == "case"

    def test_remediation_from_finding_with_case_id(self, engines):
        _es, _re, _me, integration = engines
        result = integration.remediation_from_finding(
            "rem-fci", "t1", "find-fci", case_id="case-linked"
        )
        assert result["source_type"] == "finding"
        assert result["source_id"] == "find-fci"

    def test_memory_mesh_content_has_zero_counts_when_empty(self, engines):
        _es, _re, _me, integration = engines
        mem = integration.attach_remediation_to_memory_mesh("scope-empty")
        assert mem.content["total_remediations"] == 0
        assert mem.content["open_remediations"] == 0
        assert mem.content["total_corrective"] == 0
        assert mem.content["total_preventive"] == 0

    def test_graph_returns_zero_counts_when_empty(self, engines):
        _es, _re, _me, integration = engines
        result = integration.attach_remediation_to_graph("scope-empty")
        assert result["total_remediations"] == 0
        assert result["open_remediations"] == 0

    def test_multiple_campaign_attachments(self, engines):
        _es, _re, _me, integration = engines
        integration.remediation_from_case("rem-1", "t1", "case-1")
        c1 = integration.attach_remediation_to_campaigns("rem-1", "camp-1")
        c2 = integration.attach_remediation_to_campaigns("rem-1", "camp-2")
        assert c1["campaign_id"] == "camp-1"
        assert c2["campaign_id"] == "camp-2"

    def test_multiple_portfolio_attachments(self, engines):
        _es, _re, _me, integration = engines
        integration.remediation_from_case("rem-1", "t1", "case-1")
        p1 = integration.attach_remediation_to_portfolio("rem-1", "port-1")
        p2 = integration.attach_remediation_to_portfolio("rem-1", "port-2")
        assert p1["portfolio_id"] == "port-1"
        assert p2["portfolio_id"] == "port-2"

    def test_memory_mesh_record_scope_ref_id(self, engines):
        _es, _re, _me, integration = engines
        mem = integration.attach_remediation_to_memory_mesh("my-scope")
        assert mem.scope_ref_id == "my-scope"

    def test_memory_mesh_record_confidence(self, engines):
        _es, _re, _me, integration = engines
        mem = integration.attach_remediation_to_memory_mesh("conf-scope")
        assert mem.confidence == 1.0

    def test_attach_campaigns_unknown_remediation(self, engines):
        _es, _re, _me, integration = engines
        with pytest.raises(RuntimeCoreInvariantError):
            integration.attach_remediation_to_campaigns("nonexistent", "camp-1")

    def test_attach_portfolio_unknown_remediation(self, engines):
        _es, _re, _me, integration = engines
        with pytest.raises(RuntimeCoreInvariantError):
            integration.attach_remediation_to_portfolio("nonexistent", "port-1")
