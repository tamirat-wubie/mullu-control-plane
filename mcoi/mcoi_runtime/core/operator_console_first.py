"""Purpose: Operator Console First runtime admission and gateway dispatch.
Governance scope: episode creation, plan hashing, approval lease validation,
    side-effect and recovery gates, independent verification, and receipt emission.
Dependencies: operator-console contracts and runtime invariant helpers.
Invariants:
  - No effect-bearing action dispatches outside the console gateway.
  - Approval grants expire when plan, state, risk, scope, or time changes.
  - Tool success is never promoted to verified success without evidence.
  - Receipts are emitted for blocked, partial, failed, quarantined, and verified outcomes.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from hashlib import sha256
import json
from typing import Callable, Protocol

from mcoi_runtime.contracts.operator_console_first import (
    ApprovalLease,
    ApprovalMode,
    ConsoleEpisodeStatus,
    ConsoleEvent,
    ConsoleFinalStatus,
    ConsoleIntentClass,
    ConsolePlannedAction,
    DispatchDecision,
    EpisodeLimits,
    GatewayDispatchResult,
    OperatorConsoleEpisode,
    OperatorConsoleReceipt,
    RecoveryClass,
    SideEffectManifest,
    StateSnapshot,
    VerificationRecord,
)
from mcoi_runtime.core.invariants import (
    RuntimeCoreInvariantError,
    ensure_non_empty_text,
    stable_identifier,
)


class ConsoleExternalEffectGateway(Protocol):
    """Gateway protocol for the only legal effectful dispatch path."""

    def dispatch(
        self,
        episode: OperatorConsoleEpisode,
        action: ConsolePlannedAction,
    ) -> GatewayDispatchResult: ...


class ConsoleVerificationProvider(Protocol):
    """Independent verifier protocol for observed world-state evidence."""

    def verify(
        self,
        action: ConsolePlannedAction,
        dispatch_result: GatewayDispatchResult,
        verified_at: str,
    ) -> VerificationRecord: ...


StateHashProvider = Callable[[OperatorConsoleEpisode, ConsolePlannedAction], str]
AbortPredicate = Callable[[OperatorConsoleEpisode, ConsolePlannedAction], bool]


class OperatorConsoleFirstRuntime:
    """Minimal product runtime for Operator Console First episodes."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock

    def capture_episode(
        self,
        *,
        operator_id: str,
        raw_request: str,
        intent_class: ConsoleIntentClass,
        governed_goal: dict[str, object],
        scope: dict[str, object],
        snapshot: StateSnapshot | None = None,
        limits: EpisodeLimits | None = None,
    ) -> OperatorConsoleEpisode:
        """Capture operator intent and optional initial state snapshot."""
        now = self._clock()
        episode_id = stable_identifier(
            "ocf-episode",
            {
                "operator_id": operator_id,
                "raw_request": raw_request,
                "intent_class": intent_class.value,
                "captured_at": now,
            },
        )
        events = [
            ConsoleEvent(
                event_type="intent_captured",
                occurred_at=now,
                details={"raw_request": raw_request, "intent_class": intent_class.value},
            )
        ]
        status = ConsoleEpisodeStatus.BOUNDED
        if snapshot is not None:
            events.append(
                ConsoleEvent(
                    event_type="state_snapshotted",
                    occurred_at=now,
                    details={
                        "source": snapshot.source,
                        "state_hash": snapshot.state_hash,
                    },
                )
            )
            status = ConsoleEpisodeStatus.SNAPSHOTTED
        return OperatorConsoleEpisode(
            episode_id=episode_id,
            operator_id=operator_id,
            raw_request=raw_request,
            intent_class=intent_class,
            governed_goal=governed_goal,
            scope=scope,
            status=status,
            snapshot=snapshot,
            limits=limits or EpisodeLimits(),
            events=tuple(events),
        )

    def plan_episode(
        self,
        episode: OperatorConsoleEpisode,
        actions: tuple[ConsolePlannedAction, ...],
    ) -> OperatorConsoleEpisode:
        """Bind a non-empty proposed plan to the episode."""
        if not actions:
            raise RuntimeCoreInvariantError("operator console plan must contain at least one action")
        now = self._clock()
        plan_hash = compute_plan_hash(actions)
        approval_needed = any(
            approval_mode_for_action(action) in {ApprovalMode.EXPLICIT, ApprovalMode.STRONG}
            for action in actions
        )
        event = ConsoleEvent(
            event_type="plan_built",
            occurred_at=now,
            details={
                "action_count": len(actions),
                "plan_hash": plan_hash,
                "approval_needed": approval_needed,
            },
        )
        return replace(
            episode,
            plan=actions,
            status=(
                ConsoleEpisodeStatus.WAITING_APPROVAL
                if approval_needed
                else ConsoleEpisodeStatus.PLANNED
            ),
            events=episode.events + (event,),
        )

    def issue_approval(
        self,
        episode: OperatorConsoleEpisode,
        *,
        operator_id: str,
        risk_ceiling: int | None = None,
        expires_at: str | None = None,
        allowed_actions: tuple[str, ...] | None = None,
    ) -> OperatorConsoleEpisode:
        """Issue an approval lease bound to the current plan and snapshot."""
        if episode.snapshot is None:
            raise RuntimeCoreInvariantError("approval lease requires a state snapshot")
        if not episode.plan:
            raise RuntimeCoreInvariantError("approval lease requires a planned episode")
        now = self._clock()
        lease = ApprovalLease(
            operator_id=operator_id,
            plan_hash=compute_plan_hash(episode.plan),
            target_state_hash=episode.snapshot.state_hash,
            risk_ceiling=(
                risk_ceiling
                if risk_ceiling is not None
                else max(action.risk_score for action in episode.plan)
            ),
            scope=episode.scope,
            issued_at=now,
            expires_at=expires_at or episode.snapshot.expires_at,
            allowed_actions=allowed_actions or tuple(action.action_id for action in episode.plan),
        )
        event = ConsoleEvent(
            event_type="approval_lease_issued",
            occurred_at=now,
            details={
                "operator_id": operator_id,
                "plan_hash": lease.plan_hash,
                "target_state_hash": lease.target_state_hash,
                "risk_ceiling": lease.risk_ceiling,
            },
        )
        return replace(
            episode,
            approval_lease=lease,
            status=ConsoleEpisodeStatus.APPROVED,
            events=episode.events + (event,),
        )

    def can_dispatch(
        self,
        episode: OperatorConsoleEpisode,
        action: ConsolePlannedAction,
        *,
        current_state_hash: str | None = None,
    ) -> DispatchDecision:
        """Evaluate the full console gateway admission predicate."""
        now = self._clock()
        approval_mode = approval_mode_for_action(action)
        if episode.snapshot is None:
            return _decision(False, "missing_snapshot", approval_mode, now)
        if _is_expired(episode.snapshot.expires_at, now):
            return _decision(False, "stale_snapshot", approval_mode, now)
        if action.action_id not in {planned.action_id for planned in episode.plan}:
            return _decision(False, "action_not_in_plan", approval_mode, now)
        observed_state_hash = current_state_hash or episode.snapshot.state_hash
        if episode.limits.max_cost and action.estimated_cost > episode.limits.max_cost:
            return _decision(False, "cost_limit_exceeded", approval_mode, now)
        if not action.side_effects_declared:
            return _decision(False, "undeclared_side_effects", approval_mode, now)
        if action.hostile_input_boundary.blocks_dispatch:
            return _decision(False, "hostile_input_authority_violation", approval_mode, now)
        if action.side_effects.effect_bearing and not action.recovery_declared:
            return _decision(False, "missing_recovery_plan", approval_mode, now)
        if observed_state_hash != episode.snapshot.state_hash:
            if episode.approval_lease is not None:
                return _decision(False, "approval_state_mismatch", approval_mode, now)
            return _decision(False, "stale_snapshot", approval_mode, now)
        if approval_mode in {ApprovalMode.EXPLICIT, ApprovalMode.STRONG}:
            lease = episode.approval_lease
            if lease is None:
                return _decision(False, "missing_approval_lease", approval_mode, now)
            if _is_expired(lease.expires_at, now):
                return _decision(False, "approval_expired", approval_mode, now)
            if lease.plan_hash != compute_plan_hash(episode.plan):
                return _decision(False, "approval_plan_mismatch", approval_mode, now)
            if lease.target_state_hash != observed_state_hash:
                return _decision(False, "approval_state_mismatch", approval_mode, now)
            if action.risk_score > lease.risk_ceiling:
                return _decision(False, "risk_exceeds_approval", approval_mode, now)
            if action.action_id not in lease.allowed_actions:
                return _decision(False, "action_not_approved", approval_mode, now)
        return _decision(True, "dispatch_allowed", approval_mode, now)

    def execute_episode(
        self,
        episode: OperatorConsoleEpisode,
        *,
        gateway: ConsoleExternalEffectGateway,
        verifier: ConsoleVerificationProvider | None = None,
        state_hash_provider: StateHashProvider | None = None,
        abort_requested: AbortPredicate | None = None,
    ) -> tuple[OperatorConsoleEpisode, OperatorConsoleReceipt]:
        """Execute actions only through the gateway and emit a terminal receipt."""
        if not episode.plan:
            blocked = replace(
                episode,
                status=ConsoleEpisodeStatus.BLOCKED,
                events=episode.events
                + (
                    ConsoleEvent(
                        event_type="episode_blocked",
                        occurred_at=self._clock(),
                        details={"reason": "missing_plan"},
                    ),
                ),
            )
            return blocked, self._build_receipt(
                episode=blocked,
                final_status=ConsoleFinalStatus.BLOCKED,
                attempted=(),
                blocked=("missing_plan",),
                verifications=(),
                evidence_refs=(),
                unverified_claims=("missing_plan",),
            )

        running = replace(
            episode,
            status=ConsoleEpisodeStatus.DISPATCHING,
            events=episode.events
            + (
                ConsoleEvent(
                    event_type="dispatch_started",
                    occurred_at=self._clock(),
                    details={"plan_hash": compute_plan_hash(episode.plan)},
                ),
            ),
        )
        attempted: list[str] = []
        blocked_actions: list[str] = []
        verifications: list[VerificationRecord] = []
        evidence_refs: list[str] = []
        unverified_claims: list[str] = []

        for action in running.plan:
            if abort_requested is not None and abort_requested(running, action):
                final_episode = replace(
                    running,
                    status=ConsoleEpisodeStatus.ABORTED,
                    events=running.events
                    + (
                        ConsoleEvent(
                            event_type="episode_aborted",
                            occurred_at=self._clock(),
                            details={"action_id": action.action_id},
                        ),
                    ),
                )
                return final_episode, self._build_receipt(
                    episode=final_episode,
                    final_status=ConsoleFinalStatus.ABORTED,
                    attempted=tuple(attempted),
                    blocked=(action.action_id,),
                    verifications=tuple(verifications),
                    evidence_refs=tuple(evidence_refs),
                    unverified_claims=("operator_abort_requested",),
                )

            current_state_hash = (
                state_hash_provider(running, action)
                if state_hash_provider is not None
                else (running.snapshot.state_hash if running.snapshot is not None else None)
            )
            decision = self.can_dispatch(
                running,
                action,
                current_state_hash=current_state_hash,
            )
            if not decision.allowed:
                blocked_actions.append(action.action_id)
                unverified_claims.append(decision.reason)
                final_episode = replace(
                    running,
                    status=_episode_status_for_block_reason(decision.reason),
                    events=running.events
                    + (
                        ConsoleEvent(
                            event_type="action_blocked",
                            occurred_at=decision.evaluated_at,
                            details={
                                "action_id": action.action_id,
                                "reason": decision.reason,
                                "approval_mode": decision.approval_mode.value,
                            },
                        ),
                    ),
                )
                return final_episode, self._build_receipt(
                    episode=final_episode,
                    final_status=ConsoleFinalStatus.BLOCKED,
                    attempted=tuple(attempted),
                    blocked=tuple(blocked_actions),
                    verifications=tuple(verifications),
                    evidence_refs=tuple(evidence_refs),
                    unverified_claims=tuple(unverified_claims),
                )

            attempted.append(action.action_id)
            dispatch_result = _dispatch_through_gateway(gateway, running, action, self._clock())
            evidence_refs.extend(dispatch_result.evidence_refs)
            if _risk_escalated_beyond_lane(action, dispatch_result, running.approval_lease):
                unverified_claims.append("risk_escalated")
                final_episode = replace(
                    running,
                    status=ConsoleEpisodeStatus.PAUSED,
                    events=running.events
                    + (
                        ConsoleEvent(
                            event_type="risk_escalation_paused",
                            occurred_at=self._clock(),
                            details={
                                "action_id": action.action_id,
                                "original_risk_score": action.risk_score,
                                "escalated_risk_score": dispatch_result.escalated_risk_score,
                            },
                        ),
                    ),
                )
                return final_episode, self._build_receipt(
                    episode=final_episode,
                    final_status=ConsoleFinalStatus.BLOCKED,
                    attempted=tuple(attempted),
                    blocked=(action.action_id,),
                    verifications=tuple(verifications),
                    evidence_refs=tuple(evidence_refs),
                    unverified_claims=tuple(unverified_claims),
                )

            hidden_side_effects = _hidden_side_effect_names(
                declared=action.side_effects,
                actual=dispatch_result.actual_side_effects,
            )
            if hidden_side_effects:
                unverified_claims.extend(hidden_side_effects)
                final_episode = replace(
                    running,
                    status=ConsoleEpisodeStatus.QUARANTINED,
                    events=running.events
                    + (
                        ConsoleEvent(
                            event_type="action_quarantined",
                            occurred_at=self._clock(),
                            details={
                                "action_id": action.action_id,
                                "reason": "undeclared_observed_side_effects",
                                "side_effects": tuple(hidden_side_effects),
                            },
                        ),
                    ),
                )
                return final_episode, self._build_receipt(
                    episode=final_episode,
                    final_status=ConsoleFinalStatus.QUARANTINED,
                    attempted=tuple(attempted),
                    blocked=tuple(blocked_actions),
                    verifications=tuple(verifications),
                    evidence_refs=tuple(evidence_refs),
                    unverified_claims=tuple(unverified_claims),
                )

            verification = (
                verifier.verify(action, dispatch_result, self._clock())
                if verifier is not None
                else default_verify(action, dispatch_result, self._clock())
            )
            verifications.append(verification)
            if not dispatch_result.tool_success:
                final_status = (
                    ConsoleFinalStatus.FAILED_UNRECOVERABLE
                    if action.recovery_class is RecoveryClass.R4_MANUAL_ESCALATION
                    else ConsoleFinalStatus.FAILED_RECOVERABLE
                )
                unverified_claims.append(dispatch_result.failure_reason or "tool_reported_failure")
                final_episode = replace(
                    running,
                    status=ConsoleEpisodeStatus.CLOSED,
                    events=running.events
                    + (
                        ConsoleEvent(
                            event_type="action_failed",
                            occurred_at=self._clock(),
                            details={
                                "action_id": action.action_id,
                                "reason": dispatch_result.failure_reason or "tool_reported_failure",
                            },
                        ),
                    ),
                )
                return final_episode, self._build_receipt(
                    episode=final_episode,
                    final_status=final_status,
                    attempted=tuple(attempted),
                    blocked=tuple(blocked_actions),
                    verifications=tuple(verifications),
                    evidence_refs=tuple(evidence_refs),
                    unverified_claims=tuple(unverified_claims),
                )
            if verification.missing_effects:
                unverified_claims.extend(verification.missing_effects)
                final_episode = replace(running, status=ConsoleEpisodeStatus.CLOSED)
                return final_episode, self._build_receipt(
                    episode=final_episode,
                    final_status=ConsoleFinalStatus.PARTIAL_SUCCESS,
                    attempted=tuple(attempted),
                    blocked=tuple(blocked_actions),
                    verifications=tuple(verifications),
                    evidence_refs=tuple(evidence_refs),
                    unverified_claims=tuple(unverified_claims),
                )
            if not verification.independently_verified:
                unverified_claims.extend(verification.mismatch_reasons or ("independent_evidence_missing",))
                final_episode = replace(running, status=ConsoleEpisodeStatus.CLOSED)
                return final_episode, self._build_receipt(
                    episode=final_episode,
                    final_status=ConsoleFinalStatus.UNVERIFIED_SUCCESS,
                    attempted=tuple(attempted),
                    blocked=tuple(blocked_actions),
                    verifications=tuple(verifications),
                    evidence_refs=tuple(evidence_refs),
                    unverified_claims=tuple(unverified_claims),
                )

        final_episode = replace(
            running,
            status=ConsoleEpisodeStatus.CLOSED,
            events=running.events
            + (
                ConsoleEvent(
                    event_type="episode_verified",
                    occurred_at=self._clock(),
                    details={"attempted": tuple(attempted)},
                ),
            ),
        )
        return final_episode, self._build_receipt(
            episode=final_episode,
            final_status=ConsoleFinalStatus.VERIFIED_SUCCESS,
            attempted=tuple(attempted),
            blocked=tuple(blocked_actions),
            verifications=tuple(verifications),
            evidence_refs=tuple(evidence_refs),
            unverified_claims=tuple(unverified_claims),
        )

    def _build_receipt(
        self,
        *,
        episode: OperatorConsoleEpisode,
        final_status: ConsoleFinalStatus,
        attempted: tuple[str, ...],
        blocked: tuple[str, ...],
        verifications: tuple[VerificationRecord, ...],
        evidence_refs: tuple[str, ...],
        unverified_claims: tuple[str, ...],
    ) -> OperatorConsoleReceipt:
        issued_at = self._clock()
        safe_evidence_refs = tuple(_redact_sensitive_ref(ref) for ref in evidence_refs)
        receipt_id = stable_identifier(
            "ocf-receipt",
            {
                "episode_id": episode.episode_id,
                "final_status": final_status.value,
                "issued_at": issued_at,
            },
        )
        receipt_hash = _receipt_hash(
            {
                "receipt_id": receipt_id,
                "episode_id": episode.episode_id,
                "final_status": final_status.value,
                "attempted": attempted,
                "blocked": blocked,
                "verification_count": len(verifications),
                "evidence_refs": safe_evidence_refs,
                "unverified_claims": unverified_claims,
                "issued_at": issued_at,
            }
        )
        return OperatorConsoleReceipt(
            receipt_id=receipt_id,
            episode_id=episode.episode_id,
            final_status=final_status,
            actions_attempted=attempted,
            actions_blocked=blocked,
            verification_records=verifications,
            evidence_refs=safe_evidence_refs,
            unverified_claims=tuple(_redact_sensitive_ref(ref) for ref in unverified_claims),
            issued_at=issued_at,
            receipt_hash=receipt_hash,
        )


