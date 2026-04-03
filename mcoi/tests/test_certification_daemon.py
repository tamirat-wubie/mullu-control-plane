"""Phase 200D — Certification daemon tests."""

import pytest
from mcoi_runtime.core.certification_daemon import (
    CertificationConfig,
    CertificationDaemon,
    CertificationHealth,
)
from mcoi_runtime.core.live_path_certification import LivePathCertifier
from mcoi_runtime.adapters.llm_adapter import StubLLMBackend
from mcoi_runtime.contracts.llm import LLMBudget
from mcoi_runtime.core.llm_integration import LLMIntegrationBridge
from mcoi_runtime.persistence.postgres_store import InMemoryStore

import hashlib
import json

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestCertificationConfig:
    def test_defaults(self):
        config = CertificationConfig()
        assert config.interval_seconds == 300.0
        assert config.max_history == 100
        assert config.health_window == 10
        assert config.enabled is True

    def test_custom(self):
        config = CertificationConfig(interval_seconds=60, max_history=50, enabled=False)
        assert config.interval_seconds == 60
        assert config.enabled is False


class TestCertificationHealth:
    def test_initial_health(self):
        health = CertificationHealth()
        assert health.health_score == 1.0
        assert health.is_healthy is True
        assert health.total_runs == 0

    def test_health_after_pass(self):
        health = CertificationHealth(total_runs=5, total_passed=5)
        assert health.health_score == 1.0
        assert health.is_healthy is True

    def test_health_after_failures(self):
        health = CertificationHealth(total_runs=10, total_passed=5, total_failed=5, consecutive_failures=3)
        assert health.health_score == 0.5
        assert health.is_healthy is False

    def test_consecutive_failures_unhealthy(self):
        health = CertificationHealth(total_runs=10, total_passed=9, total_failed=1, consecutive_failures=3)
        assert health.health_score == 0.9
        assert health.is_healthy is False  # 3 consecutive failures


class TestCertificationDaemon:
    def _setup(self, enabled=True, interval=0.0):
        store = InMemoryStore()
        bridge = LLMIntegrationBridge(clock=FIXED_CLOCK, default_backend=StubLLMBackend())
        bridge.register_budget(LLMBudget(budget_id="b1", tenant_id="t1", max_cost=10.0))
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        config = CertificationConfig(enabled=enabled, interval_seconds=interval)

        daemon = CertificationDaemon(
            certifier=certifier,
            clock=FIXED_CLOCK,
            config=config,
            api_handle_fn=lambda req: {"governed": True},
            db_write_fn=lambda t, c: store.append_ledger(
                "cert", "certifier", t, c,
                hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest(),
            ),
            db_read_fn=lambda t: store.query_ledger(t),
            llm_invoke_fn=lambda prompt: bridge.complete(prompt, budget_id="b1"),
            ledger_fn=lambda t: store.query_ledger(t),
            state_fn=lambda: (hashlib.sha256(b"state").hexdigest(), store.ledger_count()),
        )
        return daemon, store, bridge

    def test_tick_runs_certification(self):
        daemon, _, _ = self._setup()
        chain = daemon.tick()
        assert chain is not None
        assert chain.all_passed is True
        assert daemon.health.total_runs == 1
        assert daemon.health.total_passed == 1

    def test_disabled_daemon_skips(self):
        daemon, _, _ = self._setup(enabled=False)
        assert daemon.should_run() is False
        chain = daemon.tick()
        assert chain is None

    def test_should_run_respects_interval(self):
        daemon, _, _ = self._setup(interval=9999.0)
        # First run after tick resets timer
        daemon.tick()
        assert daemon.should_run() is False

    def test_should_run_zero_interval(self):
        daemon, _, _ = self._setup(interval=0.0)
        assert daemon.should_run() is True

    def test_multiple_ticks(self):
        daemon, _, _ = self._setup()
        daemon.tick()
        daemon.tick()
        daemon.tick()
        assert daemon.health.total_runs == 3
        assert daemon.health.total_passed == 3
        assert daemon.health.health_score == 1.0

    def test_force_run_when_disabled(self):
        daemon, _, _ = self._setup(enabled=False)
        chain = daemon.force_run()
        assert chain is not None
        assert chain.all_passed is True
        # Should be disabled again after force_run
        assert daemon.is_enabled is False

    def test_status_report(self):
        daemon, _, _ = self._setup()
        daemon.tick()
        status = daemon.status()
        assert status["enabled"] is True
        assert status["total_runs"] == 1
        assert status["total_passed"] == 1
        assert status["health_score"] == 1.0
        assert status["is_healthy"] is True
        assert status["last_status"] == "passed"

    def test_history_tracked(self):
        daemon, _, _ = self._setup()
        daemon.tick()
        daemon.tick()
        assert len(daemon.history) == 2
        assert all(h["all_passed"] for h in daemon.history)

    def test_history_bounded(self):
        config = CertificationConfig(max_history=3, interval_seconds=0)
        daemon, store, bridge = self._setup()
        daemon._config = config
        for _ in range(5):
            daemon.tick()
        assert len(daemon.history) == 3

    def test_failure_tracking(self):
        store = InMemoryStore()
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        daemon = CertificationDaemon(
            certifier=certifier,
            clock=FIXED_CLOCK,
            config=CertificationConfig(interval_seconds=0),
            api_handle_fn=lambda req: (_ for _ in ()).throw(RuntimeError("api down")),
        )
        daemon.tick()
        assert daemon.health.total_runs == 1
        assert daemon.health.total_failed == 1
        assert daemon.health.consecutive_failures == 1
        assert daemon.health.health_score == 0.0  # 0 passed / 1 total
        assert daemon.health.is_healthy is False  # Below 0.8 threshold

    def test_consecutive_failures_degrade_health(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        daemon = CertificationDaemon(
            certifier=certifier,
            clock=FIXED_CLOCK,
            config=CertificationConfig(interval_seconds=0),
            api_handle_fn=lambda req: (_ for _ in ()).throw(RuntimeError("down")),
        )
        for _ in range(4):
            daemon.tick()
        assert daemon.health.consecutive_failures >= 3
        assert daemon.health.is_healthy is False

    def test_recovery_resets_consecutive(self):
        daemon, _, _ = self._setup()
        # Simulate prior failures
        daemon._health.consecutive_failures = 5
        daemon._health.total_runs = 5
        daemon._health.total_failed = 5
        # Now tick with success
        daemon.tick()
        assert daemon.health.consecutive_failures == 0

    def test_exception_in_tick_caught(self):
        certifier = LivePathCertifier(clock=FIXED_CLOCK)
        daemon = CertificationDaemon(
            certifier=certifier,
            clock=FIXED_CLOCK,
            config=CertificationConfig(interval_seconds=0),
            ledger_fn=lambda tenant_id: (_ for _ in ()).throw(RuntimeError("secret ledger failure")),
        )
        # Should not raise
        chain = daemon.tick()
        assert chain is None
        assert daemon.health.total_runs >= 1
        assert daemon.history[-1]["error"] == "certification run error (RuntimeError)"
        assert "secret ledger failure" not in daemon.history[-1]["error"]
