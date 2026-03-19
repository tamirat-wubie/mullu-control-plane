"""Tests for skill system contracts."""

import pytest

from mcoi_runtime.contracts.skill import (
    DeterminismClass,
    EffectClass,
    PostconditionType,
    PreconditionType,
    SkillClass,
    SkillDescriptor,
    SkillExecutionRecord,
    SkillLifecycle,
    SkillOutcome,
    SkillOutcomeStatus,
    SkillPostcondition,
    SkillPrecondition,
    SkillSelectionDecision,
    SkillStep,
    SkillStepOutcome,
    TrustClass,
    VerificationStrength,
)


# --- Helpers ---


def _primitive_descriptor(**overrides):
    defaults = dict(
        skill_id="skill-001",
        name="test-skill",
        skill_class=SkillClass.PRIMITIVE,
        effect_class=EffectClass.INTERNAL_PURE,
        determinism_class=DeterminismClass.DETERMINISTIC,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.STRONG,
    )
    defaults.update(overrides)
    return SkillDescriptor(**defaults)


def _composite_descriptor(**overrides):
    steps = overrides.pop("steps", (
        SkillStep(step_id="s1", name="step-one", action_type="shell"),
        SkillStep(step_id="s2", name="step-two", action_type="shell", depends_on=("s1",)),
    ))
    defaults = dict(
        skill_id="skill-comp",
        name="composite-skill",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.BOUNDED_EXTERNAL,
        verification_strength=VerificationStrength.MODERATE,
        steps=steps,
    )
    defaults.update(overrides)
    return SkillDescriptor(**defaults)


# --- SkillPrecondition ---


class TestSkillPrecondition:
    def test_valid(self):
        pc = SkillPrecondition(
            condition_id="pc-1",
            condition_type=PreconditionType.STATE_CHECK,
            description="check file exists",
        )
        assert pc.condition_id == "pc-1"
        assert pc.condition_type is PreconditionType.STATE_CHECK

    def test_empty_id_rejected(self):
        with pytest.raises(ValueError, match="condition_id"):
            SkillPrecondition(condition_id="", condition_type=PreconditionType.STATE_CHECK, description="x")

    def test_invalid_type_rejected(self):
        with pytest.raises(ValueError, match="condition_type"):
            SkillPrecondition(condition_id="pc-1", condition_type="bad", description="x")

    def test_parameters_frozen(self):
        pc = SkillPrecondition(
            condition_id="pc-1",
            condition_type=PreconditionType.PROVIDER_HEALTHY,
            description="check provider",
            parameters={"provider_id": "p1"},
        )
        assert pc.parameters["provider_id"] == "p1"


# --- SkillPostcondition ---


class TestSkillPostcondition:
    def test_valid(self):
        pc = SkillPostcondition(
            condition_id="post-1",
            condition_type=PostconditionType.FILE_EXISTS,
            description="output file created",
        )
        assert pc.condition_type is PostconditionType.FILE_EXISTS


# --- SkillStep ---


class TestSkillStep:
    def test_valid_step(self):
        step = SkillStep(step_id="s1", name="run-cmd", action_type="shell")
        assert step.step_id == "s1"
        assert step.depends_on == ()

    def test_with_dependencies(self):
        step = SkillStep(step_id="s2", name="check", action_type="verify", depends_on=("s1",))
        assert step.depends_on == ("s1",)

    def test_empty_id_rejected(self):
        with pytest.raises(ValueError, match="step_id"):
            SkillStep(step_id="", name="x", action_type="shell")

    def test_empty_dependency_rejected(self):
        with pytest.raises(ValueError, match="depends_on"):
            SkillStep(step_id="s1", name="x", action_type="shell", depends_on=("",))


# --- SkillDescriptor ---