def compute_plan_hash(actions: tuple[ConsolePlannedAction, ...]) -> str:
    """Return the stable approval fingerprint for an exact plan version."""
    if not actions:
        raise RuntimeCoreInvariantError("plan hash requires at least one action")
    payload = [action.to_json_dict() for action in actions]
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


def score_action_risk(
    *,
    impact: int,
    irreversibility: int,
    uncertainty: int,
    data_sensitivity: int,
    externality: int,
    novelty: int,
    blast_radius: int,
    cost_exposure: int,
    permission_power: int,
    recovery_confidence: int,
    evidence_strength: int,
) -> int:
    """Compute the OCF-R2 bounded risk score."""
    raw = (
        impact
        + irreversibility
        + uncertainty
        + data_sensitivity
        + externality
        + novelty
        + blast_radius
        + cost_exposure
        + permission_power
        - recovery_confidence
        - evidence_strength
    )
    return max(0, min(100, raw))


def approval_mode_for_action(action: ConsolePlannedAction) -> ApprovalMode:
    """Map risk score and intent class to the required autonomy lane."""
    if action.intent_class is ConsoleIntentClass.CRITICAL or action.risk_score >= 71:
        return ApprovalMode.STRONG
    if action.risk_score >= 46:
        return ApprovalMode.EXPLICIT
    if action.risk_score >= 21:
        return ApprovalMode.SOFT_NOTIFY
    return ApprovalMode.AUTO


