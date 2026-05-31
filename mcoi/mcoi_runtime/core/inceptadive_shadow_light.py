"""Light InceptaDive Shadow Pass.

Purpose: run cheap deterministic ambiguity, risk, memory-relevance, and missing
precondition checks before deeper interrogation is requested.
Governance scope: advisory analysis only; this module has no execution,
mutation, approval, retrieval, or tool authority.
Dependencies: shared shadow types and deterministic lexical inspection.
Invariants: light findings can request repair or deep review, but cannot approve
or execute an action.
"""

from __future__ import annotations

import re

from mcoi_runtime.core.inceptadive_shadow_types import (
    ShadowContext,
    ShadowFinding,
    ShadowFindingKind,
    ShadowMode,
    ShadowPassResult,
    ShadowSeverity,
    ShadowVerdict,
    severity_rank,
)

_AMBIGUOUS_TERMS = {"it", "that", "this", "them", "those", "these"}
_RISKY_VERBS = {"deploy", "release", "publish", "merge", "approve", "rollback", "migrate", "launch"}
_DESTRUCTIVE_VERBS = {"delete", "destroy", "purge", "wipe", "drop", "remove"}
_EXTERNAL_VERBS = {"send", "email", "notify", "post", "publish", "message"}
_APPROVAL_TERMS = {"deploy", "release", "contract", "payment", "legal", "production", "prod", "dns"}
_EVIDENCE_TERMS = {"approved", "verified", "evidence", "receipt", "proof", "review"}
_SCOPE_TERMS = {"production", "prod", "staging", "dev", "repository", "project", "module", "tenant"}


def run_light_shadow_pass(context: ShadowContext) -> ShadowPassResult:
    """Run a deterministic lightweight shadow inspection.

    The light pass is designed to be safe as an almost-always-on helper. It does
    not retrieve memory; it only flags when memory or a deeper pass should be
    consulted.
    """

    checked_context = context.with_integrity()
    text = _normalize_text(checked_context.text_surface())
    tokens = frozenset(_word_tokens(text))
    findings: list[ShadowFinding] = []

    if _contains_ambiguous_reference(tokens) and not checked_context.explicit_target.strip():
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.MISSING_TARGET,
                severity=ShadowSeverity.HIGH if _has_side_effect(tokens, checked_context) else ShadowSeverity.MEDIUM,
                summary="request contains an ambiguous reference without an explicit target",
                repair_required=True,
                recommended_action="resolve the target before planning or execution",
            )
        )

    if _is_continue_without_scope(text, checked_context):
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.MISSING_SCOPE,
                severity=ShadowSeverity.MEDIUM,
                summary="continuation request lacks an explicit project, workflow, or scope",
                repair_required=True,
                recommended_action="retrieve or ask for the intended project scope",
            )
        )

    risky_hits = sorted(tokens.intersection(_RISKY_VERBS))
    if risky_hits:
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.RISK_DETECTED,
                severity=ShadowSeverity.HIGH,
                summary="request contains high-impact workflow verbs: " + ", ".join(risky_hits),
                recommended_action="run deep shadow interrogation before governance",
            )
        )

    destructive_hits = sorted(tokens.intersection(_DESTRUCTIVE_VERBS))
    if destructive_hits:
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.UNSAFE_ACTION,
                severity=ShadowSeverity.CRITICAL,
                summary="request contains destructive verbs: " + ", ".join(destructive_hits),
                repair_required=True,
                recommended_action="require strict preflight with target, scope, retention policy, and rollback evidence",
            )
        )

    external_hits = sorted(tokens.intersection(_EXTERNAL_VERBS))
    if external_hits or checked_context.external_side_effect:
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.RISK_DETECTED,
                severity=ShadowSeverity.HIGH,
                summary="request may create an external side effect",
                recommended_action="run deep or strict preflight before execution",
            )
        )

    if tokens.intersection(_APPROVAL_TERMS) and not tokens.intersection(_EVIDENCE_TERMS):
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.MISSING_EVIDENCE,
                severity=ShadowSeverity.MEDIUM,
                summary="action appears approval- or proof-sensitive but no evidence marker is present",
                repair_required=True,
                recommended_action="attach proof, receipt, approval, or review evidence before governance",
            )
        )

    if _memory_likely_relevant(tokens, checked_context):
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.MEMORY_RELEVANT,
                severity=ShadowSeverity.LOW,
                summary="prior memory may affect interpretation, blockers, or next safe action",
                constructive_delta=True,
                recommended_action="consult note-memory projection before final planning",
            )
        )

    if checked_context.memory_contradiction:
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.MEMORY_CONTRADICTION,
                severity=ShadowSeverity.HIGH,
                summary="related memory has an active contradiction marker",
                repair_required=True,
                recommended_action="open repair path before allowing the candidate action to proceed",
            )
        )

    if checked_context.scope.strip() == "" and tokens.intersection(_SCOPE_TERMS):
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.MISSING_SCOPE,
                severity=ShadowSeverity.MEDIUM,
                summary="scope-sensitive term appears but structured scope is unset",
                repair_required=True,
                recommended_action="bind the request to a concrete scope before governance",
            )
        )

    if not findings:
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.SAFE_CLEAR,
                severity=ShadowSeverity.INFO,
                summary="light shadow pass found no ambiguity, risky verb, or missing evidence marker",
                constructive_delta=True,
                recommended_action="continue to normal governance path",
            )
        )

    return _result_from_findings(checked_context, tuple(findings))


