"""Purpose: product ops runtime integration bridge.
Governance scope: composing product ops runtime with assurance, continuity,
    service health, customer impact, change runtime; memory mesh and graph.
Dependencies: product_ops engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every release action emits events.
  - Release state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.product_ops import ReleaseKind
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .product_ops import ProductOpsEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-popsint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ProductOpsIntegration:
    """Integration bridge for product ops runtime with platform layers."""

    def __init__(
        self,
        ops_engine: ProductOpsEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(ops_engine, ProductOpsEngine):
            raise RuntimeCoreInvariantError(
                "ops_engine must be a ProductOpsEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._ops = ops_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Release from platform layers
    # ------------------------------------------------------------------

    def release_from_assurance(
        self,
        release_id: str,
        gate_id: str,
        version_id: str,
        tenant_id: str,
        assurance_ref: str,
        passed: bool,
        kind: ReleaseKind = ReleaseKind.MINOR,
        target_environment: str = "staging",
    ) -> dict[str, Any]:
        rel = self._ops.create_release(
            release_id=release_id, version_id=version_id, tenant_id=tenant_id,
            kind=kind, target_environment=target_environment,
        )
        gate = self._ops.evaluate_gate(
            gate_id=gate_id, release_id=release_id, tenant_id=tenant_id,
            gate_name="assurance", passed=passed, reason="assurance gate",
        )
        _emit(self._events, "release_from_assurance", {
            "release_id": release_id, "assurance_ref": assurance_ref, "passed": passed,
        }, release_id)
        return {
            "release_id": rel.release_id,
            "gate_id": gate.gate_id,
            "version_id": version_id,
            "tenant_id": tenant_id,
            "assurance_ref": assurance_ref,
            "passed": passed,
            "source_type": "assurance",
        }

    def release_from_continuity(
        self,
        release_id: str,
        gate_id: str,
        version_id: str,
        tenant_id: str,
        continuity_ref: str,
        passed: bool,
        kind: ReleaseKind = ReleaseKind.PATCH,
        target_environment: str = "staging",
    ) -> dict[str, Any]:
        rel = self._ops.create_release(
            release_id=release_id, version_id=version_id, tenant_id=tenant_id,
            kind=kind, target_environment=target_environment,
        )
        gate = self._ops.evaluate_gate(
            gate_id=gate_id, release_id=release_id, tenant_id=tenant_id,
            gate_name="continuity", passed=passed, reason="continuity gate",
        )
        _emit(self._events, "release_from_continuity", {
            "release_id": release_id, "continuity_ref": continuity_ref,
        }, release_id)
        return {
            "release_id": rel.release_id,
            "gate_id": gate.gate_id,
            "version_id": version_id,
            "tenant_id": tenant_id,
            "continuity_ref": continuity_ref,
            "passed": passed,
            "source_type": "continuity",
        }

    def release_from_service_health(
        self,
        release_id: str,
        gate_id: str,
        version_id: str,
        tenant_id: str,
        service_ref: str,
        passed: bool,
        kind: ReleaseKind = ReleaseKind.MINOR,
        target_environment: str = "staging",
    ) -> dict[str, Any]:
        rel = self._ops.create_release(
            release_id=release_id, version_id=version_id, tenant_id=tenant_id,
            kind=kind, target_environment=target_environment,
        )
        gate = self._ops.evaluate_gate(
            gate_id=gate_id, release_id=release_id, tenant_id=tenant_id,
            gate_name="service_health", passed=passed, reason="service health gate",
        )
        _emit(self._events, "release_from_service_health", {
            "release_id": release_id, "service_ref": service_ref,
        }, release_id)
        return {
            "release_id": rel.release_id,
            "gate_id": gate.gate_id,
            "version_id": version_id,
            "tenant_id": tenant_id,
            "service_ref": service_ref,
            "passed": passed,
            "source_type": "service_health",
        }

    def release_from_customer_impact(
        self,
        assessment_id: str,
        release_id: str,
        tenant_id: str,
        customer_impact_score: float,
        readiness_score: float = 1.0,
    ) -> dict[str, Any]:
        assessment = self._ops.assess_release(
            assessment_id=assessment_id, release_id=release_id, tenant_id=tenant_id,
            readiness_score=readiness_score, customer_impact_score=customer_impact_score,
        )
        _emit(self._events, "release_from_customer_impact", {
            "assessment_id": assessment_id, "release_id": release_id,
            "impact": customer_impact_score,
        }, assessment_id)
        return {
            "assessment_id": assessment.assessment_id,
            "release_id": release_id,
            "tenant_id": tenant_id,
            "risk_level": assessment.risk_level.value,
            "readiness_score": readiness_score,
            "customer_impact_score": customer_impact_score,
            "source_type": "customer_impact",
        }

    def release_from_change_runtime(
        self,
        release_id: str,
        gate_id: str,
        version_id: str,
        tenant_id: str,
        change_ref: str,
        passed: bool,
        kind: ReleaseKind = ReleaseKind.MINOR,
        target_environment: str = "staging",
    ) -> dict[str, Any]:
        rel = self._ops.create_release(
            release_id=release_id, version_id=version_id, tenant_id=tenant_id,
            kind=kind, target_environment=target_environment,
        )
        gate = self._ops.evaluate_gate(
            gate_id=gate_id, release_id=release_id, tenant_id=tenant_id,
            gate_name="change_approval", passed=passed, reason="change approval gate",
        )
        _emit(self._events, "release_from_change_runtime", {
            "release_id": release_id, "change_ref": change_ref,
        }, release_id)
        return {
            "release_id": rel.release_id,
            "gate_id": gate.gate_id,
            "version_id": version_id,
            "tenant_id": tenant_id,
            "change_ref": change_ref,
            "passed": passed,
            "source_type": "change_runtime",
        }

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_release_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        mid = stable_identifier("mem-pops", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)})
        content = {
            "versions": self._ops.version_count,
            "releases": self._ops.release_count,
            "gates": self._ops.gate_count,
            "promotions": self._ops.promotion_count,
            "rollbacks": self._ops.rollback_count,
            "milestones": self._ops.milestone_count,
            "assessments": self._ops.assessment_count,
            "violations": self._ops.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            memory_type=MemoryType.OBSERVATION,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Product ops runtime state",
            content=content,
            tags=("product_ops", "release", "lifecycle"),
            source_ids=(scope_ref_id,),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_release_to_memory", {"memory_id": mid}, mid)
        return record

    # ------------------------------------------------------------------
    # Graph attachment
    # ------------------------------------------------------------------

    def attach_release_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        return {
            "scope_ref_id": scope_ref_id,
            "versions": self._ops.version_count,
            "releases": self._ops.release_count,
            "gates": self._ops.gate_count,
            "promotions": self._ops.promotion_count,
            "rollbacks": self._ops.rollback_count,
            "milestones": self._ops.milestone_count,
            "assessments": self._ops.assessment_count,
            "violations": self._ops.violation_count,
        }
