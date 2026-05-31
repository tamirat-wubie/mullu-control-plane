"""Mode gate for the InceptaDive Shadow Pass.

Purpose: choose off, light, deep, or strict-preflight shadow interrogation before
normal interpretation, planning, workflow, and execution steps continue.
Governance scope: trigger selection only; no tool invocation, execution,
mutation, or governance approval is performed here.
Dependencies: shared shadow types and deterministic text matching.
Invariants: high-risk side effects route to strict/deep review, ambiguous targets
cannot silently pass, and disabled mode emits an explicit off decision.
"""

from __future__ import annotations

import re

from mcoi_runtime.core.inceptadive_shadow_types import (
    ShadowContext,
    ShadowInterrogationConfig,
    ShadowInterrogationDecision,
    ShadowMode,
    ShadowSeverity,
    ShadowStage,
    severity_rank,
)

_AMBIGUOUS_REFERENCES = {
    "it",
    "that",
    "this",
    "them",
    "those",
    "these",
    "do it",
    "go do it",
    "deploy it",
    "ship it",
    "send it",
    "delete it",
}

_DEEP_ACTIONS = {
    "deploy",
    "release",
    "publish",
    "merge",
    "approve",
    "schedule",
    "migrate",
    "rollback",
    "rotate",
    "configure",
    "provision",
    "launch",
}

_STRICT_ACTIONS = {
    "delete",
    "destroy",
    "purge",
    "wipe",
    "drop",
    "send",
    "email",
    "contract",
    "payment",
    "pay",
    "charge",
    "invoice",
    "dns",
    "secret",
    "token",
    "production",
    "prod",
    "legal",
}

_EXTERNAL_COMMUNICATIONS = {"send", "email", "notify", "post", "publish", "message", "contract"}


def decide_shadow_mode(
    context: ShadowContext,
    config: ShadowInterrogationConfig | None = None,
) -> ShadowInterrogationDecision:
    """Return the deterministic shadow mode for a request or candidate action.

    The gate is intentionally conservative for side effects. It performs only
    lexical/risk classification and returns a recommendation for downstream
    shadow execution. It does not execute, approve, mutate, or retrieve memory.
    """

    policy = config or ShadowInterrogationConfig()
    if not policy.enabled:
        return ShadowInterrogationDecision(
            request_id=context.request_id,
            mode=ShadowMode.OFF,
            triggers=("disabled",),
            reason="shadow pass disabled by policy",
        )

    text = _normalize_text(context.text_surface())
    tokens = frozenset(_word_tokens(text))
    triggers: list[str] = []

    if context.memory_contradiction:
        triggers.append("memory_contradiction")

    if _has_ambiguous_reference(text, tokens) and not context.explicit_target.strip():
        triggers.append("ambiguous_reference_without_target")

    if _is_continue_without_scope(text, context):
        triggers.append("continue_without_scope")

    strict_hits = sorted(tokens.intersection(_STRICT_ACTIONS))
    deep_hits = sorted(tokens.intersection(_DEEP_ACTIONS))
    external_hits = sorted(tokens.intersection(_EXTERNAL_COMMUNICATIONS))

    if strict_hits:
        triggers.append("strict_action:" + ",".join(strict_hits))
    if deep_hits:
        triggers.append("deep_action:" + ",".join(deep_hits))
    if external_hits or context.external_side_effect:
        triggers.append("external_side_effect")

    if severity_rank(context.risk_level) >= severity_rank(ShadowSeverity.HIGH):
        triggers.append("high_risk_context")

    if context.stage == ShadowStage.PREFLIGHT and policy.strict_preflight_enabled:
        if strict_hits or context.external_side_effect or severity_rank(context.risk_level) >= severity_rank(ShadowSeverity.HIGH):
            return ShadowInterrogationDecision(
                request_id=context.request_id,
                mode=ShadowMode.STRICT_PREFLIGHT,
                triggers=tuple(triggers or ["preflight_strict_default"]),
                reason="strict preflight required for high-impact candidate action",
                strict_fail_closed=True,
            )

    if strict_hits and policy.strict_preflight_enabled:
        return ShadowInterrogationDecision(
            request_id=context.request_id,
            mode=ShadowMode.STRICT_PREFLIGHT,
            triggers=tuple(triggers),
            reason="strict action requires preflight before governance",
            strict_fail_closed=True,
        )

    deep_required = bool(
        context.memory_contradiction
        or deep_hits
        or context.external_side_effect
        or external_hits
        or "ambiguous_reference_without_target" in triggers
        or "continue_without_scope" in triggers
        or severity_rank(context.risk_level) >= severity_rank(ShadowSeverity.HIGH)
    )
    if deep_required and policy.deep_enabled:
        return ShadowInterrogationDecision(
            request_id=context.request_id,
            mode=ShadowMode.DEEP,
            triggers=tuple(triggers),
            reason="deep shadow interrogation required by ambiguity, memory, side effect, or risk",
        )

    if policy.light_always_on:
        return ShadowInterrogationDecision(
            request_id=context.request_id,
            mode=ShadowMode.LIGHT,
            triggers=tuple(triggers or ["light_default"]),
            reason="light shadow interrogation selected for low-risk request",
        )

    return ShadowInterrogationDecision(
        request_id=context.request_id,
        mode=ShadowMode.OFF,
        triggers=tuple(triggers or ["no_shadow_required"]),
        reason="shadow pass not required by policy",
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _word_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9_#.-]+", value))


def _has_ambiguous_reference(text: str, tokens: frozenset[str]) -> bool:
    if text in _AMBIGUOUS_REFERENCES:
        return True
    return bool(tokens.intersection(_AMBIGUOUS_REFERENCES))


def _is_continue_without_scope(text: str, context: ShadowContext) -> bool:
    if context.scope.strip() or context.explicit_target.strip():
        return False
    return bool(re.search(r"\b(continue|resume|finish|complete)\b", text)) and bool(
        re.search(r"\b(project|work|task|it|this|that)?\b", text)
    )