class TestSkillDescriptor:
    def test_primitive_valid(self):
        d = _primitive_descriptor()
        assert d.skill_id == "skill-001"
        assert d.lifecycle is SkillLifecycle.CANDIDATE
        assert d.confidence == 0.0

    def test_composite_valid(self):
        d = _composite_descriptor()
        assert d.skill_class is SkillClass.COMPOSITE
        assert len(d.steps) == 2

    def test_composite_without_steps_rejected(self):
        with pytest.raises(ValueError, match="composite skills must have"):
            SkillDescriptor(
                skill_id="bad",
                name="no-steps",
                skill_class=SkillClass.COMPOSITE,
                effect_class=EffectClass.INTERNAL_PURE,
                determinism_class=DeterminismClass.DETERMINISTIC,
                trust_class=TrustClass.TRUSTED_INTERNAL,
                verification_strength=VerificationStrength.NONE,
                steps=(),
            )

    def test_learned_without_runbook_rejected(self):
        with pytest.raises(ValueError, match="learned skills must reference"):
            SkillDescriptor(
                skill_id="bad",
                name="no-runbook",
                skill_class=SkillClass.LEARNED,
                effect_class=EffectClass.INTERNAL_PURE,
                determinism_class=DeterminismClass.DETERMINISTIC,
                trust_class=TrustClass.TRUSTED_INTERNAL,
                verification_strength=VerificationStrength.NONE,
            )

    def test_learned_with_runbook_valid(self):
        d = SkillDescriptor(
            skill_id="learned-001",
            name="learned-skill",
            skill_class=SkillClass.LEARNED,
            effect_class=EffectClass.INTERNAL_PURE,
            determinism_class=DeterminismClass.DETERMINISTIC,
            trust_class=TrustClass.TRUSTED_INTERNAL,
            verification_strength=VerificationStrength.STRONG,
            runbook_id="rb-001",
        )
        assert d.runbook_id == "rb-001"

    def test_confidence_out_of_range_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _primitive_descriptor(confidence=1.5)

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _primitive_descriptor(confidence=-0.1)

    def test_circular_dependency_rejected(self):
        with pytest.raises(ValueError, match="circular"):
            _composite_descriptor(steps=(
                SkillStep(step_id="a", name="a", action_type="x", depends_on=("b",)),
                SkillStep(step_id="b", name="b", action_type="x", depends_on=("a",)),
            ))

    def test_unknown_dependency_rejected(self):
        with pytest.raises(ValueError, match="unknown step"):
            _composite_descriptor(steps=(
                SkillStep(step_id="a", name="a", action_type="x", depends_on=("missing",)),
            ))

    def test_three_step_chain_valid(self):
        d = _composite_descriptor(steps=(
            SkillStep(step_id="s1", name="first", action_type="x"),
            SkillStep(step_id="s2", name="second", action_type="x", depends_on=("s1",)),
            SkillStep(step_id="s3", name="third", action_type="x", depends_on=("s2",)),
        ))
        assert len(d.steps) == 3


# --- SkillStepOutcome ---


class TestSkillStepOutcome:
    def test_success(self):
        o = SkillStepOutcome(step_id="s1", status=SkillOutcomeStatus.SUCCEEDED)
        assert o.status is SkillOutcomeStatus.SUCCEEDED

    def test_with_outputs(self):
        o = SkillStepOutcome(
            step_id="s1",
            status=SkillOutcomeStatus.SUCCEEDED,
            outputs={"result": "ok"},
        )
        assert o.outputs["result"] == "ok"


# --- SkillOutcome ---


class TestSkillOutcome:
    def test_success(self):
        o = SkillOutcome(skill_id="sk-1", status=SkillOutcomeStatus.SUCCEEDED)
        assert o.preconditions_met is True
        assert o.postconditions_met is True

    def test_precondition_failed(self):
        o = SkillOutcome(
            skill_id="sk-1",
            status=SkillOutcomeStatus.PRECONDITION_NOT_MET,
            preconditions_met=False,
        )
        assert o.preconditions_met is False


# --- SkillSelectionDecision ---


class TestSkillSelectionDecision:
    def test_valid(self):
        d = SkillSelectionDecision(
            selected_skill_id="sk-1",
            candidates_considered=("sk-1", "sk-2"),
            selection_reasons=("lifecycle:trusted",),
            rejected_reasons={"sk-2": "blocked"},
        )
        assert d.selected_skill_id == "sk-1"
        assert d.rejected_reasons["sk-2"] == "blocked"


# --- SkillExecutionRecord ---


class TestSkillExecutionRecord:
    def test_valid(self):
        outcome = SkillOutcome(skill_id="sk-1", status=SkillOutcomeStatus.SUCCEEDED)
        rec = SkillExecutionRecord(
            record_id="rec-001",
            skill_id="sk-1",
            outcome=outcome,
        )
        assert rec.record_id == "rec-001"

    def test_invalid_outcome_type(self):
        with pytest.raises(ValueError, match="outcome must be"):
            SkillExecutionRecord(record_id="rec-001", skill_id="sk-1", outcome="bad")
