"""Phase 200D — Certification Daemon.

Purpose: Periodic automated live-path certification proofs.
    Runs certification at configurable intervals and maintains
    a certification history with health scoring.
Governance scope: certification scheduling and execution only.
Dependencies: live_path_certification, persistence, llm_integration.
Invariants:
  - Daemon is non-blocking — each certification run is bounded.
  - Certification failures are recorded but never crash the daemon.
  - Health score degrades on consecutive failures.
  - Certification history is bounded (max entries).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from mcoi_runtime.core.live_path_certification import (
    CertificationChain,
    CertificationStatus,
    LivePathCertifier,
)


def _classify_certification_exception(exc: Exception) -> str:
    """Return a bounded certification failure message."""
    exc_type = type(exc).__name__
    if isinstance(exc, TimeoutError):
        return f"certification run timeout ({exc_type})"
    return f"certification run error ({exc_type})"


@dataclass(frozen=True, slots=True)
class CertificationConfig:
    """Configuration for the certification daemon."""

    interval_seconds: float = 300.0  # 5 minutes
    max_history: int = 100
    health_window: int = 10  # Last N runs for health score
    enabled: bool = True


@dataclass
class CertificationHealth:
    """Rolling health score based on recent certification runs."""

    total_runs: int = 0
    total_passed: int = 0
    total_failed: int = 0
    consecutive_failures: int = 0
    last_run_at: str = ""
    last_status: str = ""

    @property
    def health_score(self) -> float:
        """Health score 0.0-1.0 based on pass rate."""
        if self.total_runs == 0:
            return 1.0
        return self.total_passed / self.total_runs

    @property
    def is_healthy(self) -> bool:
        return self.health_score >= 0.8 and self.consecutive_failures < 3


class CertificationDaemon:
    """Periodic certification runner with health tracking.

    Not a real background thread — instead provides a tick() method
    that the runtime's main loop calls periodically. This avoids
    thread-safety issues while maintaining the daemon pattern.

    Usage:
        daemon = CertificationDaemon(certifier=certifier, ...)
        # In main loop:
        if daemon.should_run():
            daemon.tick()
    """

    def __init__(
        self,
        *,
        certifier: LivePathCertifier,
        clock: Callable[[], str],
        config: CertificationConfig | None = None,
        api_handle_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        db_write_fn: Callable[[str, dict[str, Any]], int] | None = None,
        db_read_fn: Callable[[str], list[dict[str, Any]]] | None = None,
        llm_invoke_fn: Callable[[str], Any] | None = None,
        ledger_fn: Callable[[str], list[dict[str, Any]]] | None = None,
        state_fn: Callable[[], tuple[str, int]] | None = None,
    ) -> None:
        self._certifier = certifier
        self._clock = clock
        self._config = config or CertificationConfig()
        self._health = CertificationHealth()
        self._history: list[dict[str, Any]] = []
        self._last_tick_time: float = 0.0

        # Certification step functions
        self._api_handle_fn = api_handle_fn
        self._db_write_fn = db_write_fn
        self._db_read_fn = db_read_fn
        self._llm_invoke_fn = llm_invoke_fn
        self._ledger_fn = ledger_fn
        self._state_fn = state_fn

    @property
    def config(self) -> CertificationConfig:
        return self._config

    @property
    def health(self) -> CertificationHealth:
        return self._health

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)

    @property
    def is_enabled(self) -> bool:
        return self._config.enabled

    def should_run(self) -> bool:
        """Check if enough time has passed since last certification."""
        if not self._config.enabled:
            return False
        elapsed = time.monotonic() - self._last_tick_time
        return elapsed >= self._config.interval_seconds

    def tick(self) -> CertificationChain | None:
        """Run one certification cycle.

        Returns the chain if run, None if skipped (disabled or too early).
        """
        if not self._config.enabled:
            return None

        self._last_tick_time = time.monotonic()

        try:
            # Build ledger entries if function available
            ledger_entries = None
            if self._ledger_fn is not None:
                ledger_entries = self._ledger_fn("system")

            chain = self._certifier.run_full_certification(
                api_handle_fn=self._api_handle_fn,
                db_write_fn=self._db_write_fn,
                db_read_fn=self._db_read_fn,
                llm_invoke_fn=self._llm_invoke_fn,
                ledger_entries=ledger_entries,
                pre_state_fn=self._state_fn,
                post_state_fn=self._state_fn,
            )

            self._record_result(chain)
            return chain

        except Exception as exc:
            # Never crash the daemon — record the failure
            self._health.total_runs += 1
            self._health.total_failed += 1
            self._health.consecutive_failures += 1
            self._health.last_run_at = self._clock()
            self._health.last_status = f"exception: {type(exc).__name__}"

            self._history.append({
                "chain_id": "error",
                "all_passed": False,
                "error": _classify_certification_exception(exc),
                "at": self._clock(),
            })
            self._trim_history()
            return None

    def force_run(self) -> CertificationChain | None:
        """Force an immediate certification regardless of interval."""
        saved_enabled = self._config.enabled
        # Temporarily enable if disabled
        if not saved_enabled:
            self._config = CertificationConfig(
                interval_seconds=self._config.interval_seconds,
                max_history=self._config.max_history,
                health_window=self._config.health_window,
                enabled=True,
            )
        result = self.tick()
        if not saved_enabled:
            self._config = CertificationConfig(
                interval_seconds=self._config.interval_seconds,
                max_history=self._config.max_history,
                health_window=self._config.health_window,
                enabled=False,
            )
        return result

    def _record_result(self, chain: CertificationChain) -> None:
        """Record certification result in health tracking."""
        self._health.total_runs += 1
        self._health.last_run_at = self._clock()

        if chain.all_passed:
            self._health.total_passed += 1
            self._health.consecutive_failures = 0
            self._health.last_status = "passed"
        else:
            self._health.total_failed += 1
            self._health.consecutive_failures += 1
            failed_steps = [
                s.name for s in chain.steps
                if s.status == CertificationStatus.FAILED
            ]
            self._health.last_status = f"failed: {', '.join(failed_steps)}"

        self._history.append({
            "chain_id": chain.chain_id,
            "all_passed": chain.all_passed,
            "chain_hash": chain.chain_hash,
            "steps": len(chain.steps),
            "passed": sum(1 for s in chain.steps if s.status == CertificationStatus.PASSED),
            "failed": sum(1 for s in chain.steps if s.status == CertificationStatus.FAILED),
            "at": chain.certified_at,
        })
        self._trim_history()

    def _trim_history(self) -> None:
        """Keep history bounded."""
        if len(self._history) > self._config.max_history:
            self._history = self._history[-self._config.max_history:]

    def status(self) -> dict[str, Any]:
        """Full daemon status for health endpoint."""
        return {
            "enabled": self._config.enabled,
            "interval_seconds": self._config.interval_seconds,
            "health_score": round(self._health.health_score, 3),
            "is_healthy": self._health.is_healthy,
            "total_runs": self._health.total_runs,
            "total_passed": self._health.total_passed,
            "total_failed": self._health.total_failed,
            "consecutive_failures": self._health.consecutive_failures,
            "last_run_at": self._health.last_run_at,
            "last_status": self._health.last_status,
            "history_size": len(self._history),
        }
