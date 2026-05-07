"""v3.13.1 substrate metrics — soak telemetry contract.

Asserts:
  - both grid paths record lookups
  - per-request mixing is detected at request close
  - legacy-only and canonical-only requests are distinguished
  - background lookups (no correlation) do not corrupt per-request stats
  - prometheus exporter export is non-empty and well-shaped
  - request_correlation bridge wires both start() and complete()
"""
from __future__ import annotations

import pytest

from mcoi_runtime.substrate.metrics import (
    CANONICAL_GRID_PATH,
    LEGACY_MATRIX_PATH,
    REGISTRY,
    bind_correlation,
    current_correlation,
)


@pytest.fixture(autouse=True)
def _reset_registry():
    REGISTRY.reset()
    bind_correlation("")
    yield
    REGISTRY.reset()
    bind_correlation("")


def test_canonical_grid_records_lookup():
    from mcoi_runtime.substrate.mfidel import fidel_at

    bind_correlation("test-cid-canonical")
    fidel_at(1, 1)
    fidel_at(4, 3)

    snap = REGISTRY.snapshot()
    assert snap.canonical_lookups_total == 2
    assert snap.legacy_lookups_total == 0


def test_legacy_matrix_records_lookup():
    from mcoi_runtime.core.mfidel_matrix import MfidelMatrix

    bind_correlation("test-cid-legacy")
    MfidelMatrix.lookup(1, 1)
    MfidelMatrix.lookup(2, 3)

    snap = REGISTRY.snapshot()
    assert snap.legacy_lookups_total == 2
    assert snap.canonical_lookups_total == 0


def test_legacy_only_request_classified_at_close():
    from mcoi_runtime.core.mfidel_matrix import MfidelMatrix

    bind_correlation("req-legacy-only")
    MfidelMatrix.lookup(5, 2)
    verdict = REGISTRY.close_request("req-legacy-only")

    assert verdict == "legacy_only"
    snap = REGISTRY.snapshot()
    assert snap.requests_legacy_only == 1
    assert snap.requests_canonical_only == 0
    assert snap.requests_mixed == 0


def test_canonical_only_request_classified_at_close():
    from mcoi_runtime.substrate.mfidel import fidel_at

    bind_correlation("req-canonical-only")
    fidel_at(7, 4)
    verdict = REGISTRY.close_request("req-canonical-only")

    assert verdict == "canonical_only"
    snap = REGISTRY.snapshot()
    assert snap.requests_canonical_only == 1
    assert snap.requests_legacy_only == 0
    assert snap.requests_mixed == 0


def test_mixed_request_is_flagged():
    """The signal that gates Option 1b convergence — must not be silent."""
    from mcoi_runtime.core.mfidel_matrix import MfidelMatrix
    from mcoi_runtime.substrate.mfidel import fidel_at

    bind_correlation("req-mixed")
    MfidelMatrix.lookup(1, 1)
    fidel_at(1, 1)
    verdict = REGISTRY.close_request("req-mixed")

    assert verdict == "mixed", "mixed-path requests must be detected"
    snap = REGISTRY.snapshot()
    assert snap.requests_mixed == 1
    assert snap.legacy_lookups_total == 1
    assert snap.canonical_lookups_total == 1


def test_background_lookup_without_correlation_does_not_pollute_per_request():
    from mcoi_runtime.substrate.mfidel import fidel_at

    bind_correlation("")  # no active request
    fidel_at(2, 2)

    snap = REGISTRY.snapshot()
    # global counter still moves
    assert snap.canonical_lookups_total == 1
    # but no per-request bucket was created
    assert snap.requests_legacy_only == 0
    assert snap.requests_canonical_only == 0
    assert snap.requests_mixed == 0
    assert snap.requests_closed_total == 0


def test_close_unknown_correlation_id_returns_none():
    verdict = REGISTRY.close_request("never-touched-anything")
    assert verdict == "none"
    assert REGISTRY.snapshot().requests_closed_total == 0


def test_close_with_empty_correlation_id_returns_none():
    assert REGISTRY.close_request("") == "none"


