"""Purpose: bind certification daemon lifecycle witnesses to exact anchors.
Governance scope: daemon status, interval-gated ticks, forced runs, bounded
    health/history state, sanitized exceptions, and governed HTTP contracts.
Dependencies: certification_daemon core, live_path_certification, persistence
    store, LLM bridge, and FastAPI test client fixture.
Invariants:
  - Daemon state transitions never expose raw provider details.
  - Tick execution is interval and enabled-state gated.
  - History remains bounded by daemon config.
  - HTTP daemon routes return governed bounded response contracts.
"""

from __future__ import annotations

import hashlib
import json

from mcoi_runtime.adapters.llm_adapter import StubLLMBackend
from mcoi_runtime.contracts.llm import LLMBudget
from mcoi_runtime.core.certification_daemon import CertificationConfig, CertificationDaemon
from mcoi_runtime.core.live_path_certification import LivePathCertifier
from mcoi_runtime.core.llm_integration import LLMIntegrationBridge
from mcoi_runtime.persistence.postgres_store import InMemoryStore

FIXED_CLOCK_VALUE = "2026-05-16T12:00:00Z"


def _fixed_clock() -> str:
    return FIXED_CLOCK_VALUE


def _daemon(*, enabled: bool = True, interval_seconds: float = 0.0, max_history: int = 100) -> CertificationDaemon:
    store = InMemoryStore()
    bridge = LLMIntegrationBridge(clock=_fixed_clock, default_backend=StubLLMBackend())
    bridge.register_budget(LLMBudget(budget_id="daemon-budget", tenant_id="system", max_cost=100.0))
    return CertificationDaemon(
        certifier=LivePathCertifier(clock=_fixed_clock),
        clock=_fixed_clock,
        config=CertificationConfig(
            enabled=enabled,
            interval_seconds=interval_seconds,
            max_history=max_history,
        ),
        api_handle_fn=lambda request: {"governed": True, "path": request.get("path", "")},
        db_write_fn=lambda tenant_id, content: store.append_ledger(
            "certification",
            "daemon",
            tenant_id,
            content,
            hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest(),
        ),
        db_read_fn=lambda tenant_id: store.query_ledger(tenant_id),
        llm_invoke_fn=lambda prompt: bridge.complete(prompt, budget_id="daemon-budget"),
        ledger_fn=lambda tenant_id: store.query_ledger(tenant_id),
        state_fn=lambda: (hashlib.sha256(b"daemon-state").hexdigest(), store.ledger_count()),
    )


def test_daemon_status_bounded() -> None:
    daemon = _daemon()
    daemon.tick()

    status = daemon.status()
    assert set(status) == {
        "enabled",
        "interval_seconds",
        "health_score",
        "is_healthy",
        "total_runs",
        "total_passed",
        "total_failed",
        "consecutive_failures",
        "last_run_at",
        "last_status",
        "history_size",
    }
    assert status["enabled"] is True
    assert status["total_runs"] == 1
    assert status["total_passed"] == 1
    assert status["health_score"] == 1.0
    assert status["history_size"] == 1


def test_daemon_tick_interval_gated() -> None:
    daemon = _daemon(interval_seconds=9999.0)

    first_chain = daemon.tick()
    should_run_after_tick = daemon.should_run()
    second_chain = daemon.tick()
    assert first_chain is not None
    assert should_run_after_tick is False
    assert second_chain is None
    assert daemon.health.total_runs == 1
    assert daemon.status()["total_runs"] == 1


def test_daemon_force_runs_when_disabled() -> None:
    daemon = _daemon(enabled=False)

    tick_chain = daemon.tick()
    forced_chain = daemon.force_run()
    assert tick_chain is None
    assert forced_chain is not None
    assert forced_chain.all_passed is True
    assert daemon.is_enabled is False
    assert daemon.health.total_runs == 1


def test_daemon_force_returns_chain_hash() -> None:
    daemon = _daemon(enabled=False)

    chain = daemon.force_run()
    history = daemon.history
    assert chain is not None
    assert chain.chain_hash
    assert len(chain.chain_hash) == 64
    assert history[-1]["chain_id"] == chain.chain_id
    assert history[-1]["chain_hash"] == chain.chain_hash


def test_daemon_history_bounded() -> None:
    daemon = _daemon(max_history=3)

    for _ in range(5):
        daemon.force_run()

    history = daemon.history
    assert len(history) == 3
    assert daemon.status()["history_size"] == 3
    assert all(entry["chain_hash"] for entry in history)
    assert all(set(entry) == {"chain_id", "all_passed", "chain_hash", "steps", "passed", "failed", "at"} for entry in history)


def test_daemon_health_degrades_on_failures() -> None:
    daemon = CertificationDaemon(
        certifier=LivePathCertifier(clock=_fixed_clock),
        clock=_fixed_clock,
        config=CertificationConfig(interval_seconds=0),
        api_handle_fn=lambda request: (_ for _ in ()).throw(RuntimeError("raw api failure detail")),
    )

    for _ in range(4):
        daemon.tick()

    status = daemon.status()
    assert status["total_runs"] == 4
    assert status["total_failed"] == 4
    assert status["consecutive_failures"] == 4
    assert status["health_score"] == 0.0
    assert status["is_healthy"] is False


def test_daemon_exceptions_sanitized() -> None:
    daemon = CertificationDaemon(
        certifier=LivePathCertifier(clock=_fixed_clock),
        clock=_fixed_clock,
        config=CertificationConfig(interval_seconds=0),
        ledger_fn=lambda tenant_id: (_ for _ in ()).throw(RuntimeError("raw ledger secret")),
    )

    chain = daemon.tick()
    history_entry = daemon.history[-1]
    assert chain is None
    assert history_entry["chain_id"] == "error"
    assert history_entry["all_passed"] is False
    assert history_entry["error"] == "certification run error (RuntimeError)"
    assert daemon.health.last_status == "exception: RuntimeError"
    assert "raw ledger secret" not in str(history_entry)


def test_daemon_endpoint_contracts_governed(test_client) -> None:
    status_response = test_client.get("/api/v1/daemon/status")
    tick_response = test_client.post("/api/v1/daemon/tick")
    force_response = test_client.post("/api/v1/daemon/force")

    status_body = status_response.json()
    tick_body = tick_response.json()
    force_body = force_response.json()
    assert status_response.status_code == 200
    assert tick_response.status_code == 200
    assert force_response.status_code == 200
    assert status_body["governed"] is True
    assert tick_body["governed"] is True
    assert force_body["governed"] is True
    assert "health_score" in status_body
    assert "ran" in tick_body
    assert force_body["ran"] is True
    assert force_body["chain_hash"]
