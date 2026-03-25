"""Tests for formal verification runtime contracts (~200 tests).

Covers: FormalSpecification, FormalProperty, VerificationRun, ProofCertificate,
    CounterExample, InvariantRecord, VerificationAssessment,
    FormalVerificationViolation, FormalVerificationSnapshot,
    FormalVerificationClosureReport, and all enums.
"""

import pytest
from dataclasses import FrozenInstanceError

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
    VerificationRiskLevel,
)

_NOW = "2026-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestFormalVerificationStatusEnum:
    def test_values(self):
        assert FormalVerificationStatus.PENDING.value == "pending"
        assert FormalVerificationStatus.PROVING.value == "proving"
        assert FormalVerificationStatus.PROVEN.value == "proven"
        assert FormalVerificationStatus.DISPROVEN.value == "disproven"
        assert FormalVerificationStatus.TIMEOUT.value == "timeout"

    def test_member_count(self):
        assert len(FormalVerificationStatus) == 5


class TestPropertyKindEnum:
    def test_values(self):
        assert PropertyKind.SAFETY.value == "safety"
        assert PropertyKind.LIVENESS.value == "liveness"
        assert PropertyKind.INVARIANT.value == "invariant"
        assert PropertyKind.REACHABILITY.value == "reachability"
        assert PropertyKind.DEADLOCK_FREE.value == "deadlock_free"

    def test_member_count(self):
        assert len(PropertyKind) == 5


class TestProofMethodEnum:
    def test_values(self):
        assert ProofMethod.MODEL_CHECK.value == "model_check"
        assert ProofMethod.THEOREM_PROVE.value == "theorem_prove"
        assert ProofMethod.ABSTRACT_INTERPRET.value == "abstract_interpret"
        assert ProofMethod.BOUNDED_CHECK.value == "bounded_check"
        assert ProofMethod.SIMULATION.value == "simulation"

    def test_member_count(self):
        assert len(ProofMethod) == 5


class TestAssertionStatusEnum:
    def test_values(self):
        assert AssertionStatus.HOLDS.value == "holds"
        assert AssertionStatus.VIOLATED.value == "violated"
        assert AssertionStatus.UNKNOWN.value == "unknown"
        assert AssertionStatus.VACUOUS.value == "vacuous"

    def test_member_count(self):
        assert len(AssertionStatus) == 4


class TestSpecificationStatusEnum:
    def test_values(self):
        assert SpecificationStatus.DRAFT.value == "draft"
        assert SpecificationStatus.ACTIVE.value == "active"
        assert SpecificationStatus.DEPRECATED.value == "deprecated"
        assert SpecificationStatus.RETIRED.value == "retired"

    def test_member_count(self):
        assert len(SpecificationStatus) == 4


class TestVerificationRiskLevelEnum:
    def test_values(self):
        assert VerificationRiskLevel.LOW.value == "low"
        assert VerificationRiskLevel.CRITICAL.value == "critical"

    def test_member_count(self):
        assert len(VerificationRiskLevel) == 4


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _spec(**ov):
    d = dict(spec_id="sp1", tenant_id="t1", display_name="Spec1",
             target_runtime="default", status=SpecificationStatus.ACTIVE,
             property_count=0, created_at=_NOW)
    d.update(ov)
    return FormalSpecification(**d)


def _prop(**ov):
    d = dict(property_id="p1", tenant_id="t1", spec_ref="sp1",
             kind=PropertyKind.SAFETY, expression="x > 0",
             status=AssertionStatus.UNKNOWN, created_at=_NOW)
    d.update(ov)
    return FormalProperty(**d)


def _run(**ov):
    d = dict(run_id="r1", tenant_id="t1", spec_ref="sp1",
             method=ProofMethod.MODEL_CHECK,
             status=FormalVerificationStatus.PROVING,
             duration_ms=0.0, created_at=_NOW)
    d.update(ov)
    return VerificationRun(**d)


def _cert(**ov):
    d = dict(cert_id="c1", tenant_id="t1", run_ref="r1",
             property_ref="p1", proven=True, witness="auto",
             created_at=_NOW)
    d.update(ov)
    return ProofCertificate(**d)


def _counter(**ov):
    d = dict(example_id="ce1", tenant_id="t1", run_ref="r1",
             property_ref="p1", trace="x=0 violates x>0",
             created_at=_NOW)
    d.update(ov)
    return CounterExample(**d)


def _invariant(**ov):
    d = dict(invariant_id="inv1", tenant_id="t1", target_runtime="default",
             expression="true", status=AssertionStatus.UNKNOWN, created_at=_NOW)
    d.update(ov)
    return InvariantRecord(**d)


