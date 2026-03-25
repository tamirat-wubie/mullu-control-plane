"""Purpose: persona / role / behavioral style runtime engine.
Governance scope: managing agent persona profiles, role behavior policies,
    style directives, escalation directives, session bindings, decisions,
    violations, assessments, snapshots, and closure reports.
Dependencies: persona_runtime contracts, event_spine, core invariants.
Invariants:
  - RETIRED personas cannot be reactivated.
  - Cross-tenant bindings are DENIED with a violation.
  - Authority-exceeded decisions produce violations.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.persona_runtime import (
    AuthorityMode,
    EscalationDirective,
    EscalationStyle,
    InteractionStyle,
    PersonaAssessment,
    PersonaClosureReport,
    PersonaDecision,
    PersonaKind,
    PersonaProfile,
    PersonaRiskLevel,
    PersonaSessionBinding,
    PersonaSnapshot,
    PersonaStatus,
    PersonaViolation,
    RoleBehaviorPolicy,
    StyleDirective,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


_PERSONA_TERMINAL = frozenset({PersonaStatus.RETIRED})


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-psrt", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class PersonaRuntimeEngine:
    """Engine for governed agent persona / role / behavioral style runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._personas: dict[str, PersonaProfile] = {}
        self._policies: dict[str, RoleBehaviorPolicy] = {}
        self._style_directives: dict[str, StyleDirective] = {}
        self._escalation_directives: dict[str, EscalationDirective] = {}
        self._bindings: dict[str, PersonaSessionBinding] = {}
        self._decisions: dict[str, PersonaDecision] = {}
        self._violations: dict[str, PersonaViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def persona_count(self) -> int:
        return len(self._personas)

    @property
    def policy_count(self) -> int:
        return len(self._policies)

    @property
    def style_directive_count(self) -> int:
        return len(self._style_directives)

    @property
    def escalation_directive_count(self) -> int:
        return len(self._escalation_directives)

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
    # Personas
    # ------------------------------------------------------------------

    def register_persona(
        self,
        persona_id: str,
        tenant_id: str,
        display_name: str,
        kind: PersonaKind,
        interaction_style: InteractionStyle = InteractionStyle.CONCISE,
        authority_mode: AuthorityMode = AuthorityMode.GUIDED,
    ) -> PersonaProfile:
        """Register a new persona. Duplicate persona_id raises."""
        if persona_id in self._personas:
            raise RuntimeCoreInvariantError(f"Duplicate persona_id: {persona_id}")
        now = self._now()
        persona = PersonaProfile(
            persona_id=persona_id,
            tenant_id=tenant_id,
            display_name=display_name,
            kind=kind,
            status=PersonaStatus.ACTIVE,
            interaction_style=interaction_style,
            authority_mode=authority_mode,
            created_at=now,
        )
        self._personas[persona_id] = persona
        _emit(self._events, "persona_registered", {
            "persona_id": persona_id, "kind": kind.value,
        }, persona_id, self._now())
        return persona

    def get_persona(self, persona_id: str) -> PersonaProfile:
        p = self._personas.get(persona_id)
        if p is None:
            raise RuntimeCoreInvariantError(f"Unknown persona_id: {persona_id}")
        return p

    def personas_for_tenant(self, tenant_id: str) -> tuple[PersonaProfile, ...]:
        return tuple(p for p in self._personas.values() if p.tenant_id == tenant_id)

    def _replace_persona(self, persona_id: str, **kwargs: Any) -> PersonaProfile:
        """Replace a persona with updated fields."""
        old = self.get_persona(persona_id)
        fields = {
            "persona_id": old.persona_id,
            "tenant_id": old.tenant_id,
            "display_name": old.display_name,
            "kind": old.kind,
            "status": old.status,
            "interaction_style": old.interaction_style,
            "authority_mode": old.authority_mode,
            "created_at": old.created_at,
            "metadata": old.metadata,
        }
        fields.update(kwargs)
        updated = PersonaProfile(**fields)
        self._personas[persona_id] = updated
        return updated

    def suspend_persona(self, persona_id: str) -> PersonaProfile:
        """Suspend an ACTIVE persona."""
        old = self.get_persona(persona_id)
        if old.status in _PERSONA_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Persona {persona_id} is in terminal state {old.status.value}"
            )
        if old.status != PersonaStatus.ACTIVE:
            raise RuntimeCoreInvariantError(
                f"Cannot suspend persona in {old.status.value} state"
            )
        updated = self._replace_persona(persona_id, status=PersonaStatus.SUSPENDED)
        _emit(self._events, "persona_suspended", {
            "persona_id": persona_id,
        }, persona_id, self._now())
        return updated

    def retire_persona(self, persona_id: str) -> PersonaProfile:
        """Retire a persona. Terminal state."""
        old = self.get_persona(persona_id)
        if old.status in _PERSONA_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Persona {persona_id} is in terminal state {old.status.value}"
            )
        updated = self._replace_persona(persona_id, status=PersonaStatus.RETIRED)
        _emit(self._events, "persona_retired", {
            "persona_id": persona_id,
        }, persona_id, self._now())
        return updated

    def activate_persona(self, persona_id: str) -> PersonaProfile:
        """Activate a SUSPENDED persona."""
        old = self.get_persona(persona_id)
        if old.status in _PERSONA_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Persona {persona_id} is in terminal state {old.status.value}"
            )
        if old.status != PersonaStatus.SUSPENDED:
            raise RuntimeCoreInvariantError(
                f"Cannot activate persona in {old.status.value} state"
            )
        updated = self._replace_persona(persona_id, status=PersonaStatus.ACTIVE)
        _emit(self._events, "persona_activated", {
            "persona_id": persona_id,
        }, persona_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Role Behavior Policies
    # ------------------------------------------------------------------

    def register_role_policy(
        self,
        policy_id: str,
        tenant_id: str,
        persona_ref: str,
        escalation_style: EscalationStyle = EscalationStyle.THRESHOLD,
        risk_level: PersonaRiskLevel = PersonaRiskLevel.LOW,
        max_autonomy_depth: int = 3,
    ) -> RoleBehaviorPolicy:
        """Register a role behavior policy. Validates persona exists."""
        if policy_id in self._policies:
            raise RuntimeCoreInvariantError(f"Duplicate policy_id: {policy_id}")
        self.get_persona(persona_ref)  # validates existence
        now = self._now()
        policy = RoleBehaviorPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            persona_ref=persona_ref,
            escalation_style=escalation_style,
            risk_level=risk_level,
            max_autonomy_depth=max_autonomy_depth,
            created_at=now,
        )
        self._policies[policy_id] = policy
        _emit(self._events, "role_policy_registered", {
            "policy_id": policy_id, "persona_ref": persona_ref,
        }, policy_id, self._now())
        return policy

    def get_policy(self, policy_id: str) -> RoleBehaviorPolicy:
        p = self._policies.get(policy_id)
        if p is None:
            raise RuntimeCoreInvariantError(f"Unknown policy_id: {policy_id}")
        return p

    def policies_for_persona(self, persona_ref: str) -> tuple[RoleBehaviorPolicy, ...]:
        return tuple(p for p in self._policies.values() if p.persona_ref == persona_ref)

    # ------------------------------------------------------------------
    # Style Directives
    # ------------------------------------------------------------------

    def add_style_directive(
        self,
        directive_id: str,
        tenant_id: str,
        persona_ref: str,
        scope: str,
        instruction: str,
        priority: int = 0,
    ) -> StyleDirective:
        """Add a style directive for a persona."""
        if directive_id in self._style_directives:
            raise RuntimeCoreInvariantError(f"Duplicate directive_id: {directive_id}")
        self.get_persona(persona_ref)  # validates existence
        now = self._now()
        directive = StyleDirective(
            directive_id=directive_id,
            tenant_id=tenant_id,
            persona_ref=persona_ref,
            scope=scope,
            instruction=instruction,
            priority=priority,
            created_at=now,
        )
        self._style_directives[directive_id] = directive
        _emit(self._events, "style_directive_added", {
            "directive_id": directive_id, "persona_ref": persona_ref,
        }, directive_id, self._now())
        return directive

    # ------------------------------------------------------------------
    # Escalation Directives
    # ------------------------------------------------------------------

    def add_escalation_directive(
        self,
        directive_id: str,
        tenant_id: str,
        persona_ref: str,
        trigger_condition: str,
        target_role: str,
    ) -> EscalationDirective:
        """Add an escalation directive for a persona."""
        if directive_id in self._escalation_directives:
            raise RuntimeCoreInvariantError(f"Duplicate directive_id: {directive_id}")
        self.get_persona(persona_ref)  # validates existence
        now = self._now()
        directive = EscalationDirective(
            directive_id=directive_id,
            tenant_id=tenant_id,
            persona_ref=persona_ref,
            trigger_condition=trigger_condition,
            target_role=target_role,
            created_at=now,
        )
        self._escalation_directives[directive_id] = directive
        _emit(self._events, "escalation_directive_added", {
            "directive_id": directive_id, "persona_ref": persona_ref,
        }, directive_id, self._now())
        return directive

    # ------------------------------------------------------------------
    # Session Bindings
    # ------------------------------------------------------------------

    def bind_persona_to_session(
        self,
        binding_id: str,
        tenant_id: str,
        persona_ref: str,
        session_ref: str,
    ) -> PersonaSessionBinding:
        """Bind a persona to a session. Persona must be ACTIVE.
        Duplicate binding_id raises. Cross-tenant produces a violation."""
        if binding_id in self._bindings:
            raise RuntimeCoreInvariantError(f"Duplicate binding_id: {binding_id}")
        persona = self.get_persona(persona_ref)
        now = self._now()

        # Cross-tenant check
        if persona.tenant_id != tenant_id:
            vid = stable_identifier("viol-psrt", {
                "binding": binding_id, "op": "cross_tenant_binding",
            })
            if vid not in self._violations:
                v = PersonaViolation(
                    violation_id=vid,
                    tenant_id=tenant_id,
                    operation="cross_tenant_binding",
                    reason=f"Binding {binding_id} targets tenant {tenant_id} but persona {persona_ref} belongs to {persona.tenant_id}",
                    detected_at=now,
                )
                self._violations[vid] = v
            raise RuntimeCoreInvariantError(
                f"Cross-tenant binding: persona {persona_ref} belongs to {persona.tenant_id}, not {tenant_id}"
            )

        if persona.status != PersonaStatus.ACTIVE:
            raise RuntimeCoreInvariantError(
                f"Persona {persona_ref} is not ACTIVE (status: {persona.status.value})"
            )

        binding = PersonaSessionBinding(
            binding_id=binding_id,
            tenant_id=tenant_id,
            persona_ref=persona_ref,
            session_ref=session_ref,
            bound_at=now,
        )
        self._bindings[binding_id] = binding
        _emit(self._events, "persona_bound_to_session", {
            "binding_id": binding_id, "persona_ref": persona_ref, "session_ref": session_ref,
        }, binding_id, self._now())
        return binding

    # ------------------------------------------------------------------
    # Behavior Resolution
    # ------------------------------------------------------------------

    def resolve_behavior(self, tenant_id: str, session_ref: str) -> dict[str, Any]:
        """Resolve behavior for a session. Returns defaults if no binding."""
        # Find binding for this session+tenant
        binding = None
        for b in self._bindings.values():
            if b.tenant_id == tenant_id and b.session_ref == session_ref:
                binding = b
                break

        if binding is None:
            return {
                "persona_kind": PersonaKind.OPERATOR.value,
                "interaction_style": InteractionStyle.CONCISE.value,
                "authority_mode": AuthorityMode.GUIDED.value,
                "escalation_style": EscalationStyle.MANUAL.value,
                "risk_level": PersonaRiskLevel.LOW.value,
            }

        persona = self.get_persona(binding.persona_ref)

        # Find policy for persona
        policies = self.policies_for_persona(binding.persona_ref)
        if policies:
            policy = policies[0]
            escalation_style = policy.escalation_style.value
            risk_level = policy.risk_level.value
        else:
            escalation_style = EscalationStyle.MANUAL.value
            risk_level = PersonaRiskLevel.LOW.value

        return {
            "persona_kind": persona.kind.value,
            "interaction_style": persona.interaction_style.value,
            "authority_mode": persona.authority_mode.value,
            "escalation_style": escalation_style,
            "risk_level": risk_level,
        }

    def resolve_escalation_style(self, tenant_id: str, session_ref: str) -> EscalationStyle:
        """Resolve escalation style for a session. MANUAL if no binding/policy."""
        binding = None
        for b in self._bindings.values():
            if b.tenant_id == tenant_id and b.session_ref == session_ref:
                binding = b
                break

        if binding is None:
            return EscalationStyle.MANUAL

        policies = self.policies_for_persona(binding.persona_ref)
        if policies:
            return policies[0].escalation_style
        return EscalationStyle.MANUAL

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def record_persona_decision(
        self,
        decision_id: str,
        tenant_id: str,
        persona_ref: str,
        session_ref: str,
        action_taken: str,
        style_applied: InteractionStyle,
        authority_used: AuthorityMode,
    ) -> PersonaDecision:
        """Record a decision made under persona authority."""
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError(f"Duplicate decision_id: {decision_id}")
        now = self._now()
        dec = PersonaDecision(
            decision_id=decision_id,
            tenant_id=tenant_id,
            persona_ref=persona_ref,
            session_ref=session_ref,
            action_taken=action_taken,
            style_applied=style_applied,
            authority_used=authority_used,
            decided_at=now,
        )
        self._decisions[decision_id] = dec
        _emit(self._events, "persona_decision_recorded", {
            "decision_id": decision_id, "authority_used": authority_used.value,
        }, decision_id, self._now())
        return dec

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def persona_assessment(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> PersonaAssessment:
        """Produce a persona assessment for a tenant.
        compliance_rate = decisions_within_authority / total_decisions or 1.0"""
        now = self._now()
        tenant_personas = [p for p in self._personas.values() if p.tenant_id == tenant_id]
        tenant_bindings = [b for b in self._bindings.values() if b.tenant_id == tenant_id]
        tenant_decisions = [d for d in self._decisions.values() if d.tenant_id == tenant_id]

        # Compute compliance: decisions within authority
        within_authority = 0
        for dec in tenant_decisions:
            persona = self._personas.get(dec.persona_ref)
            if persona is None:
                continue
            policies = self.policies_for_persona(dec.persona_ref)
            if not policies:
                # No policy means no restriction -> within authority
                within_authority += 1
                continue
            policy = policies[0]
            # Authority exceeded if decision uses AUTONOMOUS but policy is RESTRICTED or READ_ONLY
            if dec.authority_used == AuthorityMode.AUTONOMOUS and persona.authority_mode in (
                AuthorityMode.RESTRICTED, AuthorityMode.READ_ONLY
            ):
                continue  # not within authority
            within_authority += 1

        total = len(tenant_decisions)
        rate = within_authority / total if total > 0 else 1.0

        asm = PersonaAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_personas=len(tenant_personas),
            total_bindings=len(tenant_bindings),
            total_decisions=total,
            compliance_rate=rate,
            assessed_at=now,
        )
        _emit(self._events, "persona_assessed", {
            "assessment_id": assessment_id, "compliance_rate": rate,
        }, assessment_id, self._now())
        return asm

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def persona_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> PersonaSnapshot:
        """Produce a point-in-time snapshot for a tenant."""
        now = self._now()
        snap = PersonaSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_personas=sum(1 for p in self._personas.values() if p.tenant_id == tenant_id),
            total_policies=sum(1 for p in self._policies.values() if p.tenant_id == tenant_id),
            total_bindings=sum(1 for b in self._bindings.values() if b.tenant_id == tenant_id),
            total_decisions=sum(1 for d in self._decisions.values() if d.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            captured_at=now,
        )
        return snap

    # ------------------------------------------------------------------
    # Violation Detection
    # ------------------------------------------------------------------

    def detect_persona_violations(self, tenant_id: str) -> tuple[PersonaViolation, ...]:
        """Detect persona violations for a tenant. Idempotent."""
        now = self._now()
        new_violations: list[PersonaViolation] = []

        tenant_personas = [p for p in self._personas.values() if p.tenant_id == tenant_id]
        tenant_bindings = [b for b in self._bindings.values() if b.tenant_id == tenant_id]
        tenant_decisions = [d for d in self._decisions.values() if d.tenant_id == tenant_id]

        # 1) persona_no_policy: ACTIVE persona with no RoleBehaviorPolicy
        for persona in tenant_personas:
            if persona.status == PersonaStatus.ACTIVE:
                has_policy = any(
                    p.persona_ref == persona.persona_id
                    for p in self._policies.values()
                )
                if not has_policy:
                    vid = stable_identifier("viol-psrt", {
                        "persona": persona.persona_id, "op": "persona_no_policy",
                    })
                    if vid not in self._violations:
                        v = PersonaViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="persona_no_policy",
                            reason=f"Persona {persona.persona_id} is ACTIVE with no role behavior policy",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # 2) binding_to_retired_persona: binding references a RETIRED persona
        for binding in tenant_bindings:
            persona = self._personas.get(binding.persona_ref)
            if persona is not None and persona.status == PersonaStatus.RETIRED:
                vid = stable_identifier("viol-psrt", {
                    "binding": binding.binding_id, "op": "binding_to_retired_persona",
                })
                if vid not in self._violations:
                    v = PersonaViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="binding_to_retired_persona",
                        reason=f"Binding {binding.binding_id} references retired persona {binding.persona_ref}",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3) authority_exceeded: decision with AUTONOMOUS authority but persona policy is RESTRICTED or READ_ONLY
        for dec in tenant_decisions:
            if dec.authority_used == AuthorityMode.AUTONOMOUS:
                persona = self._personas.get(dec.persona_ref)
                if persona is not None and persona.authority_mode in (
                    AuthorityMode.RESTRICTED, AuthorityMode.READ_ONLY
                ):
                    vid = stable_identifier("viol-psrt", {
                        "decision": dec.decision_id, "op": "authority_exceeded",
                    })
                    if vid not in self._violations:
                        v = PersonaViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="authority_exceeded",
                            reason=f"Decision {dec.decision_id} uses AUTONOMOUS authority but persona {dec.persona_ref} has {persona.authority_mode.value} mode",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "personas": self._personas,
            "policies": self._policies,
            "style_directives": self._style_directives,
            "escalation_directives": self._escalation_directives,
            "bindings": self._bindings,
            "decisions": self._decisions,
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
        """Compute a deterministic hash of engine state (sorted keys)."""
        parts = [
            f"bindings={self.binding_count}",
            f"decisions={self.decision_count}",
            f"escalation_directives={self.escalation_directive_count}",
            f"personas={self.persona_count}",
            f"policies={self.policy_count}",
            f"style_directives={self.style_directive_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
