"""Purpose: partner / ecosystem / marketplace runtime engine.
Governance scope: registering partners, linking to accounts, managing
    ecosystem agreements, revenue shares, commitments, health tracking,
    detecting violations, producing immutable snapshots.
Dependencies: partner_runtime contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise.
  - Terminated partners cannot be modified.
  - Revenue shares auto-compute from agreement percentage.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.partner_runtime import (
    EcosystemAgreement,
    EcosystemRole,
    PartnerAccountLink,
    PartnerClosureReport,
    PartnerCommitment,
    PartnerDecision,
    PartnerDisposition,
    PartnerHealthSnapshot,
    PartnerHealthStatus,
    PartnerKind,
    PartnerRecord,
    PartnerSnapshot,
    PartnerStatus,
    PartnerViolation,
    RevenueShareRecord,
    RevenueShareStatus,
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
        event_id=stable_identifier("evt-prt", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_PARTNER_TERMINAL = frozenset({PartnerStatus.TERMINATED})
_REVENUE_SHARE_TERMINAL = frozenset({RevenueShareStatus.SETTLED, RevenueShareStatus.CANCELLED})


class PartnerRuntimeEngine:
    """Partner / ecosystem / marketplace runtime engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._partners: dict[str, PartnerRecord] = {}
        self._links: dict[str, PartnerAccountLink] = {}
        self._agreements: dict[str, EcosystemAgreement] = {}
        self._revenue_shares: dict[str, RevenueShareRecord] = {}
        self._commitments: dict[str, PartnerCommitment] = {}
        self._health_snapshots: dict[str, PartnerHealthSnapshot] = {}
        self._decisions: dict[str, PartnerDecision] = {}
        self._violations: dict[str, PartnerViolation] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def partner_count(self) -> int:
        return len(self._partners)

    @property
    def link_count(self) -> int:
        return len(self._links)

    @property
    def agreement_count(self) -> int:
        return len(self._agreements)

    @property
    def revenue_share_count(self) -> int:
        return len(self._revenue_shares)

    @property
    def commitment_count(self) -> int:
        return len(self._commitments)

    @property
    def health_snapshot_count(self) -> int:
        return len(self._health_snapshots)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Partners
    # ------------------------------------------------------------------

    def register_partner(
        self,
        partner_id: str,
        tenant_id: str,
        display_name: str,
        kind: PartnerKind = PartnerKind.RESELLER,
        tier: str = "standard",
        status: PartnerStatus = PartnerStatus.ACTIVE,
    ) -> PartnerRecord:
        if partner_id in self._partners:
            raise RuntimeCoreInvariantError("partner already registered")
        now = _now_iso()
        record = PartnerRecord(
            partner_id=partner_id,
            tenant_id=tenant_id,
            display_name=display_name,
            kind=kind,
            status=status,
            tier=tier,
            account_link_count=0,
            created_at=now,
        )
        self._partners[partner_id] = record
        _emit(self._events, "register_partner", {"partner_id": partner_id, "kind": kind.value}, partner_id)
        return record

    def get_partner(self, partner_id: str) -> PartnerRecord:
        if partner_id not in self._partners:
            raise RuntimeCoreInvariantError("unknown partner")
        return self._partners[partner_id]

    def update_partner_status(self, partner_id: str, status: PartnerStatus) -> PartnerRecord:
        if partner_id not in self._partners:
            raise RuntimeCoreInvariantError("unknown partner")
        old = self._partners[partner_id]
        if old.status in _PARTNER_TERMINAL:
            raise RuntimeCoreInvariantError("partner is in terminal state")
        updated = PartnerRecord(
            partner_id=old.partner_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            kind=old.kind,
            status=status,
            tier=old.tier,
            account_link_count=old.account_link_count,
            created_at=old.created_at,
        )
        self._partners[partner_id] = updated
        _emit(self._events, "update_partner_status", {"partner_id": partner_id, "status": status.value}, partner_id)
        return updated

    def partners_for_tenant(self, tenant_id: str) -> tuple[PartnerRecord, ...]:
        return tuple(p for p in self._partners.values() if p.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Account links
    # ------------------------------------------------------------------

    def link_partner_to_account(
        self,
        link_id: str,
        partner_id: str,
        account_id: str,
        tenant_id: str,
        role: EcosystemRole = EcosystemRole.INTERMEDIARY,
    ) -> PartnerAccountLink:
        if link_id in self._links:
            raise RuntimeCoreInvariantError("link already exists")
        if partner_id not in self._partners:
            raise RuntimeCoreInvariantError("unknown partner")
        partner = self._partners[partner_id]
        if partner.status in _PARTNER_TERMINAL:
            raise RuntimeCoreInvariantError("partner is in terminal state")
        now = _now_iso()
        link = PartnerAccountLink(
            link_id=link_id,
            partner_id=partner_id,
            account_id=account_id,
            tenant_id=tenant_id,
            role=role,
            created_at=now,
        )
        self._links[link_id] = link
        # Increment partner link count
        updated = PartnerRecord(
            partner_id=partner.partner_id,
            tenant_id=partner.tenant_id,
            display_name=partner.display_name,
            kind=partner.kind,
            status=partner.status,
            tier=partner.tier,
            account_link_count=partner.account_link_count + 1,
            created_at=partner.created_at,
        )
        self._partners[partner_id] = updated
        _emit(self._events, "link_partner_to_account", {"link_id": link_id, "partner_id": partner_id, "account_id": account_id}, link_id)
        return link

    def links_for_partner(self, partner_id: str) -> tuple[PartnerAccountLink, ...]:
        return tuple(l for l in self._links.values() if l.partner_id == partner_id)

    def links_for_account(self, account_id: str) -> tuple[PartnerAccountLink, ...]:
        return tuple(l for l in self._links.values() if l.account_id == account_id)

    # ------------------------------------------------------------------
    # Ecosystem agreements
    # ------------------------------------------------------------------

    def register_agreement(
        self,
        agreement_id: str,
        partner_id: str,
        tenant_id: str,
        title: str,
        contract_ref: str = "",
        revenue_share_pct: float = 0.0,
    ) -> EcosystemAgreement:
        if agreement_id in self._agreements:
            raise RuntimeCoreInvariantError("agreement already exists")
        if partner_id not in self._partners:
            raise RuntimeCoreInvariantError("unknown partner")
        now = _now_iso()
        agreement = EcosystemAgreement(
            agreement_id=agreement_id,
            partner_id=partner_id,
            tenant_id=tenant_id,
            title=title,
            contract_ref=contract_ref if contract_ref else "none",
            revenue_share_pct=revenue_share_pct,
            created_at=now,
        )
        self._agreements[agreement_id] = agreement
        _emit(self._events, "register_agreement", {"agreement_id": agreement_id, "partner_id": partner_id}, agreement_id)
        return agreement

    def get_agreement(self, agreement_id: str) -> EcosystemAgreement:
        if agreement_id not in self._agreements:
            raise RuntimeCoreInvariantError("unknown agreement")
        return self._agreements[agreement_id]

    def agreements_for_partner(self, partner_id: str) -> tuple[EcosystemAgreement, ...]:
        return tuple(a for a in self._agreements.values() if a.partner_id == partner_id)

    # ------------------------------------------------------------------
    # Revenue shares
    # ------------------------------------------------------------------

    def record_revenue_share(
        self,
        share_id: str,
        partner_id: str,
        agreement_id: str,
        tenant_id: str,
        gross_amount: float,
    ) -> RevenueShareRecord:
        if share_id in self._revenue_shares:
            raise RuntimeCoreInvariantError("revenue share already exists")
        if partner_id not in self._partners:
            raise RuntimeCoreInvariantError("unknown partner")
        if agreement_id not in self._agreements:
            raise RuntimeCoreInvariantError("unknown agreement")
        agreement = self._agreements[agreement_id]
        share_pct = agreement.revenue_share_pct
        share_amount = round(gross_amount * share_pct, 2)
        now = _now_iso()
        record = RevenueShareRecord(
            share_id=share_id,
            partner_id=partner_id,
            agreement_id=agreement_id,
            tenant_id=tenant_id,
            gross_amount=gross_amount,
            share_amount=share_amount,
            share_pct=share_pct,
            status=RevenueShareStatus.PENDING,
            created_at=now,
        )
        self._revenue_shares[share_id] = record
        _emit(self._events, "record_revenue_share", {"share_id": share_id, "gross": gross_amount, "share": share_amount}, share_id)
        return record

    def settle_revenue_share(self, share_id: str) -> RevenueShareRecord:
        if share_id not in self._revenue_shares:
            raise RuntimeCoreInvariantError("unknown revenue share")
        old = self._revenue_shares[share_id]
        if old.status in _REVENUE_SHARE_TERMINAL:
            raise RuntimeCoreInvariantError("revenue share is in terminal state")
        updated = RevenueShareRecord(
            share_id=old.share_id,
            partner_id=old.partner_id,
            agreement_id=old.agreement_id,
            tenant_id=old.tenant_id,
            gross_amount=old.gross_amount,
            share_amount=old.share_amount,
            share_pct=old.share_pct,
            status=RevenueShareStatus.SETTLED,
            created_at=old.created_at,
        )
        self._revenue_shares[share_id] = updated
        _emit(self._events, "settle_revenue_share", {"share_id": share_id}, share_id)
        return updated

    def dispute_revenue_share(self, share_id: str) -> RevenueShareRecord:
        if share_id not in self._revenue_shares:
            raise RuntimeCoreInvariantError("unknown revenue share")
        old = self._revenue_shares[share_id]
        if old.status in _REVENUE_SHARE_TERMINAL:
            raise RuntimeCoreInvariantError("revenue share is in terminal state")
        updated = RevenueShareRecord(
            share_id=old.share_id,
            partner_id=old.partner_id,
            agreement_id=old.agreement_id,
            tenant_id=old.tenant_id,
            gross_amount=old.gross_amount,
            share_amount=old.share_amount,
            share_pct=old.share_pct,
            status=RevenueShareStatus.DISPUTED,
            created_at=old.created_at,
        )
        self._revenue_shares[share_id] = updated
        _emit(self._events, "dispute_revenue_share", {"share_id": share_id}, share_id)
        return updated

    def revenue_shares_for_partner(self, partner_id: str) -> tuple[RevenueShareRecord, ...]:
        return tuple(r for r in self._revenue_shares.values() if r.partner_id == partner_id)

    # ------------------------------------------------------------------
    # Commitments
    # ------------------------------------------------------------------

    def record_commitment(
        self,
        commitment_id: str,
        partner_id: str,
        tenant_id: str,
        description: str,
        target_value: float,
        actual_value: float = 0.0,
    ) -> PartnerCommitment:
        if commitment_id in self._commitments:
            raise RuntimeCoreInvariantError("commitment already exists")
        if partner_id not in self._partners:
            raise RuntimeCoreInvariantError("unknown partner")
        now = _now_iso()
        met = actual_value >= target_value
        commitment = PartnerCommitment(
            commitment_id=commitment_id,
            partner_id=partner_id,
            tenant_id=tenant_id,
            description=description,
            target_value=target_value,
            actual_value=actual_value,
            met=met,
            assessed_at=now,
        )
        self._commitments[commitment_id] = commitment
        _emit(self._events, "record_commitment", {"commitment_id": commitment_id, "met": met}, commitment_id)
        return commitment

    def commitments_for_partner(self, partner_id: str) -> tuple[PartnerCommitment, ...]:
        return tuple(c for c in self._commitments.values() if c.partner_id == partner_id)

    # ------------------------------------------------------------------
    # Partner health
    # ------------------------------------------------------------------

    def partner_health(
        self,
        snapshot_id: str,
        partner_id: str,
        tenant_id: str,
        sla_breaches: int = 0,
        open_cases: int = 0,
        billing_issues: int = 0,
        commitment_failures: int = 0,
    ) -> PartnerHealthSnapshot:
        if snapshot_id in self._health_snapshots:
            raise RuntimeCoreInvariantError("health snapshot already exists")
        if partner_id not in self._partners:
            raise RuntimeCoreInvariantError("unknown partner")
        now = _now_iso()
        score = 1.0
        score -= sla_breaches * 0.15
        score -= open_cases * 0.1
        score -= billing_issues * 0.2
        score -= commitment_failures * 0.15
        score = max(0.0, min(1.0, round(score, 4)))
        health_status = self._derive_health_status(score)

        snapshot = PartnerHealthSnapshot(
            snapshot_id=snapshot_id,
            partner_id=partner_id,
            tenant_id=tenant_id,
            health_status=health_status,
            health_score=score,
            sla_breaches=sla_breaches,
            open_cases=open_cases,
            billing_issues=billing_issues,
            commitment_failures=commitment_failures,
            captured_at=now,
        )
        self._health_snapshots[snapshot_id] = snapshot
        _emit(self._events, "partner_health", {"snapshot_id": snapshot_id, "partner_id": partner_id, "score": score}, snapshot_id)

        # Auto-escalation on CRITICAL
        if health_status == PartnerHealthStatus.CRITICAL:
            dec_id = stable_identifier("dec-prt", {"partner_id": partner_id, "snapshot_id": snapshot_id})
            if dec_id not in self._decisions:
                decision = PartnerDecision(
                    decision_id=dec_id,
                    tenant_id=tenant_id,
                    partner_id=partner_id,
                    disposition=PartnerDisposition.ESCALATED,
                    reason="partner health critical",
                    decided_at=now,
                )
                self._decisions[dec_id] = decision

        return snapshot

    def health_snapshots_for_partner(self, partner_id: str) -> tuple[PartnerHealthSnapshot, ...]:
        return tuple(h for h in self._health_snapshots.values() if h.partner_id == partner_id)

    # ------------------------------------------------------------------
    # Partner snapshot
    # ------------------------------------------------------------------

    def partner_snapshot(self, snapshot_id: str) -> PartnerSnapshot:
        now = _now_iso()
        return PartnerSnapshot(
            snapshot_id=snapshot_id,
            total_partners=len(self._partners),
            total_links=len(self._links),
            total_agreements=len(self._agreements),
            total_revenue_shares=len(self._revenue_shares),
            total_commitments=len(self._commitments),
            total_health_snapshots=len(self._health_snapshots),
            total_decisions=len(self._decisions),
            total_violations=len(self._violations),
            captured_at=now,
        )

    # ------------------------------------------------------------------
    # Violations
    # ------------------------------------------------------------------

    def detect_partner_violations(self, tenant_id: str) -> tuple[PartnerViolation, ...]:
        """Detect partner violations. Idempotent per violation_id."""
        now = _now_iso()
        new_violations: list[PartnerViolation] = []

        # 1. Active partners with no agreements
        for p in self._partners.values():
            if p.tenant_id == tenant_id and p.status == PartnerStatus.ACTIVE:
                agreements = self.agreements_for_partner(p.partner_id)
                if not agreements:
                    vid = stable_identifier("viol-prt", {"type": "no_agreement", "partner_id": p.partner_id})
                    if vid not in self._violations:
                        v = PartnerViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            partner_id=p.partner_id,
                            operation="no_agreement",
                            reason="active partner has no ecosystem agreement",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # 2. Disputed revenue shares
        for rs in self._revenue_shares.values():
            if rs.tenant_id == tenant_id and rs.status == RevenueShareStatus.DISPUTED:
                vid = stable_identifier("viol-prt", {"type": "disputed_revenue", "share_id": rs.share_id})
                if vid not in self._violations:
                    v = PartnerViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        partner_id=rs.partner_id,
                        operation="disputed_revenue",
                        reason="revenue share is disputed",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3. Unmet commitments
        for c in self._commitments.values():
            if c.tenant_id == tenant_id and not c.met:
                vid = stable_identifier("viol-prt", {"type": "unmet_commitment", "commitment_id": c.commitment_id})
                if vid not in self._violations:
                    v = PartnerViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        partner_id=c.partner_id,
                        operation="unmet_commitment",
                        reason="commitment unmet",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        _emit(self._events, "detect_partner_violations", {"tenant_id": tenant_id, "count": len(new_violations)}, tenant_id)
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[PartnerViolation, ...]:
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def closure_report(self, report_id: str, tenant_id: str) -> PartnerClosureReport:
        now = _now_iso()
        return PartnerClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_partners=len([p for p in self._partners.values() if p.tenant_id == tenant_id]),
            total_links=len([l for l in self._links.values() if l.tenant_id == tenant_id]),
            total_agreements=len([a for a in self._agreements.values() if a.tenant_id == tenant_id]),
            total_revenue_shares=len([r for r in self._revenue_shares.values() if r.tenant_id == tenant_id]),
            total_commitments=len([c for c in self._commitments.values() if c.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.tenant_id == tenant_id]),
            closed_at=now,
        )

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._partners):
            parts.append(f"p:{k}")
        for k in sorted(self._links):
            parts.append(f"l:{k}")
        for k in sorted(self._agreements):
            parts.append(f"a:{k}")
        for k in sorted(self._revenue_shares):
            parts.append(f"rs:{k}")
        for k in sorted(self._commitments):
            parts.append(f"c:{k}")
        for k in sorted(self._health_snapshots):
            parts.append(f"h:{k}")
        for k in sorted(self._decisions):
            parts.append(f"d:{k}")
        for k in sorted(self._violations):
            parts.append(f"v:{k}")
        return sha256("|".join(parts).encode()).hexdigest()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_health_status(score: float) -> PartnerHealthStatus:
        if score >= 0.8:
            return PartnerHealthStatus.HEALTHY
        if score >= 0.5:
            return PartnerHealthStatus.AT_RISK
        if score >= 0.3:
            return PartnerHealthStatus.DEGRADED
        return PartnerHealthStatus.CRITICAL