def _v_assessment(**ov):
    d = dict(assessment_id="va1", tenant_id="t1", total_specs=1,
             total_properties=1, total_proven=0, proof_coverage=0.5,
             assessed_at=_NOW)
    d.update(ov)
    return VerificationAssessment(**d)


def _v_violation(**ov):
    d = dict(violation_id="vv1", tenant_id="t1", operation="unproven_safety",
             reason="not proven", detected_at=_NOW)
    d.update(ov)
    return FormalVerificationViolation(**d)


def _v_snapshot(**ov):
    d = dict(snapshot_id="vs1", tenant_id="t1", total_specs=1,
             total_properties=1, total_runs=0, total_certificates=0,
             total_counterexamples=0, total_violations=0, captured_at=_NOW)
    d.update(ov)
    return FormalVerificationSnapshot(**d)


def _v_closure(**ov):
    d = dict(report_id="vr1", tenant_id="t1", total_specs=1,
             total_properties=1, total_proven=0, total_violations=0,
             created_at=_NOW)
    d.update(ov)
    return FormalVerificationClosureReport(**d)


# ---------------------------------------------------------------------------
# FormalSpecification tests
# ---------------------------------------------------------------------------


class TestFormalSpecification:
    def test_valid(self):
        s = _spec()
        assert s.spec_id == "sp1"
        assert s.status is SpecificationStatus.ACTIVE

    def test_all_statuses(self):
        for st in SpecificationStatus:
            s = _spec(status=st)
            assert s.status is st

    def test_empty_spec_id_rejected(self):
        with pytest.raises(ValueError, match="spec_id"):
            _spec(spec_id="")

    def test_empty_display_name_rejected(self):
        with pytest.raises(ValueError, match="display_name"):
            _spec(display_name="")

    def test_empty_target_runtime_rejected(self):
        with pytest.raises(ValueError, match="target_runtime"):
            _spec(target_runtime="")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _spec(status="invalid")

    def test_property_count_negative_rejected(self):
        with pytest.raises(ValueError, match="property_count"):
            _spec(property_count=-1)

    def test_property_count_bool_rejected(self):
        with pytest.raises(ValueError, match="property_count"):
            _spec(property_count=True)

    def test_frozen(self):
        s = _spec()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "spec_id", "x")

    def test_to_dict(self):
        d = _spec().to_dict()
        assert d["status"] is SpecificationStatus.ACTIVE

    def test_to_json_dict(self):
        d = _spec().to_json_dict()
        assert d["status"] == "active"


# ---------------------------------------------------------------------------
# FormalProperty tests
# ---------------------------------------------------------------------------


class TestFormalProperty:
    def test_valid(self):
        p = _prop()
        assert p.property_id == "p1"
        assert p.kind is PropertyKind.SAFETY

    def test_all_kinds(self):
        for kind in PropertyKind:
            p = _prop(kind=kind)
            assert p.kind is kind

    def test_all_statuses(self):
        for st in AssertionStatus:
            p = _prop(status=st)
            assert p.status is st

    def test_empty_property_id_rejected(self):
        with pytest.raises(ValueError, match="property_id"):
            _prop(property_id="")

    def test_empty_spec_ref_rejected(self):
        with pytest.raises(ValueError, match="spec_ref"):
            _prop(spec_ref="")

    def test_empty_expression_rejected(self):
        with pytest.raises(ValueError, match="expression"):
            _prop(expression="")

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError, match="kind"):
            _prop(kind="bogus")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _prop(status="invalid")

    def test_frozen(self):
        p = _prop()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(p, "property_id", "x")

    def test_to_dict(self):
        d = _prop().to_dict()
        assert d["kind"] is PropertyKind.SAFETY


# ---------------------------------------------------------------------------
# VerificationRun tests
# ---------------------------------------------------------------------------


class TestVerificationRun:
    def test_valid(self):
        r = _run()
        assert r.run_id == "r1"
        assert r.method is ProofMethod.MODEL_CHECK

    def test_all_methods(self):
        for m in ProofMethod:
            r = _run(method=m)
            assert r.method is m

    def test_all_statuses(self):
        for st in FormalVerificationStatus:
            r = _run(status=st)
            assert r.status is st

    def test_duration_zero(self):
        r = _run(duration_ms=0.0)
        assert r.duration_ms == 0.0

    def test_duration_negative_rejected(self):
        with pytest.raises(ValueError, match="duration_ms"):
            _run(duration_ms=-1.0)

    def test_duration_nan_rejected(self):
        with pytest.raises(ValueError, match="duration_ms"):
            _run(duration_ms=float("nan"))

    def test_invalid_method_rejected(self):
        with pytest.raises(ValueError, match="method"):
            _run(method="invalid")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _run(status="invalid")

    def test_frozen(self):
        r = _run()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "run_id", "x")


