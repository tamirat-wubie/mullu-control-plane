"""Purpose: certify a planned interrogation gait into a platform ProofCapsule.
Governance scope: gait lifecycle state machine + transition certification only.
Dependencies: proof + state_machine contracts; the interrogation gait kernel.
Invariants:
  - The gait machine has exactly one legal edge: planned -> sealed via seal_gait.
  - Receipt hashes are deterministic (same trace + timestamp -> same receipt).
  - A coverage-failing gait still yields a receipt (the receipt IS the proof of
    the denial); the failed guard is preserved, never stripped.
  - Verification is pure and reconstructs the witness from the trace.
"""

from __future__ import annotations

import hashlib

from mcoi_runtime.contracts.proof import GuardVerdict, ProofCapsule, certify_transition
from mcoi_runtime.contracts.state_machine import StateMachineSpec, TransitionRule
from mcoi_runtime.core.interrogation_gait import GaitTrace, seal
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

_SHA256_PREFIX = "sha256:"

GAIT_MACHINE = StateMachineSpec(
    machine_id="interrogation-gait",
    name="Interrogation Gait Machine",
    version="1.0.0",
    states=("planned", "sealed"),
    initial_state="planned",
    terminal_states=("sealed",),
    transitions=(
        TransitionRule(from_state="planned", to_state="sealed", action="seal_gait"),
    ),
)


def _strip(digest: str) -> str:
    return digest[len(_SHA256_PREFIX):] if digest.startswith(_SHA256_PREFIX) else digest


def _entity_id(trace: GaitTrace) -> str:
    return f"gait:{trace.spec.phase.value}:{_strip(trace.witness())[:16]}"


def _planned_hash(entity_id: str) -> str:
    return hashlib.sha256(f"planned:{entity_id}".encode()).hexdigest()


def certify_gait(
    trace: GaitTrace,
    *,
    timestamp: str,
    actor_id: str = "interrogation-gait",
    causal_parent: str = "genesis",
) -> ProofCapsule:
    """Certify the planned -> sealed transition for a gait trace.

    A trace with no active probes (e.g. fully pruned) fails the coverage
    guard: the capsule is still returned with verdict DENIED_GUARD_FAILED so
    the receipt remains a complete proof of the empty gait.
    """
    if not isinstance(trace, GaitTrace):
        raise RuntimeCoreInvariantError("trace must be a GaitTrace")

    witness = seal(trace)
    entity_id = _entity_id(trace)
    before_hash = _planned_hash(entity_id)
    after_hash = _strip(witness.witness_hash)

    guards = (
        GuardVerdict(
            guard_id="gait_coverage",
            passed=witness.active_count > 0,
            reason="active_probes_present" if witness.active_count > 0 else "no_active_probes",
            detail={
                "active_count": witness.active_count,
                "probe_count": witness.probe_count,
                "trace_witness": witness.trace_witness,
            },
        ),
        GuardVerdict(
            guard_id="gait_determinism",
            passed=True,
            reason=trace.spec.determinism.value,
            detail={
                "phase": trace.spec.phase.value,
                "selection": trace.spec.selection.value,
                "topology": trace.spec.topology.value,
            },
        ),
    )

    return certify_transition(
        GAIT_MACHINE,
        entity_id=entity_id,
        from_state="planned",
        to_state="sealed",
        action="seal_gait",
        before_state_hash=before_hash,
        after_state_hash=after_hash,
        guards=guards,
        actor_id=actor_id,
        reason="interrogation_gait_sealed",
        causal_parent=causal_parent,
        timestamp=timestamp,
    )


def verify_gait_proof(capsule: ProofCapsule, trace: GaitTrace) -> bool:
    """Pure check: the capsule's receipt is self-consistent AND binds this trace.

    Returns True iff the receipt hash reconstructs from its own content and the
    after-state hash equals the witness independently recomputed from `trace`.
    """
    if not isinstance(capsule, ProofCapsule) or not isinstance(trace, GaitTrace):
        return False
    receipt = capsule.receipt
    content = (
        f"{receipt.entity_id}:{receipt.from_state}:{receipt.to_state}:"
        f"{receipt.action}:{receipt.before_state_hash}:{receipt.after_state_hash}:"
        f"{receipt.causal_parent}"
    )
    if hashlib.sha256(content.encode()).hexdigest() != receipt.receipt_hash:
        return False
    return receipt.after_state_hash == _strip(seal(trace).witness_hash)
