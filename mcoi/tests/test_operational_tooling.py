"""Operational Tooling Tests — Replay, dashboard, onboarding."""

from gateway.event_log import WebhookEventLog
from gateway.webhook_replay import WebhookReplayEngine
from mcoi_runtime.core.ops_dashboard import OpsDashboard
from mcoi_runtime.core.tenant_onboarding import OnboardingRequest, TenantOnboarding


# ── Webhook Replay ─────────────────────────────────────────────

class TestWebhookReplay:
    def _setup(self):
        log = WebhookEventLog(clock=lambda: "2026-04-07T12:00:00Z")
        log.record(channel="wa", sender_id="+1", message_id="m1", body="hello", status="error", outcome_detail="timeout")
        log.record(channel="wa", sender_id="+2", message_id="m2", body="world", status="processed")
        engine = WebhookReplayEngine(event_log=log, clock=lambda: "2026-04-07T13:00:00Z")
        return log, engine

    def test_replay_failed_event(self):
        log, engine = self._setup()
        result = engine.replay_event("evt-1", processor=lambda c, s, b: "success")
        assert result.replay_status == "success"
        assert result.original_status == "error"

    def test_replay_skips_processed(self):
        log, engine = self._setup()
        result = engine.replay_event("evt-2")
        assert result.replay_status == "skipped"
        assert "already processed" in result.detail

    def test_replay_nonexistent(self):
        _, engine = self._setup()
        result = engine.replay_event("evt-999")
        assert result.replay_status == "skipped"
        assert "not found" in result.detail

    def test_replay_processor_failure(self):
        log, engine = self._setup()
        def bad_processor(c, s, b):
            raise ConnectionError("down")
        result = engine.replay_event("evt-1", processor=bad_processor)
        assert result.replay_status == "failed"
        assert "ConnectionError" in result.detail

    def test_replay_failed_batch(self):
        log, engine = self._setup()
        batch = engine.replay_failed(channel="wa", processor=lambda c, s, b: "success")
        assert batch.total == 1  # Only 1 error event
        assert batch.succeeded == 1

    def test_replay_records_to_event_log(self):
        log, engine = self._setup()
        engine.replay_event("evt-1", processor=lambda c, s, b: "success")
        # Should have a new event with "replayed:success" status
        events = log.query(status="replayed:success")
        assert len(events) == 1

    def test_summary(self):
        _, engine = self._setup()
        engine.replay_event("evt-1", processor=lambda c, s, b: "success")
        s = engine.summary()
        assert s["total_replays"] == 1
        assert s["succeeded"] == 1
        assert s["skipped"] == 0

    def test_summary_counts_skipped_replay_reasons(self):
        _, engine = self._setup()
        missing = engine.replay_event("evt-999")
        processed = engine.replay_event("evt-2")
        s = engine.summary()

        assert missing.replay_status == "skipped"
        assert processed.replay_status == "skipped"
        assert s["total_replays"] == 0
        assert s["skipped"] == 2
        assert s["skip_reasons"] == {
            "already_processed": 1,
            "event_not_found": 1,
        }
        assert "evt-999" not in s["skip_reasons"]

    def test_batch_to_dict(self):
        _, engine = self._setup()
        batch = engine.replay_failed(processor=lambda c, s, b: "success")
        d = batch.to_dict()
        assert "total" in d
        assert "succeeded" in d


# ── Ops Dashboard ──────────────────────────────────────────────

class TestOpsDashboard:
    def test_all_healthy(self):
        dash = OpsDashboard(clock=lambda: "2026-04-07T12:00:00Z")
        dash.register("subsys_a", lambda: {"status": "ok"})
        dash.register("subsys_b", lambda: {"status": "ok"})
        snapshot = dash.snapshot()
        assert snapshot.overall_status == "healthy"
        assert snapshot.healthy_count == 2

    def test_degraded_detection(self):
        dash = OpsDashboard(clock=lambda: "now")
        dash.register("good", lambda: {}, health_rule=lambda d: "healthy")
        dash.register("slow", lambda: {}, health_rule=lambda d: "degraded")
        snapshot = dash.snapshot()
        assert snapshot.overall_status == "degraded"
        assert snapshot.degraded_count == 1

    def test_unhealthy_detection(self):
        dash = OpsDashboard(clock=lambda: "now")
        dash.register("good", lambda: {}, health_rule=lambda d: "healthy")
        dash.register("down", lambda: {}, health_rule=lambda d: "unhealthy")
        snapshot = dash.snapshot()
        assert snapshot.overall_status == "unhealthy"

    def test_check_exception_is_unhealthy(self):
        dash = OpsDashboard(clock=lambda: "now")
        dash.register("broken", lambda: (_ for _ in ()).throw(RuntimeError("crash")))
        snapshot = dash.snapshot()
        assert snapshot.subsystems[0].status == "unhealthy"

    def test_empty_dashboard(self):
        dash = OpsDashboard(clock=lambda: "now")
        snapshot = dash.snapshot()
        assert snapshot.overall_status == "unknown"

    def test_to_dict(self):
        dash = OpsDashboard(clock=lambda: "now", platform_version="3.15.0")
        dash.register("test", lambda: {"x": 1})
        d = dash.snapshot().to_dict()
        assert "overall_status" in d
        assert "subsystems" in d
        assert len(d["subsystems"]) == 1

    def test_unregister(self):
        dash = OpsDashboard(clock=lambda: "now")
        dash.register("test", lambda: {})
        assert dash.unregister("test") is True
        assert dash.subsystem_count == 0

    def test_list_subsystems(self):
        dash = OpsDashboard(clock=lambda: "now")
        dash.register("b", lambda: {})
        dash.register("a", lambda: {})
        assert dash.list_subsystems() == ["a", "b"]


