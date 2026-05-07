"""Platform Metrics Collector Tests — Comprehensive Prometheus metrics."""

import pytest
from mcoi_runtime.core.platform_metrics import PlatformMetricsCollector


def _metrics():
    return PlatformMetricsCollector()


# ── Gateway metrics ────────────────────────────────────────────

class TestGatewayMetrics:
    def test_message_counter(self):
        m = _metrics()
        m.record_gateway_message("whatsapp")
        m.record_gateway_message("slack")
        m.record_gateway_message("whatsapp")
        export = m.export()
        assert "gateway_messages_total" in export
        assert 'channel="whatsapp"' in export

    def test_error_counter(self):
        m = _metrics()
        m.record_gateway_message("telegram", "error")
        export = m.export()
        assert "gateway_messages_errors_total" in export

    def test_duplicate_counter(self):
        m = _metrics()
        m.record_gateway_duplicate("whatsapp")
        export = m.export()
        assert "gateway_duplicates_total" in export


# ── Governance metrics ─────────────────────────────────────────

class TestGovernanceMetrics:
    def test_decision_allowed(self):
        m = _metrics()
        m.record_governance_decision(allowed=True)
        export = m.export()
        assert "governance_decisions_total" in export

    def test_decision_denied(self):
        m = _metrics()
        m.record_governance_decision(allowed=False, guard="rbac")
        export = m.export()
        assert "governance_decisions_denied_total" in export
        assert 'guard="rbac"' in export


# ── Session metrics ────────────────────────────────────────────

class TestSessionMetrics:
    def test_session_lifecycle(self):
        m = _metrics()
        m.record_session_created("t1")
        m.record_session_created("t1")
        m.record_session_closed("t1")
        m.set_active_sessions(1)
        export = m.export()
        assert "sessions_created_total" in export
        assert "sessions_closed_total" in export
        assert "sessions_active" in export


# ── LLM metrics ───────────────────────────────────────────────

class TestLLMMetrics:
    def test_invocation(self):
        m = _metrics()
        m.record_llm_invocation(
            "anthropic", "claude-sonnet",
            latency_ms=230, success=True,
            input_tokens=100, output_tokens=50, cost=0.01,
        )
        export = m.export()
        assert "llm_invocations_total" in export
        assert 'provider="anthropic"' in export
        assert "llm_tokens_input_total" in export
        assert "llm_cost_total" in export

    def test_invocation_error(self):
        m = _metrics()
        m.record_llm_invocation(
            "openai", "gpt-4", latency_ms=5000, success=False,
        )
        export = m.export()
        assert "llm_invocations_errors_total" in export

    def test_latency_tracked(self):
        m = _metrics()
        for i in range(20):
            m.record_llm_invocation(
                "anthropic", "sonnet",
                latency_ms=100.0 + i * 10, success=True,
            )
        summary = m.latency_summary("llm")
        assert summary["count"] == 20
        assert summary["avg"] > 0
        assert summary["p95"] >= summary["p50"]


# ── Rate limiting metrics ──────────────────────────────────────

class TestRateLimitMetrics:
    def test_rate_limit_allowed(self):
        m = _metrics()
        m.record_rate_limit(allowed=True, tenant_id="t1")
        export = m.export()
        assert "rate_limit_allowed_total" in export

    def test_rate_limit_denied(self):
        m = _metrics()
        m.record_rate_limit(allowed=False, tenant_id="t1")
        export = m.export()
        assert "rate_limit_denied_total" in export


# ── Budget metrics ─────────────────────────────────────────────

class TestBudgetMetrics:
    def test_budget_check(self):
        m = _metrics()
        m.record_budget_check(exhausted=False)
        m.record_budget_check(exhausted=True, tenant_id="t1")
        export = m.export()
        assert "budget_checks_total" in export
        assert "budget_exhausted_total" in export


# ── Content safety metrics ─────────────────────────────────────

class TestContentSafetyMetrics:
    def test_content_safety(self):
        m = _metrics()
        m.record_content_safety(blocked=False)
        m.record_content_safety(blocked=True)
        export = m.export()
        assert "content_safety_checks_total" in export
        assert "content_safety_blocked_total" in export


# ── PII metrics ───────────────────────────────────────────────

