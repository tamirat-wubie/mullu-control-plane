"""Φ_gps Runtime — Universal Problem Solver (Phases 0-12).

Purpose: Runtime implementation of Φ_gps Phases 0-12 from the canonical
    Φ specification (phi2-gps-v2.2), plus additive Phi2-GPS v3 platform
    data contracts. Bridges the formal specification to executable
    governance-aware code.

Schema: phi2-gps-v2.2 runtime; phi2-gps-v3 platform data model.
Governance scope: problem framing, symbol extraction, platform skeleton data
    contracts, trace records, and proof receipt envelopes.
Dependencies: none (pure algorithm).
Invariants:
  - Profile vector is computed deterministically from problem state.
  - Ignorance map identifies unknowns × their impact.
  - Symbol extraction assigns confidence κ per symbol.
  - Phi2-GPS v3 platform records are immutable and additive to v2.2.
  - All outputs are immutable after computation.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

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
    # Phi2-GPS v3 platform data model
    "PHI_GPS_V3_SCHEMA_VERSION", "PHI_GPS_KERNEL_SCHEMA_VERSION",
    "PROBLEM_STAR_FIELD_NAMES", "ProblemFieldStatus", "ProblemDomainClass",
    "RequiredCertainty", "PolicyHint", "ProblemEvidenceInput", "RawProblemEnvelope",
    "CompilerAssumption", "CompilerUnknown", "CompilerContradiction",
    "CompilerRisk", "CompilerProofRequirement", "CompiledProblem",
    "ProblemCompiler", "ProblemStarField", "ProblemStar",
    "ProblemShapeMetrics", "PlatformProfileVector", "PlatformVerdict",
    "PlatformTraceEventKind", "PlatformTraceEvent", "PlatformTrace",
    "PlatformProofReceipt", "RegistryKind", "RegistryRecord", "PlatformRegistry",
    "ContradictionLedger", "BeliefLedgerEntry", "BeliefLedger", "SolverMode",
    "SolverRoute", "PolicyClass", "PlatformActionClass", "ActionSchema",
    "PlatformPolicy", "ActionGate", "CounterfactualReport", "CounterfactualLab",
    "PreflightResult", "GovernancePreflight", "AdapterReceipt",
    "DeterministicPlatformAdapter", "PlatformVerificationCertificate",
    "LearningSchemaRecord", "LearningSchemaLibrary", "RepresentationMutation",
    "RepresentationLab", "FailureKind", "FAILURE_REPAIR_MAP",
    "PlatformExecutionResult", "build_problem_star", "profile_problem_star",
    "emit_platform_proof_receipt", "build_platform_registry", "route_solver",
    "synthesize_platform_policy", "verify_platform_result",
    "run_platform_cycle", "repair_for_failure",
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
        return sum(1 for law in self.laws if law.confidence >= 0.95)

    def to_dict(self) -> dict[str, Any]:
        return {
            "laws": [{"name": law.name, "type": law.law_type.value,
                      "confidence": law.confidence} for law in self.laws],
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


def _first_text(mapping: dict[str, Any], keys: tuple[str, ...], *, default: str) -> str:
    for key in keys:
        raw_value = mapping.get(key)
        if isinstance(raw_value, str) and raw_value.strip():
            return raw_value.strip()
    return default


def _bounded_probability(value: Any, default: float = 1.0) -> float:
    if value is None:
        return default
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(probability) or math.isinf(probability):
        return default
    return min(max(probability, 0.0), 1.0)


def _slug(value: Any, *, fallback: str = "item", limit: int = 48) -> str:
    text = str(value).strip().lower()
    chars = [char if char.isascii() and char.isalnum() else "_" for char in text]
    slug = "".join(chars).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return (slug[:limit].strip("_") or fallback)


# ═══════════════════════════════════════════
# PHASE 5 — TRANSITIONS
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

    Produces bounded transition contracts from observations and frozen laws.
    """
    transitions: list[dict[str, Any]] = []
    state_names: set[str] = set()

    for idx, row in enumerate(observation_data or []):
        source = _first_text(row, ("source", "from", "state", "state_before"), default=f"observed:{idx}:source")
        action = _first_text(row, ("action", "event", "operation"), default="observe")
        target = _first_text(row, ("target", "to", "next_state", "state_after"), default=source)
        probability = _bounded_probability(
            row.get("probability", row.get("confidence")),
            default=1.0,
        )
        state_names.update((source, target))
        transitions.append({
            "source": source,
            "action": action,
            "target": target,
            "probability": probability,
            "origin": "observation",
            "evidence_ref": _first_text(row, ("evidence_ref", "evidence"), default=f"observation:{idx}"),
        })

    for law in model.laws:
        state_name = f"law:{law.name}"
        state_names.add(state_name)
        transitions.append({
            "source": state_name,
            "action": f"preserve_{_slug(law.name)}",
            "target": state_name,
            "probability": _bounded_probability(law.confidence),
            "origin": "law",
            "guard": law.description,
        })
    return TransitionMap(
        transitions=tuple(transitions),
        state_space_size=len(state_names),
    )


# ═══════════════════════════════════════════
# PHASE 6 — ACTIONS
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

    Produces bounded primitive and composite actions from norms and transitions.
    """
    actions: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    def append_action(spec: dict[str, Any]) -> None:
        name = str(spec.get("name") or spec.get("action") or "").strip()
        if not name or name in seen_names:
            return
        seen_names.add(name)
        actions.append(spec)

    for norm in (model.norms or ()):
        if norm.kind == NormKind.PERMISSION:
            action_name = f"perform_{_slug(norm.name)}"
            action_class = "world"
        elif norm.kind == NormKind.PROHIBITION:
            action_name = f"avoid_{_slug(norm.name)}"
            action_class = "world"
        elif norm.kind == NormKind.GOVERNANCE:
            action_name = f"request_{_slug(norm.name)}"
            action_class = "epistemic"
        else:
            action_name = f"comply_{_slug(norm.name)}"
            action_class = "world"
        append_action({
            "name": action_name,
            "action": action_name,
            "kind": "primitive",
            "class": action_class,
            "precondition": f"authority_level<={norm.authority_level}",
            "effect": norm.description,
            "norm_ref": norm.name,
            "cost": 0.1 if action_class == "epistemic" else 1.0,
        })

    for idx, transition in enumerate((transitions.transitions if transitions else ())):
        transition_action = _first_text(transition, ("action",), default=f"transition_{idx}")
        action_name = f"apply_{_slug(transition_action, fallback=f'transition_{idx}')}"
        append_action({
            "name": action_name,
            "action": action_name,
            "kind": "primitive",
            "class": "world" if transition.get("origin") == "observation" else "epistemic",
            "precondition": transition.get("source", ""),
            "effect": transition.get("target", ""),
            "transition_ref": idx,
            "probability": _bounded_probability(transition.get("probability")),
            "cost": 1.0,
        })

    primitive_actions = tuple(action for action in actions if action.get("kind") == "primitive")
    if transitions and len(primitive_actions) > 1:
        components = tuple(str(action["name"]) for action in primitive_actions[:5])
        append_action({
            "name": "complete_transition_sequence",
            "action": "complete_transition_sequence",
            "kind": "composite",
            "class": "world",
            "components": components,
            "precondition": "primitive preconditions satisfied in order",
            "effect": "advance through bounded transition map",
            "cost": sum(float(action.get("cost", 0.0)) for action in primitive_actions[:5]),
            "is_goal_action": True,
        })

    primitive_count = sum(1 for action in actions if action.get("kind") == "primitive")
    composite_count = sum(1 for action in actions if action.get("kind") == "composite")
    return ActionSet(
        actions=tuple(actions),
        primitive_count=primitive_count,
        composite_count=composite_count,
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
# PHI2-GPS v3 — PLATFORM DATA MODEL
# ═══════════════════════════════════════════

PHI_GPS_V3_SCHEMA_VERSION = "phi2-gps-v3"
PHI_GPS_KERNEL_SCHEMA_VERSION = "phi2-gps-v2.2"
PROBLEM_STAR_FIELD_NAMES = (
    "W", "B", "O", "I", "G", "U", "Lambda", "N",
    "A_e", "A_w", "T", "R", "K", "Pi",
)


class ProblemFieldStatus(StrEnum):
    """Status lattice for each field in a v3 `ProblemStar` kernel object."""

    KNOWN = "known"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"
    HYPOTHESIZED = "hypothesized"
    FORBIDDEN = "forbidden"


class ProblemDomainClass(StrEnum):
    """Domain class carried by the v3 profile vector."""

    GENERAL = "general"
    SOFTWARE_REPAIR = "software_repair"
    SCIENTIFIC_DISCOVERY = "scientific_discovery"
    DESIGN_SYNTHESIS = "design_synthesis"
    CONTROL_PLANNING = "control_planning"
    DOCUMENT_REASONING = "document_reasoning"
    VISUAL_REASONING = "visual_reasoning"
    MULTI_AGENT_COORDINATION = "multi_agent_coordination"
    RISK_CONTAINMENT = "risk_containment"


class RequiredCertainty(StrEnum):
    """Required certainty level for v3 routing and verification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    FORMAL = "formal"


class PlatformVerdict(StrEnum):
    """Terminal v3 platform verdicts aligned with the solver outcome taxonomy."""

    SOLVED_VERIFIED = "solved_verified"
    SOLVED_UNVERIFIED = "solved_unverified"
    AWAITING_EVIDENCE = "awaiting_evidence"
    SAFE_HALT = "safe_halt"
    GOVERNANCE_BLOCKED = "governance_blocked"
    BUDGET_EXHAUSTED = "budget_exhausted"
    IMPOSSIBLE_PROVED = "impossible_proved"
    MODEL_INVALIDATED = "model_invalidated"


class PolicyHint(StrEnum):
    """Safe default policy hints emitted by the v3 problem compiler."""

    SAFE_DEFAULT = "safe_default"
    EPISTEMIC_FIRST = "epistemic_first"
    PROOF_FIRST = "proof_first"
    AUTHORITY_REVIEW = "authority_review"


@dataclass(frozen=True, slots=True)
class ProblemEvidenceInput:
    """Supplementary evidence admitted before ProblemStar compilation."""

    evidence_id: str
    source_ref: str
    statement: str
    confidence: float
    field_refs: tuple[str, ...] = ("W",)

    def __post_init__(self) -> None:
        if not self.evidence_id or not self.source_ref or not self.statement:
            raise ValueError("problem evidence id, source, and statement must be non-empty")
        _validate_unit_interval(self.confidence, "problem_evidence.confidence")
        field_refs = _normalize_text_tuple(self.field_refs, "problem_evidence.field_refs")
        invalid_fields = tuple(field for field in field_refs if field not in PROBLEM_STAR_FIELD_NAMES)
        if invalid_fields:
            raise ValueError(f"problem evidence field refs are not canonical: {invalid_fields}")
        object.__setattr__(self, "field_refs", field_refs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_ref": self.source_ref,
            "statement": self.statement,
            "confidence": round(self.confidence, 6),
            "field_refs": list(self.field_refs),
        }


@dataclass(frozen=True, slots=True)
class RawProblemEnvelope:
    """Intake-layer envelope for raw v3 problem content."""

    id: str
    input_type: str
    raw_content: Any
    source: str = "local"
    timestamp: str = ""
    requester: str = ""
    authority_context: str = ""
    urgency: str = "normal"
    declared_goal: str = ""
    declared_constraints: tuple[str, ...] = ()
    evidence_inputs: tuple[ProblemEvidenceInput, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("RawProblemEnvelope.id must be non-empty")
        if not self.input_type:
            raise ValueError("RawProblemEnvelope.input_type must be non-empty")
        if not self.source:
            raise ValueError("RawProblemEnvelope.source must be non-empty")
        object.__setattr__(self, "declared_constraints", _normalize_text_tuple(self.declared_constraints, "declared_constraints"))
        object.__setattr__(self, "evidence_inputs", _coerce_problem_evidence_inputs(self.evidence_inputs))

    @property
    def input_hash(self) -> str:
        return _stable_payload_hash(self.to_dict(include_hash=False))

    def content_text(self) -> str:
        return _raw_content_to_text(self.raw_content)

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "input_type": self.input_type,
            "raw_content": self.raw_content,
            "source": self.source,
            "timestamp": self.timestamp,
            "requester": self.requester,
            "authority_context": self.authority_context,
            "urgency": self.urgency,
            "declared_goal": self.declared_goal,
            "declared_constraints": list(self.declared_constraints),
            "evidence_inputs": [evidence.to_dict() for evidence in self.evidence_inputs],
        }
        if include_hash:
            payload["input_hash"] = self.input_hash
        return payload


@dataclass(frozen=True, slots=True)
class CompilerAssumption:
    """Assumption separated from compiler evidence."""

    assumption_id: str
    statement: str
    source: str
    confidence: float

    def __post_init__(self) -> None:
        if not self.assumption_id or not self.statement or not self.source:
            raise ValueError("assumption id, statement, and source must be non-empty")
        _validate_unit_interval(self.confidence, "assumption.confidence")

    def to_dict(self) -> dict[str, Any]:
        return {
            "assumption_id": self.assumption_id,
            "statement": self.statement,
            "source": self.source,
            "confidence": round(self.confidence, 6),
        }


@dataclass(frozen=True, slots=True)
class CompilerUnknown:
    """Unknown compiler dimension that must be resolved or bounded."""

    unknown_id: str
    dimension: str
    question: str
    impact: str
    resolution: str
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if not self.unknown_id or not self.dimension or not self.question:
            raise ValueError("unknown id, dimension, and question must be non-empty")
        if self.impact not in ("critical", "significant", "minor"):
            raise ValueError("unknown impact must be critical, significant, or minor")
        if self.resolution not in ("observe", "query", "test", "assume", "verify"):
            raise ValueError("unknown resolution is not supported")
        _validate_unit_interval(self.confidence, "unknown.confidence")

    def to_dict(self) -> dict[str, Any]:
        return {
            "unknown_id": self.unknown_id,
            "dimension": self.dimension,
            "question": self.question,
            "impact": self.impact,
            "resolution": self.resolution,
            "confidence": round(self.confidence, 6),
        }


