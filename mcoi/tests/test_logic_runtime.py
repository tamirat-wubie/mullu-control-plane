"""Smoke tests for Phase 108: Logic / Proof / Truth-Maintenance Runtime.

Covers: contracts, engine lifecycle, derive_conclusion, assumption retraction,
contradiction detection, belief revision, violation detection, assessment,
snapshot, closure report, integration bridge, memory mesh, and graph.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.logic_runtime import LogicRuntimeEngine
from mcoi_runtime.core.logic_runtime_integration import LogicRuntimeIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.logic_runtime import (
    AssumptionDisposition,
    AssumptionRecord,
    ContradictionRecord,
    ContradictionSeverity,
    InferenceRule,
    LogicAssessment,
    LogicClosureReport,
    LogicSnapshot,
    LogicalStatement,
    LogicalStatus,
    ProofRecord,
    ProofStatus,
    RevisionDisposition,
    RevisionRecord,
    StatementKind,
    TruthMaintenanceDecision,
)


# =====================================================================
# Fixtures
# =====================================================================

TS = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(TS)


@pytest.fixture
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture
def engine(spine: EventSpineEngine, clock: FixedClock) -> LogicRuntimeEngine:
    return LogicRuntimeEngine(spine, clock=clock)


@pytest.fixture
def memory() -> MemoryMeshEngine:
    return MemoryMeshEngine()


# =====================================================================
# 1. Contract smoke tests
# =====================================================================


class TestContracts:
    def test_logical_statement_valid(self):
        stmt = LogicalStatement(
            statement_id="s1", tenant_id="t1", kind=StatementKind.FACT,
            content="sky is blue", status=LogicalStatus.ASSERTED, created_at=TS,
        )
        assert stmt.statement_id == "s1"
        assert stmt.kind == StatementKind.FACT

    def test_logical_statement_empty_id_raises(self):
        with pytest.raises(ValueError):
            LogicalStatement(
                statement_id="", tenant_id="t1", kind=StatementKind.FACT,
                content="sky is blue", created_at=TS,
            )

    def test_inference_rule_valid(self):
        rule = InferenceRule(
            rule_id="r1", tenant_id="t1", antecedent="A", consequent="B",
            confidence=0.9, created_at=TS,
        )
        assert rule.confidence == 0.9

    def test_inference_rule_confidence_out_of_range(self):
        with pytest.raises(ValueError):
            InferenceRule(
                rule_id="r1", tenant_id="t1", antecedent="A", consequent="B",
                confidence=1.5, created_at=TS,
            )

    def test_proof_record_valid(self):
        proof = ProofRecord(
            proof_id="p1", tenant_id="t1", conclusion_ref="s1", rule_ref="r1",
            status=ProofStatus.VALID, step_count=3, created_at=TS,
        )
        assert proof.step_count == 3

    def test_proof_record_negative_steps_raises(self):
        with pytest.raises(ValueError):
            ProofRecord(
                proof_id="p1", tenant_id="t1", conclusion_ref="s1", rule_ref="r1",
                step_count=-1, created_at=TS,
            )

    def test_assumption_record_valid(self):
        a = AssumptionRecord(
            assumption_id="a1", tenant_id="t1", statement_ref="s1",
            disposition=AssumptionDisposition.ACTIVE, justification="because",
            created_at=TS,
        )
        assert a.disposition == AssumptionDisposition.ACTIVE

    def test_contradiction_record_valid(self):
        c = ContradictionRecord(
            contradiction_id="c1", tenant_id="t1",
            statement_a_ref="s1", statement_b_ref="s2",
            severity=ContradictionSeverity.HIGH, resolved=False, detected_at=TS,
        )
        assert c.severity == ContradictionSeverity.HIGH
        assert c.resolved is False

    def test_contradiction_record_bad_bool_raises(self):
        with pytest.raises(ValueError) as exc:
            ContradictionRecord(
                contradiction_id="c1", tenant_id="t1",
                statement_a_ref="s1", statement_b_ref="s2",
                resolved=1, detected_at=TS,
            )
        assert str(exc.value) == "value must be a boolean flag"
        assert "resolved" not in str(exc.value)
        assert str(exc.value) != "resolved must be a bool"

    def test_revision_record_valid(self):
        r = RevisionRecord(
            revision_id="rv1", tenant_id="t1", statement_ref="s1",
            disposition=RevisionDisposition.ACCEPTED, reason="resolved",
            revised_at=TS,
        )
        assert r.disposition == RevisionDisposition.ACCEPTED

    def test_truth_maintenance_decision_valid(self):
        d = TruthMaintenanceDecision(
            decision_id="d1", tenant_id="t1", contradiction_ref="c1",
            disposition=RevisionDisposition.MERGED, reason="merged",
            decided_at=TS,
        )
        assert d.disposition == RevisionDisposition.MERGED

    def test_logic_assessment_valid(self):
        a = LogicAssessment(
            assessment_id="la1", tenant_id="t1",
            total_statements=10, total_proofs=5, total_contradictions=1,
            consistency_rate=0.9, assessed_at=TS,
        )
        assert a.total_statements == 10

    def test_logic_snapshot_valid(self):
        s = LogicSnapshot(
            snapshot_id="ls1", tenant_id="t1",
            total_statements=5, total_rules=3, total_proofs=2,
            total_assumptions=1, total_contradictions=0, total_violations=0,
            captured_at=TS,
        )
        assert s.total_rules == 3

    def test_logic_closure_report_valid(self):
        r = LogicClosureReport(
            report_id="lcr1", tenant_id="t1",
            total_statements=5, total_proofs=2, total_contradictions=0,
            total_revisions=1, total_violations=0, created_at=TS,
        )
        assert r.total_revisions == 1

    def test_all_enums_have_correct_counts(self):
        assert len(LogicalStatus) == 5
        assert len(StatementKind) == 5
        assert len(ProofStatus) == 4
        assert len(AssumptionDisposition) == 4
        assert len(ContradictionSeverity) == 4
        assert len(RevisionDisposition) == 4

    def test_to_dict_roundtrip(self):
        stmt = LogicalStatement(
            statement_id="s1", tenant_id="t1", kind=StatementKind.FACT,
            content="sky is blue", created_at=TS,
        )
        d = stmt.to_dict()
        assert d["statement_id"] == "s1"
        assert d["kind"] == StatementKind.FACT

    def test_to_json_dict(self):
        stmt = LogicalStatement(
            statement_id="s1", tenant_id="t1", kind=StatementKind.FACT,
            content="sky is blue", created_at=TS,
        )
        d = stmt.to_json_dict()
        assert d["kind"] == "fact"

    def test_to_json_string(self):
        stmt = LogicalStatement(
            statement_id="s1", tenant_id="t1", kind=StatementKind.FACT,
            content="sky is blue", created_at=TS,
        )
        j = stmt.to_json()
        assert '"fact"' in j


# =====================================================================
# 2. Engine constructor
# =====================================================================


class TestEngineConstructor:
    def test_valid(self, spine, clock):
        eng = LogicRuntimeEngine(spine, clock=clock)
        assert eng.statement_count == 0

    def test_none_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            LogicRuntimeEngine(None)

    def test_string_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            LogicRuntimeEngine("bad")


# =====================================================================
# 3. Engine lifecycle
# =====================================================================


class TestEngineLifecycle:
    def test_register_statement(self, engine):
        stmt = engine.register_statement("s1", "t1", StatementKind.FACT, "sky is blue")
        assert stmt.statement_id == "s1"
        assert engine.statement_count == 1

    def test_duplicate_statement_raises(self, engine):
        engine.register_statement("s1", "t1", StatementKind.FACT, "sky is blue")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_statement("s1", "t1", StatementKind.FACT, "sky is blue")

    def test_register_rule(self, engine):
        rule = engine.register_rule("r1", "t1", "A", "B", 0.95)
        assert rule.rule_id == "r1"
        assert engine.rule_count == 1

    def test_derive_conclusion(self, engine):
        engine.register_statement("s1", "t1", StatementKind.FACT, "A")
        engine.register_rule("r1", "t1", "A", "B", 0.95)
        conclusion, proof = engine.derive_conclusion("t1", "r1", "s1")
        assert conclusion.content == "B"
        assert conclusion.status == LogicalStatus.DERIVED
        assert proof.status == ProofStatus.VALID
        assert engine.statement_count == 2
        assert engine.proof_count == 1

    def test_derive_wrong_antecedent_raises(self, engine):
        engine.register_statement("s1", "t1", StatementKind.FACT, "X")
        engine.register_rule("r1", "t1", "A", "B")
        with pytest.raises(RuntimeCoreInvariantError, match="does not match"):
            engine.derive_conclusion("t1", "r1", "s1")

    def test_record_proof(self, engine):
        proof = engine.record_proof("p1", "t1", "s1", "r1", ProofStatus.PENDING, 2)
        assert proof.step_count == 2
        assert engine.proof_count == 1

    def test_register_assumption(self, engine):
        engine.register_statement("s1", "t1", StatementKind.ASSUMPTION, "rain tomorrow")
        a = engine.register_assumption("a1", "t1", "s1", "weather forecast")
        assert a.disposition == AssumptionDisposition.ACTIVE
        assert engine.assumption_count == 1

    def test_retract_assumption(self, engine):
        engine.register_statement("s1", "t1", StatementKind.ASSUMPTION, "rain tomorrow")
        engine.register_assumption("a1", "t1", "s1", "weather forecast")
        retracted = engine.retract_assumption("a1")
        assert retracted.disposition == AssumptionDisposition.RETRACTED

    def test_detect_contradictions(self, engine):
        engine.register_statement("s1", "t1", StatementKind.FACT, "sky is blue")
        engine.register_statement("s2", "t1", StatementKind.FACT, "NOT sky is blue")
        contrs = engine.detect_contradictions("t1")
        assert len(contrs) == 1
        assert engine.contradiction_count == 1

    def test_detect_contradictions_idempotent(self, engine):
        engine.register_statement("s1", "t1", StatementKind.FACT, "sky is blue")
        engine.register_statement("s2", "t1", StatementKind.FACT, "NOT sky is blue")
        engine.detect_contradictions("t1")
        contrs2 = engine.detect_contradictions("t1")
        assert len(contrs2) == 0  # no new ones
        assert engine.contradiction_count == 1

    def test_revise_belief_state(self, engine):
        engine.register_statement("s1", "t1", StatementKind.FACT, "sky is blue")
        engine.register_statement("s2", "t1", StatementKind.FACT, "NOT sky is blue")
        contrs = engine.detect_contradictions("t1")
        cid = contrs[0].contradiction_id
        revision, decision = engine.revise_belief_state("rv1", "t1", cid)
        assert revision.disposition == RevisionDisposition.ACCEPTED
        assert isinstance(decision, TruthMaintenanceDecision)
        assert engine.revision_count == 1

    def test_logic_assessment(self, engine):
        engine.register_statement("s1", "t1", StatementKind.FACT, "A")
        asm = engine.logic_assessment("la1", "t1")
        assert asm.total_statements == 1
        assert asm.consistency_rate == 1.0

    def test_logic_snapshot(self, engine):
        engine.register_statement("s1", "t1", StatementKind.FACT, "A")
        engine.register_rule("r1", "t1", "A", "B")
        snap = engine.logic_snapshot("ls1", "t1")
        assert snap.total_statements == 1
        assert snap.total_rules == 1

    def test_logic_closure_report(self, engine):
        engine.register_statement("s1", "t1", StatementKind.FACT, "A")
        report = engine.logic_closure_report("lcr1", "t1")
        assert report.total_statements == 1


# =====================================================================
# 4. Violation detection
# =====================================================================


class TestViolationDetection:
    def test_unresolved_contradiction(self, engine):
        engine.register_statement("s1", "t1", StatementKind.FACT, "sky is blue")
        engine.register_statement("s2", "t1", StatementKind.FACT, "NOT sky is blue")
        engine.detect_contradictions("t1")
        viols = engine.detect_logic_violations("t1")
        ops = [v["operation"] for v in viols]
        assert "unresolved_contradiction" in ops

    def test_violations_idempotent(self, engine):
        engine.register_statement("s1", "t1", StatementKind.FACT, "sky is blue")
        engine.register_statement("s2", "t1", StatementKind.FACT, "NOT sky is blue")
        engine.detect_contradictions("t1")
        engine.detect_logic_violations("t1")
        viols2 = engine.detect_logic_violations("t1")
        assert len(viols2) == 0


# =====================================================================
# 5. State hash & snapshot
# =====================================================================


class TestStateHash:
    def test_hash_is_64_hex(self, engine):
        h = engine.state_hash()
        assert len(h) == 64
        int(h, 16)  # valid hex

    def test_hash_changes_on_mutation(self, engine):
        h1 = engine.state_hash()
        engine.register_statement("s1", "t1", StatementKind.FACT, "A")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_snapshot_has_hash(self, engine):
        snap = engine.snapshot()
        assert "_state_hash" in snap


# =====================================================================
# 6. Integration bridge
# =====================================================================


class TestIntegration:
    def test_constructor_validation(self, spine, clock, memory):
        eng = LogicRuntimeEngine(spine, clock=clock)
        integ = LogicRuntimeIntegration(eng, spine, memory)
        assert integ is not None

    def test_bad_engine_raises(self, spine, memory):
        with pytest.raises(RuntimeCoreInvariantError):
            LogicRuntimeIntegration("bad", spine, memory)

    def test_logic_from_governance(self, spine, clock, memory):
        eng = LogicRuntimeEngine(spine, clock=clock)
        integ = LogicRuntimeIntegration(eng, spine, memory)
        result = integ.logic_from_governance("t1", "gov-ref-1")
        assert result["source_type"] == "governance"
        assert eng.statement_count == 1

    def test_logic_from_assurance(self, spine, clock, memory):
        eng = LogicRuntimeEngine(spine, clock=clock)
        integ = LogicRuntimeIntegration(eng, spine, memory)
        result = integ.logic_from_assurance("t1", "assurance-ref-1")
        assert result["source_type"] == "assurance"

    def test_logic_from_research(self, spine, clock, memory):
        eng = LogicRuntimeEngine(spine, clock=clock)
        integ = LogicRuntimeIntegration(eng, spine, memory)
        result = integ.logic_from_research("t1", "research-ref-1")
        assert result["source_type"] == "research"

    def test_logic_from_policy_simulation(self, spine, clock, memory):
        eng = LogicRuntimeEngine(spine, clock=clock)
        integ = LogicRuntimeIntegration(eng, spine, memory)
        result = integ.logic_from_policy_simulation("t1", "sim-ref-1")
        assert result["source_type"] == "policy_simulation"

    def test_logic_from_self_tuning(self, spine, clock, memory):
        eng = LogicRuntimeEngine(spine, clock=clock)
        integ = LogicRuntimeIntegration(eng, spine, memory)
        result = integ.logic_from_self_tuning("t1", "tune-ref-1")
        assert result["source_type"] == "self_tuning"

    def test_logic_from_copilot(self, spine, clock, memory):
        eng = LogicRuntimeEngine(spine, clock=clock)
        integ = LogicRuntimeIntegration(eng, spine, memory)
        result = integ.logic_from_copilot("t1", "copilot-ref-1")
        assert result["source_type"] == "copilot"

    def test_attach_to_memory_mesh(self, spine, clock, memory):
        eng = LogicRuntimeEngine(spine, clock=clock)
        integ = LogicRuntimeIntegration(eng, spine, memory)
        rec = integ.attach_logic_state_to_memory_mesh("scope-1")
        assert rec.memory_id
        assert rec.title == "Logic state"
        assert "scope-1" not in rec.title
        assert rec.scope_ref_id == "scope-1"
        assert memory.memory_count >= 1

    def test_attach_to_graph(self, spine, clock, memory):
        eng = LogicRuntimeEngine(spine, clock=clock)
        integ = LogicRuntimeIntegration(eng, spine, memory)
        result = integ.attach_logic_state_to_graph("scope-1")
        assert "total_statements" in result


class TestBoundedContracts:
    def test_duplicate_statement_redacts_statement_id(self, engine):
        engine.register_statement("stmt-secret", "t1", StatementKind.FACT, "sky is blue")
        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            engine.register_statement("stmt-secret", "t1", StatementKind.FACT, "sky is blue")
        assert "Duplicate statement_id" in str(excinfo.value)
        assert "stmt-secret" not in str(excinfo.value)

    def test_wrong_antecedent_redacts_statement_content(self, engine):
        engine.register_statement("s1", "t1", StatementKind.FACT, "secret premise")
        engine.register_rule("r1", "t1", "secret rule antecedent", "B")
        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            engine.derive_conclusion("t1", "r1", "s1")
        assert "does not match rule antecedent" in str(excinfo.value)
        assert "secret premise" not in str(excinfo.value)
        assert "secret rule antecedent" not in str(excinfo.value)

    def test_unknown_assumption_redacts_assumption_id(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            engine.retract_assumption("assumption-secret")
        assert "Unknown assumption_id" in str(excinfo.value)
        assert "assumption-secret" not in str(excinfo.value)

    def test_revision_paths_redact_ids(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            engine.revise_belief_state("revision-secret", "t1", "contradiction-secret")
        assert "Unknown contradiction_id" in str(excinfo.value)
        assert "contradiction-secret" not in str(excinfo.value)

        engine.register_statement("s1", "t1", StatementKind.FACT, "A")
        engine.register_statement("s2", "t1", StatementKind.FACT, "NOT A")
        contradiction_id = engine.detect_contradictions("t1")[0].contradiction_id
        engine.revise_belief_state("revision-secret", "t1", contradiction_id)
        with pytest.raises(RuntimeCoreInvariantError) as dup_excinfo:
            engine.revise_belief_state("revision-secret", "t1", contradiction_id)
        assert "Duplicate revision_id" in str(dup_excinfo.value)
        assert "revision-secret" not in str(dup_excinfo.value)

    def test_unresolved_contradiction_reason_redacts_contradiction_id(self, engine):
        engine.register_statement("s1", "t1", StatementKind.FACT, "sky is blue")
        engine.register_statement("s2", "t1", StatementKind.FACT, "NOT sky is blue")
        contradiction = engine.detect_contradictions("t1")[0]
        violation = engine.detect_logic_violations("t1")[0]
        assert violation["reason"] == "Contradiction is unresolved"
        assert contradiction.contradiction_id not in violation["reason"]

    def test_retracted_proof_reason_redacts_proof_and_conclusion_ids(self, engine):
        engine.register_statement("stmt-secret", "t1", StatementKind.CONCLUSION, "B")
        engine.record_proof("proof-secret", "t1", "stmt-secret", "r1", ProofStatus.RETRACTED, 1)
        violation = engine.detect_logic_violations("t1")[0]
        assert violation["operation"] == "retracted_proof_still_used"
        assert violation["reason"] == "Retracted proof still has active conclusion"
        assert "proof-secret" not in violation["reason"]
        assert "stmt-secret" not in violation["reason"]

    def test_assumption_reason_redacts_assumption_id(self, engine):
        engine.register_statement("s1", "t1", StatementKind.ASSUMPTION, "rain tomorrow")
        assumption = engine.register_assumption("assumption-secret", "t1", "s1", "because")
        object.__setattr__(assumption, "justification", "   ")
        engine._assumptions["assumption-secret"] = assumption
        violation = engine.detect_logic_violations("t1")[0]
        assert violation["operation"] == "assumption_no_justification"
        assert violation["reason"] == "Assumption has no justification"
        assert "assumption-secret" not in violation["reason"]
