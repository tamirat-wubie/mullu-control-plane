"""Tier 2 structural constructs — disambiguation, invariants, composition."""
from __future__ import annotations

from uuid import uuid4

import pytest

from mcoi_runtime.substrate.constructs import (
    Boundary,
    Causation,
    Change,
    Composition,
    Conservation,
    Constraint,
    ConstructType,
    Interaction,
    Pattern,
    State,
    TIER1_RESPONSIBILITIES,
    TIER2_RESPONSIBILITIES,
    Tier,
    Transformation,
    verify_no_cross_tier_overlap,
    verify_tier2_disambiguation,
)


# ---- Disambiguation tests ----


def test_tier2_responsibilities_are_distinct():
    verify_tier2_disambiguation()
    assert len(set(TIER2_RESPONSIBILITIES.values())) == 5


def test_no_cross_tier_overlap():
    verify_no_cross_tier_overlap()
    all_resp = list(TIER1_RESPONSIBILITIES.values()) + list(
        TIER2_RESPONSIBILITIES.values()
    )
    assert len(set(all_resp)) == 10  # 5 + 5


def test_each_tier2_construct_has_unique_type():
    types = {ct for ct in TIER2_RESPONSIBILITIES.keys()}
    expected = {
        ConstructType.PATTERN,
        ConstructType.TRANSFORMATION,
        ConstructType.COMPOSITION,
        ConstructType.INTERACTION,
        ConstructType.CONSERVATION,
    }
    assert types == expected


# ---- Pattern ----


def test_pattern_with_template_only():
    state = State(configuration={"x": 1})
    p = Pattern(template_state_id=state.id)
    assert p.tier == Tier.STRUCTURAL
    assert p.type == ConstructType.PATTERN
    assert p.similarity_threshold == 1.0
    assert p.similarity_rule == "structural_equivalence"


def test_pattern_with_instances_only():
    s1, s2 = State(configuration={"x": 1}), State(configuration={"x": 2})
    p = Pattern(instance_state_ids=(s1.id, s2.id))
    assert len(p.instance_state_ids) == 2


def test_pattern_requires_template_or_instances():
    with pytest.raises(ValueError):
        Pattern()


def test_pattern_threshold_bounds():
    s = State(configuration={})
    with pytest.raises(ValueError):
        Pattern(template_state_id=s.id, similarity_threshold=1.5)
    with pytest.raises(ValueError):
        Pattern(template_state_id=s.id, similarity_threshold=-0.1)


def test_pattern_requires_similarity_rule():
    s = State(configuration={})
    with pytest.raises(ValueError):
        Pattern(template_state_id=s.id, similarity_rule="")


# ---- Transformation ----


def test_transformation_basic():
    s_before = State(configuration={"phase": "liquid"})
    s_after = State(configuration={"phase": "solid"})
    chg = Change(
        state_before_id=s_before.id,
        state_after_id=s_after.id,
        delta_vector={"phase": "liquid->solid"},
    )
    cause = Causation(
        cause_id=s_before.id,
        effect_id=chg.id,
        mechanism="cooling",
        strength=0.9,
    )
    bnd = Boundary(inside_predicate="contained_in_vessel")

    t = Transformation(
        initial_state_id=s_before.id,
        target_state_id=s_after.id,
        change_id=chg.id,
        causation_id=cause.id,
        boundary_id=bnd.id,
        energy_estimate=10.5,
        reversibility="reversible",
    )
    assert t.tier == Tier.STRUCTURAL
    assert t.energy_estimate == 10.5
    assert t.reversibility == "reversible"


def test_transformation_rejects_negative_energy():
    with pytest.raises(ValueError):
        Transformation(energy_estimate=-1.0)


def test_transformation_rejects_invalid_reversibility():
    with pytest.raises(ValueError):
        Transformation(reversibility="maybe")


def test_transformation_default_invariants():
    t = Transformation()
    assert "tier1_references_required" in t.invariants
    assert "boundary_contains_states" in t.invariants


# ---- Composition ----


def test_composition_basic():
    s = State(configuration={})
    container = Pattern(template_state_id=s.id)
    contained_a = Pattern(template_state_id=s.id)
    contained_b = Pattern(template_state_id=s.id)
    bnd = Boundary(inside_predicate="root_scope")

    c = Composition(
        container_pattern_id=container.id,
        contained_pattern_ids=(contained_a.id, contained_b.id),
        boundary_id=bnd.id,
        nesting_depth=2,
    )
    assert c.nesting_depth == 2
    assert len(c.contained_pattern_ids) == 2


def test_composition_rejects_cyclic_nesting():
    p_id = uuid4()
    other_id = uuid4()
    with pytest.raises(ValueError, match="cyclic"):
        Composition(
            container_pattern_id=p_id,
            contained_pattern_ids=(p_id, other_id),
        )


def test_composition_rejects_excessive_depth():
    p_id, c_id = uuid4(), uuid4()
    with pytest.raises(ValueError, match="bounded-recursion"):
        Composition(
            container_pattern_id=p_id,
            contained_pattern_ids=(c_id,),
            nesting_depth=6,
        )


def test_composition_rejects_zero_depth():
    p_id, c_id = uuid4(), uuid4()
    with pytest.raises(ValueError):
        Composition(
            container_pattern_id=p_id,
            contained_pattern_ids=(c_id,),
            nesting_depth=0,
        )


def test_composition_requires_container():
    with pytest.raises(ValueError, match="container_pattern_id"):
        Composition(contained_pattern_ids=(uuid4(),))


