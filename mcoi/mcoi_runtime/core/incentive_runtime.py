"""Purpose: mechanism design / incentives runtime engine.
Governance scope: managing incentives, behavior observations, gaming
    detection, policy effects, contract bindings, decisions, assessments,
    violations, snapshots, and closure reports.
Dependencies: incentive_runtime contracts, event_spine, core invariants.
Invariants:
  - EXPIRED/RETIRED incentives are terminal.
  - Duplicate IDs raise RuntimeCoreInvariantError.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.incentive_runtime import (
    BehaviorDisposition,
    BehaviorObservation,
    ContractIncentiveBinding,
    GamingDetection,
    IncentiveAssessment,
    IncentiveClosureReport,
    IncentiveDecision,
    IncentiveKind,
    IncentiveRecord,
    IncentiveRiskLevel,
    IncentiveSnapshot,
    IncentiveStatus,
    IncentiveViolation,
    PolicyEffect,
    PolicyEffectKind,
    RiskOfGaming,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


_INCENTIVE_TERMINAL = frozenset({IncentiveStatus.EXPIRED, IncentiveStatus.RETIRED})


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-incn", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class IncentiveRuntimeEngine:
    """Engine for governed mechanism design / incentives runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._incentives: dict[str, IncentiveRecord] = {}
        self._observations: dict[str, BehaviorObservation] = {}
        self._detections: dict[str, GamingDetection] = {}
        self._effects: dict[str, PolicyEffect] = {}
        self._bindings: dict[str, ContractIncentiveBinding] = {}
        self._decisions: dict[str, IncentiveDecision] = {}
        self._violations: dict[str, IncentiveViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def incentive_count(self) -> int:
        return len(self._incentives)

    @property
    def observation_count(self) -> int:
        return len(self._observations)

    @property
    def detection_count(self) -> int:
        return len(self._detections)

    @property
    def effect_count(self) -> int:
        return len(self._effects)

    @property
    def binding_count(self) -> int:
        return len(self._bindings)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Incentive lifecycle
    # ------------------------------------------------------------------

    def register_incentive(
        self,
        incentive_id: str,
        tenant_id: str,
        display_name: str,
        *,
        kind: IncentiveKind = IncentiveKind.REWARD,
        target_actor_ref: str = "default-actor",
        value: float = 0.0,
    ) -> IncentiveRecord:
        """Register a new incentive."""
        if incentive_id in self._incentives:
            raise RuntimeCoreInvariantError(f"Duplicate incentive_id: {incentive_id}")
        now = self._now()
        record = IncentiveRecord(
            incentive_id=incentive_id,
            tenant_id=tenant_id,
            display_name=display_name,
            kind=kind,
            status=IncentiveStatus.ACTIVE,
            target_actor_ref=target_actor_ref,
            value=value,
            created_at=now,
        )
        self._incentives[incentive_id] = record
        _emit(self._events, "incentive_registered", {
            "incentive_id": incentive_id, "kind": kind.value, "value": value,
        }, incentive_id, now)
        return record

    def get_incentive(self, incentive_id: str) -> IncentiveRecord:
        """Get an incentive by ID."""
        inc = self._incentives.get(incentive_id)
        if inc is None:
            raise RuntimeCoreInvariantError(f"Unknown incentive_id: {incentive_id}")
        return inc

    def _transition_incentive(self, incentive_id: str, new_status: IncentiveStatus) -> IncentiveRecord:
        """Internal: transition incentive to a new status with terminal guards."""
        old = self.get_incentive(incentive_id)
        if old.status in _INCENTIVE_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Incentive already in terminal status {old.status.value}"
            )
        now = self._now()
        updated = IncentiveRecord(
            incentive_id=old.incentive_id, tenant_id=old.tenant_id,
            display_name=old.display_name, kind=old.kind,
            status=new_status, target_actor_ref=old.target_actor_ref,
            value=old.value, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._incentives[incentive_id] = updated
        _emit(self._events, f"incentive_{new_status.value}", {
            "incentive_id": incentive_id,
        }, incentive_id, now)
        return updated

    def suspend_incentive(self, incentive_id: str) -> IncentiveRecord:
        """Suspend an active incentive."""
        return self._transition_incentive(incentive_id, IncentiveStatus.SUSPENDED)

    def expire_incentive(self, incentive_id: str) -> IncentiveRecord:
        """Expire an incentive (terminal)."""
        return self._transition_incentive(incentive_id, IncentiveStatus.EXPIRED)

    def retire_incentive(self, incentive_id: str) -> IncentiveRecord:
        """Retire an incentive (terminal)."""
        return self._transition_incentive(incentive_id, IncentiveStatus.RETIRED)

    # ------------------------------------------------------------------
    # Behavior observations
    # ------------------------------------------------------------------

    def record_behavior_observation(
        self,
        observation_id: str,
        tenant_id: str,
        actor_ref: str,
        incentive_ref: str,
        *,
        disposition: BehaviorDisposition = BehaviorDisposition.NEUTRAL,
    ) -> BehaviorObservation:
        """Record an observed behavior relative to an incentive."""
        if observation_id in self._observations:
            raise RuntimeCoreInvariantError(f"Duplicate observation_id: {observation_id}")
        if incentive_ref not in self._incentives:
            raise RuntimeCoreInvariantError(f"Unknown incentive_ref: {incentive_ref}")
        now = self._now()
        obs = BehaviorObservation(
            observation_id=observation_id,
            tenant_id=tenant_id,
            actor_ref=actor_ref,
            incentive_ref=incentive_ref,
            disposition=disposition,
            created_at=now,
        )
        self._observations[observation_id] = obs
        _emit(self._events, "behavior_observed", {
            "observation_id": observation_id, "actor_ref": actor_ref,
            "disposition": disposition.value,
        }, observation_id, now)
        return obs

    # ------------------------------------------------------------------
    # Gaming detection
    # ------------------------------------------------------------------

    def detect_gaming(
        self,
        detection_id: str,
        tenant_id: str,
        actor_ref: str,
        incentive_ref: str,
        *,
        evidence: str = "behavioral pattern",
    ) -> GamingDetection | None:
        """Detect gaming if actor has MISALIGNED+repeated or GAMING observations.

        Returns a GamingDetection if gaming is detected, None otherwise.
        """
        if detection_id in self._detections:
            raise RuntimeCoreInvariantError(f"Duplicate detection_id: {detection_id}")

        # Check for GAMING disposition
        gaming_obs = [
            o for o in self._observations.values()
            if o.actor_ref == actor_ref
            and o.incentive_ref == incentive_ref
            and o.disposition == BehaviorDisposition.GAMING
        ]

        # Check for repeated MISALIGNED
        misaligned_obs = [
            o for o in self._observations.values()
            if o.actor_ref == actor_ref
            and o.incentive_ref == incentive_ref
            and o.disposition == BehaviorDisposition.MISALIGNED
        ]

        if not gaming_obs and len(misaligned_obs) < 2:
            return None

        # Determine risk level
        if gaming_obs:
            risk = RiskOfGaming.HIGH
        elif len(misaligned_obs) >= 3:
            risk = RiskOfGaming.HIGH
        else:
            risk = RiskOfGaming.MODERATE

        now = self._now()
        detection = GamingDetection(
            detection_id=detection_id,
            tenant_id=tenant_id,
            actor_ref=actor_ref,
            incentive_ref=incentive_ref,
            risk=risk,
            evidence=evidence,
            detected_at=now,
        )
        self._detections[detection_id] = detection
        _emit(self._events, "gaming_detected", {
            "detection_id": detection_id, "actor_ref": actor_ref,
            "risk": risk.value,
        }, detection_id, now)
        return detection

    # ------------------------------------------------------------------
    # Policy effects
    # ------------------------------------------------------------------

    def record_policy_effect(
        self,
        effect_id: str,
        tenant_id: str,
        policy_ref: str,
        *,
        kind: PolicyEffectKind = PolicyEffectKind.NEUTRAL,
        description: str = "observed effect",
    ) -> PolicyEffect:
        """Record an observed policy effect."""
        if effect_id in self._effects:
            raise RuntimeCoreInvariantError(f"Duplicate effect_id: {effect_id}")
        now = self._now()
        effect = PolicyEffect(
            effect_id=effect_id,
            tenant_id=tenant_id,
            policy_ref=policy_ref,
            kind=kind,
            description=description,
            measured_at=now,
        )
        self._effects[effect_id] = effect
        _emit(self._events, "policy_effect_recorded", {
            "effect_id": effect_id, "kind": kind.value,
        }, effect_id, now)
        return effect

    # ------------------------------------------------------------------
    # Contract bindings
    # ------------------------------------------------------------------

    def bind_incentive_to_contract(
        self,
        binding_id: str,
        tenant_id: str,
        contract_ref: str,
        incentive_ref: str,
    ) -> ContractIncentiveBinding:
        """Bind an incentive to a contract."""
        if binding_id in self._bindings:
            raise RuntimeCoreInvariantError(f"Duplicate binding_id: {binding_id}")
        if incentive_ref not in self._incentives:
            raise RuntimeCoreInvariantError(f"Unknown incentive_ref: {incentive_ref}")
        now = self._now()
        binding = ContractIncentiveBinding(
            binding_id=binding_id,
            tenant_id=tenant_id,
            contract_ref=contract_ref,
            incentive_ref=incentive_ref,
            created_at=now,
        )
        self._bindings[binding_id] = binding
        _emit(self._events, "incentive_bound_to_contract", {
            "binding_id": binding_id, "contract_ref": contract_ref,
            "incentive_ref": incentive_ref,
        }, binding_id, now)
        return binding

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def incentive_assessment(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> IncentiveAssessment:
        """Produce an assessment of incentive activity.

        alignment_rate = aligned / (aligned + misaligned + gaming)
        """
        now = self._now()
        total_incentives = sum(1 for i in self._incentives.values() if i.tenant_id == tenant_id)
        total_observations = sum(1 for o in self._observations.values() if o.tenant_id == tenant_id)
        total_gaming = sum(1 for d in self._detections.values() if d.tenant_id == tenant_id)

        aligned = sum(
            1 for o in self._observations.values()
            if o.tenant_id == tenant_id and o.disposition == BehaviorDisposition.ALIGNED
        )
        misaligned = sum(
            1 for o in self._observations.values()
            if o.tenant_id == tenant_id and o.disposition == BehaviorDisposition.MISALIGNED
        )
        gaming = sum(
            1 for o in self._observations.values()
            if o.tenant_id == tenant_id and o.disposition == BehaviorDisposition.GAMING
        )
        denom = aligned + misaligned + gaming
        alignment_rate = aligned / denom if denom > 0 else 0.0

        assessment = IncentiveAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_incentives=total_incentives,
            total_observations=total_observations,
            total_gaming_detections=total_gaming,
            alignment_rate=alignment_rate,
            assessed_at=now,
        )
        _emit(self._events, "incentive_assessment", {
            "assessment_id": assessment_id, "alignment_rate": alignment_rate,
        }, assessment_id, now)
        return assessment

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def incentive_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> IncentiveSnapshot:
        """Capture a point-in-time incentive snapshot."""
        now = self._now()
        snap = IncentiveSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_incentives=self.incentive_count,
            total_observations=self.observation_count,
            total_detections=self.detection_count,
            total_effects=self.effect_count,
            total_bindings=self.binding_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        _emit(self._events, "incentive_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id, now)
        return snap

    # ------------------------------------------------------------------
    # Closure Report
    # ------------------------------------------------------------------

    def incentive_closure_report(
        self,
        report_id: str,
        tenant_id: str,
    ) -> IncentiveClosureReport:
        """Produce a closure report for incentive activity."""
        now = self._now()
        report = IncentiveClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_incentives=self.incentive_count,
            total_observations=self.observation_count,
            total_detections=self.detection_count,
            total_violations=self.violation_count,
            created_at=now,
        )
        _emit(self._events, "incentive_closure_report", {
            "report_id": report_id,
        }, report_id, now)
        return report

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_incentive_violations(self, tenant_id: str = "") -> tuple:
        """Detect incentive violations (idempotent).

        Checks:
        1. gaming_unaddressed: gaming detection with no decision recorded
        2. perverse_effect_unresolved: perverse policy effect with no decision
        3. expired_incentive_still_bound: expired/retired incentive with active bindings
        """
        now = self._now()
        new_violations: list[IncentiveViolation] = []

        # 1) gaming_unaddressed
        for det in self._detections.values():
            if tenant_id and det.tenant_id != tenant_id:
                continue
            has_decision = any(
                d.incentive_ref == det.incentive_ref
                for d in self._decisions.values()
            )
            if not has_decision:
                vid = stable_identifier("viol-incn", {
                    "detection": det.detection_id, "op": "gaming_unaddressed",
                })
                if vid not in self._violations:
                    v = IncentiveViolation(
                        violation_id=vid,
                        tenant_id=det.tenant_id,
                        operation="gaming_unaddressed",
                        reason=f"Gaming detection {det.detection_id} has no decision recorded",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 2) perverse_effect_unresolved
        for eff in self._effects.values():
            if tenant_id and eff.tenant_id != tenant_id:
                continue
            if eff.kind == PolicyEffectKind.PERVERSE:
                vid = stable_identifier("viol-incn", {
                    "effect": eff.effect_id, "op": "perverse_effect_unresolved",
                })
                if vid not in self._violations:
                    v = IncentiveViolation(
                        violation_id=vid,
                        tenant_id=eff.tenant_id,
                        operation="perverse_effect_unresolved",
                        reason=f"Policy effect {eff.effect_id} is PERVERSE and unresolved",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3) expired_incentive_still_bound
        for binding in self._bindings.values():
            if tenant_id and binding.tenant_id != tenant_id:
                continue
            inc = self._incentives.get(binding.incentive_ref)
            if inc and inc.status in _INCENTIVE_TERMINAL:
                vid = stable_identifier("viol-incn", {
                    "binding": binding.binding_id, "op": "expired_incentive_still_bound",
                })
                if vid not in self._violations:
                    v = IncentiveViolation(
                        violation_id=vid,
                        tenant_id=binding.tenant_id,
                        operation="expired_incentive_still_bound",
                        reason=f"Binding {binding.binding_id} references {inc.status.value} incentive {inc.incentive_id}",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "incentive_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan", now)
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "bindings": self._bindings,
            "decisions": self._decisions,
            "detections": self._detections,
            "effects": self._effects,
            "incentives": self._incentives,
            "observations": self._observations,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result

    def state_hash(self) -> str:
        """Compute a deterministic hash of engine state."""
        parts = [
            f"bindings={self.binding_count}",
            f"decisions={self.decision_count}",
            f"detections={self.detection_count}",
            f"effects={self.effect_count}",
            f"incentives={self.incentive_count}",
            f"observations={self.observation_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
