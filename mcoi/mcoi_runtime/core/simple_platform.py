"""Simple user-facing facade for governed platform actions.

Purpose: expose a small task vocabulary over the MVK governance SDK so product
surfaces do not require users to understand intent frames, proof stamps, or
constraint identifiers.
Governance scope: usability projection only; all action authority remains
owned by the Runtime ABI and MVK gate.
Dependencies: dataclasses, typing literals, and governance SDK builders.
Invariants: every action check creates a bounded intent, declares side effects,
requires scope proof, and preserves raw proof references for audit readback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from .governance_sdk import (
    ActionSentenceBuilder,
    GovernanceClient,
    GovernanceClientConfig,
    IntentFrameBuilder,
)
from .invariants import RuntimeCoreInvariantError

SimpleActionKind = Literal["view", "change", "send", "verify"]
SimpleOutcome = Literal["ready", "needs_review", "blocked"]


@dataclass(frozen=True)
class SimpleActionRequest:
    """Plain task request from a user-facing surface."""

    goal: str
    action: SimpleActionKind
    target: str
    allowed_area: str
    actor_id: str = "local-user"

    def validate(self) -> None:
        """Reject incomplete requests before governance execution."""

        _require_text(self.goal, "goal")
        _require_text(self.target, "target")
        _require_text(self.allowed_area, "allowed_area")
        _require_text(self.actor_id, "actor_id")


@dataclass(frozen=True)
class SimpleActionCheck:
    """Plain outcome plus audit references for one action check."""

    outcome: SimpleOutcome
    title: str
    message: str
    next_step: str
    decision_ref: str
    proof_stamp_ref: str
    boundary_witness_ref: str
    raw_decision: str
    raw_reason: str
    blocked_reasons: tuple[str, ...]
    review_reasons: tuple[str, ...]

    @property
    def ok_to_continue(self) -> bool:
        """Return whether the action can proceed without extra review."""

        return self.outcome == "ready"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible projection."""

        return {
            "outcome": self.outcome,
            "title": self.title,
            "message": self.message,
            "next_step": self.next_step,
            "ok_to_continue": self.ok_to_continue,
            "decision_ref": self.decision_ref,
            "proof_stamp_ref": self.proof_stamp_ref,
            "boundary_witness_ref": self.boundary_witness_ref,
            "raw_decision": self.raw_decision,
            "raw_reason": self.raw_reason,
            "blocked_reasons": list(self.blocked_reasons),
            "review_reasons": list(self.review_reasons),
        }


class SimplePlatform:
    """Small governed facade for user-oriented action checks."""

    def __init__(self, client: GovernanceClient | None = None) -> None:
        self._client = client

    def check_action(self, request: SimpleActionRequest | Mapping[str, object]) -> SimpleActionCheck:
        """Check whether a plain action is ready, blocked, or needs review."""

        action_request = _request_from_mapping(request) if isinstance(request, Mapping) else request
        action_request.validate()
        client = self._client or GovernanceClient(GovernanceClientConfig(caller_id=action_request.actor_id))
        intent = (
            IntentFrameBuilder()
            .goal(action_request.goal)
            .within_scope(action_request.allowed_area)
            .succeeds_when("plain_user_outcome_emitted")
            .build()
        )
        action = _build_action(action_request).build()
        result = client.gate_action(intent=intent, action=action)
        decision = result.raw_call.output["result"]["decision"]
        blocked_reasons = tuple(_plain_reason(item) for item in decision["violated_constraints"])
        review_reasons = tuple(_plain_reason(item) for item in decision["required_escalations"])
        return _project_check(
            raw_decision=result.decision,
            raw_reason=result.explanation,
            blocked_reasons=blocked_reasons,
            review_reasons=review_reasons,
            decision_ref=result.decision_ref,
            proof_stamp_ref=result.proof_stamp_ref,
            boundary_witness_ref=result.boundary_witness_ref,
        )