def _result_from_findings(context: ShadowContext, findings: tuple[ShadowFinding, ...]) -> ShadowPassResult:
    max_severity = max((severity_rank(finding.severity) for finding in findings), default=0)
    has_destructive = any(finding.kind == ShadowFindingKind.UNSAFE_ACTION for finding in findings)
    needs_repair = any(finding.repair_required for finding in findings)
    has_contradiction = any(finding.kind == ShadowFindingKind.MEMORY_CONTRADICTION for finding in findings)
    high_risk = max_severity >= severity_rank(ShadowSeverity.HIGH)

    if has_destructive:
        verdict = ShadowVerdict.BLOCK_RECOMMENDED
        needs_deep = False
        block_recommended = True
    elif has_contradiction:
        verdict = ShadowVerdict.REPAIR_REQUIRED
        needs_deep = True
        block_recommended = False
    elif high_risk:
        verdict = ShadowVerdict.DEEP_REQUIRED
        needs_deep = True
        block_recommended = False
    elif needs_repair:
        verdict = ShadowVerdict.REPAIR_REQUIRED
        needs_deep = False
        block_recommended = False
    elif any(finding.kind != ShadowFindingKind.SAFE_CLEAR for finding in findings):
        verdict = ShadowVerdict.ADVISORY
        needs_deep = False
        block_recommended = False
    else:
        verdict = ShadowVerdict.CLEAR
        needs_deep = False
        block_recommended = False

    return ShadowPassResult(
        result_id="pending",
        request_id=context.request_id,
        mode=ShadowMode.LIGHT,
        stage=context.stage,
        verdict=verdict,
        findings=findings,
        needs_deep_pass=needs_deep,
        needs_repair=needs_repair,
        block_recommended=block_recommended,
        created_at=context.created_at,
    ).with_integrity()


def _finding(
    context: ShadowContext,
    *,
    kind: ShadowFindingKind,
    severity: ShadowSeverity,
    summary: str,
    confidence: float = 1.0,
    constructive_delta: bool = False,
    repair_required: bool = False,
    recommended_action: str = "",
) -> ShadowFinding:
    return ShadowFinding.create(
        request_id=context.request_id,
        stage=context.stage,
        kind=kind,
        severity=severity,
        summary=summary,
        confidence=confidence,
        constructive_delta=constructive_delta,
        fracture_delta=kind != ShadowFindingKind.SAFE_CLEAR and not constructive_delta,
        repair_required=repair_required,
        recommended_action=recommended_action,
        created_at=context.created_at,
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _word_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9_#.-]+", value))


def _contains_ambiguous_reference(tokens: frozenset[str]) -> bool:
    return bool(tokens.intersection(_AMBIGUOUS_TERMS))


def _has_side_effect(tokens: frozenset[str], context: ShadowContext) -> bool:
    return bool(tokens.intersection(_RISKY_VERBS | _DESTRUCTIVE_VERBS | _EXTERNAL_VERBS)) or context.external_side_effect


def _is_continue_without_scope(text: str, context: ShadowContext) -> bool:
    if context.scope.strip() or context.explicit_target.strip():
        return False
    return bool(re.search(r"\b(continue|resume|finish|complete)\b", text))


def _memory_likely_relevant(tokens: frozenset[str], context: ShadowContext) -> bool:
    memory_terms = {
        "continue",
        "resume",
        "project",
        "workflow",
        "decision",
        "blocker",
        "blocked",
        "approval",
        "approved",
        "deploy",
        "launch",
    }
    return bool(context.retrieval_receipt_ids or tokens.intersection(memory_terms))