@dataclass(frozen=True, slots=True)
class CompilerContradiction:
    """Append-only contradiction ledger entry emitted by compilation."""

    contradiction_id: str
    claims_in_conflict: tuple[str, ...]
    severity: str
    scope: str
    possible_repairs: tuple[str, ...]
    resolution_status: str = "unresolved"

    def __post_init__(self) -> None:
        if not self.contradiction_id or not self.severity or not self.scope:
            raise ValueError("contradiction id, severity, and scope must be non-empty")
        object.__setattr__(self, "claims_in_conflict", _normalize_text_tuple(self.claims_in_conflict, "claims_in_conflict"))
        object.__setattr__(self, "possible_repairs", _normalize_text_tuple(self.possible_repairs, "possible_repairs"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contradiction_id": self.contradiction_id,
            "claims_in_conflict": list(self.claims_in_conflict),
            "severity": self.severity,
            "scope": self.scope,
            "possible_repairs": list(self.possible_repairs),
            "resolution_status": self.resolution_status,
        }


@dataclass(frozen=True, slots=True)
class CompilerRisk:
    """Risk record detected during problem compilation."""

    risk_id: str
    description: str
    severity: str
    mitigation: str

    def __post_init__(self) -> None:
        if not self.risk_id or not self.description or not self.severity or not self.mitigation:
            raise ValueError("risk fields must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "description": self.description,
            "severity": self.severity,
            "mitigation": self.mitigation,
        }


@dataclass(frozen=True, slots=True)
class CompilerProofRequirement:
    """Proof obligation inferred by the v3 compiler."""

    requirement_id: str
    description: str
    required_state: ProofState = ProofState.UNKNOWN

    def __post_init__(self) -> None:
        if not self.requirement_id or not self.description:
            raise ValueError("proof requirement id and description must be non-empty")
        if not isinstance(self.required_state, ProofState):
            object.__setattr__(self, "required_state", ProofState(str(self.required_state)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "description": self.description,
            "required_state": self.required_state.value,
        }


@dataclass(frozen=True, slots=True)
class CompiledProblem:
    """Problem compiler output: `P*` draft plus evidence/assumption ledgers."""

    kernel_draft: "ProblemStar"
    symbols: tuple[Symbol, ...]
    assumptions: tuple[CompilerAssumption, ...]
    unknowns: tuple[CompilerUnknown, ...]
    contradictions: tuple[CompilerContradiction, ...]
    risks: tuple[CompilerRisk, ...]
    proof_requirements: tuple[CompilerProofRequirement, ...]
    confidence_map: dict[str, float]
    required_clarifications: tuple[str, ...]
    safe_default_policy: PolicyHint
    trace: "PlatformTrace"
    schema_version: str = PHI_GPS_V3_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PHI_GPS_V3_SCHEMA_VERSION:
            raise ValueError("CompiledProblem schema_version must be phi2-gps-v3")
        object.__setattr__(self, "symbols", tuple(self.symbols))
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "unknowns", tuple(self.unknowns))
        object.__setattr__(self, "contradictions", tuple(self.contradictions))
        object.__setattr__(self, "risks", tuple(self.risks))
        object.__setattr__(self, "proof_requirements", tuple(self.proof_requirements))
        object.__setattr__(self, "confidence_map", MappingProxyType(dict(self.confidence_map)))
        object.__setattr__(self, "required_clarifications", _normalize_text_tuple(self.required_clarifications, "required_clarifications"))
        if not isinstance(self.safe_default_policy, PolicyHint):
            object.__setattr__(self, "safe_default_policy", PolicyHint(str(self.safe_default_policy)))

    @property
    def problem_id(self) -> str:
        return self.kernel_draft.problem_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema_version,
            "kernel_draft": self.kernel_draft.to_dict(),
            "symbols": [
                {"name": symbol.name, "kind": symbol.kind, "confidence": symbol.confidence, "source": symbol.source}
                for symbol in self.symbols
            ],
            "assumptions": [assumption.to_dict() for assumption in self.assumptions],
            "unknowns": [unknown.to_dict() for unknown in self.unknowns],
            "contradictions": [contradiction.to_dict() for contradiction in self.contradictions],
            "risks": [risk.to_dict() for risk in self.risks],
            "proof_requirements": [requirement.to_dict() for requirement in self.proof_requirements],
            "confidence_map": dict(self.confidence_map),
            "required_clarifications": list(self.required_clarifications),
            "safe_default_policy": self.safe_default_policy.value,
            "trace": self.trace.to_dict(),
        }


class ProblemCompiler:
    """Deterministic v3 compiler from raw problem envelope to `CompiledProblem`."""

    @staticmethod
    def compile(envelope: RawProblemEnvelope) -> CompiledProblem:
        text = envelope.content_text()
        distinguish_result = distinguish(text)
        symbols = distinguish_result.symbols
        evidence_inputs = envelope.evidence_inputs
        assumptions = _extract_compiler_assumptions(text)
        contradictions = _detect_compiler_contradictions(text, envelope.declared_constraints)
        risks = _detect_compiler_risks(text, envelope)
        unknowns = _infer_compiler_unknowns(envelope, text, contradictions, evidence_inputs)
        proof_requirements = _infer_compiler_proof_requirements(envelope, risks, contradictions)
        confidence_map = _compiler_confidence_map(
            symbols=symbols,
            evidence_inputs=evidence_inputs,
            assumptions=assumptions,
            unknowns=unknowns,
            contradictions=contradictions,
            risks=risks,
            proof_requirements=proof_requirements,
        )
        values, statuses, evidences = _compile_problem_star_inputs(
            envelope=envelope,
            text=text,
            symbols=symbols,
            unknowns=unknowns,
            contradictions=contradictions,
            risks=risks,
            proof_requirements=proof_requirements,
            evidence_inputs=evidence_inputs,
        )
        kernel_draft = build_problem_star(
            problem_id=envelope.id,
            values=values,
            statuses=statuses,
            confidences=confidence_map,
            evidence_refs=evidences,
            input_hash=envelope.input_hash,
        )
        policy_hint = _select_compiler_policy_hint(unknowns, contradictions, risks, proof_requirements)
        required_clarifications = tuple(unknown.question for unknown in unknowns if unknown.impact in ("critical", "significant"))
        trace = (
            PlatformTrace(problem_id=envelope.id)
            .record(
                kind=PlatformTraceEventKind.INTAKED,
                cause="raw problem envelope accepted",
                payload={"input_type": envelope.input_type, "source": envelope.source},
                proof_state=ProofState.PASS,
            )
            .record(
                kind=PlatformTraceEventKind.COMPILED,
                cause="compiler separated evidence, assumptions, unknowns, contradictions, risks, and proof obligations",
                payload={
                    "symbol_count": len(symbols),
                    "evidence_input_count": len(evidence_inputs),
                    "assumption_count": len(assumptions),
                    "unknown_count": len(unknowns),
                    "contradiction_count": len(contradictions),
                    "risk_count": len(risks),
                    "proof_requirement_count": len(proof_requirements),
                },
                proof_state=ProofState.PASS if not contradictions else ProofState.UNKNOWN,
            )
        )
        return CompiledProblem(
            kernel_draft=kernel_draft,
            symbols=symbols,
            assumptions=assumptions,
            unknowns=unknowns,
            contradictions=contradictions,
            risks=risks,
            proof_requirements=proof_requirements,
            confidence_map=confidence_map,
            required_clarifications=required_clarifications,
            safe_default_policy=policy_hint,
            trace=trace,
        )


@dataclass(frozen=True, slots=True)
class ProblemStarField:
    """One field in the retained v2.2 `P*` kernel object."""

    name: str
    value: Any = None
    status: ProblemFieldStatus = ProblemFieldStatus.UNKNOWN
    confidence: float = 0.0
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.name not in PROBLEM_STAR_FIELD_NAMES:
            raise ValueError(f"unknown ProblemStar field: {self.name}")
        if not isinstance(self.status, ProblemFieldStatus):
            object.__setattr__(self, "status", ProblemFieldStatus(str(self.status)))
        _validate_unit_interval(self.confidence, f"{self.name}.confidence")
        refs = _normalize_text_tuple(self.evidence_refs, f"{self.name}.evidence_refs")
        object.__setattr__(self, "evidence_refs", refs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "status": self.status.value,
            "confidence": round(self.confidence, 6),
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class ProblemStar:
    """Phi2-GPS v3 wrapper for the retained v2.2 `P*` kernel object."""

    problem_id: str
    fields: tuple[ProblemStarField, ...]
    input_hash: str = ""
    schema_version: str = PHI_GPS_V3_SCHEMA_VERSION
    kernel_schema_version: str = PHI_GPS_KERNEL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.problem_id:
            raise ValueError("problem_id must be non-empty")
        if self.schema_version != PHI_GPS_V3_SCHEMA_VERSION:
            raise ValueError("ProblemStar schema_version must be phi2-gps-v3")
        if self.kernel_schema_version != PHI_GPS_KERNEL_SCHEMA_VERSION:
            raise ValueError("ProblemStar kernel_schema_version must be phi2-gps-v2.2")
        fields = tuple(self.fields)
        names = tuple(field.name for field in fields)
        if names != PROBLEM_STAR_FIELD_NAMES:
            raise ValueError("ProblemStar fields must preserve canonical P* field order")
        object.__setattr__(self, "fields", fields)

    @property
    def field_map(self) -> dict[str, ProblemStarField]:
        return {field.name: field for field in self.fields}

    @property
    def unknown_fields(self) -> tuple[str, ...]:
        return tuple(
            field.name
            for field in self.fields
            if field.status in (ProblemFieldStatus.UNKNOWN, ProblemFieldStatus.CONFLICTING)
        )

    def field(self, name: str) -> ProblemStarField:
        try:
            return self.field_map[name]
        except KeyError as exc:
            raise KeyError(f"ProblemStar field is not canonical: {name}") from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "schema": self.schema_version,
            "kernel_schema": self.kernel_schema_version,
            "input_hash": self.input_hash,
            "fields": {field.name: field.to_dict() for field in self.fields},
            "unknown_fields": list(self.unknown_fields),
        }


@dataclass(frozen=True, slots=True)
class ProblemShapeMetrics:
    """Normalized shape metrics used by the v3 solver router."""

    branching_factor: float = 0.0
    constraint_density: float = 0.0
    uncertainty_density: float = 0.0
    irreversibility_score: float = 0.0
    goal_sharpness: float = 0.0
    adversarial_pressure: float = 0.0
    resource_pressure: float = 0.0
    proof_burden: float = 0.0
    coupling_strength: float = 0.0

    def __post_init__(self) -> None:
        for metric_name, metric_value in self.to_dict().items():
            _validate_unit_interval(metric_value, metric_name)

    @property
    def dominant_metric(self) -> str:
        metrics = self.to_dict()
        return max(metrics, key=lambda metric_name: (metrics[metric_name], -tuple(metrics).index(metric_name)))

    def to_dict(self) -> dict[str, float]:
        return {
            "branching_factor": round(self.branching_factor, 6),
            "constraint_density": round(self.constraint_density, 6),
            "uncertainty_density": round(self.uncertainty_density, 6),
            "irreversibility_score": round(self.irreversibility_score, 6),
            "goal_sharpness": round(self.goal_sharpness, 6),
            "adversarial_pressure": round(self.adversarial_pressure, 6),
            "resource_pressure": round(self.resource_pressure, 6),
            "proof_burden": round(self.proof_burden, 6),
            "coupling_strength": round(self.coupling_strength, 6),
        }


@dataclass(frozen=True, slots=True)
class PlatformProfileVector:
    """Phi2-GPS v3 profile vector chi(P*) for platform routing."""

    k_world: ProblemFieldStatus
    k_belief: ProblemFieldStatus
    k_goal: ProblemFieldStatus
    k_laws: ProblemFieldStatus
    k_norms: ProblemFieldStatus
    k_actions: ProblemFieldStatus
    k_transition: ProblemFieldStatus
    k_proof: ProblemFieldStatus
    mode: AgentMode
    resource: ResourceLevel
    domain: ProblemDomainClass
    required_certainty: RequiredCertainty
    shape_metrics: ProblemShapeMetrics

    @property
    def unknown_count(self) -> int:
        return sum(
            1
            for status in (
                self.k_world, self.k_belief, self.k_goal, self.k_laws,
                self.k_norms, self.k_actions, self.k_transition, self.k_proof,
            )
            if status in (ProblemFieldStatus.UNKNOWN, ProblemFieldStatus.CONFLICTING)
        )

    @property
    def dominant_shape(self) -> str:
        return self.shape_metrics.dominant_metric

    def to_dict(self) -> dict[str, Any]:
        return {
            "k_world": self.k_world.value,
            "k_belief": self.k_belief.value,
            "k_goal": self.k_goal.value,
            "k_laws": self.k_laws.value,
            "k_norms": self.k_norms.value,
            "k_actions": self.k_actions.value,
            "k_transition": self.k_transition.value,
            "k_proof": self.k_proof.value,
            "mode": self.mode.value,
            "resource": self.resource.value,
            "domain": self.domain.value,
            "required_certainty": self.required_certainty.value,
            "shape_metrics": self.shape_metrics.to_dict(),
            "unknown_count": self.unknown_count,
            "dominant_shape": self.dominant_shape,
        }


class PlatformTraceEventKind(StrEnum):
    """Append-only trace event kinds in the v3 platform pipeline."""

    INTAKED = "intaked"
    COMPILED = "compiled"
    PROFILED = "profiled"
    ROUTED = "routed"
    POLICY_SYNTHESIZED = "policy_synthesized"
    PREFLIGHTED = "preflighted"
    SIMULATED = "simulated"
    EXECUTED = "executed"
    OBSERVED = "observed"
    VERIFIED = "verified"
    LEARNED = "learned"
    REFRAMED = "reframed"
    HALTED = "halted"


@dataclass(frozen=True, slots=True)
class PlatformTraceEvent:
    """One append-only v3 platform trace event."""

    event_id: int
    kind: PlatformTraceEventKind
    cause: str
    payload: dict[str, Any] = field(default_factory=dict)
    proof_state: ProofState = ProofState.UNKNOWN

    def __post_init__(self) -> None:
        if self.event_id < 0:
            raise ValueError("event_id must be non-negative")
        if not isinstance(self.kind, PlatformTraceEventKind):
            object.__setattr__(self, "kind", PlatformTraceEventKind(str(self.kind)))
        if not self.cause:
            raise ValueError("trace event cause must be non-empty")
        if not isinstance(self.proof_state, ProofState):
            object.__setattr__(self, "proof_state", ProofState(str(self.proof_state)))
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind.value,
            "cause": self.cause,
            "payload": dict(self.payload),
            "proof_state": self.proof_state.value,
        }


@dataclass(frozen=True, slots=True)
class PlatformTrace:
    """Append-only v3 trace model."""

    problem_id: str
    events: tuple[PlatformTraceEvent, ...] = ()

    def __post_init__(self) -> None:
        if not self.problem_id:
            raise ValueError("trace problem_id must be non-empty")
        events = tuple(self.events)
        for expected_id, event in enumerate(events):
            if event.event_id != expected_id:
                raise ValueError("trace event ids must be contiguous and append-only")
        object.__setattr__(self, "events", events)

    @property
    def event_count(self) -> int:
        return len(self.events)

    def record(
        self,
        *,
        kind: PlatformTraceEventKind,
        cause: str,
        payload: dict[str, Any] | None = None,
        proof_state: ProofState = ProofState.UNKNOWN,
    ) -> "PlatformTrace":
        event = PlatformTraceEvent(
            event_id=len(self.events),
            kind=kind,
            cause=cause,
            payload=payload or {},
            proof_state=proof_state,
        )
        return PlatformTrace(problem_id=self.problem_id, events=self.events + (event,))

    def events_by_kind(self, kind: PlatformTraceEventKind) -> tuple[PlatformTraceEvent, ...]:
        return tuple(event for event in self.events if event.kind == kind)

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "event_count": self.event_count,
            "events": [event.to_dict() for event in self.events],
        }


