"""Phase 207C — Capability Engine.

Purpose: Manages agent capabilities with runtime discovery, dependency
    resolution, and capability composition for complex tasks.
Governance scope: capability management only.
Dependencies: agent_protocol.
Invariants:
  - Capabilities are typed and validated.
  - Composite capabilities require all sub-capabilities.
  - Capability queries are deterministic.
  - Disabled capabilities are excluded from discovery.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    """Describes a capability with metadata."""

    capability_id: str
    name: str
    description: str
    category: str = "general"  # "llm", "tool", "data", "system"
    requires: tuple[str, ...] = ()  # Sub-capability dependencies
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class CapabilityMatch:
    """Result of matching a capability requirement."""

    capability_id: str
    matched: bool
    agent_ids: tuple[str, ...]
    missing_deps: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityReadiness:
    """Deterministic readiness assessment for one capability."""

    capability_id: str
    status: str
    score: float
    agent_ids: tuple[str, ...]
    missing_deps: tuple[str, ...] = ()
    disabled_deps: tuple[str, ...] = ()
    dependency_closure: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AgentCapabilityScore:
    """Per-agent capability coverage score."""

    agent_id: str
    capability_id: str
    score: float
    covered_capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    reasons: tuple[str, ...] = ()


class CapabilityEngine:
    """Manages capability registry with composition and discovery."""

    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDescriptor] = {}
        self._agent_capabilities: dict[str, set[str]] = {}  # agent_id -> capability_ids

    def register(self, descriptor: CapabilityDescriptor) -> None:
        """Register a capability."""
        if descriptor.capability_id in self._capabilities:
            raise ValueError("capability already registered")
        self._capabilities[descriptor.capability_id] = descriptor

    def assign_to_agent(self, agent_id: str, capability_id: str) -> None:
        """Assign a capability to an agent."""
        if capability_id not in self._capabilities:
            raise ValueError("unknown capability")
        if agent_id not in self._agent_capabilities:
            self._agent_capabilities[agent_id] = set()
        self._agent_capabilities[agent_id].add(capability_id)

    def agent_has(self, agent_id: str, capability_id: str) -> bool:
        """Check if an agent has a specific capability."""
        return capability_id in self._agent_capabilities.get(agent_id, set())

    def find_agents(self, capability_id: str) -> list[str]:
        """Find all agents with a given capability."""
        cap = self._capabilities.get(capability_id)
        if cap is None or not cap.enabled:
            return []
        return sorted(
            aid for aid, caps in self._agent_capabilities.items()
            if capability_id in caps
        )

    def match(self, capability_id: str) -> CapabilityMatch:
        """Match a capability requirement against available agents."""
        cap = self._capabilities.get(capability_id)
        if cap is None:
            return CapabilityMatch(
                capability_id=capability_id, matched=False,
                agent_ids=(), missing_deps=(capability_id,),
            )

        # Check sub-dependencies
        missing = []
        for dep_id in cap.requires:
            if dep_id not in self._capabilities or not self._capabilities[dep_id].enabled:
                missing.append(dep_id)

        agents = self.find_agents(capability_id)
        return CapabilityMatch(
            capability_id=capability_id,
            matched=len(agents) > 0 and len(missing) == 0,
            agent_ids=tuple(agents),
            missing_deps=tuple(missing),
        )

    def assess_readiness(self, capability_id: str) -> CapabilityReadiness:
        """Assess whether a capability is structurally executable."""
        cap = self._capabilities.get(capability_id)
        if cap is None:
            return CapabilityReadiness(
                capability_id=capability_id,
                status="unknown",
                score=0.0,
                agent_ids=(),
                missing_deps=(capability_id,),
                reasons=("capability is not registered",),
            )

        agents = tuple(self.find_agents(capability_id))
        missing_deps, disabled_deps, cycle_deps = self._dependency_gaps(capability_id)
        dependency_closure = self._dependency_closure(capability_id)
        dependency_ok = not missing_deps and not disabled_deps and not cycle_deps
        score = _readiness_score(
            cap_exists=True,
            cap_enabled=cap.enabled,
            deps_satisfied=dependency_ok,
            assigned=bool(agents),
        )

        reasons: list[str] = []
        status = "ready"
        if not cap.enabled:
            status = "disabled"
            reasons.append("capability is disabled")
        elif cycle_deps:
            status = "blocked"
            reasons.append("dependency cycle detected")
        elif missing_deps:
            status = "blocked"
            reasons.append("dependency is not registered")
        elif disabled_deps:
            status = "blocked"
            reasons.append("dependency is disabled")
        elif not agents:
            status = "unassigned"
            reasons.append("no agent has the capability")
        else:
            reasons.append("capability is enabled, assigned, and dependency-complete")

        return CapabilityReadiness(
            capability_id=capability_id,
            status=status,
            score=score,
            agent_ids=agents,
            missing_deps=tuple(sorted(missing_deps)),
            disabled_deps=tuple(sorted(disabled_deps)),
            dependency_closure=dependency_closure,
            reasons=tuple(reasons),
        )

    def rank_agents_for(self, capability_id: str) -> tuple[AgentCapabilityScore, ...]:
        """Rank directly assigned agents by dependency coverage."""
        cap = self._capabilities.get(capability_id)
        if cap is None or not cap.enabled:
            return ()

        closure = self._dependency_closure(capability_id)
        if not closure:
            return ()

        required = set(closure)
        scores: list[AgentCapabilityScore] = []
        for agent_id in self.find_agents(capability_id):
            assigned = self._agent_capabilities.get(agent_id, set())
            covered = tuple(sorted(required.intersection(assigned)))
            missing = tuple(sorted(required.difference(assigned)))
            score = round(len(covered) / len(required), 4)
            reasons = (
                "agent has direct capability",
                "agent covers full dependency closure" if not missing else "agent is missing dependency coverage",
            )
            scores.append(
                AgentCapabilityScore(
                    agent_id=agent_id,
                    capability_id=capability_id,
                    score=score,
                    covered_capabilities=covered,
                    missing_capabilities=missing,
                    reasons=reasons,
                )
            )
        return tuple(sorted(scores, key=lambda item: (-item.score, item.agent_id)))

    def list_capabilities(self, category: str | None = None) -> list[CapabilityDescriptor]:
        """List registered capabilities, optionally filtered by category."""
        caps = sorted(self._capabilities.values(), key=lambda c: c.capability_id)
        if category is not None:
            caps = [c for c in caps if c.category == category]
        return caps

    def agent_capabilities(self, agent_id: str) -> list[CapabilityDescriptor]:
        """Get all capabilities assigned to an agent."""
        cap_ids = self._agent_capabilities.get(agent_id, set())
        return sorted(
            [self._capabilities[cid] for cid in cap_ids if cid in self._capabilities],
            key=lambda c: c.capability_id,
        )

    def disable(self, capability_id: str) -> bool:
        """Disable a capability."""
        cap = self._capabilities.get(capability_id)
        if cap is None:
            return False
        self._capabilities[capability_id] = CapabilityDescriptor(
            capability_id=cap.capability_id, name=cap.name,
            description=cap.description, category=cap.category,
            requires=cap.requires, enabled=False,
        )
        return True

    @property
    def count(self) -> int:
        return len(self._capabilities)

    def summary(self) -> dict[str, Any]:
        by_category: dict[str, int] = {}
        for cap in self._capabilities.values():
            by_category[cap.category] = by_category.get(cap.category, 0) + 1
        return {
            "total": self.count,
            "by_category": by_category,
            "agents_with_capabilities": len(self._agent_capabilities),
        }

    def readiness_report(self, category: str | None = None) -> dict[str, Any]:
        """Return deterministic readiness records for operator inspection."""
        capabilities = self.list_capabilities(category=category)
        records = []
        for cap in capabilities:
            readiness = self.assess_readiness(cap.capability_id)
            records.append(
                {
                    "capability_id": readiness.capability_id,
                    "status": readiness.status,
                    "score": readiness.score,
                    "agent_ids": readiness.agent_ids,
                    "missing_deps": readiness.missing_deps,
                    "disabled_deps": readiness.disabled_deps,
                    "dependency_closure": readiness.dependency_closure,
                    "reasons": readiness.reasons,
                }
            )
        return {
            "total": len(records),
            "ready": sum(1 for record in records if record["status"] == "ready"),
            "blocked": sum(1 for record in records if record["status"] == "blocked"),
            "unassigned": sum(1 for record in records if record["status"] == "unassigned"),
            "disabled": sum(1 for record in records if record["status"] == "disabled"),
            "capabilities": tuple(records),
        }

    def _dependency_gaps(self, capability_id: str) -> tuple[set[str], set[str], set[str]]:
        missing: set[str] = set()
        disabled: set[str] = set()
        cycles: set[str] = set()

        def visit(current_id: str, stack: tuple[str, ...]) -> None:
            cap = self._capabilities.get(current_id)
            if cap is None:
                missing.add(current_id)
                return
            if not cap.enabled:
                disabled.add(current_id)
            for dep_id in cap.requires:
                if dep_id in stack:
                    cycles.add(dep_id)
                    continue
                visit(dep_id, (*stack, dep_id))

        cap = self._capabilities.get(capability_id)
        if cap is not None:
            for dep_id in cap.requires:
                visit(dep_id, (capability_id, dep_id))
        return missing, disabled, cycles

    def _dependency_closure(self, capability_id: str) -> tuple[str, ...]:
        closure: set[str] = set()

        def visit(current_id: str, stack: tuple[str, ...]) -> None:
            if current_id in closure:
                return
            cap = self._capabilities.get(current_id)
            if cap is None:
                return
            closure.add(current_id)
            for dep_id in cap.requires:
                if dep_id in stack:
                    continue
                visit(dep_id, (*stack, dep_id))

        visit(capability_id, (capability_id,))
        return tuple(sorted(closure))


def _readiness_score(
    *,
    cap_exists: bool,
    cap_enabled: bool,
    deps_satisfied: bool,
    assigned: bool,
) -> float:
    checks = (cap_exists, cap_enabled, deps_satisfied, assigned)
    return round(sum(1 for passed in checks if passed) / len(checks), 4)