def default_verify(
    action: ConsolePlannedAction,
    dispatch_result: GatewayDispatchResult,
    verified_at: str,
) -> VerificationRecord:
    """Verify observed effects independently from the tool status flag."""
    expected = set(action.expected_effects)
    observed = set(dispatch_result.observed_effects)
    missing = tuple(sorted(expected - observed))
    mismatch_reasons: tuple[str, ...] = ()
    if not dispatch_result.tool_success:
        mismatch_reasons = (dispatch_result.failure_reason or "tool_reported_failure",)
    elif missing:
        mismatch_reasons = ("missing_expected_effects",)
    elif not dispatch_result.evidence_refs:
        mismatch_reasons = ("independent_evidence_missing",)
    return VerificationRecord(
        action_id=action.action_id,
        tool_reported_success=dispatch_result.tool_success,
        independently_verified=dispatch_result.tool_success and not missing and bool(dispatch_result.evidence_refs),
        observed_effects=dispatch_result.observed_effects,
        missing_effects=missing,
        mismatch_reasons=mismatch_reasons,
        verified_at=verified_at,
    )


def _decision(
    allowed: bool,
    reason: str,
    approval_mode: ApprovalMode,
    evaluated_at: str,
) -> DispatchDecision:
    return DispatchDecision(
        allowed=allowed,
        reason=reason,
        approval_mode=approval_mode,
        evaluated_at=evaluated_at,
    )


