"""Purpose: ledger runtime integration bridge.
Governance scope: composing ledger runtime with contract attestations,
    assurance attestations, regulatory submissions, billing settlements,
    partner revenue shares, marketplace transactions; memory mesh and
    operational graph attachment.
Dependencies: ledger_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every anchor/proof creation emits events.
  - Ledger state is attached to memory mesh.
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
from .ledger_runtime import LedgerRuntimeEngine
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-lint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class LedgerRuntimeIntegration:
    """Integration bridge for ledger runtime with platform layers."""

    def __init__(
        self,
        ledger_engine: LedgerRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(ledger_engine, LedgerRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "ledger_engine must be a LedgerRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._ledger = ledger_engine
        self._events = event_spine
        self._memory = memory_engine
        self._seq = 0

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    # ------------------------------------------------------------------
    # Anchor helpers
    # ------------------------------------------------------------------

    def anchor_contract_attestation(
        self,
        tenant_id: str,
        contract_ref: str,
        content_hash: str,
        *,
        anchor_ref: str = "pending",
    ) -> dict[str, Any]:
        """Create an anchor from a contract attestation."""
        anchor_id = stable_identifier("anc-contract", {
            "tenant": tenant_id, "ref": contract_ref,
        })
        ar = self._ledger.create_anchor(
            anchor_id=anchor_id,
            tenant_id=tenant_id,
            source_ref=contract_ref,
            content_hash=content_hash,
            anchor_ref=anchor_ref,
        )
        _emit(self._events, "anchor_contract_attestation", {
            "anchor_id": anchor_id, "contract_ref": contract_ref,
        }, anchor_id)
        return {
            "anchor_id": ar.anchor_id,
            "tenant_id": ar.tenant_id,
            "source_ref": ar.source_ref,
            "content_hash": ar.content_hash,
            "disposition": ar.disposition.value,
            "anchor_ref": ar.anchor_ref,
            "source_type": "contract_attestation",
            "created_at": ar.created_at,
        }

    def anchor_assurance_attestation(
        self,
        tenant_id: str,
        assurance_ref: str,
        content_hash: str,
        *,
        anchor_ref: str = "pending",
    ) -> dict[str, Any]:
        """Create an anchor from an assurance attestation."""
        anchor_id = stable_identifier("anc-assurance", {
            "tenant": tenant_id, "ref": assurance_ref,
        })
        ar = self._ledger.create_anchor(
            anchor_id=anchor_id,
            tenant_id=tenant_id,
            source_ref=assurance_ref,
            content_hash=content_hash,
            anchor_ref=anchor_ref,
        )
        _emit(self._events, "anchor_assurance_attestation", {
            "anchor_id": anchor_id, "assurance_ref": assurance_ref,
        }, anchor_id)
        return {
            "anchor_id": ar.anchor_id,
            "tenant_id": ar.tenant_id,
            "source_ref": ar.source_ref,
            "content_hash": ar.content_hash,
            "disposition": ar.disposition.value,
            "anchor_ref": ar.anchor_ref,
            "source_type": "assurance_attestation",
            "created_at": ar.created_at,
        }

    def anchor_regulatory_submission(
        self,
        tenant_id: str,
        submission_ref: str,
        content_hash: str,
        *,
        anchor_ref: str = "pending",
    ) -> dict[str, Any]:
        """Create an anchor from a regulatory submission."""
        anchor_id = stable_identifier("anc-regulatory", {
            "tenant": tenant_id, "ref": submission_ref,
        })
        ar = self._ledger.create_anchor(
            anchor_id=anchor_id,
            tenant_id=tenant_id,
            source_ref=submission_ref,
            content_hash=content_hash,
            anchor_ref=anchor_ref,
        )
        _emit(self._events, "anchor_regulatory_submission", {
            "anchor_id": anchor_id, "submission_ref": submission_ref,
        }, anchor_id)
        return {
            "anchor_id": ar.anchor_id,
            "tenant_id": ar.tenant_id,
            "source_ref": ar.source_ref,
            "content_hash": ar.content_hash,
            "disposition": ar.disposition.value,
            "anchor_ref": ar.anchor_ref,
            "source_type": "regulatory_submission",
            "created_at": ar.created_at,
        }

    # ------------------------------------------------------------------
    # Settlement proof helpers
    # ------------------------------------------------------------------

    def settlement_proof_from_billing(
        self,
        tenant_id: str,
        billing_ref: str,
        transaction_ref: str,
        proof_hash: str,
    ) -> dict[str, Any]:
        """Create a settlement proof from a billing settlement."""
        proof_id = stable_identifier("prf-billing", {
            "tenant": tenant_id, "ref": billing_ref,
        })
        p = self._ledger.create_settlement_proof(
            proof_id=proof_id,
            tenant_id=tenant_id,
            transaction_ref=transaction_ref,
            proof_hash=proof_hash,
        )
        _emit(self._events, "settlement_proof_from_billing", {
            "proof_id": proof_id, "billing_ref": billing_ref,
        }, proof_id)
        return {
            "proof_id": p.proof_id,
            "tenant_id": p.tenant_id,
            "transaction_ref": p.transaction_ref,
            "status": p.status.value,
            "proof_hash": p.proof_hash,
            "source_type": "billing_settlement",
            "created_at": p.created_at,
            "billing_ref": billing_ref,
        }

    def settlement_proof_from_partner_revenue_share(
        self,
        tenant_id: str,
        partner_ref: str,
        transaction_ref: str,
        proof_hash: str,
    ) -> dict[str, Any]:
        """Create a settlement proof from a partner revenue share."""
        proof_id = stable_identifier("prf-partner", {
            "tenant": tenant_id, "ref": partner_ref,
        })
        p = self._ledger.create_settlement_proof(
            proof_id=proof_id,
            tenant_id=tenant_id,
            transaction_ref=transaction_ref,
            proof_hash=proof_hash,
        )
        _emit(self._events, "settlement_proof_from_partner_revenue_share", {
            "proof_id": proof_id, "partner_ref": partner_ref,
        }, proof_id)
        return {
            "proof_id": p.proof_id,
            "tenant_id": p.tenant_id,
            "transaction_ref": p.transaction_ref,
            "status": p.status.value,
            "proof_hash": p.proof_hash,
            "source_type": "partner_revenue_share",
            "created_at": p.created_at,
            "partner_ref": partner_ref,
        }

    def settlement_proof_from_marketplace_transaction(
        self,
        tenant_id: str,
        marketplace_ref: str,
        transaction_ref: str,
        proof_hash: str,
    ) -> dict[str, Any]:
        """Create a settlement proof from a marketplace transaction."""
        proof_id = stable_identifier("prf-marketplace", {
            "tenant": tenant_id, "ref": marketplace_ref,
        })
        p = self._ledger.create_settlement_proof(
            proof_id=proof_id,
            tenant_id=tenant_id,
            transaction_ref=transaction_ref,
            proof_hash=proof_hash,
        )
        _emit(self._events, "settlement_proof_from_marketplace_transaction", {
            "proof_id": proof_id, "marketplace_ref": marketplace_ref,
        }, proof_id)
        return {
            "proof_id": p.proof_id,
            "tenant_id": p.tenant_id,
            "transaction_ref": p.transaction_ref,
            "status": p.status.value,
            "proof_hash": p.proof_hash,
            "source_type": "marketplace_transaction",
            "created_at": p.created_at,
            "marketplace_ref": marketplace_ref,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_ledger_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist ledger state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_accounts": self._ledger.account_count,
            "total_transactions": self._ledger.transaction_count,
            "total_proofs": self._ledger.proof_count,
            "total_anchors": self._ledger.anchor_count,
            "total_wallets": self._ledger.wallet_count,
            "total_violations": self._ledger.violation_count,
        }
        seq = self._next_seq()
        mem = MemoryRecord(
            memory_id=stable_identifier("mem-ldgr", {"id": scope_ref_id, "seq": str(seq)}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Ledger state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("ledger", "blockchain", "settlement"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "ledger_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_ledger_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return ledger state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_accounts": self._ledger.account_count,
            "total_transactions": self._ledger.transaction_count,
            "total_proofs": self._ledger.proof_count,
            "total_anchors": self._ledger.anchor_count,
            "total_wallets": self._ledger.wallet_count,
            "total_violations": self._ledger.violation_count,
        }
