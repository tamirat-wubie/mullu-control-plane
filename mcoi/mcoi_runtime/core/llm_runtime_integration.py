"""Purpose: LLM runtime integration bridge.
Governance scope: connects LLM runtime engine to service requests,
    case reviews, research, reporting, remediation, and orchestration.
Dependencies: llm_runtime engine, event_spine, memory_mesh.
Invariants:
  - Constructor validates all three engine types.
  - All outputs are frozen dicts or MemoryRecord instances.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.llm_runtime import (
    GenerationStatus,
    GroundingStatus,
)
from mcoi_runtime.contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.llm_runtime import LlmRuntimeEngine
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
        event_id=stable_identifier("evt-llmi", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class LlmRuntimeIntegration:
    """Integration bridge for LLM runtime."""

    def __init__(
        self,
        llm_engine: LlmRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(llm_engine, LlmRuntimeEngine):
            raise RuntimeCoreInvariantError("llm_engine must be a LlmRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._llm = llm_engine
        self._events = event_spine
        self._memory = memory_engine

    # -- Bridge methods --

    def generate_for_service_request(
        self,
        request_id: str,
        tenant_id: str,
        model_id: str,
        pack_id: str,
        service_ref: str = "none",
        token_budget: int = 4096,
        cost_budget: float = 1.0,
    ) -> dict[str, Any]:
        req = self._llm.request_generation(
            request_id, tenant_id, model_id, pack_id,
            token_budget=token_budget, cost_budget=cost_budget,
        )
        _emit(self._events, "generate_for_service_request", {
            "request_id": request_id, "service_ref": service_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "tenant_id": tenant_id,
            "model_id": model_id,
            "service_ref": service_ref,
            "status": req.status.value,
            "token_budget": req.token_budget,
            "cost_budget": req.cost_budget,
            "source_type": "service_request",
        }

    def generate_for_case_review(
        self,
        request_id: str,
        tenant_id: str,
        model_id: str,
        pack_id: str,
        case_ref: str = "none",
        token_budget: int = 4096,
        cost_budget: float = 1.0,
    ) -> dict[str, Any]:
        req = self._llm.request_generation(
            request_id, tenant_id, model_id, pack_id,
            token_budget=token_budget, cost_budget=cost_budget,
        )
        _emit(self._events, "generate_for_case_review", {
            "request_id": request_id, "case_ref": case_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "tenant_id": tenant_id,
            "model_id": model_id,
            "case_ref": case_ref,
            "status": req.status.value,
            "token_budget": req.token_budget,
            "cost_budget": req.cost_budget,
            "source_type": "case_review",
        }

    def generate_for_research(
        self,
        request_id: str,
        tenant_id: str,
        model_id: str,
        pack_id: str,
        research_ref: str = "none",
        token_budget: int = 8192,
        cost_budget: float = 2.0,
    ) -> dict[str, Any]:
        req = self._llm.request_generation(
            request_id, tenant_id, model_id, pack_id,
            token_budget=token_budget, cost_budget=cost_budget,
        )
        _emit(self._events, "generate_for_research", {
            "request_id": request_id, "research_ref": research_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "tenant_id": tenant_id,
            "model_id": model_id,
            "research_ref": research_ref,
            "status": req.status.value,
            "token_budget": req.token_budget,
            "cost_budget": req.cost_budget,
            "source_type": "research",
        }

    def generate_for_reporting(
        self,
        request_id: str,
        tenant_id: str,
        model_id: str,
        pack_id: str,
        report_ref: str = "none",
        token_budget: int = 4096,
        cost_budget: float = 1.0,
    ) -> dict[str, Any]:
        req = self._llm.request_generation(
            request_id, tenant_id, model_id, pack_id,
            token_budget=token_budget, cost_budget=cost_budget,
        )
        _emit(self._events, "generate_for_reporting", {
            "request_id": request_id, "report_ref": report_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "tenant_id": tenant_id,
            "model_id": model_id,
            "report_ref": report_ref,
            "status": req.status.value,
            "token_budget": req.token_budget,
            "cost_budget": req.cost_budget,
            "source_type": "reporting",
        }

    def generate_for_remediation(
        self,
        request_id: str,
        tenant_id: str,
        model_id: str,
        pack_id: str,
        remediation_ref: str = "none",
        token_budget: int = 4096,
        cost_budget: float = 1.0,
    ) -> dict[str, Any]:
        req = self._llm.request_generation(
            request_id, tenant_id, model_id, pack_id,
            token_budget=token_budget, cost_budget=cost_budget,
        )
        _emit(self._events, "generate_for_remediation", {
            "request_id": request_id, "remediation_ref": remediation_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "tenant_id": tenant_id,
            "model_id": model_id,
            "remediation_ref": remediation_ref,
            "status": req.status.value,
            "token_budget": req.token_budget,
            "cost_budget": req.cost_budget,
            "source_type": "remediation",
        }

    def generate_for_orchestration(
        self,
        request_id: str,
        tenant_id: str,
        model_id: str,
        pack_id: str,
        step_ref: str = "none",
        token_budget: int = 4096,
        cost_budget: float = 1.0,
    ) -> dict[str, Any]:
        req = self._llm.request_generation(
            request_id, tenant_id, model_id, pack_id,
            token_budget=token_budget, cost_budget=cost_budget,
        )
        _emit(self._events, "generate_for_orchestration", {
            "request_id": request_id, "step_ref": step_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "tenant_id": tenant_id,
            "model_id": model_id,
            "step_ref": step_ref,
            "status": req.status.value,
            "token_budget": req.token_budget,
            "cost_budget": req.cost_budget,
            "source_type": "orchestration",
        }

    # -- Memory mesh --

    def attach_llm_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        mid = stable_identifier("mem-llm", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)})
        content = {
            "total_models": self._llm.model_count,
            "total_routes": self._llm.route_count,
            "total_templates": self._llm.template_count,
            "total_requests": self._llm.request_count,
            "total_results": self._llm.result_count,
            "total_permissions": self._llm.permission_count,
            "total_violations": self._llm.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title="LLM runtime state",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("llm_runtime", "model_execution", "generation"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_llm_state_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return record

    # -- Graph --

    def attach_llm_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        return {
            "scope_ref_id": scope_ref_id,
            "total_models": self._llm.model_count,
            "total_routes": self._llm.route_count,
            "total_templates": self._llm.template_count,
            "total_requests": self._llm.request_count,
            "total_results": self._llm.result_count,
            "total_permissions": self._llm.permission_count,
            "total_violations": self._llm.violation_count,
        }