def _build_action(request: SimpleActionRequest) -> ActionSentenceBuilder:
    """Map a plain action onto a governed action sentence builder."""

    if request.action == "view":
        return ActionSentenceBuilder.read_file(request.target).within_scope(request.target).requires_proof("scope_checked")
    if request.action == "change":
        return ActionSentenceBuilder.write_file(request.target).within_scope(request.target).requires_proof("scope_checked")
    if request.action == "send":
        return (
            ActionSentenceBuilder("notify", "message", request.target)
            .within_scope(request.target)
            .with_side_effects("external_write")
            .requires_proof("scope_checked")
        )
    if request.action == "verify":
        return (
            ActionSentenceBuilder("verify", "artifact", request.target)
            .within_scope(request.target)
            .requires_proof("scope_checked")
        )
    raise RuntimeCoreInvariantError(f"unsupported simple action: {request.action}")


def _project_check(
    *,
    raw_decision: str,
    raw_reason: str,
    blocked_reasons: tuple[str, ...],
    review_reasons: tuple[str, ...],
    decision_ref: str,
    proof_stamp_ref: str,
    boundary_witness_ref: str,
) -> SimpleActionCheck:
    """Translate governed decision details into a user-facing outcome."""

    if raw_decision == "allow":
        return SimpleActionCheck(
            outcome="ready",
            title="Ready",
            message="This action stays inside the allowed area and has the required proof.",
            next_step="Continue with the action.",
            decision_ref=decision_ref,
            proof_stamp_ref=proof_stamp_ref,
            boundary_witness_ref=boundary_witness_ref,
            raw_decision=raw_decision,
            raw_reason=raw_reason,
            blocked_reasons=(),
            review_reasons=(),
        )
    if raw_decision == "escalate":
        reasons = review_reasons or ("This action changes something outside the local workspace.",)
        return SimpleActionCheck(
            outcome="needs_review",
            title="Needs review",
            message="This action needs approval before it can continue.",
            next_step="Send it to an approver with the proof reference.",
            decision_ref=decision_ref,
            proof_stamp_ref=proof_stamp_ref,
            boundary_witness_ref=boundary_witness_ref,
            raw_decision=raw_decision,
            raw_reason=raw_reason,
            blocked_reasons=(),
            review_reasons=reasons,
        )
    if raw_decision == "block":
        reasons = blocked_reasons or ("The action does not satisfy the required constraints.",)
        return SimpleActionCheck(
            outcome="blocked",
            title="Blocked",
            message="This action cannot continue as requested.",
            next_step="Narrow the request or change the allowed area, then check again.",
            decision_ref=decision_ref,
            proof_stamp_ref=proof_stamp_ref,
            boundary_witness_ref=boundary_witness_ref,
            raw_decision=raw_decision,
            raw_reason=raw_reason,
            blocked_reasons=reasons,
            review_reasons=(),
        )
    raise RuntimeCoreInvariantError(f"unsupported governance decision: {raw_decision}")


def _request_from_mapping(value: Mapping[str, object]) -> SimpleActionRequest:
    """Load a simple request from a JSON-like mapping."""

    return SimpleActionRequest(
        goal=_required_text(value, "goal"),
        action=_action_kind(_required_text(value, "action")),
        target=_required_text(value, "target"),
        allowed_area=_required_text(value, "allowed_area"),
        actor_id=str(value.get("actor_id", "local-user")).strip() or "local-user",
    )


def _plain_reason(reason: object) -> str:
    """Translate internal constraint ids into stable plain language."""

    text = str(reason)
    translations = {
        "scope_within_intent": "The target is outside the allowed area.",
        "kernel.side_effect.declared": "The action includes an undeclared side effect.",
        "kernel.proof.scope_checked:scope_checked": "The action is missing required scope proof.",
        "kernel.side_effect.external_requires_approval:external_write": "External changes require approval.",
        "mfidel_atomicity_violation": "Mfidel atomicity would be violated.",
    }
    return translations.get(text, text.replace("_", " "))


def _action_kind(value: str) -> SimpleActionKind:
    if value in {"view", "change", "send", "verify"}:
        return value  # type: ignore[return-value]
    raise RuntimeCoreInvariantError("action must be one of: view, change, send, verify")


def _required_text(value: Mapping[str, object], field_name: str) -> str:
    if field_name not in value:
        raise RuntimeCoreInvariantError(f"{field_name} is required")
    text = str(value[field_name]).strip()
    _require_text(text, field_name)
    return text


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeCoreInvariantError(f"{field_name} must be non-empty text")
