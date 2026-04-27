"""Tier 5 cognitive constructs."""
from __future__ import annotations

from uuid import uuid4

import pytest

from mcoi_runtime.substrate.constructs import (
    Decision,
    Execution,
    Inference,
    Learning,
    Observation,
    TIER5_RESPONSIBILITIES,
    Tier,
    verify_tier5_disambiguation,
)


def test_tier5_disambiguation():
    verify_tier5_disambiguation()
    assert len(set(TIER5_RESPONSIBILITIES.values())) == 5


# ---- Observation ----


def test_observation_basic():
    s = uuid4()
    o = Observation(
        sensor_identifier="thermometer-01",
        raw_signal="bytes:0x4f5a",
        interpreted_state_id=s,
        confidence=0.95,
        timestamp_iso="2026-04-26T10:00:00Z",
    )
    assert o.tier == Tier.COGNITIVE
    assert o.confidence == 0.95


def test_observation_requires_interpretation():
    with pytest.raises(ValueError, match="interpreted_state_id"):
        Observation(
            sensor_identifier="s",
            raw_signal="x",
            interpreted_state_id=None,
        )


def test_observation_requires_signal():
    with pytest.raises(ValueError):
        Observation(
            sensor_identifier="s",
            raw_signal="",
            interpreted_state_id=uuid4(),
        )


# ---- Inference ----


def test_inference_basic():
    p1, p2, conc = uuid4(), uuid4(), uuid4()
    i = Inference(
        premise_ids=(p1, p2),
        rule_identifier="modus_ponens",
        conclusion_id=conc,
        certainty=1.0,
        inference_kind="deductive",
    )
    assert i.inference_kind == "deductive"


def test_inference_requires_premises():
    with pytest.raises(ValueError):
        Inference(
            premise_ids=(),
            rule_identifier="r",
            conclusion_id=uuid4(),
        )


def test_inference_invalid_kind():
    with pytest.raises(ValueError):
        Inference(
            premise_ids=(uuid4(),),
            rule_identifier="r",
            conclusion_id=uuid4(),
            inference_kind="psychic",
        )


# ---- Decision ----


def test_decision_basic():
    a, b, c = uuid4(), uuid4(), uuid4()
    d = Decision(
        option_ids=(a, b, c),
        selection_criteria=("lowest_risk", "shortest_latency"),
        chosen_option_id=b,
        justification="b satisfies both criteria; a fails risk; c fails latency",
        decision_kind="deliberate",
    )
    assert d.chosen_option_id == b


def test_decision_requires_two_options():
    with pytest.raises(ValueError, match=">= 2 options"):
        Decision(
            option_ids=(uuid4(),),
            selection_criteria=("c",),
            chosen_option_id=uuid4(),
            justification="j",
        )


def test_decision_chosen_must_be_in_options():
    a, b = uuid4(), uuid4()
    other = uuid4()
    with pytest.raises(ValueError, match="must be one of"):
        Decision(
            option_ids=(a, b),
            selection_criteria=("c",),
            chosen_option_id=other,
            justification="j",
        )


def test_decision_requires_justification():
    a, b = uuid4(), uuid4()
    with pytest.raises(ValueError, match="justification"):
        Decision(
            option_ids=(a, b),
            selection_criteria=("c",),
            chosen_option_id=a,
            justification="",
        )


def test_decision_rejects_duplicate_options():
    a = uuid4()
    with pytest.raises(ValueError, match="distinct"):
        Decision(
            option_ids=(a, a),
            selection_criteria=("c",),
            chosen_option_id=a,
            justification="j",
        )


# ---- Execution ----


def test_execution_basic_pending():
    d = uuid4()
    e = Execution(
        plan_description="POST /v1/transfer with amount=100",
        decision_id=d,
        resource_allocations=("api_quota:1", "compute:0.1"),
        completion_state="pending",
    )
    assert e.completion_state == "pending"


def test_execution_completed_requires_change():
    with pytest.raises(ValueError, match="produced_change_id"):
        Execution(
            plan_description="p",
            decision_id=uuid4(),
            completion_state="completed",
            produced_change_id=None,
        )


def test_execution_completed_with_change():
    e = Execution(
        plan_description="p",
        decision_id=uuid4(),
        completion_state="completed",
        produced_change_id=uuid4(),
    )
    assert e.completion_state == "completed"


def test_execution_requires_decision():
    with pytest.raises(ValueError, match="decision_id"):
        Execution(plan_description="p")


def test_execution_invalid_completion_state():
    with pytest.raises(ValueError):
        Execution(
            plan_description="p",
            decision_id=uuid4(),
            completion_state="vibing",
        )


# ---- Learning ----


def test_learning_basic():
    e1, e2 = uuid4(), uuid4()
    pat = uuid4()
    val = uuid4()
    l = Learning(
        experience_execution_ids=(e1, e2),
        extracted_pattern_id=pat,
        validation_id=val,
        learning_kind="reinforcement",
    )
    assert l.learning_kind == "reinforcement"


def test_learning_requires_validation():
    """Unvalidated learning is a fabrication pattern."""
    with pytest.raises(ValueError, match="validation"):
        Learning(
            experience_execution_ids=(uuid4(),),
            extracted_pattern_id=uuid4(),
            validation_id=None,
        )