@dataclass(frozen=True, slots=True)
class PlatformProofReceipt:
    """Phi2-GPS v3 proof receipt envelope for certified platform outcomes."""

    receipt_id: str
    problem_id: str
    input_hash: str
    terminal_verdict: PlatformVerdict
    assumptions_used: tuple[str, ...] = ()
    unresolved_unknowns: tuple[str, ...] = ()
    policy_selected: str = ""
    action_trace: tuple[str, ...] = ()
    evidence_trace: tuple[str, ...] = ()
    constraints_satisfied: tuple[str, ...] = ()
    norms_satisfied: tuple[str, ...] = ()
    resources_used: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    verification_result: dict[str, Any] = field(default_factory=dict)
    residual_risk: tuple[str, ...] = ()
    learning_updates: tuple[str, ...] = ()
    trace_event_count: int = 0
    schema_version: str = PHI_GPS_V3_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.receipt_id:
            raise ValueError("receipt_id must be non-empty")
        if not self.problem_id:
            raise ValueError("receipt problem_id must be non-empty")
        if not self.input_hash:
            raise ValueError("input_hash must be non-empty")
        if not isinstance(self.terminal_verdict, PlatformVerdict):
            object.__setattr__(self, "terminal_verdict", PlatformVerdict(str(self.terminal_verdict)))
        if self.trace_event_count < 0:
            raise ValueError("trace_event_count must be non-negative")
        if self.schema_version != PHI_GPS_V3_SCHEMA_VERSION:
            raise ValueError("PlatformProofReceipt schema_version must be phi2-gps-v3")
        for field_name in (
            "assumptions_used", "unresolved_unknowns", "action_trace", "evidence_trace",
            "constraints_satisfied", "norms_satisfied", "resources_used", "side_effects",
            "residual_risk", "learning_updates",
        ):
            object.__setattr__(self, field_name, _normalize_text_tuple(getattr(self, field_name), field_name))
        object.__setattr__(self, "verification_result", MappingProxyType(dict(self.verification_result)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "problem_id": self.problem_id,
            "input_hash": self.input_hash,
            "terminal_verdict": self.terminal_verdict.value,
            "assumptions_used": list(self.assumptions_used),
            "unresolved_unknowns": list(self.unresolved_unknowns),
            "policy_selected": self.policy_selected,
            "action_trace": list(self.action_trace),
            "evidence_trace": list(self.evidence_trace),
            "constraints_satisfied": list(self.constraints_satisfied),
            "norms_satisfied": list(self.norms_satisfied),
            "resources_used": list(self.resources_used),
            "side_effects": list(self.side_effects),
            "verification_result": dict(self.verification_result),
            "residual_risk": list(self.residual_risk),
            "learning_updates": list(self.learning_updates),
            "trace_event_count": self.trace_event_count,
            "schema": self.schema_version,
        }


def build_problem_star(
    *,
    problem_id: str,
    values: dict[str, Any] | None = None,
    statuses: dict[str, ProblemFieldStatus | str] | None = None,
    confidences: dict[str, float] | None = None,
    evidence_refs: dict[str, tuple[str, ...]] | None = None,
    input_hash: str = "",
) -> ProblemStar:
    """Build a complete v3 `ProblemStar` while preserving canonical field order."""

    value_map = dict(values or {})
    status_map = dict(statuses or {})
    confidence_map = dict(confidences or {})
    evidence_ref_map = dict(evidence_refs or {})
    fields: list[ProblemStarField] = []
    for field_name in PROBLEM_STAR_FIELD_NAMES:
        status = _status_for_problem_field(field_name, value_map, status_map)
        confidence = confidence_map.get(field_name, _default_confidence_for_status(status))
        fields.append(
            ProblemStarField(
                name=field_name,
                value=value_map.get(field_name),
                status=status,
                confidence=confidence,
                evidence_refs=evidence_ref_map.get(field_name, ()),
            )
        )
    return ProblemStar(problem_id=problem_id, fields=tuple(fields), input_hash=input_hash)


def profile_problem_star(
    problem: ProblemStar,
    *,
    mode: AgentMode = AgentMode.SINGLE,
    resource: ResourceLevel = ResourceLevel.MEDIUM,
    domain: ProblemDomainClass = ProblemDomainClass.GENERAL,
    required_certainty: RequiredCertainty = RequiredCertainty.MEDIUM,
    shape_metrics: ProblemShapeMetrics | None = None,
) -> PlatformProfileVector:
    """Derive the v3 profile vector chi(P*) from a complete `ProblemStar`."""

    status = {field.name: field.status for field in problem.fields}
    derived_shape_metrics = shape_metrics or _derive_shape_metrics(problem, mode=mode, resource=resource, required_certainty=required_certainty)
    return PlatformProfileVector(
        k_world=status["W"],
        k_belief=status["B"],
        k_goal=status["G"],
        k_laws=status["Lambda"],
        k_norms=status["N"],
        k_actions=_combine_action_status(status["A_e"], status["A_w"]),
        k_transition=status["T"],
        k_proof=status["Pi"],
        mode=mode,
        resource=resource,
        domain=domain,
        required_certainty=required_certainty,
        shape_metrics=derived_shape_metrics,
    )


def emit_platform_proof_receipt(
    *,
    problem: ProblemStar,
    trace: PlatformTrace,
    terminal_verdict: PlatformVerdict,
    assumptions_used: tuple[str, ...] = (),
    policy_selected: str = "",
    constraints_satisfied: tuple[str, ...] = (),
    norms_satisfied: tuple[str, ...] = (),
    resources_used: tuple[str, ...] = (),
    side_effects: tuple[str, ...] = (),
    verification_result: dict[str, Any] | None = None,
    residual_risk: tuple[str, ...] = (),
    learning_updates: tuple[str, ...] = (),
) -> PlatformProofReceipt:
    """Emit a deterministic v3 proof receipt from a problem and trace."""

    input_hash = problem.input_hash or _stable_payload_hash(problem.to_dict())
    action_trace = tuple(
        str(event.payload.get("action", event.kind.value))
        for event in trace.events
        if event.kind == PlatformTraceEventKind.EXECUTED
    )
    evidence_trace = tuple(
        str(event.payload.get("evidence_ref", event.cause))
        for event in trace.events
        if event.kind in (PlatformTraceEventKind.OBSERVED, PlatformTraceEventKind.VERIFIED)
    )
    receipt_payload = {
        "problem_id": problem.problem_id,
        "input_hash": input_hash,
        "terminal_verdict": terminal_verdict.value if isinstance(terminal_verdict, PlatformVerdict) else str(terminal_verdict),
        "trace_event_count": trace.event_count,
    }
    receipt_id = f"phi-gps-v3-receipt-{_stable_payload_hash(receipt_payload)[:16]}"
    return PlatformProofReceipt(
        receipt_id=receipt_id,
        problem_id=problem.problem_id,
        input_hash=input_hash,
        terminal_verdict=terminal_verdict,
        assumptions_used=assumptions_used,
        unresolved_unknowns=problem.unknown_fields,
        policy_selected=policy_selected,
        action_trace=action_trace,
        evidence_trace=evidence_trace,
        constraints_satisfied=constraints_satisfied,
        norms_satisfied=norms_satisfied,
        resources_used=resources_used,
        side_effects=side_effects,
        verification_result=verification_result or {},
        residual_risk=residual_risk,
        learning_updates=learning_updates,
        trace_event_count=trace.event_count,
    )


class RegistryKind(StrEnum):
    """First-class v3 registry partitions."""

    SYMBOL = "symbol"
    BELIEF = "belief"
    LAW = "law"
    NORM = "norm"
    ACTION = "action"
    TRANSITION = "transition"
    INVARIANT = "invariant"
    PROOF = "proof"
    FAILURE = "failure"
    ADAPTER = "adapter"


class SolverMode(StrEnum):
    """Specialized solver modes available to the v3 router."""

    SEARCH = "search"
    CONSTRAINT_SATISFACTION = "constraint_satisfaction"
    OPTIMIZATION = "optimization"
    DIAGNOSIS = "diagnosis"
    DESIGN_SYNTHESIS = "design_synthesis"
    SCIENTIFIC_DISCOVERY = "scientific_discovery"
    SOFTWARE_REPAIR = "software_repair"
    PROOF_CONSTRUCTION = "proof_construction"
    NEGOTIATION = "negotiation"
    CONTROL_PLANNING = "control_planning"
    CREATIVE_GENERATION = "creative_generation"
    RISK_CONTAINMENT = "risk_containment"


class PolicyClass(StrEnum):
    """Policy classes produced by the v3 policy layer."""

    EXACT = "exact"
    HEURISTIC = "heuristic"
    ROBUST = "robust"
    ANYTIME = "anytime"
    EXPERIMENTAL = "experimental"
    ADVERSARIAL = "adversarial"
    COOPERATIVE = "cooperative"
    PROOF = "proof"
    GENERATE_TEST_REFINE = "generate_test_refine"
    HUMAN_IN_LOOP = "human_in_loop"


class PlatformActionClass(StrEnum):
    """Action bifurcation classes used by the v3 action gate."""

    EPISTEMIC = "epistemic"
    WORLD_CHANGING = "world_changing"
    HYBRID = "hybrid"


class FailureKind(StrEnum):
    """v3 failure taxonomy with deterministic repair mapping."""

    BAD_FRAME = "bad_frame"
    MISSING_STATE = "missing_state"
    BAD_BELIEF = "bad_belief"
    MISSING_GOAL = "missing_goal"
    CONFLICTING_GOAL = "conflicting_goal"
    UNKNOWN_LAW = "unknown_law"
    VIOLATED_NORM = "violated_norm"
    INSUFFICIENT_ACTION = "insufficient_action"
    WRONG_TRANSITION_MODEL = "wrong_transition_model"
    IMPOSSIBLE_GOAL = "impossible_goal"
    RESOURCE_SHORTAGE = "resource_shortage"
    UNSAFE_POLICY = "unsafe_policy"
    VERIFICATION_FAILURE = "verification_failure"
    AUTHORITY_BLOCKED = "authority_blocked"
    REPRESENTATION_FAILURE = "representation_failure"


FAILURE_REPAIR_MAP: MappingProxyType = MappingProxyType({
    FailureKind.BAD_FRAME: "recompile",
    FailureKind.MISSING_STATE: "observe",
    FailureKind.BAD_BELIEF: "update_belief",
    FailureKind.MISSING_GOAL: "construct_goal",
    FailureKind.CONFLICTING_GOAL: "priority_negotiation",
    FailureKind.UNKNOWN_LAW: "constraint_discovery",
    FailureKind.VIOLATED_NORM: "permission_repair",
    FailureKind.INSUFFICIENT_ACTION: "action_synthesis",
    FailureKind.WRONG_TRANSITION_MODEL: "transition_learning",
    FailureKind.IMPOSSIBLE_GOAL: "impossibility_proof",
    FailureKind.RESOURCE_SHORTAGE: "satisficing",
    FailureKind.UNSAFE_POLICY: "policy_rejection",
    FailureKind.VERIFICATION_FAILURE: "proof_repair",
    FailureKind.AUTHORITY_BLOCKED: "authority_escalation",
    FailureKind.REPRESENTATION_FAILURE: "representation_mutation",
})


@dataclass(frozen=True, slots=True)
class RegistryRecord:
    """One immutable record in a v3 registry partition."""

    kind: RegistryKind
    key: str
    value: Any
    evidence_refs: tuple[str, ...] = ()
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.kind, RegistryKind):
            object.__setattr__(self, "kind", RegistryKind(str(self.kind)))
        if not self.key:
            raise ValueError("registry record key must be non-empty")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "registry.evidence_refs"))
        _validate_unit_interval(self.confidence, "registry.confidence")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "key": self.key,
            "value": self.value,
            "evidence_refs": list(self.evidence_refs),
            "confidence": round(self.confidence, 6),
        }


@dataclass(frozen=True, slots=True)
class PlatformRegistry:
    """Append-only v3 registry layer for compiled problem objects."""

    problem_id: str
    records: tuple[RegistryRecord, ...] = ()

    def __post_init__(self) -> None:
        if not self.problem_id:
            raise ValueError("registry problem_id must be non-empty")
        object.__setattr__(self, "records", tuple(self.records))

    def register(self, record: RegistryRecord) -> "PlatformRegistry":
        return PlatformRegistry(problem_id=self.problem_id, records=self.records + (record,))

    def records_by_kind(self, kind: RegistryKind | str) -> tuple[RegistryRecord, ...]:
        normalized_kind = kind if isinstance(kind, RegistryKind) else RegistryKind(str(kind))
        return tuple(record for record in self.records if record.kind == normalized_kind)

    def latest(self, kind: RegistryKind | str, key: str) -> RegistryRecord | None:
        normalized_kind = kind if isinstance(kind, RegistryKind) else RegistryKind(str(kind))
        for record in reversed(self.records):
            if record.kind == normalized_kind and record.key == key:
                return record
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "record_count": len(self.records),
            "records": [record.to_dict() for record in self.records],
        }


@dataclass(frozen=True, slots=True)
class ContradictionLedger:
    """Append-only contradiction ledger derived from compiler contradictions."""

    problem_id: str
    entries: tuple[CompilerContradiction, ...] = ()

    def __post_init__(self) -> None:
        if not self.problem_id:
            raise ValueError("contradiction ledger problem_id must be non-empty")
        object.__setattr__(self, "entries", tuple(self.entries))

    def append(self, contradiction: CompilerContradiction) -> "ContradictionLedger":
        return ContradictionLedger(problem_id=self.problem_id, entries=self.entries + (contradiction,))

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "entry_count": len(self.entries),
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True, slots=True)
class BeliefLedgerEntry:
    """One belief update with causal evidence and surprise accounting."""

    previous_belief: str
    new_evidence: str
    update_rule: str
    new_belief: str
    confidence_delta: float
    surprise_score: float

    def __post_init__(self) -> None:
        if not self.update_rule or not self.new_evidence:
            raise ValueError("belief update rule and evidence must be non-empty")
        _validate_unit_interval(abs(self.confidence_delta), "belief.confidence_delta_abs")
        _validate_unit_interval(self.surprise_score, "belief.surprise_score")

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous_belief": self.previous_belief,
            "new_evidence": self.new_evidence,
            "update_rule": self.update_rule,
            "new_belief": self.new_belief,
            "confidence_delta": round(self.confidence_delta, 6),
            "surprise_score": round(self.surprise_score, 6),
        }


