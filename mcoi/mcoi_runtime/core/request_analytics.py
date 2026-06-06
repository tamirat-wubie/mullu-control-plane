"""Request Analytics — Per-endpoint latency and throughput tracking.

Purpose: Track request latency, throughput, and error rates per endpoint
    for performance monitoring, SLO compliance, and capacity planning.
Governance scope: analytics only — read-only metric collection.
Dependencies: none (pure algorithm + threading).
Invariants:
  - Metrics are per-endpoint (no cross-endpoint aggregation leakage).
  - Sliding window prevents stale data from skewing metrics.
  - Thread-safe — concurrent request recording is safe.
  - Bounded memory — fixed window size per endpoint.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from numbers import Real
from typing import Any, Callable


_MAX_ENDPOINT_LENGTH = 2048


@dataclass(frozen=True, slots=True)
class RequestSample:
    """A single request observation."""

    timestamp: float
    latency_ms: float
    success: bool
    status_code: int = 200


@dataclass(frozen=True, slots=True)
class EndpointAnalytics:
    """Computed analytics for a single endpoint."""

    endpoint: str
    request_count: int
    error_count: int
    error_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    throughput_rps: float  # requests per second in window

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "requests": self.request_count,
            "errors": self.error_count,
            "error_rate": round(self.error_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "throughput_rps": round(self.throughput_rps, 1),
        }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    rank = max(0, int((pct / 100.0) * len(s) + 0.5) - 1)
    return s[min(rank, len(s) - 1)]


class RequestAnalytics:
    """Per-endpoint request analytics with sliding windows.

    Usage:
        analytics = RequestAnalytics()
        analytics.record("/api/v1/llm", latency_ms=230, success=True)
        analytics.record("/api/v1/llm", latency_ms=5000, success=False, status_code=500)

        report = analytics.endpoint_report("/api/v1/llm")
        all_reports = analytics.all_endpoints()
        slow = analytics.slow_endpoints(threshold_ms=1000)
    """

    WINDOW_SIZE = 1000  # Samples per endpoint
    MAX_ENDPOINTS = 500
    DEFAULT_WINDOW_SECONDS = 300.0  # 5-minute window for throughput calc

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self._clock = clock or time.monotonic
        self._window_seconds = _coerce_positive_float(window_seconds, field_name="window_seconds")
        self._samples: dict[str, deque[RequestSample]] = {}
        self._lock = threading.Lock()
        self._total_requests = 0

    def record(
        self,
        endpoint: str,
        *,
        latency_ms: float,
        success: bool = True,
        status_code: int = 200,
    ) -> None:
        """Record a request observation for an endpoint."""
        endpoint = _validate_endpoint(endpoint)
        latency_ms = _coerce_non_negative_float(latency_ms, field_name="latency_ms")
        success = _coerce_bool(success, field_name="success")
        status_code = _coerce_status_code(status_code)
        sample = RequestSample(
            timestamp=_coerce_finite_float(self._clock(), field_name="timestamp"),
            latency_ms=latency_ms,
            success=success,
            status_code=status_code,
        )
        with self._lock:
            if endpoint not in self._samples:
                if len(self._samples) >= self.MAX_ENDPOINTS:
                    # Evict endpoint with fewest samples
                    min_ep = min(self._samples, key=lambda e: len(self._samples[e]))
                    del self._samples[min_ep]
                self._samples[endpoint] = deque(maxlen=self.WINDOW_SIZE)
            self._samples[endpoint].append(sample)
            self._total_requests += 1

    def _compute(self, endpoint: str, samples: list[RequestSample]) -> EndpointAnalytics:
        """Compute analytics from a list of samples."""
        if not samples:
            return EndpointAnalytics(
                endpoint=endpoint, request_count=0, error_count=0,
                error_rate=0.0, avg_latency_ms=0.0, p50_latency_ms=0.0,
                p95_latency_ms=0.0, p99_latency_ms=0.0,
                min_latency_ms=0.0, max_latency_ms=0.0, throughput_rps=0.0,
            )

        latencies = [s.latency_ms for s in samples]
        errors = sum(1 for s in samples if not s.success)
        error_rate = errors / len(samples)

        # Throughput: requests in window / window duration
        now = self._clock()
        window_samples = [s for s in samples if (now - s.timestamp) <= self._window_seconds]
        if len(window_samples) >= 2:
            span = window_samples[-1].timestamp - window_samples[0].timestamp
            throughput = len(window_samples) / span if span > 0 else 0.0
        else:
            throughput = 0.0

        return EndpointAnalytics(
            endpoint=endpoint,
            request_count=len(samples),
            error_count=errors,
            error_rate=error_rate,
            avg_latency_ms=sum(latencies) / len(latencies),
            p50_latency_ms=_percentile(latencies, 50),
            p95_latency_ms=_percentile(latencies, 95),
            p99_latency_ms=_percentile(latencies, 99),
            min_latency_ms=min(latencies),
            max_latency_ms=max(latencies),
            throughput_rps=throughput,
        )

    def endpoint_report(self, endpoint: str) -> EndpointAnalytics | None:
        """Get analytics for a specific endpoint."""
        endpoint = _validate_endpoint(endpoint)
        with self._lock:
            samples = list(self._samples.get(endpoint, []))
        if not samples:
            return None
        return self._compute(endpoint, samples)

    def all_endpoints(self) -> list[EndpointAnalytics]:
        """Get analytics for all tracked endpoints."""
        with self._lock:
            snapshot = {ep: list(samples) for ep, samples in self._samples.items()}
        return [self._compute(ep, samples) for ep, samples in sorted(snapshot.items())]

    def slow_endpoints(self, *, threshold_ms: float = 1000.0) -> list[EndpointAnalytics]:
        """List endpoints with P95 latency above threshold."""
        threshold_ms = _coerce_non_negative_float(threshold_ms, field_name="threshold_ms")
        reports = self.all_endpoints()
        return [r for r in reports if r.p95_latency_ms > threshold_ms]

    def error_endpoints(self, *, threshold: float = 0.05) -> list[EndpointAnalytics]:
        """List endpoints with error rate above threshold."""
        threshold = _coerce_error_threshold(threshold)
        reports = self.all_endpoints()
        return [r for r in reports if r.error_rate > threshold]

    @property
    def endpoint_count(self) -> int:
        return len(self._samples)

    @property
    def total_requests(self) -> int:
        return self._total_requests

    def summary(self) -> dict[str, Any]:
        return {
            "endpoints_tracked": len(self._samples),
            "total_requests": self._total_requests,
            "window_seconds": self._window_seconds,
        }


def _validate_endpoint(endpoint: str) -> str:
    """Validate endpoint identity before it becomes an analytics partition key."""
    if not isinstance(endpoint, str):
        raise ValueError("endpoint must be a string")
    normalized = endpoint.strip()
    if not normalized:
        raise ValueError("endpoint must be non-empty")
    if len(normalized) > _MAX_ENDPOINT_LENGTH:
        raise ValueError("endpoint exceeds maximum length")
    return normalized


def _coerce_bool(value: Any, *, field_name: str) -> bool:
    """Validate explicit boolean flags."""
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _coerce_finite_float(value: Any, *, field_name: str) -> float:
    """Validate a finite numeric scalar."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field_name} must be a number")
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(f"{field_name} must be finite")
    return numeric_value


def _coerce_non_negative_float(value: Any, *, field_name: str) -> float:
    """Validate a finite non-negative numeric scalar."""
    numeric_value = _coerce_finite_float(value, field_name=field_name)
    if numeric_value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return numeric_value


def _coerce_positive_float(value: Any, *, field_name: str) -> float:
    """Validate a finite positive numeric scalar."""
    numeric_value = _coerce_finite_float(value, field_name=field_name)
    if numeric_value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return numeric_value


def _coerce_status_code(value: Any) -> int:
    """Validate an HTTP status code boundary."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("status_code must be an integer")
    numeric_value = float(value)
    if not math.isfinite(numeric_value) or not numeric_value.is_integer():
        raise ValueError("status_code must be a finite integer")
    status_code = int(value)
    if status_code < 100 or status_code > 599:
        raise ValueError("status_code must be between 100 and 599")
    return status_code


def _coerce_error_threshold(value: Any) -> float:
    """Validate error-rate threshold bounds."""
    threshold = _coerce_non_negative_float(value, field_name="threshold")
    if threshold > 1:
        raise ValueError("threshold must be between 0 and 1")
    return threshold
