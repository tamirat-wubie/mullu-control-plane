"""Application integration helpers for InceptaDive Shadow Pass.

Purpose: provide a small dependency-injection boundary for request, planning,
preflight, health, and console posture checks without mounting routes or
executing actions.
Governance scope: feature-flagged advisory/strict inspection only; final verdict
remains owned by Mullu governance.
Dependencies: environment mappings and core shadow modules.
Invariants: disabled mode is explicit, light failures degrade advisory, strict
preflight dependency failures fail closed for high-impact actions, and no helper
executes a candidate action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

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
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


@dataclass(frozen=True)
class InceptaDiveShadowRuntime:
    """Feature-flagged shadow runtime facade."""

    config: ShadowInterrogationConfig
    receipts_enabled: bool = True
    dependency_available: bool = True
    deep_engine_available: bool = False

    def inspect_request(self, context: ShadowContext) -> tuple[ShadowPassResult, ShadowReceipt | None]:
        """Inspect interpretation, planning, or workflow context."""

        decision = decide_shadow_mode(context, self.config)
        if decision.mode == ShadowMode.OFF:
            result = _off_result(context)
        elif decision.mode == ShadowMode.STRICT_PREFLIGHT:
            strict_context = _as_preflight(context)
            result = run_strict_preflight(strict_context)
        else:
            result = run_light_shadow_pass(context)
            if decision.mode == ShadowMode.DEEP and result.verdict not in {
                ShadowVerdict.BLOCK_RECOMMENDED,
                ShadowVerdict.REPAIR_REQUIRED,
            }:
                result = _deep_required_result(context, result)
        receipt = create_shadow_receipt(context, result) if self.receipts_enabled else None
        return result, receipt

    def preflight_action(
        self,
        context: ShadowContext,
        *,
        required_evidence_refs: tuple[str, ...] = (),
    ) -> tuple[ShadowPassResult, ShadowReceipt | None]:
        """Run strict preflight over a candidate action."""

        preflight_context = _as_preflight(context)
        if not self.config.enabled:
            result = _off_result(preflight_context)
        else:
            result = run_strict_preflight(
                preflight_context,
                required_evidence_refs=required_evidence_refs,
            )
        receipt = create_shadow_receipt(preflight_context, result) if self.receipts_enabled else None
        return result, receipt

    def health_posture(
        self,
        *,
        created_at: str = "1970-01-01T00:00:00+00:00",
    ) -> ShadowHealthPosture:
        """Return a redacted read-only shadow health posture snapshot."""

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
        """Return a redacted operator summary from recent result metadata."""

        return build_shadow_console_summary(
            self.config,
            results=results,
            receipts=receipts,
            created_at=created_at,
        )


def build_inceptadive_shadow_runtime(env: Mapping[str, str]) -> InceptaDiveShadowRuntime:
    """Build the shadow runtime from an environment-like mapping."""

    config = ShadowInterrogationConfig(
        enabled=_env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_ENABLED", "1")),
        light_always_on=_env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_LIGHT_ALWAYS_ON", "1")),
        deep_enabled=_env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_DEEP_ENABLED", "1")),
        strict_preflight_enabled=_env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_STRICT_PREFLIGHT", "1")),
        max_findings=_env_int(
            env.get("MULLU_INCEPTADIVE_SHADOW_MAX_FINDINGS", "12"),
            "MULLU_INCEPTADIVE_SHADOW_MAX_FINDINGS",
        ),
        max_depth=_env_int(
            env.get("MULLU_INCEPTADIVE_SHADOW_MAX_DEPTH", "3"),
            "MULLU_INCEPTADIVE_SHADOW_MAX_DEPTH",
        ),
    )
    return InceptaDiveShadowRuntime(
        config=config,
        receipts_enabled=_env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_RECEIPTS_ENABLED", "1")),
        dependency_available=_env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_DEPENDENCY_AVAILABLE", "1")),
        deep_engine_available=_env_flag(env.get("MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE", "0")),
    )


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
        summary="gate selected deep interrogation; deep engine is intentionally not auto-executed in this integration layer",
        constructive_delta=False,
        fracture_delta=True,
        repair_required=True,
        recommended_action="route through the dedicated deep shadow engine before high-impact governance",
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
