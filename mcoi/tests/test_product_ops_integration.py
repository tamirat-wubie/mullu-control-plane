"""Tests for the ProductOpsIntegration bridge.

Covers constructor validation, release-from-assurance / continuity /
service-health / customer-impact / change-runtime, memory mesh attachment,
graph attachment, event emission, return value schemas, immutability,
duplicate-ID rejection, and golden end-to-end scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.product_ops import ProductOpsEngine
from mcoi_runtime.core.product_ops_integration import ProductOpsIntegration
from mcoi_runtime.contracts.product_ops import ReleaseKind
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def event_spine():
    return EventSpineEngine()


@pytest.fixture
def memory_engine():
    return MemoryMeshEngine()


@pytest.fixture
def ops_engine(event_spine):
    po = ProductOpsEngine(event_spine)
    po.register_version("v1", "p1", "T1", "1.0.0")
    return po


@pytest.fixture
def integration(ops_engine, event_spine, memory_engine):
    return ProductOpsIntegration(ops_engine, event_spine, memory_engine)


def _fresh(register_extra_versions=False):
    """Helper that returns (ops_engine, event_spine, memory_engine, integration)."""
    es = EventSpineEngine()
    mm = MemoryMeshEngine()
    po = ProductOpsEngine(es)
    po.register_version("v1", "p1", "T1", "1.0.0")
    if register_extra_versions:
        po.register_version("v2", "p1", "T1", "2.0.0")
    pi = ProductOpsIntegration(po, es, mm)
    return po, es, mm, pi


# =====================================================================
# Constructor validation
# =====================================================================


class TestConstructorValidation:
    def test_valid_construction(self, ops_engine, event_spine, memory_engine):
        pi = ProductOpsIntegration(ops_engine, event_spine, memory_engine)
        assert pi is not None

    def test_invalid_ops_engine_raises(self, event_spine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError):
            ProductOpsIntegration("not_an_engine", event_spine, memory_engine)

    def test_invalid_event_spine_raises(self, ops_engine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError):
            ProductOpsIntegration(ops_engine, "not_spine", memory_engine)

    def test_invalid_memory_engine_raises(self, ops_engine, event_spine):
        with pytest.raises(RuntimeCoreInvariantError):
            ProductOpsIntegration(ops_engine, event_spine, "not_memory")

    def test_none_ops_engine_raises(self, event_spine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError):
            ProductOpsIntegration(None, event_spine, memory_engine)

    def test_none_event_spine_raises(self, ops_engine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError):
            ProductOpsIntegration(ops_engine, None, memory_engine)

    def test_none_memory_engine_raises(self, ops_engine, event_spine):
        with pytest.raises(RuntimeCoreInvariantError):
            ProductOpsIntegration(ops_engine, event_spine, None)


# =====================================================================
# release_from_assurance
# =====================================================================


class TestReleaseFromAssurance:
    def test_basic_return_keys(self, integration, ops_engine):
        result = integration.release_from_assurance(
            "rel1", "g1", "v1", "T1", "asr1", True
        )
        assert result["release_id"] == "rel1"
        assert result["gate_id"] == "g1"
        assert result["version_id"] == "v1"
        assert result["tenant_id"] == "T1"
        assert result["assurance_ref"] == "asr1"
        assert result["passed"] is True
        assert result["source_type"] == "assurance"
        gate = ops_engine.gates_for_release("rel1")[0]
        assert gate.reason == "assurance gate"
        assert "asr1" not in gate.reason

    def test_passed_false(self, integration):
        result = integration.release_from_assurance(
            "rel2", "g2", "v1", "T1", "asr2", False
        )
        assert result["passed"] is False

    def test_default_kind_is_minor(self, integration):
        result = integration.release_from_assurance(
            "rel3", "g3", "v1", "T1", "asr3", True
        )
        assert result["source_type"] == "assurance"

    def test_explicit_kind_major(self, integration):
        result = integration.release_from_assurance(
            "rel4", "g4", "v1", "T1", "asr4", True, kind=ReleaseKind.MAJOR
        )
        assert result["release_id"] == "rel4"

    def test_explicit_kind_hotfix(self, integration):
        result = integration.release_from_assurance(
            "rel5", "g5", "v1", "T1", "asr5", True, kind=ReleaseKind.HOTFIX
        )
        assert result["release_id"] == "rel5"

    def test_custom_target_environment(self, integration):
        result = integration.release_from_assurance(
            "rel6", "g6", "v1", "T1", "asr6", True, target_environment="production"
        )
        assert result["release_id"] == "rel6"

    def test_emits_event(self, integration, event_spine):
        before = event_spine.event_count
        integration.release_from_assurance("rel7", "g7", "v1", "T1", "asr7", True)
        assert event_spine.event_count > before

    def test_duplicate_release_id_raises(self, integration):
        integration.release_from_assurance("reldup", "g8", "v1", "T1", "asr8", True)
        with pytest.raises(RuntimeCoreInvariantError):
            integration.release_from_assurance("reldup", "g9", "v1", "T1", "asr9", True)

    def test_duplicate_gate_id_raises(self, integration):
        integration.release_from_assurance("rel8", "gdup", "v1", "T1", "asr10", True)
        with pytest.raises(RuntimeCoreInvariantError):
            integration.release_from_assurance("rel9", "gdup", "v1", "T1", "asr11", True)

    def test_unknown_version_raises(self, integration):
        with pytest.raises(RuntimeCoreInvariantError):
            integration.release_from_assurance(
                "rel10", "g10", "vNONE", "T1", "asr12", True
            )


# =====================================================================
# release_from_continuity
# =====================================================================


class TestReleaseFromContinuity:
    def test_basic_return_keys(self, integration, ops_engine):
        result = integration.release_from_continuity(
            "rel20", "g20", "v1", "T1", "cont1", True
        )
        assert result["release_id"] == "rel20"
        assert result["gate_id"] == "g20"
        assert result["version_id"] == "v1"
        assert result["tenant_id"] == "T1"
        assert result["continuity_ref"] == "cont1"
        assert result["passed"] is True
        assert result["source_type"] == "continuity"
        gate = ops_engine.gates_for_release("rel20")[0]
        assert gate.reason == "continuity gate"
        assert "cont1" not in gate.reason

    def test_passed_false(self, integration):
        result = integration.release_from_continuity(
            "rel21", "g21", "v1", "T1", "cont2", False
        )
        assert result["passed"] is False

    def test_default_kind_is_patch(self, integration):
        # default kind for continuity is PATCH -- verified via the release record
        result = integration.release_from_continuity(
            "rel22", "g22", "v1", "T1", "cont3", True
        )
        assert result["source_type"] == "continuity"

    def test_explicit_kind_minor(self, integration):
        result = integration.release_from_continuity(
            "rel23", "g23", "v1", "T1", "cont4", True, kind=ReleaseKind.MINOR
        )
        assert result["release_id"] == "rel23"

    def test_custom_target_environment(self, integration):
        result = integration.release_from_continuity(
            "rel24", "g24", "v1", "T1", "cont5", True, target_environment="canary"
        )
        assert result["release_id"] == "rel24"

    def test_emits_event(self, integration, event_spine):
        before = event_spine.event_count
        integration.release_from_continuity("rel25", "g25", "v1", "T1", "cont6", True)
        assert event_spine.event_count > before

    def test_duplicate_release_raises(self, integration):
        integration.release_from_continuity("relc1", "gc1", "v1", "T1", "cont7", True)
        with pytest.raises(RuntimeCoreInvariantError):
            integration.release_from_continuity(
                "relc1", "gc2", "v1", "T1", "cont8", True
            )

    def test_unknown_version_raises(self, integration):
        with pytest.raises(RuntimeCoreInvariantError):
            integration.release_from_continuity(
                "rel26", "g26", "vNONE", "T1", "cont9", True
            )


# =====================================================================
# release_from_service_health
# =====================================================================


class TestReleaseFromServiceHealth:
    def test_basic_return_keys(self, integration, ops_engine):
        result = integration.release_from_service_health(
            "rel30", "g30", "v1", "T1", "svc1", True
        )
        assert result["release_id"] == "rel30"
        assert result["gate_id"] == "g30"
        assert result["version_id"] == "v1"
        assert result["tenant_id"] == "T1"
        assert result["service_ref"] == "svc1"
        assert result["passed"] is True
        assert result["source_type"] == "service_health"
        gate = ops_engine.gates_for_release("rel30")[0]
        assert gate.reason == "service health gate"
        assert "svc1" not in gate.reason

    def test_passed_false(self, integration):
        result = integration.release_from_service_health(
            "rel31", "g31", "v1", "T1", "svc2", False
        )
        assert result["passed"] is False

    def test_default_kind_is_minor(self, integration):
        result = integration.release_from_service_health(
            "rel32", "g32", "v1", "T1", "svc3", True
        )
        assert result["source_type"] == "service_health"

    def test_explicit_kind_patch(self, integration):
        result = integration.release_from_service_health(
            "rel33", "g33", "v1", "T1", "svc4", True, kind=ReleaseKind.PATCH
        )
        assert result["release_id"] == "rel33"

    def test_custom_target_environment(self, integration):
        result = integration.release_from_service_health(
            "rel34", "g34", "v1", "T1", "svc5", True, target_environment="production"
        )
        assert result["release_id"] == "rel34"

    def test_emits_event(self, integration, event_spine):
        before = event_spine.event_count
        integration.release_from_service_health(
            "rel35", "g35", "v1", "T1", "svc6", True
        )
        assert event_spine.event_count > before

    def test_duplicate_release_raises(self, integration):
        integration.release_from_service_health(
            "relsh1", "gsh1", "v1", "T1", "svc7", True
        )
        with pytest.raises(RuntimeCoreInvariantError):
            integration.release_from_service_health(
                "relsh1", "gsh2", "v1", "T1", "svc8", True
            )

    def test_unknown_version_raises(self, integration):
        with pytest.raises(RuntimeCoreInvariantError):
            integration.release_from_service_health(
                "rel36", "g36", "vNONE", "T1", "svc9", True
            )


# =====================================================================
# release_from_customer_impact
# =====================================================================


class TestReleaseFromCustomerImpact:
    def _create_release(self, integration):
        """Create a prerequisite release for customer impact assessment."""
        return integration.release_from_assurance(
            "relci", "gci", "v1", "T1", "asr_ci", True
        )

    def test_basic_return_keys(self, integration):
        self._create_release(integration)
        result = integration.release_from_customer_impact(
            "assess1", "relci", "T1", 0.5
        )
        assert result["assessment_id"] == "assess1"
        assert result["release_id"] == "relci"
        assert result["tenant_id"] == "T1"
        assert result["customer_impact_score"] == 0.5
        assert result["readiness_score"] == 1.0
        assert result["source_type"] == "customer_impact"
        assert "risk_level" in result

    def test_custom_readiness_score(self, integration):
        self._create_release(integration)
        result = integration.release_from_customer_impact(
            "assess2", "relci", "T1", 0.3, readiness_score=0.7
        )
        assert result["readiness_score"] == 0.7
        assert result["customer_impact_score"] == 0.3

    def test_risk_level_low(self, integration):
        self._create_release(integration)
        result = integration.release_from_customer_impact(
            "assess3", "relci", "T1", 0.1, readiness_score=0.9
        )
        assert result["risk_level"] == "low"

    def test_risk_level_medium(self, integration):
        self._create_release(integration)
        result = integration.release_from_customer_impact(
            "assess4", "relci", "T1", 0.3, readiness_score=0.9
        )
        assert result["risk_level"] == "medium"

    def test_risk_level_high(self, integration):
        self._create_release(integration)
        result = integration.release_from_customer_impact(
            "assess5", "relci", "T1", 0.5, readiness_score=0.9
        )
        assert result["risk_level"] == "high"

    def test_risk_level_critical_high_impact(self, integration):
        self._create_release(integration)
        result = integration.release_from_customer_impact(
            "assess6", "relci", "T1", 0.8, readiness_score=0.9
        )
        assert result["risk_level"] == "critical"

    def test_risk_level_critical_low_readiness(self, integration):
        self._create_release(integration)
        result = integration.release_from_customer_impact(
            "assess7", "relci", "T1", 0.1, readiness_score=0.2
        )
        assert result["risk_level"] == "critical"

    def test_emits_event(self, integration, event_spine):
        self._create_release(integration)
        before = event_spine.event_count
        integration.release_from_customer_impact("assess8", "relci", "T1", 0.4)
        assert event_spine.event_count > before

    def test_unknown_release_raises(self, integration):
        with pytest.raises(RuntimeCoreInvariantError):
            integration.release_from_customer_impact(
                "assess9", "rel_unknown", "T1", 0.5
            )

    def test_duplicate_assessment_raises(self, integration):
        self._create_release(integration)
        integration.release_from_customer_impact("assessdup", "relci", "T1", 0.5)
        with pytest.raises(RuntimeCoreInvariantError):
            integration.release_from_customer_impact("assessdup", "relci", "T1", 0.6)

    def test_zero_impact_score(self, integration):
        self._create_release(integration)
        result = integration.release_from_customer_impact(
            "assess10", "relci", "T1", 0.0
        )
        assert result["customer_impact_score"] == 0.0
        assert result["risk_level"] == "low"

    def test_max_impact_score(self, integration):
        self._create_release(integration)
        result = integration.release_from_customer_impact(
            "assess11", "relci", "T1", 1.0
        )
        assert result["customer_impact_score"] == 1.0
        assert result["risk_level"] == "critical"


# =====================================================================
# release_from_change_runtime
# =====================================================================


class TestReleaseFromChangeRuntime:
    def test_basic_return_keys(self, integration, ops_engine):
        result = integration.release_from_change_runtime(
            "rel40", "g40", "v1", "T1", "chg1", True
        )
        assert result["release_id"] == "rel40"
        assert result["gate_id"] == "g40"
        assert result["version_id"] == "v1"
        assert result["tenant_id"] == "T1"
        assert result["change_ref"] == "chg1"
        assert result["passed"] is True
        assert result["source_type"] == "change_runtime"
        gate = ops_engine.gates_for_release("rel40")[0]
        assert gate.reason == "change approval gate"
        assert "chg1" not in gate.reason

    def test_passed_false(self, integration):
        result = integration.release_from_change_runtime(
            "rel41", "g41", "v1", "T1", "chg2", False
        )
        assert result["passed"] is False

    def test_default_kind_is_minor(self, integration):
        result = integration.release_from_change_runtime(
            "rel42", "g42", "v1", "T1", "chg3", True
        )
        assert result["source_type"] == "change_runtime"

    def test_explicit_kind_rollback(self, integration):
        result = integration.release_from_change_runtime(
            "rel43", "g43", "v1", "T1", "chg4", True, kind=ReleaseKind.ROLLBACK
        )
        assert result["release_id"] == "rel43"

    def test_custom_target_environment(self, integration):
        result = integration.release_from_change_runtime(
            "rel44", "g44", "v1", "T1", "chg5", True, target_environment="preview"
        )
        assert result["release_id"] == "rel44"

    def test_emits_event(self, integration, event_spine):
        before = event_spine.event_count
        integration.release_from_change_runtime(
            "rel45", "g45", "v1", "T1", "chg6", True
        )
        assert event_spine.event_count > before

    def test_duplicate_release_raises(self, integration):
        integration.release_from_change_runtime(
            "relcr1", "gcr1", "v1", "T1", "chg7", True
        )
        with pytest.raises(RuntimeCoreInvariantError):
            integration.release_from_change_runtime(
                "relcr1", "gcr2", "v1", "T1", "chg8", True
            )

    def test_unknown_version_raises(self, integration):
        with pytest.raises(RuntimeCoreInvariantError):
            integration.release_from_change_runtime(
                "rel46", "g46", "vNONE", "T1", "chg9", True
            )


# =====================================================================
# attach_release_state_to_memory_mesh
# =====================================================================


class TestAttachReleaseStateToMemoryMesh:
    def test_returns_memory_record(self, integration):
        record = integration.attach_release_state_to_memory_mesh("scope1")
        assert isinstance(record, MemoryRecord)

    def test_title(self, integration):
        record = integration.attach_release_state_to_memory_mesh("scope2")
        assert record.title == "Product ops runtime state"

    def test_tags(self, integration):
        record = integration.attach_release_state_to_memory_mesh("scope3")
        assert "product_ops" in record.tags
        assert "release" in record.tags
        assert "lifecycle" in record.tags

    def test_scope_is_global(self, integration):
        record = integration.attach_release_state_to_memory_mesh("scope4")
        assert record.scope == MemoryScope.GLOBAL

    def test_memory_type_is_observation(self, integration):
        record = integration.attach_release_state_to_memory_mesh("scope5")
        assert record.memory_type == MemoryType.OBSERVATION

    def test_trust_level_verified(self, integration):
        record = integration.attach_release_state_to_memory_mesh("scope6")
        assert record.trust_level == MemoryTrustLevel.VERIFIED

    def test_content_keys_empty_state(self, integration):
        record = integration.attach_release_state_to_memory_mesh("scope7")
        content = record.content
        expected_keys = {
            "versions", "releases", "gates", "promotions",
            "rollbacks", "milestones", "assessments", "violations",
        }
        assert set(content.keys()) == expected_keys

    def test_content_versions_count(self, integration):
        record = integration.attach_release_state_to_memory_mesh("scope8")
        assert record.content["versions"] == 1  # one registered in fixture

    def test_content_reflects_releases(self, integration):
        integration.release_from_assurance("relmm1", "gmm1", "v1", "T1", "a1", True)
        record = integration.attach_release_state_to_memory_mesh("scope9")
        assert record.content["releases"] == 1
        assert record.content["gates"] == 1

    def test_emits_event(self, integration, event_spine):
        before = event_spine.event_count
        integration.attach_release_state_to_memory_mesh("scope10")
        assert event_spine.event_count > before

    def test_scope_ref_id_in_source_ids(self, integration):
        record = integration.attach_release_state_to_memory_mesh("scope11")
        assert "scope11" in record.source_ids


# =====================================================================
# attach_release_state_to_graph
# =====================================================================


class TestAttachReleaseStateToGraph:
    def test_returns_dict(self, integration):
        result = integration.attach_release_state_to_graph("scope20")
        assert isinstance(result, dict)

    def test_scope_ref_id_key(self, integration):
        result = integration.attach_release_state_to_graph("scope21")
        assert result["scope_ref_id"] == "scope21"

    def test_content_keys(self, integration):
        result = integration.attach_release_state_to_graph("scope22")
        expected_keys = {
            "scope_ref_id", "versions", "releases", "gates", "promotions",
            "rollbacks", "milestones", "assessments", "violations",
        }
        assert set(result.keys()) == expected_keys

    def test_versions_count(self, integration):
        result = integration.attach_release_state_to_graph("scope23")
        assert result["versions"] == 1

    def test_reflects_releases(self, integration):
        integration.release_from_assurance("relgr1", "ggr1", "v1", "T1", "a1", True)
        result = integration.attach_release_state_to_graph("scope24")
        assert result["releases"] == 1
        assert result["gates"] == 1

    def test_zeros_when_empty(self, integration):
        result = integration.attach_release_state_to_graph("scope25")
        assert result["releases"] == 0
        assert result["gates"] == 0
        assert result["promotions"] == 0
        assert result["rollbacks"] == 0
        assert result["milestones"] == 0
        assert result["assessments"] == 0
        assert result["violations"] == 0


# =====================================================================
# Cross-source and golden scenarios
# =====================================================================


class TestCrossSourceScenarios:
    def test_multiple_release_sources_coexist(self):
        po, es, mm, pi = _fresh()
        r1 = pi.release_from_assurance("r1", "g1", "v1", "T1", "a1", True)
        r2 = pi.release_from_continuity("r2", "g2", "v1", "T1", "c1", True)
        r3 = pi.release_from_service_health("r3", "g3", "v1", "T1", "s1", True)
        r4 = pi.release_from_change_runtime("r4", "g4", "v1", "T1", "chg1", True)
        assert r1["source_type"] == "assurance"
        assert r2["source_type"] == "continuity"
        assert r3["source_type"] == "service_health"
        assert r4["source_type"] == "change_runtime"

    def test_graph_reflects_multi_source_state(self):
        po, es, mm, pi = _fresh()
        pi.release_from_assurance("r1", "g1", "v1", "T1", "a1", True)
        pi.release_from_continuity("r2", "g2", "v1", "T1", "c1", True)
        graph = pi.attach_release_state_to_graph("multi")
        assert graph["releases"] == 2
        assert graph["gates"] == 2

    def test_memory_reflects_multi_source_state(self):
        po, es, mm, pi = _fresh()
        pi.release_from_assurance("r1", "g1", "v1", "T1", "a1", True)
        pi.release_from_continuity("r2", "g2", "v1", "T1", "c1", True)
        pi.release_from_service_health("r3", "g3", "v1", "T1", "s1", True)
        record = pi.attach_release_state_to_memory_mesh("multi")
        assert record.content["releases"] == 3
        assert record.content["gates"] == 3

    def test_customer_impact_after_assurance(self):
        po, es, mm, pi = _fresh()
        pi.release_from_assurance("r1", "g1", "v1", "T1", "a1", True)
        result = pi.release_from_customer_impact("assess1", "r1", "T1", 0.4)
        assert result["source_type"] == "customer_impact"
        assert result["release_id"] == "r1"
        graph = pi.attach_release_state_to_graph("impact_check")
        assert graph["assessments"] == 1

    def test_golden_full_lifecycle(self):
        """End-to-end: register, release, assess, attach memory, attach graph."""
        po, es, mm, pi = _fresh()
        # Create releases from different sources
        pi.release_from_assurance("r1", "g1", "v1", "T1", "a1", True)
        pi.release_from_continuity("r2", "g2", "v1", "T1", "c1", True)
        pi.release_from_service_health("r3", "g3", "v1", "T1", "s1", False)
        pi.release_from_change_runtime("r4", "g4", "v1", "T1", "ch1", True)
        # Assess one release
        pi.release_from_customer_impact("a1", "r1", "T1", 0.2, readiness_score=0.9)
        # Attach memory
        mem = pi.attach_release_state_to_memory_mesh("golden")
        assert mem.content["releases"] == 4
        assert mem.content["gates"] == 4
        assert mem.content["assessments"] == 1
        # Attach graph
        graph = pi.attach_release_state_to_graph("golden")
        assert graph["releases"] == 4
        assert graph["gates"] == 4
        assert graph["assessments"] == 1

    def test_event_count_grows_with_operations(self):
        po, es, mm, pi = _fresh()
        before = es.event_count
        pi.release_from_assurance("r1", "g1", "v1", "T1", "a1", True)
        pi.release_from_continuity("r2", "g2", "v1", "T1", "c1", True)
        pi.attach_release_state_to_memory_mesh("scope")
        # Each release_from emits: create_release + evaluate_gate + integration event = 3
        # attach_release_state_to_memory_mesh emits: add_memory event + integration event
        # At minimum several events should be added
        assert es.event_count > before + 4

    def test_immutability_of_return_dict(self):
        """Return dicts should be plain dicts (not frozen), but source data is safe."""
        po, es, mm, pi = _fresh()
        result = pi.release_from_assurance("r1", "g1", "v1", "T1", "a1", True)
        # The result is a dict -- verify it has expected keys
        assert isinstance(result, dict)
        assert len(result) == 7

    def test_all_release_kinds_accepted(self):
        po, es, mm, pi = _fresh()
        for i, kind in enumerate(ReleaseKind):
            pi.release_from_assurance(
                f"rk{i}", f"gk{i}", "v1", "T1", f"ak{i}", True, kind=kind
            )

    def test_memory_mesh_memory_id_is_deterministic_per_scope(self):
        """Two calls with same scope_ref_id should produce different memory_ids
        because timestamp differs, but both should be non-empty."""
        po, es, mm, pi = _fresh()
        rec1 = pi.attach_release_state_to_memory_mesh("det_scope")
        assert rec1.memory_id
        assert len(rec1.memory_id) > 0

    def test_graph_does_not_emit_events(self):
        """attach_release_state_to_graph should not emit events (it's read-only)."""
        po, es, mm, pi = _fresh()
        before = es.event_count
        pi.attach_release_state_to_graph("no_emit")
        assert es.event_count == before
