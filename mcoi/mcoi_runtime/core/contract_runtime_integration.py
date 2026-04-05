"""Purpose: contract runtime integration bridge.
Governance scope: composing contract runtime with program, campaign, reporting,
    and assurance scopes; financial penalty and availability window binding;
    remediation requirement linkage; memory mesh and operational graph attachment.
Dependencies: contract_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every contract creation emits events.
  - Contract state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.contract_runtime import CommitmentKind
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
from .contract_runtime import ContractRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-cint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ContractRuntimeIntegration:
    """Integration bridge for contract runtime with platform layers."""

    def __init__(
        self,
        contract_engine: ContractRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(contract_engine, ContractRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "contract_engine must be a ContractRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._contracts = contract_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Contract creation helpers
    # ------------------------------------------------------------------

    def contract_from_program(
        self,
        contract_id: str,
        tenant_id: str,
        program_id: str,
        title: str = "Program SLA contract",
    ) -> dict[str, Any]:
        """Create a contract from a program."""
        c = self._contracts.register_contract(
            contract_id, tenant_id, program_id, title,
        )
        _emit(self._events, "contract_from_program", {
            "contract_id": contract_id, "program_id": program_id,
        }, contract_id)
        return {
            "contract_id": c.contract_id,
            "tenant_id": c.tenant_id,
            "counterparty": program_id,
            "status": c.status.value,
            "source_type": "program",
        }

    def contract_from_campaign(
        self,
        contract_id: str,
        tenant_id: str,
        campaign_id: str,
        title: str = "Campaign commitment contract",
    ) -> dict[str, Any]:
        """Create a contract from a campaign."""
        c = self._contracts.register_contract(
            contract_id, tenant_id, campaign_id, title,
        )
        _emit(self._events, "contract_from_campaign", {
            "contract_id": contract_id, "campaign_id": campaign_id,
        }, contract_id)
        return {
            "contract_id": c.contract_id,
            "tenant_id": c.tenant_id,
            "counterparty": campaign_id,
            "status": c.status.value,
            "source_type": "campaign",
        }

    def contract_from_reporting_requirement(
        self,
        contract_id: str,
        tenant_id: str,
        requirement_id: str,
        title: str = "Reporting compliance contract",
    ) -> dict[str, Any]:
        """Create a contract from a reporting requirement."""
        c = self._contracts.register_contract(
            contract_id, tenant_id, requirement_id, title,
        )
        _emit(self._events, "contract_from_reporting_requirement", {
            "contract_id": contract_id, "requirement_id": requirement_id,
        }, contract_id)
        return {
            "contract_id": c.contract_id,
            "tenant_id": c.tenant_id,
            "counterparty": requirement_id,
            "status": c.status.value,
            "source_type": "reporting_requirement",
        }

    def contract_from_assurance_scope(
        self,
        contract_id: str,
        tenant_id: str,
        scope_ref_id: str,
        title: str = "Assurance commitment contract",
    ) -> dict[str, Any]:
        """Create a contract from an assurance scope."""
        c = self._contracts.register_contract(
            contract_id, tenant_id, scope_ref_id, title,
        )
        _emit(self._events, "contract_from_assurance_scope", {
            "contract_id": contract_id, "scope_ref_id": scope_ref_id,
        }, contract_id)
        return {
            "contract_id": c.contract_id,
            "tenant_id": c.tenant_id,
            "counterparty": scope_ref_id,
            "status": c.status.value,
            "source_type": "assurance_scope",
        }

    # ------------------------------------------------------------------
    # Commitment binding helpers
    # ------------------------------------------------------------------

    def bind_financial_penalty(
        self,
        commitment_id: str,
        contract_id: str,
        clause_id: str,
        tenant_id: str,
        penalty_value: str,
    ) -> dict[str, Any]:
        """Bind a financial penalty commitment."""
        cm = self._contracts.register_commitment(
            commitment_id, contract_id, clause_id, tenant_id,
            penalty_value, kind=CommitmentKind.COMPLIANCE,
            scope_ref_id="financial", scope_ref_type="penalty",
        )
        _emit(self._events, "financial_penalty_bound", {
            "commitment_id": commitment_id, "value": penalty_value,
        }, contract_id)
        return {
            "commitment_id": cm.commitment_id,
            "contract_id": cm.contract_id,
            "kind": cm.kind.value,
            "target_value": penalty_value,
            "binding_type": "financial_penalty",
        }

    def bind_availability_window(
        self,
        commitment_id: str,
        contract_id: str,
        clause_id: str,
        tenant_id: str,
        availability_target: str,
    ) -> dict[str, Any]:
        """Bind an availability commitment."""
        cm = self._contracts.register_commitment(
            commitment_id, contract_id, clause_id, tenant_id,
            availability_target, kind=CommitmentKind.AVAILABILITY,
            scope_ref_id="availability", scope_ref_type="window",
        )
        _emit(self._events, "availability_window_bound", {
            "commitment_id": commitment_id, "target": availability_target,
        }, contract_id)
        return {
            "commitment_id": cm.commitment_id,
            "contract_id": cm.contract_id,
            "kind": cm.kind.value,
            "target_value": availability_target,
            "binding_type": "availability_window",
        }

    def bind_remediation_requirement(
        self,
        commitment_id: str,
        contract_id: str,
        clause_id: str,
        tenant_id: str,
        remediation_target: str,
    ) -> dict[str, Any]:
        """Bind a remediation requirement commitment."""
        cm = self._contracts.register_commitment(
            commitment_id, contract_id, clause_id, tenant_id,
            remediation_target, kind=CommitmentKind.RESPONSE_TIME,
            scope_ref_id="remediation", scope_ref_type="requirement",
        )
        _emit(self._events, "remediation_requirement_bound", {
            "commitment_id": commitment_id, "target": remediation_target,
        }, contract_id)
        return {
            "commitment_id": cm.commitment_id,
            "contract_id": cm.contract_id,
            "kind": cm.kind.value,
            "target_value": remediation_target,
            "binding_type": "remediation_requirement",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_contract_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist contract governance state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_contracts": self._contracts.contract_count,
            "active_contracts": self._contracts.active_contract_count,
            "total_commitments": self._contracts.commitment_count,
            "total_sla_windows": self._contracts.sla_window_count,
            "total_breaches": self._contracts.breach_count,
            "total_remedies": self._contracts.remedy_count,
            "total_renewals": self._contracts.renewal_count,
            "total_violations": self._contracts.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-cgov", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Contract governance state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("contract", "sla", "commitment"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "contract_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_contract_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return contract governance state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_contracts": self._contracts.contract_count,
            "active_contracts": self._contracts.active_contract_count,
            "total_commitments": self._contracts.commitment_count,
            "total_sla_windows": self._contracts.sla_window_count,
            "total_breaches": self._contracts.breach_count,
            "total_remedies": self._contracts.remedy_count,
            "total_renewals": self._contracts.renewal_count,
            "total_violations": self._contracts.violation_count,
        }
