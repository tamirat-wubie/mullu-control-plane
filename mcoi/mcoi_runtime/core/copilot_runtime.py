"""Purpose: copilot runtime engine.
Governance scope: managing conversational sessions, classifying intents,
    recording turns, building action plans, recording decisions, generating
    evidence-backed responses, detecting violations, and producing snapshots.
Dependencies: copilot_runtime contracts, event_spine, core invariants.
Invariants:
  - LOW risk auto-allows; MEDIUM defers; HIGH/CRITICAL escalates.
  - Cross-tenant action plans are DENIED with a violation.
  - Terminal sessions (COMPLETED/TERMINATED) cannot transition further.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.copilot_runtime import (
    ActionDisposition,
    ActionPlan,
    ConversationMode,
    ConversationRiskLevel,
    ConversationSession,
    ConversationTurn,
    ConversationViolation,
    CopilotAssessment,
    CopilotClosureReport,
    CopilotDecision,
    CopilotSnapshot,
    CopilotStatus,
    EvidenceBackedResponse,
    IntentKind,
    IntentRecord,
    ResponseMode,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


_SESSION_TERMINAL = frozenset({CopilotStatus.COMPLETED, CopilotStatus.TERMINATED})


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-cprt", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class CopilotRuntimeEngine:
    """Engine for governed conversational assistant / copilot runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._sessions: dict[str, ConversationSession] = {}
        self._intents: dict[str, IntentRecord] = {}
        self._turns: dict[str, ConversationTurn] = {}
        self._plans: dict[str, ActionPlan] = {}
        self._decisions: dict[str, CopilotDecision] = {}
        self._responses: dict[str, EvidenceBackedResponse] = {}
        self._violations: dict[str, ConversationViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    @property
    def intent_count(self) -> int:
        return len(self._intents)

    @property
    def plan_count(self) -> int:
        return len(self._plans)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def response_count(self) -> int:
        return len(self._responses)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def start_session(
        self,
        session_id: str,
        tenant_id: str,
        identity_ref: str,
        mode: ConversationMode = ConversationMode.INTERACTIVE,
    ) -> ConversationSession:
        """Start a new copilot session."""
        if session_id in self._sessions:
            raise RuntimeCoreInvariantError("Duplicate session_id")
        now = self._now()
        session = ConversationSession(
            session_id=session_id,
            tenant_id=tenant_id,
            identity_ref=identity_ref,
            mode=mode,
            status=CopilotStatus.ACTIVE,
            turn_count=0,
            created_at=now,
        )
        self._sessions[session_id] = session
        _emit(self._events, "session_started", {
            "session_id": session_id, "mode": mode.value,
        }, session_id, self._now())
        return session

    def get_session(self, session_id: str) -> ConversationSession:
        s = self._sessions.get(session_id)
        if s is None:
            raise RuntimeCoreInvariantError("Unknown session_id")
        return s

    def sessions_for_tenant(self, tenant_id: str) -> tuple[ConversationSession, ...]:
        return tuple(s for s in self._sessions.values() if s.tenant_id == tenant_id)

    def _replace_session(self, session_id: str, **kwargs: Any) -> ConversationSession:
        """Replace a session with updated fields."""
        old = self.get_session(session_id)
        fields = {
            "session_id": old.session_id,
            "tenant_id": old.tenant_id,
            "identity_ref": old.identity_ref,
            "mode": old.mode,
            "status": old.status,
            "turn_count": old.turn_count,
            "created_at": old.created_at,
            "metadata": old.metadata,
        }
        fields.update(kwargs)
        updated = ConversationSession(**fields)
        self._sessions[session_id] = updated
        return updated

    def pause_session(self, session_id: str) -> ConversationSession:
        """Pause an ACTIVE session."""
        old = self.get_session(session_id)
        if old.status in _SESSION_TERMINAL:
            raise RuntimeCoreInvariantError("Session is in terminal state")
        if old.status != CopilotStatus.ACTIVE:
            raise RuntimeCoreInvariantError("Cannot pause session in current state")
        updated = self._replace_session(session_id, status=CopilotStatus.PAUSED)
        _emit(self._events, "session_paused", {
            "session_id": session_id,
        }, session_id, self._now())
        return updated

    def resume_session(self, session_id: str) -> ConversationSession:
        """Resume a PAUSED session."""
        old = self.get_session(session_id)
        if old.status in _SESSION_TERMINAL:
            raise RuntimeCoreInvariantError("Session is in terminal state")
        if old.status != CopilotStatus.PAUSED:
            raise RuntimeCoreInvariantError("Cannot resume session in current state")
        updated = self._replace_session(session_id, status=CopilotStatus.ACTIVE)
        _emit(self._events, "session_resumed", {
            "session_id": session_id,
        }, session_id, self._now())
        return updated

    def complete_session(self, session_id: str) -> ConversationSession:
        """Complete a non-terminal session."""
        old = self.get_session(session_id)
        if old.status in _SESSION_TERMINAL:
            raise RuntimeCoreInvariantError("Session is in terminal state")
        updated = self._replace_session(session_id, status=CopilotStatus.COMPLETED)
        _emit(self._events, "session_completed", {
            "session_id": session_id,
        }, session_id, self._now())
        return updated

    def terminate_session(self, session_id: str) -> ConversationSession:
        """Terminate a non-terminal session."""
        old = self.get_session(session_id)
        if old.status in _SESSION_TERMINAL:
            raise RuntimeCoreInvariantError("Session is in terminal state")
        updated = self._replace_session(session_id, status=CopilotStatus.TERMINATED)
        _emit(self._events, "session_terminated", {
            "session_id": session_id,
        }, session_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Turns
    # ------------------------------------------------------------------

    def record_turn(
        self,
        turn_id: str,
        tenant_id: str,
        session_ref: str,
        intent_ref: str,
        user_input: str,
        assistant_output: str,
        response_mode: ResponseMode = ResponseMode.DIRECT,
    ) -> ConversationTurn:
        """Record a conversation turn. Session must be ACTIVE."""
        if turn_id in self._turns:
            raise RuntimeCoreInvariantError("Duplicate turn_id")
        session = self.get_session(session_ref)
        if session.status != CopilotStatus.ACTIVE:
            raise RuntimeCoreInvariantError("Session is not ACTIVE")
        now = self._now()
        turn = ConversationTurn(
            turn_id=turn_id,
            tenant_id=tenant_id,
            session_ref=session_ref,
            intent_ref=intent_ref,
            user_input=user_input,
            assistant_output=assistant_output,
            response_mode=response_mode,
            created_at=now,
        )
        self._turns[turn_id] = turn
        # Increment turn_count
        self._replace_session(session_ref, turn_count=session.turn_count + 1)
        _emit(self._events, "turn_recorded", {
            "turn_id": turn_id, "session_ref": session_ref,
        }, turn_id, self._now())
        return turn

    # ------------------------------------------------------------------
    # Intents
    # ------------------------------------------------------------------

    def classify_intent(
        self,
        intent_id: str,
        tenant_id: str,
        session_ref: str,
        kind: IntentKind,
        raw_input: str,
    ) -> IntentRecord:
        """Classify user intent. Session must exist."""
        if intent_id in self._intents:
            raise RuntimeCoreInvariantError("Duplicate intent_id")
        self.get_session(session_ref)  # validates existence
        now = self._now()
        intent = IntentRecord(
            intent_id=intent_id,
            tenant_id=tenant_id,
            session_ref=session_ref,
            kind=kind,
            raw_input=raw_input,
            classified_at=now,
        )
        self._intents[intent_id] = intent
        _emit(self._events, "intent_classified", {
            "intent_id": intent_id, "kind": kind.value,
        }, intent_id, self._now())
        return intent

    # ------------------------------------------------------------------
    # Action Plans
    # ------------------------------------------------------------------

    def build_action_plan(
        self,
        plan_id: str,
        tenant_id: str,
        session_ref: str,
        intent_ref: str,
        target_runtime: str,
        operation: str,
        risk_level: ConversationRiskLevel = ConversationRiskLevel.LOW,
    ) -> ActionPlan:
        """Build an action plan with risk-based disposition.

        LOW -> ALLOWED
        MEDIUM -> DEFERRED (needs review)
        HIGH/CRITICAL -> ESCALATED
        Cross-tenant -> DENIED + violation
        """
        if plan_id in self._plans:
            raise RuntimeCoreInvariantError("Duplicate plan_id")
        session = self.get_session(session_ref)
        now = self._now()

        # Cross-tenant check
        if session.tenant_id != tenant_id:
            disposition = ActionDisposition.DENIED
            # Record a violation
            vid = stable_identifier("viol-cprt", {
                "plan": plan_id, "op": "cross_tenant_action",
            })
            if vid not in self._violations:
                v = ConversationViolation(
                    violation_id=vid,
                    tenant_id=tenant_id,
                    operation="cross_tenant_action",
                    reason="cross-tenant action attempt",
                    detected_at=now,
                )
                self._violations[vid] = v
        elif risk_level == ConversationRiskLevel.LOW:
            disposition = ActionDisposition.ALLOWED
        elif risk_level == ConversationRiskLevel.MEDIUM:
            disposition = ActionDisposition.DEFERRED
        else:
            # HIGH or CRITICAL
            disposition = ActionDisposition.ESCALATED

        plan = ActionPlan(
            plan_id=plan_id,
            tenant_id=tenant_id,
            session_ref=session_ref,
            intent_ref=intent_ref,
            target_runtime=target_runtime,
            operation=operation,
            risk_level=risk_level,
            disposition=disposition,
            created_at=now,
        )
        self._plans[plan_id] = plan
        _emit(self._events, "action_plan_built", {
            "plan_id": plan_id, "risk_level": risk_level.value,
            "disposition": disposition.value,
        }, plan_id, self._now())
        return plan

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def record_copilot_decision(
        self,
        decision_id: str,
        tenant_id: str,
        session_ref: str,
        plan_ref: str,
        disposition: ActionDisposition,
        reason: str,
        evidence_refs: str = "",
    ) -> CopilotDecision:
        """Record a copilot decision on an action plan."""
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError("Duplicate decision_id")
        now = self._now()
        dec = CopilotDecision(
            decision_id=decision_id,
            tenant_id=tenant_id,
            session_ref=session_ref,
            plan_ref=plan_ref,
            disposition=disposition,
            reason=reason,
            evidence_refs=evidence_refs,
            decided_at=now,
        )
        self._decisions[decision_id] = dec
        _emit(self._events, "copilot_decision_recorded", {
            "decision_id": decision_id, "disposition": disposition.value,
        }, decision_id, self._now())
        return dec

    # ------------------------------------------------------------------
    # Evidence-backed responses
    # ------------------------------------------------------------------

    def generate_response(
        self,
        response_id: str,
        tenant_id: str,
        session_ref: str,
        turn_ref: str,
        content: str,
        evidence_count: int = 0,
        confidence: float = 1.0,
    ) -> EvidenceBackedResponse:
        """Generate an evidence-backed response."""
        if response_id in self._responses:
            raise RuntimeCoreInvariantError("Duplicate response_id")
        now = self._now()
        resp = EvidenceBackedResponse(
            response_id=response_id,
            tenant_id=tenant_id,
            session_ref=session_ref,
            turn_ref=turn_ref,
            content=content,
            evidence_count=evidence_count,
            confidence=confidence,
            created_at=now,
        )
        self._responses[response_id] = resp
        _emit(self._events, "response_generated", {
            "response_id": response_id, "evidence_count": evidence_count,
        }, response_id, self._now())
        return resp

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def copilot_assessment(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> CopilotAssessment:
        """Produce a copilot assessment for a tenant."""
        now = self._now()
        tenant_sessions = [s for s in self._sessions.values() if s.tenant_id == tenant_id]
        tenant_plans = [p for p in self._plans.values() if p.tenant_id == tenant_id]
        allowed = sum(1 for p in tenant_plans if p.disposition == ActionDisposition.ALLOWED)
        denied = sum(1 for p in tenant_plans if p.disposition == ActionDisposition.DENIED)
        total = allowed + denied
        rate = allowed / total if total > 0 else 1.0

        asm = CopilotAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_sessions=len(tenant_sessions),
            total_actions_allowed=allowed,
            total_actions_denied=denied,
            success_rate=rate,
            assessed_at=now,
        )
        _emit(self._events, "copilot_assessed", {
            "assessment_id": assessment_id, "success_rate": rate,
        }, assessment_id, self._now())
        return asm

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def copilot_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> CopilotSnapshot:
        """Produce a point-in-time snapshot for a tenant."""
        now = self._now()
        snap = CopilotSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_sessions=sum(1 for s in self._sessions.values() if s.tenant_id == tenant_id),
            total_turns=sum(1 for t in self._turns.values() if t.tenant_id == tenant_id),
            total_intents=sum(1 for i in self._intents.values() if i.tenant_id == tenant_id),
            total_plans=sum(1 for p in self._plans.values() if p.tenant_id == tenant_id),
            total_decisions=sum(1 for d in self._decisions.values() if d.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            captured_at=now,
        )
        return snap

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_copilot_violations(self, tenant_id: str) -> tuple[ConversationViolation, ...]:
        """Detect copilot violations for a tenant. Idempotent."""
        now = self._now()
        new_violations: list[ConversationViolation] = []

        tenant_sessions = [s for s in self._sessions.values() if s.tenant_id == tenant_id]
        tenant_plans = [p for p in self._plans.values() if p.tenant_id == tenant_id]

        # 1) session_no_turns: ACTIVE session with turn_count=0
        for sess in tenant_sessions:
            if sess.status == CopilotStatus.ACTIVE and sess.turn_count == 0:
                vid = stable_identifier("viol-cprt", {
                    "session": sess.session_id, "op": "session_no_turns",
                })
                if vid not in self._violations:
                    v = ConversationViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="session_no_turns",
                        reason="session active with zero turns",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 2) plan_no_decision: plan exists with no corresponding decision
        for plan in tenant_plans:
            has_decision = any(
                d.plan_ref == plan.plan_id
                for d in self._decisions.values()
            )
            if not has_decision:
                vid = stable_identifier("viol-cprt", {
                    "plan": plan.plan_id, "op": "plan_no_decision",
                })
                if vid not in self._violations:
                    v = ConversationViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="plan_no_decision",
                        reason="plan has no corresponding decision",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3) high_risk_auto_allowed: plan with HIGH/CRITICAL risk and ALLOWED disposition
        for plan in tenant_plans:
            if (
                plan.risk_level in (ConversationRiskLevel.HIGH, ConversationRiskLevel.CRITICAL)
                and plan.disposition == ActionDisposition.ALLOWED
            ):
                vid = stable_identifier("viol-cprt", {
                    "plan": plan.plan_id, "op": "high_risk_auto_allowed",
                })
                if vid not in self._violations:
                    v = ConversationViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="high_risk_auto_allowed",
                        reason="high risk plan has allowed disposition",
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
            "sessions": self._sessions,
            "intents": self._intents,
            "turns": self._turns,
            "plans": self._plans,
            "decisions": self._decisions,
            "responses": self._responses,
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
        """Compute a deterministic hash of engine state (sorted keys, no timestamps)."""
        parts = [
            f"decisions={self.decision_count}",
            f"intents={self.intent_count}",
            f"plans={self.plan_count}",
            f"responses={self.response_count}",
            f"sessions={self.session_count}",
            f"turns={self.turn_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