@dataclass(frozen=True, slots=True)
class BeliefLedger:
    """Append-only belief ledger for the governed platform loop."""

    problem_id: str
    entries: tuple[BeliefLedgerEntry, ...] = ()

    def __post_init__(self) -> None:
        if not self.problem_id:
            raise ValueError("belief ledger problem_id must be non-empty")
        object.__setattr__(self, "entries", tuple(self.entries))

    def update(
        self,
        *,
        new_evidence: str,
        update_rule: str,
        new_belief: str,
        confidence_delta: float,
        surprise_score: float,
    ) -> "BeliefLedger":
        previous_belief = self.entries[-1].new_belief if self.entries else "initial"
        entry = BeliefLedgerEntry(
            previous_belief=previous_belief,
            new_evidence=new_evidence,
            update_rule=update_rule,
            new_belief=new_belief,
            confidence_delta=confidence_delta,
            surprise_score=surprise_score,
        )
        return BeliefLedger(problem_id=self.problem_id, entries=self.entries + (entry,))

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "entry_count": len(self.entries),
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True, slots=True)
class SolverRoute:
    """v3 router output: primary solver modes plus fallback stack."""

    mode_stack: tuple[SolverMode, ...]
    fallback_stack: tuple[SolverMode, ...]
    routing_reasons: tuple[str, ...]
    profile_hash: str
    advisory_report_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.profile_hash:
            raise ValueError("solver route profile_hash must be non-empty")
        object.__setattr__(self, "mode_stack", tuple(
            mode if isinstance(mode, SolverMode) else SolverMode(str(mode))
            for mode in self.mode_stack
        ))
        object.__setattr__(self, "fallback_stack", tuple(
            mode if isinstance(mode, SolverMode) else SolverMode(str(mode))
            for mode in self.fallback_stack
        ))
        object.__setattr__(self, "routing_reasons", _normalize_text_tuple(self.routing_reasons, "routing_reasons"))
        object.__setattr__(
            self,
            "advisory_report_ids",
            _normalize_text_tuple(self.advisory_report_ids, "advisory_report_ids"),
        )

    @property
    def primary_mode(self) -> SolverMode:
        return self.mode_stack[0] if self.mode_stack else SolverMode.SEARCH

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode_stack": [mode.value for mode in self.mode_stack],
            "fallback_stack": [mode.value for mode in self.fallback_stack],
            "routing_reasons": list(self.routing_reasons),
            "profile_hash": self.profile_hash,
            "primary_mode": self.primary_mode.value,
            "advisory_report_ids": list(self.advisory_report_ids),
        }


@dataclass(frozen=True, slots=True)
class ActionSchema:
    """Governed v3 action schema accepted by adapters."""

    id: str
    action_class: PlatformActionClass
    adapter: str
    preconditions: tuple[str, ...] = ()
    predicted_effects: tuple[str, ...] = ()
    expected_information_gain: float = 0.0
    cost: float = 0.0
    risk: float = 0.0
    reversibility: float = 1.0
    permission_required: str = ""
    proof_obligation: str = ""
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.id or not self.adapter:
            raise ValueError("action id and adapter must be non-empty")
        if not isinstance(self.action_class, PlatformActionClass):
            object.__setattr__(self, "action_class", PlatformActionClass(str(self.action_class)))
        object.__setattr__(self, "preconditions", _normalize_text_tuple(self.preconditions, "action.preconditions"))
        object.__setattr__(self, "predicted_effects", _normalize_text_tuple(self.predicted_effects, "action.predicted_effects"))
        if self.cost < 0:
            raise ValueError("action cost must be non-negative")
        for name in ("expected_information_gain", "risk", "reversibility", "confidence"):
            _validate_unit_interval(float(getattr(self, name)), f"action.{name}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "class": self.action_class.value,
            "adapter": self.adapter,
            "preconditions": list(self.preconditions),
            "predicted_effects": list(self.predicted_effects),
            "expected_information_gain": round(self.expected_information_gain, 6),
            "cost": round(self.cost, 6),
            "risk": round(self.risk, 6),
            "reversibility": round(self.reversibility, 6),
            "permission_required": self.permission_required,
            "proof_obligation": self.proof_obligation,
            "confidence": round(self.confidence, 6),
        }


@dataclass(frozen=True, slots=True)
class PlatformPolicy:
    """v3 policy synthesized from a route and compiled problem."""

    policy_id: str
    policy_class: PolicyClass
    mode_stack: tuple[SolverMode, ...]
    actions: tuple[ActionSchema, ...]
    requires_counterfactual: bool = False
    requires_human_approval: bool = False

    def __post_init__(self) -> None:
        if not self.policy_id:
            raise ValueError("policy_id must be non-empty")
        if not isinstance(self.policy_class, PolicyClass):
            object.__setattr__(self, "policy_class", PolicyClass(str(self.policy_class)))
        object.__setattr__(self, "mode_stack", tuple(
            mode if isinstance(mode, SolverMode) else SolverMode(str(mode))
            for mode in self.mode_stack
        ))
        object.__setattr__(self, "actions", tuple(self.actions))

    @property
    def action_ids(self) -> tuple[str, ...]:
        return tuple(action.id for action in self.actions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_class": self.policy_class.value,
            "mode_stack": [mode.value for mode in self.mode_stack],
            "actions": [action.to_dict() for action in self.actions],
            "requires_counterfactual": self.requires_counterfactual,
            "requires_human_approval": self.requires_human_approval,
        }


class ActionGate:
    """Classify actions before preflight and execution."""

    @staticmethod
    def classify(action: ActionSchema | dict[str, Any]) -> PlatformActionClass:
        if isinstance(action, ActionSchema):
            return action.action_class
        action_class = action.get("class", action.get("action_class", PlatformActionClass.EPISTEMIC.value))
        return action_class if isinstance(action_class, PlatformActionClass) else PlatformActionClass(str(action_class))


@dataclass(frozen=True, slots=True)
class CounterfactualReport:
    """Counterfactual lab report for a candidate policy."""

    policy_id: str
    policy_options: tuple[str, ...]
    predicted_outcomes: MappingProxyType
    worst_case: str
    side_effects: tuple[str, ...]
    reversibility: float
    recommendation: str
    unsafe: bool = False

    def __post_init__(self) -> None:
        if not self.policy_id or not self.worst_case or not self.recommendation:
            raise ValueError("counterfactual report identifiers must be non-empty")
        object.__setattr__(self, "policy_options", _normalize_text_tuple(self.policy_options, "cf.policy_options"))
        object.__setattr__(self, "predicted_outcomes", MappingProxyType(dict(self.predicted_outcomes)))
        object.__setattr__(self, "side_effects", _normalize_text_tuple(self.side_effects, "cf.side_effects"))
        _validate_unit_interval(self.reversibility, "cf.reversibility")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_options": list(self.policy_options),
            "predicted_outcomes": dict(self.predicted_outcomes),
            "worst_case": self.worst_case,
            "side_effects": list(self.side_effects),
            "reversibility": round(self.reversibility, 6),
            "recommendation": self.recommendation,
            "unsafe": self.unsafe,
        }


class CounterfactualLab:
    """Deterministic counterfactual evaluator for policy candidates."""

    @staticmethod
    def test(
        policy: PlatformPolicy,
        problem: ProblemStar,
        *,
        plausible_worlds: int = 3,
    ) -> CounterfactualReport:
        if plausible_worlds <= 0:
            raise ValueError("plausible_worlds must be positive")
        side_effects: list[str] = []
        predicted_outcomes: dict[str, str] = {}
        reversibility_values: list[float] = []
        unsafe = False

        for action in policy.actions:
            reversibility_values.append(action.reversibility)
            predicted_outcomes[action.id] = "information_gain" if action.action_class == PlatformActionClass.EPISTEMIC else "state_change"
            if action.action_class != PlatformActionClass.EPISTEMIC:
                side_effects.extend(action.predicted_effects or (f"{action.id}:state_change",))
            if action.risk >= 0.7 and action.reversibility < 0.5:
                unsafe = True
            if action.action_class == PlatformActionClass.HYBRID and action.risk >= 0.5 and action.reversibility < 0.75:
                unsafe = True

        if problem.field("Lambda").status == ProblemFieldStatus.CONFLICTING:
            unsafe = True

        min_reversibility = min(reversibility_values) if reversibility_values else 1.0
        worst_case = "unsafe_tail" if unsafe else "bounded_uncertainty"
        recommendation = "reject_policy" if unsafe else "simulate_policy" if policy.requires_counterfactual else "execute_policy"
        return CounterfactualReport(
            policy_id=policy.policy_id,
            policy_options=policy.action_ids or ("safe_halt",),
            predicted_outcomes=predicted_outcomes or {"safe_halt": "no_action"},
            worst_case=worst_case,
            side_effects=tuple(dict.fromkeys(side_effects)) or ("none",),
            reversibility=min_reversibility,
            recommendation=recommendation,
            unsafe=unsafe,
        )