def test_learning_requires_experience():
    with pytest.raises(ValueError):
        Learning(
            experience_execution_ids=(),
            extracted_pattern_id=uuid4(),
            validation_id=uuid4(),
        )


def test_learning_requires_pattern():
    with pytest.raises(ValueError):
        Learning(
            experience_execution_ids=(uuid4(),),
            extracted_pattern_id=None,
            validation_id=uuid4(),
        )


def test_learning_invalid_kind():
    with pytest.raises(ValueError):
        Learning(
            experience_execution_ids=(uuid4(),),
            extracted_pattern_id=uuid4(),
            validation_id=uuid4(),
            learning_kind="osmosis",
        )


# ---- Cross-tier full graph smoke test ----


def test_full_25_construct_cycle():
    """Build a cognitive cycle that uses every tier."""
    from mcoi_runtime.substrate.constructs import (
        Boundary, Causation, Change, Composition, Conservation, Constraint,
        Coupling, Emergence, Equilibrium, Interaction, Pattern, Resonance,
        State, Synchronization, Transformation, Source, Binding, Validation,
        Evolution, Integrity,
    )

    # Tier 1
    s_observed = State(configuration={"sensor_value": 42})
    s_target = State(configuration={"sensor_value": 50})
    chg = Change(
        state_before_id=s_observed.id,
        state_after_id=s_target.id,
        delta_vector={"d": 8},
    )
    cause = Causation(
        cause_id=s_observed.id, effect_id=chg.id, mechanism="adjustment"
    )
    constr = Constraint(domain="control", restriction="value <= 100")
    bnd = Boundary(inside_predicate="control_loop")

    # Tier 2
    pat = Pattern(template_state_id=s_target.id)
    transf = Transformation(
        initial_state_id=s_observed.id,
        target_state_id=s_target.id,
        change_id=chg.id,
        causation_id=cause.id,
        boundary_id=bnd.id,
    )
    contained = Pattern(template_state_id=s_observed.id)
    comp = Composition(
        container_pattern_id=pat.id,
        contained_pattern_ids=(contained.id,),
        boundary_id=bnd.id,
    )
    cons = Conservation(
        invariant_pattern_id=pat.id,
        enforcing_constraint_id=constr.id,
        scope_boundary_id=bnd.id,
    )
    inter = Interaction(
        participant_state_ids=(s_observed.id, s_target.id),
        causation_ids=(cause.id, cause.id),  # spec allows reuse
        coupling_strength=0.5,
    )

    # Tier 3
    coup = Coupling(source_id=s_observed.id, target_id=s_target.id, strength=0.7)
    sync = Synchronization(pattern_ids=(pat.id, contained.id), frequency=10.0)
    res = Resonance(pattern_id=pat.id, natural_frequency=10.0, amplitude=1.0)
    eq = Equilibrium(attractor_state_ids=(s_target.id,), perturbation_tolerance=0.1)
    em = Emergence(
        component_ids=(s_observed.id, s_target.id),
        interaction_ids=(inter.id,),
        novel_pattern_id=pat.id,
        irreducibility_evidence="single state alone does not exhibit oscillation",
    )

    # Tier 4
    src = Source(
        origin_identifier="control_law_v1",
        scope_description="control loop",
        legitimacy_basis="published_spec",
    )
    bind = Binding(
        agent_identifier="controller-1",
        action_description="adjust",
        consequence_change_id=chg.id,
    )
    valid = Validation(
        target_pattern_id=pat.id,
        criteria=("matches_template",),
        confidence=0.9,
        decision="pass",
    )
    evo = Evolution(
        current_constraint_id=constr.id,
        proposed_constraint_id=uuid4(),
        justification="loosen for new sensor range",
        impact_assessment="no breaking changes",
    )
    integ = Integrity(
        core_invariant_pattern_ids=(pat.id,),
        repair_protocol="restart_loop_with_fallback_setpoint",
    )

    # Tier 5
    obs = Observation(
        sensor_identifier="thermo",
        raw_signal="0x2a",
        interpreted_state_id=s_observed.id,
        confidence=0.99,
    )
    inf = Inference(
        premise_ids=(s_observed.id,),
        rule_identifier="control_law",
        conclusion_id=s_target.id,
        certainty=0.95,
    )
    other_option = uuid4()
    dec = Decision(
        option_ids=(s_target.id, other_option),
        selection_criteria=("minimize_overshoot",),
        chosen_option_id=s_target.id,
        justification="meets criterion",
    )
    exe = Execution(
        plan_description="set actuator",
        decision_id=dec.id,
        completion_state="completed",
        produced_change_id=chg.id,
    )
    learn = Learning(
        experience_execution_ids=(exe.id,),
        extracted_pattern_id=pat.id,
        validation_id=valid.id,
    )

    # Sanity: 25 distinct constructs created
    constructs = [
        s_observed, s_target, chg, cause, constr, bnd,
        pat, transf, comp, cons, inter,
        coup, sync, res, eq, em,
        src, bind, valid, evo, integ,
        obs, inf, dec, exe, learn,
    ]
    ids = {c.id for c in constructs}
    assert len(ids) == 26  # 6 Tier 1 (incl. contained Pattern) + ... = 26 here
    # All non-base attribute checks succeed without exception
    assert learn.validation_id == valid.id
    assert exe.produced_change_id == chg.id
