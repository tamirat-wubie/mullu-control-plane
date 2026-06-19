"""Bounded deep InceptaDive Shadow Pass engine.

Purpose: run repository-local deep interrogation when the shadow gate requires
more than light checks.
Governance scope: advisory inspection only; no approval, mutation, retrieval,
scheduling, or effect authority.
Dependencies: Concept Box projections, axis traversal, action taxonomy, and
shared shadow types.
Invariants: deep results are bounded, redacted, deterministic, lineage-aware,
and always carry execution_authority=false.
"""

from __future__ import annotations

import re
from typing import Sequence

from mcoi_runtime.core.concept_box_ledger import ConceptBox, ConceptBoxType
from mcoi_runtime.core.inceptadive_action_taxonomy import classify_shadow_action
from mcoi_runtime.core.inceptadive_axis_traversal import AxisTraversalPolicy, DeltaType, traverse_concept_box
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
from mcoi_runtime.core.note_memory_mesh import ProofState


_AMBIGUOUS_TERMS = {"it", "that", "this", "them", "those", "these"}


def run_deep_shadow_pass(
    context: ShadowContext,
    *,
    max_depth: int = 3,
    max_findings: int = 12,
) -> ShadowPassResult:
    """Run a bounded, redacted, non-executing deep shadow pass."""

    if max_depth < 1 or max_findings < 1:
        raise ValueError("deep shadow bounds must be positive")
    checked = context.with_integrity()
    text = _normalize_text(checked.text_surface())
    tokens = frozenset(_word_tokens(text))
    classification = classify_shadow_action(checked)
    box = _context_box(checked, classification.action_families)
    traversal = traverse_concept_box(box, policy=AxisTraversalPolicy(max_depth=max_depth, require_evidence=False))

    findings: list[ShadowFinding] = []
    if tokens.intersection(_AMBIGUOUS_TERMS) and not checked.explicit_target.strip():
        findings.append(
            _finding(
                checked,
                ShadowFindingKind.MISSING_TARGET,
                ShadowSeverity.HIGH if classification.external_side_effect else ShadowSeverity.MEDIUM,
                "deep interrogation found unresolved target binding",
                repair=True,
                action="bind explicit target before governance continues",
            )
        )
    if classification.strict_preflight_required and not checked.scope.strip():
        findings.append(
            _finding(
                checked,
                ShadowFindingKind.MISSING_SCOPE,
                ShadowSeverity.HIGH,
                "deep interrogation found missing scope for authority-sensitive action",
                repair=True,
                action="bind tenant, repository, environment, module, or workflow scope",
            )
        )
    if checked.memory_contradiction:
        findings.append(
            _finding(
                checked,
                ShadowFindingKind.MEMORY_CONTRADICTION,
                ShadowSeverity.HIGH,
                "deep interrogation found unresolved memory contradiction pressure",
                repair=True,
                action="resolve or split contradictory memory before action promotion",
            )
        )
    if classification.blocked_by_authority:
        findings.append(
            _finding(
                checked,
                ShadowFindingKind.UNSAFE_ACTION,
                ShadowSeverity.CRITICAL,
                "deep interrogation found component authority is not granted",
                repair=True,
                action="keep candidate blocked until component authority evidence is upgraded",
            )
        )
    if classification.external_side_effect:
        findings.append(
            _finding(
                checked,
                ShadowFindingKind.RISK_DETECTED,
                ShadowSeverity.HIGH,
                "deep interrogation found possible external side effect",
                action="require strict preflight, target proof, and governance verdict",
            )
        )
    if classification.evidence_required and not (checked.retrieval_receipt_ids or _has_proof_marker(tokens)):
        findings.append(
            _finding(
                checked,
                ShadowFindingKind.MISSING_EVIDENCE,
                ShadowSeverity.HIGH,
                "deep interrogation found missing evidence for authority-sensitive action",
                repair=True,
                action="attach evidence refs, receipt ids, proof, review, or approval marker",
            )
        )

    for axis_finding in traversal.findings:
        if len(findings) >= max_findings:
            break
        if axis_finding.delta_type == DeltaType.FRACTURE:
            findings.append(
                _finding(
                    checked,
                    ShadowFindingKind.REPAIR_REQUIRED,
                    ShadowSeverity.MEDIUM,
                    "deep axis traversal found a repair-required structural fracture",
                    repair=True,
                    action=axis_finding.repair_requirement or "route structural fracture to repair queue",
                )
            )

    if not findings:
        findings.append(
            _finding(
                checked,
                ShadowFindingKind.SAFE_CLEAR,
                ShadowSeverity.INFO,
                "deep interrogation found no bounded blocker",
                constructive=True,
                action="continue to Mullu governance verdict",
            )
        )

    return _result(checked, tuple(findings[:max_findings]))


