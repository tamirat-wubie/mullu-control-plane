"""Purpose: provider-mediated temporal skill plan execution.
Governance scope: temporal workflow stage ordering, explicit provider boundary,
    output validation, terminal-output closure, and fail-closed execution
    receipts.
Dependencies: temporal_runtime contracts and invariant helpers.
Invariants:
  - Stages execute only after predecessor stages pass.
  - Providers cannot silently omit declared outputs.
  - Provider exceptions become failed receipts.
  - Plan execution stops at first failed stage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from mcoi_runtime.contracts.temporal_runtime import (
    TemporalSkillExecutionVerdict,
    TemporalSkillPlan,
    TemporalSkillPlanExecution,
    TemporalSkillStage,
    TemporalSkillStageExecution,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


class TemporalSkillStageProvider(Protocol):
    """Provider boundary for executing one temporal skill plan stage."""

    def execute_stage(
        self,
        plan: TemporalSkillPlan,
        stage: TemporalSkillStage,
        input_values: Mapping[str, Any],
        executed_at: str,
    ) -> Mapping[str, Any]:
        """Return output values for the stage or raise an explicit error."""


class TemporalSkillPlanExecutor:
    """Execute one temporal skill plan through a stage provider."""

    def __init__(self, provider: TemporalSkillStageProvider, *, clock: Any) -> None:
        if provider is None or not hasattr(provider, "execute_stage"):
            raise RuntimeCoreInvariantError("provider must expose execute_stage")
        self._provider = provider
        self._clock = clock

    def execute(self, plan: TemporalSkillPlan, *, schedule_ref: str) -> TemporalSkillPlanExecution:
        """Execute a temporal skill plan and return a bounded execution receipt."""

        if not isinstance(plan, TemporalSkillPlan):
            raise RuntimeCoreInvariantError("plan must be a TemporalSkillPlan")
        if not isinstance(schedule_ref, str) or not schedule_ref.strip():
            raise RuntimeCoreInvariantError("schedule_ref must be non-empty")
        started_at = self._clock_iso()
        stage_outputs: dict[str, Mapping[str, Any]] = {}
        stage_receipts: list[TemporalSkillStageExecution] = []
        for stage in _execution_order(plan):
            executed_at = self._clock_iso()
            try:
                input_values = _stage_input_values(stage, stage_outputs)
            except RuntimeCoreInvariantError as exc:
                receipt = _stage_receipt(
                    plan,
                    stage,
                    schedule_ref,
                    executed_at,
                    TemporalSkillExecutionVerdict.FAIL,
                    str(exc),
                    {},
                    {},
                )
                stage_receipts.append(receipt)
                return _plan_receipt(plan, schedule_ref, started_at, self._clock_iso(), stage_receipts, receipt.verdict, receipt.reason)
            try:
                raw_outputs = self._provider.execute_stage(plan, stage, input_values, executed_at)
            except Exception as exc:  # noqa: BLE001 - provider boundary must emit fail receipt.
                receipt = _stage_receipt(
                    plan,
                    stage,
                    schedule_ref,
                    executed_at,
                    TemporalSkillExecutionVerdict.FAIL,
                    f"stage_provider_error:{type(exc).__name__}",
                    input_values,
                    {},
                )
                stage_receipts.append(receipt)
                return _plan_receipt(plan, schedule_ref, started_at, self._clock_iso(), stage_receipts, receipt.verdict, receipt.reason)
            outputs = dict(raw_outputs)
            missing_outputs = tuple(key for key in stage.output_keys if key not in outputs)
            if missing_outputs:
                receipt = _stage_receipt(
                    plan,
                    stage,
                    schedule_ref,
                    executed_at,
                    TemporalSkillExecutionVerdict.FAIL,
                    "stage_output_missing",
                    input_values,
                    outputs,
                    metadata={"missing_output_keys": missing_outputs},
                )
                stage_receipts.append(receipt)
                return _plan_receipt(plan, schedule_ref, started_at, self._clock_iso(), stage_receipts, receipt.verdict, receipt.reason)
            receipt = _stage_receipt(
                plan,
                stage,
                schedule_ref,
                executed_at,
                TemporalSkillExecutionVerdict.PASS,
                "stage_executed",
                input_values,
                outputs,
            )
            stage_receipts.append(receipt)
            stage_outputs[stage.stage_id] = outputs
        terminal_outputs = _terminal_outputs(plan, stage_outputs)
        if plan.terminal_condition not in terminal_outputs:
            return _plan_receipt(
                plan,
                schedule_ref,
                started_at,
                self._clock_iso(),
                stage_receipts,
                TemporalSkillExecutionVerdict.FAIL,
                "terminal_output_missing",
                terminal_outputs=terminal_outputs,
            )
        return _plan_receipt(
            plan,
            schedule_ref,
            started_at,
            self._clock_iso(),
            stage_receipts,
            TemporalSkillExecutionVerdict.PASS,
            "skill_plan_executed",
            terminal_outputs=terminal_outputs,
        )

    def _clock_iso(self) -> str:
        value = self._clock()
        if isinstance(value, datetime):
            return _iso(value)
        return str(value).replace("+00:00", "Z")


def _execution_order(plan: TemporalSkillPlan) -> tuple[TemporalSkillStage, ...]:
    stages_by_id = {stage.stage_id: stage for stage in plan.stages}
    if len(stages_by_id) != len(plan.stages):
        raise RuntimeCoreInvariantError("duplicate_stage_id")
    ordered: list[TemporalSkillStage] = []
    emitted: set[str] = set()
    while len(ordered) < len(plan.stages):
        progress = False
        for stage in plan.stages:
            if stage.stage_id in emitted:
                continue
            if all(predecessor_id in emitted for predecessor_id in stage.predecessor_ids):
                ordered.append(stage)
                emitted.add(stage.stage_id)
                progress = True
        if not progress:
            raise RuntimeCoreInvariantError("cyclic_stage_dependency")
    return tuple(ordered)


def _stage_input_values(stage: TemporalSkillStage, stage_outputs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for input_name, binding in stage.input_bindings.items():
        values[input_name] = _resolve_input_binding(binding, stage_outputs)
    return values


def _resolve_input_binding(binding: str, stage_outputs: Mapping[str, Mapping[str, Any]]) -> Any:
    if "." in binding:
        source_stage_id, source_key = binding.split(".", 1)
        source_outputs = stage_outputs.get(source_stage_id)
        if source_outputs is None or source_key not in source_outputs:
            raise RuntimeCoreInvariantError("dangling_input_binding")
        return source_outputs[source_key]
    matches = [
        source_outputs[binding]
        for source_outputs in stage_outputs.values()
        if binding in source_outputs
    ]
    if not matches:
        raise RuntimeCoreInvariantError("dangling_input_binding")
    if len(matches) > 1:
        raise RuntimeCoreInvariantError("ambiguous_input_binding")
    return matches[0]


def _terminal_outputs(plan: TemporalSkillPlan, stage_outputs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    for values in stage_outputs.values():
        if plan.terminal_condition in values:
            outputs[plan.terminal_condition] = values[plan.terminal_condition]
    return outputs


def _stage_receipt(
    plan: TemporalSkillPlan,
    stage: TemporalSkillStage,
    schedule_ref: str,
    executed_at: str,
    verdict: TemporalSkillExecutionVerdict,
    reason: str,
    input_values: Mapping[str, Any],
    output_values: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> TemporalSkillStageExecution:
    return TemporalSkillStageExecution(
        execution_id=stable_identifier(
            "temp-skill-stage-exec",
            {
                "schedule": schedule_ref,
                "plan": plan.plan_id,
                "stage": stage.stage_id,
                "verdict": verdict.value,
                "reason": reason,
                "executed_at": executed_at,
            },
        ),
        plan_id=plan.plan_id,
        stage_id=stage.stage_id,
        stage_type=stage.stage_type,
        verdict=verdict,
        reason=reason,
        executed_at=executed_at,
        input_values=input_values,
        output_values=output_values,
        metadata=metadata or {},
    )


def _plan_receipt(
    plan: TemporalSkillPlan,
    schedule_ref: str,
    started_at: str,
    completed_at: str,
    stage_receipts: list[TemporalSkillStageExecution],
    verdict: TemporalSkillExecutionVerdict,
    reason: str,
    *,
    terminal_outputs: Mapping[str, Any] | None = None,
) -> TemporalSkillPlanExecution:
    return TemporalSkillPlanExecution(
        execution_id=stable_identifier(
            "temp-skill-plan-exec",
            {
                "schedule": schedule_ref,
                "plan": plan.plan_id,
                "verdict": verdict.value,
                "reason": reason,
                "completed_at": completed_at,
                "stage_count": str(len(stage_receipts)),
            },
        ),
        schedule_ref=schedule_ref,
        plan_id=plan.plan_id,
        verdict=verdict,
        reason=reason,
        started_at=started_at,
        completed_at=completed_at,
        stage_receipts=tuple(stage_receipts),
        terminal_outputs=terminal_outputs or {},
        metadata={"stage_count": len(stage_receipts)},
    )


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
