"""Thread-safe governance metrics registry — process singleton."""
from __future__ import annotations

from collections import deque
from threading import RLock
from time import time
from typing import Any

from mcoi_runtime.app.routers.musia_governance_metrics._constants import (
    DEFAULT_LATENCY_BUCKETS_SECONDS,
    MAX_RECENT_REJECTIONS,
    VERDICT_ALLOWED,
    VERDICT_DENIED,
    VERDICT_EXCEPTION,
    _VALID_SURFACES,
)
from mcoi_runtime.app.routers.musia_governance_metrics._models import (
    GovernanceMetricsSnapshot,
    LatencyHistogram,
    RejectionEvent,
)


class GovernanceMetricsRegistry:
    """Thread-safe registry. Singleton-style — one per process."""

    def __init__(
        self,
        *,
        latency_buckets_seconds: tuple[float, ...] = DEFAULT_LATENCY_BUCKETS_SECONDS,
    ) -> None:
        self._lock = RLock()
        self._runs_by_surface_verdict: dict[tuple[str, str], int] = {}
        self._runs_by_surface_tenant: dict[tuple[str, str], int] = {}
        # v4.24.0+: 3-way index used by per-tenant scrape views.
        # Populated alongside the 2-way indices above; never overrides
        # them (existing consumers keep working).
        self._runs_by_surface_tenant_verdict: dict[tuple[str, str, str], int] = {}
        self._denials_by_guard: dict[str, int] = {}
        self._recent_rejections: deque[RejectionEvent] = deque(
            maxlen=MAX_RECENT_REJECTIONS,
        )
        # Latency histograms — one per surface (v4.21.0+).
        # Bucket boundaries are immutable for the registry's lifetime;
        # operators wanting different boundaries construct a new
        # registry. _latency_state[surface] = (cumulative_counts_list,
        # sum_seconds, count). Cumulative count semantics (le=).
        self._latency_buckets: tuple[float, ...] = latency_buckets_seconds
        self._latency_state: dict[str, list[Any]] = {}
        # Φ_gov overall-verdict counters (USCL v3.3 / A1 observability).
        # DELIBERATELY SEPARATE from the chain counters above: these record the
        # overall Φ_gov decision for a construct write (Φ_agent + cascade +
        # external), not a chain invocation. Kept in their own fields so they
        # never enter the chain aggregates (total_runs/total_denials/
        # recent_rejections/denials_by_guard) — that separation is what makes
        # them additive rather than a contract change. Exposed as their own
        # metric families.
        self._phi_gov_decisions: dict[str, int] = {}        # verdict -> count
        self._phi_gov_denials_by_category: dict[str, int] = {}  # category -> count
        # Φ_gov cascade-coverage counter. Records, per construct write, whether
        # Phase 3 (the dependency cascade — the per-type invariant validators)
        # actually RAN or was SKIPPED. Phase 3 is skipped when the delta's
        # target is not yet in the graph (e.g. a create, whose construct is
        # registered only after a PASS). This surfaces the otherwise-silent fact
        # that validators do not cover the create path. Dedicated field; never
        # enters the chain aggregates. See docs/GOVERNANCE_GATE_COVERAGE_AUDIT.md
        self._phi_gov_cascade_coverage: dict[str, int] = {}  # "ran"|"skipped" -> count

    def _observe_latency_locked(
        self, surface: str, duration_seconds: float
    ) -> None:
        """Update the per-surface latency histogram. MUST hold _lock."""
        state = self._latency_state.get(surface)
        if state is None:
            state = [
                [0] * len(self._latency_buckets),
                0.0,
                0,
            ]
            self._latency_state[surface] = state
        # Cumulative semantics: increment every bucket whose upper
        # bound ≥ duration. The +Inf bucket is implicit in count.
        for i, ub in enumerate(self._latency_buckets):
            if duration_seconds <= ub:
                state[0][i] += 1
        state[1] += duration_seconds
        state[2] += 1

    def record(
        self,
        *,
        surface: str,
        tenant_id: str,
        allowed: bool,
        blocking_guard: str | None = None,
        reason: str = "",
        exception: bool = False,
        now: float | None = None,
        duration_seconds: float | None = None,
    ) -> None:
        """Record one chain invocation.

        Required: surface (write|domain_run) and tenant_id.
        - allowed: True → verdict=allowed; False + exception=False → denied;
          False + exception=True → verdict=exception.
        - blocking_guard / reason: only consulted on denial. ``"unknown"``
          when the bridge couldn't extract the guard name.
        - now: injectable clock for tests.
        - duration_seconds: chain-evaluation duration (v4.21.0+). Optional
          for backward compatibility — when omitted, no histogram update.
          Bridge call sites (chain_to_validator, gate_domain_run) pass
          time.monotonic_ns() deltas converted to seconds. Negative
          values are treated as zero (clock skew defense).

        Bad inputs raise ValueError to surface miswiring early; production
        callers should never trip these.
        """
        if surface not in _VALID_SURFACES:
            raise ValueError(f"unknown surface: {surface!r}")
        if exception:
            verdict = VERDICT_EXCEPTION
        elif allowed:
            verdict = VERDICT_ALLOWED
        else:
            verdict = VERDICT_DENIED
        ts = time() if now is None else now

        with self._lock:
            sv_key = (surface, verdict)
            self._runs_by_surface_verdict[sv_key] = (
                self._runs_by_surface_verdict.get(sv_key, 0) + 1
            )
            st_key = (surface, tenant_id)
            self._runs_by_surface_tenant[st_key] = (
                self._runs_by_surface_tenant.get(st_key, 0) + 1
            )
            stv_key = (surface, tenant_id, verdict)
            self._runs_by_surface_tenant_verdict[stv_key] = (
                self._runs_by_surface_tenant_verdict.get(stv_key, 0) + 1
            )
            if verdict == VERDICT_DENIED:
                guard = blocking_guard or "unknown"
                self._denials_by_guard[guard] = (
                    self._denials_by_guard.get(guard, 0) + 1
                )
                self._recent_rejections.append(
                    RejectionEvent(
                        timestamp=ts,
                        surface=surface,
                        tenant_id=tenant_id,
                        blocking_guard=guard,
                        reason=reason,
                    )
                )
            elif verdict == VERDICT_EXCEPTION:
                # Exceptions are treated as a fail-closed denial in the
                # bridge, so they also surface in the rejection ring for
                # forensic visibility — operators want to find chains
                # whose guards crash, not just deny.
                self._recent_rejections.append(
                    RejectionEvent(
                        timestamp=ts,
                        surface=surface,
                        tenant_id=tenant_id,
                        blocking_guard=blocking_guard or "exception",
                        reason=reason,
                    )
                )
            # Latency observation is recorded for every verdict
            # (allowed, denied, exception). A crashing guard is still
            # interesting wall-clock data — operators want to see if
            # certain guards are slow even when they fail.
            if duration_seconds is not None:
                d = max(0.0, duration_seconds)
                self._observe_latency_locked(surface, d)

    def record_phi_gov_decision(
        self, *, verdict: str, category: str = ""
    ) -> None:
        """Record one overall Φ_gov verdict for a construct write.

        ``verdict`` is ``VERDICT_ALLOWED`` or ``VERDICT_DENIED``. On a denial,
        ``category`` is the normalised rejection-reason class (e.g.
        ``cascade_escalated``, ``phi_agent_blocked_at``) used to attribute the
        denial without high-cardinality reason strings.

        Counted in dedicated fields only — never the chain aggregates.
        """
        if verdict not in (VERDICT_ALLOWED, VERDICT_DENIED):
            raise ValueError(f"unknown verdict: {verdict!r}")
        with self._lock:
            self._phi_gov_decisions[verdict] = (
                self._phi_gov_decisions.get(verdict, 0) + 1
            )
            if verdict == VERDICT_DENIED:
                cat = category or "unknown"
                self._phi_gov_denials_by_category[cat] = (
                    self._phi_gov_denials_by_category.get(cat, 0) + 1
                )

    def record_phi_gov_cascade_coverage(self, *, ran: bool) -> None:
        """Record whether the Φ_gov dependency cascade (Phase 3 — the per-type
        invariant validators) actually ran for one construct write.

        ``ran=True`` when Phase 3 evaluated at least one cascade; ``ran=False``
        when it was skipped (delta target not yet in the graph, e.g. a create).
        A persistently high ``skipped`` ratio is the signal that the validators
        are not covering the live write path.
        """
        key = "ran" if ran else "skipped"
        with self._lock:
            self._phi_gov_cascade_coverage[key] = (
                self._phi_gov_cascade_coverage.get(key, 0) + 1
            )

    def snapshot(self) -> GovernanceMetricsSnapshot:
        with self._lock:
            latency_by_surface: dict[str, LatencyHistogram] = {}
            for surface, state in self._latency_state.items():
                latency_by_surface[surface] = LatencyHistogram(
                    upper_bounds=self._latency_buckets,
                    bucket_counts=tuple(state[0]),
                    sum_seconds=state[1],
                    count=state[2],
                )
            return GovernanceMetricsSnapshot(
                runs_by_surface_verdict=dict(self._runs_by_surface_verdict),
                runs_by_surface_tenant=dict(self._runs_by_surface_tenant),
                denials_by_guard=dict(self._denials_by_guard),
                recent_rejections=tuple(self._recent_rejections),
                latency_by_surface=latency_by_surface,
                runs_by_surface_tenant_verdict=dict(
                    self._runs_by_surface_tenant_verdict
                ),
                phi_gov_decisions=dict(self._phi_gov_decisions),
                phi_gov_denials_by_category=dict(
                    self._phi_gov_denials_by_category
                ),
                phi_gov_cascade_coverage=dict(self._phi_gov_cascade_coverage),
            )

    def reset(self) -> None:
        """Test-only. Restores a fresh state."""
        with self._lock:
            self._runs_by_surface_verdict.clear()
            self._runs_by_surface_tenant.clear()
            self._runs_by_surface_tenant_verdict.clear()
            self._denials_by_guard.clear()
            self._recent_rejections.clear()
            self._latency_state.clear()
            self._phi_gov_decisions.clear()
            self._phi_gov_denials_by_category.clear()
            self._phi_gov_cascade_coverage.clear()


REGISTRY = GovernanceMetricsRegistry()
