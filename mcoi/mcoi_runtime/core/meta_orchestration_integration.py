"""Purpose: meta-orchestration integration bridge.
Governance scope: composing meta-orchestration with service-to-campaign,
    case-to-remediation, contract-to-billing, release-to-marketplace,
    continuity-to-customer, program-to-reporting flows;
    memory mesh and graph attachment.
Dependencies: meta_orchestration engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every orchestration action emits events.
  - Orchestration state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.meta_orchestration import (
    CoordinationMode,
    CompositionScope,
    OrchestrationStepKind,
)
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .meta_orchestration import MetaOrchestrationEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-orchint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class MetaOrchestrationIntegration:
    """Integration bridge for meta-orchestration with platform layers."""

    def __init__(
        self,
        orchestration_engine: MetaOrchestrationEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(orchestration_engine, MetaOrchestrationEngine):
            raise RuntimeCoreInvariantError(
                "orchestration_engine must be a MetaOrchestrationEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._orchestration = orchestration_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Orchestrate service → campaign
    # ------------------------------------------------------------------

    def orchestrate_service_to_campaign(
        self,
        plan_id: str,
        tenant_id: str,
        service_ref: str,
        campaign_ref: str,
    ) -> dict[str, Any]:
        plan = self._orchestration.register_plan(
            plan_id=plan_id,
            tenant_id=tenant_id,
            display_name=f"Service to Campaign: {service_ref} → {campaign_ref}",
            coordination_mode=CoordinationMode.SEQUENTIAL,
            scope=CompositionScope.SERVICE,
        )
        s1 = self._orchestration.register_step(
            step_id=f"{plan_id}-svc", plan_id=plan_id, tenant_id=tenant_id,
            display_name="Fulfill service request", kind=OrchestrationStepKind.INVOKE,
            target_runtime="service_catalog", target_action="fulfill", sequence_order=0,
        )
        s2 = self._orchestration.register_step(
            step_id=f"{plan_id}-camp", plan_id=plan_id, tenant_id=tenant_id,
            display_name="Execute campaign", kind=OrchestrationStepKind.INVOKE,
            target_runtime="campaign", target_action="execute", sequence_order=1,
        )
        self._orchestration.add_dependency(
            dependency_id=f"{plan_id}-dep1", plan_id=plan_id, tenant_id=tenant_id,
            from_step_id=s1.step_id, to_step_id=s2.step_id,
        )
        _emit(self._events, "orchestrate_service_to_campaign", {
            "plan_id": plan_id, "service_ref": service_ref, "campaign_ref": campaign_ref,
        }, plan_id)
        return {
            "plan_id": plan.plan_id,
            "tenant_id": tenant_id,
            "service_ref": service_ref,
            "campaign_ref": campaign_ref,
            "step_count": 2,
            "coordination_mode": plan.coordination_mode.value,
            "source_type": "service_to_campaign",
        }

    # ------------------------------------------------------------------
    # Orchestrate case → remediation
    # ------------------------------------------------------------------

    def orchestrate_case_to_remediation(
        self,
        plan_id: str,
        tenant_id: str,
        case_ref: str,
        remediation_ref: str,
    ) -> dict[str, Any]:
        plan = self._orchestration.register_plan(
            plan_id=plan_id,
            tenant_id=tenant_id,
            display_name=f"Case to Remediation: {case_ref} → {remediation_ref}",
            coordination_mode=CoordinationMode.SEQUENTIAL,
            scope=CompositionScope.CASE,
        )
        s1 = self._orchestration.register_step(
            step_id=f"{plan_id}-case", plan_id=plan_id, tenant_id=tenant_id,
            display_name="Review case", kind=OrchestrationStepKind.GATE,
            target_runtime="case", target_action="review", sequence_order=0,
        )
        s2 = self._orchestration.register_step(
            step_id=f"{plan_id}-rem", plan_id=plan_id, tenant_id=tenant_id,
            display_name="Execute remediation", kind=OrchestrationStepKind.INVOKE,
            target_runtime="remediation", target_action="execute", sequence_order=1,
        )
        self._orchestration.add_dependency(
            dependency_id=f"{plan_id}-dep1", plan_id=plan_id, tenant_id=tenant_id,
            from_step_id=s1.step_id, to_step_id=s2.step_id,
        )
        _emit(self._events, "orchestrate_case_to_remediation", {
            "plan_id": plan_id, "case_ref": case_ref, "remediation_ref": remediation_ref,
        }, plan_id)
        return {
            "plan_id": plan.plan_id,
            "tenant_id": tenant_id,
            "case_ref": case_ref,
            "remediation_ref": remediation_ref,
            "step_count": 2,
            "coordination_mode": plan.coordination_mode.value,
            "source_type": "case_to_remediation",
        }

    # ------------------------------------------------------------------
    # Orchestrate contract → billing
    # ------------------------------------------------------------------

    def orchestrate_contract_to_billing(
        self,
        plan_id: str,
        tenant_id: str,
        contract_ref: str,
        billing_ref: str,
    ) -> dict[str, Any]:
        plan = self._orchestration.register_plan(
            plan_id=plan_id,
            tenant_id=tenant_id,
            display_name=f"Contract to Billing: {contract_ref} → {billing_ref}",
            coordination_mode=CoordinationMode.SEQUENTIAL,
            scope=CompositionScope.TENANT,
        )
        s1 = self._orchestration.register_step(
            step_id=f"{plan_id}-contract", plan_id=plan_id, tenant_id=tenant_id,
            display_name="Validate contract", kind=OrchestrationStepKind.GATE,
            target_runtime="contract", target_action="validate", sequence_order=0,
        )
        s2 = self._orchestration.register_step(
            step_id=f"{plan_id}-billing", plan_id=plan_id, tenant_id=tenant_id,
            display_name="Create billing", kind=OrchestrationStepKind.INVOKE,
            target_runtime="billing", target_action="create_invoice", sequence_order=1,
        )
        self._orchestration.add_dependency(
            dependency_id=f"{plan_id}-dep1", plan_id=plan_id, tenant_id=tenant_id,
            from_step_id=s1.step_id, to_step_id=s2.step_id,
        )
        _emit(self._events, "orchestrate_contract_to_billing", {
            "plan_id": plan_id, "contract_ref": contract_ref, "billing_ref": billing_ref,
        }, plan_id)
        return {
            "plan_id": plan.plan_id,
            "tenant_id": tenant_id,
            "contract_ref": contract_ref,
            "billing_ref": billing_ref,
            "step_count": 2,
            "coordination_mode": plan.coordination_mode.value,
            "source_type": "contract_to_billing",
        }

    # ------------------------------------------------------------------
    # Orchestrate release → marketplace
    # ------------------------------------------------------------------

    def orchestrate_release_to_marketplace(
        self,
        plan_id: str,
        tenant_id: str,
        release_ref: str,
        offering_ref: str,
    ) -> dict[str, Any]:
        plan = self._orchestration.register_plan(
            plan_id=plan_id,
            tenant_id=tenant_id,
            display_name=f"Release to Marketplace: {release_ref} → {offering_ref}",
            coordination_mode=CoordinationMode.SEQUENTIAL,
            scope=CompositionScope.PROGRAM,
        )
        s1 = self._orchestration.register_step(
            step_id=f"{plan_id}-release", plan_id=plan_id, tenant_id=tenant_id,
            display_name="Promote release", kind=OrchestrationStepKind.GATE,
            target_runtime="product_ops", target_action="promote", sequence_order=0,
        )
        s2 = self._orchestration.register_step(
            step_id=f"{plan_id}-mkt", plan_id=plan_id, tenant_id=tenant_id,
            display_name="Activate offering", kind=OrchestrationStepKind.INVOKE,
            target_runtime="marketplace", target_action="activate", sequence_order=1,
        )
        self._orchestration.add_dependency(
            dependency_id=f"{plan_id}-dep1", plan_id=plan_id, tenant_id=tenant_id,
            from_step_id=s1.step_id, to_step_id=s2.step_id,
        )
        _emit(self._events, "orchestrate_release_to_marketplace", {
            "plan_id": plan_id, "release_ref": release_ref, "offering_ref": offering_ref,
        }, plan_id)
        return {
            "plan_id": plan.plan_id,
            "tenant_id": tenant_id,
            "release_ref": release_ref,
            "offering_ref": offering_ref,
            "step_count": 2,
            "coordination_mode": plan.coordination_mode.value,
            "source_type": "release_to_marketplace",
        }

    # ------------------------------------------------------------------
    # Orchestrate continuity → customer
    # ------------------------------------------------------------------

    def orchestrate_continuity_to_customer(
        self,
        plan_id: str,
        tenant_id: str,
        continuity_ref: str,
        customer_ref: str,
    ) -> dict[str, Any]:
        plan = self._orchestration.register_plan(
            plan_id=plan_id,
            tenant_id=tenant_id,
            display_name=f"Continuity to Customer: {continuity_ref} → {customer_ref}",
            coordination_mode=CoordinationMode.FALLBACK,
            scope=CompositionScope.TENANT,
        )
        s1 = self._orchestration.register_step(
            step_id=f"{plan_id}-cont", plan_id=plan_id, tenant_id=tenant_id,
            display_name="Assess continuity impact", kind=OrchestrationStepKind.INVOKE,
            target_runtime="continuity", target_action="assess", sequence_order=0,
        )
        s2 = self._orchestration.register_step(
            step_id=f"{plan_id}-cust", plan_id=plan_id, tenant_id=tenant_id,
            display_name="Update customer health", kind=OrchestrationStepKind.INVOKE,
            target_runtime="customer", target_action="update_health", sequence_order=1,
        )
        self._orchestration.add_dependency(
            dependency_id=f"{plan_id}-dep1", plan_id=plan_id, tenant_id=tenant_id,
            from_step_id=s1.step_id, to_step_id=s2.step_id,
        )
        _emit(self._events, "orchestrate_continuity_to_customer", {
            "plan_id": plan_id, "continuity_ref": continuity_ref, "customer_ref": customer_ref,
        }, plan_id)
        return {
            "plan_id": plan.plan_id,
            "tenant_id": tenant_id,
            "continuity_ref": continuity_ref,
            "customer_ref": customer_ref,
            "step_count": 2,
            "coordination_mode": plan.coordination_mode.value,
            "source_type": "continuity_to_customer",
        }

    # ------------------------------------------------------------------
    # Orchestrate program → reporting
    # ------------------------------------------------------------------

    def orchestrate_program_to_reporting(
        self,
        plan_id: str,
        tenant_id: str,
        program_ref: str,
        reporting_ref: str,
    ) -> dict[str, Any]:
        plan = self._orchestration.register_plan(
            plan_id=plan_id,
            tenant_id=tenant_id,
            display_name=f"Program to Reporting: {program_ref} → {reporting_ref}",
            coordination_mode=CoordinationMode.PARALLEL,
            scope=CompositionScope.PROGRAM,
        )
        s1 = self._orchestration.register_step(
            step_id=f"{plan_id}-prog", plan_id=plan_id, tenant_id=tenant_id,
            display_name="Gather program data", kind=OrchestrationStepKind.INVOKE,
            target_runtime="program", target_action="gather", sequence_order=0,
        )
        s2 = self._orchestration.register_step(
            step_id=f"{plan_id}-report", plan_id=plan_id, tenant_id=tenant_id,
            display_name="Generate report", kind=OrchestrationStepKind.INVOKE,
            target_runtime="reporting", target_action="generate", sequence_order=1,
        )
        self._orchestration.add_dependency(
            dependency_id=f"{plan_id}-dep1", plan_id=plan_id, tenant_id=tenant_id,
            from_step_id=s1.step_id, to_step_id=s2.step_id,
        )
        _emit(self._events, "orchestrate_program_to_reporting", {
            "plan_id": plan_id, "program_ref": program_ref, "reporting_ref": reporting_ref,
        }, plan_id)
        return {
            "plan_id": plan.plan_id,
            "tenant_id": tenant_id,
            "program_ref": program_ref,
            "reporting_ref": reporting_ref,
            "step_count": 2,
            "coordination_mode": plan.coordination_mode.value,
            "source_type": "program_to_reporting",
        }

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_orchestration_to_memory_mesh(
        self, scope_ref_id: str
    ) -> MemoryRecord:
        now = _now_iso()
        snap = self._orchestration.orchestration_snapshot(
            snapshot_id=stable_identifier("snap-orch", {"scope": scope_ref_id, "ts": now}),
            tenant_id=scope_ref_id,
        )
        content = {
            "total_plans": snap.total_plans,
            "active_plans": snap.active_plans,
            "total_steps": snap.total_steps,
            "completed_steps": snap.completed_steps,
            "failed_steps": snap.failed_steps,
            "total_traces": snap.total_traces,
            "total_violations": snap.total_violations,
        }
        mem = MemoryRecord(
            memory_id=stable_identifier("mem-orch", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)}),
            scope_ref_id=scope_ref_id,
            title="Meta-orchestration state",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("meta_orchestration", "composition", "cross_runtime"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)
        _emit(self._events, "attach_orchestration_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return mem

    # ------------------------------------------------------------------
    # Graph attachment
    # ------------------------------------------------------------------

    def attach_orchestration_to_graph(
        self, scope_ref_id: str
    ) -> dict[str, Any]:
        snap = self._orchestration.orchestration_snapshot(
            snapshot_id=stable_identifier("gsnap-orch", {"scope": scope_ref_id, "ts": _now_iso()}),
            tenant_id=scope_ref_id,
        )
        return {
            "scope_ref_id": scope_ref_id,
            "total_plans": snap.total_plans,
            "active_plans": snap.active_plans,
            "total_steps": snap.total_steps,
            "completed_steps": snap.completed_steps,
            "failed_steps": snap.failed_steps,
            "total_traces": snap.total_traces,
            "total_violations": snap.total_violations,
        }
