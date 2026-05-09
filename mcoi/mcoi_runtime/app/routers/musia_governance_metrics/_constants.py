"""Constants for governance chain observability."""
from __future__ import annotations


# Surfaces the chain can gate.
SURFACE_WRITE = "write"
SURFACE_DOMAIN_RUN = "domain_run"
_VALID_SURFACES = frozenset({SURFACE_WRITE, SURFACE_DOMAIN_RUN})

# Verdicts the chain can return.
VERDICT_ALLOWED = "allowed"
VERDICT_DENIED = "denied"
VERDICT_EXCEPTION = "exception"
_VALID_VERDICTS = frozenset({VERDICT_ALLOWED, VERDICT_DENIED, VERDICT_EXCEPTION})

# Cap on the rejection-event ring buffer. ~50 is plenty for forensic
# spot-checks; operators wanting full history scrape the metrics into
# a TSDB at intervals.
MAX_RECENT_REJECTIONS = 50

# Latency histogram bucket boundaries in seconds. Picked from measured
# v4.17 benchmark numbers (5–16μs typical, 41μs p99) plus headroom
# for pathological cases up to 5ms (a guard doing blocking I/O would
# fall here). Boundaries are cumulative ("less than or equal to").
# +Inf is implied by the histogram convention.
DEFAULT_LATENCY_BUCKETS_SECONDS: tuple[float, ...] = (
    0.000_001,   # 1μs   — well below any real chain
    0.000_005,   # 5μs   — typical empty-bridge cost
    0.000_010,   # 10μs  — typical 1-guard chain
    0.000_025,   # 25μs  — typical 5-guard chain
    0.000_050,   # 50μs  — measured p99 ceiling
    0.000_100,   # 100μs — first sign of slow guard
    0.000_250,   # 250μs
    0.000_500,   # 500μs
    0.001,       # 1ms   — clearly degraded
    0.002_5,     # 2.5ms
    0.005,       # 5ms   — pathological (blocking I/O in guard?)
)