def _dispatch_through_gateway(
    gateway: ConsoleExternalEffectGateway,
    episode: OperatorConsoleEpisode,
    action: ConsolePlannedAction,
    observed_at: str,
) -> GatewayDispatchResult:
    uao_binding = _console_gateway_uao_binding(episode, action)
    try:
        result = gateway.dispatch(episode, action)
    except Exception:
        return GatewayDispatchResult(
            action_id=action.action_id,
            tool_success=False,
            observed_effects=(),
            evidence_refs=(uao_binding["admission_receipt_ref"],),
            failure_reason="gateway_dispatch_failed",
        )
    if result.action_id != action.action_id:
        return GatewayDispatchResult(
            action_id=action.action_id,
            tool_success=False,
            observed_effects=(),
            evidence_refs=(uao_binding["admission_receipt_ref"],),
            failure_reason="gateway_action_mismatch",
        )
    ensure_non_empty_text("observed_at", observed_at)
    return result


def _console_gateway_uao_binding(
    episode: OperatorConsoleEpisode,
    action: ConsolePlannedAction,
) -> dict[str, str]:
    """Return the UAO-style binding identity for an OCF gateway dispatch."""
    universal_action = stable_identifier(
        "universal-action",
        {
            "episode_id": episode.episode_id,
            "action_id": action.action_id,
            "capability_id": action.capability_id,
        },
    )
    return {
        "universal_action": universal_action,
        "action_envelope": f"ocf-action-envelope://{episode.episode_id}/{action.action_id}",
        "admission_receipt_ref": f"ocf-admission://{episode.episode_id}/{action.action_id}",
        "execution_receipt_ref": f"ocf-execution://{episode.episode_id}/{action.action_id}",
        "closure_state": "pending_gateway_verification",
    }


