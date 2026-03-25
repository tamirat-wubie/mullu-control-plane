"""Purpose: verify RiskComplianceIntegration bridge — scope assessments (campaign,
    program, portfolio, connector, domain_pack), evidence binding (artifact,
    memory, event), failure escalation/blocking, memory mesh attachment, and
    operational graph attachment.
Governance scope: risk/compliance integration tests only.
Dependencies: RiskComplianceIntegration, RiskComplianceEngine, EventSpineEngine,
    MemoryMeshEngine, and real risk/compliance contracts.
Invariants:
  - All tests are deterministic.
  - No network. No real persistence.
  - Uses real contract types and engine implementations.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.risk_compliance import RiskComplianceEngine
from mcoi_runtime.core.risk_compliance_integration import RiskComplianceIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.risk_compliance import (
    RiskSeverity,
    RiskCategory,
    ControlStatus,
    ControlTestStatus,
    ExceptionStatus,
    ComplianceDisposition,
    EvidenceSourceKind,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def env():
    es = EventSpineEngine()
    mm = MemoryMeshEngine()
    eng = RiskComplianceEngine(es)
    integ = RiskComplianceIntegration(eng, es, mm)
    return es, mm, eng, integ


def _seed_risk_and_control(eng: RiskComplianceEngine, scope_ref_id: str):
    """Register a risk, a control, and bind the control to the scope."""
    eng.register_risk(
        "risk-1", "Test risk",
        severity=RiskSeverity.HIGH,
        category=RiskCategory.COMPLIANCE,
        likelihood=0.6,
        impact=0.8,
        scope_ref_id=scope_ref_id,
    )
    eng.register_control("ctrl-1", "Test control", requirement_id="req-1")
    eng.bind_control("bind-1", "ctrl-1", scope_ref_id, scope_type="campaign")


def _seed_multiple_risks(eng: RiskComplianceEngine, scope_ref_id: str):
    """Register multiple risks at different severities plus controls."""
    eng.register_risk(
        "risk-crit", "Critical risk",
        severity=RiskSeverity.CRITICAL,
        category=RiskCategory.SECURITY,
        likelihood=0.9,
        impact=0.9,
        scope_ref_id=scope_ref_id,
    )
    eng.register_risk(
        "risk-high", "High risk",
        severity=RiskSeverity.HIGH,
        category=RiskCategory.COMPLIANCE,
        likelihood=0.5,
        impact=0.7,
        scope_ref_id=scope_ref_id,
    )
    eng.register_control("ctrl-a", "Control A")
    eng.register_control("ctrl-b", "Control B")
    eng.bind_control("bind-a", "ctrl-a", scope_ref_id, scope_type="test")
    eng.bind_control("bind-b", "ctrl-b", scope_ref_id, scope_type="test")


# ---------------------------------------------------------------------------
# 1. Constructor validation (3 tests)
# ---------------------------------------------------------------------------


class TestConstructorValidation:

    def test_invalid_risk_engine_type(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="risk_engine"):
            RiskComplianceIntegration("not-an-engine", es, mm)

    def test_invalid_event_spine_type(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        eng = RiskComplianceEngine(es)
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            RiskComplianceIntegration(eng, "not-a-spine", mm)

    def test_invalid_memory_engine_type(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        eng = RiskComplianceEngine(es)
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            RiskComplianceIntegration(eng, es, "not-a-memory")


# ---------------------------------------------------------------------------
# 2. Scope assessments — each assess_* with risks and empty (10 tests)
# ---------------------------------------------------------------------------


class TestAssessCampaign:

    def test_campaign_with_risks_and_controls(self, env):
        es, mm, eng, integ = env
        _seed_risk_and_control(eng, "campaign-100")
        result = integ.assess_campaign("assess-c1", "campaign-100")
        assert result["scope_type"] == "campaign"
        assert result["assessment_id"] == "assess-c1"
        assert result["scope_ref_id"] == "campaign-100"
        assert result["overall_severity"] == RiskSeverity.HIGH.value
        assert result["risk_count"] == 1
        assert result["risk_score"] > 0
        # Snapshot should be present since there is a binding
        assert "disposition" in result
        assert "compliance_pct" in result

    def test_campaign_empty_scope(self, env):
        _es, _mm, _eng, integ = env
        result = integ.assess_campaign("assess-c2", "campaign-empty")
        assert result["scope_type"] == "campaign"
        assert result["overall_severity"] == RiskSeverity.LOW.value
        assert result["risk_count"] == 0
        assert result["risk_score"] == 0.0


class TestAssessProgram:

    def test_program_with_risks_and_controls(self, env):
        es, mm, eng, integ = env
        _seed_risk_and_control(eng, "program-200")
        result = integ.assess_program("assess-p1", "program-200")
        assert result["scope_type"] == "program"
        assert result["overall_severity"] == RiskSeverity.HIGH.value
        assert result["risk_count"] == 1
        assert result["risk_score"] > 0

    def test_program_empty_scope(self, env):
        _es, _mm, _eng, integ = env
        result = integ.assess_program("assess-p2", "program-empty")
        assert result["scope_type"] == "program"
        assert result["overall_severity"] == RiskSeverity.LOW.value
        assert result["risk_count"] == 0


class TestAssessPortfolio:

    def test_portfolio_with_risks_and_controls(self, env):
        es, mm, eng, integ = env
        _seed_risk_and_control(eng, "portfolio-300")
        result = integ.assess_portfolio("assess-pf1", "portfolio-300")
        assert result["scope_type"] == "portfolio"
        assert result["overall_severity"] == RiskSeverity.HIGH.value
        assert result["risk_count"] == 1

    def test_portfolio_empty_scope(self, env):
        _es, _mm, _eng, integ = env
        result = integ.assess_portfolio("assess-pf2", "portfolio-empty")
        assert result["scope_type"] == "portfolio"
        assert result["overall_severity"] == RiskSeverity.LOW.value
        assert result["risk_count"] == 0


class TestAssessConnector:

    def test_connector_with_risks_and_controls(self, env):
        es, mm, eng, integ = env
        _seed_risk_and_control(eng, "connector-400")
        result = integ.assess_connector("assess-cn1", "connector-400")
        assert result["scope_type"] == "connector"
        assert result["overall_severity"] == RiskSeverity.HIGH.value
        assert result["risk_count"] == 1

    def test_connector_empty_scope(self, env):
        _es, _mm, _eng, integ = env
        result = integ.assess_connector("assess-cn2", "connector-empty")
        assert result["scope_type"] == "connector"
        assert result["overall_severity"] == RiskSeverity.LOW.value
        assert result["risk_count"] == 0


class TestAssessDomainPack:

    def test_domain_pack_with_risks_and_controls(self, env):
        es, mm, eng, integ = env
        _seed_risk_and_control(eng, "dp-500")
        result = integ.assess_domain_pack("assess-dp1", "dp-500")
        assert result["scope_type"] == "domain_pack"
        assert result["overall_severity"] == RiskSeverity.HIGH.value
        assert result["risk_count"] == 1

    def test_domain_pack_empty_scope(self, env):
        _es, _mm, _eng, integ = env
        result = integ.assess_domain_pack("assess-dp2", "dp-empty")
        assert result["scope_type"] == "domain_pack"
        assert result["overall_severity"] == RiskSeverity.LOW.value
        assert result["risk_count"] == 0


# ---------------------------------------------------------------------------
# 3. Evidence binding (3 tests)
# ---------------------------------------------------------------------------


class TestBindArtifactEvidence:

    def test_bind_artifact_evidence(self, env):
        es, mm, eng, integ = env
        eng.register_control("ctrl-ev1", "Evidence control")
        result = integ.bind_artifact_evidence(
            "test-art1", "ctrl-ev1", ["artifact-a", "artifact-b"],
            tester="alice", notes="artifact check",
        )
        assert result["evidence_kind"] == EvidenceSourceKind.ARTIFACT.value
        assert result["evidence_count"] == 2
        assert result["status"] == ControlTestStatus.PASSED.value
        assert result["test_id"] == "test-art1"
        assert result["control_id"] == "ctrl-ev1"


class TestBindMemoryEvidence:

    def test_bind_memory_evidence(self, env):
        es, mm, eng, integ = env
        eng.register_control("ctrl-ev2", "Memory evidence control")
        result = integ.bind_memory_evidence(
            "test-mem1", "ctrl-ev2", ["mem-ref-1"],
            tester="bob", notes="memory check",
        )
        assert result["evidence_kind"] == EvidenceSourceKind.MEMORY.value
        assert result["evidence_count"] == 1
        assert result["status"] == ControlTestStatus.PASSED.value


class TestBindEventEvidence:

    def test_bind_event_evidence(self, env):
        es, mm, eng, integ = env
        eng.register_control("ctrl-ev3", "Event evidence control")
        result = integ.bind_event_evidence(
            "test-evt1", "ctrl-ev3", ["evt-ref-1", "evt-ref-2", "evt-ref-3"],
            tester="carol", notes="event check",
        )
        assert result["evidence_kind"] == EvidenceSourceKind.EVENT.value
        assert result["evidence_count"] == 3
        assert result["status"] == ControlTestStatus.PASSED.value


# ---------------------------------------------------------------------------
# 4. Failure escalation (3 tests)
# ---------------------------------------------------------------------------


class TestBlockOrEscalateFromFailure:

    def test_critical_severity_blocks_and_escalates(self, env):
        es, mm, eng, integ = env
        eng.register_control("ctrl-fail-c", "Critical failure control")
        result = integ.block_or_escalate_from_failure(
            "fail-crit", "ctrl-fail-c",
            test_id="t-c",
            scope_ref_id="scope-crit",
            severity=RiskSeverity.CRITICAL,
        )
        assert result["blocked"] is True
        assert result["escalated"] is True
        assert result["severity"] == RiskSeverity.CRITICAL.value
        assert result["failure_id"] == "fail-crit"
        assert result["control_id"] == "ctrl-fail-c"
        # A risk should have been registered
        assert result["risk_id"] == "fail-crit-risk"
        # Verify risk was actually registered on the engine
        risks = eng.risks_for_scope("scope-crit")
        assert len(risks) == 1
        assert risks[0].severity == RiskSeverity.CRITICAL

    def test_high_severity_escalates_without_block(self, env):
        es, mm, eng, integ = env
        eng.register_control("ctrl-fail-h", "High failure control")
        result = integ.block_or_escalate_from_failure(
            "fail-high", "ctrl-fail-h",
            test_id="t-h",
            scope_ref_id="scope-high",
            severity=RiskSeverity.HIGH,
        )
        assert result["escalated"] is True
        assert result["blocked"] is False
        assert result["risk_id"] == "fail-high-risk"
        risks = eng.risks_for_scope("scope-high")
        assert len(risks) == 1
        assert risks[0].severity == RiskSeverity.HIGH

    def test_medium_severity_logged_no_escalation(self, env):
        es, mm, eng, integ = env
        eng.register_control("ctrl-fail-m", "Medium failure control")
        result = integ.block_or_escalate_from_failure(
            "fail-med", "ctrl-fail-m",
            test_id="t-m",
            scope_ref_id="scope-med",
            severity=RiskSeverity.MEDIUM,
        )
        assert result["escalated"] is False
        assert result["blocked"] is False
        # No risk should be registered for medium severity
        assert result["risk_id"] == ""
        risks = eng.risks_for_scope("scope-med")
        assert len(risks) == 0


# ---------------------------------------------------------------------------
# 5. attach_risk_state_to_memory_mesh (1 test)
# ---------------------------------------------------------------------------


class TestAttachRiskStateToMemoryMesh:

    def test_attaches_memory_record_with_tags(self, env):
        es, mm, eng, integ = env
        eng.register_control("ctrl-mm", "Memory mesh control")
        eng.register_risk(
            "risk-mm", "Memory risk",
            severity=RiskSeverity.MEDIUM,
            scope_ref_id="scope-mm",
        )
        mem = integ.attach_risk_state_to_memory_mesh("scope-mm")
        assert isinstance(mem, MemoryRecord)
        assert "risk" in mem.tags
        assert "compliance" in mem.tags
        assert "controls" in mem.tags
        assert mem.scope_ref_id == "scope-mm"
        # Content contains expected keys
        assert mem.content["total_risks"] == 1
        assert mem.content["total_controls"] == 1


# ---------------------------------------------------------------------------
# 6. attach_risk_state_to_graph (1 test)
# ---------------------------------------------------------------------------


class TestAttachRiskStateToGraph:

    def test_returns_graph_dict_with_expected_keys(self, env):
        es, mm, eng, integ = env
        scope_id = "scope-graph"
        eng.register_control("ctrl-g1", "Graph control")
        eng.bind_control("bind-g1", "ctrl-g1", scope_id)
        eng.register_risk(
            "risk-g1", "Graph risk",
            severity=RiskSeverity.LOW,
            scope_ref_id=scope_id,
        )
        # Record a failure in scope
        eng.record_control_failure(
            "fail-g1", "ctrl-g1",
            scope_ref_id=scope_id,
            severity=RiskSeverity.LOW,
        )
        result = integ.attach_risk_state_to_graph(scope_id)
        assert result["scope_ref_id"] == scope_id
        assert "failed_control_ids" in result
        assert "scope_failure_count" in result
        assert result["scope_failure_count"] == 1
        assert "scope_active_exceptions" in result
        assert result["scope_active_exceptions"] == 0
        assert result["total_risks"] == 1
        assert result["total_controls"] == 1
        assert result["total_bindings"] == 1


# ---------------------------------------------------------------------------
# 7. End-to-end golden scenario (1 test)
# ---------------------------------------------------------------------------


class TestEndToEndGoldenScenario:

    def test_full_lifecycle(self, env):
        es, mm, eng, integ = env
        scope = "campaign-golden"

        # Step 1: Register risks
        eng.register_risk(
            "g-risk-1", "Golden risk critical",
            severity=RiskSeverity.CRITICAL,
            category=RiskCategory.SECURITY,
            likelihood=0.9,
            impact=0.95,
            scope_ref_id=scope,
        )
        eng.register_risk(
            "g-risk-2", "Golden risk medium",
            severity=RiskSeverity.MEDIUM,
            category=RiskCategory.OPERATIONAL,
            likelihood=0.3,
            impact=0.4,
            scope_ref_id=scope,
        )

        # Step 2: Register controls and bind to scope
        eng.register_control("g-ctrl-1", "Golden control A", requirement_id="g-req-1")
        eng.register_control("g-ctrl-2", "Golden control B", requirement_id="g-req-1")
        eng.bind_control("g-bind-1", "g-ctrl-1", scope, scope_type="campaign")
        eng.bind_control("g-bind-2", "g-ctrl-2", scope, scope_type="campaign")

        # Step 3: Register a requirement
        eng.register_requirement(
            "g-req-1", "Golden requirement",
            control_ids=["g-ctrl-1", "g-ctrl-2"],
        )

        # Step 4: Bind evidence via integration
        art_result = integ.bind_artifact_evidence(
            "g-test-1", "g-ctrl-1", ["art-1"],
            tester="tester-1", notes="artifact pass",
        )
        assert art_result["status"] == ControlTestStatus.PASSED.value

        mem_result = integ.bind_memory_evidence(
            "g-test-2", "g-ctrl-2", ["mem-1", "mem-2"],
            tester="tester-2", notes="memory pass",
        )
        assert mem_result["status"] == ControlTestStatus.PASSED.value

        # Step 5: Record a failing test on ctrl-2 (simulates later failure)
        eng.record_control_test(
            "g-test-3", "g-ctrl-2", ControlTestStatus.FAILED,
            tester="tester-3", notes="found issue",
        )

        # Step 6: Escalate the failure via integration
        esc_result = integ.block_or_escalate_from_failure(
            "g-fail-1", "g-ctrl-2",
            test_id="g-test-3",
            scope_ref_id=scope,
            severity=RiskSeverity.CRITICAL,
        )
        assert esc_result["blocked"] is True
        assert esc_result["escalated"] is True

        # Step 7: Assess the campaign
        assess_result = integ.assess_campaign("g-assess-1", scope)
        assert assess_result["scope_type"] == "campaign"
        assert assess_result["overall_severity"] == RiskSeverity.CRITICAL.value
        assert assess_result["risk_count"] >= 2  # original 2 + 1 from escalation

        # Step 8: Generate assurance report
        report = eng.assurance_report("g-report-1", scope)
        assert report.total_controls == 2
        assert report.failing_controls >= 1
        assert report.overall_risk_severity == RiskSeverity.CRITICAL

        # Step 9: Attach to memory mesh
        mem_record = integ.attach_risk_state_to_memory_mesh(scope)
        assert isinstance(mem_record, MemoryRecord)
        assert mem_record.content["total_risks"] >= 3
        assert mem_record.content["total_failures"] >= 1
        assert len(mem_record.content["failed_control_ids"]) >= 1

        # Step 10: Attach to graph
        graph_result = integ.attach_risk_state_to_graph(scope)
        assert graph_result["scope_failure_count"] >= 1
        assert len(graph_result["failed_control_ids"]) >= 1


# ---------------------------------------------------------------------------
# 8. Events emitted check (1 test)
# ---------------------------------------------------------------------------


class TestEventsEmitted:

    def test_operations_emit_events(self, env):
        es, mm, eng, integ = env
        scope = "scope-events"

        initial_count = es.event_count

        # Seed data
        eng.register_risk(
            "ev-risk", "Event risk",
            severity=RiskSeverity.HIGH,
            scope_ref_id=scope,
        )
        eng.register_control("ev-ctrl", "Event control")
        eng.bind_control("ev-bind", "ev-ctrl", scope)

        count_after_seed = es.event_count
        assert count_after_seed > initial_count

        # Integration operations should each emit events
        integ.assess_campaign("ev-assess", scope)
        count_after_assess = es.event_count
        assert count_after_assess > count_after_seed

        integ.bind_artifact_evidence(
            "ev-test", "ev-ctrl", ["ref-1"],
            tester="t", notes="n",
        )
        count_after_bind = es.event_count
        assert count_after_bind > count_after_assess

        integ.block_or_escalate_from_failure(
            "ev-fail", "ev-ctrl",
            scope_ref_id=scope,
            severity=RiskSeverity.HIGH,
        )
        count_after_esc = es.event_count
        assert count_after_esc > count_after_bind

        integ.attach_risk_state_to_memory_mesh(scope)
        count_after_mem = es.event_count
        assert count_after_mem > count_after_esc


# ---------------------------------------------------------------------------
# Additional edge-case tests to round out coverage
# ---------------------------------------------------------------------------


class TestAssessWithCriticalRisks:
    """Extra tests validating severity aggregation through integration."""

    def test_campaign_critical_severity_propagates(self, env):
        es, mm, eng, integ = env
        scope = "campaign-critical"
        _seed_multiple_risks(eng, scope)
        result = integ.assess_campaign("assess-mc1", scope)
        assert result["overall_severity"] == RiskSeverity.CRITICAL.value
        assert result["risk_count"] == 2

    def test_program_critical_severity_propagates(self, env):
        es, mm, eng, integ = env
        scope = "program-critical"
        _seed_multiple_risks(eng, scope)
        result = integ.assess_program("assess-mp1", scope)
        assert result["overall_severity"] == RiskSeverity.CRITICAL.value

    def test_portfolio_critical_severity_propagates(self, env):
        es, mm, eng, integ = env
        scope = "portfolio-critical"
        _seed_multiple_risks(eng, scope)
        result = integ.assess_portfolio("assess-mpf1", scope)
        assert result["overall_severity"] == RiskSeverity.CRITICAL.value

    def test_connector_critical_severity_propagates(self, env):
        es, mm, eng, integ = env
        scope = "connector-critical"
        _seed_multiple_risks(eng, scope)
        result = integ.assess_connector("assess-mcn1", scope)
        assert result["overall_severity"] == RiskSeverity.CRITICAL.value

    def test_domain_pack_critical_severity_propagates(self, env):
        es, mm, eng, integ = env
        scope = "dp-critical"
        _seed_multiple_risks(eng, scope)
        result = integ.assess_domain_pack("assess-mdp1", scope)
        assert result["overall_severity"] == RiskSeverity.CRITICAL.value


class TestComplianceSnapshotViaAssess:
    """Verify compliance disposition and pct flow through assess_* results."""

    def test_campaign_fully_compliant_disposition(self, env):
        es, mm, eng, integ = env
        scope = "campaign-compliant"
        eng.register_control("comp-ctrl", "Compliant control")
        eng.bind_control("comp-bind", "comp-ctrl", scope, enforced=True)
        # Control starts ACTIVE, so compliance snapshot should show compliant
        result = integ.assess_campaign("assess-comp", scope)
        assert result.get("disposition") == ComplianceDisposition.COMPLIANT.value
        assert result.get("compliance_pct") == 100.0

    def test_campaign_partially_compliant_disposition(self, env):
        es, mm, eng, integ = env
        scope = "campaign-partial"
        eng.register_control("part-ctrl-a", "Partial A")
        eng.register_control("part-ctrl-b", "Partial B")
        eng.bind_control("part-bind-a", "part-ctrl-a", scope)
        eng.bind_control("part-bind-b", "part-ctrl-b", scope)
        # Fail one control
        eng.record_control_test(
            "part-test-fail", "part-ctrl-b", ControlTestStatus.FAILED,
        )
        result = integ.assess_campaign("assess-partial", scope)
        assert result.get("disposition") == ComplianceDisposition.PARTIALLY_COMPLIANT.value
        assert result.get("compliance_pct") == 50.0


class TestEvidenceBindingDefaults:
    """Verify default tester/notes behavior for evidence binding."""

    def test_artifact_evidence_default_notes(self, env):
        es, mm, eng, integ = env
        eng.register_control("ctrl-def1", "Default notes control")
        result = integ.bind_artifact_evidence("t-def1", "ctrl-def1", ["a1"])
        assert result["evidence_kind"] == EvidenceSourceKind.ARTIFACT.value
        assert result["evidence_count"] == 1

    def test_memory_evidence_default_notes(self, env):
        es, mm, eng, integ = env
        eng.register_control("ctrl-def2", "Default notes control 2")
        result = integ.bind_memory_evidence("t-def2", "ctrl-def2", ["m1"])
        assert result["evidence_kind"] == EvidenceSourceKind.MEMORY.value

    def test_event_evidence_default_notes(self, env):
        es, mm, eng, integ = env
        eng.register_control("ctrl-def3", "Default notes control 3")
        result = integ.bind_event_evidence("t-def3", "ctrl-def3", ["e1"])
        assert result["evidence_kind"] == EvidenceSourceKind.EVENT.value


class TestGraphWithExceptions:
    """Verify active exceptions appear in graph attachment."""

    def test_graph_counts_active_exceptions(self, env):
        es, mm, eng, integ = env
        scope = "scope-exc"
        eng.register_control("ctrl-exc", "Exception control")
        eng.bind_control("bind-exc", "ctrl-exc", scope)
        exc = eng.request_exception(
            "exc-1", "ctrl-exc",
            scope_ref_id=scope,
            reason="temporary waiver",
        )
        eng.approve_exception("exc-1", approved_by="manager")
        result = integ.attach_risk_state_to_graph(scope)
        assert result["scope_active_exceptions"] == 1


class TestMemoryMeshContentKeys:
    """Verify all expected keys in memory mesh content."""

    def test_memory_content_has_all_summary_keys(self, env):
        es, mm, eng, integ = env
        scope = "scope-keys"
        eng.register_control("ctrl-k1", "Key control")
        eng.register_requirement("req-k1", "Key requirement", control_ids=["ctrl-k1"])
        eng.bind_control("bind-k1", "ctrl-k1", scope)
        eng.register_risk("risk-k1", "Key risk", scope_ref_id=scope)
        mem = integ.attach_risk_state_to_memory_mesh(scope)
        content = mem.content
        expected_keys = {
            "scope_ref_id",
            "total_risks",
            "total_requirements",
            "total_controls",
            "total_bindings",
            "total_tests",
            "total_exceptions",
            "total_failures",
            "failed_control_ids",
        }
        assert expected_keys.issubset(set(content.keys()))
        assert content["scope_ref_id"] == scope
        assert content["total_risks"] == 1
        assert content["total_requirements"] == 1
        assert content["total_controls"] == 1
        assert content["total_bindings"] == 1
