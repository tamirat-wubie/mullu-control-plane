"""Tests for IndustryPackEngine.

Governance scope: comprehensive coverage for pack lifecycle, capabilities,
configurations, bindings, assessments, decisions, bootstrap, violations,
snapshots, and closure reports.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.industry_pack import IndustryPackEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.industry_pack import (
    DeploymentDisposition,
    IndustryPack,
    IndustryPackStatus,
    PackAssessment,
    PackBinding,
    PackCapability,
    PackCapabilityKind,
    PackClosureReport,
    PackConfiguration,
    PackDecision,
    PackDeploymentRecord,
    PackDomain,
    PackReadiness,
    PackSnapshot,
    PackViolation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def engine(spine: EventSpineEngine) -> IndustryPackEngine:
    return IndustryPackEngine(spine)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_rejects_bad_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            IndustryPackEngine("not_an_engine")

    def test_valid(self, engine: IndustryPackEngine):
        assert engine.pack_count == 0
        assert engine.capability_count == 0


# ---------------------------------------------------------------------------
# Pack lifecycle
# ---------------------------------------------------------------------------


class TestPackLifecycle:
    def test_register_pack(self, engine: IndustryPackEngine):
        p = engine.register_pack("p1", "t1", "Test", PackDomain.REGULATED_OPS)
        assert isinstance(p, IndustryPack)
        assert p.status == IndustryPackStatus.DRAFT
        assert p.capability_count == 0
        assert engine.pack_count == 1

    def test_duplicate_rejected(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.REGULATED_OPS)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_pack("p1", "t1", "Test2", PackDomain.CUSTOM)

    def test_get_pack(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        p = engine.get_pack("p1")
        assert p.pack_id == "p1"

    def test_get_unknown_pack(self, engine: IndustryPackEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_pack("nope")

    def test_packs_for_tenant(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "A", PackDomain.CUSTOM)
        engine.register_pack("p2", "t2", "B", PackDomain.CUSTOM)
        engine.register_pack("p3", "t1", "C", PackDomain.CUSTOM)
        assert len(engine.packs_for_tenant("t1")) == 2
        assert len(engine.packs_for_tenant("t2")) == 1

    def test_validate_pack_stays_draft_without_caps(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.REGULATED_OPS)
        result = engine.validate_pack("p1")
        assert result.status == IndustryPackStatus.DRAFT  # Missing required caps

    def test_validate_pack_transitions_to_validated(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.REGULATED_OPS)
        for kind in PackCapabilityKind:
            engine.add_capability(f"c-{kind.value}", "t1", "p1", kind, f"rt-{kind.value}")
        result = engine.validate_pack("p1")
        assert result.status == IndustryPackStatus.VALIDATED

    def test_validate_non_draft_rejected(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.REGULATED_OPS)
        for kind in PackCapabilityKind:
            engine.add_capability(f"c-{kind.value}", "t1", "p1", kind, f"rt-{kind.value}")
        engine.validate_pack("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.validate_pack("p1")

    def test_deploy_pack(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.REGULATED_OPS)
        for kind in PackCapabilityKind:
            engine.add_capability(f"c-{kind.value}", "t1", "p1", kind, f"rt-{kind.value}")
        engine.validate_pack("p1")
        result = engine.deploy_pack("p1")
        assert result.status == IndustryPackStatus.DEPLOYED
        assert engine.deployment_count == 1

    def test_deploy_non_validated_rejected(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        with pytest.raises(RuntimeCoreInvariantError, match="VALIDATED"):
            engine.deploy_pack("p1")

    def test_suspend_pack(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        result = engine.suspend_pack("p1")
        assert result.status == IndustryPackStatus.SUSPENDED

    def test_retire_pack(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        result = engine.retire_pack("p1")
        assert result.status == IndustryPackStatus.RETIRED

    def test_retire_is_terminal(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        engine.retire_pack("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.suspend_pack("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.retire_pack("p1")


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_add_capability(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        cap = engine.add_capability("c1", "t1", "p1", PackCapabilityKind.INTAKE, "rt1")
        assert isinstance(cap, PackCapability)
        assert cap.enabled is True
        assert engine.capability_count == 1
        assert engine.get_pack("p1").capability_count == 1

    def test_duplicate_capability_rejected(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        engine.add_capability("c1", "t1", "p1", PackCapabilityKind.INTAKE, "rt1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.add_capability("c1", "t1", "p1", PackCapabilityKind.APPROVAL, "rt2")

    def test_unknown_pack_ref_rejected(self, engine: IndustryPackEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.add_capability("c1", "t1", "nope", PackCapabilityKind.INTAKE, "rt1")

    def test_disabled_capability(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        cap = engine.add_capability("c1", "t1", "p1", PackCapabilityKind.INTAKE, "rt1", enabled=False)
        assert cap.enabled is False


# ---------------------------------------------------------------------------
# Configurations
# ---------------------------------------------------------------------------


class TestConfigurations:
    def test_add_configuration(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        cfg = engine.add_configuration("cfg1", "t1", "p1", "key1", "val1")
        assert isinstance(cfg, PackConfiguration)
        assert engine.config_count == 1

    def test_duplicate_rejected(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        engine.add_configuration("cfg1", "t1", "p1", "k", "v")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.add_configuration("cfg1", "t1", "p1", "k2", "v2")


# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------


class TestBindings:
    def test_add_binding(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        b = engine.add_binding("b1", "t1", "p1", "rt1", "primary")
        assert isinstance(b, PackBinding)
        assert engine.binding_count == 1

    def test_duplicate_rejected(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        engine.add_binding("b1", "t1", "p1", "rt1", "primary")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.add_binding("b1", "t1", "p1", "rt2", "secondary")


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


class TestAssessment:
    def test_assess_all_enabled(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        engine.add_capability("c1", "t1", "p1", PackCapabilityKind.INTAKE, "rt1")
        engine.add_capability("c2", "t1", "p1", PackCapabilityKind.APPROVAL, "rt2")
        a = engine.assess_pack("a1", "t1", "p1")
        assert isinstance(a, PackAssessment)
        assert a.readiness == PackReadiness.READY
        assert a.readiness_score == 1.0
        assert a.total_capabilities == 2
        assert a.enabled_capabilities == 2

    def test_assess_partial(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        engine.add_capability("c1", "t1", "p1", PackCapabilityKind.INTAKE, "rt1", enabled=True)
        engine.add_capability("c2", "t1", "p1", PackCapabilityKind.APPROVAL, "rt2", enabled=False)
        a = engine.assess_pack("a1", "t1", "p1")
        assert a.readiness == PackReadiness.PARTIAL
        assert a.readiness_score == 0.5

    def test_assess_not_ready(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        engine.add_capability("c1", "t1", "p1", PackCapabilityKind.INTAKE, "rt1", enabled=False)
        engine.add_capability("c2", "t1", "p1", PackCapabilityKind.APPROVAL, "rt2", enabled=False)
        engine.add_capability("c3", "t1", "p1", PackCapabilityKind.EVIDENCE, "rt3", enabled=False)
        a = engine.assess_pack("a1", "t1", "p1")
        assert a.readiness == PackReadiness.NOT_READY
        assert a.readiness_score == 0.0

    def test_assess_empty_pack(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        a = engine.assess_pack("a1", "t1", "p1")
        assert a.readiness == PackReadiness.READY  # 0/0 = 1.0
        assert a.readiness_score == 1.0


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


class TestDecisions:
    def test_record_decision(self, engine: IndustryPackEngine):
        d = engine.record_decision("d1", "t1", "p1", DeploymentDisposition.APPROVED, "looks good")
        assert isinstance(d, PackDecision)
        assert engine.decision_count == 1


# ---------------------------------------------------------------------------
# Bootstrap Regulated Ops
# ---------------------------------------------------------------------------


class TestBootstrapRegulatedOps:
    def test_bootstrap(self, engine: IndustryPackEngine):
        summary = engine.bootstrap_regulated_ops_pack("reg-1", "t1")
        assert summary["pack_id"] == "reg-1"
        assert summary["domain"] == "regulated_ops"
        assert summary["capability_count"] == 10
        assert summary["status"] == "draft"
        assert engine.pack_count == 1
        assert engine.capability_count == 10

    def test_bootstrap_then_validate_and_deploy(self, engine: IndustryPackEngine):
        engine.bootstrap_regulated_ops_pack("reg-1", "t1")
        result = engine.validate_pack("reg-1")
        assert result.status == IndustryPackStatus.VALIDATED
        deployed = engine.deploy_pack("reg-1")
        assert deployed.status == IndustryPackStatus.DEPLOYED


# ---------------------------------------------------------------------------
# Snapshot & Closure
# ---------------------------------------------------------------------------


class TestSnapshotClosure:
    def test_pack_snapshot(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        s = engine.pack_snapshot("s1", "t1")
        assert isinstance(s, PackSnapshot)
        assert s.total_packs == 1

    def test_duplicate_snapshot_rejected(self, engine: IndustryPackEngine):
        engine.pack_snapshot("s1", "t1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.pack_snapshot("s1", "t1")

    def test_closure_report(self, engine: IndustryPackEngine):
        cr = engine.pack_closure_report("cr1", "t1")
        assert isinstance(cr, PackClosureReport)
        assert cr.total_packs == 0


# ---------------------------------------------------------------------------
# Violations
# ---------------------------------------------------------------------------


class TestViolations:
    def test_no_violations_on_clean_state(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        violations = engine.detect_pack_violations("t1")
        assert len(violations) == 0

    def test_binding_orphan(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        engine.add_binding("b1", "t1", "p1", "nonexistent-runtime", "primary")
        violations = engine.detect_pack_violations("t1")
        assert any(v.operation == "binding_orphan" for v in violations)

    def test_missing_required_capability(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.REGULATED_OPS)
        violations = engine.detect_pack_violations("t1")
        assert any(v.operation == "missing_required_capability" for v in violations)

    def test_idempotent(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.REGULATED_OPS)
        v1 = engine.detect_pack_violations("t1")
        v2 = engine.detect_pack_violations("t1")
        assert len(v1) > 0
        assert len(v2) == 0  # idempotent: no new violations


# ---------------------------------------------------------------------------
# State hash & snapshot
# ---------------------------------------------------------------------------


class TestStateHash:
    def test_state_hash_64_chars(self, engine: IndustryPackEngine):
        h = engine.state_hash()
        assert len(h) == 64

    def test_state_hash_changes(self, engine: IndustryPackEngine):
        h1 = engine.state_hash()
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_snapshot_dict(self, engine: IndustryPackEngine):
        engine.register_pack("p1", "t1", "Test", PackDomain.CUSTOM)
        s = engine.snapshot()
        assert "packs" in s
        assert "_state_hash" in s
        assert "p1" in s["packs"]

    def test_collections(self, engine: IndustryPackEngine):
        cols = engine._collections()
        assert "packs" in cols
        assert "capabilities" in cols
        assert "configurations" in cols
        assert "bindings" in cols
        assert "violations" in cols


class TestBoundedIndustryPackContracts:
    def test_registry_and_lifecycle_errors_are_bounded(self, engine: IndustryPackEngine):
        engine.register_pack("pack-secret", "t1", "Test", PackDomain.CUSTOM)
        with pytest.raises(RuntimeCoreInvariantError) as duplicate_pack:
            engine.register_pack("pack-secret", "t1", "Other", PackDomain.CUSTOM)
        with pytest.raises(RuntimeCoreInvariantError) as unknown_pack:
            engine.get_pack("pack-secret-missing")
        with pytest.raises(RuntimeCoreInvariantError) as deploy_error:
            engine.deploy_pack("pack-secret")
        engine.retire_pack("pack-secret")
        with pytest.raises(RuntimeCoreInvariantError) as terminal_suspend:
            engine.suspend_pack("pack-secret")

        assert str(duplicate_pack.value) == "Duplicate pack_id"
        assert str(unknown_pack.value) == "Unknown pack_id"
        assert str(deploy_error.value) == "Only VALIDATED packs can be deployed"
        assert str(terminal_suspend.value) == "Cannot suspend pack in current status"
        assert "pack-secret" not in str(duplicate_pack.value)
        assert "pack-secret-missing" not in str(unknown_pack.value)
        assert "draft" not in str(deploy_error.value).lower()
        assert "retired" not in str(terminal_suspend.value).lower()

    def test_component_errors_and_violation_reasons_are_bounded(self, engine: IndustryPackEngine):
        engine.register_pack("pack-secret", "t1", "Test", PackDomain.REGULATED_OPS)
        with pytest.raises(RuntimeCoreInvariantError) as duplicate_capability:
            engine.add_capability("cap-secret", "t1", "missing-pack", PackCapabilityKind.INTAKE, "rt-1")

        engine.add_binding("binding-secret", "t1", "pack-secret", "missing-runtime", "primary")
        violations = engine.detect_pack_violations("t1")

        assert str(duplicate_capability.value) == "Unknown pack_ref"
        assert "missing-pack" not in str(duplicate_capability.value)
        assert any(v.reason == "pack is missing required capability" for v in violations)
        assert any(v.reason == "binding references unknown runtime" for v in violations)
        assert all("pack-secret" not in v.reason for v in violations)
        assert all("binding-secret" not in v.reason for v in violations)
        assert all("missing-runtime" not in v.reason for v in violations)
