"""Strict preflight helpers for InceptaDive Shadow Pass.

Purpose: inspect high-impact candidate actions before execution governance is
allowed to continue.
Governance scope: advisory preflight only; no execution, mutation, approval,
retrieval, or tool call is performed here.
Dependencies: shared shadow types, deterministic action inspection, and stable
identifier generation.
Invariants: destructive, external, production, legal, financial, and security
sensitive actions require explicit target, scope, and evidence before proceeding
to governance; explicit evidence refs are retained only as deterministic public
refs.
"""

from __future__ import annotations

import re
from typing import Sequence

from mcoi_runtime.core.inceptadive_shadow_types import (
    ShadowContext,
    ShadowFinding,
    ShadowFindingKind,
    ShadowMode,
    ShadowPassResult,
    ShadowSeverity,
    ShadowStage,
    ShadowVerdict,
)
from mcoi_runtime.core.invariants import stable_identifier

_DESTRUCTIVE_TERMS = {"delete", "destroy", "purge", "wipe", "drop", "remove"}
_DEPLOY_TERMS = {"deploy", "release", "publish", "launch", "rollout"}
_LEGAL_TERMS = {"contract", "legal", "clause", "agreement", "signature"}
_FINANCE_TERMS = {"payment", "pay", "charge", "invoice", "budget", "vendor"}
_SECURITY_TERMS = {"secret", "token", "credential", "dns", "production", "prod", "security"}
_EXTERNAL_TERMS = {"send", "email", "notify", "post", "message", "publish"}
_PROOF_TERMS = {"approved", "approval", "verified", "receipt", "evidence", "review", "proof"}
_ROLLBACK_TERMS = {"rollback", "backup", "restore", "revert"}
_PUBLIC_REQUIRED_EVIDENCE_PREFIX = "shadow_required_evidence_"


def run_strict_preflight(context: ShadowContext, *, required_evidence_refs: Sequence[str] | None = None) -> ShadowPassResult:
    """Run strict preflight over a candidate action.

    The result can recommend block or repair, but cannot execute or approve. A
    downstream governance layer must still make the final decision.
    """

    checked_context = context.with_integrity()
    text = _normalize_text(checked_context.text_surface())
    tokens = frozenset(_word_tokens(text))
    evidence_refs = _public_required_evidence_refs(required_evidence_refs)
    findings: list[ShadowFinding] = []

    if checked_context.stage != ShadowStage.PREFLIGHT:
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.PLAN_GAP,
                severity=ShadowSeverity.MEDIUM,
                summary="strict preflight was invoked outside the preflight stage",
                repair_required=True,
                recommended_action="route the candidate action through preflight before governance",
            )
        )

    if not checked_context.explicit_target.strip():
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.MISSING_TARGET,
                severity=ShadowSeverity.HIGH,
                summary="candidate action has no explicit target",
                repair_required=True,
                recommended_action="bind the action to a concrete target before execution governance",
            )
        )

    if not checked_context.scope.strip() and tokens.intersection(_DESTRUCTIVE_TERMS | _DEPLOY_TERMS | _SECURITY_TERMS):
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.MISSING_SCOPE,
                severity=ShadowSeverity.HIGH,
                summary="candidate action is scope-sensitive but has no explicit scope",
                repair_required=True,
                recommended_action="bind repository, environment, tenant, module, or project scope before governance",
            )
        )

    destructive_hits = sorted(tokens.intersection(_DESTRUCTIVE_TERMS))
    if destructive_hits:
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.UNSAFE_ACTION,
                severity=ShadowSeverity.CRITICAL,
                summary="candidate action is destructive: " + ", ".join(destructive_hits),
                repair_required=True,
                recommended_action="require retention policy, backup or rollback evidence, and explicit approval",
            )
        )

    deploy_hits = sorted(tokens.intersection(_DEPLOY_TERMS))
    if deploy_hits and not tokens.intersection(_PROOF_TERMS):
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.MISSING_EVIDENCE,
                severity=ShadowSeverity.HIGH,
                summary="deployment or release action lacks approval/review/proof marker",
                repair_required=True,
                recommended_action="attach build, review, approval, rollback, and environment evidence before governance",
            )
        )

    if deploy_hits and not tokens.intersection(_ROLLBACK_TERMS):
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.MISSING_PRECONDITION,
                severity=ShadowSeverity.MEDIUM,
                summary="deployment or release action lacks rollback or revert marker",
                repair_required=True,
                recommended_action="record rollback or revert plan before execution governance",
            )
        )

    if tokens.intersection(_LEGAL_TERMS) and not tokens.intersection(_PROOF_TERMS):
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.MISSING_EVIDENCE,
                severity=ShadowSeverity.HIGH,
                summary="legal or contract action lacks approval evidence",
                repair_required=True,
                recommended_action="attach legal approval and latest-version evidence before sending or publishing",
            )
        )

    if tokens.intersection(_FINANCE_TERMS) and not tokens.intersection(_PROOF_TERMS):
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.MISSING_EVIDENCE,
                severity=ShadowSeverity.HIGH,
                summary="financial action lacks budget, approval, or receipt evidence",
                repair_required=True,
                recommended_action="attach budget/approval evidence before payment or charge governance",
            )
        )

    if tokens.intersection(_SECURITY_TERMS) and not tokens.intersection(_PROOF_TERMS):
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.MISSING_PRECONDITION,
                severity=ShadowSeverity.HIGH,
                summary="security-sensitive action lacks verification marker",
                repair_required=True,
                recommended_action="attach security verification, DNS proof, or credential-rotation evidence before governance",
            )
        )

    if tokens.intersection(_EXTERNAL_TERMS) or checked_context.external_side_effect:
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.RISK_DETECTED,
                severity=ShadowSeverity.HIGH,
                summary="candidate action can create an external side effect",
                recommended_action="require recipient/target validation and approval evidence before execution",
            )
        )

    if checked_context.memory_contradiction:
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.MEMORY_CONTRADICTION,
                severity=ShadowSeverity.HIGH,
                summary="candidate action is affected by unresolved memory contradiction",
                repair_required=True,
                recommended_action="resolve contradiction or escalate before execution governance",
            )
        )

    if evidence_refs:
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.SAFE_CLEAR,
                severity=ShadowSeverity.INFO,
                summary="preflight received explicit evidence references",
                evidence_refs=evidence_refs,
                constructive_delta=True,
                recommended_action="continue through governance with linked evidence",
            )
        )

    if not findings:
        findings.append(
            _finding(
                checked_context,
                kind=ShadowFindingKind.SAFE_CLEAR,
                severity=ShadowSeverity.INFO,
                summary="strict preflight found no high-impact blocker",
                constructive_delta=True,
                recommended_action="continue to Mullu governance verdict",
            )
        )

    return _result_from_findings(checked_context, tuple(findings))


