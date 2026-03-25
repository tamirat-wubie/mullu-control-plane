"""Tests for ConstitutionalGovernanceIntegration bridge.

Covers: constructor validation, all 6 govern_* methods, memory mesh attachment,
graph attachment, event emission, emergency mode integration, and multi-tenant
isolation.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.constitutional_governance import ConstitutionalGovernanceEngine
from mcoi_runtime.core.constitutional_governance_integration import (
    ConstitutionalGovernanceIntegration,
)
from mcoi_runtime.contracts.constitutional_governance import (
    ConstitutionRuleKind,
    EmergencyMode,
    GlobalPolicyDisposition,
    PrecedenceLevel,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPECTED_GOVERN_KEYS = {
    "decision_id",
    "tenant_id",
    "disposition",
    "matched_rule_id",
    "emergency_mode",
    "source_type",
}


def _make_engines():
    """Return (governance_engine, event_spine, memory_engine)."""
    es = EventSpineEngine()
    mm = MemoryMeshEngine()
    gov = ConstitutionalGovernanceEngine(es)
    return gov, es, mm


def _make_integration():
    """Return (integration, governance_engine, event_spine, memory_engine)."""
    gov, es, mm = _make_engines()
    bridge = ConstitutionalGovernanceIntegration(gov, es, mm)
    return bridge, gov, es, mm


# ---------------------------------------------------------------------------
# TestConstructorValidation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    """Constructor rejects invalid dependency types."""

    def test_reject_none_governance_engine(self):
        _, es, mm = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            ConstitutionalGovernanceIntegration(None, es, mm)

    def test_reject_string_governance_engine(self):
        _, es, mm = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            ConstitutionalGovernanceIntegration("not-an-engine", es, mm)

    def test_reject_dict_governance_engine(self):
        _, es, mm = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            ConstitutionalGovernanceIntegration({}, es, mm)

    def test_reject_none_event_spine(self):
        gov, _, mm = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            ConstitutionalGovernanceIntegration(gov, None, mm)

    def test_reject_string_event_spine(self):
        gov, _, mm = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            ConstitutionalGovernanceIntegration(gov, "bad", mm)

    def test_reject_none_memory_engine(self):
        gov, es, _ = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            ConstitutionalGovernanceIntegration(gov, es, None)

    def test_reject_string_memory_engine(self):
        gov, es, _ = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            ConstitutionalGovernanceIntegration(gov, es, "bad")

    def test_reject_swapped_event_spine_and_memory(self):
        gov, es, mm = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            ConstitutionalGovernanceIntegration(gov, mm, es)

    def test_accept_valid_engines(self):
        gov, es, mm = _make_engines()
        bridge = ConstitutionalGovernanceIntegration(gov, es, mm)
        assert bridge is not None


# ---------------------------------------------------------------------------
# TestGovernServiceRequest
# ---------------------------------------------------------------------------


class TestGovernServiceRequest:
    """govern_service_request returns correct dict shape and values."""

    def test_returns_dict(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_service_request("d1", "t1", "svc-001")
        assert isinstance(result, dict)

    def test_has_all_required_keys(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_service_request("d2", "t1", "svc-002")
        expected = EXPECTED_GOVERN_KEYS | {"service_ref"}
        assert set(result.keys()) == expected

    def test_source_type(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_service_request("d3", "t1", "svc-003")
        assert result["source_type"] == "service_request"

    def test_decision_id_matches(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_service_request("d4", "t1", "svc-004")
        assert result["decision_id"] == "d4"

    def test_tenant_id_matches(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_service_request("d5", "tenant-x", "svc-005")
        assert result["tenant_id"] == "tenant-x"

    def test_service_ref_matches(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_service_request("d6", "t1", "svc-ref-42")
        assert result["service_ref"] == "svc-ref-42"

    def test_default_action_allowed_no_rules(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_service_request("d7", "t1", "svc-007")
        assert result["disposition"] == GlobalPolicyDisposition.ALLOWED.value

    def test_hard_deny_rule_denies(self):
        bridge, gov, es, mm = _make_integration()
        gov.register_rule(
            "r1", "t1", "block-svc",
            kind=ConstitutionRuleKind.HARD_DENY,
            target_runtime="service_catalog",
            target_action="fulfill",
        )
        result = bridge.govern_service_request("d8", "t1", "svc-008")
        assert result["disposition"] == GlobalPolicyDisposition.DENIED.value
        assert result["matched_rule_id"] == "r1"

    def test_custom_action(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_service_request("d9", "t1", "svc-009", action="reject")
        assert result["decision_id"] == "d9"


# ---------------------------------------------------------------------------
# TestGovernRelease
# ---------------------------------------------------------------------------


class TestGovernRelease:
    """govern_release returns correct dict shape and values."""

    def test_returns_dict(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_release("d10", "t1", "rel-001")
        assert isinstance(result, dict)

    def test_has_all_required_keys(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_release("d11", "t1", "rel-002")
        expected = EXPECTED_GOVERN_KEYS | {"release_ref"}
        assert set(result.keys()) == expected

    def test_source_type(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_release("d12", "t1", "rel-003")
        assert result["source_type"] == "release"

    def test_release_ref_matches(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_release("d13", "t1", "rel-ref-99")
        assert result["release_ref"] == "rel-ref-99"

    def test_default_allowed(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_release("d14", "t1", "rel-004")
        assert result["disposition"] == GlobalPolicyDisposition.ALLOWED.value

    def test_hard_deny_rule(self):
        bridge, gov, es, mm = _make_integration()
        gov.register_rule(
            "r2", "t1", "block-release",
            kind=ConstitutionRuleKind.HARD_DENY,
            target_runtime="product_ops",
            target_action="promote",
        )
        result = bridge.govern_release("d15", "t1", "rel-005")
        assert result["disposition"] == GlobalPolicyDisposition.DENIED.value

    def test_soft_deny_escalates(self):
        bridge, gov, es, mm = _make_integration()
        gov.register_rule(
            "r3", "t1", "soft-block-release",
            kind=ConstitutionRuleKind.SOFT_DENY,
            target_runtime="product_ops",
            target_action="promote",
        )
        result = bridge.govern_release("d16", "t1", "rel-006")
        assert result["disposition"] == GlobalPolicyDisposition.ESCALATED.value


# ---------------------------------------------------------------------------
# TestGovernSettlement
# ---------------------------------------------------------------------------


class TestGovernSettlement:
    """govern_settlement returns correct dict shape and values."""

    def test_returns_dict(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_settlement("d20", "t1", "stl-001")
        assert isinstance(result, dict)

    def test_has_all_required_keys(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_settlement("d21", "t1", "stl-002")
        expected = EXPECTED_GOVERN_KEYS | {"settlement_ref"}
        assert set(result.keys()) == expected

    def test_source_type(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_settlement("d22", "t1", "stl-003")
        assert result["source_type"] == "settlement"

    def test_settlement_ref_matches(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_settlement("d23", "t1", "stl-ref-77")
        assert result["settlement_ref"] == "stl-ref-77"

    def test_default_allowed(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_settlement("d24", "t1", "stl-004")
        assert result["disposition"] == GlobalPolicyDisposition.ALLOWED.value

    def test_restrict_rule(self):
        bridge, gov, es, mm = _make_integration()
        gov.register_rule(
            "r4", "t1", "restrict-settle",
            kind=ConstitutionRuleKind.RESTRICT,
            target_runtime="settlement",
            target_action="settle",
        )
        result = bridge.govern_settlement("d25", "t1", "stl-005")
        assert result["disposition"] == GlobalPolicyDisposition.RESTRICTED.value


# ---------------------------------------------------------------------------
# TestGovernMarketplaceOffering
# ---------------------------------------------------------------------------


class TestGovernMarketplaceOffering:
    """govern_marketplace_offering returns correct dict shape and values."""

    def test_returns_dict(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_marketplace_offering("d30", "t1", "off-001")
        assert isinstance(result, dict)

    def test_has_all_required_keys(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_marketplace_offering("d31", "t1", "off-002")
        expected = EXPECTED_GOVERN_KEYS | {"offering_ref"}
        assert set(result.keys()) == expected

    def test_source_type(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_marketplace_offering("d32", "t1", "off-003")
        assert result["source_type"] == "marketplace_offering"

    def test_offering_ref_matches(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_marketplace_offering("d33", "t1", "off-ref-88")
        assert result["offering_ref"] == "off-ref-88"

    def test_default_allowed(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_marketplace_offering("d34", "t1", "off-004")
        assert result["disposition"] == GlobalPolicyDisposition.ALLOWED.value

    def test_hard_deny_blocks_marketplace(self):
        bridge, gov, es, mm = _make_integration()
        gov.register_rule(
            "r5", "t1", "block-marketplace",
            kind=ConstitutionRuleKind.HARD_DENY,
            target_runtime="marketplace",
            target_action="activate",
        )
        result = bridge.govern_marketplace_offering("d35", "t1", "off-005")
        assert result["disposition"] == GlobalPolicyDisposition.DENIED.value
        assert result["matched_rule_id"] == "r5"

    def test_allow_rule_allows(self):
        bridge, gov, es, mm = _make_integration()
        gov.register_rule(
            "r6", "t1", "allow-marketplace",
            kind=ConstitutionRuleKind.ALLOW,
            target_runtime="marketplace",
            target_action="activate",
        )
        result = bridge.govern_marketplace_offering("d36", "t1", "off-006")
        assert result["disposition"] == GlobalPolicyDisposition.ALLOWED.value


# ---------------------------------------------------------------------------
# TestGovernHumanWorkflow
# ---------------------------------------------------------------------------


class TestGovernHumanWorkflow:
    """govern_human_workflow returns correct dict shape and values."""

    def test_returns_dict(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_human_workflow("d40", "t1", "wf-001")
        assert isinstance(result, dict)

    def test_has_all_required_keys(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_human_workflow("d41", "t1", "wf-002")
        expected = EXPECTED_GOVERN_KEYS | {"workflow_ref"}
        assert set(result.keys()) == expected

    def test_source_type(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_human_workflow("d42", "t1", "wf-003")
        assert result["source_type"] == "human_workflow"

    def test_workflow_ref_matches(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_human_workflow("d43", "t1", "wf-ref-55")
        assert result["workflow_ref"] == "wf-ref-55"

    def test_default_allowed(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_human_workflow("d44", "t1", "wf-004")
        assert result["disposition"] == GlobalPolicyDisposition.ALLOWED.value

    def test_hard_deny_blocks(self):
        bridge, gov, es, mm = _make_integration()
        gov.register_rule(
            "r7", "t1", "block-workflow",
            kind=ConstitutionRuleKind.HARD_DENY,
            target_runtime="human_workflow",
            target_action="approve",
        )
        result = bridge.govern_human_workflow("d45", "t1", "wf-005")
        assert result["disposition"] == GlobalPolicyDisposition.DENIED.value

    def test_require_rule_allows(self):
        bridge, gov, es, mm = _make_integration()
        gov.register_rule(
            "r8", "t1", "require-workflow",
            kind=ConstitutionRuleKind.REQUIRE,
            target_runtime="human_workflow",
            target_action="approve",
        )
        result = bridge.govern_human_workflow("d46", "t1", "wf-006")
        assert result["disposition"] == GlobalPolicyDisposition.ALLOWED.value


# ---------------------------------------------------------------------------
# TestGovernExternalConnectorAction
# ---------------------------------------------------------------------------


class TestGovernExternalConnectorAction:
    """govern_external_connector_action returns correct dict shape and values."""

    def test_returns_dict(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_external_connector_action("d50", "t1", "conn-001")
        assert isinstance(result, dict)

    def test_has_all_required_keys(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_external_connector_action("d51", "t1", "conn-002")
        expected = EXPECTED_GOVERN_KEYS | {"connector_ref"}
        assert set(result.keys()) == expected

    def test_source_type(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_external_connector_action("d52", "t1", "conn-003")
        assert result["source_type"] == "external_connector"

    def test_connector_ref_matches(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_external_connector_action("d53", "t1", "conn-ref-66")
        assert result["connector_ref"] == "conn-ref-66"

    def test_default_allowed(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_external_connector_action("d54", "t1", "conn-004")
        assert result["disposition"] == GlobalPolicyDisposition.ALLOWED.value

    def test_hard_deny_blocks(self):
        bridge, gov, es, mm = _make_integration()
        gov.register_rule(
            "r9", "t1", "block-connector",
            kind=ConstitutionRuleKind.HARD_DENY,
            target_runtime="connector",
            target_action="execute",
        )
        result = bridge.govern_external_connector_action("d55", "t1", "conn-005")
        assert result["disposition"] == GlobalPolicyDisposition.DENIED.value
        assert result["matched_rule_id"] == "r9"

    def test_custom_action(self):
        bridge, *_ = _make_integration()
        result = bridge.govern_external_connector_action(
            "d56", "t1", "conn-006", action="validate"
        )
        assert result["decision_id"] == "d56"


# ---------------------------------------------------------------------------
# TestAttachConstitutionStateToMemoryMesh
# ---------------------------------------------------------------------------


class TestAttachConstitutionStateToMemoryMesh:
    """attach_constitution_state_to_memory_mesh returns MemoryRecord."""

    def test_returns_memory_record(self):
        bridge, *_ = _make_integration()
        mem = bridge.attach_constitution_state_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_title_contains_scope(self):
        bridge, *_ = _make_integration()
        mem = bridge.attach_constitution_state_to_memory_mesh("scope-2")
        assert "scope-2" in mem.title

    def test_tags_include_constitutional_governance(self):
        bridge, *_ = _make_integration()
        mem = bridge.attach_constitution_state_to_memory_mesh("scope-3")
        assert "constitutional_governance" in mem.tags

    def test_tags_include_global_policy(self):
        bridge, *_ = _make_integration()
        mem = bridge.attach_constitution_state_to_memory_mesh("scope-4")
        assert "global_policy" in mem.tags

    def test_tags_include_compliance(self):
        bridge, *_ = _make_integration()
        mem = bridge.attach_constitution_state_to_memory_mesh("scope-5")
        assert "compliance" in mem.tags

    def test_content_has_total_rules(self):
        bridge, *_ = _make_integration()
        mem = bridge.attach_constitution_state_to_memory_mesh("scope-6")
        assert "total_rules" in mem.content

    def test_content_has_active_rules(self):
        bridge, *_ = _make_integration()
        mem = bridge.attach_constitution_state_to_memory_mesh("scope-7")
        assert "active_rules" in mem.content

    def test_content_has_total_bundles(self):
        bridge, *_ = _make_integration()
        mem = bridge.attach_constitution_state_to_memory_mesh("scope-8")
        assert "total_bundles" in mem.content

    def test_content_has_total_overrides(self):
        bridge, *_ = _make_integration()
        mem = bridge.attach_constitution_state_to_memory_mesh("scope-9")
        assert "total_overrides" in mem.content

    def test_content_has_total_decisions(self):
        bridge, *_ = _make_integration()
        mem = bridge.attach_constitution_state_to_memory_mesh("scope-10")
        assert "total_decisions" in mem.content

    def test_content_has_total_violations(self):
        bridge, *_ = _make_integration()
        mem = bridge.attach_constitution_state_to_memory_mesh("scope-11")
        assert "total_violations" in mem.content

    def test_content_has_emergency_mode(self):
        bridge, *_ = _make_integration()
        mem = bridge.attach_constitution_state_to_memory_mesh("scope-12")
        assert "emergency_mode" in mem.content

    def test_content_reflects_registered_rules(self):
        bridge, gov, es, mm = _make_integration()
        gov.register_rule("r-mem-1", "scope-13", "rule-a",
                          target_runtime="all", target_action="all")
        gov.register_rule("r-mem-2", "scope-13", "rule-b",
                          target_runtime="all", target_action="all")
        mem = bridge.attach_constitution_state_to_memory_mesh("scope-13")
        assert mem.content["total_rules"] == 2
        assert mem.content["active_rules"] == 2


# ---------------------------------------------------------------------------
# TestAttachConstitutionStateToGraph
# ---------------------------------------------------------------------------


class TestAttachConstitutionStateToGraph:
    """attach_constitution_state_to_graph returns dict with 8 keys."""

    def test_returns_dict(self):
        bridge, *_ = _make_integration()
        result = bridge.attach_constitution_state_to_graph("scope-g1")
        assert isinstance(result, dict)

    def test_has_scope_ref_id(self):
        bridge, *_ = _make_integration()
        result = bridge.attach_constitution_state_to_graph("scope-g2")
        assert result["scope_ref_id"] == "scope-g2"

    def test_has_all_eight_keys(self):
        bridge, *_ = _make_integration()
        result = bridge.attach_constitution_state_to_graph("scope-g3")
        expected_keys = {
            "scope_ref_id", "total_rules", "active_rules", "total_bundles",
            "total_overrides", "total_decisions", "total_violations",
            "emergency_mode",
        }
        assert set(result.keys()) == expected_keys

    def test_emergency_mode_default_normal(self):
        bridge, *_ = _make_integration()
        result = bridge.attach_constitution_state_to_graph("scope-g4")
        assert result["emergency_mode"] == EmergencyMode.NORMAL.value

    def test_counters_zero_by_default(self):
        bridge, *_ = _make_integration()
        result = bridge.attach_constitution_state_to_graph("scope-g5")
        assert result["total_rules"] == 0
        assert result["active_rules"] == 0
        assert result["total_bundles"] == 0
        assert result["total_overrides"] == 0
        assert result["total_decisions"] == 0
        assert result["total_violations"] == 0

    def test_reflects_registered_rules(self):
        bridge, gov, es, mm = _make_integration()
        gov.register_rule("r-g1", "scope-g6", "rule-graph",
                          target_runtime="all", target_action="all")
        result = bridge.attach_constitution_state_to_graph("scope-g6")
        assert result["total_rules"] == 1
        assert result["active_rules"] == 1


# ---------------------------------------------------------------------------
# TestEventEmission
# ---------------------------------------------------------------------------


class TestEventEmission:
    """Every integration method emits at least one event."""

    def test_govern_service_request_emits(self):
        bridge, gov, es, mm = _make_integration()
        before = es.event_count
        bridge.govern_service_request("ev-1", "t1", "svc-ev")
        assert es.event_count > before

    def test_govern_release_emits(self):
        bridge, gov, es, mm = _make_integration()
        before = es.event_count
        bridge.govern_release("ev-2", "t1", "rel-ev")
        assert es.event_count > before

    def test_govern_settlement_emits(self):
        bridge, gov, es, mm = _make_integration()
        before = es.event_count
        bridge.govern_settlement("ev-3", "t1", "stl-ev")
        assert es.event_count > before

    def test_govern_marketplace_offering_emits(self):
        bridge, gov, es, mm = _make_integration()
        before = es.event_count
        bridge.govern_marketplace_offering("ev-4", "t1", "off-ev")
        assert es.event_count > before

    def test_govern_human_workflow_emits(self):
        bridge, gov, es, mm = _make_integration()
        before = es.event_count
        bridge.govern_human_workflow("ev-5", "t1", "wf-ev")
        assert es.event_count > before

    def test_govern_external_connector_action_emits(self):
        bridge, gov, es, mm = _make_integration()
        before = es.event_count
        bridge.govern_external_connector_action("ev-6", "t1", "conn-ev")
        assert es.event_count > before

    def test_memory_mesh_attachment_emits(self):
        bridge, gov, es, mm = _make_integration()
        before = es.event_count
        bridge.attach_constitution_state_to_memory_mesh("ev-scope")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# TestEmergencyModeIntegration
# ---------------------------------------------------------------------------


class TestEmergencyModeIntegration:
    """Emergency lockdown causes all govern methods to return denied."""

    def _lockdown(self, gov, tenant="t-em"):
        gov.enter_emergency_mode(
            "em-1", tenant, EmergencyMode.LOCKDOWN,
            authority_ref="admin", reason="test lockdown",
        )

    def test_lockdown_denies_service_request(self):
        bridge, gov, es, mm = _make_integration()
        self._lockdown(gov)
        result = bridge.govern_service_request("em-d1", "t-em", "svc-em")
        assert result["disposition"] == GlobalPolicyDisposition.DENIED.value
        assert result["emergency_mode"] == EmergencyMode.LOCKDOWN.value

    def test_lockdown_denies_release(self):
        bridge, gov, es, mm = _make_integration()
        self._lockdown(gov)
        result = bridge.govern_release("em-d2", "t-em", "rel-em")
        assert result["disposition"] == GlobalPolicyDisposition.DENIED.value

    def test_lockdown_denies_settlement(self):
        bridge, gov, es, mm = _make_integration()
        self._lockdown(gov)
        result = bridge.govern_settlement("em-d3", "t-em", "stl-em")
        assert result["disposition"] == GlobalPolicyDisposition.DENIED.value

    def test_lockdown_denies_marketplace(self):
        bridge, gov, es, mm = _make_integration()
        self._lockdown(gov)
        result = bridge.govern_marketplace_offering("em-d4", "t-em", "off-em")
        assert result["disposition"] == GlobalPolicyDisposition.DENIED.value

    def test_lockdown_denies_human_workflow(self):
        bridge, gov, es, mm = _make_integration()
        self._lockdown(gov)
        result = bridge.govern_human_workflow("em-d5", "t-em", "wf-em")
        assert result["disposition"] == GlobalPolicyDisposition.DENIED.value

    def test_lockdown_denies_external_connector(self):
        bridge, gov, es, mm = _make_integration()
        self._lockdown(gov)
        result = bridge.govern_external_connector_action("em-d6", "t-em", "conn-em")
        assert result["disposition"] == GlobalPolicyDisposition.DENIED.value

    def test_lockdown_matched_rule_id_emergency(self):
        bridge, gov, es, mm = _make_integration()
        self._lockdown(gov)
        result = bridge.govern_service_request("em-d7", "t-em", "svc-em2")
        assert result["matched_rule_id"] == "emergency_lockdown"

    def test_degraded_mode_restricts(self):
        bridge, gov, es, mm = _make_integration()
        gov.enter_emergency_mode(
            "em-deg", "t-deg", EmergencyMode.DEGRADED,
            authority_ref="admin", reason="degraded test",
        )
        result = bridge.govern_service_request("em-d8", "t-deg", "svc-deg")
        assert result["disposition"] == GlobalPolicyDisposition.RESTRICTED.value
        assert result["emergency_mode"] == EmergencyMode.DEGRADED.value

    def test_restricted_mode_restricts(self):
        bridge, gov, es, mm = _make_integration()
        gov.enter_emergency_mode(
            "em-res", "t-res", EmergencyMode.RESTRICTED,
            authority_ref="admin", reason="restricted test",
        )
        result = bridge.govern_release("em-d9", "t-res", "rel-res")
        assert result["disposition"] == GlobalPolicyDisposition.RESTRICTED.value
        assert result["emergency_mode"] == EmergencyMode.RESTRICTED.value

    def test_memory_mesh_reflects_lockdown(self):
        bridge, gov, es, mm = _make_integration()
        gov.enter_emergency_mode(
            "em-mem", "t-emmem", EmergencyMode.LOCKDOWN,
            authority_ref="admin", reason="test",
        )
        mem = bridge.attach_constitution_state_to_memory_mesh("t-emmem")
        assert mem.content["emergency_mode"] == EmergencyMode.LOCKDOWN.value

    def test_graph_reflects_lockdown(self):
        bridge, gov, es, mm = _make_integration()
        gov.enter_emergency_mode(
            "em-graph", "t-emgraph", EmergencyMode.LOCKDOWN,
            authority_ref="admin", reason="test",
        )
        result = bridge.attach_constitution_state_to_graph("t-emgraph")
        assert result["emergency_mode"] == EmergencyMode.LOCKDOWN.value


# ---------------------------------------------------------------------------
# TestMultiTenantIsolation
# ---------------------------------------------------------------------------


class TestMultiTenantIsolation:
    """Different tenants get independent governance decisions."""

    def test_different_tenants_independent_decisions(self):
        bridge, gov, es, mm = _make_integration()
        gov.register_rule(
            "iso-r1", "tenant-a", "block-a",
            kind=ConstitutionRuleKind.HARD_DENY,
            target_runtime="marketplace",
            target_action="activate",
        )
        result_a = bridge.govern_marketplace_offering("iso-d1", "tenant-a", "off-a")
        result_b = bridge.govern_marketplace_offering("iso-d2", "tenant-b", "off-b")
        assert result_a["disposition"] == GlobalPolicyDisposition.DENIED.value
        assert result_b["disposition"] == GlobalPolicyDisposition.ALLOWED.value

    def test_lockdown_only_affects_target_tenant(self):
        bridge, gov, es, mm = _make_integration()
        gov.enter_emergency_mode(
            "iso-em", "tenant-c", EmergencyMode.LOCKDOWN,
            authority_ref="admin", reason="test",
        )
        result_c = bridge.govern_service_request("iso-d3", "tenant-c", "svc-c")
        result_d = bridge.govern_service_request("iso-d4", "tenant-d", "svc-d")
        assert result_c["disposition"] == GlobalPolicyDisposition.DENIED.value
        assert result_d["disposition"] == GlobalPolicyDisposition.ALLOWED.value

    def test_graph_snapshot_per_tenant(self):
        bridge, gov, es, mm = _make_integration()
        gov.register_rule(
            "iso-r2", "tenant-e", "rule-e",
            target_runtime="all", target_action="all",
        )
        graph_e = bridge.attach_constitution_state_to_graph("tenant-e")
        graph_f = bridge.attach_constitution_state_to_graph("tenant-f")
        assert graph_e["total_rules"] == 1
        assert graph_f["total_rules"] == 0

    def test_memory_mesh_per_tenant(self):
        bridge, gov, es, mm = _make_integration()
        gov.register_rule(
            "iso-r3", "tenant-g", "rule-g",
            target_runtime="all", target_action="all",
        )
        mem_g = bridge.attach_constitution_state_to_memory_mesh("tenant-g")
        mem_h = bridge.attach_constitution_state_to_memory_mesh("tenant-h")
        assert mem_g.content["total_rules"] == 1
        assert mem_h.content["total_rules"] == 0
