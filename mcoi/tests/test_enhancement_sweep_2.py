"""Enhancement Sweep 2 Tests — Analytics, retry policies, agent capabilities."""

import pytest


# ── Request Analytics ──────────────────────────────────────────

class TestRequestAnalytics:
    def _analytics(self):
        from mcoi_runtime.core.request_analytics import RequestAnalytics
        return RequestAnalytics(clock=lambda: 0.0)

    def test_record_and_report(self):
        a = self._analytics()
        a.record("/api/v1/llm", latency_ms=200, success=True)
        a.record("/api/v1/llm", latency_ms=300, success=True)
        report = a.endpoint_report("/api/v1/llm")
        assert report is not None
        assert report.request_count == 2
        assert report.avg_latency_ms == 250.0

    def test_error_tracking(self):
        a = self._analytics()
        a.record("/api", latency_ms=100, success=True)
        a.record("/api", latency_ms=500, success=False, status_code=500)
        report = a.endpoint_report("/api")
        assert report.error_count == 1
        assert report.error_rate == 0.5

    def test_percentiles(self):
        a = self._analytics()
        for i in range(100):
            a.record("/api", latency_ms=float(i + 1), success=True)
        report = a.endpoint_report("/api")
        assert report.p50_latency_ms > 0
        assert report.p95_latency_ms > report.p50_latency_ms
        assert report.p99_latency_ms >= report.p95_latency_ms

    def test_all_endpoints(self):
        a = self._analytics()
        a.record("/api/a", latency_ms=100, success=True)
        a.record("/api/b", latency_ms=200, success=True)
        reports = a.all_endpoints()
        assert len(reports) == 2

    def test_slow_endpoints(self):
        a = self._analytics()
        a.record("/fast", latency_ms=50, success=True)
        a.record("/slow", latency_ms=5000, success=True)
        slow = a.slow_endpoints(threshold_ms=1000)
        assert len(slow) == 1
        assert slow[0].endpoint == "/slow"

    def test_error_endpoints(self):
        a = self._analytics()
        a.record("/good", latency_ms=100, success=True)
        a.record("/bad", latency_ms=100, success=False)
        errs = a.error_endpoints(threshold=0.5)
        assert len(errs) == 1

    def test_unknown_endpoint(self):
        a = self._analytics()
        assert a.endpoint_report("/nonexistent") is None

    def test_to_dict(self):
        a = self._analytics()
        a.record("/api", latency_ms=100, success=True)
        d = a.endpoint_report("/api").to_dict()
        assert "endpoint" in d
        assert "avg_latency_ms" in d
        assert "throughput_rps" in d

    def test_summary(self):
        a = self._analytics()
        a.record("/api", latency_ms=100, success=True)
        s = a.summary()
        assert s["endpoints_tracked"] == 1
        assert s["total_requests"] == 1


# ── Retry Policies ─────────────────────────────────────────────

class TestRetryPolicy:
    def test_delay_for_attempt(self):
        from gateway.retry_policy import RetryPolicy
        p = RetryPolicy(base_delay_seconds=1.0, backoff_factor=2.0, jitter=False)
        assert p.delay_for_attempt(0) == 1.0
        assert p.delay_for_attempt(1) == 2.0
        assert p.delay_for_attempt(2) == 4.0

    def test_max_delay_cap(self):
        from gateway.retry_policy import RetryPolicy
        p = RetryPolicy(base_delay_seconds=1.0, backoff_factor=10.0, max_delay_seconds=5.0, jitter=False)
        assert p.delay_for_attempt(5) == 5.0

    def test_should_retry(self):
        from gateway.retry_policy import RetryPolicy
        p = RetryPolicy(max_retries=3)
        assert p.should_retry(0) is True
        assert p.should_retry(2) is True
        assert p.should_retry(3) is False

    def test_should_retry_status(self):
        from gateway.retry_policy import RetryPolicy
        p = RetryPolicy(retry_on_status=frozenset({500}))
        assert p.should_retry(0, status_code=500) is True
        assert p.should_retry(0, status_code=400) is False

    def test_jitter(self):
        from gateway.retry_policy import RetryPolicy
        p = RetryPolicy(base_delay_seconds=1.0, jitter=True)
        delays = {p.delay_for_attempt(0) for _ in range(10)}
        assert len(delays) > 1  # Jitter produces variation

    def test_predefined_policies(self):
        from gateway.retry_policy import CHANNEL_POLICIES
        assert "whatsapp" in CHANNEL_POLICIES
        assert "slack" in CHANNEL_POLICIES
        assert "discord" in CHANNEL_POLICIES

    def test_registry(self):
        from gateway.retry_policy import RetryPolicyRegistry
        r = RetryPolicyRegistry()
        p = r.get("whatsapp")
        assert p.max_retries == 5
        p_default = r.get("unknown_channel")
        assert p_default.max_retries == 3

    def test_registry_custom(self):
        from gateway.retry_policy import RetryPolicy, RetryPolicyRegistry
        r = RetryPolicyRegistry()
        r.set("custom", RetryPolicy(max_retries=10))
        assert r.get("custom").max_retries == 10

    def test_registry_summary(self):
        from gateway.retry_policy import RetryPolicyRegistry
        s = RetryPolicyRegistry().summary()
        assert "channels" in s
        assert "whatsapp" in s["channels"]


