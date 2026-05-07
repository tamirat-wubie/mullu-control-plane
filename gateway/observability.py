"""Gateway Observability - bounded run traces and production metrics.

Purpose: Records privacy-preserving telemetry for governed gateway runs.
Governance scope: gateway execution observability only.
Dependencies: standard-library dataclasses, collections, and statistics.
Invariants:
  - Raw prompts, response bodies, attachments, and secrets are never stored.
  - Metrics are derived from governed response metadata and command states.
  - Trace retention is bounded to avoid unbounded runtime memory growth.
  - Missing signals are explicit instead of silently represented as healthy.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import ceil
from typing import Any, Deque


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded_text(value: object, *, default: str = "unknown", limit: int = 160) -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text[:limit]


def _bounded_float(value: object, *, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number < 0:
        return default
    return number


def _bounded_int(value: object, *, default: int = 0) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, number)


@dataclass(frozen=True, slots=True)
class GatewayTraceStage:
    """Single named stage in a governed gateway trace."""

    name: str
    status: str = "observed"
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True, slots=True)
class GatewayRunObservation:
    """Privacy-preserving observation for one gateway run."""

    trace_id: str
    message_id: str
    command_id: str
    tenant_id: str
    actor_id: str
    channel: str
    capability_id: str
    risk_class: str
    policy_verdict: str
    approval_verdict: str
    budget_verdict: str
    pii_decision: str
    model_used: str
    tool_used: str
    status: str
    error_type: str
    retry_count: int
    receipt_id: str
    terminal_certificate_id: str
    cost_usd: float
    latency_ms: float
    stages: tuple[GatewayTraceStage, ...]
    missing_signals: tuple[str, ...]
    observed_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "message_id": self.message_id,
            "command_id": self.command_id,
            "tenant_id": self.tenant_id,
            "actor_id": self.actor_id,
            "channel": self.channel,
            "capability_id": self.capability_id,
            "risk_class": self.risk_class,
            "policy_verdict": self.policy_verdict,
            "approval_verdict": self.approval_verdict,
            "budget_verdict": self.budget_verdict,
            "pii_decision": self.pii_decision,
            "model_used": self.model_used,
            "tool_used": self.tool_used,
            "status": self.status,
            "error_type": self.error_type,
            "retry_count": self.retry_count,
            "receipt_id": self.receipt_id,
            "terminal_certificate_id": self.terminal_certificate_id,
            "cost_usd": round(self.cost_usd, 8),
            "latency_ms": round(self.latency_ms, 3),
            "stages": [stage.to_dict() for stage in self.stages],
            "missing_signals": list(self.missing_signals),
            "observed_at": self.observed_at,
        }


class GatewayObservabilityRecorder:
    """Bounded in-memory telemetry recorder for governed gateway execution."""

    def __init__(self, *, max_traces: int = 1000) -> None:
        if max_traces < 1:
            raise ValueError("max_traces must be positive")
        self._max_traces = max_traces
        self._observations: Deque[GatewayRunObservation] = deque(maxlen=max_traces)
        self._latencies_ms: Deque[float] = deque(maxlen=max_traces)
        self._counters: Counter[str] = Counter()
        self._cost_by_tenant: Counter[str] = Counter()
        self._cost_by_capability: Counter[str] = Counter()

    def record(self, observation: GatewayRunObservation) -> GatewayRunObservation:
        """Record one bounded observation and update aggregate metrics."""
        self._observations.append(observation)
        self._latencies_ms.append(observation.latency_ms)
        self._counters["request_count"] += 1
        if observation.policy_verdict == "deny" or observation.error_type in {
            "capability_admission_rejected",
            "approval_context_denied",
            "tenant_not_found",
        }:
            self._counters["policy_denial_count"] += 1
        if observation.approval_verdict in {"pending", "escalate"}:
            self._counters["approval_escalation_count"] += 1
        if observation.status == "error" and observation.tool_used != "none":
            self._counters["tool_failure_count"] += 1
        if observation.capability_id.startswith("payment.") and observation.status == "error":
            self._counters["payment_failure_count"] += 1
        if observation.terminal_certificate_id:
            self._counters["capability_receipt_count"] += 1
        self._counters["retry_count"] += observation.retry_count
        self._counters["missing_signal_count"] += len(observation.missing_signals)
        self._cost_by_tenant[observation.tenant_id] += observation.cost_usd
        self._cost_by_capability[observation.capability_id] += observation.cost_usd
        return observation

    def record_response(
        self,
        *,
        trace_id: str,
        message_id: str,
        command_id: str = "",
        tenant_id: str = "",
        actor_id: str = "",
        channel: str = "",
        capability_id: str = "",
        risk_class: str = "",
        policy_verdict: str = "",
        approval_verdict: str = "",
        budget_verdict: str = "",
        pii_decision: str = "",
        model_used: str = "",
        tool_used: str = "",
        status: str = "",
        error_type: str = "",
        retry_count: int = 0,
        receipt_id: str = "",
        terminal_certificate_id: str = "",
        cost_usd: object = 0.0,
        latency_ms: object = 0.0,
        stage_names: tuple[str, ...] = (),
    ) -> GatewayRunObservation:
        """Create and record one response observation without sensitive payloads."""
        normalized_command_id = _bounded_text(command_id, default="")
        normalized_tenant_id = _bounded_text(tenant_id, default="unresolved")
        normalized_actor_id = _bounded_text(actor_id, default="unresolved")
        normalized_capability_id = _bounded_text(capability_id, default="llm_completion")
        normalized_policy_verdict = _bounded_text(policy_verdict, default="allow")
        normalized_approval_verdict = _bounded_text(approval_verdict, default="not_required")
        normalized_budget_verdict = _bounded_text(budget_verdict, default="not_observed")
        normalized_pii_decision = _bounded_text(pii_decision, default="not_observed")
        normalized_status = _bounded_text(status, default="ok")
        normalized_error = _bounded_text(error_type, default="")
        normalized_tool = _bounded_text(tool_used, default="none")
        normalized_certificate = _bounded_text(terminal_certificate_id, default="")
        stages = tuple(GatewayTraceStage(name=name) for name in stage_names)
        if not stages:
            stages = (GatewayTraceStage(name="request_received"), GatewayTraceStage(name="response_observed"))
        missing_signals = tuple(
            signal
            for signal, value in {
                "budget_verdict": normalized_budget_verdict,
                "pii_decision": normalized_pii_decision,
                "model_used": _bounded_text(model_used, default="not_observed"),
            }.items()
            if value == "not_observed"
        )
        observation = GatewayRunObservation(
            trace_id=_bounded_text(trace_id, default="trace-unavailable"),
            message_id=_bounded_text(message_id, default="message-unavailable"),
            command_id=normalized_command_id,
            tenant_id=normalized_tenant_id,
            actor_id=normalized_actor_id,
            channel=_bounded_text(channel, default="unknown"),
            capability_id=normalized_capability_id,
            risk_class=_bounded_text(risk_class, default="unknown"),
            policy_verdict=normalized_policy_verdict,
            approval_verdict=normalized_approval_verdict,
            budget_verdict=normalized_budget_verdict,
            pii_decision=normalized_pii_decision,
            model_used=_bounded_text(model_used, default="not_observed"),
            tool_used=normalized_tool,
            status=normalized_status,
            error_type=normalized_error,
            retry_count=_bounded_int(retry_count),
            receipt_id=_bounded_text(receipt_id, default=""),
            terminal_certificate_id=normalized_certificate,
            cost_usd=_bounded_float(cost_usd),
            latency_ms=_bounded_float(latency_ms),
            stages=stages,
            missing_signals=missing_signals,
        )
        return self.record(observation)

    def trace(self, trace_id: str) -> dict[str, Any] | None:
        """Return the most recent observation for a trace id."""
        normalized_trace_id = _bounded_text(trace_id, default="")
        for observation in reversed(self._observations):
            if observation.trace_id == normalized_trace_id:
                return observation.to_dict()
        return None

    def snapshot(self, *, command_summary: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return a production metric snapshot derived from recorded runs."""
        command_summary = command_summary or {}
        states = command_summary.get("states", {})
        if not isinstance(states, dict):
            states = {}
        unclosed_action_count = sum(
            int(states.get(state, 0))
            for state in ("allowed", "approved", "pending_approval", "requires_review")
        )
        model_cost_usd = sum(observation.cost_usd for observation in self._observations)
        return {
            "enabled": True,
            "retention_limit": self._max_traces,
            "retained_trace_count": len(self._observations),
            "metrics": {
                "request_count": int(self._counters["request_count"]),
                "policy_denial_count": int(self._counters["policy_denial_count"]),
                "approval_escalation_count": int(self._counters["approval_escalation_count"]),
                "tool_failure_count": int(self._counters["tool_failure_count"]),
                "payment_failure_count": int(self._counters["payment_failure_count"]),
                "p95_latency": round(self._p95_latency_ms(), 3),
                "model_cost_usd": round(model_cost_usd, 8),
                "cost_per_tenant": {
                    key: round(value, 8)
                    for key, value in sorted(self._cost_by_tenant.items())
                },
                "cost_per_capability": {
                    key: round(value, 8)
                    for key, value in sorted(self._cost_by_capability.items())
                },
                "eval_pass_rate": None,
                "capability_receipt_rate": self._ratio(
                    self._counters["capability_receipt_count"],
                    self._counters["request_count"],
                ),
                "unclosed_action_count": unclosed_action_count,
                "retry_count": int(self._counters["retry_count"]),
                "missing_signal_count": int(self._counters["missing_signal_count"]),
            },
            "latest_trace_ids": [observation.trace_id for observation in list(self._observations)[-10:]],
            "missing_signal_policy": "explicit_not_observed",
        }

    def _p95_latency_ms(self) -> float:
        if not self._latencies_ms:
            return 0.0
        sorted_latencies = sorted(self._latencies_ms)
        index = max(0, ceil(0.95 * len(sorted_latencies)) - 1)
        return sorted_latencies[index]

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(float(numerator) / float(denominator), 6)
