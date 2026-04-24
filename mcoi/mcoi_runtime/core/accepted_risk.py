"""Purpose: accepted-risk admission and anchoring runtime.
Governance scope: residual-risk closure after unresolved verification or
effect reconciliation gaps.
Dependencies: accepted-risk, effect-assurance, verification, operational graph.
Invariants:
  - Matched reconciliation cannot create accepted risk.
  - Accepted risk requires explicit owner, approver, case, review obligation,
    evidence, and expiry.
  - Expired accepted risk cannot remain active.
  - Graph anchoring records the review decision and evidence relation.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from mcoi_runtime.contracts.accepted_risk import (
    AcceptedRiskDecision,
    AcceptedRiskDisposition,
    AcceptedRiskRecord,
    AcceptedRiskScope,
)
from mcoi_runtime.contracts.effect_assurance import EffectPlan, EffectReconciliation, ReconciliationStatus
from mcoi_runtime.contracts.execution import ExecutionResult
from mcoi_runtime.contracts.graph import EdgeType, NodeType
from mcoi_runtime.contracts.verification import VerificationResult, VerificationStatus

from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier
from .operational_graph import OperationalGraph


_UNRESOLVED_STATUSES = (
    ReconciliationStatus.PARTIAL_MATCH,
    ReconciliationStatus.MISMATCH,
    ReconciliationStatus.UNKNOWN,
)


class AcceptedRiskLedger:
    """Admit, store, and graph-anchor explicit accepted-risk records."""

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        graph: OperationalGraph | None = None,
    ) -> None:
        self._clock = clock
        self._graph = graph
        self._records: dict[str, AcceptedRiskRecord] = {}
        self._decisions: dict[str, AcceptedRiskDecision] = {}

    @property
    def record_count(self) -> int:
        """Return total accepted-risk records."""
        return len(self._records)

    def get_record(self, risk_id: str) -> AcceptedRiskRecord | None:
        """Return one accepted-risk record by identifier."""
        ensure_non_empty_text("risk_id", risk_id)
        return self._records.get(risk_id)

    def list_records(
        self,
        *,
        disposition: AcceptedRiskDisposition | None = None,
    ) -> tuple[AcceptedRiskRecord, ...]:
        """List accepted-risk records in stable identifier order."""
        records = sorted(self._records.values(), key=lambda record: record.risk_id)
        if disposition is not None:
            records = [record for record in records if record.disposition is disposition]
        return tuple(records)

    def evaluate_acceptance(
        self,
        *,
        plan: EffectPlan,
        execution_result: ExecutionResult,
        reconciliation: EffectReconciliation,
        verification_result: VerificationResult | None,
        case_id: str,
        reason: str,
        accepted_by: str,
        owner_id: str,
        expires_at: str,
        review_obligation_id: str,
        evidence_refs: tuple[str, ...],
    ) -> AcceptedRiskDecision:
        """Evaluate whether a proposed accepted-risk closure is admissible."""
        now = self._clock()
        missing = self._missing_requirements(
            plan=plan,
            execution_result=execution_result,
            reconciliation=reconciliation,
            verification_result=verification_result,
            case_id=case_id,
            reason=reason,
            accepted_by=accepted_by,
            owner_id=owner_id,
            expires_at=expires_at,
            review_obligation_id=review_obligation_id,
            evidence_refs=evidence_refs,
            now=now,
        )
        allowed = not missing
        decision = AcceptedRiskDecision(
            decision_id=stable_identifier(
                "accepted-risk-decision",
                {
                    "command_id": plan.command_id,
                    "reconciliation_id": reconciliation.reconciliation_id,
                    "decided_at": now,
                    "allowed": allowed,
                },
            ),
            command_id=plan.command_id,
            allowed=allowed,
            reason="accepted_risk_admissible" if allowed else "accepted_risk_requirements_missing",
            decided_at=now,
            missing_requirements=missing,
        )
        self._decisions[decision.decision_id] = decision
        return decision

    def accept(
        self,
        *,
        plan: EffectPlan,
        execution_result: ExecutionResult,
        reconciliation: EffectReconciliation,
        verification_result: VerificationResult | None,
        case_id: str,
        reason: str,
        accepted_by: str,
        owner_id: str,
        expires_at: str,
        review_obligation_id: str,
        evidence_refs: tuple[str, ...],
        scope: AcceptedRiskScope = AcceptedRiskScope.EFFECT_RECONCILIATION,
    ) -> AcceptedRiskRecord:
        """Create an active accepted-risk record after deterministic admission."""
        decision = self.evaluate_acceptance(
            plan=plan,
            execution_result=execution_result,
            reconciliation=reconciliation,
            verification_result=verification_result,
            case_id=case_id,
            reason=reason,
            accepted_by=accepted_by,
            owner_id=owner_id,
            expires_at=expires_at,
            review_obligation_id=review_obligation_id,
            evidence_refs=evidence_refs,
        )
        if not decision.allowed:
            raise RuntimeCoreInvariantError("accepted risk requirements missing")
        now = decision.decided_at
        record = AcceptedRiskRecord(
            risk_id=stable_identifier(
                "accepted-risk",
                {
                    "command_id": plan.command_id,
                    "execution_id": execution_result.execution_id,
                    "reconciliation_id": reconciliation.reconciliation_id,
                    "accepted_at": now,
                },
            ),
            command_id=plan.command_id,
            execution_id=execution_result.execution_id,
            effect_plan_id=plan.effect_plan_id,
            reconciliation_id=reconciliation.reconciliation_id,
            case_id=case_id,
            scope=scope,
            disposition=AcceptedRiskDisposition.ACTIVE,
            reason=reason,
            accepted_by=accepted_by,
            owner_id=owner_id,
            expires_at=expires_at,
            review_obligation_id=review_obligation_id,
            evidence_refs=evidence_refs,
            accepted_at=now,
            metadata={
                "decision_id": decision.decision_id,
                "verification_result_id": (
                    verification_result.verification_id if verification_result is not None else ""
                ),
                "reconciliation_status": reconciliation.status.value,
            },
        )
        if record.risk_id in self._records:
            raise RuntimeCoreInvariantError("accepted risk already exists")
        self._records[record.risk_id] = record
        if self._graph is not None:
            self.anchor_to_graph(record)
        return record

    def expire_due_records(self) -> tuple[AcceptedRiskRecord, ...]:
        """Expire active accepted-risk records whose review window has elapsed."""
        now = self._clock()
        expired: list[AcceptedRiskRecord] = []
        for record in self.list_records(disposition=AcceptedRiskDisposition.ACTIVE):
            if _parse_datetime(record.expires_at) <= _parse_datetime(now):
                updated = _replace_disposition(record, AcceptedRiskDisposition.EXPIRED)
                self._records[record.risk_id] = updated
                expired.append(updated)
        return tuple(expired)

    def close(self, risk_id: str, *, evidence_ref: str) -> AcceptedRiskRecord:
        """Close an accepted-risk record after follow-up evidence is attached."""
        ensure_non_empty_text("risk_id", risk_id)
        ensure_non_empty_text("evidence_ref", evidence_ref)
        record = self._records.get(risk_id)
        if record is None:
            raise RuntimeCoreInvariantError("accepted risk not found")
        if record.disposition is not AcceptedRiskDisposition.ACTIVE:
            raise RuntimeCoreInvariantError("accepted risk is not active")
        updated = _replace_disposition(
            record,
            AcceptedRiskDisposition.CLOSED,
            evidence_refs=record.evidence_refs + (evidence_ref,),
        )
        self._records[risk_id] = updated
        return updated

    def anchor_to_graph(self, record: AcceptedRiskRecord) -> None:
        """Anchor accepted risk, owner, case, obligation, and evidence to graph."""
        if self._graph is None:
            raise RuntimeCoreInvariantError("accepted risk graph anchoring requires graph")
        command_node = self._graph.ensure_node(
            f"command:{record.command_id}",
            NodeType.JOB,
            f"Command {record.command_id}",
        )
        case_node = self._graph.ensure_node(
            f"case:{record.case_id}",
            NodeType.INCIDENT,
            f"Accepted-risk case {record.case_id}",
        )
        review_node = self._graph.ensure_node(
            f"accepted_risk:{record.risk_id}",
            NodeType.REVIEW,
            f"Accepted risk {record.risk_id}",
        )
        owner_node = self._graph.ensure_node(
            f"person:{record.owner_id}",
            NodeType.PERSON,
            f"Risk owner {record.owner_id}",
        )
        obligation_node = self._graph.ensure_node(
            f"obligation:{record.review_obligation_id}",
            NodeType.JOB,
            f"Risk review obligation {record.review_obligation_id}",
        )
        self._graph.add_edge(EdgeType.BLOCKED_BY, command_node.node_id, case_node.node_id)
        self._graph.add_edge(EdgeType.DECIDED_BY, command_node.node_id, review_node.node_id)
        self._graph.add_edge(EdgeType.OWNS, owner_node.node_id, review_node.node_id)
        self._graph.add_edge(EdgeType.OBLIGATED_TO, review_node.node_id, obligation_node.node_id)
        for evidence_ref in record.evidence_refs:
            evidence_node = self._graph.ensure_node(
                f"evidence:{evidence_ref}",
                NodeType.DOCUMENT,
                f"Accepted-risk evidence {evidence_ref}",
            )
            self._graph.add_evidence_link(review_node.node_id, evidence_node.node_id, "accepted_risk", 1.0)

    def _missing_requirements(
        self,
        *,
        plan: EffectPlan,
        execution_result: ExecutionResult,
        reconciliation: EffectReconciliation,
        verification_result: VerificationResult | None,
        case_id: str,
        reason: str,
        accepted_by: str,
        owner_id: str,
        expires_at: str,
        review_obligation_id: str,
        evidence_refs: tuple[str, ...],
        now: str,
    ) -> tuple[str, ...]:
        missing: list[str] = []
        if reconciliation.command_id != plan.command_id:
            missing.append("reconciliation_command_mismatch")
        if verification_result is not None and verification_result.execution_id != execution_result.execution_id:
            missing.append("verification_execution_mismatch")
        if reconciliation.status is ReconciliationStatus.MATCH:
            missing.append("matched_reconciliation_cannot_be_accepted_risk")
        if reconciliation.status not in _UNRESOLVED_STATUSES:
            missing.append("unresolved_reconciliation_required")
        if verification_result is not None and verification_result.status is VerificationStatus.PASS:
            missing.append("passing_verification_cannot_be_accepted_risk")
        for field_name, field_value in (
            ("case_id", case_id),
            ("reason", reason),
            ("accepted_by", accepted_by),
            ("owner_id", owner_id),
            ("review_obligation_id", review_obligation_id),
        ):
            if not isinstance(field_value, str) or not field_value.strip():
                missing.append(field_name)
        if not evidence_refs:
            missing.append("evidence_refs")
        else:
            for evidence_ref in evidence_refs:
                if not isinstance(evidence_ref, str) or not evidence_ref.strip():
                    missing.append("evidence_refs")
                    break
        try:
            if _parse_datetime(expires_at) <= _parse_datetime(now):
                missing.append("future_expires_at")
        except ValueError:
            missing.append("expires_at")
        return tuple(missing)


def _parse_datetime(value: str) -> datetime:
    ensure_non_empty_text("datetime", value)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _replace_disposition(
    record: AcceptedRiskRecord,
    disposition: AcceptedRiskDisposition,
    *,
    evidence_refs: tuple[str, ...] | None = None,
) -> AcceptedRiskRecord:
    return AcceptedRiskRecord(
        risk_id=record.risk_id,
        command_id=record.command_id,
        execution_id=record.execution_id,
        effect_plan_id=record.effect_plan_id,
        reconciliation_id=record.reconciliation_id,
        case_id=record.case_id,
        scope=record.scope,
        disposition=disposition,
        reason=record.reason,
        accepted_by=record.accepted_by,
        owner_id=record.owner_id,
        expires_at=record.expires_at,
        review_obligation_id=record.review_obligation_id,
        evidence_refs=evidence_refs or record.evidence_refs,
        accepted_at=record.accepted_at,
        metadata=record.metadata,
    )
