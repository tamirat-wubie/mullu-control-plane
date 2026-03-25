"""Purpose: external execution integration bridge.
Governance scope: connects external execution engine to service requests,
    orchestration steps, remediation, procurement, marketplace, and operator
    workspace runtimes.
Dependencies: external_execution engine, event_spine, memory_mesh.
Invariants:
  - Constructor validates all three engine types.
  - All outputs are frozen dicts or MemoryRecord instances.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.external_execution import (
    ExecutionKind,
    ExecutionRiskLevel,
    SandboxDisposition,
)
from mcoi_runtime.contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.external_execution import ExternalExecutionEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict[str, Any], cid: str) -> None:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-exi", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class ExternalExecutionIntegration:
    """Integration bridge for external execution runtime."""

    def __init__(
        self,
        execution_engine: ExternalExecutionEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(execution_engine, ExternalExecutionEngine):
            raise RuntimeCoreInvariantError("execution_engine must be an ExternalExecutionEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._exec = execution_engine
        self._events = event_spine
        self._memory = memory_engine

    # -- Bridge methods --

    def execute_from_service_request(
        self,
        request_id: str,
        tenant_id: str,
        target_id: str,
        service_ref: str = "none",
        kind: ExecutionKind = ExecutionKind.TOOL,
        sandbox: SandboxDisposition = SandboxDisposition.SANDBOXED,
        risk_level: ExecutionRiskLevel = ExecutionRiskLevel.LOW,
    ) -> dict[str, Any]:
        req = self._exec.request_execution(
            request_id, tenant_id, target_id,
            kind=kind, sandbox=sandbox, risk_level=risk_level,
        )
        _emit(self._events, "execute_from_service_request", {
            "request_id": request_id, "service_ref": service_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "tenant_id": tenant_id,
            "target_id": target_id,
            "service_ref": service_ref,
            "status": req.status.value,
            "sandbox": req.sandbox.value,
            "risk_level": req.risk_level.value,
            "source_type": "service_request",
        }

    def execute_from_orchestration_step(
        self,
        request_id: str,
        tenant_id: str,
        target_id: str,
        step_ref: str = "none",
        kind: ExecutionKind = ExecutionKind.AGENT,
        sandbox: SandboxDisposition = SandboxDisposition.ISOLATED,
        risk_level: ExecutionRiskLevel = ExecutionRiskLevel.MEDIUM,
    ) -> dict[str, Any]:
        req = self._exec.request_execution(
            request_id, tenant_id, target_id,
            kind=kind, sandbox=sandbox, risk_level=risk_level,
        )
        _emit(self._events, "execute_from_orchestration_step", {
            "request_id": request_id, "step_ref": step_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "tenant_id": tenant_id,
            "target_id": target_id,
            "step_ref": step_ref,
            "status": req.status.value,
            "sandbox": req.sandbox.value,
            "risk_level": req.risk_level.value,
            "source_type": "orchestration_step",
        }

    def execute_from_remediation(
        self,
        request_id: str,
        tenant_id: str,
        target_id: str,
        remediation_ref: str = "none",
        kind: ExecutionKind = ExecutionKind.SCRIPT,
        sandbox: SandboxDisposition = SandboxDisposition.SANDBOXED,
        risk_level: ExecutionRiskLevel = ExecutionRiskLevel.MEDIUM,
    ) -> dict[str, Any]:
        req = self._exec.request_execution(
            request_id, tenant_id, target_id,
            kind=kind, sandbox=sandbox, risk_level=risk_level,
        )
        _emit(self._events, "execute_from_remediation", {
            "request_id": request_id, "remediation_ref": remediation_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "tenant_id": tenant_id,
            "target_id": target_id,
            "remediation_ref": remediation_ref,
            "status": req.status.value,
            "sandbox": req.sandbox.value,
            "risk_level": req.risk_level.value,
            "source_type": "remediation",
        }

    def execute_from_procurement_need(
        self,
        request_id: str,
        tenant_id: str,
        target_id: str,
        procurement_ref: str = "none",
        kind: ExecutionKind = ExecutionKind.API_CALL,
        sandbox: SandboxDisposition = SandboxDisposition.RESTRICTED,
        risk_level: ExecutionRiskLevel = ExecutionRiskLevel.LOW,
    ) -> dict[str, Any]:
        req = self._exec.request_execution(
            request_id, tenant_id, target_id,
            kind=kind, sandbox=sandbox, risk_level=risk_level,
        )
        _emit(self._events, "execute_from_procurement_need", {
            "request_id": request_id, "procurement_ref": procurement_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "tenant_id": tenant_id,
            "target_id": target_id,
            "procurement_ref": procurement_ref,
            "status": req.status.value,
            "sandbox": req.sandbox.value,
            "risk_level": req.risk_level.value,
            "source_type": "procurement_need",
        }

    def execute_from_marketplace_action(
        self,
        request_id: str,
        tenant_id: str,
        target_id: str,
        marketplace_ref: str = "none",
        kind: ExecutionKind = ExecutionKind.WEBHOOK,
        sandbox: SandboxDisposition = SandboxDisposition.SANDBOXED,
        risk_level: ExecutionRiskLevel = ExecutionRiskLevel.LOW,
    ) -> dict[str, Any]:
        req = self._exec.request_execution(
            request_id, tenant_id, target_id,
            kind=kind, sandbox=sandbox, risk_level=risk_level,
        )
        _emit(self._events, "execute_from_marketplace_action", {
            "request_id": request_id, "marketplace_ref": marketplace_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "tenant_id": tenant_id,
            "target_id": target_id,
            "marketplace_ref": marketplace_ref,
            "status": req.status.value,
            "sandbox": req.sandbox.value,
            "risk_level": req.risk_level.value,
            "source_type": "marketplace_action",
        }

    def execute_from_operator_workspace(
        self,
        request_id: str,
        tenant_id: str,
        target_id: str,
        workspace_ref: str = "none",
        kind: ExecutionKind = ExecutionKind.TOOL,
        sandbox: SandboxDisposition = SandboxDisposition.SANDBOXED,
        risk_level: ExecutionRiskLevel = ExecutionRiskLevel.LOW,
    ) -> dict[str, Any]:
        req = self._exec.request_execution(
            request_id, tenant_id, target_id,
            kind=kind, sandbox=sandbox, risk_level=risk_level,
        )
        _emit(self._events, "execute_from_operator_workspace", {
            "request_id": request_id, "workspace_ref": workspace_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "tenant_id": tenant_id,
            "target_id": target_id,
            "workspace_ref": workspace_ref,
            "status": req.status.value,
            "sandbox": req.sandbox.value,
            "risk_level": req.risk_level.value,
            "source_type": "operator_workspace",
        }

    # -- Memory mesh --

    def attach_execution_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        mid = stable_identifier("mem-exec", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)})
        content = {
            "total_targets": self._exec.target_count,
            "total_requests": self._exec.request_count,
            "total_receipts": self._exec.receipt_count,
            "total_results": self._exec.result_count,
            "total_failures": self._exec.failure_count,
            "total_traces": self._exec.trace_count,
            "total_violations": self._exec.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"External execution state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("external_execution", "tool_execution", "agent_execution"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_execution_state_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return record

    # -- Graph --

    def attach_execution_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        return {
            "scope_ref_id": scope_ref_id,
            "total_targets": self._exec.target_count,
            "total_requests": self._exec.request_count,
            "total_receipts": self._exec.receipt_count,
            "total_results": self._exec.result_count,
            "total_failures": self._exec.failure_count,
            "total_traces": self._exec.trace_count,
            "total_violations": self._exec.violation_count,
        }
