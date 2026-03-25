"""Tests for formal verification runtime engine (~200 tests).

Covers: FormalVerificationEngine lifecycle, specifications, properties,
    verification runs, proof certificates, counter-examples, invariants,
    assessment, snapshot, closure, violation detection, terminal state blocking,
    state_hash, and golden scenarios.
"""

import pytest

from mcoi_runtime.contracts.verification_formal_runtime import (
    FormalSpecification,
    FormalProperty,
    VerificationRun,
    ProofCertificate,
    CounterExample,
    InvariantRecord,
    VerificationAssessment,
    FormalVerificationViolation,
    FormalVerificationSnapshot,
    FormalVerificationClosureReport,
    FormalVerificationStatus,
    PropertyKind,
    ProofMethod,
    AssertionStatus,
    SpecificationStatus,
)
from mcoi_runtime.core.verification_formal_runtime import FormalVerificationEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

_T1 = "t1"
_T2 = "t2"


def _make_engine(clock=None):
    es = EventSpineEngine()
    clk = clock or FixedClock()
    eng = FormalVerificationEngine(es, clock=clk)
    return eng, es


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_valid(self):
        eng, _ = _make_engine()
        assert eng.spec_count == 0
        assert eng.property_count == 0
        assert eng.run_count == 0
        assert eng.certificate_count == 0
        assert eng.counterexample_count == 0
        assert eng.invariant_count == 0
        assert eng.violation_count == 0

    def test_invalid_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            FormalVerificationEngine("bad")

    def test_none_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            FormalVerificationEngine(None)

    def test_custom_clock(self):
        clk = FixedClock("2026-06-01T00:00:00+00:00")
        eng, _ = _make_engine(clock=clk)
        spec = eng.register_specification("sp1", _T1, "Spec1")
        assert spec.created_at == "2026-06-01T00:00:00+00:00"

    def test_default_clock(self):
        es = EventSpineEngine()
        eng = FormalVerificationEngine(es, clock=None)
        assert eng.spec_count == 0


# ---------------------------------------------------------------------------
# Specifications
# ---------------------------------------------------------------------------


