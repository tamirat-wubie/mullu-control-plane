"""Purpose: bridge between domain pack engine and domain-specific engines.
Governance scope: resolving domain packs for goals, workflows, functions,
    teams and applying their rules/profiles to extraction, routing, memory,
    simulation, utility, governance, and benchmarking engines.
Dependencies: DomainPackEngine, EventSpineEngine, MemoryMeshEngine,
    core invariants.
Invariants:
  - Does not mutate engines directly — returns typed config/profiles.
  - Only ACTIVE packs participate in resolution.
  - All outputs are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from ..contracts.domain_pack import (
    DomainBenchmarkProfile,
    DomainEscalationProfile,
    DomainExtractionRule,
    DomainMemoryRule,
    DomainPackResolution,
    DomainRoutingRule,
    DomainRuleKind,
    DomainSimulationProfile,
    DomainUtilityProfile,
    PackScope,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .domain_pack import DomainPackEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(event_spine: EventSpineEngine, action: str, payload: dict, correlation_id: str) -> EventRecord:
    """Create and emit an event record."""
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-dp", {"action": action, "ts": now, "cid": correlation_id}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=correlation_id,
        payload=payload,
        emitted_at=now,
    )
    event_spine.emit(event)
    return event


class DomainPackIntegration:
    """Bridge connecting domain pack engine to runtime subsystems."""

    def __init__(
        self,
        pack_engine: DomainPackEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(pack_engine, DomainPackEngine):
            raise RuntimeCoreInvariantError("pack_engine must be a DomainPackEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._pack_engine = pack_engine
        self._event_spine = event_spine
        self._memory_engine = memory_engine

    # -----------------------------------------------------------------------
    # Scope-based resolution
    # -----------------------------------------------------------------------

    def resolve_for_goal(self, goal_id: str) -> DomainPackResolution:
        return self._pack_engine.resolve_for_scope(PackScope.GOAL, goal_id)

    def resolve_for_workflow(self, workflow_id: str) -> DomainPackResolution:
        return self._pack_engine.resolve_for_scope(PackScope.WORKFLOW, workflow_id)

    def resolve_for_function(self, function_id: str) -> DomainPackResolution:
        return self._pack_engine.resolve_for_scope(PackScope.FUNCTION, function_id)

    def resolve_for_team(self, team_id: str) -> DomainPackResolution:
        return self._pack_engine.resolve_for_scope(PackScope.TEAM, team_id)

    # -----------------------------------------------------------------------
    # Domain-specific application methods
    # -----------------------------------------------------------------------

    def apply_to_commitment_extraction(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> dict[str, Any]:
        """Resolve extraction rules and vocabulary for commitment extraction."""
        rules = self._pack_engine.resolve_extraction_rules(scope, scope_ref_id)
        vocab = []
        for pack_id in sorted({r.pack_id for r in rules}):
            vocab.extend(self._pack_engine.get_vocabulary_for_pack(pack_id))

        event = _emit(self._event_spine, "domain_pack_extraction_applied", {
            "scope": scope.value,
            "scope_ref_id": scope_ref_id,
            "rule_count": len(rules),
            "vocab_count": len(vocab),
        }, scope_ref_id or "domain-extraction")

        return {
            "extraction_rules": rules,
            "vocabulary": tuple(vocab),
            "event": event,
        }

    def apply_to_artifact_ingestion(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> dict[str, Any]:
        """Resolve ingestion-related rules for artifact processing."""
        rules = self._pack_engine.resolve_extraction_rules(scope, scope_ref_id)
        ingestion_rules = [
            r for r in rules
            if r.commitment_type in ("ingestion", "artifact", "config", "dataset")
        ]

        event = _emit(self._event_spine, "domain_pack_ingestion_applied", {
            "scope": scope.value,
            "rule_count": len(ingestion_rules),
        }, scope_ref_id or "domain-ingestion")

        return {
            "ingestion_rules": tuple(ingestion_rules),
            "event": event,
        }

    def apply_to_contact_routing(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> dict[str, Any]:
        """Resolve routing rules for contact/identity routing."""
        rules = self._pack_engine.resolve_routing_rules(scope, scope_ref_id)
        escalation = self._pack_engine.resolve_escalation_profile(scope, scope_ref_id)

        event = _emit(self._event_spine, "domain_pack_routing_applied", {
            "scope": scope.value,
            "routing_rule_count": len(rules),
            "has_escalation_profile": escalation is not None,
        }, scope_ref_id or "domain-routing")

        return {
            "routing_rules": rules,
            "escalation_profile": escalation,
            "event": event,
        }

    def apply_to_memory_mesh(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> dict[str, Any]:
        """Resolve memory rules for memory mesh configuration."""
        rules = self._pack_engine.resolve_memory_rules(scope, scope_ref_id)

        event = _emit(self._event_spine, "domain_pack_memory_applied", {
            "scope": scope.value,
            "memory_rule_count": len(rules),
        }, scope_ref_id or "domain-memory")

        return {
            "memory_rules": rules,
            "event": event,
        }

    def apply_to_simulation(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> dict[str, Any]:
        """Resolve simulation profile for domain-specific risk weighting."""
        profile = self._pack_engine.resolve_simulation_profile(scope, scope_ref_id)

        event = _emit(self._event_spine, "domain_pack_simulation_applied", {
            "scope": scope.value,
            "has_profile": profile is not None,
        }, scope_ref_id or "domain-simulation")

        return {
            "simulation_profile": profile,
            "event": event,
        }

    def apply_to_utility(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> dict[str, Any]:
        """Resolve utility profile for domain-specific tradeoff defaults."""
        profile = self._pack_engine.resolve_utility_profile(scope, scope_ref_id)

        event = _emit(self._event_spine, "domain_pack_utility_applied", {
            "scope": scope.value,
            "has_profile": profile is not None,
        }, scope_ref_id or "domain-utility")

        return {
            "utility_profile": profile,
            "event": event,
        }

    def apply_to_governance(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> dict[str, Any]:
        """Resolve governance-relevant rules for domain-specific thresholds."""
        all_rules = self._pack_engine.resolve_extraction_rules(scope, scope_ref_id)
        gov_rules = [
            r for r in all_rules
            if r.commitment_type in ("approval", "review", "governance")
        ]

        event = _emit(self._event_spine, "domain_pack_governance_applied", {
            "scope": scope.value,
            "governance_rule_count": len(gov_rules),
        }, scope_ref_id or "domain-governance")

        return {
            "governance_rules": tuple(gov_rules),
            "event": event,
        }

    def apply_to_benchmarking(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> dict[str, Any]:
        """Resolve benchmark profile for domain-specific suite selection."""
        profile = self._pack_engine.resolve_benchmark_profile(scope, scope_ref_id)

        event = _emit(self._event_spine, "domain_pack_benchmark_applied", {
            "scope": scope.value,
            "has_profile": profile is not None,
            "suite_count": len(profile.suite_ids) if profile else 0,
            "adversarial_count": len(profile.adversarial_categories) if profile else 0,
        }, scope_ref_id or "domain-benchmark")

        return {
            "benchmark_profile": profile,
            "event": event,
        }

    # -----------------------------------------------------------------------
    # Memory integration
    # -----------------------------------------------------------------------

    def remember_pack_activation(
        self,
        pack_id: str,
        activation_reason: str = "",
        tags: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Record a pack activation decision in memory."""
        pack = self._pack_engine.get_pack(pack_id)
        now = _now_iso()
        mem = MemoryRecord(
            memory_id=stable_identifier("pack-mem", {"pack_id": pack_id, "ts": now}),
            memory_type=MemoryType.DECISION,
            scope=MemoryScope.DOMAIN,
            scope_ref_id=pack_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Domain pack activation: {pack.domain_name}",
            content={
                "pack_id": pack_id,
                "domain_name": pack.domain_name,
                "status": pack.status.value,
                "version": pack.version,
                "scope": pack.scope.value,
                "activation_reason": activation_reason,
            },
            source_ids=(pack_id,),
            tags=("domain_pack",) + tags,
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory_engine.add_memory(mem)

        event = _emit(self._event_spine, "domain_pack_remembered", {
            "pack_id": pack_id,
        }, pack_id)

        return {
            "memory": mem,
            "event": event,
        }