# ── Tenant Onboarding ─────────────────────────────────────────

class TestTenantOnboarding:
    def test_successful_onboarding(self):
        onb = TenantOnboarding(clock=lambda: "2026-04-07T12:00:00Z")
        onb.register_step("create_budget", lambda r: f"budget for {r.tenant_id}")
        onb.register_step("assign_plan", lambda r: f"plan: {r.plan}")
        result = onb.onboard(OnboardingRequest(tenant_id="t1", tenant_name="Acme", plan="pro"))
        assert result.success is True
        assert len(result.steps) == 2
        assert result.steps[0].status == "completed"
        assert result.steps[1].status == "completed"

    def test_failed_step_cascades(self):
        onb = TenantOnboarding(clock=lambda: "now")
        onb.register_step("step1", lambda r: "ok")
        onb.register_step("step2", lambda r: (_ for _ in ()).throw(RuntimeError("db down")))
        onb.register_step("step3", lambda r: "ok")
        result = onb.onboard(OnboardingRequest(tenant_id="t1", tenant_name="X"))
        assert result.success is False
        assert result.steps[0].status == "completed"
        assert result.steps[1].status == "failed"
        assert result.steps[2].status == "skipped"

    def test_duplicate_onboarding_rejected(self):
        onb = TenantOnboarding(clock=lambda: "now")
        onb.register_step("step1", lambda r: "ok")
        onb.onboard(OnboardingRequest(tenant_id="t1", tenant_name="X"))
        result = onb.onboard(OnboardingRequest(tenant_id="t1", tenant_name="X"))
        assert result.success is False
        assert "already onboarded" in result.error

    def test_failed_onboarding_can_retry(self):
        call_count = [0]
        onb = TenantOnboarding(clock=lambda: "now")
        def flaky(r):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("first time fails")
            return "ok"
        onb.register_step("step1", flaky)
        r1 = onb.onboard(OnboardingRequest(tenant_id="t1", tenant_name="X"))
        assert r1.success is False
        r2 = onb.onboard(OnboardingRequest(tenant_id="t1", tenant_name="X"))
        assert r2.success is True

    def test_is_onboarded(self):
        onb = TenantOnboarding(clock=lambda: "now")
        onb.register_step("step1", lambda r: "ok")
        assert onb.is_onboarded("t1") is False
        onb.onboard(OnboardingRequest(tenant_id="t1", tenant_name="X"))
        assert onb.is_onboarded("t1") is True

    def test_get_result(self):
        onb = TenantOnboarding(clock=lambda: "now")
        onb.register_step("step1", lambda r: "ok")
        onb.onboard(OnboardingRequest(tenant_id="t1", tenant_name="X"))
        result = onb.get_result("t1")
        assert result is not None
        assert result.success is True

    def test_to_dict(self):
        onb = TenantOnboarding(clock=lambda: "now")
        onb.register_step("step1", lambda r: "ok")
        result = onb.onboard(OnboardingRequest(tenant_id="t1", tenant_name="X"))
        d = result.to_dict()
        assert d["tenant_id"] == "t1"
        assert d["success"] is True
        assert len(d["steps"]) == 1

    def test_summary(self):
        onb = TenantOnboarding(clock=lambda: "now")
        onb.register_step("step1", lambda r: "ok")
        onb.onboard(OnboardingRequest(tenant_id="t1", tenant_name="X"))
        s = onb.summary()
        assert s["total_onboarded"] == 1
        assert s["registered_steps"] == 1

    def test_no_steps(self):
        onb = TenantOnboarding(clock=lambda: "now")
        result = onb.onboard(OnboardingRequest(tenant_id="t1", tenant_name="X"))
        assert result.success is True
        assert len(result.steps) == 0
