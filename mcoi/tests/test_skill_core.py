"""Tests for skill system core: registry, selector, executor."""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from mcoi_runtime.contracts.skill import (
    DeterminismClass,
    EffectClass,
    PreconditionType,
    PostconditionType,
    SkillClass,
    SkillDescriptor,
    SkillLifecycle,
    SkillOutcomeStatus,
    SkillPostcondition,
    SkillPrecondition,
    SkillStep,
    SkillStepOutcome,
    TrustClass,
    VerificationStrength,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.skills import (
    PostconditionChecker,
    PreconditionChecker,
    SkillExecutor,
    SkillRegistry,
    SkillSelector,
    StepExecutor,
)


# --- Test helpers ---


FIXED_CLOCK = "2025-01-15T10:00:00+00:00"


def _clock():
    return FIXED_CLOCK


def _make_skill(skill_id="sk-1", lifecycle=SkillLifecycle.CANDIDATE, confidence=0.5, **kw):
    defaults = dict(
        skill_id=skill_id,
        name=f"skill-{skill_id}",
        skill_class=SkillClass.PRIMITIVE,
        effect_class=EffectClass.INTERNAL_PURE,
        determinism_class=DeterminismClass.DETERMINISTIC,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.STRONG,
        lifecycle=lifecycle,
        confidence=confidence,
    )
    defaults.update(kw)
    return SkillDescriptor(**defaults)


class SuccessStepExecutor:
    """Always returns success with optional outputs."""

    def __init__(self, outputs: dict[str, Any] | None = None):
        self._outputs = outputs or {}

    def execute_step(self, step_id: str, action_type: str, input_bindings: Mapping[str, Any]) -> SkillStepOutcome:
        return SkillStepOutcome(
            step_id=step_id,
            status=SkillOutcomeStatus.SUCCEEDED,
            outputs=self._outputs,
        )


class FailStepExecutor:
    """Always returns failure."""

    def execute_step(self, step_id: str, action_type: str, input_bindings: Mapping[str, Any]) -> SkillStepOutcome:
        return SkillStepOutcome(
            step_id=step_id,
            status=SkillOutcomeStatus.FAILED,
            error_message="simulated failure",
        )


class SelectiveStepExecutor:
    """Succeeds on some steps, fails on others."""

    def __init__(self, fail_step_ids: set[str]):
        self._fail = fail_step_ids

    def execute_step(self, step_id: str, action_type: str, input_bindings: Mapping[str, Any]) -> SkillStepOutcome:
        if step_id in self._fail:
            return SkillStepOutcome(step_id=step_id, status=SkillOutcomeStatus.FAILED, error_message="fail")
        return SkillStepOutcome(step_id=step_id, status=SkillOutcomeStatus.SUCCEEDED, outputs={"done": True})


class AlwaysTrueChecker:
    def check(self, condition_id: str, condition_type: str, parameters: Mapping[str, Any]) -> bool:
        return True


class AlwaysFalseChecker:
    def check(self, condition_id: str, condition_type: str, parameters: Mapping[str, Any]) -> bool:
        return False


# --- SkillRegistry ---


class TestSkillRegistry:
    def test_register_and_get(self):
        reg = SkillRegistry()
        skill = _make_skill()
        reg.register(skill)
        assert reg.get("sk-1") is skill
        assert reg.size == 1

    def test_duplicate_registration_rejected(self):
        reg = SkillRegistry()
        reg.register(_make_skill())
        with pytest.raises(RuntimeCoreInvariantError, match="already registered") as excinfo:
            reg.register(_make_skill())
        assert str(excinfo.value) == "skill already registered"
        assert "sk-1" not in str(excinfo.value)

    def test_get_nonexistent_returns_none(self):
        reg = SkillRegistry()
        assert reg.get("missing") is None

    def test_list_all(self):
        reg = SkillRegistry()
        reg.register(_make_skill("a"))
        reg.register(_make_skill("b"))
        reg.register(_make_skill("c", lifecycle=SkillLifecycle.BLOCKED))
        # Blocked excluded by default
        listed = reg.list_skills()
        assert len(listed) == 2
        assert listed[0].skill_id == "a"

    def test_list_include_blocked(self):
        reg = SkillRegistry()
        reg.register(_make_skill("a", lifecycle=SkillLifecycle.BLOCKED))
        listed = reg.list_skills(exclude_blocked=False)
        assert len(listed) == 1

    def test_list_by_class(self):
        reg = SkillRegistry()
        reg.register(_make_skill("a"))
        reg.register(_make_skill("b", skill_class=SkillClass.COMPOSITE, steps=(
            SkillStep(step_id="s1", name="s", action_type="x"),
        )))
        listed = reg.list_skills(skill_class=SkillClass.PRIMITIVE)
        assert len(listed) == 1
        assert listed[0].skill_id == "a"

    def test_list_by_lifecycle(self):
        reg = SkillRegistry()
        reg.register(_make_skill("a", lifecycle=SkillLifecycle.VERIFIED))
        reg.register(_make_skill("b", lifecycle=SkillLifecycle.CANDIDATE))
        listed = reg.list_skills(lifecycle=SkillLifecycle.VERIFIED)
        assert len(listed) == 1

    def test_transition_valid(self):
        reg = SkillRegistry()
        reg.register(_make_skill("a"))
        updated = reg.transition("a", SkillLifecycle.PROVISIONAL)
        assert updated.lifecycle is SkillLifecycle.PROVISIONAL
        assert reg.get("a").lifecycle is SkillLifecycle.PROVISIONAL

    def test_transition_invalid(self):
        reg = SkillRegistry()
        reg.register(_make_skill("a"))
        with pytest.raises(RuntimeCoreInvariantError, match="invalid lifecycle transition") as excinfo:
            reg.transition("a", SkillLifecycle.TRUSTED)  # candidate -> trusted not allowed
        assert str(excinfo.value) == "invalid lifecycle transition"
        assert "candidate" not in str(excinfo.value).lower()
        assert "trusted" not in str(excinfo.value).lower()

    def test_transition_not_found(self):
        reg = SkillRegistry()
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as excinfo:
            reg.transition("missing", SkillLifecycle.PROVISIONAL)
        assert str(excinfo.value) == "skill not found"
        assert "missing" not in str(excinfo.value)

    def test_transition_blocked_is_terminal(self):
        reg = SkillRegistry()
        reg.register(_make_skill("a", lifecycle=SkillLifecycle.BLOCKED))
        with pytest.raises(RuntimeCoreInvariantError, match="invalid lifecycle"):
            reg.transition("a", SkillLifecycle.CANDIDATE)

    def test_update_confidence(self):
        reg = SkillRegistry()
        reg.register(_make_skill("a", confidence=0.3))
        updated = reg.update_confidence("a", 0.9)
        assert updated.confidence == 0.9
        assert reg.get("a").confidence == 0.9

    def test_update_confidence_out_of_range(self):
        reg = SkillRegistry()
        reg.register(_make_skill("a"))
        with pytest.raises(RuntimeCoreInvariantError, match="confidence"):
            reg.update_confidence("a", 2.0)

    def test_update_confidence_not_found(self):
        reg = SkillRegistry()
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as excinfo:
            reg.update_confidence("missing", 0.5)
        assert str(excinfo.value) == "skill not found"
        assert "missing" not in str(excinfo.value)


# --- SkillSelector ---


class TestSkillSelector:
    def test_select_single_candidate(self):
        sel = SkillSelector()
        decision = sel.select((_make_skill("a"),))
        assert decision is not None
        assert decision.selected_skill_id == "a"

    def test_select_empty(self):
        sel = SkillSelector()
        assert sel.select(()) is None

    def test_blocked_skills_never_selected(self):
        sel = SkillSelector()
        decision = sel.select((_make_skill("a", lifecycle=SkillLifecycle.BLOCKED),))
        assert decision is None

    def test_prefers_higher_lifecycle(self):
        sel = SkillSelector()
        candidates = (
            _make_skill("a", lifecycle=SkillLifecycle.CANDIDATE, confidence=0.9),
            _make_skill("b", lifecycle=SkillLifecycle.VERIFIED, confidence=0.5),
        )
        decision = sel.select(candidates)
        assert decision.selected_skill_id == "b"

    def test_same_lifecycle_prefers_higher_confidence(self):
        sel = SkillSelector()
        candidates = (
            _make_skill("a", confidence=0.3),
            _make_skill("b", confidence=0.8),
        )
        decision = sel.select(candidates)
        assert decision.selected_skill_id == "b"

    def test_same_lifecycle_and_confidence_prefers_least_privileged(self):
        sel = SkillSelector()
        candidates = (
            _make_skill("a", effect_class=EffectClass.EXTERNAL_WRITE),
            _make_skill("b", effect_class=EffectClass.INTERNAL_PURE),
        )
        decision = sel.select(candidates)
        assert decision.selected_skill_id == "b"

    def test_tie_broken_by_skill_id(self):
        sel = SkillSelector()
        candidates = (
            _make_skill("b"),
            _make_skill("a"),
        )
        decision = sel.select(candidates)
        assert decision.selected_skill_id == "a"

    def test_precondition_filter(self):
        sel = SkillSelector()
        pc = SkillPrecondition(
            condition_id="pc-1", condition_type=PreconditionType.STATE_CHECK, description="x",
        )
        candidates = (
            _make_skill("a", preconditions=(pc,)),
            _make_skill("b"),
        )
        decision = sel.select(candidates, precondition_checker=AlwaysFalseChecker())
        assert decision.selected_skill_id == "b"
        assert decision.rejected_reasons["a"] == "precondition_not_met"

    def test_policy_filter(self):
        sel = SkillSelector()
        candidates = (_make_skill("a"), _make_skill("b"))
        decision = sel.select(candidates, policy_checker=lambda sid: sid == "b")
        assert decision.selected_skill_id == "b"
        assert decision.rejected_reasons["a"] == "policy_denied"

    def test_provider_filter(self):
        sel = SkillSelector()
        candidates = (
            _make_skill("a", provider_requirements=("model",)),
            _make_skill("b"),
        )
        decision = sel.select(candidates, provider_checker=lambda reqs: False)
        assert decision.selected_skill_id == "b"
        assert decision.rejected_reasons["a"] == "provider_unavailable"

    def test_all_filtered_returns_none(self):
        sel = SkillSelector()
        candidates = (_make_skill("a", lifecycle=SkillLifecycle.BLOCKED),)
        assert sel.select(candidates) is None


# --- SkillExecutor ---


class TestSkillExecutor:
    def test_primitive_success(self):
        executor = SkillExecutor(clock=_clock)
        skill = _make_skill("a")
        record = executor.execute(skill, step_executor=SuccessStepExecutor())
        assert record.outcome.status is SkillOutcomeStatus.SUCCEEDED
        assert len(record.outcome.step_outcomes) == 1
        assert record.started_at == FIXED_CLOCK

    def test_primitive_failure(self):
        executor = SkillExecutor(clock=_clock)
        skill = _make_skill("a")
        record = executor.execute(skill, step_executor=FailStepExecutor())
        assert record.outcome.status is SkillOutcomeStatus.STEP_FAILED

    def test_precondition_failure_prevents_execution(self):
        executor = SkillExecutor(clock=_clock)
        pc = SkillPrecondition(
            condition_id="pc-1", condition_type=PreconditionType.STATE_CHECK, description="x",
        )
        skill = _make_skill("a", preconditions=(pc,))
        record = executor.execute(
            skill,
            step_executor=SuccessStepExecutor(),
            precondition_checker=AlwaysFalseChecker(),
        )
        assert record.outcome.status is SkillOutcomeStatus.PRECONDITION_NOT_MET
        assert record.outcome.preconditions_met is False
        # No steps should have been executed
        assert len(record.outcome.step_outcomes) == 0

    def test_postcondition_failure(self):
        executor = SkillExecutor(clock=_clock)
        postc = SkillPostcondition(
            condition_id="post-1", condition_type=PostconditionType.FILE_EXISTS, description="x",
        )
        skill = _make_skill("a", postconditions=(postc,))
        record = executor.execute(
            skill,
            step_executor=SuccessStepExecutor(),
            postcondition_checker=AlwaysFalseChecker(),
        )
        assert record.outcome.status is SkillOutcomeStatus.POSTCONDITION_NOT_SATISFIED
        assert record.outcome.postconditions_met is False

    def test_composite_success(self):
        executor = SkillExecutor(clock=_clock)
        steps = (
            SkillStep(step_id="s1", name="first", action_type="x"),
            SkillStep(step_id="s2", name="second", action_type="x", depends_on=("s1",)),
            SkillStep(step_id="s3", name="third", action_type="x", depends_on=("s2",)),
        )
        skill = _make_skill(
            "comp", skill_class=SkillClass.COMPOSITE, steps=steps,
        )
        record = executor.execute(skill, step_executor=SuccessStepExecutor())
        assert record.outcome.status is SkillOutcomeStatus.SUCCEEDED
        assert len(record.outcome.step_outcomes) == 3
        # Steps should be in dependency order
        assert record.outcome.step_outcomes[0].step_id == "s1"
        assert record.outcome.step_outcomes[1].step_id == "s2"
        assert record.outcome.step_outcomes[2].step_id == "s3"

    def test_composite_stops_on_failure(self):
        executor = SkillExecutor(clock=_clock)
        steps = (
            SkillStep(step_id="s1", name="first", action_type="x"),
            SkillStep(step_id="s2", name="second", action_type="x", depends_on=("s1",)),
            SkillStep(step_id="s3", name="third", action_type="x", depends_on=("s2",)),
        )
        skill = _make_skill(
            "comp", skill_class=SkillClass.COMPOSITE, steps=steps,
        )
        # s2 fails
        record = executor.execute(skill, step_executor=SelectiveStepExecutor(fail_step_ids={"s2"}))
        assert record.outcome.status is SkillOutcomeStatus.STEP_FAILED
        # s3 should not have been executed
        assert len(record.outcome.step_outcomes) == 2
        assert record.outcome.step_outcomes[0].status is SkillOutcomeStatus.SUCCEEDED
        assert record.outcome.step_outcomes[1].status is SkillOutcomeStatus.FAILED

    def test_composite_parallel_steps(self):
        """Steps without dependencies execute in deterministic (ID-sorted) order."""
        executor = SkillExecutor(clock=_clock)
        steps = (
            SkillStep(step_id="c", name="c", action_type="x"),
            SkillStep(step_id="a", name="a", action_type="x"),
            SkillStep(step_id="b", name="b", action_type="x"),
        )
        skill = _make_skill(
            "comp", skill_class=SkillClass.COMPOSITE, steps=steps,
        )
        record = executor.execute(skill, step_executor=SuccessStepExecutor())
        assert record.outcome.status is SkillOutcomeStatus.SUCCEEDED
        ids = [so.step_id for so in record.outcome.step_outcomes]
        assert ids == ["a", "b", "c"]  # sorted by ID

    def test_execution_record_has_stable_id(self):
        executor = SkillExecutor(clock=_clock)
        skill = _make_skill("a")
        r1 = executor.execute(skill, step_executor=SuccessStepExecutor())
        r2 = executor.execute(skill, step_executor=SuccessStepExecutor())
        # Same skill + same clock = same record_id (deterministic)
        assert r1.record_id == r2.record_id

    def test_input_context_passed_to_step(self):
        captured = {}

        class CapturingExecutor:
            def execute_step(self, step_id, action_type, input_bindings):
                captured.update(input_bindings)
                return SkillStepOutcome(step_id=step_id, status=SkillOutcomeStatus.SUCCEEDED)

        executor = SkillExecutor(clock=_clock)
        skill = _make_skill("a")
        executor.execute(skill, step_executor=CapturingExecutor(), input_context={"key": "val"})
        assert captured["key"] == "val"
