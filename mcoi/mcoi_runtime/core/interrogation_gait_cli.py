"""Purpose: side-effect-free CLI surface for planning/sealing/certifying gaits.
Governance scope: observation-only gait inspection; deterministic envelope output.
Dependencies: argparse; the interrogation gait kernel and its proof module.
Invariants:
  - No effects: planning, sealing, and certification are pure and deterministic.
  - Fail closed: malformed enum/spec input raises RuntimeCoreInvariantError.
  - Output envelope is deterministic for identical input.
"""

from __future__ import annotations

import argparse
import json
from enum import EnumMeta
from typing import Any

from mcoi_runtime.core.interrogation_gait import (
    CognitivePhase,
    ConcurrencyMode,
    DeterminismClass,
    GaitSpec,
    GranularityMode,
    InterrogationGaitPlanner,
    PathTopology,
    PerspectiveMode,
    SelectionPolicy,
    TerminationPolicy,
    TraversalDirection,
    seal,
)
from mcoi_runtime.core.interrogation_gait_proof import certify_gait
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.whqr import WHRole

_AXES: dict[str, EnumMeta] = {
    "topology": PathTopology,
    "direction": TraversalDirection,
    "granularity": GranularityMode,
    "selection": SelectionPolicy,
    "termination": TerminationPolicy,
    "concurrency": ConcurrencyMode,
    "determinism": DeterminismClass,
    "perspective": PerspectiveMode,
}


def _parse_enum(enum_cls: EnumMeta, value: str, field: str) -> Any:
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise RuntimeCoreInvariantError(f"invalid {field}: {value!r}") from exc


def _parse_roles(csv: str, field: str) -> tuple[WHRole, ...]:
    parts = [p.strip() for p in csv.split(",") if p.strip()]
    if not parts:
        raise RuntimeCoreInvariantError(f"{field} must list at least one WHRole")
    return tuple(_parse_enum(WHRole, p, field) for p in parts)


def build_gait_envelope(args: argparse.Namespace) -> dict[str, Any]:
    """Plan, seal, and (optionally) certify a gait into a deterministic envelope."""
    spec = GaitSpec(
        roles=_parse_roles(args.roles, "roles"),
        phase=_parse_enum(CognitivePhase, args.phase, "phase"),
        topology=_parse_enum(PathTopology, args.topology, "topology"),
        direction=_parse_enum(TraversalDirection, args.direction, "direction"),
        granularity=_parse_enum(GranularityMode, args.granularity, "granularity"),
        selection=_parse_enum(SelectionPolicy, args.selection, "selection"),
        termination=_parse_enum(TerminationPolicy, args.termination, "termination"),
        concurrency=_parse_enum(ConcurrencyMode, args.concurrency, "concurrency"),
        determinism=_parse_enum(DeterminismClass, args.determinism, "determinism"),
        perspective=_parse_enum(PerspectiveMode, args.perspective, "perspective"),
        max_depth=args.max_depth,
        seed=args.seed,
        budget=args.budget,
    )
    subject = _parse_roles(args.subject_roles, "subject_roles") if args.subject_roles is not None else None
    trace = InterrogationGaitPlanner().plan(spec, subject_roles=subject)
    witness = seal(trace)

    proof: dict[str, Any] | None = None
    if args.certify:
        if not args.at:
            raise RuntimeCoreInvariantError("--certify requires --at <ISO-8601 timestamp>")
        capsule = certify_gait(trace, timestamp=args.at)
        r = capsule.receipt
        proof = {
            "after_state_hash": r.after_state_hash,
            "before_state_hash": r.before_state_hash,
            "causal_parent": r.causal_parent,
            "issued_at": r.issued_at,
            "machine_id": r.machine_id,
            "receipt_hash": r.receipt_hash,
            "receipt_id": r.receipt_id,
            "replay_token": r.replay_token,
            "verdict": r.verdict.value,
        }

    return {
        "operation": "gait",
        "spec": {
            "roles": [role.value for role in spec.roles],
            "phase": spec.phase.value,
            "topology": spec.topology.value,
            "direction": spec.direction.value,
            "granularity": spec.granularity.value,
            "selection": spec.selection.value,
            "termination": spec.termination.value,
            "concurrency": spec.concurrency.value,
            "determinism": spec.determinism.value,
            "perspective": spec.perspective.value,
            "max_depth": spec.max_depth,
            "seed": spec.seed,
            "budget": spec.budget,
        },
        "gait_version": trace.gait_version,
        "probe_count": witness.probe_count,
        "active_count": witness.active_count,
        "witness": witness.trace_witness,
        "witness_seal": witness.witness_hash,
        "proof": proof,
    }


def render_gait_envelope(envelope: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(envelope, sort_keys=True, indent=2))
        return
    print("=== Interrogation Gait ===")
    print(f"phase: {envelope['spec']['phase']}")
    print(f"topology: {envelope['spec']['topology']}")
    print(f"roles: {','.join(envelope['spec']['roles'])}")
    print(f"probe_count: {envelope['probe_count']}")
    print(f"active_count: {envelope['active_count']}")
    print(f"witness: {envelope['witness']}")
    print(f"witness_seal: {envelope['witness_seal']}")
    if envelope["proof"] is not None:
        print(f"proof_verdict: {envelope['proof']['verdict']}")
        print(f"proof_receipt: {envelope['proof']['receipt_id']}")
        print(f"proof_receipt_hash: {envelope['proof']['receipt_hash']}")


def add_gait_parser(subparsers: Any) -> None:
    """Register the ``mcoi gait`` subcommand. Defaults mirror GaitSpec defaults."""
    p = subparsers.add_parser("gait", help="Plan/seal/certify an interrogation gait")
    p.add_argument("--roles", required=True, help="Comma-separated WHRole values")
    p.add_argument("--phase", required=True, choices=[e.value for e in CognitivePhase])
    for name, enum_cls in _AXES.items():
        members = list(enum_cls)  # type: ignore[call-overload]
        p.add_argument(f"--{name}", default=members[0].value,
                       choices=[m.value for m in members])
    p.add_argument("--max-depth", dest="max_depth", type=int, default=1)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--budget", type=int, default=None)
    p.add_argument("--subject-roles", dest="subject_roles", default=None,
                   help="Comma-separated WHRole values to keep in scope (pruned selection)")
    p.add_argument("--certify", action="store_true", help="Certify into a ProofCapsule")
    p.add_argument("--at", default=None, help="ISO-8601 timestamp (required with --certify)")
    p.add_argument("--json", action="store_true", help="Emit JSON envelope")


def gait_command(args: argparse.Namespace) -> int:
    """Thin shell: build and render the gait envelope; fail closed on bad input."""
    try:
        envelope = build_gait_envelope(args)
    except (RuntimeCoreInvariantError, ValueError) as exc:
        print(f"error: gait command rejected input ({type(exc).__name__})")
        return 1
    render_gait_envelope(envelope, json_output=args.json)
    return 0