class TestPIIMetrics:
    def test_pii_scan(self):
        m = _metrics()
        m.record_pii_scan(detected=False)
        m.record_pii_scan(detected=True, redacted=True)
        export = m.export()
        assert "pii_scans_total" in export
        assert "pii_detections_total" in export
        assert "pii_redactions_total" in export


# ── Skill execution metrics ────────────────────────────────────

class TestSkillMetrics:
    def test_skill_execution(self):
        m = _metrics()
        m.record_skill_execution("payment", success=True)
        m.record_skill_execution("payment", success=False)
        export = m.export()
        assert "skill_executions_total" in export
        assert 'skill="payment"' in export
        assert "skill_executions_errors_total" in export


# ── Approval metrics ───────────────────────────────────────────

class TestApprovalMetrics:
    def test_approval_lifecycle(self):
        m = _metrics()
        m.record_approval(outcome="requested")
        m.record_approval(outcome="granted")
        m.record_approval(outcome="denied")
        export = m.export()
        assert "approvals_requested_total" in export
        assert "approvals_granted_total" in export
        assert "approvals_denied_total" in export


# ── Provider health metrics ────────────────────────────────────

class TestProviderHealthMetrics:
    def test_provider_health(self):
        m = _metrics()
        m.set_provider_health("anthropic", score=0.95, error_rate=0.02)
        m.set_provider_health("openai", score=0.7, error_rate=0.15)
        export = m.export()
        assert "provider_health_score" in export
        assert "provider_error_rate" in export
        assert 'provider="anthropic"' in export
        assert 'provider="openai"' in export


# ── Lock metrics ───────────────────────────────────────────────

class TestLockMetrics:
    def test_lock_outcomes(self):
        m = _metrics()
        m.record_lock(outcome="acquired")
        m.record_lock(outcome="denied")
        m.record_lock(outcome="expired")
        export = m.export()
        assert "locks_acquired_total" in export
        assert "locks_denied_total" in export
        assert "locks_expired_total" in export


# ── Webhook metrics ────────────────────────────────────────────

class TestWebhookMetrics:
    def test_webhook_verification(self):
        m = _metrics()
        m.record_webhook_verification(verified=True, channel="slack")
        m.record_webhook_verification(verified=False, channel="discord")
        export = m.export()
        assert "webhook_verified_total" in export
        assert "webhook_rejected_total" in export


# ── Audit metrics ──────────────────────────────────────────────

class TestAuditMetrics:
    def test_audit_entry(self):
        m = _metrics()
        m.record_audit_entry()
        export = m.export()
        assert "audit_entries_total" in export

    def test_audit_chain_valid(self):
        m = _metrics()
        m.set_audit_chain_valid(True)
        export = m.export()
        assert "audit_chain_valid" in export


# ── Export format ──────────────────────────────────────────────

class TestExportFormat:
    def test_prometheus_format(self):
        m = _metrics()
        m.record_gateway_message("whatsapp")
        export = m.export()
        # Verify Prometheus format: # HELP, # TYPE, metric_name{labels} value
        assert "# HELP" in export
        assert "# TYPE" in export
        assert "mullu_" in export

    def test_export_includes_all_registered(self):
        m = _metrics()
        export = m.export()
        # All registered counters should appear in export even if zero
        assert "gateway_messages_total" in export
        assert "governance_decisions_total" in export
        assert "llm_invocations_total" in export


# ── Latency summary ───────────────────────────────────────────

class TestLatencySummary:
    def test_empty_latency(self):
        m = _metrics()
        s = m.latency_summary("nonexistent")
        assert s["count"] == 0
        assert s["avg"] == 0.0

    def test_latency_percentiles(self):
        m = _metrics()
        for i in range(100):
            m.record_llm_invocation(
                "test", "model", latency_ms=float(i + 1), success=True,
            )
        s = m.latency_summary("llm")
        assert s["count"] == 100
        assert s["p50"] > 0
        assert s["p95"] > s["p50"]
        assert s["p99"] >= s["p95"]


# ── Summary ────────────────────────────────────────────────────

class TestSummary:
    def test_summary_fields(self):
        m = _metrics()
        s = m.summary()
        assert "prefix" in s
        assert "counters" in s
        assert "gauges" in s
        assert "latency_categories" in s
