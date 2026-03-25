"""Purpose: constitutional governance integration bridge.
Governance scope: composing constitutional governance with service requests,
    releases, settlements, marketplace offerings, human workflows, and external
    connectors; memory mesh and graph attachment.
Dependencies: constitutional_governance engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every governance action emits events.
  - Constitutional state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .constitutional_governance import ConstitutionalGovernanceEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-cgovint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ConstitutionalGovernanceIntegration:
    """Integration bridge for constitutional governance with platform layers."""

    def __init__(
        self,
        governance_engine: ConstitutionalGovernanceEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(governance_engine, ConstitutionalGovernanceEngine):
            raise RuntimeCoreInvariantError(
                "governance_engine must be a ConstitutionalGovernanceEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._governance = governance_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Govern service request
    # ------------------------------------------------------------------

    def govern_service_request(
        self,
        decision_id: str,
        tenant_id: str,
        service_ref: str,
        action: str = "fulfill",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="service_catalog",
            target_action=action,
        )
        _emit(self._events, "govern_service_request", {
            "decision_id": decision_id, "service_ref": service_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "service_ref": service_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "service_request",
        }

    # ------------------------------------------------------------------
    # Govern release
    # ------------------------------------------------------------------

    def govern_release(
        self,
        decision_id: str,
        tenant_id: str,
        release_ref: str,
        action: str = "promote",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="product_ops",
            target_action=action,
        )
        _emit(self._events, "govern_release", {
            "decision_id": decision_id, "release_ref": release_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "release_ref": release_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "release",
        }

    # ------------------------------------------------------------------
    # Govern settlement
    # ------------------------------------------------------------------

    def govern_settlement(
        self,
        decision_id: str,
        tenant_id: str,
        settlement_ref: str,
        action: str = "settle",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="settlement",
            target_action=action,
        )
        _emit(self._events, "govern_settlement", {
            "decision_id": decision_id, "settlement_ref": settlement_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "settlement_ref": settlement_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "settlement",
        }

    # ------------------------------------------------------------------
    # Govern marketplace offering
    # ------------------------------------------------------------------

    def govern_marketplace_offering(
        self,
        decision_id: str,
        tenant_id: str,
        offering_ref: str,
        action: str = "activate",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="marketplace",
            target_action=action,
        )
        _emit(self._events, "govern_marketplace_offering", {
            "decision_id": decision_id, "offering_ref": offering_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "offering_ref": offering_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "marketplace_offering",
        }

    # ------------------------------------------------------------------
    # Govern human workflow
    # ------------------------------------------------------------------

    def govern_human_workflow(
        self,
        decision_id: str,
        tenant_id: str,
        workflow_ref: str,
        action: str = "approve",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="human_workflow",
            target_action=action,
        )
        _emit(self._events, "govern_human_workflow", {
            "decision_id": decision_id, "workflow_ref": workflow_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "workflow_ref": workflow_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "human_workflow",
        }

    # ------------------------------------------------------------------
    # Govern external connector action
    # ------------------------------------------------------------------

    def govern_external_connector_action(
        self,
        decision_id: str,
        tenant_id: str,
        connector_ref: str,
        action: str = "execute",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="connector",
            target_action=action,
        )
        _emit(self._events, "govern_external_connector_action", {
            "decision_id": decision_id, "connector_ref": connector_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "connector_ref": connector_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "external_connector",
        }

    # ------------------------------------------------------------------
    # Govern billing action
    # ------------------------------------------------------------------

    def govern_billing_action(
        self,
        decision_id: str,
        tenant_id: str,
        billing_ref: str,
        action: str = "billing_action",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="billing",
            target_action=action,
        )
        _emit(self._events, "govern_billing_action", {
            "decision_id": decision_id, "billing_ref": billing_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "billing_ref": billing_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "billing_action",
        }

    # ------------------------------------------------------------------
    # Govern financial action
    # ------------------------------------------------------------------

    def govern_financial_action(
        self,
        decision_id: str,
        tenant_id: str,
        financial_ref: str,
        action: str = "financial_action",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="financial",
            target_action=action,
        )
        _emit(self._events, "govern_financial_action", {
            "decision_id": decision_id, "financial_ref": financial_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "financial_ref": financial_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "financial_action",
        }

    # ------------------------------------------------------------------
    # Govern copilot action
    # ------------------------------------------------------------------

    def govern_copilot_action(
        self,
        decision_id: str,
        tenant_id: str,
        session_ref: str,
        action: str = "copilot_action",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="copilot",
            target_action=action,
        )
        _emit(self._events, "govern_copilot_action", {
            "decision_id": decision_id, "session_ref": session_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "session_ref": session_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "copilot_action",
        }

    # ------------------------------------------------------------------
    # Govern LLM generation
    # ------------------------------------------------------------------

    def govern_llm_generation(
        self,
        decision_id: str,
        tenant_id: str,
        request_ref: str,
        action: str = "llm_generation",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="llm",
            target_action=action,
        )
        _emit(self._events, "govern_llm_generation", {
            "decision_id": decision_id, "request_ref": request_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "request_ref": request_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "llm_generation",
        }

    # ------------------------------------------------------------------
    # Govern workforce action
    # ------------------------------------------------------------------

    def govern_workforce_action(
        self,
        decision_id: str,
        tenant_id: str,
        workforce_ref: str,
        action: str = "workforce_action",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="workforce",
            target_action=action,
        )
        _emit(self._events, "govern_workforce_action", {
            "decision_id": decision_id, "workforce_ref": workforce_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "workforce_ref": workforce_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "workforce_action",
        }

    # ------------------------------------------------------------------
    # Govern access action
    # ------------------------------------------------------------------

    def govern_access_action(
        self,
        decision_id: str,
        tenant_id: str,
        identity_ref: str,
        action: str = "access_action",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="access",
            target_action=action,
        )
        _emit(self._events, "govern_access_action", {
            "decision_id": decision_id, "identity_ref": identity_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "identity_ref": identity_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "access_action",
        }

    # ------------------------------------------------------------------
    # Govern executive action
    # ------------------------------------------------------------------

    def govern_executive_action(
        self,
        decision_id: str,
        tenant_id: str,
        directive_ref: str,
        action: str = "executive_action",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="executive",
            target_action=action,
        )
        _emit(self._events, "govern_executive_action", {
            "decision_id": decision_id, "directive_ref": directive_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "directive_ref": directive_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "executive_action",
        }

    # ------------------------------------------------------------------
    # Govern factory action
    # ------------------------------------------------------------------

    def govern_factory_action(
        self,
        decision_id: str,
        tenant_id: str,
        factory_ref: str,
        action: str = "factory_action",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="factory",
            target_action=action,
        )
        _emit(self._events, "govern_factory_action", {
            "decision_id": decision_id, "factory_ref": factory_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "factory_ref": factory_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "factory_action",
        }

    # ------------------------------------------------------------------
    # Govern customer action
    # ------------------------------------------------------------------

    def govern_customer_action(
        self,
        decision_id: str,
        tenant_id: str,
        customer_ref: str,
        action: str = "customer_action",
    ) -> dict[str, Any]:
        decision = self._governance.evaluate_global_policy(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime="customer",
            target_action=action,
        )
        _emit(self._events, "govern_customer_action", {
            "decision_id": decision_id, "customer_ref": customer_ref,
        }, decision_id)
        return {
            "decision_id": decision.decision_id,
            "tenant_id": decision.tenant_id,
            "customer_ref": customer_ref,
            "disposition": decision.disposition.value,
            "matched_rule_id": decision.matched_rule_id,
            "emergency_mode": decision.emergency_mode.value,
            "source_type": "customer_action",
        }

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_constitution_state_to_memory_mesh(
        self, scope_ref_id: str
    ) -> MemoryRecord:
        now = _now_iso()
        snap = self._governance.constitution_snapshot(
            snapshot_id=stable_identifier("snap-cgov", {"scope": scope_ref_id, "ts": now}),
            tenant_id=scope_ref_id,
        )
        content = {
            "total_rules": snap.total_rules,
            "active_rules": snap.active_rules,
            "total_bundles": snap.total_bundles,
            "total_overrides": snap.total_overrides,
            "total_decisions": snap.total_decisions,
            "total_violations": snap.total_violations,
            "emergency_mode": snap.emergency_mode.value,
        }
        mem = MemoryRecord(
            memory_id=stable_identifier("mem-cgov", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)}),
            scope_ref_id=scope_ref_id,
            title=f"Constitutional governance state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("constitutional_governance", "global_policy", "compliance"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)
        _emit(self._events, "attach_constitution_state_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return mem

    # ------------------------------------------------------------------
    # Graph attachment
    # ------------------------------------------------------------------

    def attach_constitution_state_to_graph(
        self, scope_ref_id: str
    ) -> dict[str, Any]:
        snap = self._governance.constitution_snapshot(
            snapshot_id=stable_identifier("gsnap-cgov", {"scope": scope_ref_id, "ts": _now_iso()}),
            tenant_id=scope_ref_id,
        )
        return {
            "scope_ref_id": scope_ref_id,
            "total_rules": snap.total_rules,
            "active_rules": snap.active_rules,
            "total_bundles": snap.total_bundles,
            "total_overrides": snap.total_overrides,
            "total_decisions": snap.total_decisions,
            "total_violations": snap.total_violations,
            "emergency_mode": snap.emergency_mode.value,
        }