def _context_box(context: ShadowContext, families: Sequence[str]) -> ConceptBox:
    evidence_refs = context.retrieval_receipt_ids or (context.context_hash,)
    risk_facets = []
    if severity_rank(context.risk_level) >= severity_rank(ShadowSeverity.HIGH):
        risk_facets.append(f"risk-level:{context.risk_level.value}")
    if context.memory_contradiction:
        risk_facets.append("memory-contradiction")
    if context.external_side_effect:
        risk_facets.append("external-side-effect")
    risk_facets.extend(f"authority-sensitive:{family}" for family in families)
    return ConceptBox(
        box_id="pending",
        box_type=ConceptBoxType.PROCESS,
        source_note_ids=(context.request_id,),
        source_event_ids=(f"{context.request_id}:{context.stage.value}",),
        identity_facets=(f"shadow-stage:{context.stage.value}", f"request:{context.request_id}"),
        behavior_facets=tuple(f"action-family:{family}" for family in families),
        intention_facets=("intent:present" if context.normal_intent.strip() else "intent:absent",),
        cause_facets=tuple(f"evidence:{ref}" for ref in evidence_refs),
        effect_facets=("external_side_effect" if context.external_side_effect else "governance_advisory_only",),
        risk_facets=tuple(dict.fromkeys(risk_facets)),
        evidence_refs=evidence_refs,
        created_at=context.created_at,
        updated_at=context.created_at,
        lineage=("InceptaDive-Shadow", "InceptaDive-M", "deep-engine"),
        proof_state=ProofState.UNKNOWN if risk_facets else ProofState.PASS,
    ).with_integrity()


def _finding(
    context: ShadowContext,
    kind: ShadowFindingKind,
    severity: ShadowSeverity,
    summary: str,
    *,
    constructive: bool = False,
    repair: bool = False,
    action: str = "",
) -> ShadowFinding:
    return ShadowFinding.create(
        request_id=context.request_id,
        stage=context.stage,
        kind=kind,
        severity=severity,
        summary=summary,
        evidence_refs=context.retrieval_receipt_ids,
        confidence=0.9 if repair else 0.78,
        constructive_delta=constructive,
        fracture_delta=kind != ShadowFindingKind.SAFE_CLEAR and not constructive,
        repair_required=repair,
        recommended_action=action,
        created_at=context.created_at,
    )


def _result(context: ShadowContext, findings: tuple[ShadowFinding, ...]) -> ShadowPassResult:
    has_critical = any(f.severity == ShadowSeverity.CRITICAL for f in findings)
    high_repair = any(f.repair_required and f.severity == ShadowSeverity.HIGH for f in findings)
    needs_repair = any(f.repair_required for f in findings)
    high_risk = any(severity_rank(f.severity) >= severity_rank(ShadowSeverity.HIGH) for f in findings)
    if has_critical or high_repair:
        verdict = ShadowVerdict.BLOCK_RECOMMENDED
        block = True
    elif needs_repair:
        verdict = ShadowVerdict.REPAIR_REQUIRED
        block = False
    elif high_risk or any(f.kind != ShadowFindingKind.SAFE_CLEAR for f in findings):
        verdict = ShadowVerdict.ADVISORY
        block = False
    else:
        verdict = ShadowVerdict.CLEAR
        block = False
    return ShadowPassResult(
        result_id="pending",
        request_id=context.request_id,
        mode=ShadowMode.DEEP,
        stage=context.stage,
        verdict=verdict,
        findings=findings,
        needs_deep_pass=False,
        needs_repair=needs_repair,
        block_recommended=block,
        created_at=context.created_at,
    ).with_integrity()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _word_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9_#.-]+", value))


def _has_proof_marker(tokens: frozenset[str]) -> bool:
    return bool(tokens.intersection({"approved", "approval", "verified", "receipt", "evidence", "review", "proof"}))
