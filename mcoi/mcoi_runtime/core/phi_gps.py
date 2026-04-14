"""Φ_gps Runtime — Universal Problem Solver (Phases 0-12).

Purpose: Runtime implementation of Φ_gps Phases 0-12 from the canonical
    Φ specification (phi2-gps-v2.2).  Bridges the formal specification
    to executable governance-aware code.

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

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable

__all__ = [
    # Phase 0
    "KnowledgeLevel", "ResourceLevel", "ProfileVector", "IgnoranceEntry",
    "IgnoranceMap", "FrameResult", "frame_problem",
    # Phase 1
    "Symbol", "DistinguishResult", "distinguish",
    # Phase 2
    "BeliefVariable", "BeliefState", "VoIEstimate", "estimate_belief", "compute_voi",
    # Phase 3
    "GoalStatus", "GoalRegion", "SafetyFloor", "UtilityStructure",
    "GoalConstructionResult", "construct_goal",
    # Phase 4
    "LawType", "NormKind", "DiscoveredLaw", "DiscoveredNorm",
    "LawDiscoveryResult", "discover_laws",
    # Phase 4.5
    "ModelStatus", "EpisodeModelSet", "freeze_models",
    # Phase 5
    "TransitionMap", "discover_transitions",
    # Phase 6
    "ActionSet", "synthesize_actions",
    # Phase 7
    "InvariantGrade", "Invariant", "FeasibilityResult", "check_feasibility",
    # Phase 7.5
    "ProofState", "ProofSketch", "build_proof_sketch",
    # Phase 8
    "DecompositionResult", "decompose_problem",
    # Phase 9
    "PolicyResult", "select_policy",
    # Phase 10
    "ExecutionStep", "ExecutionTrace", "execute_plan",
    # Phase 11
    "DiagnosisResult", "diagnose_failure",
    # Phase 12
    "Verification", "SolverOutcome", "SolverOutput", "verify_and_judge",
    # Utilities
    "AgentMode", "StrategyScore", "select_strategies",
]


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


# ═══════════════════════════════════════════
# PHASE 2 — ESTIMATE BELIEF
# ═══════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class BeliefVariable:
    """A single variable in the belief state."""

    name: str
    observability: str  # "observable", "noisy", "hidden"
    value: Any = None
    confidence: float = 0.5
    source: str = ""  # "observed", "inferred", "prior", "assumed"


@dataclass(frozen=True, slots=True)
class BeliefState:
    """Estimated belief about the world state B̂ = P(W | observations, K).

    Separates what is known (observed) from what is inferred (estimated)
    from what is unknown (prior/assumed).
    """

    variables: tuple[BeliefVariable, ...]
    overall_confidence: float  # Weighted average confidence
    entropy: float  # Information entropy (higher = more uncertain)
    observation_count: int

    @property
    def observed_count(self) -> int:
        return sum(1 for v in self.variables if v.source == "observed")

    @property
    def hidden_count(self) -> int:
        return sum(1 for v in self.variables if v.observability == "hidden")

    def get(self, name: str) -> BeliefVariable | None:
        for v in self.variables:
            if v.name == name:
                return v
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "variables": [
                {"name": v.name, "observability": v.observability,
                 "confidence": v.confidence, "source": v.source}
                for v in self.variables
            ],
            "overall_confidence": round(self.overall_confidence, 3),
            "entropy": round(self.entropy, 3),
            "observed": self.observed_count,
            "hidden": self.hidden_count,
        }


@dataclass(frozen=True, slots=True)
class VoIEstimate:
    """Value of Information estimate for a query."""

    query: str
    estimated_entropy_reduction: float
    cost: float = 0.0
    priority: float = 0.0  # Higher = more valuable to ask


def estimate_belief(
    observations: dict[str, Any],
    *,
    prior_knowledge: dict[str, Any] | None = None,
    hidden_variables: list[str] | None = None,
) -> BeliefState:
    """Phase 2 — ESTIMATE BELIEF: Build belief state from observations.

    Classifies each variable as observable/noisy/hidden, assigns
    confidence based on source, and computes overall belief entropy.
    """
    import math

    prior = prior_knowledge or {}
    hidden = set(hidden_variables or [])
    variables: list[BeliefVariable] = []

    # Observed variables (high confidence)
    for name, value in observations.items():
        variables.append(BeliefVariable(
            name=name, observability="observable",
            value=value, confidence=0.9, source="observed",
        ))

    # Prior knowledge (medium confidence)
    for name, value in prior.items():
        if name not in observations:
            obs = "hidden" if name in hidden else "noisy"
            variables.append(BeliefVariable(
                name=name, observability=obs,
                value=value, confidence=0.5, source="prior",
            ))

    # Hidden variables (low confidence)
    for name in hidden:
        if name not in observations and name not in prior:
            variables.append(BeliefVariable(
                name=name, observability="hidden",
                value=None, confidence=0.1, source="assumed",
            ))

    # Compute overall confidence and entropy
    if variables:
        confidences = [v.confidence for v in variables]
        overall = sum(confidences) / len(confidences)
        # Shannon entropy: H = -Σ p·log(p)
        entropy = -sum(
            c * math.log(max(c, 1e-10)) + (1 - c) * math.log(max(1 - c, 1e-10))
            for c in confidences
        ) / len(confidences)
    else:
        overall = 0.0
        entropy = 0.0

    return BeliefState(
        variables=tuple(variables),
        overall_confidence=overall,
        entropy=entropy,
        observation_count=len(observations),
    )


def compute_voi(
    belief: BeliefState,
    candidate_queries: list[str],
) -> list[VoIEstimate]:
    """Compute Value of Information for candidate queries.

    Myopic VoI: estimates entropy reduction if the query is answered.
    Higher priority = ask this question first.
    """
    estimates: list[VoIEstimate] = []
    for query in candidate_queries:
        # Find the variable this query would resolve
        target = belief.get(query)
        if target is not None and target.confidence < 0.8:
            reduction = (0.9 - target.confidence) * 0.5  # Expected entropy reduction
            priority = reduction / max(0.01, 1.0)  # Normalize
        else:
            reduction = 0.1
            priority = 0.1
        estimates.append(VoIEstimate(
            query=query,
            estimated_entropy_reduction=round(reduction, 3),
            priority=round(priority, 3),
        ))
    estimates.sort(key=lambda e: -e.priority)
    return estimates


# ═══════════════════════════════════════════
# PHASE 3 — GOAL + UTILITY
# ═══════════════════════════════════════════

class GoalStatus(StrEnum):
    CRISP = "crisp"           # Goal is clearly defined
    FUZZY = "fuzzy"           # Goal has imprecise boundaries
    ABSENT = "absent"         # No goal specified
    CONTRADICTORY = "contradictory"  # Multiple conflicting goals


@dataclass(frozen=True, slots=True)
class SafetyFloor:
    """Minimum acceptable state — violation triggers immediate halt."""

    description: str
    variables: tuple[str, ...]  # Variables that must stay within bounds
    severity: str = "critical"  # "critical" = halt, "warning" = alert


@dataclass(frozen=True, slots=True)
class GoalRegion:
    """The satisfying set for the goal (not a single point)."""

    description: str
    satisfaction_criteria: dict[str, Any]
    gamma_goal: float = 0.8  # P(satisfied | B_t) threshold


@dataclass(frozen=True, slots=True)
class UtilityStructure:
    """Four-layer utility structure (§5.3 of spec).

    Priority: safety_floor > goal_satisfaction > optimization > satisficing
    """

    safety_floor: SafetyFloor
    goal: GoalRegion
    optimization_preferences: tuple[str, ...] = ()  # Preference ordering within goal
    satisficing_threshold: float = 0.7  # "Good enough" threshold

    def to_dict(self) -> dict[str, Any]:
        return {
            "safety_floor": {
                "description": self.safety_floor.description,
                "variables": list(self.safety_floor.variables),
                "severity": self.safety_floor.severity,
            },
            "goal": {
                "description": self.goal.description,
                "gamma_goal": self.goal.gamma_goal,
                "criteria": self.goal.satisfaction_criteria,
            },
            "optimization": list(self.optimization_preferences),
            "satisficing_threshold": self.satisficing_threshold,
        }


@dataclass(frozen=True, slots=True)
class GoalConstructionResult:
    """Output of Phase 3 (GOAL + UTILITY)."""

    goal_status: GoalStatus
    utility: UtilityStructure
    tradeoffs: tuple[str, ...] = ()  # Recorded tradeoffs if goal was contradictory

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_status": self.goal_status.value,
            "utility": self.utility.to_dict(),
            "tradeoffs": list(self.tradeoffs),
        }


def construct_goal(
    *,
    description: str = "",
    safety_variables: list[str] | None = None,
    satisfaction_criteria: dict[str, Any] | None = None,
    optimization_preferences: list[str] | None = None,
    contradictions: list[str] | None = None,
    gamma_goal: float = 0.8,
    satisficing: float = 0.7,
) -> GoalConstructionResult:
    """Phase 3 — CONSTRUCT GOAL + UTILITY.

    Builds the four-layer utility structure from goal description,
    safety constraints, satisfaction criteria, and preferences.
    """
    # Classify goal status
    if contradictions:
        status = GoalStatus.CONTRADICTORY
    elif not description and not satisfaction_criteria:
        status = GoalStatus.ABSENT
    elif satisfaction_criteria:
        status = GoalStatus.CRISP
    else:
        status = GoalStatus.FUZZY

    # Safety floor
    safety = SafetyFloor(
        description="System safety constraints",
        variables=tuple(safety_variables or []),
    )

    # Goal region
    goal = GoalRegion(
        description=description or "No explicit goal",
        satisfaction_criteria=satisfaction_criteria or {},
        gamma_goal=gamma_goal,
    )

    # Build utility structure
    utility = UtilityStructure(
        safety_floor=safety,
        goal=goal,
        optimization_preferences=tuple(optimization_preferences or []),
        satisficing_threshold=satisficing,
    )

    # Record tradeoffs for contradictory goals
    tradeoffs: list[str] = []
    if contradictions:
        for c in contradictions:
            tradeoffs.append(f"tradeoff: {c}")

    return GoalConstructionResult(
        goal_status=status,
        utility=utility,
        tradeoffs=tuple(tradeoffs),
    )


# ═══════════════════════════════════════════
# PHASE 4 — DISCOVER LAWS + NORMS
# ═══════════════════════════════════════════

class LawType(StrEnum):
    PHYSICAL = "physical"
    LOGICAL = "logical"
    MATHEMATICAL = "mathematical"


class NormKind(StrEnum):
    PERMISSION = "permission"
    PROHIBITION = "prohibition"
    SOCIAL = "social_expectation"
    GOVERNANCE = "governance_rule"


@dataclass(frozen=True, slots=True)
class DiscoveredLaw:
    """A hard law discovered during problem analysis."""

    name: str
    law_type: LawType
    description: str
    confidence: float  # κ ∈ [0, 1]
    falsification_condition: str = ""


@dataclass(frozen=True, slots=True)
class DiscoveredNorm:
    """A norm governing agent behavior."""

    name: str
    kind: NormKind
    description: str
    authority_level: int = 10  # 0 = highest (USCL/Φ_gov), 10 = default
    scope: str = "global"
    conflict_resolution: str = "escalate"  # "prohibitive", "permissive", "escalate"


@dataclass(frozen=True, slots=True)
class LawDiscoveryResult:
    """Output of Phase 4."""

    laws: tuple[DiscoveredLaw, ...]
    norms: tuple[DiscoveredNorm, ...]
    resource_constraints: dict[str, Any]

    @property
    def hard_law_count(self) -> int:
        return sum(1 for l in self.laws if l.confidence >= 0.95)

    def to_dict(self) -> dict[str, Any]:
        return {
            "laws": [{"name": l.name, "type": l.law_type.value,
                      "confidence": l.confidence} for l in self.laws],
            "norms": [{"name": n.name, "kind": n.kind.value,
                       "authority": n.authority_level} for n in self.norms],
            "resources": self.resource_constraints,
            "hard_laws": self.hard_law_count,
        }


def discover_laws(
    *,
    domain: str = "",
    constraints: list[str] | None = None,
    permissions: list[str] | None = None,
    prohibitions: list[str] | None = None,
    resource_limits: dict[str, Any] | None = None,
) -> LawDiscoveryResult:
    """Phase 4 — DISCOVER LAWS + NORMS + RESOURCES.

    Identifies hard laws (physical/logical/mathematical impossibilities),
    norms (permissions, prohibitions, social expectations), and resource
    constraints that bound the solution space.
    """
    laws: list[DiscoveredLaw] = []
    norms: list[DiscoveredNorm] = []

    # Domain-specific hard laws
    if domain:
        laws.append(DiscoveredLaw(
            name="domain_boundary",
            law_type=LawType.LOGICAL,
            description="Solution must operate within specified domain",
            confidence=1.0,
        ))

    # User-specified constraints become laws
    for idx, c in enumerate(constraints or []):
        laws.append(DiscoveredLaw(
            name="constraint_{}".format(idx),
            law_type=LawType.LOGICAL,
            description=c,
            confidence=0.95,
            falsification_condition="constraint violation",
        ))

    # Universal governance laws (always present)
    laws.append(DiscoveredLaw(
        name="identity_preservation",
        law_type=LawType.LOGICAL,
        description="System identity invariants must be preserved",
        confidence=1.0,
    ))
    laws.append(DiscoveredLaw(
        name="audit_completeness",
        law_type=LawType.LOGICAL,
        description="Every state change must be audited",
        confidence=1.0,
    ))

    # Permissions → norms
    for idx, p in enumerate(permissions or []):
        norms.append(DiscoveredNorm(
            name="permit_{}".format(idx),
            kind=NormKind.PERMISSION,
            description=p,
            conflict_resolution="permissive",
        ))

    # Prohibitions → norms (higher authority)
    for idx, p in enumerate(prohibitions or []):
        norms.append(DiscoveredNorm(
            name="prohibit_{}".format(idx),
            kind=NormKind.PROHIBITION,
            description=p,
            authority_level=2,
            conflict_resolution="prohibitive",
        ))

    # Governance norms (always present)
    norms.append(DiscoveredNorm(
        name="governance_authority",
        kind=NormKind.GOVERNANCE,
        description="All state writes require Φ_gov authority",
        authority_level=0,
        conflict_resolution="prohibitive",
    ))

    return LawDiscoveryResult(
        laws=tuple(laws),
        norms=tuple(norms),
        resource_constraints=resource_limits or {},
    )


# ═══════════════════════════════════════════
# PHASE 4.5 — APPROVE + FREEZE MODELS
# ═══════════════════════════════════════════

class ModelStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    FROZEN = "frozen"
    DEPRECATED = "deprecated"
    QUARANTINED = "quarantined"


@dataclass(frozen=True, slots=True)
class EpisodeModelSet:
    """Frozen model set for an execution episode (§5.8 of spec).

    Once frozen, execution uses ONLY these models. Proposed changes
    accumulate as ΔM but are NEVER applied during the episode.
    They are reviewed by Φ_gov after Phase 12 verification.
    """

    model_id: str
    laws: tuple[DiscoveredLaw, ...]
    norms: tuple[DiscoveredNorm, ...]
    belief: Any  # BeliefState from Phase 2
    goal: Any  # GoalConstructionResult from Phase 3
    status: ModelStatus
    frozen_at: str = ""
    approved_by: str = ""

    @property
    def is_frozen(self) -> bool:
        return self.status == ModelStatus.FROZEN

    @property
    def law_count(self) -> int:
        return len(self.laws)

    @property
    def norm_count(self) -> int:
        return len(self.norms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "status": self.status.value,
            "laws": self.law_count,
            "norms": self.norm_count,
            "frozen_at": self.frozen_at,
            "approved_by": self.approved_by,
            "is_frozen": self.is_frozen,
        }


def freeze_models(
    *,
    laws: LawDiscoveryResult,
    belief: Any,
    goal: Any,
    approver: str = "phi_gov",
    clock: Any = None,
) -> EpisodeModelSet:
    """Phase 4.5 — APPROVE + FREEZE MODELS.

    Creates an immutable EpisodeModelSet from the outputs of Phases 2-4.
    Once frozen, execution uses ONLY these models. Changes accumulate
    as proposals, reviewed post-episode by Φ_gov.
    """
    import hashlib
    now = clock() if clock else ""
    model_id = f"model-{hashlib.sha256(f'{now}:{len(laws.laws)}'.encode()).hexdigest()[:12]}"

    return EpisodeModelSet(
        model_id=model_id,
        laws=laws.laws,
        norms=laws.norms,
        belief=belief,
        goal=goal,
        status=ModelStatus.FROZEN,
        frozen_at=now,
        approved_by=approver,
    )


# ═══════════════════════════════════════════
# PHASE 5 — TRANSITIONS (structural placeholder)
# ═══════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class TransitionMap:
    """Output of Phase 5 (TRANSITIONS)."""

    transitions: tuple[dict[str, Any], ...]
    state_space_size: int = 0


def discover_transitions(
    *,
    model: EpisodeModelSet,
    observation_data: list[dict[str, Any]] | None = None,
) -> TransitionMap:
    """Phase 5 — DISCOVER STATE TRANSITIONS.

    Identifies how the world changes: state-action-state triples,
    transition probabilities, and reachability from the current state.

    Status: structural stub — returns identity transitions from model laws.
    """
    transitions: list[dict[str, Any]] = []
    for law in model.laws:
        transitions.append({
            "source": law.description,
            "action": "observe",
            "target": law.description,
            "probability": law.confidence,
        })
    return TransitionMap(
        transitions=tuple(transitions),
        state_space_size=len(transitions),
    )


# ═══════════════════════════════════════════
# PHASE 6 — ACTIONS (structural placeholder)
# ═══════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class ActionSet:
    """Output of Phase 6 (ACTIONS)."""

    actions: tuple[dict[str, Any], ...]
    primitive_count: int = 0
    composite_count: int = 0


def synthesize_actions(
    *,
    model: EpisodeModelSet,
    transitions: TransitionMap | None = None,
) -> ActionSet:
    """Phase 6 — SYNTHESIZE ACTIONS.

    Constructs the action repertoire: primitives (single-step),
    composites (macro-actions), and precondition/effect annotations.

    Status: structural stub — extracts actions from norms and laws.
    """
    actions: list[dict[str, Any]] = []
    for norm in (model.norms or ()):
        actions.append({
            "name": f"comply_{norm.description[:30]}",
            "kind": "primitive",
            "precondition": f"authority_level<={norm.authority_level}",
            "effect": norm.description,
        })
    return ActionSet(
        actions=tuple(actions),
        primitive_count=len(actions),
        composite_count=0,
    )


# ═══════════════════════════════════════════
# PHASE 7 — FEASIBILITY + INVARIANTS
# ═══════════════════════════════════════════

class InvariantGrade(StrEnum):
    HARD = "hard"           # confidence ≥ 0.95, n_observed ≥ 20
    SOFT = "soft"           # tolerance band
    CANDIDATE = "candidate" # not trusted for solvability gate


@dataclass(frozen=True, slots=True)
class Invariant:
    """A discovered invariant of the problem."""

    name: str
    grade: InvariantGrade
    description: str
    confidence: float
    current_value: Any = None
    goal_value: Any = None
    satisfied: bool = True


@dataclass(frozen=True, slots=True)
class FeasibilityResult:
    """Output of Phase 7 (FEASIBILITY)."""

    feasible: bool
    invariants: tuple[Invariant, ...]
    hard_violations: tuple[str, ...]  # Names of hard invariants that block
    soft_warnings: tuple[str, ...]    # Names of soft invariants drifting
    solvability: str  # "feasible", "infeasible", "unknown"

    @property
    def hard_count(self) -> int:
        return sum(1 for i in self.invariants if i.grade == InvariantGrade.HARD)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feasible": self.feasible,
            "solvability": self.solvability,
            "invariants": [{"name": i.name, "grade": i.grade.value,
                            "satisfied": i.satisfied, "confidence": i.confidence}
                           for i in self.invariants],
            "hard_violations": list(self.hard_violations),
            "soft_warnings": list(self.soft_warnings),
        }


def check_feasibility(
    *,
    model: EpisodeModelSet,
    current_state: dict[str, Any] | None = None,
    goal_state: dict[str, Any] | None = None,
    invariant_specs: list[dict[str, Any]] | None = None,
) -> FeasibilityResult:
    """Phase 7 — FEASIBILITY + INVARIANTS.

    Discovers invariants from the frozen model, classifies them by grade,
    and runs the solvability gate: if ANY Hard invariant is violated
    between current state and goal, the problem is PROVABLY UNREACHABLE.
    """
    current = current_state or {}
    goal = goal_state or {}
    invariants: list[Invariant] = []
    hard_violations: list[str] = []
    soft_warnings: list[str] = []

    # Extract invariants from laws
    for law in model.laws:
        grade = InvariantGrade.HARD if law.confidence >= 0.95 else InvariantGrade.SOFT
        invariants.append(Invariant(
            name=law.name, grade=grade,
            description=law.description,
            confidence=law.confidence,
            satisfied=True,  # Laws are structural — always satisfied by definition
        ))

    # User-specified invariant checks
    for spec in (invariant_specs or []):
        name = spec.get("name", "unknown")
        grade_str = spec.get("grade", "candidate")
        grade = InvariantGrade(grade_str) if grade_str in ("hard", "soft", "candidate") else InvariantGrade.CANDIDATE

        current_val = current.get(name)
        goal_val = goal.get(name)
        satisfied = True

        if current_val is not None and goal_val is not None:
            satisfied = (current_val == goal_val) or spec.get("reachable", True)

        confidence = float(spec.get("confidence", 0.5))
        if confidence >= 0.95 and spec.get("n_observed", 0) >= 20:
            grade = InvariantGrade.HARD

        invariant = Invariant(
            name=name, grade=grade, description=spec.get("description", ""),
            confidence=confidence, current_value=current_val,
            goal_value=goal_val, satisfied=satisfied,
        )
        invariants.append(invariant)

        # SOLVABILITY GATE: Hard invariant violation = PROVABLY UNREACHABLE
        if grade == InvariantGrade.HARD and not satisfied:
            hard_violations.append(name)
        elif grade == InvariantGrade.SOFT and not satisfied:
            soft_warnings.append(name)

    feasible = len(hard_violations) == 0
    solvability = "feasible" if feasible else "infeasible"
    if not feasible:
        solvability = "infeasible"
    elif soft_warnings:
        solvability = "feasible"  # Soft violations don't block

    return FeasibilityResult(
        feasible=feasible,
        invariants=tuple(invariants),
        hard_violations=tuple(hard_violations),
        soft_warnings=tuple(soft_warnings),
        solvability=solvability,
    )


# ═══════════════════════════════════════════
# PHASE 7.5 — FORWARD PROOF SKETCH
# ═══════════════════════════════════════════

class ProofState(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    BUDGET_UNKNOWN = "budget_unknown"


@dataclass(frozen=True, slots=True)
class ProofSketch:
    """Forward proof sketch for a sub-goal (§5.6 of spec)."""

    sub_goal: str
    pi_goal: ProofState       # Reachability witness
    pi_law: ProofState        # No hard law blocks required actions
    pi_norm: ProofState       # Required actions are norm-permitted
    pi_side_effect: ProofState  # Estimated damage within bounds

    @property
    def is_verified(self) -> bool:
        return all(p == ProofState.PASS for p in
                   (self.pi_goal, self.pi_law, self.pi_norm, self.pi_side_effect))

    @property
    def has_unknown(self) -> bool:
        return any(p in (ProofState.UNKNOWN, ProofState.BUDGET_UNKNOWN)
                   for p in (self.pi_goal, self.pi_law, self.pi_norm, self.pi_side_effect))

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub_goal": self.sub_goal,
            "pi_goal": self.pi_goal.value,
            "pi_law": self.pi_law.value,
            "pi_norm": self.pi_norm.value,
            "pi_side_effect": self.pi_side_effect.value,
            "verified": self.is_verified,
            "has_unknown": self.has_unknown,
        }


def build_proof_sketch(
    *,
    sub_goal: str,
    feasibility: FeasibilityResult,
    model: EpisodeModelSet,
) -> ProofSketch:
    """Phase 7.5 — FORWARD PROOF SKETCH.

    Builds a proof sketch for a sub-goal based on feasibility results
    and the frozen model. Hard constraint failures → FAIL.
    Unknown on hard constraints → UNKNOWN (action BLOCKED).
    """
    # Goal reachability
    pi_goal = ProofState.PASS if feasibility.feasible else ProofState.FAIL

    # Law compliance
    if feasibility.hard_violations:
        pi_law = ProofState.FAIL
    elif feasibility.soft_warnings:
        pi_law = ProofState.PASS  # Soft violations don't block
    else:
        pi_law = ProofState.PASS

    # Norm compliance (check against model norms)
    prohibitions = [n for n in model.norms if n.kind == NormKind.PROHIBITION]
    pi_norm = ProofState.PASS if not prohibitions else ProofState.UNKNOWN

    # Side effects (conservative: unknown unless explicitly checked)
    pi_side = ProofState.UNKNOWN

    return ProofSketch(
        sub_goal=sub_goal,
        pi_goal=pi_goal,
        pi_law=pi_law,
        pi_norm=pi_norm,
        pi_side_effect=pi_side,
    )


# ═══════════════════════════════════════════
# SOLVER OUTCOME (§5.10 of spec)
# ═══════════════════════════════════════════

class SolverOutcome(StrEnum):
    SOLVED_VERIFIED = "solved_verified"
    SOLVED_UNVERIFIED = "solved_unverified"
    AWAITING_EVIDENCE = "awaiting_evidence"
    SAFE_HALT = "safe_halt"
    GOVERNANCE_BLOCKED = "governance_blocked"
    BUDGET_EXHAUSTED = "budget_exhausted"
    IMPOSSIBLE_PROVED = "impossible_proved"
    MODEL_INVALIDATED = "model_invalidated"


# ═══════════════════════════════════════════
# PHASE 8 — DECOMPOSE (structural placeholder)
# ═══════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class DecompositionResult:
    """Output of Phase 8 (DECOMPOSE)."""

    subproblems: tuple[dict[str, Any], ...]
    dependency_edges: tuple[tuple[int, int], ...]  # (from_idx, to_idx)


def decompose_problem(
    *,
    model: EpisodeModelSet,
    feasibility: Any,
    proof_sketch: Any = None,
) -> DecompositionResult:
    """Phase 8 — DECOMPOSE into sub-problems.

    Breaks the problem into independent or weakly-coupled sub-problems.
    Each sub-problem inherits the safety floor and can be solved in parallel
    or sequentially depending on dependency edges.

    Status: structural stub — returns single monolithic subproblem.
    """
    mono = {
        "id": 0,
        "description": "monolithic (no decomposition)",
        "laws": [law.description for law in model.laws],
        "norms": [n.description for n in (model.norms or ())],
    }
    return DecompositionResult(
        subproblems=(mono,),
        dependency_edges=(),
    )


# ═══════════════════════════════════════════
# PHASE 9 — POLICY (structural placeholder)
# ═══════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class PolicyResult:
    """Output of Phase 9 (POLICY)."""

    strategy: str  # "greedy", "satisficing", "optimal", "safe_default"
    action_sequence: tuple[str, ...]
    expected_cost: float = 0.0


def select_policy(
    *,
    model: EpisodeModelSet,
    feasibility: Any,
    actions: ActionSet | None = None,
    decomposition: DecompositionResult | None = None,
) -> PolicyResult:
    """Phase 9 — SELECT POLICY.

    Chooses the execution strategy: greedy, satisficing, optimal search,
    or safe-default (when proof sketch is UNKNOWN). Maps decomposed
    sub-problems to action sequences.

    Status: structural stub — returns safe_default with empty sequence.
    """
    return PolicyResult(
        strategy="safe_default",
        action_sequence=(),
        expected_cost=0.0,
    )


# ═══════════════════════════════════════════
# PHASE 10 — EXECUTE UNDER FULL FEEDBACK
# ═══════════════════════════════════════════

@dataclass
class ExecutionStep:
    """A single step in the execution trace."""

    step_id: int
    action: str
    action_class: str  # "epistemic" or "world"
    outcome: str = ""
    safety_ok: bool = True
    surprise: float = 0.0  # KL divergence between predicted and observed
    cost: float = 0.0


@dataclass(frozen=True, slots=True)
class ExecutionTrace:
    """Full execution trace from Phase 10."""

    steps: tuple[ExecutionStep, ...]
    total_cost: float
    safety_violations: int
    stall_count: int
    goal_reached: bool

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [{"id": s.step_id, "action": s.action,
                       "class": s.action_class, "outcome": s.outcome,
                       "safety_ok": s.safety_ok, "surprise": s.surprise}
                      for s in self.steps],
            "total_cost": round(self.total_cost, 4),
            "safety_violations": self.safety_violations,
            "stall_count": self.stall_count,
            "goal_reached": self.goal_reached,
        }


def execute_plan(
    *,
    model: EpisodeModelSet,
    actions: list[dict[str, Any]],
    executor: Any = None,
    safety_check: Any = None,
    max_steps: int = 100,
    cost_budget: float = 0.0,
) -> ExecutionTrace:
    """Phase 10 — EXECUTE UNDER FULL FEEDBACK.

    Executes a sequence of actions against the frozen model with:
    - Safety pre-check before every action
    - Cost tracking against budget
    - Surprise detection (prediction vs observation divergence)
    - Stall detection (no progress for consecutive steps)
    """
    steps: list[ExecutionStep] = []
    total_cost = 0.0
    safety_violations = 0
    stall_count = 0
    goal_reached = False

    for i, action_spec in enumerate(actions[:max_steps]):
        action_name = action_spec.get("action", "unknown")
        action_class = action_spec.get("class", "world")
        action_cost = float(action_spec.get("cost", 0.0))

        # 1. Safety pre-check
        safety_ok = True
        if safety_check is not None:
            try:
                safety_ok = safety_check(action_spec)
            except Exception:
                safety_ok = False

        if not safety_ok:
            safety_violations += 1
            steps.append(ExecutionStep(
                step_id=i, action=action_name, action_class=action_class,
                outcome="safety_blocked", safety_ok=False,
            ))
            continue

        # 2. Budget check
        if cost_budget > 0 and total_cost + action_cost > cost_budget:
            steps.append(ExecutionStep(
                step_id=i, action=action_name, action_class=action_class,
                outcome="budget_exceeded", cost=action_cost,
            ))
            break

        # 3. Execute
        outcome = "executed"
        surprise = 0.0
        if executor is not None:
            try:
                result = executor(action_name, action_spec.get("params", {}))
                outcome = result.get("outcome", "executed") if isinstance(result, dict) else "executed"
                surprise = float(result.get("surprise", 0.0)) if isinstance(result, dict) else 0.0
            except Exception as exc:
                outcome = "execution_error"

        total_cost += action_cost

        # 4. Goal check
        if action_spec.get("is_goal_action", False):
            goal_reached = True

        # 5. Stall detection
        if surprise < 0.01 and outcome == "executed":
            stall_count += 1
        else:
            stall_count = 0

        steps.append(ExecutionStep(
            step_id=i, action=action_name, action_class=action_class,
            outcome=outcome, safety_ok=True, surprise=surprise, cost=action_cost,
        ))

    return ExecutionTrace(
        steps=tuple(steps),
        total_cost=total_cost,
        safety_violations=safety_violations,
        stall_count=stall_count,
        goal_reached=goal_reached,
    )


# ═══════════════════════════════════════════
# PHASE 11 — DIAGNOSE (structural placeholder)
# ═══════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class DiagnosisResult:
    """Output of Phase 11 (DIAGNOSE)."""

    diagnosis: str
    root_causes: tuple[str, ...]
    suggested_repairs: tuple[str, ...]
    model_drift_detected: bool = False


def diagnose_failure(
    *,
    trace: Any,
    model: EpisodeModelSet,
    feasibility: Any,
) -> DiagnosisResult:
    """Phase 11 — DIAGNOSE execution failures.

    Analyses a failed or stalled execution trace to identify root causes:
    model mismatch, insufficient actions, violated assumptions, or
    resource exhaustion. Suggests repairs for the next episode.

    Status: structural stub — returns generic diagnosis from trace state.
    """
    causes: list[str] = []
    repairs: list[str] = []

    if hasattr(trace, "safety_violations") and trace.safety_violations > 0:
        causes.append("safety_violation")
        repairs.append("tighten safety floor constraints")
    if hasattr(trace, "stall_count") and trace.stall_count > 0:
        causes.append("execution_stall")
        repairs.append("expand action repertoire or decompose further")
    if hasattr(trace, "goal_reached") and not trace.goal_reached:
        causes.append("goal_not_reached")
        repairs.append("re-estimate belief state and retry with updated model")

    if not causes:
        causes.append("unknown")
        repairs.append("collect more observations before retrying")

    return DiagnosisResult(
        diagnosis="structural_diagnosis",
        root_causes=tuple(causes),
        suggested_repairs=tuple(repairs),
        model_drift_detected=False,
    )


# ═══════════════════════════════════════════
# PHASE 12 — DUAL VERIFY + SOLVER OUTPUT
# ═══════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class Verification:
    """Dual-channel verification result (§5.7 of spec)."""

    pi_goal: ProofState
    pi_law: ProofState
    pi_norm: ProofState
    pi_side: ProofState
    misfit: float = 0.0  # Divergence between model and observed
    misfit_verdict: str = "consistent"  # "consistent", "suspicious", "invalidated"

    @property
    def all_pass(self) -> bool:
        return all(p == ProofState.PASS for p in (self.pi_goal, self.pi_law, self.pi_norm, self.pi_side))

    def to_dict(self) -> dict[str, Any]:
        return {
            "pi_goal": self.pi_goal.value, "pi_law": self.pi_law.value,
            "pi_norm": self.pi_norm.value, "pi_side": self.pi_side.value,
            "misfit": round(self.misfit, 4), "misfit_verdict": self.misfit_verdict,
            "all_pass": self.all_pass,
        }


@dataclass(frozen=True, slots=True)
class SolverOutput:
    """Complete output of the Φ_gps solver (§5.10 of spec)."""

    outcome: SolverOutcome
    trace: ExecutionTrace | None = None
    verification: Verification | None = None
    diagnosis: str = ""
    schema_version: str = "phi2-gps-v2.2"

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "trace": self.trace.to_dict() if self.trace else None,
            "verification": self.verification.to_dict() if self.verification else None,
            "diagnosis": self.diagnosis,
            "schema": self.schema_version,
        }


def verify_and_judge(
    *,
    trace: ExecutionTrace,
    model: EpisodeModelSet,
    feasibility: FeasibilityResult,
    misfit_threshold: float = 0.5,
) -> SolverOutput:
    """Phase 12 — DUAL VERIFY + Ψ JUDGMENT.

    Verifies the execution trace against the frozen model and
    produces the final SolverOutput with outcome classification.
    """
    # Goal verification
    pi_goal = ProofState.PASS if trace.goal_reached else ProofState.FAIL

    # Law compliance (no safety violations)
    pi_law = ProofState.PASS if trace.safety_violations == 0 else ProofState.FAIL

    # Norm compliance (based on feasibility)
    pi_norm = ProofState.PASS if feasibility.feasible else ProofState.FAIL

    # Side effects (conservative)
    pi_side = ProofState.PASS if trace.safety_violations == 0 else ProofState.UNKNOWN

    # Misfit (surprise accumulation as proxy)
    total_surprise = sum(s.surprise for s in trace.steps)
    avg_surprise = total_surprise / max(len(trace.steps), 1)
    misfit_verdict = "consistent"
    if avg_surprise > misfit_threshold:
        misfit_verdict = "invalidated"
    elif avg_surprise > misfit_threshold * 0.5:
        misfit_verdict = "suspicious"

    verification = Verification(
        pi_goal=pi_goal, pi_law=pi_law, pi_norm=pi_norm, pi_side=pi_side,
        misfit=avg_surprise, misfit_verdict=misfit_verdict,
    )

    # Classify outcome
    if verification.all_pass and misfit_verdict == "consistent":
        outcome = SolverOutcome.SOLVED_VERIFIED
    elif trace.goal_reached and not verification.all_pass:
        outcome = SolverOutcome.SOLVED_UNVERIFIED
    elif trace.safety_violations > 0:
        outcome = SolverOutcome.SAFE_HALT
    elif not feasibility.feasible:
        outcome = SolverOutcome.IMPOSSIBLE_PROVED
    elif misfit_verdict == "invalidated":
        outcome = SolverOutcome.MODEL_INVALIDATED
    elif not trace.goal_reached and trace.step_count > 0:
        outcome = SolverOutcome.BUDGET_EXHAUSTED
    else:
        outcome = SolverOutcome.AWAITING_EVIDENCE

    return SolverOutput(
        outcome=outcome,
        trace=trace,
        verification=verification,
    )
