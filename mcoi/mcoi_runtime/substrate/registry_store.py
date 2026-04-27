"""
Tenanted Registry Store — multi-tenant construct isolation.

Each tenant gets its own DependencyGraph + Φ_agent filter. Constructs
created under tenant A are invisible to tenant B; cascade walks never
cross the tenant boundary; Φ_gov decisions are scoped per-tenant.

The store is the structural enforcement of the Boundary construct at the
runtime level: each tenant *is* a Boundary, and the registry honors that.

Tenant identifiers are opaque strings. Authentication and tenant resolution
happen in middleware (or, for v4.3.0, via an X-Tenant-ID header).

Persistence (v4.4.0+) is opt-in via configure_persistence(directory).
Snapshots are JSON files per tenant; Φ_agent filters are NOT persisted
(they are Python callables) and must be re-installed at startup.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Optional

from mcoi_runtime.substrate._quota import TenantQuota
from mcoi_runtime.substrate.cascade import DependencyGraph
from mcoi_runtime.substrate.phi_gov import PhiAgentFilter


DEFAULT_TENANT = "default"


# TenantQuota now lives in substrate/_quota.py (extracted v4.14.1 to break
# registry_store ↔ persistence circular import). Re-exported here for
# backward compatibility — existing imports of TenantQuota from
# mcoi_runtime.substrate.registry_store keep working.


@dataclass
class TenantState:
    """Per-tenant substrate state."""

    tenant_id: str
    graph: DependencyGraph = field(default_factory=DependencyGraph)
    phi_agent: PhiAgentFilter = field(default_factory=PhiAgentFilter)
    quota: TenantQuota = field(default_factory=TenantQuota)
    # Sliding-window write timestamps. Not persisted (transient state;
    # rate limit effectively resets on process restart, which is
    # acceptable behavior — restart is a rare event compared to writes,
    # and the alternative would be persisting potentially-thousands of
    # timestamps per tenant per hour, which is not worth the cost).
    _recent_writes: deque[float] = field(default_factory=deque)
    # v4.13.0: secondary index from run_id → set of construct UUIDs in
    # that run. Avoids O(N) scans for list_runs / delete_run / filter-by-run.
    # Always derivable from `graph.constructs.values()` metadata, so we
    # don't persist it — it's rebuilt on load_tenant via _rebuild_runs_index.
    _runs_index: dict[str, set] = field(default_factory=dict)

    def check_quota_for_write(self) -> tuple[bool, str]:
        """Check the lifetime construct count quota.

        Returns (ok, reason). When ok is False, reason names the violation.
        """
        if self.quota.max_constructs is not None:
            current = len(self.graph.constructs)
            if current >= self.quota.max_constructs:
                return (
                    False,
                    f"max_constructs quota reached: "
                    f"{current}/{self.quota.max_constructs}",
                )
        return True, ""

    def check_rate_limit_for_write(
        self, *, now: float | None = None
    ) -> tuple[bool, int, str]:
        """Check the sliding-window write rate.

        Returns (ok, retry_after_seconds, reason). When ok is False,
        retry_after_seconds is the integer count of seconds until the
        oldest in-window timestamp expires; reason names the violation.
        Rate-limit-rejected writes do NOT consume a slot in the window.

        Side effect: evicts timestamps older than the window from the deque.
        Callers that successfully pass should call ``record_write()`` to
        consume a slot.
        """
        if self.quota.max_writes_per_window is None:
            return True, 0, ""
        ts_now = time.time() if now is None else now
        cutoff = ts_now - self.quota.window_seconds
        # Evict expired timestamps. deque.popleft is O(1).
        while self._recent_writes and self._recent_writes[0] < cutoff:
            self._recent_writes.popleft()
        if len(self._recent_writes) >= self.quota.max_writes_per_window:
            oldest = self._recent_writes[0]
            retry_after = max(1, int(oldest + self.quota.window_seconds - ts_now))
            return (
                False,
                retry_after,
                f"max_writes_per_window quota reached: "
                f"{len(self._recent_writes)}/{self.quota.max_writes_per_window} "
                f"in last {self.quota.window_seconds}s",
            )
        return True, 0, ""

    def record_write(self, *, now: float | None = None) -> None:
        """Consume a rate-limit slot. Called after a successful write."""
        if self.quota.max_writes_per_window is None:
            return  # no tracking when unlimited — keeps the deque empty
        ts_now = time.time() if now is None else now
        self._recent_writes.append(ts_now)

    def merge_run(
        self,
        run_id: str,
        constructs: list,
        *,
        domain: str | None = None,
        summary: str | None = None,
        timestamp_iso: str | None = None,
    ) -> tuple[bool, str]:
        """Atomically merge a domain-cycle's audit constructs into the registry.

        Each construct gets the following metadata stamped in place:
          - ``run_id``       — always stamped
          - ``run_domain``   — stamped if ``domain`` provided (v4.12.0)
          - ``run_summary``  — stamped if ``summary`` provided (v4.12.0)
          - ``run_timestamp``— ISO-format datetime (v4.12.0). Auto-generated
                                if not supplied.

        The merge is rejected (no constructs land) if it would push the
        lifetime construct count over ``quota.max_constructs``.

        v4.11.0+: persistence of cycle constructs.
        v4.12.0+: extended metadata (domain, summary, timestamp).

        Φ_gov is NOT re-evaluated on merge — the constructs originated from
        an UCJA-passed input that was already governance-gated. The lifetime
        quota IS checked because it bounds tenant blast radius. Rate limits
        are NOT checked because a single domain run is one user-facing
        operation regardless of how many internal constructs it produces.

        Returns (ok, reason). On rejection, no constructs are merged.
        """
        if self.quota.max_constructs is not None:
            current = len(self.graph.constructs)
            available = self.quota.max_constructs - current
            if available < len(constructs):
                return (
                    False,
                    f"merge_run would exceed max_constructs quota: "
                    f"{current}+{len(constructs)} > {self.quota.max_constructs} "
                    f"(headroom={available})",
                )

        # Default timestamp if not supplied
        if timestamp_iso is None:
            from datetime import datetime, timezone
            timestamp_iso = datetime.now(timezone.utc).isoformat()

        # Atomic: stamp metadata + register all, or no changes.
        # Stamp first so any failure mid-loop doesn't leave half-stamped
        # constructs in caller's hands.
        for c in constructs:
            c.metadata["run_id"] = run_id
            c.metadata["run_timestamp"] = timestamp_iso
            if domain is not None:
                c.metadata["run_domain"] = domain
            if summary is not None:
                c.metadata["run_summary"] = summary
        index_bucket = self._runs_index.setdefault(run_id, set())
        for c in constructs:
            # Direct dict insertion — these constructs come with no
            # depends_on edges (audit artifacts, not governance state).
            self.graph.constructs[c.id] = c
            index_bucket.add(c.id)
        return True, ""

    def list_runs(self) -> list[dict[str, Any]]:
        """Group registry constructs by run_id and return per-run summaries.

        Returns a list of ``{run_id, domain, summary, timestamp, construct_count}``
        in newest-first timestamp order. Constructs without a ``run_id`` in
        their metadata are skipped (they're direct API writes, not domain runs).

        v4.13.0+: O(R) where R is the number of distinct runs (vs. O(N)
        scan over all constructs). Uses ``_runs_index`` populated by
        ``merge_run`` and rebuilt on ``_rebuild_runs_index`` (called after
        persistence load).
        """
        out: list[dict[str, Any]] = []
        for run_id, member_ids in self._runs_index.items():
            # Pull metadata from any member; all members of a run share
            # the same run_domain/run_summary/run_timestamp.
            sample_id = next(iter(member_ids), None)
            if sample_id is None or sample_id not in self.graph.constructs:
                continue
            sample = self.graph.constructs[sample_id]
            out.append({
                "run_id": run_id,
                "domain": sample.metadata.get("run_domain"),
                "summary": sample.metadata.get("run_summary"),
                "timestamp": sample.metadata.get("run_timestamp"),
                "construct_count": len(member_ids),
            })
        return sorted(
            out,
            key=lambda r: r["timestamp"] or "",
            reverse=True,
        )

    def constructs_in_run(self, run_id: str) -> list[Any]:
        """Return the constructs persisted for a given run, indexed lookup.

        Returns [] if no such run. Constructs are returned in arbitrary order;
        callers that need a stable ordering should sort by ``created_at`` or
        another field on the construct.
        """
        member_ids = self._runs_index.get(run_id, set())
        return [
            self.graph.constructs[cid]
            for cid in member_ids
            if cid in self.graph.constructs
        ]

    def delete_run(self, run_id: str) -> dict[str, Any]:
        """Bulk delete constructs stamped with the given run_id.

        Returns ``{"deleted": int, "skipped": int, "skipped_ids": [...]}``.
        Skips constructs that have live dependents — those would orphan
        registered references if removed. The graph layer enforces this:
        ``unregister`` raises if ``dependents[id]`` is non-empty.

        v4.13.0+: O(M) where M is the number of constructs in the run
        (vs. O(N) scan over all constructs). Uses ``_runs_index``.

        Atomicity: best-effort. Each construct is independently attempted;
        a skip on one does not block deletion of the others. The caller
        receives a structured count + ids list of what was skipped.
        """
        targets = list(self._runs_index.get(run_id, set()))
        deleted = 0
        skipped: list[str] = []
        deleted_ids: list = []
        for cid in targets:
            try:
                self.graph.unregister(cid)
                deleted += 1
                deleted_ids.append(cid)
            except ValueError:
                skipped.append(str(cid))
        # Scrub the index of successfully-deleted ids.
        if run_id in self._runs_index:
            for cid in deleted_ids:
                self._runs_index[run_id].discard(cid)
            # If the run is now fully empty, drop the index entry entirely.
            if not self._runs_index[run_id]:
                del self._runs_index[run_id]
        return {
            "deleted": deleted,
            "skipped": len(skipped),
            "skipped_ids": skipped,
        }

    def _rebuild_runs_index(self) -> None:
        """Reconstruct _runs_index from the current graph contents.

        Called after a persistence load (where graph is restored but the
        index is not). O(N) where N is total construct count; runs are
        identified by ``metadata['run_id']`` presence.
        """
        self._runs_index.clear()
        for cid, c in self.graph.constructs.items():
            rid = c.metadata.get("run_id")
            if rid:
                self._runs_index.setdefault(rid, set()).add(cid)


class TenantQuotaExceeded(Exception):
    """Raised when an auto-provisioning request would exceed max_tenants.

    v4.18.0+. When max_tenants is set on a TenantedRegistryStore, any
    auto-provisioning attempt past the cap raises this. Callers can
    catch and translate to an HTTP 429/507 — or pre-register tenants
    via an admin path that bypasses the cap (set_max_tenants higher,
    or accept the raise as the policy signal).
    """


class TenantedRegistryStore:
    """Thread-safe map of tenant_id → TenantState.

    Get-or-create semantics: any request for an unknown tenant_id creates
    a fresh state. This is the right default for v4.3.0 (no enrollment
    flow yet); production deployments will wire an explicit tenant
    onboarding step that pre-creates the state.

    v4.18.0+: optional ``max_tenants`` cap. When set, auto-provisioning
    a NEW tenant past the cap raises :class:`TenantQuotaExceeded`.
    Existing tenants are unaffected. Default ``None`` preserves the
    original unbounded behavior — wire a cap in production where
    tenant_ids may come from arbitrary auth claims.
    """

    def __init__(self, *, max_tenants: int | None = None) -> None:
        self._lock = RLock()
        self._tenants: dict[str, TenantState] = {}
        self._max_tenants = max_tenants

    @property
    def max_tenants(self) -> int | None:
        """Current cap, or None for unbounded."""
        with self._lock:
            return self._max_tenants

    def set_max_tenants(self, value: int | None) -> None:
        """Update the cap at runtime. Pass None to disable.

        Lowering the cap below the current tenant count is allowed —
        existing tenants are not evicted (would lose data); only NEW
        auto-provisions past the new cap will fail.
        """
        with self._lock:
            self._max_tenants = value

    def get_or_create(self, tenant_id: str) -> TenantState:
        if not tenant_id:
            raise ValueError("tenant_id must be non-empty")
        with self._lock:
            state = self._tenants.get(tenant_id)
            if state is None:
                if (
                    self._max_tenants is not None
                    and len(self._tenants) >= self._max_tenants
                ):
                    raise TenantQuotaExceeded(
                        f"max_tenants cap reached: "
                        f"{len(self._tenants)}/{self._max_tenants} "
                        f"(tenant {tenant_id!r} not auto-provisioned)"
                    )
                state = TenantState(tenant_id=tenant_id)
                self._tenants[tenant_id] = state
            return state

    def get(self, tenant_id: str) -> TenantState | None:
        with self._lock:
            return self._tenants.get(tenant_id)

    def list_tenants(self) -> list[str]:
        with self._lock:
            return sorted(self._tenants.keys())

    def reset_tenant(self, tenant_id: str) -> None:
        """Drop a tenant's state. Other tenants unaffected."""
        with self._lock:
            self._tenants.pop(tenant_id, None)

    def reset_all(self) -> None:
        """Test-only: drop every tenant."""
        with self._lock:
            self._tenants.clear()

    def install_phi_agent_filter(
        self,
        tenant_id: str,
        filter_obj: PhiAgentFilter,
    ) -> None:
        """Replace the Φ_agent filter for one tenant."""
        state = self.get_or_create(tenant_id)
        state.phi_agent = filter_obj

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "tenant_count": len(self._tenants),
                "tenants": [
                    {
                        "tenant_id": tid,
                        "construct_count": len(state.graph.constructs),
                    }
                    for tid, state in self._tenants.items()
                ],
            }

    # ---- Persistence (v4.4.0) ----
    #
    # Persistence is delegated to a FileBackedPersistence (or any object
    # that has matching .save(), .load(), .list_tenants(), .delete()).
    # The store does not itself touch disk; it just routes calls.

    def attach_persistence(self, persistence: Any) -> None:
        """Bind a persistence backend. The store will route snapshot/load through it."""
        with self._lock:
            self._persistence = persistence

    def detach_persistence(self) -> None:
        with self._lock:
            self._persistence = None
            self._auto_snapshot = False

    def set_auto_snapshot(self, enabled: bool) -> None:
        """Enable/disable automatic per-tenant snapshotting after writes.

        When enabled, callers should invoke ``maybe_snapshot(tenant_id)``
        after every successful write. The store does not itself observe
        register/unregister calls (those go directly on DependencyGraph).
        """
        with self._lock:
            if enabled and self.persistence is None:
                raise RuntimeError(
                    "auto-snapshot requires a persistence backend; "
                    "call attach_persistence() first"
                )
            self._auto_snapshot = enabled

    @property
    def auto_snapshot(self) -> bool:
        return getattr(self, "_auto_snapshot", False)

    def maybe_snapshot(self, tenant_id: str) -> Any | None:
        """Snapshot a tenant if auto-snapshot is enabled. Returns the path or None."""
        if not self.auto_snapshot:
            return None
        if self.persistence is None:
            return None  # auto disabled if backend was detached
        try:
            return self.snapshot_tenant(tenant_id)
        except Exception:
            # Swallow: a failed snapshot must not roll back an already-committed
            # in-memory write. Production wiring should monitor the backend
            # health separately.
            return None

    @property
    def persistence(self) -> Any:
        return getattr(self, "_persistence", None)

    def snapshot_tenant(self, tenant_id: str) -> Any:
        """Persist a single tenant's graph + quota.

        Quota is included only if the backend supports it (FileBackedPersistence
        accepts a ``quota=`` kwarg from v4.10.0). For other backends that may
        not, we fall back to the legacy graph-only call.
        """
        backend = self.persistence
        if backend is None:
            raise RuntimeError(
                "no persistence backend attached; call attach_persistence() first"
            )
        state = self.get_or_create(tenant_id)
        try:
            return backend.save(tenant_id, state.graph, quota=state.quota)
        except TypeError:
            # Backend predates the quota kwarg; fall back to graph-only.
            return backend.save(tenant_id, state.graph)

    def snapshot_all(self) -> list[Any]:
        """Persist every known tenant."""
        backend = self.persistence
        if backend is None:
            raise RuntimeError("no persistence backend attached")
        with self._lock:
            tids = list(self._tenants.keys())
        out: list[Any] = []
        for tid in tids:
            state = self._tenants[tid]
            try:
                out.append(backend.save(tid, state.graph, quota=state.quota))
            except TypeError:
                out.append(backend.save(tid, state.graph))
        return out

    def load_tenant(self, tenant_id: str) -> bool:
        """Load a tenant's graph + quota from the backend. Returns True if loaded.

        Φ_agent filter is NOT restored — callers must re-install custom
        filters. The default permissive filter applies otherwise. Recent-write
        timestamps are also not persisted (transient state).

        v4.10.0+: prefers ``load_with_quota()`` if the backend supports it.
        Falls back to ``load()`` (graph-only) for older backends.
        """
        backend = self.persistence
        if backend is None:
            raise RuntimeError("no persistence backend attached")

        graph = None
        quota = None
        load_with_quota = getattr(backend, "load_with_quota", None)
        if load_with_quota is not None:
            result = load_with_quota(tenant_id)
            if result is not None:
                graph, quota = result
        else:
            graph = backend.load(tenant_id)

        if graph is None:
            return False
        with self._lock:
            existing = self._tenants.get(tenant_id)
            if existing is None:
                ts = TenantState(tenant_id=tenant_id, graph=graph)
                if quota is not None:
                    ts.quota = quota
                ts._rebuild_runs_index()  # v4.13.0
                self._tenants[tenant_id] = ts
            else:
                # Replace the graph + quota in place; preserve filter
                existing.graph = graph
                if quota is not None:
                    existing.quota = quota
                existing._rebuild_runs_index()  # v4.13.0
        return True

    def load_all(self) -> list[str]:
        """Load every tenant the backend knows about. Returns loaded tenant ids."""
        backend = self.persistence
        if backend is None:
            raise RuntimeError("no persistence backend attached")
        loaded: list[str] = []
        for tid in backend.list_tenants():
            if self.load_tenant(tid):
                loaded.append(tid)
        return loaded


# Module-level singleton. Tests use reset_all().
STORE = TenantedRegistryStore()


def configure_persistence(
    directory: str | None,
    *,
    auto_snapshot: bool = False,
) -> None:
    """Convenience: attach a FileBackedPersistence rooted at ``directory``.

    Pass None to detach. ``auto_snapshot=True`` enables automatic snapshots
    after every governed write (callers must invoke ``STORE.maybe_snapshot``
    in their write paths). Lazy import keeps registry_store from importing
    the persistence module unless persistence is actually used.
    """
    if directory is None:
        STORE.detach_persistence()
        return
    from mcoi_runtime.substrate.persistence import FileBackedPersistence
    STORE.attach_persistence(FileBackedPersistence(directory))
    STORE.set_auto_snapshot(auto_snapshot)