def _result_from_findings(context: ShadowContext, findings: tuple[ShadowFinding, ...]) -> ShadowPassResult:
    has_critical = any(finding.severity == ShadowSeverity.CRITICAL for finding in findings)
    has_high_repair = any(finding.repair_required and finding.severity == ShadowSeverity.HIGH for finding in findings)
    needs_repair = any(finding.repair_required for finding in findings)
    needs_escalation = any(finding.kind == ShadowFindingKind.ESCALATION_REQUIRED for finding in findings)

    if has_critical or has_high_repair:
        verdict = ShadowVerdict.BLOCK_RECOMMENDED
        block_recommended = True
    elif needs_escalation:
        verdict = ShadowVerdict.ESCALATE
        block_recommended = False
    elif needs_repair:
        verdict = ShadowVerdict.REPAIR_REQUIRED
        block_recommended = False
    elif any(finding.kind != ShadowFindingKind.SAFE_CLEAR for finding in findings):
        verdict = ShadowVerdict.ADVISORY
        block_recommended = False
    else:
        verdict = ShadowVerdict.CLEAR
        block_recommended = False

    return ShadowPassResult(
        result_id="pending",
        request_id=context.request_id,
        mode=ShadowMode.STRICT_PREFLIGHT,
        stage=context.stage,
        verdict=verdict,
        findings=findings,
        needs_repair=needs_repair,
        needs_escalation=needs_escalation,
        block_recommended=block_recommended,
        created_at=context.created_at,
    ).with_integrity()


def _finding(
    context: ShadowContext,
    *,
    kind: ShadowFindingKind,
    severity: ShadowSeverity,
    summary: str,
    evidence_refs: Sequence[str] | None = None,
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
        evidence_refs=evidence_refs,
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


def _public_required_evidence_refs(values: Sequence[str] | None) -> tuple[str, ...]:
    """Return stable non-raw evidence refs for finding/result persistence."""

    refs: list[str] = []
    for value in values or ():
        normalized = " ".join(str(value or "").strip().split())
        if not normalized:
            continue
        if normalized.startswith(_PUBLIC_REQUIRED_EVIDENCE_PREFIX):
            refs.append(normalized)
        else:
            refs.append(
                _PUBLIC_REQUIRED_EVIDENCE_PREFIX
                + stable_identifier(
                    "inceptadive-shadow-core-required-evidence",
                    {"value": normalized},
                )
            )
    return tuple(refs)