def _hidden_side_effect_names(
    *,
    declared: SideEffectManifest,
    actual: SideEffectManifest | None,
) -> tuple[str, ...]:
    if actual is None:
        return ()
    hidden: list[str] = []
    for field_name in (
        "reads_data",
        "writes_data",
        "sends_external_data",
        "changes_permissions",
        "changes_money",
        "changes_public_state",
        "uses_network",
        "stores_logs",
        "touches_secrets",
    ):
        if getattr(actual, field_name) and not getattr(declared, field_name):
            hidden.append(field_name)
    return tuple(hidden)


def _risk_escalated_beyond_lane(
    action: ConsolePlannedAction,
    dispatch_result: GatewayDispatchResult,
    approval_lease: ApprovalLease | None,
) -> bool:
    escalated_score = dispatch_result.escalated_risk_score
    if escalated_score is None or escalated_score <= action.risk_score:
        return False
    if approval_lease is not None:
        return escalated_score > approval_lease.risk_ceiling
    return approval_mode_for_action(
        replace(action, risk_score=escalated_score),
    ) != approval_mode_for_action(action)


def _episode_status_for_block_reason(reason: str) -> ConsoleEpisodeStatus:
    if reason in {"approval_expired", "approval_plan_mismatch", "approval_state_mismatch"}:
        return ConsoleEpisodeStatus.APPROVAL_EXPIRED
    if reason == "stale_snapshot":
        return ConsoleEpisodeStatus.STALE_STATE
    if reason in {
        "undeclared_side_effects",
        "missing_recovery_plan",
        "hostile_input_authority_violation",
        "risk_exceeds_approval",
        "action_not_approved",
        "cost_limit_exceeded",
    }:
        return ConsoleEpisodeStatus.POLICY_DENIED
    return ConsoleEpisodeStatus.BLOCKED


def _is_expired(expires_at: str, now: str) -> bool:
    return _parse_datetime(now) > _parse_datetime(expires_at)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _receipt_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


def _redact_sensitive_ref(value: str) -> str:
    text = ensure_non_empty_text("value", value)
    lowered = text.lower()
    if "secret" not in lowered and "token" not in lowered and "password" not in lowered:
        return text
    digest = sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"redacted-sensitive-ref:{digest}"
