"""Tests for mcoi_runtime.contracts.executive_control contracts.

Covers all 7 enums and 9 frozen dataclasses (+ ControlTowerSnapshot) with tests spanning:
  - Enum member existence and count
  - Valid construction with defaults and explicit values
  - Frozen immutability (FrozenInstanceError)
  - ContractRecord.to_dict() serialization
  - require_non_empty_text validation
  - require_unit_float validation
  - require_non_negative_int validation
  - require_non_negative_float validation
  - require_datetime_text validation
  - Enum-typed field rejection of wrong types
  - freeze_value checks (MappingProxyType, tuples)
  - Default values
  - Edge case boundary values
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.executive_control import (
    ControlTowerHealth,
    ControlTowerSnapshot,
    DirectiveStatus,
    DirectiveType,
    ExecutiveIntervention,
    InterventionSeverity,
    ObjectiveStatus,
    PortfolioDirectiveBinding,
    PriorityLevel,
    PriorityShift,
    ScenarioOutcome,
    ScenarioPlan,
    ScenarioStatus,
    StrategicDecision,
    StrategicDirective,
    StrategicObjective,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts() -> str:
    """Return a valid ISO-8601 datetime string."""
    return datetime.now(timezone.utc).isoformat()


def _make_strategic_objective(**overrides) -> StrategicObjective:
    defaults = dict(
        objective_id="obj-001",
        title="Increase Revenue",
        description="Grow quarterly revenue by 20%",
        priority=PriorityLevel.P1_HIGH,
        status=ObjectiveStatus.ACTIVE,
        target_kpi="revenue_growth",
        target_value=20.0,
        current_value=12.5,
        tolerance_pct=5.0,
        owner="exec-team",
        scope_ref_ids=("scope-1", "scope-2"),
        created_at=_ts(),
        updated_at=_ts(),
        metadata={"quarter": "Q1"},
    )
    defaults.update(overrides)
    return StrategicObjective(**defaults)


def _make_strategic_directive(**overrides) -> StrategicDirective:
    defaults = dict(
        directive_id="dir-001",
        objective_id="obj-001",
        directive_type=DirectiveType.PRIORITY_SHIFT,
        status=DirectiveStatus.PENDING,
        title="Shift priority to sales",
        reason="Sales pipeline needs focus",
        target_scope_ref_id="scope-1",
        parameters={"boost": 1.5},
        issued_by="ceo",
        issued_at=_ts(),
        expires_at="",
        metadata={"urgency": "high"},
    )
    defaults.update(overrides)
    return StrategicDirective(**defaults)


def _make_priority_shift(**overrides) -> PriorityShift:
    defaults = dict(
        shift_id="ps-001",
        directive_id="dir-001",
        from_priority=PriorityLevel.P2_MEDIUM,
        to_priority=PriorityLevel.P0_CRITICAL,
        target_scope_ref_id="scope-1",
        reason="Critical escalation",
        shifted_at=_ts(),
    )
    defaults.update(overrides)
    return PriorityShift(**defaults)


def _make_scenario_plan(**overrides) -> ScenarioPlan:
    defaults = dict(
        scenario_id="scn-001",
        objective_id="obj-001",
        title="Revenue acceleration plan",
        status=ScenarioStatus.DRAFT,
        baseline_snapshot={"revenue": 100},
        projected_snapshot={"revenue": 120},
        assumptions=("market stable", "no new competitors"),
        risk_score=0.3,
        confidence=0.75,
        created_at=_ts(),
        completed_at="",
        metadata={"version": "1"},
    )
    defaults.update(overrides)
    return ScenarioPlan(**defaults)


def _make_scenario_outcome(**overrides) -> ScenarioOutcome:
    defaults = dict(
        outcome_id="out-001",
        scenario_id="scn-001",
        verdict="favorable",
        projected_improvement_pct=15.0,
        projected_risk_delta=-0.1,
        projected_cost_delta=5000.0,
        recommendation="Proceed with plan",
        assessed_at=_ts(),
        metadata={"analyst": "ai"},
    )
    defaults.update(overrides)
    return ScenarioOutcome(**defaults)


def _make_executive_intervention(**overrides) -> ExecutiveIntervention:
    defaults = dict(
        intervention_id="int-001",
        directive_id="dir-001",
        severity=InterventionSeverity.HIGH,
        target_engine="optimizer",
        target_ref_id="ref-001",
        action="pause_optimization",
        reason="Budget exceeded",
        intervened_at=_ts(),
        resolved_at="",
        metadata={"triggered_by": "alert"},
    )
    defaults.update(overrides)
    return ExecutiveIntervention(**defaults)


def _make_strategic_decision(**overrides) -> StrategicDecision:
    defaults = dict(
        decision_id="dec-001",
        objective_id="obj-001",
        directive_ids=("dir-001", "dir-002"),
        title="Approve revenue plan",
        rationale="All scenarios show positive outcomes",
        confidence=0.85,
        risk_score=0.2,
        decided_at=_ts(),
        metadata={"board_approved": True},
    )
    defaults.update(overrides)
    return StrategicDecision(**defaults)


def _make_portfolio_directive_binding(**overrides) -> PortfolioDirectiveBinding:
    defaults = dict(
        binding_id="bind-001",
        directive_id="dir-001",
        portfolio_ref_id="pf-001",
        campaign_ref_id="camp-001",
        domain_ref_id="dom-001",
        effect="priority_boost",
        bound_at=_ts(),
    )
    defaults.update(overrides)
    return PortfolioDirectiveBinding(**defaults)


def _make_control_tower_snapshot(**overrides) -> ControlTowerSnapshot:
    defaults = dict(
        snapshot_id="snap-001",
        health=ControlTowerHealth.HEALTHY,
        active_objectives=5,
        active_directives=12,
        pending_scenarios=3,
        interventions_in_progress=1,
        total_priority_shifts=8,
        total_decisions=20,
        captured_at=_ts(),
        metadata={"region": "us-east"},
    )
    defaults.update(overrides)
    return ControlTowerSnapshot(**defaults)


# ---------------------------------------------------------------------------
# Enum membership tests
# ---------------------------------------------------------------------------

class TestEnumMembers:
    def test_objective_status_count(self):
        assert len(ObjectiveStatus) == 6

    def test_objective_status_values(self):
        expected = {"DRAFT", "ACTIVE", "PAUSED", "ACHIEVED", "ABANDONED", "SUPERSEDED"}
        assert {m.name for m in ObjectiveStatus} == expected

    def test_directive_type_count(self):
        assert len(DirectiveType) == 9

    def test_directive_type_values(self):
        expected = {
            "PRIORITY_SHIFT", "BUDGET_REALLOCATION", "CAPACITY_SHIFT",
            "PAUSE_OPERATIONS", "RESUME_OPERATIONS", "OVERRIDE_OPTIMIZER",
            "HALT_AUTONOMOUS", "LAUNCH_SCENARIO", "ESCALATE",
        }
        assert {m.name for m in DirectiveType} == expected

    def test_directive_status_count(self):
        assert len(DirectiveStatus) == 6

    def test_directive_status_values(self):
        expected = {"PENDING", "ISSUED", "ACKNOWLEDGED", "EXECUTED", "REJECTED", "EXPIRED"}
        assert {m.name for m in DirectiveStatus} == expected

    def test_intervention_severity_count(self):
        assert len(InterventionSeverity) == 4

    def test_intervention_severity_values(self):
        expected = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert {m.name for m in InterventionSeverity} == expected

    def test_scenario_status_count(self):
        assert len(ScenarioStatus) == 5

    def test_scenario_status_values(self):
        expected = {"DRAFT", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}
        assert {m.name for m in ScenarioStatus} == expected

    def test_priority_level_count(self):
        assert len(PriorityLevel) == 5

    def test_priority_level_values(self):
        expected = {"P0_CRITICAL", "P1_HIGH", "P2_MEDIUM", "P3_LOW", "P4_OPPORTUNISTIC"}
        assert {m.name for m in PriorityLevel} == expected

    def test_control_tower_health_count(self):
        assert len(ControlTowerHealth) == 4

    def test_control_tower_health_values(self):
        expected = {"HEALTHY", "DEGRADED", "CRITICAL", "OFFLINE"}
        assert {m.name for m in ControlTowerHealth} == expected


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------

class TestStrategicObjectiveConstruction:
    def test_valid_construction(self):
        obj = _make_strategic_objective()
        assert obj.objective_id == "obj-001"
        assert obj.title == "Increase Revenue"
        assert obj.priority is PriorityLevel.P1_HIGH
        assert obj.status is ObjectiveStatus.ACTIVE
        assert obj.target_value == 20.0
        assert obj.current_value == 12.5
        assert obj.tolerance_pct == 5.0

    def test_to_dict(self):
        obj = _make_strategic_objective()
        d = obj.to_dict()
        assert isinstance(d, dict)
        assert d["objective_id"] == "obj-001"


class TestStrategicDirectiveConstruction:
    def test_valid_construction(self):
        d = _make_strategic_directive()
        assert d.directive_id == "dir-001"
        assert d.directive_type is DirectiveType.PRIORITY_SHIFT
        assert d.status is DirectiveStatus.PENDING
        assert d.title == "Shift priority to sales"

    def test_to_dict(self):
        d = _make_strategic_directive()
        result = d.to_dict()
        assert isinstance(result, dict)
        assert result["directive_id"] == "dir-001"


class TestPriorityShiftConstruction:
    def test_valid_construction(self):
        ps = _make_priority_shift()
        assert ps.shift_id == "ps-001"
        assert ps.from_priority is PriorityLevel.P2_MEDIUM
        assert ps.to_priority is PriorityLevel.P0_CRITICAL

    def test_to_dict(self):
        ps = _make_priority_shift()
        d = ps.to_dict()
        assert isinstance(d, dict)
        assert d["shift_id"] == "ps-001"


class TestScenarioPlanConstruction:
    def test_valid_construction(self):
        sp = _make_scenario_plan()
        assert sp.scenario_id == "scn-001"
        assert sp.status is ScenarioStatus.DRAFT
        assert sp.risk_score == 0.3
        assert sp.confidence == 0.75

    def test_to_dict(self):
        sp = _make_scenario_plan()
        d = sp.to_dict()
        assert isinstance(d, dict)
        assert d["scenario_id"] == "scn-001"


class TestScenarioOutcomeConstruction:
    def test_valid_construction(self):
        so = _make_scenario_outcome()
        assert so.outcome_id == "out-001"
        assert so.verdict == "favorable"
        assert so.projected_improvement_pct == 15.0

    def test_to_dict(self):
        so = _make_scenario_outcome()
        d = so.to_dict()
        assert isinstance(d, dict)
        assert d["outcome_id"] == "out-001"


class TestExecutiveInterventionConstruction:
    def test_valid_construction(self):
        ei = _make_executive_intervention()
        assert ei.intervention_id == "int-001"
        assert ei.severity is InterventionSeverity.HIGH
        assert ei.action == "pause_optimization"

    def test_to_dict(self):
        ei = _make_executive_intervention()
        d = ei.to_dict()
        assert isinstance(d, dict)
        assert d["intervention_id"] == "int-001"


class TestStrategicDecisionConstruction:
    def test_valid_construction(self):
        sd = _make_strategic_decision()
        assert sd.decision_id == "dec-001"
        assert sd.confidence == 0.85
        assert sd.risk_score == 0.2

    def test_to_dict(self):
        sd = _make_strategic_decision()
        d = sd.to_dict()
        assert isinstance(d, dict)
        assert d["decision_id"] == "dec-001"


class TestPortfolioDirectiveBindingConstruction:
    def test_valid_construction(self):
        b = _make_portfolio_directive_binding()
        assert b.binding_id == "bind-001"
        assert b.directive_id == "dir-001"
        assert b.portfolio_ref_id == "pf-001"

    def test_to_dict(self):
        b = _make_portfolio_directive_binding()
        d = b.to_dict()
        assert isinstance(d, dict)
        assert d["binding_id"] == "bind-001"


class TestControlTowerSnapshotConstruction:
    def test_valid_construction(self):
        s = _make_control_tower_snapshot()
        assert s.snapshot_id == "snap-001"
        assert s.health is ControlTowerHealth.HEALTHY
        assert s.active_objectives == 5
        assert s.active_directives == 12

    def test_to_dict(self):
        s = _make_control_tower_snapshot()
        d = s.to_dict()
        assert isinstance(d, dict)
        assert d["snapshot_id"] == "snap-001"


# ---------------------------------------------------------------------------
# Frozen immutability
# ---------------------------------------------------------------------------

class TestFrozenImmutability:
    def test_strategic_objective_frozen(self):
        obj = _make_strategic_objective()
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.objective_id = "other"

    def test_strategic_directive_frozen(self):
        d = _make_strategic_directive()
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.directive_id = "other"

    def test_priority_shift_frozen(self):
        ps = _make_priority_shift()
        with pytest.raises(dataclasses.FrozenInstanceError):
            ps.shift_id = "other"

    def test_scenario_plan_frozen(self):
        sp = _make_scenario_plan()
        with pytest.raises(dataclasses.FrozenInstanceError):
            sp.scenario_id = "other"

    def test_scenario_outcome_frozen(self):
        so = _make_scenario_outcome()
        with pytest.raises(dataclasses.FrozenInstanceError):
            so.outcome_id = "other"

    def test_executive_intervention_frozen(self):
        ei = _make_executive_intervention()
        with pytest.raises(dataclasses.FrozenInstanceError):
            ei.intervention_id = "other"

    def test_strategic_decision_frozen(self):
        sd = _make_strategic_decision()
        with pytest.raises(dataclasses.FrozenInstanceError):
            sd.decision_id = "other"

    def test_portfolio_directive_binding_frozen(self):
        b = _make_portfolio_directive_binding()
        with pytest.raises(dataclasses.FrozenInstanceError):
            b.binding_id = "other"

    def test_control_tower_snapshot_frozen(self):
        s = _make_control_tower_snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.snapshot_id = "other"


# ---------------------------------------------------------------------------
# require_non_empty_text validation
# ---------------------------------------------------------------------------

class TestRequireNonEmptyText:
    # StrategicObjective: objective_id, title
    def test_objective_empty_objective_id(self):
        with pytest.raises(ValueError):
            _make_strategic_objective(objective_id="")

    def test_objective_whitespace_objective_id(self):
        with pytest.raises(ValueError):
            _make_strategic_objective(objective_id="   ")

    def test_objective_empty_title(self):
        with pytest.raises(ValueError):
            _make_strategic_objective(title="")

    def test_objective_whitespace_title(self):
        with pytest.raises(ValueError):
            _make_strategic_objective(title="   ")

    # StrategicDirective: directive_id, title
    def test_directive_empty_directive_id(self):
        with pytest.raises(ValueError):
            _make_strategic_directive(directive_id="")

    def test_directive_whitespace_directive_id(self):
        with pytest.raises(ValueError):
            _make_strategic_directive(directive_id="   ")

    def test_directive_empty_title(self):
        with pytest.raises(ValueError):
            _make_strategic_directive(title="")

    # PriorityShift: shift_id, directive_id
    def test_priority_shift_empty_shift_id(self):
        with pytest.raises(ValueError):
            _make_priority_shift(shift_id="")

    def test_priority_shift_empty_directive_id(self):
        with pytest.raises(ValueError):
            _make_priority_shift(directive_id="")

    # ScenarioPlan: scenario_id, title
    def test_scenario_plan_empty_scenario_id(self):
        with pytest.raises(ValueError):
            _make_scenario_plan(scenario_id="")

    def test_scenario_plan_empty_title(self):
        with pytest.raises(ValueError):
            _make_scenario_plan(title="")

    # ScenarioOutcome: outcome_id, scenario_id, verdict
    def test_scenario_outcome_empty_outcome_id(self):
        with pytest.raises(ValueError):
            _make_scenario_outcome(outcome_id="")

    def test_scenario_outcome_empty_scenario_id(self):
        with pytest.raises(ValueError):
            _make_scenario_outcome(scenario_id="")

    def test_scenario_outcome_empty_verdict(self):
        with pytest.raises(ValueError):
            _make_scenario_outcome(verdict="")

    # ExecutiveIntervention: intervention_id, directive_id, action
    def test_intervention_empty_intervention_id(self):
        with pytest.raises(ValueError):
            _make_executive_intervention(intervention_id="")

    def test_intervention_empty_directive_id(self):
        with pytest.raises(ValueError):
            _make_executive_intervention(directive_id="")

    def test_intervention_empty_action(self):
        with pytest.raises(ValueError):
            _make_executive_intervention(action="")

    # StrategicDecision: decision_id, title
    def test_decision_empty_decision_id(self):
        with pytest.raises(ValueError):
            _make_strategic_decision(decision_id="")

    def test_decision_empty_title(self):
        with pytest.raises(ValueError):
            _make_strategic_decision(title="")

    # PortfolioDirectiveBinding: binding_id, directive_id
    def test_binding_empty_binding_id(self):
        with pytest.raises(ValueError):
            _make_portfolio_directive_binding(binding_id="")

    def test_binding_empty_directive_id(self):
        with pytest.raises(ValueError):
            _make_portfolio_directive_binding(directive_id="")

    # ControlTowerSnapshot: snapshot_id
    def test_snapshot_empty_snapshot_id(self):
        with pytest.raises(ValueError):
            _make_control_tower_snapshot(snapshot_id="")

    def test_snapshot_whitespace_snapshot_id(self):
        with pytest.raises(ValueError):
            _make_control_tower_snapshot(snapshot_id="   ")


# ---------------------------------------------------------------------------
# require_unit_float validation
# ---------------------------------------------------------------------------

class TestRequireUnitFloat:
    # ScenarioPlan: risk_score, confidence
    def test_scenario_plan_risk_score_below_zero(self):
        with pytest.raises(ValueError):
            _make_scenario_plan(risk_score=-0.1)

    def test_scenario_plan_risk_score_above_one(self):
        with pytest.raises(ValueError):
            _make_scenario_plan(risk_score=1.1)

    def test_scenario_plan_confidence_below_zero(self):
        with pytest.raises(ValueError):
            _make_scenario_plan(confidence=-0.01)

    def test_scenario_plan_confidence_above_one(self):
        with pytest.raises(ValueError):
            _make_scenario_plan(confidence=1.001)

    # StrategicDecision: confidence, risk_score
    def test_decision_confidence_below_zero(self):
        with pytest.raises(ValueError):
            _make_strategic_decision(confidence=-0.5)

    def test_decision_confidence_above_one(self):
        with pytest.raises(ValueError):
            _make_strategic_decision(confidence=1.5)

    def test_decision_risk_score_below_zero(self):
        with pytest.raises(ValueError):
            _make_strategic_decision(risk_score=-0.01)

    def test_decision_risk_score_above_one(self):
        with pytest.raises(ValueError):
            _make_strategic_decision(risk_score=2.0)


# ---------------------------------------------------------------------------
# require_non_negative_int validation
# ---------------------------------------------------------------------------

class TestRequireNonNegativeInt:
    def test_snapshot_active_objectives_negative(self):
        with pytest.raises(ValueError):
            _make_control_tower_snapshot(active_objectives=-1)

    def test_snapshot_active_directives_negative(self):
        with pytest.raises(ValueError):
            _make_control_tower_snapshot(active_directives=-1)

    def test_snapshot_pending_scenarios_negative(self):
        with pytest.raises(ValueError):
            _make_control_tower_snapshot(pending_scenarios=-1)

    def test_snapshot_interventions_in_progress_negative(self):
        with pytest.raises(ValueError):
            _make_control_tower_snapshot(interventions_in_progress=-1)

    def test_snapshot_total_priority_shifts_negative(self):
        with pytest.raises(ValueError):
            _make_control_tower_snapshot(total_priority_shifts=-1)

    def test_snapshot_total_decisions_negative(self):
        with pytest.raises(ValueError):
            _make_control_tower_snapshot(total_decisions=-1)


# ---------------------------------------------------------------------------
# require_non_negative_float validation
# ---------------------------------------------------------------------------

class TestRequireNonNegativeFloat:
    def test_objective_tolerance_pct_negative(self):
        with pytest.raises(ValueError):
            _make_strategic_objective(tolerance_pct=-0.1)

    def test_objective_tolerance_pct_negative_large(self):
        with pytest.raises(ValueError):
            _make_strategic_objective(tolerance_pct=-100.0)


# ---------------------------------------------------------------------------
# require_datetime_text validation
# ---------------------------------------------------------------------------

class TestRequireDatetimeText:
    def test_objective_invalid_created_at(self):
        with pytest.raises(ValueError):
            _make_strategic_objective(created_at="not-a-date")

    def test_directive_invalid_issued_at(self):
        with pytest.raises(ValueError):
            _make_strategic_directive(issued_at="nope")

    def test_priority_shift_invalid_shifted_at(self):
        with pytest.raises(ValueError):
            _make_priority_shift(shifted_at="invalid")

    def test_scenario_plan_invalid_created_at(self):
        with pytest.raises(ValueError):
            _make_scenario_plan(created_at="wrong")

    def test_scenario_outcome_invalid_assessed_at(self):
        with pytest.raises(ValueError):
            _make_scenario_outcome(assessed_at="nah")

    def test_intervention_invalid_intervened_at(self):
        with pytest.raises(ValueError):
            _make_executive_intervention(intervened_at="xxx")

    def test_decision_invalid_decided_at(self):
        with pytest.raises(ValueError):
            _make_strategic_decision(decided_at="bad-time")

    def test_binding_invalid_bound_at(self):
        with pytest.raises(ValueError):
            _make_portfolio_directive_binding(bound_at="not-valid")

    def test_snapshot_invalid_captured_at(self):
        with pytest.raises(ValueError):
            _make_control_tower_snapshot(captured_at="garbage")


# ---------------------------------------------------------------------------
# Enum type validation
# ---------------------------------------------------------------------------

class TestEnumTypeValidation:
    def test_objective_bad_priority(self):
        with pytest.raises(ValueError):
            _make_strategic_objective(priority="P1_HIGH")

    def test_objective_bad_status(self):
        with pytest.raises(ValueError):
            _make_strategic_objective(status="ACTIVE")

    def test_directive_bad_directive_type(self):
        with pytest.raises(ValueError):
            _make_strategic_directive(directive_type="PRIORITY_SHIFT")

    def test_directive_bad_status(self):
        with pytest.raises(ValueError):
            _make_strategic_directive(status="PENDING")

    def test_priority_shift_bad_from_priority(self):
        with pytest.raises(ValueError):
            _make_priority_shift(from_priority="P2_MEDIUM")

    def test_priority_shift_bad_to_priority(self):
        with pytest.raises(ValueError):
            _make_priority_shift(to_priority="P0_CRITICAL")

    def test_scenario_plan_bad_status(self):
        with pytest.raises(ValueError):
            _make_scenario_plan(status="DRAFT")

    def test_intervention_bad_severity(self):
        with pytest.raises(ValueError):
            _make_executive_intervention(severity="HIGH")

    def test_snapshot_bad_health(self):
        with pytest.raises(ValueError):
            _make_control_tower_snapshot(health="HEALTHY")


# ---------------------------------------------------------------------------
# freeze_value checks
# ---------------------------------------------------------------------------

class TestFreezeValue:
    # metadata -> MappingProxyType
    def test_objective_metadata_is_mapping_proxy(self):
        obj = _make_strategic_objective(metadata={"k": "v"})
        assert isinstance(obj.metadata, MappingProxyType)

    def test_directive_metadata_is_mapping_proxy(self):
        d = _make_strategic_directive(metadata={"k": "v"})
        assert isinstance(d.metadata, MappingProxyType)

    def test_scenario_plan_metadata_is_mapping_proxy(self):
        sp = _make_scenario_plan(metadata={"k": "v"})
        assert isinstance(sp.metadata, MappingProxyType)

    def test_scenario_outcome_metadata_is_mapping_proxy(self):
        so = _make_scenario_outcome(metadata={"k": "v"})
        assert isinstance(so.metadata, MappingProxyType)

    def test_intervention_metadata_is_mapping_proxy(self):
        ei = _make_executive_intervention(metadata={"k": "v"})
        assert isinstance(ei.metadata, MappingProxyType)

    def test_decision_metadata_is_mapping_proxy(self):
        sd = _make_strategic_decision(metadata={"k": "v"})
        assert isinstance(sd.metadata, MappingProxyType)

    def test_snapshot_metadata_is_mapping_proxy(self):
        s = _make_control_tower_snapshot(metadata={"k": "v"})
        assert isinstance(s.metadata, MappingProxyType)

    # metadata dict is not mutable
    def test_objective_metadata_immutable(self):
        obj = _make_strategic_objective(metadata={"a": 1})
        with pytest.raises(TypeError):
            obj.metadata["a"] = 2  # type: ignore[index]

    def test_directive_metadata_immutable(self):
        d = _make_strategic_directive(metadata={"a": 1})
        with pytest.raises(TypeError):
            d.metadata["a"] = 2  # type: ignore[index]

    # scope_ref_ids -> tuple
    def test_objective_scope_ref_ids_is_tuple(self):
        obj = _make_strategic_objective(scope_ref_ids=["s1", "s2"])
        assert isinstance(obj.scope_ref_ids, tuple)
        assert obj.scope_ref_ids == ("s1", "s2")

    # assumptions -> tuple
    def test_scenario_plan_assumptions_is_tuple(self):
        sp = _make_scenario_plan(assumptions=["a1", "a2", "a3"])
        assert isinstance(sp.assumptions, tuple)
        assert sp.assumptions == ("a1", "a2", "a3")

    # directive_ids -> tuple
    def test_decision_directive_ids_is_tuple(self):
        sd = _make_strategic_decision(directive_ids=["d1", "d2"])
        assert isinstance(sd.directive_ids, tuple)
        assert sd.directive_ids == ("d1", "d2")

    # parameters -> MappingProxyType
    def test_directive_parameters_is_mapping_proxy(self):
        d = _make_strategic_directive(parameters={"x": 10})
        assert isinstance(d.parameters, MappingProxyType)

    # baseline_snapshot, projected_snapshot -> MappingProxyType
    def test_scenario_plan_baseline_snapshot_is_mapping_proxy(self):
        sp = _make_scenario_plan(baseline_snapshot={"rev": 100})
        assert isinstance(sp.baseline_snapshot, MappingProxyType)

    def test_scenario_plan_projected_snapshot_is_mapping_proxy(self):
        sp = _make_scenario_plan(projected_snapshot={"rev": 120})
        assert isinstance(sp.projected_snapshot, MappingProxyType)


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_objective_description_default(self):
        obj = _make_strategic_objective(description="")
        assert obj.description == ""

    def test_objective_target_kpi_default(self):
        obj = _make_strategic_objective(target_kpi="")
        assert obj.target_kpi == ""

    def test_objective_owner_default(self):
        obj = _make_strategic_objective(owner="")
        assert obj.owner == ""

    def test_directive_objective_id_accepts_empty(self):
        d = _make_strategic_directive(objective_id="")
        assert d.objective_id == ""

    def test_directive_reason_accepts_empty(self):
        d = _make_strategic_directive(reason="")
        assert d.reason == ""

    def test_directive_target_scope_ref_id_accepts_empty(self):
        d = _make_strategic_directive(target_scope_ref_id="")
        assert d.target_scope_ref_id == ""

    def test_directive_issued_by_accepts_empty(self):
        d = _make_strategic_directive(issued_by="")
        assert d.issued_by == ""

    def test_directive_expires_at_accepts_empty(self):
        d = _make_strategic_directive(expires_at="")
        assert d.expires_at == ""

    def test_priority_shift_target_scope_ref_id_accepts_empty(self):
        ps = _make_priority_shift(target_scope_ref_id="")
        assert ps.target_scope_ref_id == ""

    def test_priority_shift_reason_accepts_empty(self):
        ps = _make_priority_shift(reason="")
        assert ps.reason == ""

    def test_scenario_plan_objective_id_accepts_empty(self):
        sp = _make_scenario_plan(objective_id="")
        assert sp.objective_id == ""

    def test_scenario_plan_completed_at_accepts_empty(self):
        sp = _make_scenario_plan(completed_at="")
        assert sp.completed_at == ""

    def test_scenario_outcome_recommendation_accepts_empty(self):
        so = _make_scenario_outcome(recommendation="")
        assert so.recommendation == ""

    def test_intervention_target_engine_accepts_empty(self):
        ei = _make_executive_intervention(target_engine="")
        assert ei.target_engine == ""

    def test_intervention_target_ref_id_accepts_empty(self):
        ei = _make_executive_intervention(target_ref_id="")
        assert ei.target_ref_id == ""

    def test_intervention_reason_accepts_empty(self):
        ei = _make_executive_intervention(reason="")
        assert ei.reason == ""

    def test_intervention_resolved_at_accepts_empty(self):
        ei = _make_executive_intervention(resolved_at="")
        assert ei.resolved_at == ""

    def test_decision_objective_id_accepts_empty(self):
        sd = _make_strategic_decision(objective_id="")
        assert sd.objective_id == ""

    def test_decision_rationale_accepts_empty(self):
        sd = _make_strategic_decision(rationale="")
        assert sd.rationale == ""

    def test_binding_portfolio_ref_id_accepts_empty(self):
        b = _make_portfolio_directive_binding(portfolio_ref_id="")
        assert b.portfolio_ref_id == ""

    def test_binding_campaign_ref_id_accepts_empty(self):
        b = _make_portfolio_directive_binding(campaign_ref_id="")
        assert b.campaign_ref_id == ""

    def test_binding_domain_ref_id_accepts_empty(self):
        b = _make_portfolio_directive_binding(domain_ref_id="")
        assert b.domain_ref_id == ""

    def test_binding_effect_accepts_empty(self):
        b = _make_portfolio_directive_binding(effect="")
        assert b.effect == ""


# ---------------------------------------------------------------------------
# Edge case boundary values
# ---------------------------------------------------------------------------

class TestEdgeCaseBoundaries:
    # unit float boundaries
    def test_scenario_plan_risk_score_zero(self):
        sp = _make_scenario_plan(risk_score=0.0)
        assert sp.risk_score == 0.0

    def test_scenario_plan_risk_score_one(self):
        sp = _make_scenario_plan(risk_score=1.0)
        assert sp.risk_score == 1.0

    def test_scenario_plan_confidence_zero(self):
        sp = _make_scenario_plan(confidence=0.0)
        assert sp.confidence == 0.0

    def test_scenario_plan_confidence_one(self):
        sp = _make_scenario_plan(confidence=1.0)
        assert sp.confidence == 1.0

    def test_decision_confidence_zero(self):
        sd = _make_strategic_decision(confidence=0.0)
        assert sd.confidence == 0.0

    def test_decision_confidence_one(self):
        sd = _make_strategic_decision(confidence=1.0)
        assert sd.confidence == 1.0

    def test_decision_risk_score_zero(self):
        sd = _make_strategic_decision(risk_score=0.0)
        assert sd.risk_score == 0.0

    def test_decision_risk_score_one(self):
        sd = _make_strategic_decision(risk_score=1.0)
        assert sd.risk_score == 1.0

    # non-negative int boundaries
    def test_snapshot_active_objectives_zero(self):
        s = _make_control_tower_snapshot(active_objectives=0)
        assert s.active_objectives == 0

    def test_snapshot_active_directives_zero(self):
        s = _make_control_tower_snapshot(active_directives=0)
        assert s.active_directives == 0

    def test_snapshot_pending_scenarios_zero(self):
        s = _make_control_tower_snapshot(pending_scenarios=0)
        assert s.pending_scenarios == 0

    def test_snapshot_interventions_in_progress_zero(self):
        s = _make_control_tower_snapshot(interventions_in_progress=0)
        assert s.interventions_in_progress == 0

    def test_snapshot_total_priority_shifts_zero(self):
        s = _make_control_tower_snapshot(total_priority_shifts=0)
        assert s.total_priority_shifts == 0

    def test_snapshot_total_decisions_zero(self):
        s = _make_control_tower_snapshot(total_decisions=0)
        assert s.total_decisions == 0

    # non-negative float boundary
    def test_objective_tolerance_pct_zero(self):
        obj = _make_strategic_objective(tolerance_pct=0.0)
        assert obj.tolerance_pct == 0.0

    # empty metadata
    def test_objective_empty_metadata(self):
        obj = _make_strategic_objective(metadata={})
        assert isinstance(obj.metadata, MappingProxyType)
        assert len(obj.metadata) == 0

    # empty tuple fields
    def test_objective_empty_scope_ref_ids(self):
        obj = _make_strategic_objective(scope_ref_ids=())
        assert obj.scope_ref_ids == ()

    def test_scenario_plan_empty_assumptions(self):
        sp = _make_scenario_plan(assumptions=())
        assert sp.assumptions == ()

    def test_decision_empty_directive_ids(self):
        sd = _make_strategic_decision(directive_ids=())
        assert sd.directive_ids == ()


# ---------------------------------------------------------------------------
# to_dict serialization
# ---------------------------------------------------------------------------

class TestToDictSerialization:
    """to_dict() returns a plain dict and preserves enum objects (not .value)."""

    def test_objective_to_dict_returns_dict(self):
        d = _make_strategic_objective().to_dict()
        assert isinstance(d, dict)

    def test_objective_to_dict_preserves_enum(self):
        d = _make_strategic_objective().to_dict()
        assert d["priority"] is PriorityLevel.P1_HIGH
        assert d["status"] is ObjectiveStatus.ACTIVE

    def test_directive_to_dict_returns_dict(self):
        d = _make_strategic_directive().to_dict()
        assert isinstance(d, dict)

    def test_directive_to_dict_preserves_enum(self):
        d = _make_strategic_directive().to_dict()
        assert d["directive_type"] is DirectiveType.PRIORITY_SHIFT
        assert d["status"] is DirectiveStatus.PENDING

    def test_priority_shift_to_dict_preserves_enum(self):
        d = _make_priority_shift().to_dict()
        assert d["from_priority"] is PriorityLevel.P2_MEDIUM
        assert d["to_priority"] is PriorityLevel.P0_CRITICAL

    def test_scenario_plan_to_dict_preserves_enum(self):
        d = _make_scenario_plan().to_dict()
        assert d["status"] is ScenarioStatus.DRAFT

    def test_intervention_to_dict_preserves_enum(self):
        d = _make_executive_intervention().to_dict()
        assert d["severity"] is InterventionSeverity.HIGH

    def test_snapshot_to_dict_preserves_enum(self):
        d = _make_control_tower_snapshot().to_dict()
        assert d["health"] is ControlTowerHealth.HEALTHY

    def test_objective_to_dict_all_keys(self):
        d = _make_strategic_objective().to_dict()
        expected_keys = {
            "objective_id", "title", "description", "priority", "status",
            "target_kpi", "target_value", "current_value", "tolerance_pct",
            "owner", "scope_ref_ids", "created_at", "updated_at", "metadata",
        }
        assert expected_keys.issubset(d.keys())

    def test_directive_to_dict_all_keys(self):
        d = _make_strategic_directive().to_dict()
        expected_keys = {
            "directive_id", "objective_id", "directive_type", "status",
            "title", "reason", "target_scope_ref_id", "parameters",
            "issued_by", "issued_at", "expires_at", "metadata",
        }
        assert expected_keys.issubset(d.keys())

    def test_scenario_plan_to_dict_all_keys(self):
        d = _make_scenario_plan().to_dict()
        expected_keys = {
            "scenario_id", "objective_id", "title", "status",
            "baseline_snapshot", "projected_snapshot", "assumptions",
            "risk_score", "confidence", "created_at", "completed_at", "metadata",
        }
        assert expected_keys.issubset(d.keys())

    def test_decision_to_dict_all_keys(self):
        d = _make_strategic_decision().to_dict()
        expected_keys = {
            "decision_id", "objective_id", "directive_ids", "title",
            "rationale", "confidence", "risk_score", "decided_at", "metadata",
        }
        assert expected_keys.issubset(d.keys())

    def test_snapshot_to_dict_all_keys(self):
        d = _make_control_tower_snapshot().to_dict()
        expected_keys = {
            "snapshot_id", "health", "active_objectives", "active_directives",
            "pending_scenarios", "interventions_in_progress",
            "total_priority_shifts", "total_decisions", "captured_at", "metadata",
        }
        assert expected_keys.issubset(d.keys())
