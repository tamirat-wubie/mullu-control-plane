"""Purpose: contract / SLA / commitment governance runtime engine.
Governance scope: registering contracts, clauses, and commitments; binding
    commitments to scopes; evaluating SLA windows; recording breaches and
    remedies; tracking renewal windows; producing immutable assessments,
    snapshots, and closure reports; detecting violations.
Dependencies: contract_runtime contracts, event_spine, core invariants.
Invariants:
  - Breaches require explicit severity.
  - SLA windows degrade from HEALTHY to AT_RISK/BREACHED.
  - Renewal windows enforce deadlines.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.contract_runtime import (
    BreachRecord,
    BreachSeverity,
    CommitmentKind,
    CommitmentRecord,
    ContractAssessment,
    ContractClause,
    ContractClosureReport,
    ContractSnapshot,
    ContractStatus,
    GovernanceContractRecord,
    RemedyDisposition,
    RemedyRecord,
    RenewalStatus,
    RenewalWindow,
    SLAStatus,
    SLAWindow,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-cgov", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_CONTRACT_TERMINAL = frozenset({ContractStatus.EXPIRED, ContractStatus.TERMINATED})


class ContractRuntimeEngine:
    """Contract, SLA, and commitment governance engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._contracts: dict[str, GovernanceContractRecord] = {}
        self._clauses: dict[str, ContractClause] = {}
        self._commitments: dict[str, CommitmentRecord] = {}
        self._sla_windows: dict[str, SLAWindow] = {}
        self._breaches: dict[str, BreachRecord] = {}
        self._remedies: dict[str, RemedyRecord] = {}
        self._renewals: dict[str, RenewalWindow] = {}
        self._assessments: dict[str, ContractAssessment] = {}
        self._violations: dict[str, Any] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def contract_count(self) -> int:
        return len(self._contracts)

    @property
    def active_contract_count(self) -> int:
        return sum(1 for c in self._contracts.values() if c.status == ContractStatus.ACTIVE)

    @property
    def clause_count(self) -> int:
        return len(self._clauses)

    @property
    def commitment_count(self) -> int:
        return len(self._commitments)

    @property
    def sla_window_count(self) -> int:
        return len(self._sla_windows)

    @property
    def breach_count(self) -> int:
        return len(self._breaches)

    @property
    def remedy_count(self) -> int:
        return len(self._remedies)

    @property
    def renewal_count(self) -> int:
        return len(self._renewals)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Contracts
    # ------------------------------------------------------------------

    def register_contract(
        self,
        contract_id: str,
        tenant_id: str,
        counterparty: str,
        title: str,
        *,
        effective_at: str = "",
        expires_at: str = "",
        description: str = "",
    ) -> GovernanceContractRecord:
        """Register a governance contract."""
        if contract_id in self._contracts:
            raise RuntimeCoreInvariantError("Duplicate contract_id")
        now = _now_iso()
        if not effective_at:
            effective_at = now
        rec = GovernanceContractRecord(
            contract_id=contract_id,
            tenant_id=tenant_id,
            counterparty=counterparty,
            status=ContractStatus.DRAFT,
            title=title,
            description=description,
            effective_at=effective_at,
            expires_at=expires_at,
        )
        self._contracts[contract_id] = rec
        _emit(self._events, "contract_registered", {
            "contract_id": contract_id, "counterparty": counterparty,
        }, contract_id)
        return rec

    def get_contract(self, contract_id: str) -> GovernanceContractRecord:
        """Get a contract by ID."""
        c = self._contracts.get(contract_id)
        if c is None:
            raise RuntimeCoreInvariantError("Unknown contract_id")
        return c

    def activate_contract(self, contract_id: str) -> GovernanceContractRecord:
        """Activate a contract."""
        old = self.get_contract(contract_id)
        if old.status in _CONTRACT_TERMINAL:
            raise RuntimeCoreInvariantError(
                "cannot activate contract from current status"
            )
        updated = GovernanceContractRecord(
            contract_id=old.contract_id,
            tenant_id=old.tenant_id,
            counterparty=old.counterparty,
            status=ContractStatus.ACTIVE,
            title=old.title,
            description=old.description,
            effective_at=old.effective_at,
            expires_at=old.expires_at,
            metadata=old.metadata,
        )
        self._contracts[contract_id] = updated
        _emit(self._events, "contract_activated", {
            "contract_id": contract_id,
        }, contract_id)
        return updated

    def suspend_contract(self, contract_id: str, *, reason: str = "") -> GovernanceContractRecord:
        """Suspend an active contract."""
        old = self.get_contract(contract_id)
        if old.status != ContractStatus.ACTIVE:
            raise RuntimeCoreInvariantError("Can only suspend ACTIVE contracts")
        updated = GovernanceContractRecord(
            contract_id=old.contract_id,
            tenant_id=old.tenant_id,
            counterparty=old.counterparty,
            status=ContractStatus.SUSPENDED,
            title=old.title,
            description=old.description,
            effective_at=old.effective_at,
            expires_at=old.expires_at,
            metadata=old.metadata,
        )
        self._contracts[contract_id] = updated
        _emit(self._events, "contract_suspended", {
            "contract_id": contract_id, "reason": reason,
        }, contract_id)
        return updated

    def terminate_contract(self, contract_id: str, *, reason: str = "") -> GovernanceContractRecord:
        """Terminate a contract."""
        old = self.get_contract(contract_id)
        if old.status in _CONTRACT_TERMINAL:
            raise RuntimeCoreInvariantError(
                "cannot terminate contract from current status"
            )
        updated = GovernanceContractRecord(
            contract_id=old.contract_id,
            tenant_id=old.tenant_id,
            counterparty=old.counterparty,
            status=ContractStatus.TERMINATED,
            title=old.title,
            description=old.description,
            effective_at=old.effective_at,
            expires_at=old.expires_at,
            metadata=old.metadata,
        )
        self._contracts[contract_id] = updated
        _emit(self._events, "contract_terminated", {
            "contract_id": contract_id, "reason": reason,
        }, contract_id)
        return updated

    def expire_contract(self, contract_id: str) -> GovernanceContractRecord:
        """Mark a contract as expired."""
        old = self.get_contract(contract_id)
        if old.status in _CONTRACT_TERMINAL:
            raise RuntimeCoreInvariantError(
                "cannot expire contract from current status"
            )
        updated = GovernanceContractRecord(
            contract_id=old.contract_id,
            tenant_id=old.tenant_id,
            counterparty=old.counterparty,
            status=ContractStatus.EXPIRED,
            title=old.title,
            description=old.description,
            effective_at=old.effective_at,
            expires_at=old.expires_at,
            metadata=old.metadata,
        )
        self._contracts[contract_id] = updated
        _emit(self._events, "contract_expired", {
            "contract_id": contract_id,
        }, contract_id)
        return updated

    def contracts_for_tenant(self, tenant_id: str) -> tuple[GovernanceContractRecord, ...]:
        """Return all contracts for a tenant."""
        return tuple(c for c in self._contracts.values() if c.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Clauses
    # ------------------------------------------------------------------

    def register_clause(
        self,
        clause_id: str,
        contract_id: str,
        title: str,
        *,
        description: str = "",
        commitment_kind: CommitmentKind = CommitmentKind.SLA,
    ) -> ContractClause:
        """Register a clause within a contract."""
        if clause_id in self._clauses:
            raise RuntimeCoreInvariantError("Duplicate clause_id")
        if contract_id not in self._contracts:
            raise RuntimeCoreInvariantError("Unknown contract_id")
        clause = ContractClause(
            clause_id=clause_id,
            contract_id=contract_id,
            title=title,
            description=description,
            commitment_kind=commitment_kind,
        )
        self._clauses[clause_id] = clause
        _emit(self._events, "clause_registered", {
            "clause_id": clause_id, "contract_id": contract_id,
        }, contract_id)
        return clause

    def clauses_for_contract(self, contract_id: str) -> tuple[ContractClause, ...]:
        """Return all clauses for a contract."""
        return tuple(c for c in self._clauses.values() if c.contract_id == contract_id)

    # ------------------------------------------------------------------
    # Commitments
    # ------------------------------------------------------------------

    def register_commitment(
        self,
        commitment_id: str,
        contract_id: str,
        clause_id: str,
        tenant_id: str,
        target_value: str,
        *,
        kind: CommitmentKind = CommitmentKind.SLA,
        scope_ref_id: str = "",
        scope_ref_type: str = "",
    ) -> CommitmentRecord:
        """Register a contractual commitment."""
        if commitment_id in self._commitments:
            raise RuntimeCoreInvariantError("Duplicate commitment_id")
        if contract_id not in self._contracts:
            raise RuntimeCoreInvariantError("Unknown contract_id")
        if clause_id not in self._clauses:
            raise RuntimeCoreInvariantError("Unknown clause_id")
        now = _now_iso()
        rec = CommitmentRecord(
            commitment_id=commitment_id,
            contract_id=contract_id,
            clause_id=clause_id,
            tenant_id=tenant_id,
            kind=kind,
            target_value=target_value,
            scope_ref_id=scope_ref_id,
            scope_ref_type=scope_ref_type,
            created_at=now,
        )
        self._commitments[commitment_id] = rec
        _emit(self._events, "commitment_registered", {
            "commitment_id": commitment_id, "kind": kind.value,
        }, contract_id)
        return rec

    def commitments_for_contract(self, contract_id: str) -> tuple[CommitmentRecord, ...]:
        """Return all commitments for a contract."""
        return tuple(c for c in self._commitments.values() if c.contract_id == contract_id)

    # ------------------------------------------------------------------
    # SLA windows
    # ------------------------------------------------------------------

    def evaluate_sla(
        self,
        window_id: str,
        commitment_id: str,
        opens_at: str,
        closes_at: str,
        *,
        actual_value: str = "",
        compliance: float = 1.0,
    ) -> SLAWindow:
        """Evaluate an SLA measurement window."""
        if window_id in self._sla_windows:
            raise RuntimeCoreInvariantError("Duplicate window_id")
        if commitment_id not in self._commitments:
            raise RuntimeCoreInvariantError("Unknown commitment_id")

        # Determine status based on compliance
        if compliance >= 0.95:
            status = SLAStatus.HEALTHY
        elif compliance >= 0.80:
            status = SLAStatus.AT_RISK
        else:
            status = SLAStatus.BREACHED

        window = SLAWindow(
            window_id=window_id,
            commitment_id=commitment_id,
            status=status,
            opens_at=opens_at,
            closes_at=closes_at,
            actual_value=actual_value,
            compliance=compliance,
        )
        self._sla_windows[window_id] = window

        # Auto-create breach for BREACHED SLA
        if status == SLAStatus.BREACHED:
            breach_id = stable_identifier("breach-auto", {
                "window": window_id, "commitment": commitment_id,
            })
            commitment = self._commitments[commitment_id]
            if breach_id not in self._breaches:
                now = _now_iso()
                breach = BreachRecord(
                    breach_id=breach_id,
                    commitment_id=commitment_id,
                    contract_id=commitment.contract_id,
                    tenant_id=commitment.tenant_id,
                    severity=BreachSeverity.MAJOR if compliance >= 0.5 else BreachSeverity.CRITICAL,
                    description="SLA breached",
                    detected_at=now,
                )
                self._breaches[breach_id] = breach

        _emit(self._events, "sla_evaluated", {
            "window_id": window_id, "status": status.value,
            "compliance": compliance,
        }, commitment_id)
        return window

    def get_sla_window(self, window_id: str) -> SLAWindow:
        """Get an SLA window by ID."""
        w = self._sla_windows.get(window_id)
        if w is None:
            raise RuntimeCoreInvariantError("Unknown window_id")
        return w

    def sla_windows_for_commitment(self, commitment_id: str) -> tuple[SLAWindow, ...]:
        """Return all SLA windows for a commitment."""
        return tuple(w for w in self._sla_windows.values() if w.commitment_id == commitment_id)

    # ------------------------------------------------------------------
    # Breaches
    # ------------------------------------------------------------------

    def record_breach(
        self,
        breach_id: str,
        commitment_id: str,
        *,
        severity: BreachSeverity = BreachSeverity.MINOR,
        description: str = "",
    ) -> BreachRecord:
        """Record a contract breach."""
        if breach_id in self._breaches:
            raise RuntimeCoreInvariantError("Duplicate breach_id")
        if commitment_id not in self._commitments:
            raise RuntimeCoreInvariantError("Unknown commitment_id")
        commitment = self._commitments[commitment_id]
        now = _now_iso()
        breach = BreachRecord(
            breach_id=breach_id,
            commitment_id=commitment_id,
            contract_id=commitment.contract_id,
            tenant_id=commitment.tenant_id,
            severity=severity,
            description=description,
            detected_at=now,
        )
        self._breaches[breach_id] = breach
        _emit(self._events, "breach_recorded", {
            "breach_id": breach_id, "severity": severity.value,
        }, commitment.contract_id)
        return breach

    def breaches_for_commitment(self, commitment_id: str) -> tuple[BreachRecord, ...]:
        """Return all breaches for a commitment."""
        return tuple(b for b in self._breaches.values() if b.commitment_id == commitment_id)

    def breaches_for_contract(self, contract_id: str) -> tuple[BreachRecord, ...]:
        """Return all breaches for a contract."""
        return tuple(b for b in self._breaches.values() if b.contract_id == contract_id)

    # ------------------------------------------------------------------
    # Remedies
    # ------------------------------------------------------------------

    def record_remedy(
        self,
        remedy_id: str,
        breach_id: str,
        *,
        disposition: RemedyDisposition = RemedyDisposition.PENDING,
        amount: str = "",
        description: str = "",
    ) -> RemedyRecord:
        """Record a remedy for a breach."""
        if remedy_id in self._remedies:
            raise RuntimeCoreInvariantError("Duplicate remedy_id")
        if breach_id not in self._breaches:
            raise RuntimeCoreInvariantError("Unknown breach_id")
        breach = self._breaches[breach_id]
        now = _now_iso()
        remedy = RemedyRecord(
            remedy_id=remedy_id,
            breach_id=breach_id,
            tenant_id=breach.tenant_id,
            disposition=disposition,
            amount=amount,
            description=description,
            applied_at=now,
        )
        self._remedies[remedy_id] = remedy
        _emit(self._events, "remedy_recorded", {
            "remedy_id": remedy_id, "disposition": disposition.value,
        }, breach.contract_id)
        return remedy

    def remedies_for_breach(self, breach_id: str) -> tuple[RemedyRecord, ...]:
        """Return all remedies for a breach."""
        return tuple(r for r in self._remedies.values() if r.breach_id == breach_id)

    # ------------------------------------------------------------------
    # Renewal windows
    # ------------------------------------------------------------------

    def schedule_renewal(
        self,
        window_id: str,
        contract_id: str,
        opens_at: str,
        closes_at: str,
    ) -> RenewalWindow:
        """Schedule a renewal window for a contract."""
        if window_id in self._renewals:
            raise RuntimeCoreInvariantError("Duplicate window_id")
        if contract_id not in self._contracts:
            raise RuntimeCoreInvariantError("Unknown contract_id")
        window = RenewalWindow(
            window_id=window_id,
            contract_id=contract_id,
            status=RenewalStatus.SCHEDULED,
            opens_at=opens_at,
            closes_at=closes_at,
        )
        self._renewals[window_id] = window
        _emit(self._events, "renewal_scheduled", {
            "window_id": window_id, "contract_id": contract_id,
        }, contract_id)
        return window

    def complete_renewal(self, window_id: str) -> RenewalWindow:
        """Mark a renewal window as completed."""
        old = self._renewals.get(window_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown window_id")
        now = _now_iso()
        updated = RenewalWindow(
            window_id=old.window_id,
            contract_id=old.contract_id,
            status=RenewalStatus.COMPLETED,
            opens_at=old.opens_at,
            closes_at=old.closes_at,
            completed_at=now,
            metadata=old.metadata,
        )
        self._renewals[window_id] = updated

        # Update contract status to RENEWED
        contract = self._contracts.get(old.contract_id)
        if contract and contract.status not in _CONTRACT_TERMINAL:
            renewed = GovernanceContractRecord(
                contract_id=contract.contract_id,
                tenant_id=contract.tenant_id,
                counterparty=contract.counterparty,
                status=ContractStatus.RENEWED,
                title=contract.title,
                description=contract.description,
                effective_at=contract.effective_at,
                expires_at=contract.expires_at,
                metadata=contract.metadata,
            )
            self._contracts[contract.contract_id] = renewed

        _emit(self._events, "renewal_completed", {
            "window_id": window_id,
        }, old.contract_id)
        return updated

    def decline_renewal(self, window_id: str) -> RenewalWindow:
        """Decline a renewal window."""
        old = self._renewals.get(window_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown window_id")
        updated = RenewalWindow(
            window_id=old.window_id,
            contract_id=old.contract_id,
            status=RenewalStatus.DECLINED,
            opens_at=old.opens_at,
            closes_at=old.closes_at,
            metadata=old.metadata,
        )
        self._renewals[window_id] = updated
        _emit(self._events, "renewal_declined", {
            "window_id": window_id,
        }, old.contract_id)
        return updated

    def renewals_for_contract(self, contract_id: str) -> tuple[RenewalWindow, ...]:
        """Return all renewal windows for a contract."""
        return tuple(r for r in self._renewals.values() if r.contract_id == contract_id)

    # ------------------------------------------------------------------
    # Assessments
    # ------------------------------------------------------------------

    def assess_contract(
        self,
        assessment_id: str,
        contract_id: str,
    ) -> ContractAssessment:
        """Assess a contract's compliance status."""
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError("Duplicate assessment_id")
        contract = self.get_contract(contract_id)
        commitments = self.commitments_for_contract(contract_id)
        total = len(commitments)

        healthy = 0
        at_risk = 0
        breached = 0
        for c in commitments:
            windows = self.sla_windows_for_commitment(c.commitment_id)
            if not windows:
                healthy += 1
                continue
            latest = windows[-1]
            if latest.status == SLAStatus.BREACHED:
                breached += 1
            elif latest.status == SLAStatus.AT_RISK:
                at_risk += 1
            else:
                healthy += 1

        if total == 0:
            overall = 1.0
        else:
            overall = round(healthy / total, 2)

        now = _now_iso()
        assessment = ContractAssessment(
            assessment_id=assessment_id,
            contract_id=contract_id,
            tenant_id=contract.tenant_id,
            total_commitments=total,
            healthy_commitments=healthy,
            at_risk_commitments=at_risk,
            breached_commitments=breached,
            overall_compliance=overall,
            assessed_at=now,
        )
        self._assessments[assessment_id] = assessment
        _emit(self._events, "contract_assessed", {
            "assessment_id": assessment_id, "overall_compliance": overall,
        }, contract_id)
        return assessment

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_contract_violations(self) -> tuple[Any, ...]:
        """Detect contract governance violations."""
        now = _now_iso()
        new_violations: list[Any] = []

        # Overdue renewal windows
        for window in self._renewals.values():
            if window.status == RenewalStatus.SCHEDULED:
                try:
                    close_dt = datetime.fromisoformat(window.closes_at.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > close_dt:
                        vid = stable_identifier("viol-cgov", {
                            "win": window.window_id, "op": "overdue_renewal",
                        })
                        if vid not in self._violations:
                            v = {
                                "violation_id": vid,
                                "contract_id": window.contract_id,
                                "window_id": window.window_id,
                                "operation": "overdue_renewal",
                                "reason": "Renewal window overdue",
                                "detected_at": now,
                            }
                            self._violations[vid] = v
                            new_violations.append(v)
                except (ValueError, TypeError):
                    pass

        # Active contracts past expires_at
        for contract in self._contracts.values():
            if contract.status == ContractStatus.ACTIVE and contract.expires_at:
                try:
                    exp_dt = datetime.fromisoformat(contract.expires_at.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > exp_dt:
                        vid = stable_identifier("viol-cgov", {
                            "cid": contract.contract_id, "op": "expired_active",
                        })
                        if vid not in self._violations:
                            v = {
                                "violation_id": vid,
                                "contract_id": contract.contract_id,
                                "operation": "expired_active_contract",
                                "reason": "Active contract has expired",
                                "detected_at": now,
                            }
                            self._violations[vid] = v
                            new_violations.append(v)
                except (ValueError, TypeError):
                    pass

        if new_violations:
            _emit(self._events, "contract_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def contract_snapshot(self, snapshot_id: str) -> ContractSnapshot:
        """Capture a point-in-time contract governance snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")
        now = _now_iso()
        snap = ContractSnapshot(
            snapshot_id=snapshot_id,
            total_contracts=self.contract_count,
            active_contracts=self.active_contract_count,
            total_commitments=self.commitment_count,
            total_sla_windows=self.sla_window_count,
            total_breaches=self.breach_count,
            total_remedies=self.remedy_count,
            total_renewals=self.renewal_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "contract_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"contracts={self.contract_count}",
            f"active={self.active_contract_count}",
            f"clauses={self.clause_count}",
            f"commitments={self.commitment_count}",
            f"sla_windows={self.sla_window_count}",
            f"breaches={self.breach_count}",
            f"remedies={self.remedy_count}",
            f"renewals={self.renewal_count}",
            f"assessments={self.assessment_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
