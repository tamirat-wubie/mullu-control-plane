"""Purpose: verify gait trace certification into a platform ProofCapsule.
Governance scope: gait lifecycle certification, determinism, and proof verification.
Dependencies: proof/state_machine contracts and the gait proof module.
Invariants: receipt hashes are deterministic; coverage-failing gaits still yield a
receipt; verification reconstructs the witness from the trace.
"""

from __future__ import annotations

from mcoi_runtime.contracts.state_machine import TransitionVerdict
from mcoi_runtime.contracts.whqr import WHRole
from mcoi_runtime.core.interrogation_gait import (
    CognitivePhase,
    GaitSpec,
    InterrogationGaitPlanner,
    PathTopology,
    SelectionPolicy,
)
from mcoi_runtime.core.interrogation_gait_proof import (
    GAIT_MACHINE,
    certify_gait,
    verify_gait_proof,
)

TS = "2026-05-19T12:00:00+00:00"
ROLES = (WHRole.WHY, WHRole.WHAT, WHRole.HOW)


def _trace(**overrides):
    base = dict(roles=ROLES, phase=CognitivePhase.VERIFY, topology=PathTopology.CYCLE)
    base.update(overrides)
    return InterrogationGaitPlanner().plan(GaitSpec(**base))


def test_machine_has_single_legal_seal_edge() -> None:
    assert GAIT_MACHINE.is_legal("planned", "sealed", "seal_gait") is TransitionVerdict.ALLOWED
    assert GAIT_MACHINE.is_legal("planned", "sealed", "other") is TransitionVerdict.DENIED_ILLEGAL_EDGE
    # sealed is terminal — no outgoing edge
    assert GAIT_MACHINE.is_legal("sealed", "planned", "seal_gait") is TransitionVerdict.DENIED_TERMINAL_STATE


def test_certify_gait_allows_a_normal_trace_and_binds_the_witness() -> None:
    trace = _trace()
    capsule = certify_gait(trace, timestamp=TS)

    assert capsule.receipt.machine_id == "interrogation-gait"
    assert capsule.receipt.verdict is TransitionVerdict.ALLOWED
    assert capsule.receipt.to_state == "sealed"
    assert verify_gait_proof(capsule, trace) is True


def test_certification_is_deterministic() -> None:
    a = certify_gait(_trace(), timestamp=TS)
    b = certify_gait(_trace(), timestamp=TS)

    assert a.receipt.receipt_hash == b.receipt.receipt_hash
    assert a.receipt.replay_token == b.receipt.replay_token


def test_fully_pruned_gait_still_produces_a_denial_receipt() -> None:
    pruned = InterrogationGaitPlanner().plan(
        GaitSpec(roles=ROLES, phase=CognitivePhase.VERIFY, selection=SelectionPolicy.PRUNED),
        subject_roles=(),
    )
    capsule = certify_gait(pruned, timestamp=TS)

    assert capsule.receipt.verdict is TransitionVerdict.DENIED_GUARD_FAILED
    coverage = next(g for g in capsule.receipt.guard_verdicts if g.guard_id == "gait_coverage")
    assert coverage.passed is False and coverage.reason == "no_active_probes"
    # the denial receipt is still a complete, verifiable proof
    assert verify_gait_proof(capsule, pruned) is True


def test_verification_rejects_a_mismatched_trace() -> None:
    capsule = certify_gait(_trace(), timestamp=TS)
    other = _trace(phase=CognitivePhase.PLAN)

    assert verify_gait_proof(capsule, other) is False
