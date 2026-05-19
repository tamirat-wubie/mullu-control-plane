"""Purpose: verify the deterministic WH-question traversal kernel.
Governance scope: gait planning determinism, fail-closed validation, coverage, and bounded recursion.
Dependencies: WHRole contract and the interrogation gait kernel.
Invariants: same spec yields same witness; recursion is depth-bounded; pruned/over-budget
probes are kept explicit; non-reproducible configurations fail closed.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.whqr import WHRole
from mcoi_runtime.contracts.whqr import TruthGate
from mcoi_runtime.core.interrogation_gait import (
    CognitivePhase,
    DeterminismClass,
    GaitSpec,
    GaitWitness,
    GranularityMode,
    InterrogationGaitPlanner,
    PathTopology,
    PerspectiveMode,
    SelectionPolicy,
    TerminationPolicy,
    TraversalDirection,
    evaluate_gait,
    seal,
    to_forge_input,
    to_whqr_document,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

ROLES = (WHRole.WHO, WHRole.WHAT, WHRole.WHY, WHRole.HOW)


def spec(**overrides) -> GaitSpec:
    base = dict(roles=ROLES, phase=CognitivePhase.DEFINE)
    base.update(overrides)
    return GaitSpec(**base)


def test_same_spec_yields_identical_witness() -> None:
    planner = InterrogationGaitPlanner()
    a = planner.plan(spec(topology=PathTopology.CYCLE))
    b = planner.plan(spec(topology=PathTopology.CYCLE))

    assert a.witness() == b.witness()
    assert a.canonical_json() == b.canonical_json()
    assert a.witness().startswith("sha256:")
    assert " " not in a.canonical_json()


def test_distinct_style_vectors_produce_distinct_witnesses() -> None:
    planner = InterrogationGaitPlanner()
    linear = planner.plan(spec(topology=PathTopology.LINEAR))
    zigzag = planner.plan(
        spec(topology=PathTopology.ZIGZAG, granularity=GranularityMode.REFINE, max_depth=3)
    )

    assert linear.witness() != zigzag.witness()


def test_cycle_exhaustive_covers_every_role_exactly_once() -> None:
    trace = InterrogationGaitPlanner().plan(spec(topology=PathTopology.CYCLE))

    covered = [p.role for p in trace.active]
    assert sorted(covered, key=lambda r: r.value) == sorted(ROLES, key=lambda r: r.value)
    assert len(covered) == len(ROLES)


def test_pruned_roles_are_kept_as_explicit_skips_not_dropped() -> None:
    trace = InterrogationGaitPlanner().plan(
        spec(selection=SelectionPolicy.PRUNED),
        subject_roles=(WHRole.WHAT, WHRole.WHY),
    )

    skipped = [p for p in trace.probes if p.status == "skipped"]
    assert {p.role for p in skipped} == {WHRole.WHO, WHRole.HOW}
    assert all(p.reason == "out_of_subject_scope" for p in skipped)
    # nothing is silently removed: every spec role still appears in the trace
    assert {p.role for p in trace.probes} == set(ROLES)


def test_budget_termination_caps_active_probes_and_marks_rest() -> None:
    trace = InterrogationGaitPlanner().plan(
        spec(termination=TerminationPolicy.BUDGET, budget=2)
    )

    assert len(trace.active) == 2
    overflow = [p for p in trace.probes if p.status == "skipped"]
    assert overflow and all(p.reason == "budget_exhausted" for p in overflow)


def test_tree_dfs_recursion_is_depth_bounded() -> None:
    trace = InterrogationGaitPlanner().plan(
        spec(topology=PathTopology.TREE_DFS, max_depth=3)
    )

    assert max(p.depth for p in trace.probes) == 2  # 0-indexed, < max_depth


def test_dialectic_perspective_doubles_probes() -> None:
    planner = InterrogationGaitPlanner()
    single = planner.plan(spec(perspective=PerspectiveMode.SINGLE))
    dialectic = planner.plan(spec(perspective=PerspectiveMode.DIALECTIC))

    assert len(dialectic.probes) == 2 * len(single.probes)
    assert {p.perspective for p in dialectic.probes} == {"proponent", "skeptic"}


def test_seeded_random_selection_is_reproducible() -> None:
    planner = InterrogationGaitPlanner()
    cfg = dict(
        selection=SelectionPolicy.RANDOM,
        determinism=DeterminismClass.SEEDED,
        seed=42,
    )
    first = planner.plan(spec(**cfg))
    second = planner.plan(spec(**cfg))

    assert first.witness() == second.witness()


def test_backward_direction_reverses_the_trace() -> None:
    planner = InterrogationGaitPlanner()
    fwd = planner.plan(spec(topology=PathTopology.LINEAR))
    bwd = planner.plan(
        spec(topology=PathTopology.LINEAR, direction=TraversalDirection.BACKWARD)
    )

    assert [p.role for p in fwd.active] == list(ROLES)
    assert [p.role for p in bwd.active] == list(reversed(ROLES))


def test_stochastic_determinism_is_refused() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="stochastic"):
        spec(determinism=DeterminismClass.STOCHASTIC)


def test_seeded_without_seed_fails_closed() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="seed"):
        spec(determinism=DeterminismClass.SEEDED)


def test_random_selection_without_seeded_determinism_fails_closed() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="random selection requires seeded"):
        spec(selection=SelectionPolicy.RANDOM)


def test_budget_policy_requires_a_budget() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="budget"):
        spec(termination=TerminationPolicy.BUDGET)


def test_empty_roles_and_bad_depth_fail_closed() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="at least one WHRole"):
        GaitSpec(roles=(), phase=CognitivePhase.DEFINE)
    with pytest.raises(RuntimeCoreInvariantError, match="max_depth"):
        spec(max_depth=0)
    with pytest.raises(RuntimeCoreInvariantError, match="unique"):
        GaitSpec(roles=(WHRole.WHO, WHRole.WHO), phase=CognitivePhase.DEFINE)


def test_extended_interrogatives_are_available_and_traversable() -> None:
    extended = (WHRole.WHAT_IF, WHRole.WHY_NOT, WHRole.SO_WHAT, WHRole.ACCORDING_TO_WHOM)
    trace = InterrogationGaitPlanner().plan(
        GaitSpec(roles=extended, phase=CognitivePhase.CRITIQUE)
    )
    assert {p.role for p in trace.active} == set(extended)


def test_gait_lowers_to_whqr_and_evaluates_as_explicit_uncertainty() -> None:
    trace = InterrogationGaitPlanner().plan(spec(topology=PathTopology.CYCLE))
    document = to_whqr_document(trace)

    # Round-trips through the existing WHQR canonical serializer.
    assert document.canonical_json() == to_whqr_document(trace).canonical_json()
    # Unbound probes resolve to UNKNOWN via the real evaluator, never a guess.
    assert evaluate_gait(trace).truth == TruthGate.UNKNOWN


def test_fully_pruned_trace_refuses_to_lower() -> None:
    trace = InterrogationGaitPlanner().plan(
        spec(selection=SelectionPolicy.PRUNED),
        subject_roles=(),
    )
    assert trace.active == ()
    with pytest.raises(RuntimeCoreInvariantError, match="no active probes"):
        to_whqr_document(trace)


def test_seal_is_deterministic_and_self_verifying() -> None:
    trace = InterrogationGaitPlanner().plan(spec(topology=PathTopology.SPIRAL, max_depth=3,
                                                 granularity=GranularityMode.REFINE))
    w1, w2 = seal(trace), seal(trace)

    assert w1 == w2
    assert w1.witness_hash.startswith("sha256:")
    assert w1.trace_witness == trace.witness()
    with pytest.raises(RuntimeCoreInvariantError, match="hash mismatch"):
        GaitWitness(
            gait_version=w1.gait_version,
            trace_witness=w1.trace_witness,
            probe_count=w1.probe_count,
            active_count=w1.active_count,
            witness_hash="sha256:deadbeef",
        )


def test_to_forge_input_is_accepted_by_the_real_capability_forge() -> None:
    forge_mod = pytest.importorskip("gateway.capability_forge")

    payload = to_forge_input(spec(phase=CognitivePhase.VERIFY), owner_team="meta-reasoning")
    candidate = forge_mod.CapabilityForge().create_candidate(
        forge_mod.CapabilityForgeInput(**payload)
    )
    validation = forge_mod.CapabilityForge().validate(candidate)

    assert validation.accepted, validation.errors
    assert candidate.promotion_blocked is True
    assert candidate.certification_status == "candidate"


def test_to_forge_input_fails_closed_on_blank_owner() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="owner_team"):
        to_forge_input(spec(), owner_team="  ")