@dataclass(frozen=True, slots=True)
class PreflightResult:
    """Governance preflight result for one action."""

    passed: bool
    blocked_level: str = ""
    checks: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    proof_state: ProofState = ProofState.UNKNOWN

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", _normalize_text_tuple(self.checks, "preflight.checks"))
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if not isinstance(self.proof_state, ProofState):
            object.__setattr__(self, "proof_state", ProofState(str(self.proof_state)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "blocked_level": self.blocked_level,
            "checks": list(self.checks),
            "reasons": list(self.reasons),
            "proof_state": self.proof_state.value,
        }


class GovernancePreflight:
    """Law, norm, resource, risk, proof, and trace check before action."""

    @staticmethod
    def preflight(
        action: ActionSchema,
        compiled: CompiledProblem,
        cf_report: CounterfactualReport,
        *,
        allow_world_actions: bool = False,
    ) -> PreflightResult:
        checks = (
            "law_check",
            "norm_permission_check",
            "resource_check",
            "risk_check",
            "proof_obligation_check",
            "trace_write_check",
        )
        reasons: list[str] = []
        blocked_level = ""

        action_class = ActionGate.classify(action)
        if cf_report.unsafe:
            blocked_level = "risk_check"
            reasons.append("counterfactual report marked policy unsafe")
        if action_class != PlatformActionClass.EPISTEMIC and not allow_world_actions:
            blocked_level = blocked_level or "permission_check"
            reasons.append("world-changing action requires explicit allow_world_actions")
        if compiled.contradictions and action_class != PlatformActionClass.EPISTEMIC:
            blocked_level = blocked_level or "law_check"
            reasons.append("world-changing action blocked while contradictions are unresolved")
        if action.permission_required and not compiled.kernel_draft.field("I").value:
            blocked_level = blocked_level or "norm_permission_check"
            reasons.append("permission boundary lacks authority context")
        if action.risk >= 0.7 and action.reversibility < 0.5:
            blocked_level = blocked_level or "risk_check"
            reasons.append("high-risk action lacks sufficient reversibility")
        if action.proof_obligation and compiled.kernel_draft.field("Pi").status == ProblemFieldStatus.UNKNOWN:
            blocked_level = blocked_level or "proof_obligation_check"
            reasons.append("proof obligation is unknown")

        return PreflightResult(
            passed=not reasons,
            blocked_level=blocked_level,
            checks=checks,
            reasons=tuple(reasons),
            proof_state=ProofState.FAIL if reasons else ProofState.PASS,
        )


@dataclass(frozen=True, slots=True)
class AdapterReceipt:
    """Governed adapter receipt emitted for simulation or execution."""

    adapter_id: str
    action_id: str
    outcome: str
    observation: str
    side_effects: tuple[str, ...] = ()
    proof_state: ProofState = ProofState.PASS
    rollback_available: bool = True

    def __post_init__(self) -> None:
        if not self.adapter_id or not self.action_id or not self.outcome:
            raise ValueError("adapter receipt identifiers must be non-empty")
        if not self.observation:
            raise ValueError("adapter receipt observation must be non-empty")
        object.__setattr__(self, "side_effects", _normalize_text_tuple(self.side_effects, "adapter.side_effects"))
        if not isinstance(self.proof_state, ProofState):
            object.__setattr__(self, "proof_state", ProofState(str(self.proof_state)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "action_id": self.action_id,
            "outcome": self.outcome,
            "observation": self.observation,
            "side_effects": list(self.side_effects),
            "proof_state": self.proof_state.value,
            "rollback_available": self.rollback_available,
        }


class DeterministicPlatformAdapter:
    """Local deterministic adapter that simulates governed v3 actions."""

    id = "deterministic-simulation-adapter"
    domain = "local_simulation"

    def observe(self, query: str) -> AdapterReceipt:
        if not query:
            raise ValueError("observe query must be non-empty")
        return AdapterReceipt(
            adapter_id=self.id,
            action_id=f"observe:{_slug(query)}",
            outcome="observed",
            observation=f"simulated_observation:{query}",
            side_effects=("none",),
        )

    def simulate(self, action: ActionSchema, state: ProblemStar) -> AdapterReceipt:
        return AdapterReceipt(
            adapter_id=self.id,
            action_id=action.id,
            outcome="simulated",
            observation=f"predicted:{state.problem_id}:{action.id}",
            side_effects=action.predicted_effects or ("none",),
            rollback_available=True,
        )

    def preflight(self, action: ActionSchema, context: dict[str, Any]) -> PreflightResult:
        compiled = context.get("compiled")
        cf_report = context.get("cf_report")
        if not isinstance(compiled, CompiledProblem) or not isinstance(cf_report, CounterfactualReport):
            return PreflightResult(
                passed=False,
                blocked_level="adapter_context",
                checks=("adapter_context_check",),
                reasons=("missing compiled problem or counterfactual report",),
                proof_state=ProofState.FAIL,
            )
        return GovernancePreflight.preflight(
            action,
            compiled,
            cf_report,
            allow_world_actions=bool(context.get("allow_world_actions", False)),
        )

    def execute(self, action: ActionSchema, context: dict[str, Any]) -> AdapterReceipt:
        if action.action_class != PlatformActionClass.EPISTEMIC and not context.get("allow_world_actions", False):
            raise RuntimeError("world-changing action blocked by deterministic adapter")
        return AdapterReceipt(
            adapter_id=self.id,
            action_id=action.id,
            outcome="executed",
            observation=f"executed:{action.id}",
            side_effects=action.predicted_effects or ("none",),
            rollback_available=action.reversibility > 0.0,
        )

    def rollback_or_compensate(self, action: ActionSchema, result: AdapterReceipt) -> AdapterReceipt:
        return AdapterReceipt(
            adapter_id=self.id,
            action_id=f"rollback:{action.id}",
            outcome="compensated" if not result.rollback_available else "rolled_back",
            observation=f"rollback_or_compensate:{result.outcome}",
            side_effects=("compensation_logged",),
        )

    def permissions(self) -> dict[str, Any]:
        return {"world_action_default": "blocked", "simulation": "allowed"}

    def emit_receipt(self, result: AdapterReceipt) -> AdapterReceipt:
        return result


@dataclass(frozen=True, slots=True)
class PlatformVerificationCertificate:
    """v3 verification decomposition and terminal verdict."""

    terminal_verdict: PlatformVerdict
    pi_goal: ProofState
    pi_law: ProofState
    pi_norm: ProofState
    pi_resource: ProofState
    pi_side_effect: ProofState
    pi_explanation: ProofState
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.terminal_verdict, PlatformVerdict):
            object.__setattr__(self, "terminal_verdict", PlatformVerdict(str(self.terminal_verdict)))
        for field_name in ("pi_goal", "pi_law", "pi_norm", "pi_resource", "pi_side_effect", "pi_explanation"):
            value = getattr(self, field_name)
            if not isinstance(value, ProofState):
                object.__setattr__(self, field_name, ProofState(str(value)))
        object.__setattr__(self, "reasons", tuple(self.reasons))

    @property
    def all_pass(self) -> bool:
        return all(
            value == ProofState.PASS
            for value in (
                self.pi_goal, self.pi_law, self.pi_norm,
                self.pi_resource, self.pi_side_effect, self.pi_explanation,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "terminal_verdict": self.terminal_verdict.value,
            "pi_goal": self.pi_goal.value,
            "pi_law": self.pi_law.value,
            "pi_norm": self.pi_norm.value,
            "pi_resource": self.pi_resource.value,
            "pi_side_effect": self.pi_side_effect.value,
            "pi_explanation": self.pi_explanation.value,
            "all_pass": self.all_pass,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class LearningSchemaRecord:
    """Validated learning record admitted by the v3 schema library."""

    profile_hash: str
    route_modes: tuple[str, ...]
    policy_id: str
    verdict: PlatformVerdict
    reusable_schema: str
    evidence_ref: str

    def __post_init__(self) -> None:
        if not self.profile_hash or not self.policy_id or not self.reusable_schema or not self.evidence_ref:
            raise ValueError("learning schema fields must be non-empty")
        if not isinstance(self.verdict, PlatformVerdict):
            object.__setattr__(self, "verdict", PlatformVerdict(str(self.verdict)))
        object.__setattr__(self, "route_modes", _normalize_text_tuple(self.route_modes, "learning.route_modes"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_hash": self.profile_hash,
            "route_modes": list(self.route_modes),
            "policy_id": self.policy_id,
            "verdict": self.verdict.value,
            "reusable_schema": self.reusable_schema,
            "evidence_ref": self.evidence_ref,
        }


@dataclass(frozen=True, slots=True)
class LearningSchemaLibrary:
    """Append-only validated learning and schema library."""

    records: tuple[LearningSchemaRecord, ...] = ()

    def consolidate(
        self,
        *,
        receipt: PlatformProofReceipt,
        route: SolverRoute,
        policy: PlatformPolicy,
    ) -> "LearningSchemaLibrary":
        if receipt.terminal_verdict != PlatformVerdict.SOLVED_VERIFIED:
            return self
        record = LearningSchemaRecord(
            profile_hash=route.profile_hash,
            route_modes=tuple(mode.value for mode in route.mode_stack),
            policy_id=policy.policy_id,
            verdict=receipt.terminal_verdict,
            reusable_schema=f"{route.primary_mode.value}:{policy.policy_class.value}",
            evidence_ref=receipt.receipt_id,
        )
        return LearningSchemaLibrary(records=self.records + (record,))

    def retrieve(self, profile_hash: str) -> tuple[LearningSchemaRecord, ...]:
        return tuple(record for record in self.records if record.profile_hash == profile_hash)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_count": len(self.records),
            "records": [record.to_dict() for record in self.records],
        }


@dataclass(frozen=True, slots=True)
class RepresentationMutation:
    """Representation mutation lab acceptance record."""

    operator: str
    reason: str
    accepted: bool
    evidence_preserved: bool
    hard_invariants_preserved: bool
    search_burden_delta: float
    opened_policy: bool

    def __post_init__(self) -> None:
        if not self.operator or not self.reason:
            raise ValueError("representation mutation operator and reason must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "reason": self.reason,
            "accepted": self.accepted,
            "evidence_preserved": self.evidence_preserved,
            "hard_invariants_preserved": self.hard_invariants_preserved,
            "search_burden_delta": round(self.search_burden_delta, 6),
            "opened_policy": self.opened_policy,
        }


class RepresentationLab:
    """Governed representation mutation evaluator."""

    @staticmethod
    def mutate(
        problem: ProblemStar,
        *,
        failure_kind: FailureKind,
        operator: str = "causalize",
    ) -> RepresentationMutation:
        normalized_failure = failure_kind if isinstance(failure_kind, FailureKind) else FailureKind(str(failure_kind))
        evidence_preserved = bool(problem.input_hash or any(field.evidence_refs for field in problem.fields))
        hard_invariants_preserved = problem.field("Lambda").status != ProblemFieldStatus.CONFLICTING
        opens_policy = normalized_failure in (
            FailureKind.REPRESENTATION_FAILURE,
            FailureKind.WRONG_TRANSITION_MODEL,
            FailureKind.BAD_FRAME,
        )
        accepted = evidence_preserved and hard_invariants_preserved and opens_policy
        return RepresentationMutation(
            operator=operator,
            reason=normalized_failure.value,
            accepted=accepted,
            evidence_preserved=evidence_preserved,
            hard_invariants_preserved=hard_invariants_preserved,
            search_burden_delta=-0.25 if accepted else 0.0,
            opened_policy=opens_policy,
        )


@dataclass(frozen=True, slots=True)
class PlatformExecutionResult:
    """End-to-end local v3 platform loop result."""

    compiled: CompiledProblem
    profile: PlatformProfileVector
    registry: PlatformRegistry
    route: SolverRoute
    policy: PlatformPolicy
    counterfactual_report: CounterfactualReport
    trace: PlatformTrace
    verification: PlatformVerificationCertificate
    receipt: PlatformProofReceipt
    learning_library: LearningSchemaLibrary

    @property
    def verdict(self) -> PlatformVerdict:
        return self.receipt.terminal_verdict

    def to_dict(self) -> dict[str, Any]:
        return {
            "compiled": self.compiled.to_dict(),
            "profile": self.profile.to_dict(),
            "registry": self.registry.to_dict(),
            "route": self.route.to_dict(),
            "policy": self.policy.to_dict(),
            "counterfactual_report": self.counterfactual_report.to_dict(),
            "trace": self.trace.to_dict(),
            "verification": self.verification.to_dict(),
            "receipt": self.receipt.to_dict(),
            "learning_library": self.learning_library.to_dict(),
            "verdict": self.verdict.value,
        }


def build_platform_registry(compiled: CompiledProblem) -> PlatformRegistry:
    """Load compiled v3 objects into deterministic first-class registries."""

    registry = PlatformRegistry(problem_id=compiled.problem_id)
    for symbol in compiled.symbols:
        registry = registry.register(RegistryRecord(
            kind=RegistryKind.SYMBOL,
            key=symbol.name,
            value={"kind": symbol.kind, "source": symbol.source},
            evidence_refs=("distinguish",),
            confidence=symbol.confidence,
        ))
    for field in compiled.kernel_draft.fields:
        if field.status in (ProblemFieldStatus.KNOWN, ProblemFieldStatus.PARTIAL, ProblemFieldStatus.HYPOTHESIZED):
            registry_kind = _registry_kind_for_problem_field(field.name)
            registry = registry.register(RegistryRecord(
                kind=registry_kind,
                key=field.name,
                value=field.value,
                evidence_refs=field.evidence_refs or ("kernel_draft",),
                confidence=field.confidence,
            ))
    for proof_requirement in compiled.proof_requirements:
        registry = registry.register(RegistryRecord(
            kind=RegistryKind.PROOF,
            key=proof_requirement.requirement_id,
            value=proof_requirement.to_dict(),
            evidence_refs=("compiler_proof_requirements",),
            confidence=0.5,
        ))
    for contradiction in compiled.contradictions:
        registry = registry.register(RegistryRecord(
            kind=RegistryKind.FAILURE,
            key=contradiction.contradiction_id,
            value=contradiction.to_dict(),
            evidence_refs=("contradiction_ledger",),
            confidence=1.0,
        ))
    registry = registry.register(RegistryRecord(
        kind=RegistryKind.ADAPTER,
        key=DeterministicPlatformAdapter.id,
        value={"domain": DeterministicPlatformAdapter.domain, "mode": "simulation"},
        evidence_refs=("platform_default",),
        confidence=1.0,
    ))
    return registry


def route_solver(
    profile: PlatformProfileVector,
    problem: ProblemStar,
    *,
    advisory_report: Any | None = None,
) -> SolverRoute:
    """Route a profiled `ProblemStar` through specialized solver modes."""

    modes: list[SolverMode] = []
    reasons: list[str] = []
    shape = profile.shape_metrics
    advisory_fingerprint: dict[str, Any] = {}
    advisory_report_ids: tuple[str, ...] = ()

    if profile.k_goal == ProblemFieldStatus.CONFLICTING or profile.k_laws == ProblemFieldStatus.CONFLICTING:
        _append_unique_mode(modes, SolverMode.NEGOTIATION)
        reasons.append("conflicting goal or law requires priority negotiation")
    if shape.uncertainty_density >= 0.35 or profile.unknown_count > 0:
        _append_unique_mode(modes, SolverMode.DIAGNOSIS)
        reasons.append("unknown or conflicting fields require diagnosis and epistemic action")
    if shape.constraint_density >= 0.66:
        _append_unique_mode(modes, SolverMode.CONSTRAINT_SATISFACTION)
        reasons.append("high constraint density requires constraint propagation")
    if shape.irreversibility_score >= 0.7:
        _append_unique_mode(modes, SolverMode.RISK_CONTAINMENT)
        reasons.append("irreversibility requires risk containment before execution")
    if shape.coupling_strength >= 0.7:
        _append_unique_mode(modes, SolverMode.CONTROL_PLANNING)
        reasons.append("high coupling requires causal control planning")
    if shape.proof_burden >= 0.75 or profile.required_certainty == RequiredCertainty.FORMAL:
        _append_unique_mode(modes, SolverMode.PROOF_CONSTRUCTION)
        reasons.append("proof burden requires verifier-first solving")

    domain_mode = {
        ProblemDomainClass.SOFTWARE_REPAIR: SolverMode.SOFTWARE_REPAIR,
        ProblemDomainClass.SCIENTIFIC_DISCOVERY: SolverMode.SCIENTIFIC_DISCOVERY,
        ProblemDomainClass.DESIGN_SYNTHESIS: SolverMode.DESIGN_SYNTHESIS,
        ProblemDomainClass.CONTROL_PLANNING: SolverMode.CONTROL_PLANNING,
        ProblemDomainClass.RISK_CONTAINMENT: SolverMode.RISK_CONTAINMENT,
    }.get(profile.domain)
    if domain_mode is not None:
        _append_unique_mode(modes, domain_mode)
        reasons.append(f"domain class routes to {domain_mode.value}")

    if advisory_report is not None:
        advisory_fingerprint, advisory_report_ids = _apply_advisory_route_report(
            modes,
            reasons,
            advisory_report,
            problem,
        )

    if not modes:
        _append_unique_mode(modes, SolverMode.SEARCH)
        reasons.append("bounded general search fallback")

    fallback = tuple(mode for mode in (SolverMode.PROOF_CONSTRUCTION, SolverMode.DIAGNOSIS, SolverMode.SEARCH) if mode not in modes)
    return SolverRoute(
        mode_stack=tuple(modes),
        fallback_stack=fallback or (SolverMode.SEARCH,),
        routing_reasons=tuple(reasons),
        profile_hash=_stable_payload_hash({
            "profile": profile.to_dict(),
            "advisory": advisory_fingerprint,
        }),
        advisory_report_ids=advisory_report_ids,
    )


def _apply_advisory_route_report(
    modes: list[SolverMode],
    reasons: list[str],
    advisory_report: Any,
    problem: ProblemStar,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Apply read-only structural advisory evidence to solver routing."""

    if bool(getattr(advisory_report, "execution_approval", False)):
        raise ValueError("advisory report cannot approve execution")
    report_problem_id = getattr(advisory_report, "problem_id", problem.problem_id)
    if report_problem_id != problem.problem_id:
        raise ValueError("advisory report problem_id must match ProblemStar")
    report_id = str(getattr(advisory_report, "report_id", "")).strip()
    if not report_id:
        raise ValueError("advisory report requires report_id")
    suggested_modes = tuple(
        mode if isinstance(mode, SolverMode) else SolverMode(str(mode))
        for mode in tuple(getattr(advisory_report, "suggested_solver_modes", ()))
    )
    proof_gaps = _normalize_text_tuple(tuple(getattr(advisory_report, "proof_gaps", ())), "advisory.proof_gaps")
    hidden_assumptions = _normalize_text_tuple(
        tuple(getattr(advisory_report, "hidden_assumptions", ())),
        "advisory.hidden_assumptions",
    )
    repair_recommendations = _normalize_text_tuple(
        tuple(getattr(advisory_report, "repair_recommendations", ())),
        "advisory.repair_recommendations",
    )
    fracture_count = int(getattr(advisory_report, "fracture_count", 0))

    for suggested_mode in suggested_modes:
        _append_unique_mode(modes, suggested_mode)
        reasons.append(f"advisory report {report_id} recommends {suggested_mode.value}")
    if proof_gaps:
        _append_unique_mode(modes, SolverMode.PROOF_CONSTRUCTION)
        reasons.append(f"advisory report {report_id} identifies {len(proof_gaps)} proof gap(s)")
    if hidden_assumptions:
        _append_unique_mode(modes, SolverMode.DIAGNOSIS)
        reasons.append(f"advisory report {report_id} identifies {len(hidden_assumptions)} hidden assumption(s)")
    if repair_recommendations or fracture_count > 0:
        _append_unique_mode(modes, SolverMode.RISK_CONTAINMENT)
        reasons.append(f"advisory report {report_id} requires repair before action")

    return (
        {
            "report_id": report_id,
            "problem_id": report_problem_id,
            "suggested_solver_modes": [mode.value for mode in suggested_modes],
            "proof_gaps": list(proof_gaps),
            "hidden_assumptions": list(hidden_assumptions),
            "repair_recommendation_count": len(repair_recommendations),
            "fracture_count": fracture_count,
            "execution_approval": False,
        },
        (report_id,),
    )


def synthesize_platform_policy(
    compiled: CompiledProblem,
    route: SolverRoute,
    profile: PlatformProfileVector,
) -> PlatformPolicy:
    """Build a deterministic policy from compiler output and route modes."""

    actions: list[ActionSchema] = []
    requires_human_approval = compiled.safe_default_policy == PolicyHint.AUTHORITY_REVIEW

    for contradiction in compiled.contradictions:
        actions.append(ActionSchema(
            id=f"query_authority:{contradiction.contradiction_id}",
            action_class=PlatformActionClass.EPISTEMIC,
            adapter=DeterministicPlatformAdapter.id,
            preconditions=("contradiction_recorded",),
            predicted_effects=("authority_context_needed",),
            expected_information_gain=0.9,
            cost=1.0,
            risk=0.1,
            reversibility=1.0,
            proof_obligation="resolve compiler contradiction before execution",
        ))

    for unknown in compiled.unknowns:
        action_prefix = "observe" if unknown.resolution in ("observe", "test", "verify") else "query"
        actions.append(ActionSchema(
            id=f"{action_prefix}:{unknown.dimension}",
            action_class=PlatformActionClass.EPISTEMIC,
            adapter=DeterministicPlatformAdapter.id,
            preconditions=("compiled_unknown_recorded",),
            predicted_effects=(f"reduce_unknown:{unknown.dimension}",),
            expected_information_gain=0.9 if unknown.impact == "critical" else 0.6,
            cost=1.0 if unknown.impact == "critical" else 0.5,
            risk=0.0,
            reversibility=1.0,
            proof_obligation=unknown.question,
            confidence=0.8,
        ))

    if route.primary_mode == SolverMode.PROOF_CONSTRUCTION or compiled.safe_default_policy == PolicyHint.PROOF_FIRST:
        for proof_requirement in compiled.proof_requirements:
            actions.append(ActionSchema(
                id=f"verify:{proof_requirement.requirement_id}",
                action_class=PlatformActionClass.EPISTEMIC,
                adapter=DeterministicPlatformAdapter.id,
                preconditions=("proof_requirement_recorded",),
                predicted_effects=("verification_evidence",),
                expected_information_gain=0.7,
                cost=0.5,
                risk=0.0,
                reversibility=1.0,
                proof_obligation=proof_requirement.description,
                confidence=0.9,
            ))

    action_field = compiled.kernel_draft.field("A_w")
    if action_field.status in (ProblemFieldStatus.KNOWN, ProblemFieldStatus.PARTIAL, ProblemFieldStatus.HYPOTHESIZED):
        for action_name in _normalize_action_names(action_field.value):
            action_risk = 0.8 if any(risk.severity == "critical" for risk in compiled.risks) else 0.4
            actions.append(ActionSchema(
                id=f"simulate_world:{action_name}",
                action_class=PlatformActionClass.WORLD_CHANGING,
                adapter=DeterministicPlatformAdapter.id,
                preconditions=("counterfactual_passed", "governance_preflight_passed"),
                predicted_effects=(f"state_change:{action_name}",),
                expected_information_gain=0.2,
                cost=2.0,
                risk=action_risk,
                reversibility=0.4 if action_risk >= 0.7 else 0.8,
                permission_required="explicit_world_action_authority",
                proof_obligation="adapter receipt required",
                confidence=action_field.confidence,
            ))

    deduped_actions = tuple(_dedupe_actions(actions))
    if not deduped_actions:
        deduped_actions = (ActionSchema(
            id="verify:terminal_claim",
            action_class=PlatformActionClass.EPISTEMIC,
            adapter=DeterministicPlatformAdapter.id,
            preconditions=("compiled_problem_available",),
            predicted_effects=("terminal_verification",),
            expected_information_gain=0.5,
            cost=0.5,
            proof_obligation="verify terminal claim",
        ),)

    policy_class = _select_platform_policy_class(compiled, route, profile)
    requires_counterfactual = any(action.action_class != PlatformActionClass.EPISTEMIC or action.risk >= 0.5 for action in deduped_actions)
    policy_payload = {
        "problem_id": compiled.problem_id,
        "class": policy_class.value,
        "actions": [action.id for action in deduped_actions],
        "route": route.profile_hash,
    }
    return PlatformPolicy(
        policy_id=f"phi-gps-v3-policy-{_stable_payload_hash(policy_payload)[:16]}",
        policy_class=policy_class,
        mode_stack=route.mode_stack,
        actions=deduped_actions,
        requires_counterfactual=requires_counterfactual,
        requires_human_approval=requires_human_approval,
    )


def verify_platform_result(
    *,
    compiled: CompiledProblem,
    trace: PlatformTrace,
    policy: PlatformPolicy,
    cf_report: CounterfactualReport,
    profile: PlatformProfileVector,
) -> PlatformVerificationCertificate:
    """Verify a v3 platform loop and classify the terminal verdict."""

    reasons: list[str] = []
    preflight_failures = tuple(
        event for event in trace.events_by_kind(PlatformTraceEventKind.PREFLIGHTED)
        if event.proof_state == ProofState.FAIL
    )
    halted_events = trace.events_by_kind(PlatformTraceEventKind.HALTED)
    epistemic_actions = tuple(action for action in policy.actions if action.action_class == PlatformActionClass.EPISTEMIC)
    world_actions = tuple(action for action in policy.actions if action.action_class != PlatformActionClass.EPISTEMIC)
    evidence_events = trace.events_by_kind(PlatformTraceEventKind.OBSERVED)
    executed_action_ids = frozenset(
        str(event.payload.get("action", ""))
        for event in trace.events_by_kind(PlatformTraceEventKind.EXECUTED)
    )
    executed_world_action_ids = frozenset(action.id for action in world_actions if action.id in executed_action_ids)

    pi_law = ProofState.FAIL if compiled.contradictions or cf_report.unsafe else ProofState.PASS
    pi_norm = ProofState.FAIL if preflight_failures else ProofState.PASS
    pi_resource = ProofState.BUDGET_UNKNOWN if profile.resource == ResourceLevel.CRITICAL and len(policy.actions) > 1 else ProofState.PASS
    pi_side_effect = (
        ProofState.PASS
        if not world_actions
        else ProofState.PASS
        if len(executed_world_action_ids) == len(world_actions)
        else ProofState.UNKNOWN
    )
    pi_explanation = ProofState.PASS if trace.event_count > 0 else ProofState.FAIL

    if compiled.unknowns:
        pi_goal = ProofState.UNKNOWN
        reasons.append("compiler unknowns require additional evidence")
    elif compiled.kernel_draft.field("G").status in (ProblemFieldStatus.KNOWN, ProblemFieldStatus.PARTIAL):
        pi_goal = ProofState.PASS
    else:
        pi_goal = ProofState.UNKNOWN
        reasons.append("goal field is not known")

    if evidence_events and epistemic_actions and not compiled.contradictions:
        reasons.append("epistemic evidence gathered; terminal claim remains bounded")
    if cf_report.unsafe:
        reasons.append("counterfactual lab rejected unsafe tail")
    if preflight_failures:
        reasons.append("governance preflight blocked at least one action")
    if world_actions and pi_side_effect == ProofState.PASS:
        reasons.append("world-changing actions have executed adapter receipts")
    elif world_actions:
        reasons.append("world-changing action candidates lack executed receipt coverage")
    if halted_events and not reasons:
        reasons.append("platform loop halted before verification")

    if pi_resource == ProofState.BUDGET_UNKNOWN:
        terminal_verdict = PlatformVerdict.BUDGET_EXHAUSTED
    elif preflight_failures:
        terminal_verdict = PlatformVerdict.GOVERNANCE_BLOCKED
    elif cf_report.unsafe:
        terminal_verdict = PlatformVerdict.SAFE_HALT
    elif compiled.contradictions:
        terminal_verdict = PlatformVerdict.GOVERNANCE_BLOCKED
    elif compiled.unknowns:
        terminal_verdict = PlatformVerdict.AWAITING_EVIDENCE
    elif world_actions and pi_side_effect != ProofState.PASS:
        terminal_verdict = PlatformVerdict.SOLVED_UNVERIFIED
    elif all(
        proof_state == ProofState.PASS
        for proof_state in (pi_goal, pi_law, pi_norm, pi_resource, pi_side_effect, pi_explanation)
    ):
        terminal_verdict = PlatformVerdict.SOLVED_VERIFIED
    else:
        terminal_verdict = PlatformVerdict.AWAITING_EVIDENCE

    return PlatformVerificationCertificate(
        terminal_verdict=terminal_verdict,
        pi_goal=pi_goal,
        pi_law=pi_law,
        pi_norm=pi_norm,
        pi_resource=pi_resource,
        pi_side_effect=pi_side_effect,
        pi_explanation=pi_explanation,
        reasons=tuple(reasons),
    )


def run_platform_cycle(
    compiled: CompiledProblem,
    *,
    profile: PlatformProfileVector | None = None,
    registry: PlatformRegistry | None = None,
    adapter: DeterministicPlatformAdapter | None = None,
    learning_library: LearningSchemaLibrary | None = None,
    allow_world_actions: bool = False,
) -> PlatformExecutionResult:
    """Run the deterministic local v3 compile-route-policy-simulate-verify loop."""

    problem = compiled.kernel_draft
    active_profile = profile or profile_problem_star(problem)
    active_registry = registry or build_platform_registry(compiled)
    active_adapter = adapter or DeterministicPlatformAdapter()
    active_learning_library = learning_library or LearningSchemaLibrary()

    trace = compiled.trace.record(
        kind=PlatformTraceEventKind.PROFILED,
        cause="profile vector derived from kernel object",
        payload=active_profile.to_dict(),
        proof_state=ProofState.PASS,
    )
    route = route_solver(active_profile, problem)
    trace = trace.record(
        kind=PlatformTraceEventKind.ROUTED,
        cause="solver router selected mode stack",
        payload=route.to_dict(),
        proof_state=ProofState.PASS,
    )
    policy = synthesize_platform_policy(compiled, route, active_profile)
    trace = trace.record(
        kind=PlatformTraceEventKind.POLICY_SYNTHESIZED,
        cause="policy synthesized from route and compiled problem",
        payload=policy.to_dict(),
        proof_state=ProofState.PASS,
    )
    cf_report = CounterfactualLab.test(policy, problem)
    trace = trace.record(
        kind=PlatformTraceEventKind.SIMULATED,
        cause="counterfactual lab evaluated candidate policy",
        payload=cf_report.to_dict(),
        proof_state=ProofState.FAIL if cf_report.unsafe else ProofState.PASS,
    )

    if cf_report.unsafe:
        trace = trace.record(
            kind=PlatformTraceEventKind.HALTED,
            cause="counterfactual lab blocked unsafe policy",
            payload={"failure_kind": FailureKind.UNSAFE_POLICY.value},
            proof_state=ProofState.FAIL,
        )
    else:
        belief_ledger = BeliefLedger(problem_id=compiled.problem_id)
        for action in policy.actions:
            preflight = active_adapter.preflight(action, {
                "compiled": compiled,
                "cf_report": cf_report,
                "allow_world_actions": allow_world_actions,
            })
            trace = trace.record(
                kind=PlatformTraceEventKind.PREFLIGHTED,
                cause="governance preflight evaluated action",
                payload={"action": action.id, "preflight": preflight.to_dict()},
                proof_state=preflight.proof_state,
            )
            if not preflight.passed:
                trace = trace.record(
                    kind=PlatformTraceEventKind.HALTED,
                    cause="governance preflight blocked action",
                    payload={"action": action.id, "blocked_level": preflight.blocked_level},
                    proof_state=ProofState.FAIL,
                )
                break

            if action.action_class == PlatformActionClass.EPISTEMIC:
                adapter_receipt = active_adapter.observe(action.id)
                event_kind = PlatformTraceEventKind.OBSERVED
            elif allow_world_actions:
                adapter_receipt = active_adapter.execute(action, {"allow_world_actions": allow_world_actions})
                event_kind = PlatformTraceEventKind.EXECUTED
            else:
                adapter_receipt = active_adapter.simulate(action, problem)
                event_kind = PlatformTraceEventKind.SIMULATED

            trace = trace.record(
                kind=event_kind,
                cause="adapter emitted governed receipt",
                payload={
                    "action": action.id,
                    "evidence_ref": adapter_receipt.observation,
                    "adapter_receipt": adapter_receipt.to_dict(),
                },
                proof_state=adapter_receipt.proof_state,
            )
            belief_ledger = belief_ledger.update(
                new_evidence=adapter_receipt.observation,
                update_rule="deterministic_adapter_receipt",
                new_belief=f"evidence:{action.id}",
                confidence_delta=0.1,
                surprise_score=0.0,
            )

        if belief_ledger.entries:
            trace = trace.record(
                kind=PlatformTraceEventKind.OBSERVED,
                cause="belief ledger updated from adapter receipts",
                payload={"belief_ledger": belief_ledger.to_dict(), "evidence_ref": "belief_ledger"},
                proof_state=ProofState.PASS,
            )

    verification = verify_platform_result(
        compiled=compiled,
        trace=trace,
        policy=policy,
        cf_report=cf_report,
        profile=active_profile,
    )
    trace = trace.record(
        kind=PlatformTraceEventKind.VERIFIED,
        cause="platform verifier decomposed proof obligations",
        payload=verification.to_dict(),
        proof_state=ProofState.PASS if verification.terminal_verdict in (
            PlatformVerdict.SOLVED_VERIFIED,
            PlatformVerdict.SOLVED_UNVERIFIED,
            PlatformVerdict.AWAITING_EVIDENCE,
        ) else ProofState.FAIL,
    )
    receipt = emit_platform_proof_receipt(
        problem=problem,
        trace=trace,
        terminal_verdict=verification.terminal_verdict,
        assumptions_used=tuple(assumption.assumption_id for assumption in compiled.assumptions),
        policy_selected=policy.policy_id,
        constraints_satisfied=_satisfied_constraints(problem),
        norms_satisfied=_satisfied_norms(problem),
        resources_used=(f"actions:{len(policy.actions)}", f"events:{trace.event_count}"),
        side_effects=cf_report.side_effects,
        verification_result=verification.to_dict(),
        residual_risk=tuple(risk.description for risk in compiled.risks),
    )
    active_learning_library = active_learning_library.consolidate(
        receipt=receipt,
        route=route,
        policy=policy,
    )
    learning_updates = tuple(record.evidence_ref for record in active_learning_library.retrieve(route.profile_hash))
    if learning_updates:
        receipt = emit_platform_proof_receipt(
            problem=problem,
            trace=trace,
            terminal_verdict=verification.terminal_verdict,
            assumptions_used=tuple(assumption.assumption_id for assumption in compiled.assumptions),
            policy_selected=policy.policy_id,
            constraints_satisfied=_satisfied_constraints(problem),
            norms_satisfied=_satisfied_norms(problem),
            resources_used=(f"actions:{len(policy.actions)}", f"events:{trace.event_count}"),
            side_effects=cf_report.side_effects,
            verification_result=verification.to_dict(),
            residual_risk=tuple(risk.description for risk in compiled.risks),
            learning_updates=learning_updates,
        )
    trace = trace.record(
        kind=PlatformTraceEventKind.LEARNED,
        cause="learning library consolidated validated schema when allowed",
        payload={"learning_updates": list(learning_updates)},
        proof_state=ProofState.PASS,
    )
    return PlatformExecutionResult(
        compiled=compiled,
        profile=active_profile,
        registry=active_registry,
        route=route,
        policy=policy,
        counterfactual_report=cf_report,
        trace=trace,
        verification=verification,
        receipt=receipt,
        learning_library=active_learning_library,
    )


def repair_for_failure(failure_kind: FailureKind | str) -> str:
    """Return the deterministic repair action for a v3 failure kind."""

    normalized_kind = failure_kind if isinstance(failure_kind, FailureKind) else FailureKind(str(failure_kind))
    return str(FAILURE_REPAIR_MAP[normalized_kind])


def _registry_kind_for_problem_field(field_name: str) -> RegistryKind:
    mapping = {
        "W": RegistryKind.BELIEF,
        "B": RegistryKind.BELIEF,
        "O": RegistryKind.SYMBOL,
        "I": RegistryKind.INVARIANT,
        "G": RegistryKind.INVARIANT,
        "U": RegistryKind.INVARIANT,
        "Lambda": RegistryKind.LAW,
        "N": RegistryKind.NORM,
        "A_e": RegistryKind.ACTION,
        "A_w": RegistryKind.ACTION,
        "T": RegistryKind.TRANSITION,
        "R": RegistryKind.INVARIANT,
        "K": RegistryKind.SYMBOL,
        "Pi": RegistryKind.PROOF,
    }
    try:
        return mapping[field_name]
    except KeyError as exc:
        raise KeyError(f"ProblemStar field has no v3 registry mapping: {field_name}") from exc


def _append_unique_mode(modes: list[SolverMode], mode: SolverMode) -> None:
    if mode not in modes:
        modes.append(mode)


def _normalize_action_names(action_value: Any) -> tuple[str, ...]:
    if action_value is None:
        return ()
    if isinstance(action_value, str):
        return (_slug(action_value, fallback="action"),)
    if isinstance(action_value, dict):
        names: list[str] = []
        for key, value in action_value.items():
            if isinstance(value, str) and value:
                names.append(f"{key}:{value}")
            elif isinstance(value, (list, tuple, set, frozenset)):
                names.extend(f"{key}:{item}" for item in value if str(item))
            elif value:
                names.append(f"{key}:{value}")
            else:
                names.append(str(key))
        return tuple(_slug(name, fallback="action") for name in names)
    if isinstance(action_value, (list, tuple, set, frozenset)):
        return tuple(_slug(str(item), fallback="action") for item in action_value if str(item))
    return (_slug(str(action_value), fallback="action"),)


def _dedupe_actions(actions: list[ActionSchema]) -> tuple[ActionSchema, ...]:
    seen: set[str] = set()
    deduped: list[ActionSchema] = []
    for action in actions:
        if action.id not in seen:
            seen.add(action.id)
            deduped.append(action)
    return tuple(deduped)


def _select_platform_policy_class(
    compiled: CompiledProblem,
    route: SolverRoute,
    profile: PlatformProfileVector,
) -> PolicyClass:
    if compiled.safe_default_policy == PolicyHint.AUTHORITY_REVIEW:
        return PolicyClass.HUMAN_IN_LOOP
    if SolverMode.PROOF_CONSTRUCTION in route.mode_stack or compiled.safe_default_policy == PolicyHint.PROOF_FIRST:
        return PolicyClass.PROOF
    if profile.mode == AgentMode.ADVERSARIAL:
        return PolicyClass.ADVERSARIAL
    if profile.mode == AgentMode.COOPERATIVE:
        return PolicyClass.COOPERATIVE
    if SolverMode.RISK_CONTAINMENT in route.mode_stack:
        return PolicyClass.ROBUST
    if compiled.unknowns:
        return PolicyClass.GENERATE_TEST_REFINE
    return PolicyClass.HEURISTIC


def _satisfied_constraints(problem: ProblemStar) -> tuple[str, ...]:
    law_field = problem.field("Lambda")
    if law_field.status not in (ProblemFieldStatus.KNOWN, ProblemFieldStatus.PARTIAL):
        return ()
    return _normalize_text_tuple(law_field.value, "satisfied_constraints") if isinstance(law_field.value, (tuple, list, str)) else ("kernel_laws_checked",)


def _satisfied_norms(problem: ProblemStar) -> tuple[str, ...]:
    norm_field = problem.field("N")
    if norm_field.status not in (ProblemFieldStatus.KNOWN, ProblemFieldStatus.PARTIAL):
        return ()
    return _normalize_text_tuple(norm_field.value, "satisfied_norms") if isinstance(norm_field.value, (tuple, list, str)) else ("kernel_norms_checked",)


def _extract_compiler_assumptions(text: str) -> tuple[CompilerAssumption, ...]:
    assumption_markers = ("assume", "assumption", "hypothesis", "maybe", "probably", "if ")
    assumptions: list[CompilerAssumption] = []
    for sentence in _split_problem_sentences(text):
        lowered_sentence = sentence.lower()
        if any(marker in lowered_sentence for marker in assumption_markers):
            assumptions.append(
                CompilerAssumption(
                    assumption_id=f"assumption-{len(assumptions) + 1}",
                    statement=sentence,
                    source="raw_content",
                    confidence=0.5,
                )
            )
    return tuple(assumptions)


def _detect_compiler_contradictions(
    text: str,
    declared_constraints: tuple[str, ...],
) -> tuple[CompilerContradiction, ...]:
    contradictions: list[CompilerContradiction] = []
    lowered_text = text.lower()
    if "contradict" in lowered_text or "conflict" in lowered_text:
        contradictions.append(
            CompilerContradiction(
                contradiction_id="contradiction-1",
                claims_in_conflict=("raw content declares a conflict", text[:160] or "empty raw content"),
                severity="high",
                scope="raw_problem",
                possible_repairs=("split into contexts", "ask for missing evidence", "return underdetermined"),
            )
        )

    positive_targets: dict[str, str] = {}
    negative_targets: dict[str, str] = {}
    for constraint in declared_constraints:
        normalized = " ".join(constraint.lower().split())
        if normalized.startswith("must not "):
            negative_targets[normalized.removeprefix("must not ").strip()] = constraint
        elif normalized.startswith("cannot "):
            negative_targets[normalized.removeprefix("cannot ").strip()] = constraint
        elif normalized.startswith("must "):
            positive_targets[normalized.removeprefix("must ").strip()] = constraint

    for target, positive_claim in positive_targets.items():
        if target in negative_targets:
            contradictions.append(
                CompilerContradiction(
                    contradiction_id=f"contradiction-{len(contradictions) + 1}",
                    claims_in_conflict=(positive_claim, negative_targets[target]),
                    severity="critical",
                    scope="declared_constraints",
                    possible_repairs=("reject one claim", "priority negotiation", "return underdetermined"),
                )
            )
    return tuple(contradictions)


def _detect_compiler_risks(
    text: str,
    envelope: RawProblemEnvelope,
) -> tuple[CompilerRisk, ...]:
    lowered_text = f"{text} {envelope.declared_goal} {' '.join(envelope.declared_constraints)}".lower()
    risk_specs = (
        ("delete", "destructive change may remove state", "high", "require rollback or compensation plan"),
        ("payment", "money movement or finance boundary", "critical", "require approval and payment-provider receipt"),
        ("production", "production exposure boundary", "critical", "require deployment witness and public-health proof"),
        ("deploy", "deployment exposure boundary", "high", "require deployment preflight and rollback evidence"),
        ("secret", "secret or credential boundary", "critical", "redact values and require credential handling proof"),
        ("external", "external endpoint boundary", "high", "require connector preflight and effect receipt"),
        ("irreversible", "irreversible action declared", "critical", "require counterfactual lab and authority review"),
    )
    risks: list[CompilerRisk] = []
    for keyword, description, severity, mitigation in risk_specs:
        if keyword in lowered_text:
            risks.append(
                CompilerRisk(
                    risk_id=f"risk-{len(risks) + 1}",
                    description=description,
                    severity=severity,
                    mitigation=mitigation,
                )
            )
    return tuple(risks)


def _infer_compiler_unknowns(
    envelope: RawProblemEnvelope,
    text: str,
    contradictions: tuple[CompilerContradiction, ...],
    evidence_inputs: tuple[ProblemEvidenceInput, ...] = (),
) -> tuple[CompilerUnknown, ...]:
    lowered_text = text.lower()
    unknowns: list[CompilerUnknown] = []
    if not envelope.declared_goal and "goal" not in lowered_text and "done" not in lowered_text:
        unknowns.append(
            CompilerUnknown(
                unknown_id="unknown-1",
                dimension="goal",
                question="What measurable goal region should be satisfied?",
                impact="critical",
                resolution="query",
            )
        )
    has_world_evidence = _contains_any(lowered_text, ("observed", "evidence:", "state:", "current state", "system state")) or bool(_evidence_inputs_for_field(evidence_inputs, "W"))
    if not has_world_evidence:
        unknowns.append(
            CompilerUnknown(
                unknown_id=f"unknown-{len(unknowns) + 1}",
                dimension="world_state",
                question="What observed state evidence anchors the latent world state?",
                impact="critical",
                resolution="observe",
            )
        )
    if not _contains_any(lowered_text, ("verify", "test", "proof", "receipt", "assert")):
        unknowns.append(
            CompilerUnknown(
                unknown_id=f"unknown-{len(unknowns) + 1}",
                dimension="proof",
                question="Which verification evidence proves the terminal claim?",
                impact="significant",
                resolution="verify",
            )
        )
    if _contains_any(lowered_text, tuple(_ACTION_WORDS)) and not _contains_any(lowered_text, ("causes", "after", "transition", "changes to")):
        unknowns.append(
            CompilerUnknown(
                unknown_id=f"unknown-{len(unknowns) + 1}",
                dimension="transition_model",
                question="What transition model predicts action effects?",
                impact="significant",
                resolution="test",
                confidence=0.1,
            )
        )
    if contradictions:
        unknowns.append(
            CompilerUnknown(
                unknown_id=f"unknown-{len(unknowns) + 1}",
                dimension="contradiction_resolution",
                question="Which conflicting claim has authority?",
                impact="critical",
                resolution="query",
            )
        )
    return tuple(unknowns)


def _infer_compiler_proof_requirements(
    envelope: RawProblemEnvelope,
    risks: tuple[CompilerRisk, ...],
    contradictions: tuple[CompilerContradiction, ...],
) -> tuple[CompilerProofRequirement, ...]:
    requirements: list[CompilerProofRequirement] = []
    if envelope.declared_goal:
        requirements.append(
            CompilerProofRequirement(
                requirement_id="proof-1",
                description="Verify declared goal before terminal judgment",
            )
        )
    for constraint in envelope.declared_constraints:
        requirements.append(
            CompilerProofRequirement(
                requirement_id=f"proof-{len(requirements) + 1}",
                description="Verify declared constraint before execution",
            )
        )
    for risk in risks:
        requirements.append(
            CompilerProofRequirement(
                requirement_id=f"proof-{len(requirements) + 1}",
                description="Verify risk mitigation before execution",
            )
        )
    for contradiction in contradictions:
        requirements.append(
            CompilerProofRequirement(
                requirement_id=f"proof-{len(requirements) + 1}",
                description="Resolve compiler contradiction before execution",
            )
        )
    if not requirements:
        requirements.append(
            CompilerProofRequirement(
                requirement_id="proof-1",
                description="Define verification obligation before terminal judgment",
            )
        )
    return tuple(requirements)


def _compiler_confidence_map(
    *,
    symbols: tuple[Symbol, ...],
    evidence_inputs: tuple[ProblemEvidenceInput, ...] = (),
    assumptions: tuple[CompilerAssumption, ...],
    unknowns: tuple[CompilerUnknown, ...],
    contradictions: tuple[CompilerContradiction, ...],
    risks: tuple[CompilerRisk, ...],
    proof_requirements: tuple[CompilerProofRequirement, ...],
) -> dict[str, float]:
    symbol_confidence = _average(symbol.confidence for symbol in symbols)
    evidence_confidence = _average(evidence.confidence for evidence in evidence_inputs) if evidence_inputs else 0.0
    assumption_confidence = _average(assumption.confidence for assumption in assumptions) if assumptions else 1.0
    unknown_penalty = min(len(unknowns) / 10.0, 0.6)
    contradiction_penalty = min(len(contradictions) / 5.0, 0.8)
    risk_penalty = min(len(risks) / 10.0, 0.4)
    base_confidence = max(0.0, min(1.0, (symbol_confidence + assumption_confidence + evidence_confidence) / (3.0 if evidence_inputs else 2.0) - unknown_penalty - contradiction_penalty))
    proof_confidence = 0.5 if proof_requirements else 0.0
    return {
        "W": max(0.0, min(1.0, base_confidence - 0.2 + evidence_confidence * 0.3)),
        "B": base_confidence,
        "O": 0.9 if symbols else 0.5,
        "I": 0.8,
        "G": max(0.0, 1.0 - unknown_penalty - contradiction_penalty),
        "U": max(0.0, 0.7 - unknown_penalty),
        "Lambda": max(0.0, 0.8 - contradiction_penalty),
        "N": max(0.0, 0.7 - risk_penalty),
        "A_e": 0.8 if unknowns else 0.4,
        "A_w": max(0.0, symbol_confidence - risk_penalty),
        "T": max(0.0, 0.4 - unknown_penalty),
        "R": 0.8,
        "K": symbol_confidence,
        "Pi": proof_confidence,
    }


def _compile_problem_star_inputs(
    *,
    envelope: RawProblemEnvelope,
    text: str,
    symbols: tuple[Symbol, ...],
    unknowns: tuple[CompilerUnknown, ...],
    contradictions: tuple[CompilerContradiction, ...],
    risks: tuple[CompilerRisk, ...],
    proof_requirements: tuple[CompilerProofRequirement, ...],
    evidence_inputs: tuple[ProblemEvidenceInput, ...] = (),
) -> tuple[dict[str, Any], dict[str, ProblemFieldStatus], dict[str, tuple[str, ...]]]:
    action_symbols = tuple(dict.fromkeys(
        tuple(symbol.name for symbol in symbols if symbol.kind == "action") + _extract_action_keywords(text)
    ))
    lowered_text = text.lower()
    values: dict[str, Any] = {
        "O": {"input_type": envelope.input_type, "source": envelope.source},
        "I": {"requester": envelope.requester, "authority_context": envelope.authority_context},
        "R": {"urgency": envelope.urgency},
        "K": {"symbol_count": len(symbols), "symbols": [symbol.name for symbol in symbols]},
        "A_e": tuple(unknown.resolution for unknown in unknowns),
        "Pi": tuple(requirement.description for requirement in proof_requirements),
    }
    world_evidence_inputs = _evidence_inputs_for_field(evidence_inputs, "W")
    if _contains_any(lowered_text, ("observed", "evidence:", "state:", "current state", "system state")):
        values["W"] = {"evidence_ref": "raw_content"}
    if world_evidence_inputs:
        values["W"] = {
            "evidence_refs": [evidence.source_ref for evidence in world_evidence_inputs],
            "statements": [evidence.statement for evidence in world_evidence_inputs],
        }
    if symbols:
        values["B"] = {"hypotheses": [symbol.name for symbol in symbols]}
    if envelope.declared_goal:
        values["G"] = envelope.declared_goal
        values["U"] = {"goal": envelope.declared_goal, "satisficing_threshold": 0.7}
    if envelope.declared_constraints:
        values["Lambda"] = envelope.declared_constraints
    if _contains_any(lowered_text, ("approval", "permission", "governance", "consent", "policy")):
        values["N"] = {"detected_norm_markers": True}
    if action_symbols:
        values["A_w"] = action_symbols
    if _contains_any(lowered_text, ("causes", "after", "transition", "changes to")):
        values["T"] = {"transition_markers": True}

    statuses: dict[str, ProblemFieldStatus] = {
        "W": _status_from_evidence_inputs(world_evidence_inputs, default=ProblemFieldStatus.PARTIAL if "W" in values else ProblemFieldStatus.UNKNOWN),
        "B": ProblemFieldStatus.PARTIAL if "B" in values else ProblemFieldStatus.UNKNOWN,
        "O": ProblemFieldStatus.KNOWN,
        "I": ProblemFieldStatus.KNOWN if envelope.authority_context else ProblemFieldStatus.PARTIAL,
        "G": ProblemFieldStatus.KNOWN if envelope.declared_goal else ProblemFieldStatus.UNKNOWN,
        "U": ProblemFieldStatus.PARTIAL if envelope.declared_goal else ProblemFieldStatus.UNKNOWN,
        "Lambda": ProblemFieldStatus.KNOWN if envelope.declared_constraints else ProblemFieldStatus.UNKNOWN,
        "N": ProblemFieldStatus.PARTIAL if "N" in values else ProblemFieldStatus.UNKNOWN,
        "A_e": ProblemFieldStatus.KNOWN if unknowns else ProblemFieldStatus.UNKNOWN,
        "A_w": ProblemFieldStatus.PARTIAL if action_symbols else ProblemFieldStatus.UNKNOWN,
        "T": ProblemFieldStatus.PARTIAL if "T" in values else ProblemFieldStatus.UNKNOWN,
        "R": ProblemFieldStatus.KNOWN,
        "K": ProblemFieldStatus.KNOWN,
        "Pi": ProblemFieldStatus.PARTIAL if proof_requirements else ProblemFieldStatus.UNKNOWN,
    }
    if contradictions:
        statuses["G"] = ProblemFieldStatus.CONFLICTING if envelope.declared_goal else statuses["G"]
        statuses["Lambda"] = ProblemFieldStatus.CONFLICTING
    if risks and "A_w" in values:
        statuses["A_w"] = ProblemFieldStatus.HYPOTHESIZED

    evidences: dict[str, tuple[str, ...]] = {
        "O": ("raw_problem_envelope",),
        "I": ("raw_problem_envelope",),
        "R": ("raw_problem_envelope",),
        "K": ("distinguish",),
        "Pi": ("compiler_proof_requirements",),
    }
    if "W" in values:
        evidences["W"] = ("raw_content_state_marker",)
    for field_name in PROBLEM_STAR_FIELD_NAMES:
        field_evidence_inputs = _evidence_inputs_for_field(evidence_inputs, field_name)
        if not field_evidence_inputs:
            continue
        existing_refs = evidences.get(field_name, ())
        evidences[field_name] = tuple(dict.fromkeys(existing_refs + tuple(evidence.evidence_id for evidence in field_evidence_inputs)))
    if "G" in values:
        evidences["G"] = ("declared_goal",)
    if "Lambda" in values:
        evidences["Lambda"] = ("declared_constraints",)
    if "N" in values:
        evidences["N"] = ("raw_content_norm_marker",)
    if "A_w" in values:
        evidences["A_w"] = ("distinguish_actions",)
    if "A_e" in values:
        evidences["A_e"] = ("compiler_unknowns",)
    return values, statuses, evidences


def _select_compiler_policy_hint(
    unknowns: tuple[CompilerUnknown, ...],
    contradictions: tuple[CompilerContradiction, ...],
    risks: tuple[CompilerRisk, ...],
    proof_requirements: tuple[CompilerProofRequirement, ...],
) -> PolicyHint:
    if contradictions:
        return PolicyHint.AUTHORITY_REVIEW
    if any(risk.severity == "critical" for risk in risks):
        return PolicyHint.PROOF_FIRST
    if any(unknown.impact in ("critical", "significant") for unknown in unknowns):
        return PolicyHint.EPISTEMIC_FIRST
    if proof_requirements:
        return PolicyHint.PROOF_FIRST
    return PolicyHint.SAFE_DEFAULT


def _status_for_problem_field(
    field_name: str,
    value_map: dict[str, Any],
    status_map: dict[str, ProblemFieldStatus | str],
) -> ProblemFieldStatus:
    if field_name in status_map:
        status_value = status_map[field_name]
        return status_value if isinstance(status_value, ProblemFieldStatus) else ProblemFieldStatus(str(status_value))
    return ProblemFieldStatus.KNOWN if field_name in value_map else ProblemFieldStatus.UNKNOWN


def _default_confidence_for_status(status: ProblemFieldStatus) -> float:
    if status == ProblemFieldStatus.KNOWN:
        return 1.0
    if status in (ProblemFieldStatus.PARTIAL, ProblemFieldStatus.HYPOTHESIZED):
        return 0.5
    return 0.0


def _combine_action_status(
    epistemic_status: ProblemFieldStatus,
    world_status: ProblemFieldStatus,
) -> ProblemFieldStatus:
    if ProblemFieldStatus.CONFLICTING in (epistemic_status, world_status):
        return ProblemFieldStatus.CONFLICTING
    if epistemic_status == world_status:
        return epistemic_status
    if ProblemFieldStatus.FORBIDDEN in (epistemic_status, world_status):
        return ProblemFieldStatus.PARTIAL
    if ProblemFieldStatus.UNKNOWN in (epistemic_status, world_status):
        return ProblemFieldStatus.PARTIAL
    if ProblemFieldStatus.HYPOTHESIZED in (epistemic_status, world_status):
        return ProblemFieldStatus.HYPOTHESIZED
    return ProblemFieldStatus.PARTIAL


def _derive_shape_metrics(
    problem: ProblemStar,
    *,
    mode: AgentMode,
    resource: ResourceLevel,
    required_certainty: RequiredCertainty,
) -> ProblemShapeMetrics:
    fields = problem.fields
    status_by_name = problem.field_map
    unknown_or_conflicting = sum(
        1
        for field in fields
        if field.status in (ProblemFieldStatus.UNKNOWN, ProblemFieldStatus.CONFLICTING)
    )
    action_count = _bounded_action_count(status_by_name["A_e"].value) + _bounded_action_count(status_by_name["A_w"].value)
    known_constraint_count = sum(
        1
        for field_name in ("Lambda", "N", "Pi")
        if status_by_name[field_name].status in (ProblemFieldStatus.KNOWN, ProblemFieldStatus.PARTIAL)
    )
    return ProblemShapeMetrics(
        branching_factor=min(action_count / 10.0, 1.0),
        constraint_density=known_constraint_count / 3.0,
        uncertainty_density=unknown_or_conflicting / len(PROBLEM_STAR_FIELD_NAMES),
        irreversibility_score=0.75 if status_by_name["A_w"].status in (ProblemFieldStatus.KNOWN, ProblemFieldStatus.PARTIAL) else 0.25,
        goal_sharpness=_goal_sharpness(status_by_name["G"].status),
        adversarial_pressure=1.0 if mode == AgentMode.ADVERSARIAL else 0.4 if mode == AgentMode.COOPERATIVE else 0.0,
        resource_pressure={ResourceLevel.LOW: 0.25, ResourceLevel.MEDIUM: 0.5, ResourceLevel.CRITICAL: 1.0}[resource],
        proof_burden=1.0 if required_certainty == RequiredCertainty.FORMAL else 0.75 if status_by_name["Pi"].status == ProblemFieldStatus.UNKNOWN else 0.5,
        coupling_strength=0.75 if status_by_name["T"].status == ProblemFieldStatus.UNKNOWN else 0.35,
    )


def _bounded_action_count(action_value: Any) -> int:
    if isinstance(action_value, dict):
        return len(action_value)
    if isinstance(action_value, (list, tuple, set, frozenset)):
        return len(action_value)
    return 1 if action_value is not None else 0


def _goal_sharpness(status: ProblemFieldStatus) -> float:
    if status == ProblemFieldStatus.KNOWN:
        return 1.0
    if status in (ProblemFieldStatus.PARTIAL, ProblemFieldStatus.HYPOTHESIZED):
        return 0.5
    return 0.0


def _validate_unit_interval(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"{name} must be within [0, 1]")


def _coerce_problem_evidence_inputs(value: Any) -> tuple[ProblemEvidenceInput, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, ProblemEvidenceInput):
        return (value,)
    if isinstance(value, dict):
        return (ProblemEvidenceInput(**value),)
    if isinstance(value, (list, tuple)):
        coerced: list[ProblemEvidenceInput] = []
        for item in value:
            if isinstance(item, ProblemEvidenceInput):
                coerced.append(item)
            elif isinstance(item, dict):
                coerced.append(ProblemEvidenceInput(**item))
            else:
                raise ValueError("problem evidence inputs must be typed evidence objects")
        return tuple(coerced)
    raise ValueError("problem evidence inputs must be a sequence")


def _evidence_inputs_for_field(
    evidence_inputs: tuple[ProblemEvidenceInput, ...],
    field_name: str,
) -> tuple[ProblemEvidenceInput, ...]:
    return tuple(evidence for evidence in evidence_inputs if field_name in evidence.field_refs)


def _status_from_evidence_inputs(
    evidence_inputs: tuple[ProblemEvidenceInput, ...],
    *,
    default: ProblemFieldStatus,
) -> ProblemFieldStatus:
    if not evidence_inputs:
        return default
    if any(evidence.confidence >= 0.85 for evidence in evidence_inputs):
        return ProblemFieldStatus.KNOWN
    return ProblemFieldStatus.PARTIAL


def _normalize_text_tuple(value: tuple[str, ...] | list[str] | str, name: str) -> tuple[str, ...]:
    normalized = (value,) if isinstance(value, str) else tuple(value)
    if not all(isinstance(item, str) and item for item in normalized):
        raise ValueError(f"{name} must contain non-empty strings")
    return normalized


def _stable_payload_hash(payload: Any) -> str:
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(canonical_payload).hexdigest()


def _raw_content_to_text(raw_content: Any) -> str:
    if isinstance(raw_content, str):
        return raw_content
    return json.dumps(raw_content, sort_keys=True, default=str)


def _split_problem_sentences(text: str) -> tuple[str, ...]:
    normalized = text.replace("\r", "\n").replace(".", "\n").replace(";", "\n")
    return tuple(sentence.strip() for sentence in normalized.splitlines() if sentence.strip())


def _extract_action_keywords(text: str) -> tuple[str, ...]:
    actions: list[str] = []
    for word in text.split():
        normalized_word = word.strip(".,;:!?()[]{}\"'").lower()
        if normalized_word in _ACTION_WORDS and normalized_word not in actions:
            actions.append(normalized_word)
    return tuple(actions)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _average(values: Any) -> float:
    collected_values = tuple(float(value) for value in values)
    if not collected_values:
        return 0.0
    return sum(collected_values) / len(collected_values)


# ═══════════════════════════════════════════
# PHASE 8 — DECOMPOSE
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

    Emits explicit safety, norm, goal, and evidence subproblems when present.
    """
    subproblems: list[dict[str, Any]] = []
    edges: list[tuple[int, int]] = []
    ids: dict[str, int] = {}

    def append_subproblem(kind: str, description: str, **payload: Any) -> int:
        subproblem_id = len(subproblems)
        ids[kind] = subproblem_id
        subproblem = {"id": subproblem_id, "kind": kind, "description": description}
        subproblem.update(payload)
        subproblems.append(subproblem)
        return subproblem_id

    safety_variables: tuple[str, ...] = ()
    goal_description = ""
    goal_criteria: dict[str, Any] = {}
    if isinstance(model.goal, GoalConstructionResult):
        safety_variables = model.goal.utility.safety_floor.variables
        goal_description = model.goal.utility.goal.description
        goal_criteria = dict(model.goal.utility.goal.satisfaction_criteria)

    hard_violations = tuple(getattr(feasibility, "hard_violations", ()) or ())
    soft_warnings = tuple(getattr(feasibility, "soft_warnings", ()) or ())
    if model.laws or safety_variables or hard_violations:
        append_subproblem(
            "safety",
            "preserve hard laws and safety floor",
            law_refs=[law.name for law in model.laws],
            safety_variables=list(safety_variables),
            hard_violations=list(hard_violations),
            soft_warnings=list(soft_warnings),
        )

    if model.norms:
        append_subproblem(
            "norms",
            "satisfy governing norms before world action",
            norm_refs=[norm.name for norm in model.norms],
            prohibition_refs=[norm.name for norm in model.norms if norm.kind == NormKind.PROHIBITION],
        )

    if goal_description or goal_criteria:
        append_subproblem(
            "goal",
            goal_description or "satisfy goal criteria",
            criteria=goal_criteria,
        )

    if getattr(proof_sketch, "has_unknown", False):
        append_subproblem(
            "evidence",
            "collect evidence for unknown proof obligations",
            proof_state=getattr(proof_sketch, "to_dict", lambda: {})(),
        )

    if not subproblems:
        append_subproblem("monolithic", "bounded fallback problem", laws=[], norms=[])

    goal_id = ids.get("goal")
    if goal_id is not None:
        for dependency_kind in ("safety", "norms", "evidence"):
            dependency_id = ids.get(dependency_kind)
            if dependency_id is not None and dependency_id != goal_id:
                edges.append((dependency_id, goal_id))

    return DecompositionResult(
        subproblems=tuple(subproblems),
        dependency_edges=tuple(edges),
    )


# ═══════════════════════════════════════════
# PHASE 9 — POLICY
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

    Selects a bounded policy from feasibility, decomposition, and actions.
    """
    if feasibility is None or not getattr(feasibility, "feasible", False):
        return PolicyResult(
            strategy="safe_default",
            action_sequence=(),
            expected_cost=0.0,
        )

    executable_actions = tuple(actions.actions if actions else ())
    if not executable_actions:
        return PolicyResult(
            strategy="safe_default",
            action_sequence=(),
            expected_cost=0.0,
        )

    needs_evidence = any(
        subproblem.get("kind") == "evidence"
        for subproblem in (decomposition.subproblems if decomposition else ())
    )
    if needs_evidence:
        selected = tuple(action for action in executable_actions if action.get("class") == "epistemic")
        if not selected:
            return PolicyResult(
                strategy="safe_default",
                action_sequence=(),
                expected_cost=0.0,
            )
        strategy = "satisficing"
    elif getattr(feasibility, "soft_warnings", ()):
        selected = executable_actions[: min(len(executable_actions), 5)]
        strategy = "satisficing"
    elif actions and actions.composite_count > 0:
        selected = tuple(action for action in executable_actions if action.get("kind") == "composite")[:1]
        strategy = "greedy"
    else:
        selected = executable_actions[: min(len(executable_actions), 3)]
        strategy = "greedy"

    action_sequence = tuple(str(action.get("action") or action.get("name")) for action in selected)
    expected_cost = sum(float(action.get("cost", 0.0)) for action in selected)
    return PolicyResult(
        strategy=strategy,
        action_sequence=action_sequence,
        expected_cost=expected_cost,
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
            except Exception:
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
# PHASE 11 — DIAGNOSE
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

    Diagnoses safety, budget, execution, feasibility, and model-drift causes.
    """
    causes: list[str] = []
    repairs: list[str] = []
    steps = tuple(getattr(trace, "steps", ()) or ())
    outcomes = tuple(str(getattr(step, "outcome", "")) for step in steps)
    surprises = tuple(float(getattr(step, "surprise", 0.0) or 0.0) for step in steps)
    average_surprise = sum(surprises) / max(len(surprises), 1)
    model_drift_detected = average_surprise > 0.5 or any(surprise > 0.8 for surprise in surprises)

    if hasattr(trace, "safety_violations") and trace.safety_violations > 0:
        causes.append("safety_violation")
        repairs.append("tighten safety floor constraints")
    if "budget_exceeded" in outcomes:
        causes.append("budget_exhausted")
        repairs.append("reduce action cost or raise governed cost budget")
    if "execution_error" in outcomes:
        causes.append("execution_error")
        repairs.append("replace failing executor binding before retry")
    if hasattr(trace, "stall_count") and trace.stall_count > 0:
        causes.append("execution_stall")
        repairs.append("expand action repertoire or decompose further")
    if hasattr(trace, "goal_reached") and not trace.goal_reached:
        causes.append("goal_not_reached")
        repairs.append("re-estimate belief state and retry with updated model")
    if feasibility is not None and not getattr(feasibility, "feasible", True):
        causes.append("infeasible_model")
        repairs.append("revise goal or remove hard invariant contradiction")
    if model_drift_detected:
        causes.append("model_drift")
        repairs.append("freeze a new model from fresh observations")

    if not causes:
        causes.append("unknown")
        repairs.append("collect more observations before retrying")

    diagnosis = "model_drift" if model_drift_detected else "repairable_failure"
    if causes == ["unknown"]:
        diagnosis = "no_failure_observed"

    return DiagnosisResult(
        diagnosis=diagnosis,
        root_causes=tuple(causes),
        suggested_repairs=tuple(repairs),
        model_drift_detected=model_drift_detected,
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