# ---------------------------------------------------------------------------
# ProofCertificate tests
# ---------------------------------------------------------------------------


class TestProofCertificate:
    def test_valid(self):
        c = _cert()
        assert c.cert_id == "c1"
        assert c.proven is True

    def test_proven_false(self):
        c = _cert(proven=False)
        assert c.proven is False

    def test_proven_non_bool_rejected(self):
        with pytest.raises(ValueError, match="proven"):
            _cert(proven=1)

    def test_proven_string_rejected(self):
        with pytest.raises(ValueError, match="proven"):
            _cert(proven="true")

    def test_empty_cert_id_rejected(self):
        with pytest.raises(ValueError, match="cert_id"):
            _cert(cert_id="")

    def test_empty_witness_rejected(self):
        with pytest.raises(ValueError, match="witness"):
            _cert(witness="")

    def test_empty_run_ref_rejected(self):
        with pytest.raises(ValueError, match="run_ref"):
            _cert(run_ref="")

    def test_empty_property_ref_rejected(self):
        with pytest.raises(ValueError, match="property_ref"):
            _cert(property_ref="")

    def test_frozen(self):
        c = _cert()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, "cert_id", "x")

    def test_to_dict(self):
        d = _cert().to_dict()
        assert d["proven"] is True


# ---------------------------------------------------------------------------
# CounterExample tests
# ---------------------------------------------------------------------------


class TestCounterExample:
    def test_valid(self):
        ce = _counter()
        assert ce.example_id == "ce1"

    def test_empty_example_id_rejected(self):
        with pytest.raises(ValueError, match="example_id"):
            _counter(example_id="")

    def test_empty_trace_rejected(self):
        with pytest.raises(ValueError, match="trace"):
            _counter(trace="")

    def test_empty_run_ref_rejected(self):
        with pytest.raises(ValueError, match="run_ref"):
            _counter(run_ref="")

    def test_empty_property_ref_rejected(self):
        with pytest.raises(ValueError, match="property_ref"):
            _counter(property_ref="")

    def test_frozen(self):
        ce = _counter()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(ce, "example_id", "x")


# ---------------------------------------------------------------------------
# InvariantRecord tests
# ---------------------------------------------------------------------------


class TestInvariantRecord:
    def test_valid(self):
        inv = _invariant()
        assert inv.invariant_id == "inv1"
        assert inv.status is AssertionStatus.UNKNOWN

    def test_all_statuses(self):
        for st in AssertionStatus:
            inv = _invariant(status=st)
            assert inv.status is st

    def test_empty_invariant_id_rejected(self):
        with pytest.raises(ValueError, match="invariant_id"):
            _invariant(invariant_id="")

    def test_empty_expression_rejected(self):
        with pytest.raises(ValueError, match="expression"):
            _invariant(expression="")

    def test_empty_target_runtime_rejected(self):
        with pytest.raises(ValueError, match="target_runtime"):
            _invariant(target_runtime="")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _invariant(status="invalid")

    def test_frozen(self):
        inv = _invariant()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(inv, "invariant_id", "x")


# ---------------------------------------------------------------------------
# VerificationAssessment tests
# ---------------------------------------------------------------------------


class TestVerificationAssessment:
    def test_valid(self):
        a = _v_assessment()
        assert a.proof_coverage == 0.5

    def test_proof_coverage_zero(self):
        a = _v_assessment(proof_coverage=0.0)
        assert a.proof_coverage == 0.0

    def test_proof_coverage_one(self):
        a = _v_assessment(proof_coverage=1.0)
        assert a.proof_coverage == 1.0

    def test_proof_coverage_negative_rejected(self):
        with pytest.raises(ValueError, match="proof_coverage"):
            _v_assessment(proof_coverage=-0.1)

    def test_proof_coverage_above_one_rejected(self):
        with pytest.raises(ValueError, match="proof_coverage"):
            _v_assessment(proof_coverage=1.1)

    def test_total_specs_negative_rejected(self):
        with pytest.raises(ValueError, match="total_specs"):
            _v_assessment(total_specs=-1)

    def test_total_properties_negative_rejected(self):
        with pytest.raises(ValueError, match="total_properties"):
            _v_assessment(total_properties=-1)

    def test_total_proven_negative_rejected(self):
        with pytest.raises(ValueError, match="total_proven"):
            _v_assessment(total_proven=-1)

    def test_frozen(self):
        a = _v_assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "assessment_id", "x")


