"""Purpose: global policy / constitutional governance runtime engine.
Governance scope: registering constitutional rules and bundles,
    evaluating global policy, resolving precedence, managing overrides
    and emergency modes, detecting violations, producing snapshots.
Dependencies: constitutional_governance contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise.
  - HARD_DENY rules cannot be overridden.
  - Emergency mode blocks non-essential actions.
  - Constitutional precedence always wins.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.constitutional_governance import (
    ConstitutionAssessment,
    ConstitutionBundle,
    ConstitutionClosureReport,
    ConstitutionDecision,
    ConstitutionRule,
    ConstitutionRuleKind,
    ConstitutionSnapshot,
    ConstitutionStatus,
    ConstitutionViolation,
    EmergencyGovernanceRecord,
    EmergencyMode,
    GlobalOverrideRecord,
    GlobalPolicyDisposition,
    OverrideDisposition,
    PrecedenceLevel,
    PrecedenceResolution,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str = "") -> EventRecord:
    if not now:
        now = datetime.now(timezone.utc).isoformat()
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


_RULE_TERMINAL = frozenset({ConstitutionStatus.RETIRED})

_PRECEDENCE_RANK = {
    PrecedenceLevel.CONSTITUTIONAL: 0,
    PrecedenceLevel.PLATFORM: 1,
    PrecedenceLevel.TENANT: 2,
    PrecedenceLevel.RUNTIME: 3,
}

_ESSENTIAL_ACTIONS = frozenset()  # empty — all actions non-essential during emergency


class ConstitutionalGovernanceEngine:
    """Global policy / constitutional governance runtime engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._rules: dict[str, ConstitutionRule] = {}
        self._bundles: dict[str, ConstitutionBundle] = {}
        self._bundle_rules: dict[str, list[str]] = {}  # bundle_id -> [rule_id]
        self._overrides: dict[str, GlobalOverrideRecord] = {}
        self._emergency_records: dict[str, EmergencyGovernanceRecord] = {}
        self._decisions: dict[str, ConstitutionDecision] = {}
        self._violations: dict[str, ConstitutionViolation] = {}
        self._resolutions: dict[str, PrecedenceResolution] = {}
        self._assessments: dict[str, ConstitutionAssessment] = {}
        self._emergency_modes: dict[str, EmergencyMode] = {}  # tenant_id -> mode

    def _now(self) -> str:
        """Get current time from injected clock."""
        return self._clock.now_iso()

    # -- Properties ----------------------------------------------------------

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    @property
    def bundle_count(self) -> int:
        return len(self._bundles)

    @property
    def override_count(self) -> int:
        return len(self._overrides)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def resolution_count(self) -> int:
        return len(self._resolutions)

    @property
    def emergency_record_count(self) -> int:
        return len(self._emergency_records)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    # -- Rules ---------------------------------------------------------------

    def register_rule(
        self,
        rule_id: str,
        tenant_id: str,
        display_name: str,
        kind: ConstitutionRuleKind = ConstitutionRuleKind.HARD_DENY,
        precedence: PrecedenceLevel = PrecedenceLevel.CONSTITUTIONAL,
        target_runtime: str = "all",
        target_action: str = "all",
    ) -> ConstitutionRule:
        if rule_id in self._rules:
            raise RuntimeCoreInvariantError(f"duplicate rule_id: {rule_id}")
        now = self._now()
        rule = ConstitutionRule(
            rule_id=rule_id,
            tenant_id=tenant_id,
            display_name=display_name,
            kind=kind,
            precedence=precedence,
            status=ConstitutionStatus.ACTIVE,
            target_runtime=target_runtime,
            target_action=target_action,
            created_at=now,
        )
        self._rules[rule_id] = rule
        _emit(self._events, "register_rule", {"rule_id": rule_id, "tenant_id": tenant_id}, rule_id, now=self._now())
        return rule

    def get_rule(self, rule_id: str) -> ConstitutionRule:
        if rule_id not in self._rules:
            raise RuntimeCoreInvariantError(f"unknown rule_id: {rule_id}")
        return self._rules[rule_id]

    def suspend_rule(self, rule_id: str) -> ConstitutionRule:
        rule = self.get_rule(rule_id)
        if rule.status in _RULE_TERMINAL:
            raise RuntimeCoreInvariantError(f"rule {rule_id} is in terminal state: {rule.status.value}")
        now = self._now()
        updated = ConstitutionRule(
            rule_id=rule.rule_id,
            tenant_id=rule.tenant_id,
            display_name=rule.display_name,
            kind=rule.kind,
            precedence=rule.precedence,
            status=ConstitutionStatus.SUSPENDED,
            target_runtime=rule.target_runtime,
            target_action=rule.target_action,
            created_at=now,
        )
        self._rules[rule_id] = updated
        _emit(self._events, "suspend_rule", {"rule_id": rule_id}, rule_id, now=self._now())
        return updated

    def retire_rule(self, rule_id: str) -> ConstitutionRule:
        rule = self.get_rule(rule_id)
        if rule.status == ConstitutionStatus.RETIRED:
            raise RuntimeCoreInvariantError(f"rule {rule_id} already retired")
        now = self._now()
        updated = ConstitutionRule(
            rule_id=rule.rule_id,
            tenant_id=rule.tenant_id,
            display_name=rule.display_name,
            kind=rule.kind,
            precedence=rule.precedence,
            status=ConstitutionStatus.RETIRED,
            target_runtime=rule.target_runtime,
            target_action=rule.target_action,
            created_at=now,
        )
        self._rules[rule_id] = updated
        _emit(self._events, "retire_rule", {"rule_id": rule_id}, rule_id, now=self._now())
        return updated

    def rules_for_tenant(self, tenant_id: str) -> tuple[ConstitutionRule, ...]:
        return tuple(r for r in self._rules.values() if r.tenant_id == tenant_id)

    def active_rules_for_tenant(self, tenant_id: str) -> tuple[ConstitutionRule, ...]:
        return tuple(r for r in self._rules.values() if r.tenant_id == tenant_id and r.status == ConstitutionStatus.ACTIVE)

    # -- Bundles -------------------------------------------------------------

    def register_bundle(
        self,
        bundle_id: str,
        tenant_id: str,
        display_name: str,
    ) -> ConstitutionBundle:
        if bundle_id in self._bundles:
            raise RuntimeCoreInvariantError(f"duplicate bundle_id: {bundle_id}")
        now = self._now()
        bundle = ConstitutionBundle(
            bundle_id=bundle_id,
            tenant_id=tenant_id,
            display_name=display_name,
            rule_count=0,
            status=ConstitutionStatus.ACTIVE,
            created_at=now,
        )
        self._bundles[bundle_id] = bundle
        self._bundle_rules[bundle_id] = []
        _emit(self._events, "register_bundle", {"bundle_id": bundle_id, "tenant_id": tenant_id}, bundle_id, now=self._now())
        return bundle

    def add_rule_to_bundle(self, bundle_id: str, rule_id: str) -> ConstitutionBundle:
        if bundle_id not in self._bundles:
            raise RuntimeCoreInvariantError(f"unknown bundle_id: {bundle_id}")
        if rule_id not in self._rules:
            raise RuntimeCoreInvariantError(f"unknown rule_id: {rule_id}")
        if rule_id in self._bundle_rules[bundle_id]:
            raise RuntimeCoreInvariantError(f"rule {rule_id} already in bundle {bundle_id}")
        self._bundle_rules[bundle_id].append(rule_id)
        old = self._bundles[bundle_id]
        updated = ConstitutionBundle(
            bundle_id=old.bundle_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            rule_count=old.rule_count + 1,
            status=old.status,
            created_at=old.created_at,
        )
        self._bundles[bundle_id] = updated
        _emit(self._events, "add_rule_to_bundle", {"bundle_id": bundle_id, "rule_id": rule_id}, bundle_id, now=self._now())
        return updated

    def get_bundle(self, bundle_id: str) -> ConstitutionBundle:
        if bundle_id not in self._bundles:
            raise RuntimeCoreInvariantError(f"unknown bundle_id: {bundle_id}")
        return self._bundles[bundle_id]

    def bundles_for_tenant(self, tenant_id: str) -> tuple[ConstitutionBundle, ...]:
        return tuple(b for b in self._bundles.values() if b.tenant_id == tenant_id)

    # -- Global policy evaluation --------------------------------------------

    def evaluate_global_policy(
        self,
        decision_id: str,
        tenant_id: str,
        target_runtime: str,
        target_action: str,
    ) -> ConstitutionDecision:
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError(f"duplicate decision_id: {decision_id}")
        now = self._now()
        em = self._emergency_modes.get(tenant_id, EmergencyMode.NORMAL)

        # Emergency mode blocks non-essential actions
        if em == EmergencyMode.LOCKDOWN:
            decision = ConstitutionDecision(
                decision_id=decision_id,
                tenant_id=tenant_id,
                target_runtime=target_runtime,
                target_action=target_action,
                disposition=GlobalPolicyDisposition.DENIED,
                matched_rule_id="emergency_lockdown",
                emergency_mode=em,
                created_at=now,
            )
            self._decisions[decision_id] = decision
            _emit(self._events, "evaluate_global_policy", {"decision_id": decision_id, "disposition": "denied"}, decision_id, now=self._now())
            return decision

        if em in (EmergencyMode.DEGRADED, EmergencyMode.RESTRICTED):
            decision = ConstitutionDecision(
                decision_id=decision_id,
                tenant_id=tenant_id,
                target_runtime=target_runtime,
                target_action=target_action,
                disposition=GlobalPolicyDisposition.RESTRICTED,
                matched_rule_id=f"emergency_{em.value}",
                emergency_mode=em,
                created_at=now,
            )
            self._decisions[decision_id] = decision
            _emit(self._events, "evaluate_global_policy", {"decision_id": decision_id, "disposition": "restricted"}, decision_id, now=self._now())
            return decision

        # Check active rules — highest precedence first
        active = [r for r in self._rules.values() if r.tenant_id == tenant_id and r.status == ConstitutionStatus.ACTIVE]
        matching = []
        for r in active:
            rt_match = r.target_runtime in ("all", target_runtime)
            act_match = r.target_action in ("all", target_action)
            if rt_match and act_match:
                matching.append(r)

        # Sort by precedence rank (CONSTITUTIONAL=0 is highest)
        matching.sort(key=lambda r: _PRECEDENCE_RANK.get(r.precedence, 99))

        if matching:
            top = matching[0]
            if top.kind == ConstitutionRuleKind.HARD_DENY:
                disp = GlobalPolicyDisposition.DENIED
            elif top.kind == ConstitutionRuleKind.SOFT_DENY:
                disp = GlobalPolicyDisposition.ESCALATED
            elif top.kind == ConstitutionRuleKind.RESTRICT:
                disp = GlobalPolicyDisposition.RESTRICTED
            elif top.kind == ConstitutionRuleKind.ALLOW:
                disp = GlobalPolicyDisposition.ALLOWED
            elif top.kind == ConstitutionRuleKind.REQUIRE:
                disp = GlobalPolicyDisposition.ALLOWED
            else:
                disp = GlobalPolicyDisposition.ALLOWED
            matched_id = top.rule_id
        else:
            disp = GlobalPolicyDisposition.ALLOWED
            matched_id = "none"

        decision = ConstitutionDecision(
            decision_id=decision_id,
            tenant_id=tenant_id,
            target_runtime=target_runtime,
            target_action=target_action,
            disposition=disp,
            matched_rule_id=matched_id,
            emergency_mode=em,
            created_at=now,
        )
        self._decisions[decision_id] = decision
        _emit(self._events, "evaluate_global_policy", {"decision_id": decision_id, "disposition": disp.value}, decision_id, now=self._now())
        return decision

    def get_decision(self, decision_id: str) -> ConstitutionDecision:
        if decision_id not in self._decisions:
            raise RuntimeCoreInvariantError(f"unknown decision_id: {decision_id}")
        return self._decisions[decision_id]

    def decisions_for_tenant(self, tenant_id: str) -> tuple[ConstitutionDecision, ...]:
        return tuple(d for d in self._decisions.values() if d.tenant_id == tenant_id)

    # -- Precedence resolution -----------------------------------------------

    def resolve_precedence(
        self,
        resolution_id: str,
        tenant_id: str,
        rule_id_a: str,
        rule_id_b: str,
    ) -> PrecedenceResolution:
        if resolution_id in self._resolutions:
            raise RuntimeCoreInvariantError(f"duplicate resolution_id: {resolution_id}")
        rule_a = self.get_rule(rule_id_a)
        rule_b = self.get_rule(rule_id_b)

        rank_a = _PRECEDENCE_RANK.get(rule_a.precedence, 99)
        rank_b = _PRECEDENCE_RANK.get(rule_b.precedence, 99)

        if rank_a <= rank_b:
            winner, loser = rule_a, rule_b
        else:
            winner, loser = rule_b, rule_a

        now = self._now()
        resolution = PrecedenceResolution(
            resolution_id=resolution_id,
            tenant_id=tenant_id,
            winning_rule_id=winner.rule_id,
            losing_rule_id=loser.rule_id,
            winning_precedence=winner.precedence,
            losing_precedence=loser.precedence,
            resolved_at=now,
        )
        self._resolutions[resolution_id] = resolution
        _emit(self._events, "resolve_precedence", {"resolution_id": resolution_id, "winner": winner.rule_id}, resolution_id, now=self._now())
        return resolution

    def resolutions_for_tenant(self, tenant_id: str) -> tuple[PrecedenceResolution, ...]:
        return tuple(r for r in self._resolutions.values() if r.tenant_id == tenant_id)

    # -- Overrides -----------------------------------------------------------

    def apply_override(
        self,
        override_id: str,
        rule_id: str,
        tenant_id: str,
        authority_ref: str,
        reason: str = "executive override",
    ) -> GlobalOverrideRecord:
        if override_id in self._overrides:
            raise RuntimeCoreInvariantError(f"duplicate override_id: {override_id}")
        rule = self.get_rule(rule_id)
        now = self._now()

        # HARD_DENY rules cannot be overridden — record but deny
        if rule.kind == ConstitutionRuleKind.HARD_DENY:
            override = GlobalOverrideRecord(
                override_id=override_id,
                rule_id=rule_id,
                tenant_id=tenant_id,
                authority_ref=authority_ref,
                disposition=OverrideDisposition.DENIED,
                reason=f"hard_deny rule cannot be overridden: {reason}",
                created_at=now,
            )
            self._overrides[override_id] = override
            # Also record a violation
            vid = stable_identifier("viol-cgov", {"override_id": override_id, "rule_id": rule_id})
            v = ConstitutionViolation(
                violation_id=vid,
                tenant_id=tenant_id,
                operation="override_hard_deny",
                reason=f"attempted override of hard_deny rule {rule_id}",
                detected_at=now,
            )
            self._violations[vid] = v
            _emit(self._events, "apply_override_denied", {"override_id": override_id, "rule_id": rule_id}, override_id, now=self._now())
            return override

        # For non-hard-deny rules, apply the override
        override = GlobalOverrideRecord(
            override_id=override_id,
            rule_id=rule_id,
            tenant_id=tenant_id,
            authority_ref=authority_ref,
            disposition=OverrideDisposition.APPLIED,
            reason=reason,
            created_at=now,
        )
        self._overrides[override_id] = override
        # Suspend the overridden rule
        if rule.status == ConstitutionStatus.ACTIVE:
            self._rules[rule_id] = ConstitutionRule(
                rule_id=rule.rule_id,
                tenant_id=rule.tenant_id,
                display_name=rule.display_name,
                kind=rule.kind,
                precedence=rule.precedence,
                status=ConstitutionStatus.SUSPENDED,
                target_runtime=rule.target_runtime,
                target_action=rule.target_action,
                created_at=now,
            )
        _emit(self._events, "apply_override", {"override_id": override_id, "rule_id": rule_id}, override_id, now=self._now())
        return override

    def get_override(self, override_id: str) -> GlobalOverrideRecord:
        if override_id not in self._overrides:
            raise RuntimeCoreInvariantError(f"unknown override_id: {override_id}")
        return self._overrides[override_id]

    def overrides_for_tenant(self, tenant_id: str) -> tuple[GlobalOverrideRecord, ...]:
        return tuple(o for o in self._overrides.values() if o.tenant_id == tenant_id)

    # -- Emergency modes -----------------------------------------------------

    def enter_emergency_mode(
        self,
        emergency_id: str,
        tenant_id: str,
        mode: EmergencyMode,
        authority_ref: str,
        reason: str = "emergency declared",
    ) -> EmergencyGovernanceRecord:
        if emergency_id in self._emergency_records:
            raise RuntimeCoreInvariantError(f"duplicate emergency_id: {emergency_id}")
        if mode == EmergencyMode.NORMAL:
            raise RuntimeCoreInvariantError("cannot enter NORMAL mode — use exit_emergency_mode")
        prev = self._emergency_modes.get(tenant_id, EmergencyMode.NORMAL)
        now = self._now()
        record = EmergencyGovernanceRecord(
            emergency_id=emergency_id,
            tenant_id=tenant_id,
            mode=mode,
            previous_mode=prev,
            authority_ref=authority_ref,
            reason=reason,
            created_at=now,
        )
        self._emergency_records[emergency_id] = record
        self._emergency_modes[tenant_id] = mode
        _emit(self._events, "enter_emergency_mode", {"emergency_id": emergency_id, "mode": mode.value}, emergency_id, now=self._now())
        return record

    def exit_emergency_mode(
        self,
        emergency_id: str,
        tenant_id: str,
        authority_ref: str,
        reason: str = "emergency resolved",
    ) -> EmergencyGovernanceRecord:
        if emergency_id in self._emergency_records:
            raise RuntimeCoreInvariantError(f"duplicate emergency_id: {emergency_id}")
        prev = self._emergency_modes.get(tenant_id, EmergencyMode.NORMAL)
        if prev == EmergencyMode.NORMAL:
            raise RuntimeCoreInvariantError(f"tenant {tenant_id} is not in emergency mode")
        now = self._now()
        record = EmergencyGovernanceRecord(
            emergency_id=emergency_id,
            tenant_id=tenant_id,
            mode=EmergencyMode.NORMAL,
            previous_mode=prev,
            authority_ref=authority_ref,
            reason=reason,
            created_at=now,
        )
        self._emergency_records[emergency_id] = record
        self._emergency_modes[tenant_id] = EmergencyMode.NORMAL
        _emit(self._events, "exit_emergency_mode", {"emergency_id": emergency_id, "previous_mode": prev.value}, emergency_id, now=self._now())
        return record

    def get_emergency_mode(self, tenant_id: str) -> EmergencyMode:
        return self._emergency_modes.get(tenant_id, EmergencyMode.NORMAL)

    def emergency_records_for_tenant(self, tenant_id: str) -> tuple[EmergencyGovernanceRecord, ...]:
        return tuple(r for r in self._emergency_records.values() if r.tenant_id == tenant_id)

    # -- Snapshots -----------------------------------------------------------

    def constitution_snapshot(self, snapshot_id: str, tenant_id: str) -> ConstitutionSnapshot:
        now = self._now()
        rules = self.rules_for_tenant(tenant_id)
        active = self.active_rules_for_tenant(tenant_id)
        bundles = self.bundles_for_tenant(tenant_id)
        overrides = self.overrides_for_tenant(tenant_id)
        decisions = self.decisions_for_tenant(tenant_id)
        violations = tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)
        em = self.get_emergency_mode(tenant_id)

        snap = ConstitutionSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_rules=len(rules),
            active_rules=len(active),
            total_bundles=len(bundles),
            total_overrides=len(overrides),
            total_decisions=len(decisions),
            total_violations=len(violations),
            emergency_mode=em,
            captured_at=now,
        )
        _emit(self._events, "constitution_snapshot", {"snapshot_id": snapshot_id, "tenant_id": tenant_id}, snapshot_id, now=self._now())
        return snap

    # -- Assessment ----------------------------------------------------------

    def constitution_assessment(self, assessment_id: str, tenant_id: str) -> ConstitutionAssessment:
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError(f"duplicate assessment_id: {assessment_id}")
        now = self._now()
        rules = self.rules_for_tenant(tenant_id)
        active = self.active_rules_for_tenant(tenant_id)
        overrides = self.overrides_for_tenant(tenant_id)
        violations = tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

        total = len(rules)
        active_count = len(active)
        # compliance = active / total if total > 0 else 1.0, adjusted by violations
        if total > 0:
            base = active_count / total
            penalty = min(len(violations) * 0.1, base)
            score = round(base - penalty, 4)
        else:
            score = 1.0

        assessment = ConstitutionAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_rules=total,
            active_rules=active_count,
            compliance_score=max(0.0, min(1.0, score)),
            override_count=len(overrides),
            violation_count=len(violations),
            assessed_at=now,
        )
        self._assessments[assessment_id] = assessment
        _emit(self._events, "constitution_assessment", {"assessment_id": assessment_id}, assessment_id, now=self._now())
        return assessment

    # -- Violations ----------------------------------------------------------

    def detect_constitution_violations(self, tenant_id: str) -> tuple[ConstitutionViolation, ...]:
        now = self._now()
        new_violations: list[ConstitutionViolation] = []

        # Check for suspended rules with no override record
        for rule in self._rules.values():
            if rule.tenant_id != tenant_id:
                continue
            if rule.status == ConstitutionStatus.SUSPENDED:
                has_override = any(
                    o.rule_id == rule.rule_id for o in self._overrides.values()
                )
                if not has_override:
                    vid = stable_identifier("viol-cgov", {"op": "suspended_no_override", "rule_id": rule.rule_id})
                    if vid not in self._violations:
                        v = ConstitutionViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="suspended_no_override",
                            reason=f"rule {rule.rule_id} suspended without override record",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # Check for empty bundles
        for bundle in self._bundles.values():
            if bundle.tenant_id != tenant_id:
                continue
            if bundle.rule_count == 0 and bundle.status == ConstitutionStatus.ACTIVE:
                vid = stable_identifier("viol-cgov", {"op": "empty_bundle", "bundle_id": bundle.bundle_id})
                if vid not in self._violations:
                    v = ConstitutionViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="empty_bundle",
                        reason=f"active bundle {bundle.bundle_id} has no rules",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # Check for denied decisions (policy was violated somewhere)
        for dec in self._decisions.values():
            if dec.tenant_id != tenant_id:
                continue
            if dec.disposition == GlobalPolicyDisposition.DENIED and dec.matched_rule_id not in ("emergency_lockdown", "none"):
                vid = stable_identifier("viol-cgov", {"op": "policy_denied", "decision_id": dec.decision_id})
                if vid not in self._violations:
                    v = ConstitutionViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="policy_denied",
                        reason=f"action denied by rule {dec.matched_rule_id}",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "detect_constitution_violations", {"tenant_id": tenant_id, "count": len(new_violations)}, tenant_id, now=self._now())
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[ConstitutionViolation, ...]:
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # -- Closure report ------------------------------------------------------

    def closure_report(self, report_id: str, tenant_id: str) -> ConstitutionClosureReport:
        now = self._now()
        report = ConstitutionClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_rules=len(self.rules_for_tenant(tenant_id)),
            total_bundles=len(self.bundles_for_tenant(tenant_id)),
            total_overrides=len(self.overrides_for_tenant(tenant_id)),
            total_decisions=len(self.decisions_for_tenant(tenant_id)),
            total_violations=len(self.violations_for_tenant(tenant_id)),
            total_resolutions=len(self.resolutions_for_tenant(tenant_id)),
            created_at=now,
        )
        _emit(self._events, "closure_report", {"report_id": report_id}, report_id, now=self._now())
        return report

    # -- State hash ----------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._rules):
            parts.append(f"rule:{k}:{self._rules[k].status.value}")
        for k in sorted(self._bundles):
            parts.append(f"bundle:{k}:{self._bundles[k].rule_count}")
        for k in sorted(self._overrides):
            parts.append(f"override:{k}:{self._overrides[k].disposition.value}")
        for k in sorted(self._decisions):
            parts.append(f"decision:{k}:{self._decisions[k].disposition.value}")
        for k in sorted(self._violations):
            parts.append(f"violation:{k}")
        for k in sorted(self._resolutions):
            parts.append(f"resolution:{k}")
        for t in sorted(self._emergency_modes):
            parts.append(f"emergency:{t}:{self._emergency_modes[t].value}")
        return sha256("|".join(parts).encode()).hexdigest()

    # -- Snapshot / Restore --------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        return {
            "rules": self._rules,
            "bundles": self._bundles,
            "bundle_rules": self._bundle_rules,
            "overrides": self._overrides,
            "emergency_records": self._emergency_records,
            "decisions": self._decisions,
            "violations": self._violations,
            "resolutions": self._resolutions,
            "assessments": self._assessments,
            "emergency_modes": self._emergency_modes,
        }

    def snapshot(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else (v.value if hasattr(v, "value") else v)
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result
