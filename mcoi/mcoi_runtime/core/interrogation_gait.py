"""Purpose: deterministic WH-question traversal kernel (the "gait" over WHRole space).
Governance scope: side-effect-free interrogation planning; emits an auditable probe trace.
Dependencies: WHRole from the shared WHQR contract; runtime-core invariant helpers.
Invariants: traversal is deterministic and canonically hashed; recursion is depth-bounded;
pruned/over-budget probes are kept as explicit skipped probes with a reason, never dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
from random import Random
from typing import Any, Mapping
import hashlib
import json

from mcoi_runtime.contracts.whqr import (
    GateResult,
    LogicalExpr,
    LogicalOp,
    WHQRDocument,
    WHQRNode,
    WHRole,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.whqr.evaluator import WHQREvaluationContext, evaluate

GAIT_VERSION = "0.1.0"

# Bounded-recursion / anti-combinatorial guardrails (meta-reasoning plane invariant:
# never reason recursively without a declared depth limit).
_MAX_DEPTH_CAP = 16
_MAX_PROBE_CAP = 4096


class CognitivePhase(StrEnum):
    """List 3 - the need the traversal serves."""

    DEFINE = "define"
    RESEARCH = "research"
    THINK = "think"
    DECIDE = "decide"
    PLAN = "plan"
    ACT = "act"
    ANSWER = "answer"
    EXPLAIN = "explain"
    ASK = "ask"
    WORK = "work"
    VERIFY = "verify"
    CRITIQUE = "critique"
    REFLECT = "reflect"
    PRIORITIZE = "prioritize"
    RECALL = "recall"
    LEARN = "learn"
    MONITOR = "monitor"
    PREDICT = "predict"
    RECONCILE = "reconcile"


class PathTopology(StrEnum):
    LINEAR = "linear"
    CYCLE = "cycle"
    SPIRAL = "spiral"
    ZIGZAG = "zigzag"
    TABULAR = "tabular"
    LAYERED = "layered"
    TREE_DFS = "tree_dfs"
    TREE_BFS = "tree_bfs"
    GRAPH = "graph"
    DIAGONAL = "diagonal"
    FRACTAL = "fractal"


class TraversalDirection(StrEnum):
    FORWARD = "forward"
    BACKWARD = "backward"
    BIDIRECTIONAL = "bidirectional"


class GranularityMode(StrEnum):
    FIXED = "fixed"
    REFINE = "refine"
    ABSTRACT = "abstract"
    OSCILLATING = "oscillating"


class SelectionPolicy(StrEnum):
    EXHAUSTIVE = "exhaustive"
    RANDOM = "random"
    PRUNED = "pruned"
    INFO_GAIN = "info_gain"


class TerminationPolicy(StrEnum):
    FIXED_COUNT = "fixed_count"
    BUDGET = "budget"
    SATURATION = "saturation"
    GOAL_SATISFACTION = "goal_satisfaction"
    CONTRADICTION = "contradiction"


class ConcurrencyMode(StrEnum):
    SERIAL = "serial"
    PARALLEL = "parallel"
    PIPELINED = "pipelined"
    ENSEMBLE = "ensemble"


class DeterminismClass(StrEnum):
    DETERMINISTIC = "deterministic"
    SEEDED = "seeded"
    STOCHASTIC = "stochastic"


class PerspectiveMode(StrEnum):
    SINGLE = "single"
    DIALECTIC = "dialectic"
    POLYPHONIC = "polyphonic"
    ADVERSARIAL = "adversarial"


# Fixed dependency/information-gain precedence over WHRole. Used by GRAPH topology
# (degenerate without an explicit edge input) and INFO_GAIN selection. A role not
# listed sorts last, in declared order, so unknown contract extensions stay stable.
_ROLE_PRECEDENCE: tuple[WHRole, ...] = (
    WHRole.WHY,
    WHRole.WHY_NOT,
    WHRole.WHAT,
    WHRole.WHAT_IF,
    WHRole.WHAT_ELSE,
    WHRole.WHICH,
    WHRole.WHO,
    WHRole.WHOM,
    WHRole.WHOSE,
    WHRole.ACCORDING_TO_WHOM,
    WHRole.WHERE,
    WHRole.WHEN,
    WHRole.HOW_LONG,
    WHRole.HOW_OFTEN,
    WHRole.HOW,
    WHRole.BY_WHAT_MEANS,
    WHRole.HOW_MUCH,
    WHRole.HOW_MANY,
    WHRole.UNDER_WHAT_CONDITIONS,
    WHRole.SO_WHAT,
)

_PERSPECTIVES: Mapping[PerspectiveMode, tuple[str, ...]] = {
    PerspectiveMode.SINGLE: ("self",),
    PerspectiveMode.DIALECTIC: ("proponent", "skeptic"),
    PerspectiveMode.POLYPHONIC: ("operator", "attacker", "auditor", "subject"),
    PerspectiveMode.ADVERSARIAL: ("self", "adversary"),
}


def _precedence_index(role: WHRole) -> int:
    try:
        return _ROLE_PRECEDENCE.index(role)
    except ValueError:
        return len(_ROLE_PRECEDENCE)


@dataclass(frozen=True, slots=True)
class GaitSpec:
    """A traversal style as a vector: interrogative mask x 8 axes x cognitive need."""

    roles: tuple[WHRole, ...]
    phase: CognitivePhase
    topology: PathTopology = PathTopology.LINEAR
    direction: TraversalDirection = TraversalDirection.FORWARD
    granularity: GranularityMode = GranularityMode.FIXED
    selection: SelectionPolicy = SelectionPolicy.EXHAUSTIVE
    termination: TerminationPolicy = TerminationPolicy.FIXED_COUNT
    concurrency: ConcurrencyMode = ConcurrencyMode.SERIAL
    determinism: DeterminismClass = DeterminismClass.DETERMINISTIC
    perspective: PerspectiveMode = PerspectiveMode.SINGLE
    max_depth: int = 1
    seed: int | None = None
    budget: int | None = None

    def __post_init__(self) -> None:
        roles = tuple(self.roles)
        if not roles:
            raise RuntimeCoreInvariantError("roles must contain at least one WHRole")
        if any(not isinstance(role, WHRole) for role in roles):
            raise RuntimeCoreInvariantError("roles must all be WHRole values")
        if len(set(roles)) != len(roles):
            raise RuntimeCoreInvariantError("roles must be unique")
        object.__setattr__(self, "roles", roles)

        for name, enum_type in (
            ("phase", CognitivePhase),
            ("topology", PathTopology),
            ("direction", TraversalDirection),
            ("granularity", GranularityMode),
            ("selection", SelectionPolicy),
            ("termination", TerminationPolicy),
            ("concurrency", ConcurrencyMode),
            ("determinism", DeterminismClass),
            ("perspective", PerspectiveMode),
        ):
            if not isinstance(getattr(self, name), enum_type):
                raise RuntimeCoreInvariantError(f"{name} must be a {enum_type.__name__} value")

        if not isinstance(self.max_depth, int) or isinstance(self.max_depth, bool):
            raise RuntimeCoreInvariantError("max_depth must be an int")
        if not 1 <= self.max_depth <= _MAX_DEPTH_CAP:
            raise RuntimeCoreInvariantError(
                f"max_depth must be in [1, {_MAX_DEPTH_CAP}]"
            )

        # Determinism is a platform invariant: stochastic traversal is refused;
        # randomness is only admitted when it is reproducible from a seed.
        if self.determinism is DeterminismClass.STOCHASTIC:
            raise RuntimeCoreInvariantError(
                "stochastic determinism is forbidden; use seeded for reproducible randomness"
            )
        if self.determinism is DeterminismClass.SEEDED:
            if not isinstance(self.seed, int) or isinstance(self.seed, bool):
                raise RuntimeCoreInvariantError("seeded determinism requires an int seed")
        elif self.seed is not None:
            raise RuntimeCoreInvariantError("seed is only permitted with seeded determinism")
        if self.selection is SelectionPolicy.RANDOM and self.determinism is not DeterminismClass.SEEDED:
            raise RuntimeCoreInvariantError("random selection requires seeded determinism")

        if self.termination is TerminationPolicy.BUDGET:
            if not isinstance(self.budget, int) or isinstance(self.budget, bool) or self.budget < 1:
                raise RuntimeCoreInvariantError("budget termination requires a budget >= 1")
        elif self.budget is not None:
            raise RuntimeCoreInvariantError("budget is only permitted with budget termination")


@dataclass(frozen=True, slots=True)
class Probe:
    """One interrogation step. status is 'active' or 'skipped'; skipped carries a reason."""

    index: int
    role: WHRole
    phase: CognitivePhase
    depth: int
    perspective: str
    status: str = "active"
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class GaitTrace:
    """The ordered probe sequence a GaitSpec produces. The trace digest is the witness."""

    spec: GaitSpec
    probes: tuple[Probe, ...]
    gait_version: str = GAIT_VERSION

    def canonical_json(self) -> str:
        try:
            return json.dumps(
                _canonical(self),
                sort_keys=True,
                ensure_ascii=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeCoreInvariantError(
                "gait trace must serialize to deterministic canonical JSON"
            ) from exc

    def witness(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @property
    def active(self) -> tuple[Probe, ...]:
        return tuple(p for p in self.probes if p.status == "active")


def _canonical(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _canonical(getattr(value, f.name)) for f in fields(value)}
    return value


def _levels(spec: GaitSpec) -> tuple[int, ...]:
    if spec.granularity is GranularityMode.FIXED:
        return (0,)
    depth = spec.max_depth
    if spec.granularity is GranularityMode.REFINE:
        return tuple(range(depth))
    if spec.granularity is GranularityMode.ABSTRACT:
        return tuple(reversed(range(depth)))
    # OSCILLATING: 0, depth-1, 1, depth-2, ...
    lo, hi, out = 0, depth - 1, []
    while lo <= hi:
        out.append(lo)
        if hi != lo:
            out.append(hi)
        lo, hi = lo + 1, hi - 1
    return tuple(out)


def _topology_pairs(spec: GaitSpec, roles: tuple[WHRole, ...]) -> list[tuple[WHRole, int]]:
    """Return ordered (role, depth) pairs for the chosen path topology."""
    levels = _levels(spec)
    n = len(roles)
    pairs: list[tuple[WHRole, int]] = []

    if spec.topology in (PathTopology.LINEAR, PathTopology.CYCLE):
        for lvl in levels:
            pairs.extend((r, lvl) for r in roles)
    elif spec.topology in (PathTopology.LAYERED, PathTopology.TABULAR):
        for lvl in levels:
            pairs.extend((r, lvl) for r in roles)
    elif spec.topology is PathTopology.GRAPH:
        ordered = sorted(roles, key=_precedence_index)
        for lvl in levels:
            pairs.extend((r, lvl) for r in ordered)
    elif spec.topology is PathTopology.ZIGZAG:
        for i, lvl in enumerate(levels):
            row = roles if i % 2 == 0 else tuple(reversed(roles))
            pairs.extend((r, lvl) for r in row)
    elif spec.topology is PathTopology.SPIRAL:
        steps = max(n, len(levels))
        for k in range(steps):
            pairs.append((roles[k % n], levels[k % len(levels)]))
    elif spec.topology is PathTopology.DIAGONAL:
        for k in range(n * len(levels)):
            pairs.append((roles[k % n], levels[(k // n) % len(levels)]))
    elif spec.topology in (PathTopology.TREE_DFS, PathTopology.TREE_BFS, PathTopology.FRACTAL):
        pairs = _tree_pairs(spec, roles)
    else:  # pragma: no cover - all enum members handled above
        raise RuntimeCoreInvariantError(f"unhandled topology {spec.topology}")

    if len(pairs) > _MAX_PROBE_CAP:
        raise RuntimeCoreInvariantError(
            f"gait expansion {len(pairs)} exceeds bounded probe cap {_MAX_PROBE_CAP}"
        )
    return pairs


def _tree_pairs(spec: GaitSpec, roles: tuple[WHRole, ...]) -> list[tuple[WHRole, int]]:
    depth_limit = min(spec.max_depth, _MAX_DEPTH_CAP)
    out: list[tuple[WHRole, int]] = []

    def emit(depth: int) -> None:
        if depth >= depth_limit or len(out) > _MAX_PROBE_CAP:
            return
        for r in roles:
            out.append((r, depth))
            emit(depth + 1)

    if spec.topology is PathTopology.TREE_BFS:
        for depth in range(depth_limit):
            out.extend((r, depth) for r in roles)
    else:
        # TREE_DFS / FRACTAL: pre-order, role set re-applied at each deeper level.
        emit(0)
    if len(out) > _MAX_PROBE_CAP:
        raise RuntimeCoreInvariantError(
            f"gait expansion {len(out)} exceeds bounded probe cap {_MAX_PROBE_CAP}"
        )
    return out


def _apply_direction(
    spec: GaitSpec, pairs: list[tuple[WHRole, int]]
) -> list[tuple[WHRole, int]]:
    if spec.direction is TraversalDirection.FORWARD:
        return pairs
    if spec.direction is TraversalDirection.BACKWARD:
        return list(reversed(pairs))
    # BIDIRECTIONAL: interleave forward and reversed, meeting in the middle.
    fwd, bwd, out = pairs, list(reversed(pairs)), []
    for i in range((len(pairs) + 1) // 2):
        out.append(fwd[i])
        if i != len(pairs) - 1 - i:
            out.append(bwd[i])
    return out


class InterrogationGaitPlanner:
    """Compile a GaitSpec into a deterministic, auditable probe trace."""

    def plan(
        self,
        spec: GaitSpec,
        subject_roles: tuple[WHRole, ...] | None = None,
    ) -> GaitTrace:
        if not isinstance(spec, GaitSpec):
            raise RuntimeCoreInvariantError("spec must be a GaitSpec")

        pairs = _apply_direction(spec, _topology_pairs(spec, spec.roles))

        if spec.selection is SelectionPolicy.INFO_GAIN:
            pairs = sorted(pairs, key=lambda rp: (_precedence_index(rp[0]), rp[1]))
        elif spec.selection is SelectionPolicy.RANDOM:
            rng = Random(spec.seed)
            pairs = pairs[:]
            rng.shuffle(pairs)

        in_scope = set(subject_roles) if subject_roles is not None else None
        perspectives = _PERSPECTIVES[spec.perspective]

        probes: list[Probe] = []
        active_count = 0
        idx = 0
        for role, depth in pairs:
            pruned = (
                spec.selection is SelectionPolicy.PRUNED
                and in_scope is not None
                and role not in in_scope
            )
            for vp in perspectives:
                status, reason = "active", None
                if pruned:
                    status, reason = "skipped", "out_of_subject_scope"
                elif (
                    spec.termination is TerminationPolicy.BUDGET
                    and spec.budget is not None
                    and active_count >= spec.budget
                ):
                    status, reason = "skipped", "budget_exhausted"
                if status == "active":
                    active_count += 1
                probes.append(
                    Probe(
                        index=idx,
                        role=role,
                        phase=spec.phase,
                        depth=depth,
                        perspective=vp,
                        status=status,
                        reason=reason,
                    )
                )
                idx += 1

        return GaitTrace(spec=spec, probes=tuple(probes))


# --- Bridge into the existing WHQR semantic layer ---------------------------
#
# The gait kernel decides *how to traverse* the interrogation; WHQR decides
# *what each question means and whether it is resolved*. Lowering a trace into a
# WHQRDocument lets the existing pure evaluator/split-gates judge the gait
# instead of the kernel being an island.


def _lowered_target(probe: Probe) -> str:
    return f"{probe.phase.value}:{probe.perspective}:{probe.role.value}:{probe.depth}:{probe.index}"


def to_whqr_document(trace: GaitTrace) -> WHQRDocument:
    """Lower the active probes of a trace into a conjunctive WHQR document."""
    nodes = tuple(
        WHQRNode(
            role=p.role,
            target=_lowered_target(p),
            metadata={
                "phase": p.phase.value,
                "perspective": p.perspective,
                "depth": p.depth,
            },
        )
        for p in trace.active
    )
    if not nodes:
        raise RuntimeCoreInvariantError("gait trace has no active probes to lower")
    root = nodes[0] if len(nodes) == 1 else LogicalExpr(op=LogicalOp.AND, args=nodes)
    return WHQRDocument(root=root, metadata={"gait_witness": trace.witness()})


def evaluate_gait(
    trace: GaitTrace,
    context: WHQREvaluationContext | None = None,
) -> GateResult:
    """Resolve a gait trace through the existing WHQR evaluator.

    With no node bindings every probe is an unresolved question, so the
    aggregate truth is UNKNOWN/unproven - explicit uncertainty, not a guess.
    """
    return evaluate(to_whqr_document(trace).root, context)


# --- Sealed witness (proof-surface artifact) --------------------------------


@dataclass(frozen=True, slots=True)
class GaitWitness:
    """Compact, canonically hashed seal over a planned trace.

    The trace digest is the reproducibility anchor; this record is the
    portable proof-surface form (same shape as other platform witnesses:
    deterministic sha256 over canonical JSON, ``sha256:`` prefixed).
    """

    gait_version: str
    trace_witness: str
    probe_count: int
    active_count: int
    witness_hash: str = ""

    def __post_init__(self) -> None:
        payload = {
            "active_count": self.active_count,
            "gait_version": self.gait_version,
            "probe_count": self.probe_count,
            "trace_witness": self.trace_witness,
        }
        digest = "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":"), allow_nan=False).encode("utf-8")
        ).hexdigest()
        if self.witness_hash and self.witness_hash != digest:
            raise RuntimeCoreInvariantError("gait witness hash mismatch")
        object.__setattr__(self, "witness_hash", digest)


def seal(trace: GaitTrace) -> GaitWitness:
    """Produce the portable witness record for a planned trace."""
    return GaitWitness(
        gait_version=trace.gait_version,
        trace_witness=trace.witness(),
        probe_count=len(trace.probes),
        active_count=len(trace.active),
    )


# --- Capability Forge adapter ------------------------------------------------
#
# mcoi_runtime must not import the gateway layer (that inverts the dependency),
# so this returns the structured kwargs for gateway.capability_forge's
# CapabilityForgeInput. The caller in the gateway layer constructs and forges.


def to_forge_input(spec: GaitSpec, *, owner_team: str) -> dict[str, Any]:
    """Describe a gait as a side-effect-free, low-risk forge candidate."""
    if not isinstance(spec, GaitSpec):
        raise RuntimeCoreInvariantError("spec must be a GaitSpec")
    if not isinstance(owner_team, str) or not owner_team.strip():
        raise RuntimeCoreInvariantError("owner_team must be a non-empty string")
    return {
        "capability_id": f"interrogation.gait.{spec.phase.value}",
        "version": GAIT_VERSION,
        "domain": "meta_reasoning",
        "risk": "low",
        "side_effects": (),
        "api_docs_ref": "docs/17_meta_reasoning_plane.md",
        "input_schema_ref": "schemas/plan.schema.json",
        "output_schema_ref": "schemas/trace_entry.schema.json",
        "owner_team": owner_team.strip(),
        "secret_scope": "none",
        "requires_approval": False,
        "metadata": {
            "topology": spec.topology.value,
            "selection": spec.selection.value,
            "determinism": spec.determinism.value,
            "perspective": spec.perspective.value,
        },
    }
