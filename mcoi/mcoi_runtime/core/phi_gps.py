"""Φ_gps Runtime — Universal Problem Solver (Phases 0-1).

Purpose: Runtime implementation of Φ_gps Phase 0 (FRAME) and Phase 1
    (DISTINGUISH) from the canonical Φ specification (phi2-gps-v2.2).
    Bridges the formal specification to executable governance-aware code.

Schema: phi2-gps-v2.2
Governance scope: problem framing and symbol extraction only.
Dependencies: none (pure algorithm).
Invariants:
  - Profile vector is computed deterministically from problem state.
  - Ignorance map identifies unknowns × their impact.
  - Symbol extraction assigns confidence κ per symbol.
  - All outputs are immutable after computation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable


# ═══════════════════════════════════════════
# PROFILE VECTOR (§5.4 of spec)
# ═══════════════════════════════════════════

class KnowledgeLevel(StrEnum):
    KNOWN = "known"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class AgentMode(StrEnum):
    SINGLE = "single"
    COOPERATIVE = "cooperative"
    ADVERSARIAL = "adversarial"


class ResourceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class ProfileVector:
    """Problem profile vector χ(𝒫*) — classifies problem dimensions."""

    k_world: KnowledgeLevel      # World state knowledge
    k_goal: KnowledgeLevel       # Goal clarity
    k_laws: KnowledgeLevel       # Law/constraint knowledge
    k_actions: KnowledgeLevel    # Action repertoire
    k_transitions: KnowledgeLevel  # Transition model
    mode: AgentMode              # Single, cooperative, adversarial
    resource: ResourceLevel      # Resource pressure

    def to_dict(self) -> dict[str, str]:
        return {
            "k_world": self.k_world.value,
            "k_goal": self.k_goal.value,
            "k_laws": self.k_laws.value,
            "k_actions": self.k_actions.value,
            "k_transitions": self.k_transitions.value,
            "mode": self.mode.value,
            "resource": self.resource.value,
        }

    @property
    def unknowns(self) -> int:
        """Count of unknown dimensions."""
        return sum(
            1 for v in [self.k_world, self.k_goal, self.k_laws,
                        self.k_actions, self.k_transitions]
            if v == KnowledgeLevel.UNKNOWN
        )

    @property
    def dominance(self) -> str:
        """Which dimension is most unknown — drives phase routing."""
        dims = {
            "world": self.k_world,
            "goal": self.k_goal,
            "laws": self.k_laws,
            "actions": self.k_actions,
            "transitions": self.k_transitions,
        }
        unknowns = [k for k, v in dims.items() if v == KnowledgeLevel.UNKNOWN]
        if unknowns:
            return unknowns[0]
        partials = [k for k, v in dims.items() if v == KnowledgeLevel.PARTIAL]
        if partials:
            return partials[0]
        return "none"


# ═══════════════════════════════════════════
# IGNORANCE MAP (Phase 0 output)
# ═══════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class IgnoranceEntry:
    """A single unknown in the ignorance map."""

    dimension: str      # What is unknown
    impact: str         # How much it matters: "critical", "significant", "minor"
    resolution: str     # How to resolve: "observe", "query", "test", "assume"
    confidence: float   # Current confidence in best guess (0.0-1.0)


@dataclass(frozen=True, slots=True)
class IgnoranceMap:
    """Maps unknowns to their impact and resolution strategy."""

    entries: tuple[IgnoranceEntry, ...]

    @property
    def critical_unknowns(self) -> int:
        return sum(1 for e in self.entries if e.impact == "critical")

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": [
                {"dimension": e.dimension, "impact": e.impact,
                 "resolution": e.resolution, "confidence": e.confidence}
                for e in self.entries
            ],
            "critical_unknowns": self.critical_unknowns,
        }


# ═══════════════════════════════════════════
# PHASE 0 — FRAME
# ═══════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class FrameResult:
    """Output of Phase 0 (FRAME)."""

    profile: ProfileVector
    ignorance: IgnoranceMap
    resource_envelope: dict[str, Any]
    recommended_phases: tuple[str, ...]  # Phase sequence to follow

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "ignorance": self.ignorance.to_dict(),
            "resource_envelope": self.resource_envelope,
            "recommended_phases": list(self.recommended_phases),
        }


def frame_problem(
    *,
    world_known: bool = False,
    world_partial: bool = False,
    goal_known: bool = False,
    goal_partial: bool = False,
    laws_known: bool = False,
    actions_known: bool = False,
    transitions_known: bool = False,
    multi_agent: bool = False,
    adversarial: bool = False,
    resource_pressure: str = "medium",
    context: dict[str, Any] | None = None,
) -> FrameResult:
    """Phase 0 — FRAME: Profile the problem and build ignorance map.

    This is the entry point to Φ_gps. It classifies the problem along
    5 knowledge dimensions, identifies unknowns, and recommends a
    phase sequence for solving.
    """
    # 1. Classify knowledge dimensions
    k_world = (KnowledgeLevel.KNOWN if world_known
               else KnowledgeLevel.PARTIAL if world_partial
               else KnowledgeLevel.UNKNOWN)
    k_goal = (KnowledgeLevel.KNOWN if goal_known
              else KnowledgeLevel.PARTIAL if goal_partial
              else KnowledgeLevel.UNKNOWN)
    k_laws = KnowledgeLevel.KNOWN if laws_known else KnowledgeLevel.PARTIAL
    k_actions = KnowledgeLevel.KNOWN if actions_known else KnowledgeLevel.PARTIAL
    k_transitions = KnowledgeLevel.KNOWN if transitions_known else KnowledgeLevel.UNKNOWN

    mode = (AgentMode.ADVERSARIAL if adversarial
            else AgentMode.COOPERATIVE if multi_agent
            else AgentMode.SINGLE)
    resource = ResourceLevel(resource_pressure) if resource_pressure in ("low", "medium", "critical") else ResourceLevel.MEDIUM

    profile = ProfileVector(
        k_world=k_world, k_goal=k_goal, k_laws=k_laws,
        k_actions=k_actions, k_transitions=k_transitions,
        mode=mode, resource=resource,
    )

    # 2. Build ignorance map
    ignorance_entries: list[IgnoranceEntry] = []
    if k_world == KnowledgeLevel.UNKNOWN:
        ignorance_entries.append(IgnoranceEntry("world_state", "critical", "observe", 0.0))
    elif k_world == KnowledgeLevel.PARTIAL:
        ignorance_entries.append(IgnoranceEntry("world_state", "significant", "observe", 0.5))

    if k_goal == KnowledgeLevel.UNKNOWN:
        ignorance_entries.append(IgnoranceEntry("goal", "critical", "query", 0.0))
    elif k_goal == KnowledgeLevel.PARTIAL:
        ignorance_entries.append(IgnoranceEntry("goal", "significant", "query", 0.5))

    if k_transitions == KnowledgeLevel.UNKNOWN:
        ignorance_entries.append(IgnoranceEntry("transitions", "significant", "test", 0.1))

    if k_actions == KnowledgeLevel.PARTIAL:
        ignorance_entries.append(IgnoranceEntry("actions", "minor", "assume", 0.6))

    ignorance = IgnoranceMap(entries=tuple(ignorance_entries))

    # 3. Resource envelope
    resource_envelope = {
        "pressure": resource.value,
        "max_phases": 13 if resource != ResourceLevel.CRITICAL else 5,
        "max_reentries": 3 if resource != ResourceLevel.CRITICAL else 1,
    }

    # 4. Recommend phase sequence based on profile
    phases = _recommend_phases(profile)

    return FrameResult(
        profile=profile, ignorance=ignorance,
        resource_envelope=resource_envelope,
        recommended_phases=tuple(phases),
    )


def _recommend_phases(profile: ProfileVector) -> list[str]:
    """Select phase sequence based on problem profile."""
    phases = ["phase_0_frame"]

    # Always distinguish first
    phases.append("phase_1_distinguish")

    # If world unknown, estimate belief early
    if profile.k_world != KnowledgeLevel.KNOWN:
        phases.append("phase_2_estimate_belief")

    # Goal construction
    phases.append("phase_3_goal_utility")

    # Law/norm discovery
    if profile.k_laws != KnowledgeLevel.KNOWN:
        phases.append("phase_4_discover_laws")

    phases.append("phase_4_5_freeze_models")

    # Transitions
    if profile.k_transitions != KnowledgeLevel.KNOWN:
        phases.append("phase_5_transitions")

    # Action synthesis
    phases.append("phase_6_actions")

    # Feasibility
    phases.append("phase_7_feasibility")
    phases.append("phase_7_5_proof_sketch")

    # Decomposition + policy
    phases.append("phase_8_decompose")
    phases.append("phase_9_policy")

    # Execute
    phases.append("phase_10_execute")

    # Diagnose if resource allows
    if profile.resource != ResourceLevel.CRITICAL:
        phases.append("phase_11_diagnose")

    # Verify
    phases.append("phase_12_verify")
    phases.append("phase_12_5_calibrate")

    return phases


# ═══════════════════════════════════════════
# PHASE 1 — DISTINGUISH
# ═══════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class Symbol:
    """An extracted symbol with confidence."""

    name: str
    kind: str           # "entity", "property", "relation", "boundary", "action"
    confidence: float   # κ ∈ [0, 1]
    source: str = ""    # Where this was extracted from
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DistinguishResult:
    """Output of Phase 1 (DISTINGUISH)."""

    symbols: tuple[Symbol, ...]
    low_confidence_count: int  # Symbols below κ_min
    epistemic_actions_needed: tuple[str, ...]  # Actions to resolve low-κ symbols

    @property
    def symbol_count(self) -> int:
        return len(self.symbols)

    def symbols_by_kind(self, kind: str) -> tuple[Symbol, ...]:
        return tuple(s for s in self.symbols if s.kind == kind)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbols": [
                {"name": s.name, "kind": s.kind, "confidence": s.confidence}
                for s in self.symbols
            ],
            "low_confidence_count": self.low_confidence_count,
            "epistemic_actions": list(self.epistemic_actions_needed),
        }


def distinguish(
    text: str,
    *,
    kappa_min: float = 0.5,
    context: dict[str, Any] | None = None,
) -> DistinguishResult:
    """Phase 1 — DISTINGUISH: Extract symbols from text with confidence.

    Identifies entities, properties, relations, boundaries, and actions
    from the problem description. Each symbol gets a confidence κ.
    Symbols below κ_min trigger epistemic action recommendations.
    """
    symbols: list[Symbol] = []
    words = text.split()

    # Entity extraction (nouns / capitalized words)
    seen: set[str] = set()
    for word in words:
        clean = word.strip(".,;:!?()[]{}\"'")
        if not clean or clean.lower() in seen:
            continue
        lower = clean.lower()

        # High confidence: capitalized proper nouns
        if clean[0].isupper() and len(clean) > 1 and not clean.isupper():
            symbols.append(Symbol(name=clean, kind="entity", confidence=0.8, source="capitalization"))
            seen.add(lower)
            continue

        # Medium confidence: domain keywords
        if lower in _ACTION_WORDS:
            symbols.append(Symbol(name=lower, kind="action", confidence=0.7, source="keyword"))
            seen.add(lower)
        elif lower in _RELATION_WORDS:
            symbols.append(Symbol(name=lower, kind="relation", confidence=0.6, source="keyword"))
            seen.add(lower)
        elif lower in _PROPERTY_WORDS:
            symbols.append(Symbol(name=lower, kind="property", confidence=0.6, source="keyword"))
            seen.add(lower)
        elif lower in _BOUNDARY_WORDS:
            symbols.append(Symbol(name=lower, kind="boundary", confidence=0.7, source="keyword"))
            seen.add(lower)

    # Identify low-confidence symbols
    low_confidence = [s for s in symbols if s.confidence < kappa_min]
    epistemic_actions = []
    for s in low_confidence:
        if s.kind == "entity":
            epistemic_actions.append(f"query: clarify entity '{s.name}'")
        elif s.kind == "relation":
            epistemic_actions.append(f"observe: verify relation '{s.name}'")
        else:
            epistemic_actions.append(f"test: validate '{s.name}'")

    return DistinguishResult(
        symbols=tuple(symbols),
        low_confidence_count=len(low_confidence),
        epistemic_actions_needed=tuple(epistemic_actions),
    )


# ═══════════════════════════════════════════
# STRATEGY SELECTION (§5.4 of spec)
# ═══════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class StrategyScore:
    """Scored strategy for the problem profile."""

    name: str
    score: float
    compatible_dimensions: int
    incompatible_dimensions: int


STRATEGIES = [
    "exhaustive_search", "heuristic_search", "plan_observe_replan",
    "constraint_satisfaction", "survival_first", "game_theoretic",
    "norm_negotiation", "anytime_greedy",
]

_STRATEGY_COMPAT: dict[str, dict[str, int]] = {
    "exhaustive_search": {"k_world": 1, "k_transitions": 1, "resource": -1},
    "heuristic_search": {"k_world": 0, "k_goal": 1, "resource": 1},
    "plan_observe_replan": {"k_world": -1, "k_transitions": 0, "resource": 0},
    "constraint_satisfaction": {"k_laws": 1, "k_goal": 1, "resource": 0},
    "survival_first": {"resource": 1, "k_world": -1, "mode": -1},
    "game_theoretic": {"mode": 1, "k_world": 0, "resource": -1},
    "norm_negotiation": {"mode": 1, "k_laws": 0, "resource": 0},
    "anytime_greedy": {"resource": 1, "k_goal": 0, "k_world": 0},
}


def select_strategies(profile: ProfileVector, *, top_k: int = 3) -> list[StrategyScore]:
    """Select top-k strategies for the problem profile (§5.4).

    Scores each strategy by compatibility with the profile dimensions.
    """
    scored: list[StrategyScore] = []
    for name, compat in _STRATEGY_COMPAT.items():
        total = 0
        pos = 0
        neg = 0
        for dim, val in compat.items():
            total += val
            if val > 0:
                pos += 1
            elif val < 0:
                neg += 1
        scored.append(StrategyScore(name=name, score=total, compatible_dimensions=pos, incompatible_dimensions=neg))

    scored.sort(key=lambda s: -s.score)
    if profile.resource == ResourceLevel.CRITICAL:
        return scored[:1]  # Only top strategy under critical pressure
    return scored[:top_k]


# ═══════════════════════════════════════════
# KEYWORD SETS (for Phase 1 extraction)
# ═══════════════════════════════════════════

_ACTION_WORDS = frozenset({
    "create", "delete", "update", "send", "receive", "compute",
    "calculate", "transform", "allocate", "commit", "deploy",
    "build", "generate", "analyze", "optimize", "validate",
    "transfer", "process", "execute", "schedule", "notify",
})

_RELATION_WORDS = frozenset({
    "between", "connects", "causes", "requires", "depends",
    "contains", "belongs", "affects", "influences", "relates",
    "precedes", "follows", "enables", "blocks", "triggers",
})

_PROPERTY_WORDS = frozenset({
    "amount", "count", "rate", "size", "weight", "duration",
    "cost", "price", "score", "percentage", "threshold",
    "capacity", "limit", "maximum", "minimum", "average",
})

_BOUNDARY_WORDS = frozenset({
    "limit", "boundary", "constraint", "deadline", "budget",
    "threshold", "cap", "floor", "maximum", "minimum",
    "timeout", "restriction", "requirement", "condition",
})
