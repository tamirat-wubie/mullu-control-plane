"""Purpose: observability runtime integration bridge.
Governance scope: composing observability with API, workspace, orchestration,
    continuity, financials, and service catalog; memory mesh and graph attachment.
Dependencies: observability_runtime engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every observability action emits events.
  - Observability state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.observability_runtime import AnomalySeverity, ObservabilityScope
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .observability_runtime import ObservabilityRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-obsint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ObservabilityRuntimeIntegration:
    """Integration bridge for observability with platform layers."""

    def __init__(
        self,
        observability_engine: ObservabilityRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(observability_engine, ObservabilityRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "observability_engine must be an ObservabilityRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._obs = observability_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Observe API
    # ------------------------------------------------------------------

    def observe_api(
        self,
        trace_id: str,
        tenant_id: str,
        metric_id: str,
        request_count: float = 0.0,
    ) -> dict[str, Any]:
        trace = self._obs.open_trace(trace_id, tenant_id, "API observation", "public_api")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "api_request_count", request_count,
            "public_api", ObservabilityScope.ENDPOINT,
        )
        _emit(self._events, "observe_api", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "source_runtime": "public_api",
            "metric_value": metric.value,
            "source_type": "api",
        }

    # ------------------------------------------------------------------
    # Observe workspace
    # ------------------------------------------------------------------

    def observe_workspace(
        self,
        trace_id: str,
        tenant_id: str,
        metric_id: str,
        queue_depth: float = 0.0,
    ) -> dict[str, Any]:
        trace = self._obs.open_trace(trace_id, tenant_id, "Workspace observation", "operator_workspace")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "workspace_queue_depth", queue_depth,
            "operator_workspace", ObservabilityScope.WORKSPACE,
        )
        _emit(self._events, "observe_workspace", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "source_runtime": "operator_workspace",
            "metric_value": metric.value,
            "source_type": "workspace",
        }

    # ------------------------------------------------------------------
    # Observe orchestration
    # ------------------------------------------------------------------

    def observe_orchestration(
        self,
        trace_id: str,
        tenant_id: str,
        metric_id: str,
        active_plans: float = 0.0,
    ) -> dict[str, Any]:
        trace = self._obs.open_trace(trace_id, tenant_id, "Orchestration observation", "meta_orchestration")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "orchestration_active_plans", active_plans,
            "meta_orchestration", ObservabilityScope.RUNTIME,
        )
        _emit(self._events, "observe_orchestration", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "source_runtime": "meta_orchestration",
            "metric_value": metric.value,
            "source_type": "orchestration",
        }

    # ------------------------------------------------------------------
    # Observe continuity
    # ------------------------------------------------------------------

    def observe_continuity(
        self,
        trace_id: str,
        tenant_id: str,
        metric_id: str,
        disruption_count: float = 0.0,
    ) -> dict[str, Any]:
        trace = self._obs.open_trace(trace_id, tenant_id, "Continuity observation", "continuity")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "continuity_disruption_count", disruption_count,
            "continuity", ObservabilityScope.SERVICE,
        )
        _emit(self._events, "observe_continuity", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "source_runtime": "continuity",
            "metric_value": metric.value,
            "source_type": "continuity",
        }

    # ------------------------------------------------------------------
    # Observe financials
    # ------------------------------------------------------------------

    def observe_financials(
        self,
        trace_id: str,
        tenant_id: str,
        metric_id: str,
        outstanding_amount: float = 0.0,
    ) -> dict[str, Any]:
        trace = self._obs.open_trace(trace_id, tenant_id, "Financial observation", "settlement")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "financial_outstanding_amount", outstanding_amount,
            "settlement", ObservabilityScope.TENANT,
        )
        _emit(self._events, "observe_financials", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "source_runtime": "settlement",
            "metric_value": metric.value,
            "source_type": "financials",
        }

    # ------------------------------------------------------------------
    # Observe service catalog
    # ------------------------------------------------------------------

    def observe_service_catalog(
        self,
        trace_id: str,
        tenant_id: str,
        metric_id: str,
        pending_requests: float = 0.0,
    ) -> dict[str, Any]:
        trace = self._obs.open_trace(trace_id, tenant_id, "Service catalog observation", "service_catalog")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "service_pending_requests", pending_requests,
            "service_catalog", ObservabilityScope.SERVICE,
        )
        _emit(self._events, "observe_service_catalog", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "source_runtime": "service_catalog",
            "metric_value": metric.value,
            "source_type": "service_catalog",
        }

    # ------------------------------------------------------------------
    # Observe billing
    # ------------------------------------------------------------------

    def observe_billing(
        self,
        tenant_id: str,
        billing_ref: str,
        description: str = "billing activity",
    ) -> dict[str, Any]:
        trace_id = stable_identifier("trace-billing", {"tenant": tenant_id, "ref": billing_ref})
        metric_id = stable_identifier("metric-billing", {"tenant": tenant_id, "ref": billing_ref})
        trace = self._obs.open_trace(trace_id, tenant_id, description, "billing")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "billing_activity_count", 1.0,
            "billing", ObservabilityScope.TENANT,
        )
        _emit(self._events, "observe_billing", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "billing_ref": billing_ref,
            "source_type": "billing",
            "description": description,
        }

    # ------------------------------------------------------------------
    # Observe copilot
    # ------------------------------------------------------------------

    def observe_copilot(
        self,
        tenant_id: str,
        session_ref: str,
        description: str = "copilot activity",
    ) -> dict[str, Any]:
        trace_id = stable_identifier("trace-copilot", {"tenant": tenant_id, "ref": session_ref})
        metric_id = stable_identifier("metric-copilot", {"tenant": tenant_id, "ref": session_ref})
        trace = self._obs.open_trace(trace_id, tenant_id, description, "copilot")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "copilot_session_count", 1.0,
            "copilot", ObservabilityScope.RUNTIME,
        )
        _emit(self._events, "observe_copilot", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "session_ref": session_ref,
            "source_type": "copilot",
            "description": description,
        }

    # ------------------------------------------------------------------
    # Observe LLM
    # ------------------------------------------------------------------

    def observe_llm(
        self,
        tenant_id: str,
        request_ref: str,
        description: str = "llm generation",
    ) -> dict[str, Any]:
        trace_id = stable_identifier("trace-llm", {"tenant": tenant_id, "ref": request_ref})
        metric_id = stable_identifier("metric-llm", {"tenant": tenant_id, "ref": request_ref})
        trace = self._obs.open_trace(trace_id, tenant_id, description, "llm")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "llm_generation_count", 1.0,
            "llm", ObservabilityScope.RUNTIME,
        )
        _emit(self._events, "observe_llm", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "request_ref": request_ref,
            "source_type": "llm",
            "description": description,
        }

    # ------------------------------------------------------------------
    # Observe workforce
    # ------------------------------------------------------------------

    def observe_workforce(
        self,
        tenant_id: str,
        workforce_ref: str,
        description: str = "workforce activity",
    ) -> dict[str, Any]:
        trace_id = stable_identifier("trace-workforce", {"tenant": tenant_id, "ref": workforce_ref})
        metric_id = stable_identifier("metric-workforce", {"tenant": tenant_id, "ref": workforce_ref})
        trace = self._obs.open_trace(trace_id, tenant_id, description, "workforce")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "workforce_activity_count", 1.0,
            "workforce", ObservabilityScope.SERVICE,
        )
        _emit(self._events, "observe_workforce", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "workforce_ref": workforce_ref,
            "source_type": "workforce",
            "description": description,
        }

    # ------------------------------------------------------------------
    # Observe factory
    # ------------------------------------------------------------------

    def observe_factory(
        self,
        tenant_id: str,
        factory_ref: str,
        description: str = "factory operation",
    ) -> dict[str, Any]:
        trace_id = stable_identifier("trace-factory", {"tenant": tenant_id, "ref": factory_ref})
        metric_id = stable_identifier("metric-factory", {"tenant": tenant_id, "ref": factory_ref})
        trace = self._obs.open_trace(trace_id, tenant_id, description, "factory")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "factory_operation_count", 1.0,
            "factory", ObservabilityScope.SERVICE,
        )
        _emit(self._events, "observe_factory", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "factory_ref": factory_ref,
            "source_type": "factory",
            "description": description,
        }

    # ------------------------------------------------------------------
    # Observe case
    # ------------------------------------------------------------------

    def observe_case(
        self,
        tenant_id: str,
        case_ref: str,
        description: str = "case activity",
    ) -> dict[str, Any]:
        trace_id = stable_identifier("trace-case", {"tenant": tenant_id, "ref": case_ref})
        metric_id = stable_identifier("metric-case", {"tenant": tenant_id, "ref": case_ref})
        trace = self._obs.open_trace(trace_id, tenant_id, description, "case")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "case_activity_count", 1.0,
            "case", ObservabilityScope.SERVICE,
        )
        _emit(self._events, "observe_case", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "case_ref": case_ref,
            "source_type": "case",
            "description": description,
        }

    # ------------------------------------------------------------------
    # Observe remediation
    # ------------------------------------------------------------------

    def observe_remediation(
        self,
        tenant_id: str,
        remediation_ref: str,
        description: str = "remediation activity",
    ) -> dict[str, Any]:
        trace_id = stable_identifier("trace-remediation", {"tenant": tenant_id, "ref": remediation_ref})
        metric_id = stable_identifier("metric-remediation", {"tenant": tenant_id, "ref": remediation_ref})
        trace = self._obs.open_trace(trace_id, tenant_id, description, "remediation")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "remediation_activity_count", 1.0,
            "remediation", ObservabilityScope.SERVICE,
        )
        _emit(self._events, "observe_remediation", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "remediation_ref": remediation_ref,
            "source_type": "remediation",
            "description": description,
        }

    # ------------------------------------------------------------------
    # Observe access
    # ------------------------------------------------------------------

    def observe_access(
        self,
        tenant_id: str,
        identity_ref: str,
        description: str = "access activity",
    ) -> dict[str, Any]:
        trace_id = stable_identifier("trace-access", {"tenant": tenant_id, "ref": identity_ref})
        metric_id = stable_identifier("metric-access", {"tenant": tenant_id, "ref": identity_ref})
        trace = self._obs.open_trace(trace_id, tenant_id, description, "access")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "access_activity_count", 1.0,
            "access", ObservabilityScope.ENDPOINT,
        )
        _emit(self._events, "observe_access", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "identity_ref": identity_ref,
            "source_type": "access",
            "description": description,
        }

    # ------------------------------------------------------------------
    # Observe customer
    # ------------------------------------------------------------------

    def observe_customer(
        self,
        tenant_id: str,
        customer_ref: str,
        description: str = "customer activity",
    ) -> dict[str, Any]:
        trace_id = stable_identifier("trace-customer", {"tenant": tenant_id, "ref": customer_ref})
        metric_id = stable_identifier("metric-customer", {"tenant": tenant_id, "ref": customer_ref})
        trace = self._obs.open_trace(trace_id, tenant_id, description, "customer")
        metric = self._obs.record_metric(
            metric_id, tenant_id, "customer_activity_count", 1.0,
            "customer", ObservabilityScope.TENANT,
        )
        _emit(self._events, "observe_customer", {"trace_id": trace_id, "metric_id": metric_id}, trace_id)
        return {
            "trace_id": trace.trace_id,
            "metric_id": metric.metric_id,
            "tenant_id": tenant_id,
            "customer_ref": customer_ref,
            "source_type": "customer",
            "description": description,
        }

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_observability_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        snap = self._obs.observability_snapshot(
            snapshot_id=stable_identifier("snap-obs", {"scope": scope_ref_id, "ts": now}),
            tenant_id=scope_ref_id,
        )
        content = {
            "total_metrics": snap.total_metrics,
            "total_logs": snap.total_logs,
            "total_traces": snap.total_traces,
            "total_spans": snap.total_spans,
            "total_anomalies": snap.total_anomalies,
            "total_debug_sessions": snap.total_debug_sessions,
            "total_violations": snap.total_violations,
        }
        mem = MemoryRecord(
            memory_id=stable_identifier("mem-obs", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)}),
            scope_ref_id=scope_ref_id,
            title="Observability state",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("observability", "telemetry", "debug"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)
        _emit(self._events, "attach_observability_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return mem

    # ------------------------------------------------------------------
    # Graph attachment
    # ------------------------------------------------------------------

    def attach_observability_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        snap = self._obs.observability_snapshot(
            snapshot_id=stable_identifier("gsnap-obs", {"scope": scope_ref_id, "ts": _now_iso()}),
            tenant_id=scope_ref_id,
        )
        return {
            "scope_ref_id": scope_ref_id,
            "total_metrics": snap.total_metrics,
            "total_logs": snap.total_logs,
            "total_traces": snap.total_traces,
            "total_spans": snap.total_spans,
            "total_anomalies": snap.total_anomalies,
            "total_debug_sessions": snap.total_debug_sessions,
            "total_violations": snap.total_violations,
        }