# ── Agent Capabilities ─────────────────────────────────────────

class TestAgentCapabilities:
    def _registry(self):
        from mcoi_runtime.core.agent_capabilities import AgentCapabilityRegistry, AgentCapability
        r = AgentCapabilityRegistry()
        r.register_capability(AgentCapability(name="finance", description="Financial analysis"))
        r.register_capability(AgentCapability(name="reports", description="Report generation"))
        r.register_capability(AgentCapability(name="email", description="Send emails"))
        return r

    def test_register_agent(self):
        from mcoi_runtime.core.agent_capabilities import AgentProfile
        r = self._registry()
        r.register_agent(AgentProfile(
            agent_id="a1", tenant_id="t1", name="Finance Bot",
            capabilities=frozenset({"finance", "reports"}),
        ))
        assert r.agent_count == 1

    def test_unknown_capability_rejected(self):
        from mcoi_runtime.core.agent_capabilities import AgentProfile
        r = self._registry()
        with pytest.raises(ValueError, match="unknown"):
            r.register_agent(AgentProfile(
                agent_id="a1", tenant_id="t1", name="Bad",
                capabilities=frozenset({"nonexistent"}),
            ))

    def test_find_by_capability(self):
        from mcoi_runtime.core.agent_capabilities import AgentProfile
        r = self._registry()
        r.register_agent(AgentProfile(
            agent_id="a1", tenant_id="t1", name="Finance", capabilities=frozenset({"finance"}),
        ))
        r.register_agent(AgentProfile(
            agent_id="a2", tenant_id="t1", name="Email", capabilities=frozenset({"email"}),
        ))
        agents = r.find_agents_with_capability("finance", "t1")
        assert len(agents) == 1
        assert agents[0].agent_id == "a1"

    def test_find_for_task(self):
        from mcoi_runtime.core.agent_capabilities import AgentProfile
        r = self._registry()
        r.register_agent(AgentProfile(
            agent_id="a1", tenant_id="t1", name="Full",
            capabilities=frozenset({"finance", "reports", "email"}),
        ))
        r.register_agent(AgentProfile(
            agent_id="a2", tenant_id="t1", name="Partial",
            capabilities=frozenset({"finance"}),
        ))
        agent = r.find_agent_for_task(frozenset({"finance", "reports"}), "t1")
        assert agent is not None
        assert agent.agent_id == "a1"

    def test_find_no_match(self):
        r = self._registry()
        assert r.find_agent_for_task(frozenset({"finance"}), "t1") is None

    def test_tenant_isolation(self):
        from mcoi_runtime.core.agent_capabilities import AgentProfile
        r = self._registry()
        r.register_agent(AgentProfile(
            agent_id="a1", tenant_id="t1", name="T1", capabilities=frozenset({"finance"}),
        ))
        assert len(r.find_agents_with_capability("finance", "t2")) == 0

    def test_disable_agent(self):
        from mcoi_runtime.core.agent_capabilities import AgentProfile
        r = self._registry()
        r.register_agent(AgentProfile(
            agent_id="a1", tenant_id="t1", name="Bot", capabilities=frozenset({"finance"}),
        ))
        assert r.disable_agent("a1") is True
        assert len(r.find_agents_with_capability("finance", "t1", enabled_only=True)) == 0

    def test_unregister(self):
        from mcoi_runtime.core.agent_capabilities import AgentProfile
        r = self._registry()
        r.register_agent(AgentProfile(
            agent_id="a1", tenant_id="t1", name="Bot", capabilities=frozenset({"finance"}),
        ))
        assert r.unregister_agent("a1") is True
        assert r.agent_count == 0

    def test_has_capability(self):
        from mcoi_runtime.core.agent_capabilities import AgentProfile
        p = AgentProfile(agent_id="a1", tenant_id="t1", name="Bot",
                         capabilities=frozenset({"finance", "reports"}))
        assert p.has_capability("finance") is True
        assert p.has_capability("email") is False

    def test_to_dict(self):
        from mcoi_runtime.core.agent_capabilities import AgentProfile
        p = AgentProfile(agent_id="a1", tenant_id="t1", name="Bot",
                         capabilities=frozenset({"finance"}))
        d = p.to_dict()
        assert d["agent_id"] == "a1"
        assert "finance" in d["capabilities"]

    def test_summary(self):
        from mcoi_runtime.core.agent_capabilities import AgentProfile
        r = self._registry()
        r.register_agent(AgentProfile(
            agent_id="a1", tenant_id="t1", name="Bot", capabilities=frozenset({"finance"}),
        ))
        s = r.summary()
        assert s["capabilities"] == 3
        assert s["agents"] == 1
