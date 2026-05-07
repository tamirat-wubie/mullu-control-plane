"""Purpose: partner runtime integration bridge.
Governance scope: composing partner runtime with contracts, customer accounts,
    procurement vendors, SLA breaches, settlements, cases; memory mesh
    and graph attachment.
Dependencies: partner_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every partner action emits events.
  - Partner state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.partner_runtime import EcosystemRole, PartnerKind
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .partner_runtime import PartnerRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-prtint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class PartnerRuntimeIntegration:
    """Integration bridge for partner runtime with platform layers."""

    def __init__(
        self,
        partner_engine: PartnerRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(partner_engine, PartnerRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "partner_engine must be a PartnerRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._partner = partner_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Partner from platform layers
    # ------------------------------------------------------------------

    def partner_from_contract(
        self,
        partner_id: str,
        tenant_id: str,
        display_name: str,
        contract_ref: str,
        kind: PartnerKind = PartnerKind.RESELLER,
        revenue_share_pct: float = 0.0,
        tier: str = "standard",
    ) -> dict[str, Any]:
        partner = self._partner.register_partner(
            partner_id=partner_id,
            tenant_id=tenant_id,
            display_name=display_name,
            kind=kind,
            tier=tier,
        )
        agr_id = stable_identifier("agr", {"partner_id": partner_id, "contract_ref": contract_ref})
        agreement = self._partner.register_agreement(
            agreement_id=agr_id,
            partner_id=partner_id,
            tenant_id=tenant_id,
            title="Partner agreement",
            contract_ref=contract_ref,
            revenue_share_pct=revenue_share_pct,
        )
        _emit(self._events, "partner_from_contract", {
            "partner_id": partner_id, "contract_ref": contract_ref,
        }, partner_id)
        return {
            "partner_id": partner.partner_id,
            "agreement_id": agreement.agreement_id,
            "tenant_id": tenant_id,
            "contract_ref": contract_ref,
            "kind": kind.value,
            "revenue_share_pct": revenue_share_pct,
            "source_type": "contract",
        }

    def partner_from_customer_account(
        self,
        link_id: str,
        partner_id: str,
        account_id: str,
        tenant_id: str,
        role: EcosystemRole = EcosystemRole.INTERMEDIARY,
    ) -> dict[str, Any]:
        link = self._partner.link_partner_to_account(
            link_id=link_id,
            partner_id=partner_id,
            account_id=account_id,
            tenant_id=tenant_id,
            role=role,
        )
        _emit(self._events, "partner_from_customer_account", {
            "link_id": link_id, "partner_id": partner_id, "account_id": account_id,
        }, link_id)
        return {
            "link_id": link.link_id,
            "partner_id": partner_id,
            "account_id": account_id,
            "tenant_id": tenant_id,
            "role": role.value,
            "source_type": "customer_account",
        }

    def partner_from_procurement_vendor(
        self,
        partner_id: str,
        tenant_id: str,
        display_name: str,
        vendor_ref: str,
        kind: PartnerKind = PartnerKind.DISTRIBUTOR,
        tier: str = "standard",
    ) -> dict[str, Any]:
        partner = self._partner.register_partner(
            partner_id=partner_id,
            tenant_id=tenant_id,
            display_name=display_name,
            kind=kind,
            tier=tier,
        )
        _emit(self._events, "partner_from_procurement_vendor", {
            "partner_id": partner_id, "vendor_ref": vendor_ref,
        }, partner_id)
        return {
            "partner_id": partner.partner_id,
            "tenant_id": tenant_id,
            "vendor_ref": vendor_ref,
            "kind": kind.value,
            "source_type": "procurement_vendor",
        }

    def partner_health_from_sla_breach(
        self,
        snapshot_id: str,
        partner_id: str,
        tenant_id: str,
        breach_count: int = 1,
    ) -> dict[str, Any]:
        snap = self._partner.partner_health(
            snapshot_id=snapshot_id,
            partner_id=partner_id,
            tenant_id=tenant_id,
            sla_breaches=breach_count,
        )
        _emit(self._events, "partner_health_from_sla_breach", {
            "snapshot_id": snapshot_id, "partner_id": partner_id,
        }, snapshot_id)
        return {
            "snapshot_id": snap.snapshot_id,
            "partner_id": partner_id,
            "tenant_id": tenant_id,
            "health_score": snap.health_score,
            "health_status": snap.health_status.value,
            "sla_breaches": breach_count,
            "source_type": "sla_breach",
        }

    def partner_health_from_settlement(
        self,
        snapshot_id: str,
        partner_id: str,
        tenant_id: str,
        billing_issues: int = 1,
    ) -> dict[str, Any]:
        snap = self._partner.partner_health(
            snapshot_id=snapshot_id,
            partner_id=partner_id,
            tenant_id=tenant_id,
            billing_issues=billing_issues,
        )
        _emit(self._events, "partner_health_from_settlement", {
            "snapshot_id": snapshot_id, "partner_id": partner_id,
        }, snapshot_id)
        return {
            "snapshot_id": snap.snapshot_id,
            "partner_id": partner_id,
            "tenant_id": tenant_id,
            "health_score": snap.health_score,
            "health_status": snap.health_status.value,
            "billing_issues": billing_issues,
            "source_type": "settlement",
        }

    def partner_health_from_case(
        self,
        snapshot_id: str,
        partner_id: str,
        tenant_id: str,
        open_cases: int = 1,
    ) -> dict[str, Any]:
        snap = self._partner.partner_health(
            snapshot_id=snapshot_id,
            partner_id=partner_id,
            tenant_id=tenant_id,
            open_cases=open_cases,
        )
        _emit(self._events, "partner_health_from_case", {
            "snapshot_id": snapshot_id, "partner_id": partner_id,
        }, snapshot_id)
        return {
            "snapshot_id": snap.snapshot_id,
            "partner_id": partner_id,
            "tenant_id": tenant_id,
            "health_score": snap.health_score,
            "health_status": snap.health_status.value,
            "open_cases": open_cases,
            "source_type": "case",
        }

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_partner_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        mid = stable_identifier("mem-prt", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)})
        content = {
            "partners": self._partner.partner_count,
            "links": self._partner.link_count,
            "agreements": self._partner.agreement_count,
            "revenue_shares": self._partner.revenue_share_count,
            "commitments": self._partner.commitment_count,
            "health_snapshots": self._partner.health_snapshot_count,
            "decisions": self._partner.decision_count,
            "violations": self._partner.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            memory_type=MemoryType.OBSERVATION,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Partner runtime state",
            content=content,
            tags=("partner", "ecosystem", "marketplace"),
            source_ids=(scope_ref_id,),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_partner_to_memory", {"memory_id": mid, "scope_ref_id": scope_ref_id}, mid)
        return record

    # ------------------------------------------------------------------
    # Graph attachment
    # ------------------------------------------------------------------

    def attach_partner_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        return {
            "scope_ref_id": scope_ref_id,
            "partners": self._partner.partner_count,
            "links": self._partner.link_count,
            "agreements": self._partner.agreement_count,
            "revenue_shares": self._partner.revenue_share_count,
            "commitments": self._partner.commitment_count,
            "health_snapshots": self._partner.health_snapshot_count,
            "decisions": self._partner.decision_count,
            "violations": self._partner.violation_count,
        }