def test_invalid_path_rejected():
    with pytest.raises(ValueError):
        REGISTRY.record_lookup("not_a_real_path")


def test_correlation_manager_bridges_to_substrate():
    """End-to-end: starting a CorrelationContext stamps substrate's contextvar,
    and completing it closes the substrate per-request bucket.
    """
    from mcoi_runtime.core.request_correlation import CorrelationManager
    from mcoi_runtime.substrate.mfidel import fidel_at

    mgr = CorrelationManager(clock=lambda: "2026-04-26T00:00:00Z")
    ctx = mgr.start(tenant_id="tenant-test", endpoint="/test")
    assert current_correlation() == ctx.correlation_id

    fidel_at(1, 1)
    fidel_at(2, 2)
    mgr.complete(ctx.correlation_id)

    assert current_correlation() == ""
    snap = REGISTRY.snapshot()
    assert snap.requests_canonical_only == 1
    assert snap.canonical_lookups_total == 2


def test_mode_distribution_records():
    REGISTRY.record_mode("unset")
    REGISTRY.record_mode("unset")
    REGISTRY.record_mode("llm_only")  # reserved for v4.1+; recorded if supplied

    snap = REGISTRY.snapshot()
    assert snap.mode_distribution["unset"] == 2
    assert snap.mode_distribution["llm_only"] == 1


def test_export_to_prometheus_emits_expected_gauges():
    """Verify the exporter contract without importing the real PrometheusExporter."""
    from mcoi_runtime.substrate.metrics import export_to_prometheus
    from mcoi_runtime.substrate.mfidel import fidel_at

    bind_correlation("req-x")
    fidel_at(1, 1)
    REGISTRY.close_request("req-x")
    REGISTRY.record_mode("unset")

    captured: list[tuple[str, float, dict]] = []

    class FakeExporter:
        def set_gauge(self, name, value, **labels):
            captured.append((name, value, labels))

    export_to_prometheus(FakeExporter())

    names = {row[0] for row in captured}
    assert "substrate_mfidel_lookups_total" in names
    assert "substrate_requests_total" in names
    assert "substrate_requests_open" in names
    assert "substrate_musia_mode_total" in names

    # Verify the canonical-only bucket got the request
    canonical_only_rows = [
        r for r in captured
        if r[0] == "substrate_requests_total" and r[2].get("bucket") == "canonical_only"
    ]
    assert len(canonical_only_rows) == 1
    assert canonical_only_rows[0][1] == 1


def test_lookups_outside_grid_bounds_still_safe():
    """Lookup helper validations precede metrics increment — failure path
    must not increment counters."""
    from mcoi_runtime.substrate.mfidel import fidel_at
    from mcoi_runtime.core.mfidel_matrix import MfidelMatrix

    with pytest.raises(ValueError):
        fidel_at(99, 1)
    with pytest.raises(ValueError):
        MfidelMatrix.lookup(99, 1)

    snap = REGISTRY.snapshot()
    assert snap.legacy_lookups_total == 0
    assert snap.canonical_lookups_total == 0


def test_glyph_to_position_records_legacy_lookup():
    from mcoi_runtime.core.mfidel_matrix import MfidelMatrix

    bind_correlation("req-glyph")
    pos = MfidelMatrix.glyph_to_position("ሀ")
    assert pos == (1, 1)
    REGISTRY.close_request("req-glyph")

    snap = REGISTRY.snapshot()
    assert snap.legacy_lookups_total == 1
    assert snap.requests_legacy_only == 1


def test_vectorize_records_legacy_lookup():
    from mcoi_runtime.core.mfidel_matrix import MfidelMatrix

    bind_correlation("req-vec")
    vec = MfidelMatrix.vectorize("ሀለ")
    assert vec.dimension == 272
    REGISTRY.close_request("req-vec")

    snap = REGISTRY.snapshot()
    # vectorize records once at entry; it does not call lookup() internally
    assert snap.legacy_lookups_total == 1
    assert snap.requests_legacy_only == 1
