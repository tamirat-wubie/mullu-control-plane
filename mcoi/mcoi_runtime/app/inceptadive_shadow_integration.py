"""Application integration helpers for InceptaDive Shadow Pass."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from mcoi_runtime.core.inceptadive_action_taxonomy import classify_shadow_action
from mcoi_runtime.core.inceptadive_deep_engine import run_deep_shadow_pass
from mcoi_runtime.core.inceptadive_external_effect_boundary import (
    ExternalEffectBoundaryAdvisory,
    build_external_effect_boundary_advisory,
)
from mcoi_runtime.core.inceptadive_shadow_gate import decide_shadow_mode
from mcoi_runtime.core.inceptadive_shadow_light import run_light_shadow_pass
from mcoi_runtime.core.inceptadive_shadow_posture import (
    ShadowConsoleSummary,
    ShadowHealthPosture,
    build_shadow_console_summary,
    build_shadow_health_posture,
)
from mcoi_runtime.core.inceptadive_shadow_preflight import run_strict_preflight
from mcoi_runtime.core.inceptadive_shadow_receipt import create_shadow_receipt
from mcoi_runtime.core.inceptadive_shadow_receipt_store import (
    InMemoryShadowReceiptStore,
    JsonlShadowReceiptStore,
    ShadowReceiptStore,
)
from mcoi_runtime.core.inceptadive_shadow_types import (
    ShadowContext,
    ShadowFinding,
    ShadowFindingKind,
    ShadowInterrogationConfig,
    ShadowMode,
    ShadowPassResult,
    ShadowReceipt,
    ShadowSeverity,
    ShadowStage,
    ShadowVerdict,
    severity_rank,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


@dataclass(frozen=True)
class InceptaDiveShadowRuntime:
    """Feature-flagged shadow runtime facade."""

    config: ShadowInterrogationConfig
    receipts_enabled: bool = True
    dependency_available: bool = True
    deep_engine_available: bool = False
    receipt_store: ShadowReceiptStore | None = None

    def inspect_request(self, context: ShadowContext) -> tuple[ShadowPassResult, ShadowReceipt | None]:
        decision = decide_shadow_mode(context, self.config)
        if decision.mode == ShadowMode.OFF:
            result = _off_result(context)
        elif decision.mode == ShadowMode.STRICT_PREFLIGHT:
            result = run_strict_preflight(_as_preflight(context))
        elif decision.mode == ShadowMode.DEEP and self.deep_engine_available:
            result = run_deep_shadow_pass(
                context,
                max_depth=self.config.max_depth,
                max_findings=self.config.max_findings,
            )
        elif decision.mode == ShadowMode.DEEP:
            light = run_light_shadow_pass(context)
            result = light if light.verdict in {ShadowVerdict.BLOCK_RECOMMENDED, ShadowVerdict.REPAIR_REQUIRED} else _deep_required_result(context, light)
        else:
            result = run_light_shadow_pass(context)
        receipt = create_shadow_receipt(context, result) if self.receipts_enabled else None
        self._record(result, receipt)
        return result, receipt

    def preflight_action(
        self,
        context: ShadowContext,
        *,
        required_evidence_refs: tuple[str, ...] = (),
    ) -> tuple[ShadowPassResult, ShadowReceipt | None]:
        preflight_context = _as_preflight(context)
        if not self.config.enabled:
            result = _off_result(preflight_context)
        else:
            strict_result = run_strict_preflight(
                preflight_context,
                required_evidence_refs=required_evidence_refs,
            )
            result = _with_external_effect_deep_advisory(
                preflight_context,
                strict_result,
                config=self.config,
                deep_engine_available=self.deep_engine_available,
            )
        receipt = create_shadow_receipt(preflight_context, result) if self.receipts_enabled else None
        self._record(result, receipt)
        return result, receipt

    def external_effect_advisory(
        self,
        context: ShadowContext,
        *,
        required_evidence_refs: tuple[str, ...] = (),
        authority_receipt_refs: tuple[str, ...] = (),
    ) -> ExternalEffectBoundaryAdvisory:
        """Return redacted obligations for an effect-bearing candidate action."""

        advisory = build_external_effect_boundary_advisory(
            _as_preflight(context),
            required_evidence_refs=required_evidence_refs,
            authority_receipt_refs=authority_receipt_refs,
        )
        if self.receipt_store is not None:
            self.receipt_store.append_external_effect_advisory(advisory)
        return advisory

    def health_posture(
        self,
        *,
        created_at: str = "1970-01-01T00:00:00+00:00",
    ) -> ShadowHealthPosture:
        return build_shadow_health_posture(
            self.config,
            receipts_enabled=self.receipts_enabled,
            dependency_available=self.dependency_available,
            deep_engine_available=self.deep_engine_available,
            created_at=created_at,
        )

    def console_summary(
        self,
        *,
        results: Sequence[ShadowPassResult] = (),
        receipts: Sequence[ShadowReceipt] = (),
        created_at: str = "1970-01-01T00:00:00+00:00",
    ) -> ShadowConsoleSummary:
        result_tuple = tuple(results)
        receipt_tuple = tuple(receipts)
        if not result_tuple and self.receipt_store is not None:
            result_tuple = self.receipt_store.recent_results(limit=self.config.max_findings)
        if not receipt_tuple and self.receipt_store is not None:
            receipt_tuple = self.receipt_store.recent_receipts(limit=self.config.max_findings)
        return build_shadow_console_summary(
            self.config,
            results=result_tuple,
            receipts=receipt_tuple,
            created_at=created_at,
        )

    def recent_activity(self, *, limit: int = 25) -> tuple[tuple[ShadowPassResult, ...], tuple[ShadowReceipt, ...]]:
        if self.receipt_store is None:
            return (), ()
        return self.receipt_store.recent_results(limit=limit), self.receipt_store.recent_receipts(limit=limit)

    def recent_external_effect_advisories(self, *, limit: int = 25) -> tuple[ExternalEffectBoundaryAdvisory, ...]:
        if self.receipt_store is None:
            return ()
        return self.receipt_store.recent_external_effect_advisories(limit=limit)

    def _record(self, result: ShadowPassResult, receipt: ShadowReceipt | None) -> None:
        if self.receipt_store is None:
            return
        self.receipt_store.append_result(result)
        if receipt is not None:
            self.receipt_store.append_receipt(receipt)


def build_inceptadive_shadow_runtime(env: Mapping[str, str]) -> InceptaDiveShadowRuntime:
    config = ShadowInterrogationConfig(
        enabled=_env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_ENABLED", "1")),
        light_always_on=_env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_LIGHT_ALWAYS_ON", "1")),
        deep_enabled=_env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_DEEP_ENABLED", "1")),
        strict_preflight_enabled=_env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_STRICT_PREFLIGHT", "1")),
        max_findings=_env_int(env.get("MULLU_INCEPTADIVE_SHADOW_MAX_FINDINGS", "12"), "MULLU_INCEPTADIVE_SHADOW_MAX_FINDINGS"),
        max_depth=_env_int(env.get("MULLU_INCEPTADIVE_SHADOW_MAX_DEPTH", "3"), "MULLU_INCEPTADIVE_SHADOW_MAX_DEPTH"),
    )
    return InceptaDiveShadowRuntime(
        config=config,
        receipts_enabled=_env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_RECEIPTS_ENABLED", "1")),
        dependency_available=_env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_DEPENDENCY_AVAILABLE", "1")),
        deep_engine_available=_env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE", "0")),
        receipt_store=select_shadow_receipt_store(env),
    )


def select_shadow_receipt_store(env: Mapping[str, str]) -> ShadowReceiptStore | None:
    if not _env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_STORE_ENABLED", "1")):
        return None
    max_items = _env_int(env.get("MULLU_INCEPTADIVE_SHADOW_STORE_MAX_ITEMS", "200"), "MULLU_INCEPTADIVE_SHADOW_STORE_MAX_ITEMS")
    store_path = str(env.get("MULLU_INCEPTADIVE_SHADOW_STORE_PATH", "") or "").strip()
    if store_path:
        return JsonlShadowReceiptStore(Path(store_path), max_items=max_items)
    return InMemoryShadowReceiptStore(max_items=max_items)


def _off_result(context: ShadowContext) -> ShadowPassResult:
    finding = ShadowFinding.create(
        request_id=context.request_id,
        stage=context.stage,
        kind=ShadowFindingKind.SAFE_CLEAR,
        severity=ShadowSeverity.INFO,
        summary="InceptaDive Shadow Pass is disabled by policy",
        constructive_delta=True,
        recommended_action="continue without shadow advisory only if governance policy permits",
        created_at=context.created_at,
    )
    return ShadowPassResult(
        result_id="pending",
        request_id=context.request_id,
        mode=ShadowMode.OFF,
        stage=context.stage,
        verdict=ShadowVerdict.CLEAR,
        findings=(finding,),
        created_at=context.created_at,
    ).with_integrity()


def _deep_required_result(context: ShadowContext, light_result: ShadowPassResult) -> ShadowPassResult:
    finding = ShadowFinding.create(
        request_id=context.request_id,
        stage=context.stage,
        kind=ShadowFindingKind.REPAIR_REQUIRED,
        severity=ShadowSeverity.MEDIUM,
        summary="gate selected deep interrogation; deep engine is unavailable in this runtime posture",
        fracture_delta=True,
        repair_required=True,
        recommended_action="enable bounded deep shadow or route through dedicated deep review before governance",
        created_at=context.created_at,
    )
    return ShadowPassResult(
        result_id="pending",
        request_id=context.request_id,
        mode=ShadowMode.DEEP,
        stage=context.stage,
        verdict=ShadowVerdict.DEEP_REQUIRED,
        findings=light_result.findings + (finding,),
        needs_deep_pass=True,
        needs_repair=light_result.needs_repair,
        block_recommended=light_result.block_recommended,
        created_at=context.created_at,
    ).with_integrity()


def _with_external_effect_deep_advisory(
    context: ShadowContext,
    strict_result: ShadowPassResult,
    *,
    config: ShadowInterrogationConfig,
    deep_engine_available: bool,
) -> ShadowPassResult:
    if not deep_engine_available or not config.deep_enabled or not _preflight_needs_deep_advisory(context):
        return strict_result

    deep_result = run_deep_shadow_pass(
        context,
        max_depth=config.max_depth,
        max_findings=config.max_findings,
    )
    remaining = max(config.max_findings - len(strict_result.findings), 0)
    if remaining < 1:
        return strict_result
    merged_findings = strict_result.findings + deep_result.findings[:remaining]
    if merged_findings == strict_result.findings:
        return strict_result
    return _preflight_result_from_findings(context, merged_findings)


def _preflight_needs_deep_advisory(context: ShadowContext) -> bool:
    classification = classify_shadow_action(context)
    return bool(
        classification.deep_interrogation_required
        or context.external_side_effect
        or context.memory_contradiction
        or severity_rank(context.risk_level) >= severity_rank(ShadowSeverity.HIGH)
    )


def _preflight_result_from_findings(
    context: ShadowContext,
    findings: tuple[ShadowFinding, ...],
) -> ShadowPassResult:
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
        stage=ShadowStage.PREFLIGHT,
        verdict=verdict,
        findings=findings,
        needs_repair=needs_repair,
        needs_escalation=needs_escalation,
        block_recommended=block_recommended,
        created_at=context.created_at,
    ).with_integrity()


def _as_preflight(context: ShadowContext) -> ShadowContext:
    return ShadowContext(
        request_id=context.request_id,
        stage=ShadowStage.PREFLIGHT,
        user_input=context.user_input,
        normal_intent=context.normal_intent,
        normal_plan=context.normal_plan,
        candidate_action=context.candidate_action or context.user_input,
        explicit_target=context.explicit_target,
        scope=context.scope,
        risk_level=context.risk_level,
        external_side_effect=context.external_side_effect,
        memory_contradiction=context.memory_contradiction,
        retrieval_receipt_ids=context.retrieval_receipt_ids,
        created_at=context.created_at,
    ).with_integrity()


def _env_flag(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(value: str, env_name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeCoreInvariantError(env_name + " must be an integer") from exc
    if parsed < 1:
        raise RuntimeCoreInvariantError(env_name + " must be positive")
    return parsed