def test_composition_requires_contained():
    with pytest.raises(ValueError, match="contained pattern"):
        Composition(container_pattern_id=uuid4())


# ---- Conservation ----


def test_conservation_basic():
    s = State(configuration={})
    p = Pattern(template_state_id=s.id)
    c = Constraint(domain="physics", restriction="energy_total_constant")
    b = Boundary(inside_predicate="closed_system")

    cons = Conservation(
        invariant_pattern_id=p.id,
        enforcing_constraint_id=c.id,
        scope_boundary_id=b.id,
        violation_detection="continuous_monitoring",
    )
    assert cons.tier == Tier.STRUCTURAL
    assert cons.violation_detection == "continuous_monitoring"


def test_conservation_rejects_missing_references():
    with pytest.raises(ValueError):
        Conservation()
    with pytest.raises(ValueError):
        Conservation(invariant_pattern_id=uuid4())  # missing other two


def test_conservation_rejects_invalid_detection_mode():
    with pytest.raises(ValueError):
        Conservation(
            invariant_pattern_id=uuid4(),
            enforcing_constraint_id=uuid4(),
            scope_boundary_id=uuid4(),
            violation_detection="when_we_feel_like_it",
        )


def test_conservation_default_detection_mode():
    cons = Conservation(
        invariant_pattern_id=uuid4(),
        enforcing_constraint_id=uuid4(),
        scope_boundary_id=uuid4(),
    )
    assert cons.violation_detection == "post_change_validation"


# ---- Interaction ----


def test_interaction_basic():
    s1, s2 = State(configuration={"x": 1}), State(configuration={"x": 2})
    chg1 = Change(
        state_before_id=s1.id, state_after_id=s2.id, delta_vector={"d": 1}
    )
    chg2 = Change(
        state_before_id=s2.id, state_after_id=s1.id, delta_vector={"d": -1}
    )
    c1 = Causation(cause_id=s1.id, effect_id=chg1.id, mechanism="push")
    c2 = Causation(cause_id=s2.id, effect_id=chg2.id, mechanism="reaction")

    inter = Interaction(
        participant_state_ids=(s1.id, s2.id),
        causation_ids=(c1.id, c2.id),
        coupling_strength=0.7,
        feedback_kind="negative",
    )
    assert len(inter.participant_state_ids) == 2
    assert inter.coupling_strength == 0.7
    assert inter.feedback_kind == "negative"


def test_interaction_requires_two_participants():
    with pytest.raises(ValueError, match=">= 2"):
        Interaction(
            participant_state_ids=(uuid4(),),
            causation_ids=(uuid4(),),
        )


def test_interaction_requires_causation_per_participant():
    p1, p2, p3 = uuid4(), uuid4(), uuid4()
    with pytest.raises(ValueError, match="Causation per participant"):
        Interaction(
            participant_state_ids=(p1, p2, p3),
            causation_ids=(uuid4(),),  # only 1 for 3 participants
        )


def test_interaction_rejects_duplicate_participants():
    p = uuid4()
    with pytest.raises(ValueError, match="distinct"):
        Interaction(
            participant_state_ids=(p, p),
            causation_ids=(uuid4(), uuid4()),
        )


def test_interaction_coupling_bounds():
    p1, p2 = uuid4(), uuid4()
    with pytest.raises(ValueError):
        Interaction(
            participant_state_ids=(p1, p2),
            causation_ids=(uuid4(), uuid4()),
            coupling_strength=1.5,
        )


def test_interaction_invalid_feedback_kind():
    p1, p2 = uuid4(), uuid4()
    with pytest.raises(ValueError):
        Interaction(
            participant_state_ids=(p1, p2),
            causation_ids=(uuid4(), uuid4()),
            feedback_kind="confused",
        )


# ---- Cross-tier integration ----


def test_full_construct_graph_smoke():
    """Build a complete graph using all 10 implemented constructs.

    Scenario: ice forms in a closed thermos.
    """
    # Tier 1
    liquid = State(configuration={"phase": "liquid", "temp_c": 5})
    solid = State(configuration={"phase": "solid", "temp_c": -2})
    cooling_change = Change(
        state_before_id=liquid.id,
        state_after_id=solid.id,
        delta_vector={"phase": "liquid->solid", "delta_temp": -7},
    )
    ambient = Causation(
        cause_id=liquid.id,
        effect_id=cooling_change.id,
        mechanism="ambient_heat_loss",
        strength=0.85,
    )
    freezing_rule = Constraint(
        domain="thermodynamics",
        restriction="temp_c <= 0 -> water freezes",
        violation_response="block",
    )
    thermos = Boundary(
        inside_predicate="contained_in_thermos",
        permeability="closed",
    )

    # Tier 2
    freeze_pattern = Pattern(
        template_state_id=solid.id,
        instance_state_ids=(solid.id,),
    )
    freeze_transform = Transformation(
        initial_state_id=liquid.id,
        target_state_id=solid.id,
        change_id=cooling_change.id,
        causation_id=ambient.id,
        boundary_id=thermos.id,
        energy_estimate=334.0,  # latent heat of fusion (J/g)
        reversibility="reversible",
    )
    energy_conservation = Conservation(
        invariant_pattern_id=freeze_pattern.id,
        enforcing_constraint_id=freezing_rule.id,
        scope_boundary_id=thermos.id,
        violation_detection="continuous_monitoring",
    )

    # All constructs created successfully
    assert freeze_transform.boundary_id == thermos.id
    assert energy_conservation.scope_boundary_id == thermos.id
    assert freeze_pattern.template_state_id == solid.id
