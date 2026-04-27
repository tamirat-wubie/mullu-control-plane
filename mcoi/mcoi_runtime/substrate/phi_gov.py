"""
Φ_gov call contract — Governance Core Operator.

Signature (per MUSIA spec):
    Φ_gov(𝕊, Δ, Ctx, auth) → ⟨𝕊′, 𝕁, Δ_reject⟩

Where:
    𝕊       — current symbol field (construct registry)
    Δ       — proposed change (one or more construct modifications)
    Ctx     — request context (correlation id, tenant id, etc.)
    auth    — requesting authority
    𝕊′      — updated symbol field (Δ applied if approved)
    𝕁       — judgment record (the audit-grade decision)
    Δ_reject — any sub-deltas that were rejected (never silent)

This module provides the contract; the existing core/governance_guard.py
chain is one of several validators that Φ_gov consults. Wiring the existing
guard chain into this contract happens at runtime/governance integration
(separate work).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from mcoi_runtime.substrate.cascade import (
    CascadeEngine,
    CascadeOutcome,
    CascadeResult,
    DependencyGraph,
)
from mcoi_runtime.substrate.constructs import ConstructBase


class ProofState(Enum):
    """Decision states (mirrors v2 proof object enum)."""

    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    BUDGET_UNKNOWN = "budget_unknown"


class PhiAgentLevel(Enum):
    """6-level Φ_agent filter stack from MUSIA spec."""

    L0_PHYSICAL_LOGICAL = 0
    L1_IDENTITY = 1
    L2_SURVIVAL = 2
    L3_NORMATIVE = 3
    L4_SOCIAL = 4
    L5_OPTIMIZATION = 5


@dataclass(frozen=True)
class ProposedDelta:
    """One unit of proposed change."""

    construct_id: UUID
    operation: str  # "create" | "update" | "delete"
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.operation not in {"create", "update", "delete"}:
            raise ValueError(f"invalid operation: {self.operation}")


@dataclass(frozen=True)
class GovernanceContext:
    """Request-scoped context. Bound at request entry by core/request_correlation."""

    correlation_id: str
    tenant_id: str = ""
    actor_id: str = ""
    endpoint: str = ""


@dataclass(frozen=True)
class Authority:
    """Identifier of the principal proposing the delta."""

    identifier: str
    kind: str = "agent"  # agent | human | system

    def __post_init__(self) -> None:
        if not self.identifier:
            raise ValueError("Authority requires identifier")
        if self.kind not in {"agent", "human", "system"}:
            raise ValueError(f"invalid Authority kind: {self.kind}")


@dataclass
class Judgment:
    """Audit-grade record of a Φ_gov decision."""

    judgment_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    state: ProofState = ProofState.UNKNOWN
    reason: str = ""
    cascade_summaries: tuple[dict[str, Any], ...] = ()
    phi_agent_level_passed: Optional[PhiAgentLevel] = None
    rejected_deltas: tuple[ProposedDelta, ...] = ()

    def __post_init__(self) -> None:
        if self.state == ProofState.FAIL and not self.reason:
            raise ValueError(
                "Judgment: FAIL state requires a reason "
                "(silent rejection is the same fabrication pattern as MUSIA_MODE)"
            )


# ---- Φ_agent 6-level filter ----

PhiAgentChecker = Callable[
    [ProposedDelta, GovernanceContext, Authority], bool
]
"""Returns True iff the delta passes this level. False blocks at this level."""


class PhiAgentFilter:
    """6-level filter stack. Failure at any level blocks the delta there."""

    def __init__(
        self,
        l0: Optional[PhiAgentChecker] = None,
        l1: Optional[PhiAgentChecker] = None,
        l2: Optional[PhiAgentChecker] = None,
        l3: Optional[PhiAgentChecker] = None,
        l4: Optional[PhiAgentChecker] = None,
        l5: Optional[PhiAgentChecker] = None,
    ) -> None:
        # Default to permissive checkers at every level. Production wiring
        # replaces these per-level. Permissive default is consistent with
        # cascade engine — Φ_gov is a contract, not a policy.
        self._levels: list[tuple[PhiAgentLevel, PhiAgentChecker]] = [
            (PhiAgentLevel.L0_PHYSICAL_LOGICAL, l0 or (lambda d, c, a: True)),
            (PhiAgentLevel.L1_IDENTITY,         l1 or (lambda d, c, a: True)),
            (PhiAgentLevel.L2_SURVIVAL,         l2 or (lambda d, c, a: True)),
            (PhiAgentLevel.L3_NORMATIVE,        l3 or (lambda d, c, a: True)),
            (PhiAgentLevel.L4_SOCIAL,           l4 or (lambda d, c, a: True)),
            (PhiAgentLevel.L5_OPTIMIZATION,     l5 or (lambda d, c, a: True)),
        ]

    def evaluate(
        self,
        delta: ProposedDelta,
        ctx: GovernanceContext,
        auth: Authority,
    ) -> tuple[bool, Optional[PhiAgentLevel]]:
        """Run levels in order. Return (passed, blocking_level).

        If passed=True, blocking_level is the highest level that passed.
        If passed=False, blocking_level is the level that failed.
        """
        last_passed: Optional[PhiAgentLevel] = None
        for level, checker in self._levels:
            if not checker(delta, ctx, auth):
                return (False, level)
            last_passed = level
        return (True, last_passed)


# ---- Φ_gov core ----


@dataclass
class PhiGovResult:
    """Return type of Φ_gov.evaluate.

    Mirrors the spec signature ⟨𝕊′, 𝕁, Δ_reject⟩.
    """

    state_after: DependencyGraph  # 𝕊′
    judgment: Judgment            # 𝕁
    rejected_deltas: tuple[ProposedDelta, ...]  # Δ_reject


class PhiGov:
    """Governance core operator. Wraps cascade + Φ_agent + judgment recording.

    Existing core/governance_guard.py guard chain plugs in via
    `external_validators` — each returns (passed, reason). All must pass for
    a delta to be approved.
    """

    def __init__(
        self,
        graph: DependencyGraph,
        cascade_engine: Optional[CascadeEngine] = None,
        phi_agent: Optional[PhiAgentFilter] = None,
        external_validators: tuple[
            Callable[[ProposedDelta, GovernanceContext, Authority], tuple[bool, str]],
            ...,
        ] = (),
    ) -> None:
        self._graph = graph
        self._cascade = cascade_engine or CascadeEngine(graph)
        self._phi_agent = phi_agent or PhiAgentFilter()
        self._external = external_validators

    def evaluate(
        self,
        deltas: tuple[ProposedDelta, ...],
        ctx: GovernanceContext,
        auth: Authority,
    ) -> PhiGovResult:
        """Apply Φ_gov to a batch of proposed deltas."""
        if not deltas:
            return PhiGovResult(
                state_after=self._graph,
                judgment=Judgment(
                    state=ProofState.PASS,
                    reason="empty delta batch",
                ),
                rejected_deltas=(),
            )

        rejected: list[ProposedDelta] = []
        # v4.15.0: per-delta rejection reasons. Same order as rejected.
        # Surfaced in Judgment.reason so callers can attribute denials to
        # specific guards (Φ_agent level, external validator name, cascade).
        rejection_reasons: list[str] = []
        cascade_summaries: list[dict[str, Any]] = []
        last_phi_level: Optional[PhiAgentLevel] = None

        for delta in deltas:
            # Phase 1 — Φ_agent 6-level filter
            passed, level = self._phi_agent.evaluate(delta, ctx, auth)
            last_phi_level = level
            if not passed:
                rejected.append(delta)
                rejection_reasons.append(
                    f"phi_agent_blocked_at:{level.name if level else 'unknown'}"
                )
                continue

            # Phase 2 — external validators (existing guard_chain plugs here)
            external_failure: Optional[str] = None
            for validator in self._external:
                ok, reason = validator(delta, ctx, auth)
                if not ok:
                    external_failure = reason
                    break
            if external_failure is not None:
                rejected.append(delta)
                rejection_reasons.append(external_failure)
                continue

            # Phase 3 — cascade analysis
            if delta.construct_id in self._graph.constructs:
                cascade = self._cascade.cascade(delta.construct_id)
                cascade_summaries.append(cascade.summary())
                if cascade.rejected:
                    rejected.append(delta)
                    rejection_reasons.append(
                        f"cascade_rejected:depth_or_dependency_violation"
                    )
                    continue

        # Final judgment. The first specific rejection reason is surfaced
        # so callers can attribute denials without parsing rejected_deltas.
        if rejected:
            # v4.15 contract: surface the first specific rejection reason
            # so callers can attribute denials without parsing rejected_deltas.
            # Counts are derivable: len(rejected_deltas) vs len(deltas).
            primary = rejection_reasons[0] if rejection_reasons else "unknown"
            judgment = Judgment(
                state=ProofState.FAIL,
                reason=primary,
                cascade_summaries=tuple(cascade_summaries),
                phi_agent_level_passed=last_phi_level,
                rejected_deltas=tuple(rejected),
            )
        else:
            judgment = Judgment(
                state=ProofState.PASS,
                reason="all deltas approved",
                cascade_summaries=tuple(cascade_summaries),
                phi_agent_level_passed=last_phi_level,
                rejected_deltas=(),
            )

        return PhiGovResult(
            state_after=self._graph,
            judgment=judgment,
            rejected_deltas=tuple(rejected),
        )