# ---------------------------------------------------------------------------
# FormalVerificationViolation tests
# ---------------------------------------------------------------------------


class TestFormalVerificationViolation:
    def test_valid(self):
        v = _v_violation()
        assert v.violation_id == "vv1"

    def test_empty_violation_id_rejected(self):
        with pytest.raises(ValueError, match="violation_id"):
            _v_violation(violation_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError, match="operation"):
            _v_violation(operation="")

    def test_frozen(self):
        v = _v_violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "violation_id", "x")


# ---------------------------------------------------------------------------
# FormalVerificationSnapshot tests
# ---------------------------------------------------------------------------


class TestFormalVerificationSnapshot:
    def test_valid(self):
        s = _v_snapshot()
        assert s.snapshot_id == "vs1"

    def test_negative_counts_rejected(self):
        for field in ["total_specs", "total_properties", "total_runs",
                      "total_certificates", "total_counterexamples", "total_violations"]:
            with pytest.raises(ValueError, match=field):
                _v_snapshot(**{field: -1})

    def test_frozen(self):
        s = _v_snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "snapshot_id", "x")


# ---------------------------------------------------------------------------
# FormalVerificationClosureReport tests
# ---------------------------------------------------------------------------


class TestFormalVerificationClosureReport:
    def test_valid(self):
        r = _v_closure()
        assert r.report_id == "vr1"

    def test_negative_counts_rejected(self):
        for field in ["total_specs", "total_properties", "total_proven", "total_violations"]:
            with pytest.raises(ValueError, match=field):
                _v_closure(**{field: -1})

    def test_frozen(self):
        r = _v_closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "report_id", "x")


# ---------------------------------------------------------------------------
# Cross-cutting tests
# ---------------------------------------------------------------------------


class TestVerificationCrossCutting:
    def test_all_contracts_have_to_dict(self):
        objs = [_spec(), _prop(), _run(), _cert(), _counter(), _invariant(),
                _v_assessment(), _v_violation(), _v_snapshot(), _v_closure()]
        for obj in objs:
            assert isinstance(obj.to_dict(), dict)

    def test_all_contracts_frozen(self):
        objs = [_spec(), _prop(), _run(), _cert(), _counter(), _invariant(),
                _v_assessment(), _v_violation(), _v_snapshot(), _v_closure()]
        for obj in objs:
            with pytest.raises((FrozenInstanceError, AttributeError)):
                setattr(obj, "tenant_id", "x")

    def test_all_invalid_datetime(self):
        with pytest.raises(ValueError):
            _spec(created_at="bad")
        with pytest.raises(ValueError):
            _prop(created_at="bad")
        with pytest.raises(ValueError):
            _run(created_at="bad")
        with pytest.raises(ValueError):
            _cert(created_at="bad")
        with pytest.raises(ValueError):
            _counter(created_at="bad")
        with pytest.raises(ValueError):
            _invariant(created_at="bad")
        with pytest.raises(ValueError):
            _v_assessment(assessed_at="bad")
        with pytest.raises(ValueError):
            _v_violation(detected_at="bad")
        with pytest.raises(ValueError):
            _v_snapshot(captured_at="bad")
        with pytest.raises(ValueError):
            _v_closure(created_at="bad")

    def test_all_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _spec(tenant_id="")
        with pytest.raises(ValueError):
            _prop(tenant_id="")
        with pytest.raises(ValueError):
            _run(tenant_id="")
        with pytest.raises(ValueError):
            _cert(tenant_id="")
        with pytest.raises(ValueError):
            _counter(tenant_id="")
        with pytest.raises(ValueError):
            _invariant(tenant_id="")
        with pytest.raises(ValueError):
            _v_assessment(tenant_id="")
        with pytest.raises(ValueError):
            _v_violation(tenant_id="")
        with pytest.raises(ValueError):
            _v_snapshot(tenant_id="")
        with pytest.raises(ValueError):
            _v_closure(tenant_id="")

    def test_all_to_json(self):
        import json
        objs = [_spec(), _prop(), _run(), _cert(), _counter(), _invariant(),
                _v_assessment(), _v_violation(), _v_snapshot(), _v_closure()]
        for obj in objs:
            j = obj.to_json()
            assert isinstance(json.loads(j), dict)