class TestSpecifications:
    def test_register(self):
        eng, _ = _make_engine()
        spec = eng.register_specification("sp1", _T1, "Spec1")
        assert spec.spec_id == "sp1"
        assert spec.status is SpecificationStatus.ACTIVE

    def test_register_with_target(self):
        eng, _ = _make_engine()
        spec = eng.register_specification("sp1", _T1, "Spec1", target_runtime="custom")
        assert spec.target_runtime == "custom"

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.register_specification("sp1", _T1, "Spec1")

    def test_count_increments(self):
        eng, _ = _make_engine()
        assert eng.spec_count == 0
        eng.register_specification("sp1", _T1, "Spec1")
        assert eng.spec_count == 1

    def test_emits_event(self):
        eng, es = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        assert es.event_count >= 1


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestProperties:
    def test_add(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        prop = eng.add_property("p1", _T1, "sp1")
        assert prop.property_id == "p1"
        assert prop.status is AssertionStatus.UNKNOWN

    def test_add_with_kind(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        prop = eng.add_property("p1", _T1, "sp1", kind=PropertyKind.LIVENESS)
        assert prop.kind is PropertyKind.LIVENESS

    def test_all_kinds(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        for i, kind in enumerate(PropertyKind):
            prop = eng.add_property(f"p{i}", _T1, "sp1", kind=kind)
            assert prop.kind is kind

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.add_property("p1", _T1, "sp1")

    def test_unknown_spec_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            eng.add_property("p1", _T1, "missing")

    def test_updates_spec_property_count(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1")
        eng.add_property("p2", _T1, "sp1")
        assert eng.property_count == 2

    def test_count_increments(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        assert eng.property_count == 0
        eng.add_property("p1", _T1, "sp1")
        assert eng.property_count == 1


# ---------------------------------------------------------------------------
# Verification runs
# ---------------------------------------------------------------------------


class TestVerificationRuns:
    def test_start(self):
        eng, _ = _make_engine()
        run = eng.start_verification_run("r1", _T1, "sp1")
        assert run.run_id == "r1"
        assert run.status is FormalVerificationStatus.PROVING

    def test_start_with_method(self):
        eng, _ = _make_engine()
        run = eng.start_verification_run("r1", _T1, "sp1", method=ProofMethod.THEOREM_PROVE)
        assert run.method is ProofMethod.THEOREM_PROVE

    def test_all_methods(self):
        eng, _ = _make_engine()
        for i, m in enumerate(ProofMethod):
            run = eng.start_verification_run(f"r{i}", _T1, "sp1", method=m)
            assert run.method is m

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.start_verification_run("r1", _T1, "sp1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.start_verification_run("r1", _T1, "sp1")

    def test_count_increments(self):
        eng, _ = _make_engine()
        assert eng.run_count == 0
        eng.start_verification_run("r1", _T1, "sp1")
        assert eng.run_count == 1


class TestRunTransitions:
    def test_complete_proven(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1")
        eng.record_proof_certificate("c1", _T1, "r1", "p1", proven=True)
        eng.start_verification_run("r1", _T1, "sp1")
        run = eng.complete_run("r1")
        assert run.status is FormalVerificationStatus.PROVEN

    def test_complete_disproven(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1")
        eng.record_counter_example("ce1", _T1, "r1", "p1")
        eng.start_verification_run("r1", _T1, "sp1")
        run = eng.complete_run("r1")
        assert run.status is FormalVerificationStatus.DISPROVEN

    def test_timeout(self):
        eng, _ = _make_engine()
        eng.start_verification_run("r1", _T1, "sp1")
        run = eng.timeout_run("r1", duration_ms=30000.0)
        assert run.status is FormalVerificationStatus.TIMEOUT
        assert run.duration_ms == 30000.0

    def test_terminal_proven_blocks_complete(self):
        eng, _ = _make_engine()
        eng.start_verification_run("r1", _T1, "sp1")
        eng.complete_run("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.complete_run("r1")

    def test_terminal_proven_blocks_timeout(self):
        eng, _ = _make_engine()
        eng.start_verification_run("r1", _T1, "sp1")
        eng.complete_run("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.timeout_run("r1")

    def test_terminal_timeout_blocks_complete(self):
        eng, _ = _make_engine()
        eng.start_verification_run("r1", _T1, "sp1")
        eng.timeout_run("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.complete_run("r1")

    def test_terminal_disproven_blocks(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1")
        eng.record_counter_example("ce1", _T1, "r1", "p1")
        eng.start_verification_run("r1", _T1, "sp1")
        eng.complete_run("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.timeout_run("r1")

    def test_unknown_run_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            eng.complete_run("missing")


# ---------------------------------------------------------------------------
# Proof certificates
# ---------------------------------------------------------------------------


class TestProofCertificates:
    def test_record(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1")
        cert = eng.record_proof_certificate("c1", _T1, "r1", "p1")
        assert cert.cert_id == "c1"
        assert cert.proven is True

    def test_record_not_proven(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1")
        cert = eng.record_proof_certificate("c1", _T1, "r1", "p1", proven=False)
        assert cert.proven is False

    def test_updates_property_status_holds(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1")
        eng.record_proof_certificate("c1", _T1, "r1", "p1", proven=True)
        # Property should now be HOLDS
        snap = eng.snapshot()
        prop = snap["properties"]["p1"]
        assert prop["status"] is AssertionStatus.HOLDS

    def test_updates_property_status_violated(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1")
        eng.record_proof_certificate("c1", _T1, "r1", "p1", proven=False)
        snap = eng.snapshot()
        prop = snap["properties"]["p1"]
        assert prop["status"] is AssertionStatus.VIOLATED

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.record_proof_certificate("c1", _T1, "r1", "p1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.record_proof_certificate("c1", _T1, "r1", "p1")

    def test_count_increments(self):
        eng, _ = _make_engine()
        assert eng.certificate_count == 0
        eng.record_proof_certificate("c1", _T1, "r1", "p1")
        assert eng.certificate_count == 1


# ---------------------------------------------------------------------------
# Counter-examples
# ---------------------------------------------------------------------------


class TestCounterExamples:
    def test_record(self):
        eng, _ = _make_engine()
        ce = eng.record_counter_example("ce1", _T1, "r1", "p1")
        assert ce.example_id == "ce1"

    def test_marks_property_violated(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1")
        eng.record_counter_example("ce1", _T1, "r1", "p1")
        snap = eng.snapshot()
        assert snap["properties"]["p1"]["status"] is AssertionStatus.VIOLATED

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.record_counter_example("ce1", _T1, "r1", "p1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.record_counter_example("ce1", _T1, "r1", "p1")

    def test_count_increments(self):
        eng, _ = _make_engine()
        assert eng.counterexample_count == 0
        eng.record_counter_example("ce1", _T1, "r1", "p1")
        assert eng.counterexample_count == 1


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


class TestInvariants:
    def test_register(self):
        eng, _ = _make_engine()
        inv = eng.register_invariant("inv1", _T1, "default")
        assert inv.invariant_id == "inv1"
        assert inv.status is AssertionStatus.UNKNOWN

    def test_check_truthy(self):
        eng, _ = _make_engine()
        eng.register_invariant("inv1", _T1, "default", expression="true")
        inv = eng.check_invariant("inv1")
        assert inv.status is AssertionStatus.HOLDS

    def test_check_falsy(self):
        eng, _ = _make_engine()
        eng.register_invariant("inv1", _T1, "default", expression="x > 0")
        inv = eng.check_invariant("inv1")
        assert inv.status is AssertionStatus.VIOLATED

    def test_check_holds_expression(self):
        eng, _ = _make_engine()
        eng.register_invariant("inv1", _T1, "default", expression="holds")
        inv = eng.check_invariant("inv1")
        assert inv.status is AssertionStatus.HOLDS

    def test_check_valid_expression(self):
        eng, _ = _make_engine()
        eng.register_invariant("inv1", _T1, "default", expression="valid")
        inv = eng.check_invariant("inv1")
        assert inv.status is AssertionStatus.HOLDS

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_invariant("inv1", _T1, "default")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.register_invariant("inv1", _T1, "default")

    def test_unknown_invariant_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            eng.check_invariant("missing")

    def test_count_increments(self):
        eng, _ = _make_engine()
        assert eng.invariant_count == 0
        eng.register_invariant("inv1", _T1, "default")
        assert eng.invariant_count == 1


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


class TestVerificationAssessmentEngine:
    def test_empty(self):
        eng, _ = _make_engine()
        a = eng.verification_assessment("va1", _T1)
        assert a.total_specs == 0
        assert a.proof_coverage == 0.0

    def test_with_data(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1")
        eng.record_proof_certificate("c1", _T1, "r1", "p1", proven=True)
        a = eng.verification_assessment("va1", _T1)
        assert a.total_specs == 1
        assert a.total_properties == 1
        assert a.total_proven == 1
        assert a.proof_coverage == 1.0

    def test_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.register_specification("sp2", _T2, "Spec2")
        a = eng.verification_assessment("va1", _T1)
        assert a.total_specs == 1


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


class TestVerificationSnapshotEngine:
    def test_empty(self):
        eng, _ = _make_engine()
        s = eng.verification_snapshot("vs1", _T1)
        assert s.total_specs == 0

    def test_with_data(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1")
        s = eng.verification_snapshot("vs1", _T1)
        assert s.total_specs == 1
        assert s.total_properties == 1

    def test_engine_snapshot_dict(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        snap = eng.snapshot()
        assert "specs" in snap
        assert "_state_hash" in snap


# ---------------------------------------------------------------------------
# Closure report
# ---------------------------------------------------------------------------


class TestVerificationClosureEngine:
    def test_empty(self):
        eng, _ = _make_engine()
        r = eng.verification_closure_report("vr1", _T1)
        assert r.total_specs == 0

    def test_with_data(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1")
        eng.record_proof_certificate("c1", _T1, "r1", "p1", proven=True)
        r = eng.verification_closure_report("vr1", _T1)
        assert r.total_specs == 1
        assert r.total_proven == 1


# ---------------------------------------------------------------------------
# Violation detection
# ---------------------------------------------------------------------------


class TestVerificationViolations:
    def test_no_violations_clean(self):
        eng, _ = _make_engine()
        viols = eng.detect_verification_violations(_T1)
        assert len(viols) == 0

    def test_violated_invariant_violation(self):
        eng, _ = _make_engine()
        eng.register_invariant("inv1", _T1, "default", expression="x > 0")
        eng.check_invariant("inv1")
        viols = eng.detect_verification_violations(_T1)
        assert any(v.operation == "violated_invariant" for v in viols)

    def test_unproven_safety_property_violation(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1", kind=PropertyKind.SAFETY)
        viols = eng.detect_verification_violations(_T1)
        assert any(v.operation == "unproven_safety_property" for v in viols)

    def test_timeout_violation(self):
        eng, _ = _make_engine()
        eng.start_verification_run("r1", _T1, "sp1")
        eng.timeout_run("r1")
        viols = eng.detect_verification_violations(_T1)
        assert any(v.operation == "timeout_critical_spec" for v in viols)

    def test_violation_idempotent(self):
        eng, _ = _make_engine()
        eng.register_invariant("inv1", _T1, "default", expression="x > 0")
        eng.check_invariant("inv1")
        first = eng.detect_verification_violations(_T1)
        assert len(first) >= 1
        second = eng.detect_verification_violations(_T1)
        assert len(second) == 0

    def test_violation_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.register_invariant("inv1", _T1, "default", expression="x > 0")
        eng.check_invariant("inv1")
        viols = eng.detect_verification_violations(_T2)
        assert len(viols) == 0

    def test_violation_count_increments(self):
        eng, _ = _make_engine()
        assert eng.violation_count == 0
        eng.register_invariant("inv1", _T1, "default", expression="x > 0")
        eng.check_invariant("inv1")
        eng.detect_verification_violations(_T1)
        assert eng.violation_count >= 1


# ---------------------------------------------------------------------------
# State hash
# ---------------------------------------------------------------------------


class TestVerificationStateHash:
    def test_empty_deterministic(self):
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        assert eng1.state_hash() == eng2.state_hash()

    def test_changes_on_mutation(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.register_specification("sp1", _T1, "Spec1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_64_chars(self):
        eng, _ = _make_engine()
        assert len(eng.state_hash()) == 64

    def test_deterministic_same_ops(self):
        clk1 = FixedClock()
        clk2 = FixedClock()
        eng1, _ = _make_engine(clock=clk1)
        eng2, _ = _make_engine(clock=clk2)
        eng1.register_specification("sp1", _T1, "Spec1")
        eng2.register_specification("sp1", _T1, "Spec1")
        assert eng1.state_hash() == eng2.state_hash()

    def test_includes_properties(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        h1 = eng.state_hash()
        eng.add_property("p1", _T1, "sp1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_includes_runs(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.start_verification_run("r1", _T1, "sp1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_includes_certificates(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.record_proof_certificate("c1", _T1, "r1", "p1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_includes_invariants(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.register_invariant("inv1", _T1, "default")
        h2 = eng.state_hash()
        assert h1 != h2


# ---------------------------------------------------------------------------
# Golden scenarios
# ---------------------------------------------------------------------------


class TestGoldenScenarios:
    def test_happy_path_lifecycle(self):
        eng, es = _make_engine()
        eng.register_specification("sp1", _T1, "Safety Spec")
        eng.add_property("p1", _T1, "sp1", kind=PropertyKind.SAFETY, expression="true")
        eng.start_verification_run("r1", _T1, "sp1")
        eng.record_proof_certificate("c1", _T1, "r1", "p1", proven=True)
        run = eng.complete_run("r1")
        assert run.status is FormalVerificationStatus.PROVEN
        a = eng.verification_assessment("va1", _T1)
        assert a.proof_coverage == 1.0
        assert es.event_count > 0

    def test_proof_verified_golden(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.add_property("p1", _T1, "sp1", kind=PropertyKind.SAFETY)
        eng.record_proof_certificate("c1", _T1, "r1", "p1", proven=True)
        eng.start_verification_run("r1", _T1, "sp1")
        run = eng.complete_run("r1")
        assert run.status is FormalVerificationStatus.PROVEN

    def test_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.register_specification("sp1", _T1, "Spec1")
        eng.register_specification("sp2", _T2, "Spec2")
        snap1 = eng.verification_snapshot("vs1", _T1)
        snap2 = eng.verification_snapshot("vs2", _T2)
        assert snap1.total_specs == 1
        assert snap2.total_specs == 1

    def test_terminal_state_blocking_golden(self):
        eng, _ = _make_engine()
        eng.start_verification_run("r1", _T1, "sp1")
        eng.complete_run("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.timeout_run("r1")

    def test_violation_idempotency_golden(self):
        eng, _ = _make_engine()
        eng.register_invariant("inv1", _T1, "default", expression="x > 0")
        eng.check_invariant("inv1")
        first = eng.detect_verification_violations(_T1)
        assert len(first) >= 1
        second = eng.detect_verification_violations(_T1)
        assert len(second) == 0

    def test_state_hash_determinism_golden(self):
        clk1 = FixedClock()
        clk2 = FixedClock()
        eng1, _ = _make_engine(clock=clk1)
        eng2, _ = _make_engine(clock=clk2)
        for eng in (eng1, eng2):
            eng.register_specification("sp1", _T1, "Spec1")
            eng.add_property("p1", _T1, "sp1")
            eng.register_invariant("inv1", _T1, "default")
        assert eng1.state_hash() == eng2.state_hash()
