"""Phase 228B — Request Deduplication Pipeline.

Purpose: Detect and suppress duplicate requests using content hashing
    with configurable time windows and per-tenant tracking.
Dependencies: None (stdlib only).
Invariants:
  - Duplicate detection uses SHA-256 of canonical request.
  - Window-based expiry prevents unbounded growth.
  - Per-tenant isolation of dedup state.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class DedupResult:
    """Result of duplicate check."""
    is_duplicate: bool
    request_hash: str
    original_timestamp: float | None = None


class RequestDeduplicator:
    """Detects duplicate requests using content hashing."""

    def __init__(self, window_seconds: float = 300.0, max_entries: int = 50_000):
        self._window = window_seconds
        self._max_entries = max_entries
        self._seen: dict[str, float] = {}  # hash -> timestamp
        self._tenant_seen: dict[str, dict[str, float]] = {}
        self._total_checked = 0
        self._total_duplicates = 0

    @staticmethod
    def _hash_request(data: dict[str, Any]) -> str:
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:24]

    def check(self, request_data: dict[str, Any], tenant_id: str = "") -> DedupResult:
        """Check if request is a duplicate. Returns DedupResult."""
        self._total_checked += 1
        now = time.time()
        self._cleanup(now)

        req_hash = self._hash_request(request_data)
        key = f"{tenant_id}:{req_hash}" if tenant_id else req_hash

        existing = self._seen.get(key)
        if existing is not None:
            self._total_duplicates += 1
            return DedupResult(is_duplicate=True, request_hash=req_hash, original_timestamp=existing)

        # Store
        if len(self._seen) >= self._max_entries:
            oldest_key = min(self._seen, key=self._seen.get)
            del self._seen[oldest_key]
        self._seen[key] = now

        # Track per-tenant
        if tenant_id:
            if tenant_id not in self._tenant_seen:
                self._tenant_seen[tenant_id] = {}
            self._tenant_seen[tenant_id][req_hash] = now

        return DedupResult(is_duplicate=False, request_hash=req_hash)

    def _cleanup(self, now: float) -> None:
        cutoff = now - self._window
        expired = [k for k, t in self._seen.items() if t < cutoff]
        for k in expired:
            del self._seen[k]

    @property
    def tracked_count(self) -> int:
        return len(self._seen)

    @property
    def duplicate_rate(self) -> float:
        if self._total_checked == 0:
            return 0.0
        return self._total_duplicates / self._total_checked

    def tenant_stats(self, tenant_id: str) -> dict[str, Any]:
        tenant_data = self._tenant_seen.get(tenant_id, {})
        return {
            "tenant_id": tenant_id,
            "tracked_requests": len(tenant_data),
        }

    def summary(self) -> dict[str, Any]:
        return {
            "total_checked": self._total_checked,
            "total_duplicates": self._total_duplicates,
            "duplicate_rate": round(self.duplicate_rate, 4),
            "tracked_entries": self.tracked_count,
            "window_seconds": self._window,
            "tenants_tracked": len(self._tenant_seen),
        }
