"""Platform Metrics Collector — Comprehensive Prometheus metrics.

Purpose: Pre-registers and collects metrics across all platform subsystems:
    gateway throughput, governance decisions, LLM invocations, skill execution,
    rate limiting, PII redaction, session lifecycle, provider health.
Governance scope: observability only — read-only metric collection.
Dependencies: PrometheusExporter.
Invariants:
  - All metrics follow Prometheus naming conventions (snake_case, prefixed).
  - Labels are bounded (no unbounded cardinality).
  - Thread-safe — concurrent metric updates from multiple request handlers.
  - Metric collection is lightweight — no blocking I/O.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from mcoi_runtime.core.prometheus_exporter import PrometheusExporter


@dataclass(frozen=True, slots=True)
class LatencyBuckets:
    """Histogram bucket boundaries for latency tracking."""

    boundaries: tuple[float, ...] = (
        50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000,
    )  # milliseconds


class PlatformMetricsCollector:
    """Comprehensive metrics collector for the Mullu platform.

    Registers all platform metrics on init, then provides typed
    recording methods that subsystems call during operation.

    Usage:
        metrics = PlatformMetricsCollector()

        # Gateway
        metrics.record_gateway_message("whatsapp", "success")
        metrics.record_gateway_duplicate("whatsapp")

        # Governance
        metrics.record_governance_decision(allowed=True, guard="rate_limit")
        metrics.record_governance_decision(allowed=False, guard="rbac")

        # LLM
        metrics.record_llm_invocation("anthropic", "claude-sonnet", latency_ms=230, success=True)

        # Export
        print(metrics.export())
    """

    # Allowlists prevent unbounded cardinality from user-supplied values
    ALLOWED_CHANNELS = frozenset({"whatsapp", "telegram", "slack", "discord", "web", "unknown"})
    ALLOWED_PROVIDERS = frozenset({
        "anthropic", "openai", "groq", "gemini", "deepseek",
        "grok", "mistral", "openrouter", "ollama", "stub", "unknown",
    })

    def __init__(self, *, prefix: str = "mullu") -> None:
        self._exporter = PrometheusExporter(prefix=prefix)
        self._lock = threading.Lock()
        self._latency_samples: dict[str, deque[float]] = {}
        self._latency_window = 1000  # Keep last N samples per metric
        self._start_time = time.monotonic()
        self._uptime_override_seconds: float | None = None

        self._register_all()

    @classmethod
    def _sanitize_channel(cls, channel: str) -> str:
        return channel if channel in cls.ALLOWED_CHANNELS else "unknown"

    @classmethod
    def _sanitize_provider(cls, provider: str) -> str:
        return provider if provider in cls.ALLOWED_PROVIDERS else "unknown"

    @staticmethod
    def _require_non_negative_float(value: float, field_name: str) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be a non-negative number")
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < 0.0:
            raise ValueError(f"{field_name} must be a non-negative finite number")
        return numeric

    @classmethod
    def _require_unit_interval(cls, value: float, field_name: str) -> float:
        numeric = cls._require_non_negative_float(value, field_name)
        if numeric > 1.0:
            raise ValueError(f"{field_name} must be within [0.0, 1.0]")
        return numeric

    @staticmethod
    def _require_non_negative_int(value: int, field_name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field_name} must be a non-negative integer")
        return value

    def _register_all(self) -> None:
        e = self._exporter

        # ── Gateway metrics ────────────────────────────────
        e.register_counter("gateway_messages_total", "Total inbound gateway messages")
        e.register_counter("gateway_messages_errors_total", "Gateway message processing errors")
        e.register_counter("gateway_duplicates_total", "Duplicate messages caught by dedup")

        # ── Governance metrics ─────────────────────────────
        e.register_counter("governance_decisions_total", "Total governance guard chain evaluations")
        e.register_counter("governance_decisions_denied_total", "Governance decisions denied")

        # ── Session metrics ────────────────────────────────
        e.register_counter("sessions_created_total", "Total governed sessions created")
        e.register_counter("sessions_closed_total", "Total governed sessions closed")
        e.register_gauge("sessions_active", "Currently active governed sessions")

        # ── LLM metrics ───────────────────────────────────
        e.register_counter("llm_invocations_total", "Total LLM invocations")
        e.register_counter("llm_invocations_errors_total", "Failed LLM invocations")
        e.register_counter("llm_tokens_input_total", "Total LLM input tokens")
        e.register_counter("llm_tokens_output_total", "Total LLM output tokens")
        e.register_counter("llm_cost_total", "Total LLM cost in dollars")

        # ── Rate limiting metrics ──────────────────────────
        e.register_counter("rate_limit_allowed_total", "Rate limit checks that passed")
        e.register_counter("rate_limit_denied_total", "Rate limit checks that denied")

        # ── Budget metrics ─────────────────────────────────
        e.register_counter("budget_checks_total", "Total budget enforcement checks")
        e.register_counter("budget_exhausted_total", "Budget exhaustion events")

        # ── Content safety metrics ─────────────────────────
        e.register_counter("content_safety_checks_total", "Content safety evaluations")
        e.register_counter("content_safety_blocked_total", "Content blocked by safety")

        # ── PII metrics ───────────────────────────────────
        e.register_counter("pii_scans_total", "Total PII scans performed")
        e.register_counter("pii_detections_total", "PII detections (text had PII)")
        e.register_counter("pii_redactions_total", "PII redaction operations")

        # ── Skill execution metrics ────────────────────────
        e.register_counter("skill_executions_total", "Total skill executions")
        e.register_counter("skill_executions_errors_total", "Failed skill executions")

        # ── Approval metrics ───────────────────────────────
        e.register_counter("approvals_requested_total", "Approval requests created")
        e.register_counter("approvals_granted_total", "Approvals granted")
        e.register_counter("approvals_denied_total", "Approvals denied")

        # ── Provider health metrics ────────────────────────
        e.register_gauge("provider_health_score", "Provider health score (0.0-1.0)")
        e.register_gauge("provider_error_rate", "Provider error rate (0.0-1.0)")

        # ── Coordination lock metrics ──────────────────────
        e.register_counter("locks_acquired_total", "Coordination locks acquired")
        e.register_counter("locks_denied_total", "Coordination lock acquisitions denied")
        e.register_counter("locks_expired_total", "Coordination locks expired by TTL")

        # ── Webhook verification metrics ───────────────────
        e.register_counter("webhook_verified_total", "Webhook signatures verified")
        e.register_counter("webhook_rejected_total", "Webhook signatures rejected")

        # ── Audit metrics ──────────────────────────────────
        e.register_counter("audit_entries_total", "Total audit trail entries recorded")
        e.register_gauge("audit_chain_valid", "Audit hash chain integrity (1=valid, 0=broken)")

        # Dashboard exact metric families.
        e.register_gauge("uptime_seconds", "Platform uptime in seconds")
        e.register_gauge("health_score", "Platform health score as a unit ratio")
        e.register_gauge("active_tenants", "Active tenant count")
        e.register_counter("errors_total", "Total platform errors")
        e.register_counter("llm_requests_total", "Total LLM requests")
        e.register_gauge("llm_latency_p99_seconds", "Observed LLM p99 latency in seconds")
        e.register_counter("llm_tokens_total", "Total LLM input and output tokens")
        e.register_gauge("llm_budget_utilization_ratio", "LLM budget utilization as a unit ratio")
        e.register_counter("requests_governed_total", "Total governed requests")
        e.register_counter("policy_violations_total", "Total policy violations")
        e.register_counter("audit_events_total", "Total audit events")
        e.register_gauge("circuit_breaker_open", "Circuit breaker state (1=open, 0=closed)")
        e.register_gauge("active_agents", "Active agent count")
        e.register_counter("tasks_completed_total", "Total completed tasks")
        e.register_gauge("chain_success_rate", "Governance chain success rate as a unit ratio")
        e.register_counter("memory_ops_total", "Total memory operations")

    # ── Gateway recording methods ──────────────────────────

    def record_gateway_message(self, channel: str, outcome: str = "success") -> None:
        channel = self._sanitize_channel(channel)
        self._exporter.inc_counter("gateway_messages_total", channel=channel)
        if outcome == "error":
            self._exporter.inc_counter("gateway_messages_errors_total", channel=channel)
            self.record_error()

    def record_gateway_duplicate(self, channel: str) -> None:
        self._exporter.inc_counter("gateway_duplicates_total", channel=self._sanitize_channel(channel))

    # ── Governance recording methods ───────────────────────

    def record_governance_decision(self, *, allowed: bool, guard: str = "") -> None:
        self._exporter.inc_counter("governance_decisions_total")
        if not allowed:
            self._exporter.inc_counter("governance_decisions_denied_total", guard=guard)
            self.record_policy_violation()

    # ── Session recording methods ──────────────────────────

    def record_session_created(self, tenant_id: str = "") -> None:
        self._exporter.inc_counter("sessions_created_total", tenant_id=tenant_id)

    def record_session_closed(self, tenant_id: str = "") -> None:
        self._exporter.inc_counter("sessions_closed_total", tenant_id=tenant_id)

    def set_active_sessions(self, count: int) -> None:
        self._exporter.set_gauge("sessions_active", float(count))

    # ── Dashboard recording methods ────────────────────────

    def set_platform_health(
        self,
        *,
        uptime_seconds: float | None = None,
        health_score: float,
        active_tenants: int,
    ) -> None:
        """Set dashboard health gauges.

        `health_score` is a unit ratio. Grafana multiplies it by 100 for
        percent display.
        """
        with self._lock:
            if uptime_seconds is not None:
                self._uptime_override_seconds = self._require_non_negative_float(
                    uptime_seconds, "uptime_seconds"
                )
        self._exporter.set_gauge(
            "health_score",
            self._require_unit_interval(health_score, "health_score"),
        )
        self.set_active_tenants(active_tenants)

    def set_active_tenants(self, count: int) -> None:
        count = self._require_non_negative_int(count, "active_tenants")
        self._exporter.set_gauge("active_tenants", float(count))

    def record_error(self) -> None:
        self._exporter.inc_counter("errors_total")

    def record_governed_request(self) -> None:
        self._exporter.inc_counter("requests_governed_total")

    def record_policy_violation(self) -> None:
        self._exporter.inc_counter("policy_violations_total")

    def set_llm_budget_utilization(self, ratio: float) -> None:
        self._exporter.set_gauge(
            "llm_budget_utilization_ratio",
            self._require_unit_interval(ratio, "llm_budget_utilization_ratio"),
        )

    def set_circuit_breaker_open(self, opened: bool) -> None:
        self._exporter.set_gauge("circuit_breaker_open", 1.0 if opened else 0.0)

    def set_active_agents(self, count: int) -> None:
        count = self._require_non_negative_int(count, "active_agents")
        self._exporter.set_gauge("active_agents", float(count))

    def record_task_completed(self) -> None:
        self._exporter.inc_counter("tasks_completed_total")

    def set_chain_success_rate(self, ratio: float) -> None:
        self._exporter.set_gauge(
            "chain_success_rate",
            self._require_unit_interval(ratio, "chain_success_rate"),
        )

    def record_memory_operation(self) -> None:
        self._exporter.inc_counter("memory_ops_total")

    # ── LLM recording methods ──────────────────────────────

    def record_llm_invocation(
        self,
        provider: str,
        model: str,
        *,
        latency_ms: float,
        success: bool,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
    ) -> None:
        latency_ms = self._require_non_negative_float(latency_ms, "latency_ms")
        input_tokens = self._require_non_negative_int(input_tokens, "input_tokens")
        output_tokens = self._require_non_negative_int(output_tokens, "output_tokens")
        provider = self._sanitize_provider(provider)
        self._exporter.inc_counter("llm_invocations_total", provider=provider, model=model)
        self._exporter.inc_counter("llm_requests_total")
        if not success:
            self._exporter.inc_counter("llm_invocations_errors_total", provider=provider, model=model)
            self.record_error()
        if input_tokens > 0:
            self._exporter.inc_counter("llm_tokens_input_total", float(input_tokens), provider=provider)
        if output_tokens > 0:
            self._exporter.inc_counter("llm_tokens_output_total", float(output_tokens), provider=provider)
        token_total = input_tokens + output_tokens
        if token_total > 0:
            self._exporter.inc_counter("llm_tokens_total", float(token_total))
        if cost > 0:
            self._exporter.inc_counter("llm_cost_total", cost, provider=provider)
        self._record_latency("llm", latency_ms)
        p99_seconds = self.latency_summary("llm")["p99"] / 1000.0
        self._exporter.set_gauge("llm_latency_p99_seconds", round(p99_seconds, 6))

    # ── Rate limiting recording ────────────────────────────

    def record_rate_limit(self, *, allowed: bool, tenant_id: str = "") -> None:
        if allowed:
            self._exporter.inc_counter("rate_limit_allowed_total", tenant_id=tenant_id)
        else:
            self._exporter.inc_counter("rate_limit_denied_total", tenant_id=tenant_id)

    # ── Budget recording ───────────────────────────────────

    def record_budget_check(self, *, exhausted: bool, tenant_id: str = "") -> None:
        self._exporter.inc_counter("budget_checks_total", tenant_id=tenant_id)
        if exhausted:
            self._exporter.inc_counter("budget_exhausted_total", tenant_id=tenant_id)

    # ── Content safety recording ───────────────────────────

    def record_content_safety(self, *, blocked: bool) -> None:
        self._exporter.inc_counter("content_safety_checks_total")
        if blocked:
            self._exporter.inc_counter("content_safety_blocked_total")

    # ── PII recording ──────────────────────────────────────

    def record_pii_scan(self, *, detected: bool, redacted: bool = False) -> None:
        self._exporter.inc_counter("pii_scans_total")
        if detected:
            self._exporter.inc_counter("pii_detections_total")
        if redacted:
            self._exporter.inc_counter("pii_redactions_total")

    # ── Skill execution recording ──────────────────────────

    def record_skill_execution(self, skill_name: str, *, success: bool) -> None:
        self._exporter.inc_counter("skill_executions_total", skill=skill_name)
        if not success:
            self._exporter.inc_counter("skill_executions_errors_total", skill=skill_name)
            self.record_error()

    # ── Approval recording ─────────────────────────────────

    def record_approval(self, *, outcome: str) -> None:
        """outcome: 'requested', 'granted', 'denied'"""
        if outcome == "requested":
            self._exporter.inc_counter("approvals_requested_total")
        elif outcome == "granted":
            self._exporter.inc_counter("approvals_granted_total")
        elif outcome == "denied":
            self._exporter.inc_counter("approvals_denied_total")

    # ── Provider health recording ──────────────────────────

    def set_provider_health(self, provider: str, *, score: float, error_rate: float) -> None:
        provider = self._sanitize_provider(provider)
        self._exporter.set_gauge("provider_health_score", score, provider=provider)
        self._exporter.set_gauge("provider_error_rate", error_rate, provider=provider)

    # ── Lock recording ─────────────────────────────────────

    def record_lock(self, *, outcome: str) -> None:
        """outcome: 'acquired', 'denied', 'expired'"""
        if outcome == "acquired":
            self._exporter.inc_counter("locks_acquired_total")
        elif outcome == "denied":
            self._exporter.inc_counter("locks_denied_total")
        elif outcome == "expired":
            self._exporter.inc_counter("locks_expired_total")

    # ── Webhook recording ──────────────────────────────────

    def record_webhook_verification(self, *, verified: bool, channel: str = "") -> None:
        if verified:
            self._exporter.inc_counter("webhook_verified_total", channel=channel)
        else:
            self._exporter.inc_counter("webhook_rejected_total", channel=channel)

    # ── Audit recording ────────────────────────────────────

    def record_audit_entry(self) -> None:
        self._exporter.inc_counter("audit_entries_total")
        self._exporter.inc_counter("audit_events_total")

    def set_audit_chain_valid(self, valid: bool) -> None:
        self._exporter.set_gauge("audit_chain_valid", 1.0 if valid else 0.0)

    # ── Latency tracking (internal) ────────────────────────

    def _record_latency(self, category: str, latency_ms: float) -> None:
        with self._lock:
            if category not in self._latency_samples:
                self._latency_samples[category] = deque(maxlen=self._latency_window)
            self._latency_samples[category].append(latency_ms)

    def latency_summary(self, category: str) -> dict[str, float]:
        """Get latency summary (avg, p50, p95, p99) for a category."""
        with self._lock:
            samples = list(self._latency_samples.get(category, []))
        if not samples:
            return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}
        sorted_s = sorted(samples)
        n = len(sorted_s)

        def _pct(pct: float) -> float:
            rank = max(0, int((pct / 100.0) * n + 0.5) - 1)
            return sorted_s[min(rank, n - 1)]

        return {
            "avg": round(sum(sorted_s) / n, 2),
            "p50": _pct(50),
            "p95": _pct(95),
            "p99": _pct(99),
            "count": n,
        }

    # ── Export ─────────────────────────────────────────────

    def export(self) -> str:
        """Export all metrics in Prometheus text format."""
        with self._lock:
            uptime_seconds = (
                self._uptime_override_seconds
                if self._uptime_override_seconds is not None
                else time.monotonic() - self._start_time
            )
        self._exporter.set_gauge("uptime_seconds", round(uptime_seconds, 3))
        return self._exporter.export()

    def summary(self) -> dict[str, Any]:
        """Summary for health/status endpoints."""
        return {
            **self._exporter.summary(),
            "latency_categories": list(self._latency_samples.keys()),
        }
