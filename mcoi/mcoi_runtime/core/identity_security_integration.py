"""Purpose: Identity / security integration bridge.
Governance scope: connects identity/security engine to workforce, customer,
    partner, external execution, LLM runtime, and operator workspace subsystems.
Dependencies: identity_security engine, event_spine, memory_mesh.
Invariants:
  - Constructor validates all three engine types.
  - All outputs are frozen dicts or MemoryRecord instances.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.identity_security import IdentityType
from mcoi_runtime.contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.identity_security import IdentitySecurityEngine
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
        event_id=stable_identifier("evt-idseci", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class IdentitySecurityIntegration:
    """Integration bridge for identity/security runtime."""

    def __init__(
        self,
        security_engine: IdentitySecurityEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(security_engine, IdentitySecurityEngine):
            raise RuntimeCoreInvariantError("security_engine must be an IdentitySecurityEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._security = security_engine
        self._events = event_spine
        self._memory = memory_engine

    # -- Bridge methods --

    def identity_from_workforce(
        self,
        identity_id: str,
        tenant_id: str,
        display_name: str,
        workforce_ref: str = "none",
    ) -> dict[str, Any]:
        identity = self._security.register_identity(
            identity_id, tenant_id, display_name,
            identity_type=IdentityType.HUMAN,
        )
        _emit(self._events, "identity_from_workforce", {
            "identity_id": identity_id, "workforce_ref": workforce_ref,
        }, identity_id)
        return {
            "identity_id": identity.identity_id,
            "tenant_id": tenant_id,
            "display_name": display_name,
            "workforce_ref": workforce_ref,
            "identity_type": identity.identity_type.value,
            "source_type": "workforce",
        }

    def identity_from_customer(
        self,
        identity_id: str,
        tenant_id: str,
        display_name: str,
        customer_ref: str = "none",
    ) -> dict[str, Any]:
        identity = self._security.register_identity(
            identity_id, tenant_id, display_name,
            identity_type=IdentityType.HUMAN,
        )
        _emit(self._events, "identity_from_customer", {
            "identity_id": identity_id, "customer_ref": customer_ref,
        }, identity_id)
        return {
            "identity_id": identity.identity_id,
            "tenant_id": tenant_id,
            "display_name": display_name,
            "customer_ref": customer_ref,
            "identity_type": identity.identity_type.value,
            "source_type": "customer",
        }

    def identity_from_partner(
        self,
        identity_id: str,
        tenant_id: str,
        display_name: str,
        partner_ref: str = "none",
    ) -> dict[str, Any]:
        identity = self._security.register_identity(
            identity_id, tenant_id, display_name,
            identity_type=IdentityType.DELEGATED,
        )
        _emit(self._events, "identity_from_partner", {
            "identity_id": identity_id, "partner_ref": partner_ref,
        }, identity_id)
        return {
            "identity_id": identity.identity_id,
            "tenant_id": tenant_id,
            "display_name": display_name,
            "partner_ref": partner_ref,
            "identity_type": identity.identity_type.value,
            "source_type": "partner",
        }

    def identity_from_external_execution(
        self,
        identity_id: str,
        tenant_id: str,
        display_name: str,
        execution_ref: str = "none",
    ) -> dict[str, Any]:
        identity = self._security.register_identity(
            identity_id, tenant_id, display_name,
            identity_type=IdentityType.SERVICE,
        )
        _emit(self._events, "identity_from_external_execution", {
            "identity_id": identity_id, "execution_ref": execution_ref,
        }, identity_id)
        return {
            "identity_id": identity.identity_id,
            "tenant_id": tenant_id,
            "display_name": display_name,
            "execution_ref": execution_ref,
            "identity_type": identity.identity_type.value,
            "source_type": "external_execution",
        }

    def identity_from_llm_runtime(
        self,
        identity_id: str,
        tenant_id: str,
        display_name: str,
        model_ref: str = "none",
    ) -> dict[str, Any]:
        identity = self._security.register_identity(
            identity_id, tenant_id, display_name,
            identity_type=IdentityType.MACHINE,
        )
        _emit(self._events, "identity_from_llm_runtime", {
            "identity_id": identity_id, "model_ref": model_ref,
        }, identity_id)
        return {
            "identity_id": identity.identity_id,
            "tenant_id": tenant_id,
            "display_name": display_name,
            "model_ref": model_ref,
            "identity_type": identity.identity_type.value,
            "source_type": "llm_runtime",
        }

    def identity_from_operator_workspace(
        self,
        identity_id: str,
        tenant_id: str,
        display_name: str,
        workspace_ref: str = "none",
    ) -> dict[str, Any]:
        identity = self._security.register_identity(
            identity_id, tenant_id, display_name,
            identity_type=IdentityType.HUMAN,
        )
        _emit(self._events, "identity_from_operator_workspace", {
            "identity_id": identity_id, "workspace_ref": workspace_ref,
        }, identity_id)
        return {
            "identity_id": identity.identity_id,
            "tenant_id": tenant_id,
            "display_name": display_name,
            "workspace_ref": workspace_ref,
            "identity_type": identity.identity_type.value,
            "source_type": "operator_workspace",
        }

    # -- Memory mesh --

    def attach_security_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        mid = stable_identifier("mem-idsec", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)})
        content = {
            "total_identities": self._security.identity_count,
            "total_credentials": self._security.credential_count,
            "total_chains": self._security.chain_count,
            "total_elevations": self._security.elevation_count,
            "total_sessions": self._security.session_count,
            "total_vault_accesses": self._security.vault_access_count,
            "total_recertifications": self._security.recertification_count,
            "total_break_glass": self._security.break_glass_count,
            "total_violations": self._security.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Identity/security state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("identity", "security", "vault"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_security_state_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return record

    # -- Graph --

    def attach_security_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        return {
            "scope_ref_id": scope_ref_id,
            "total_identities": self._security.identity_count,
            "total_credentials": self._security.credential_count,
            "total_chains": self._security.chain_count,
            "total_elevations": self._security.elevation_count,
            "total_sessions": self._security.session_count,
            "total_vault_accesses": self._security.vault_access_count,
            "total_recertifications": self._security.recertification_count,
            "total_break_glass": self._security.break_glass_count,
            "total_violations": self._security.violation_count,
        }
