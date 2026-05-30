"""Φ_gov cascade-coverage metric.

Records whether Phase 3 (the dependency cascade / per-type invariant
validators) actually ran or was skipped for each construct write. A skip
happens when the delta target is not yet in the graph (e.g. a create) — which
is the silent reason the validators do not cover the live create path. This
metric makes that visible. Dedicated field; never enters chain aggregates.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.app.routers.musia_governance_metrics import REGISTRY


@pytest.fixture(autouse=True)
def _reset_metrics():
    REGISTRY.reset()
    yield
    REGISTRY.reset()


def test_ran_and_skipped_counted_separately():
    REGISTRY.record_phi_gov_cascade_coverage(ran=True)
    REGISTRY.record_phi_gov_cascade_coverage(ran=False)
    REGISTRY.record_phi_gov_cascade_coverage(ran=False)
    snap = REGISTRY.snapshot()
    assert snap.phi_gov_cascade_coverage == {"ran": 1, "skipped": 2}


def test_coverage_does_not_touch_chain_aggregates():
    REGISTRY.record_phi_gov_cascade_coverage(ran=False)
    snap = REGISTRY.snapshot()
    assert snap.total_runs() == 0
    assert snap.total_denials() == 0
    assert snap.recent_rejections == ()
    assert snap.denials_by_guard == {}


def test_coverage_in_prometheus_and_json():
    REGISTRY.record_phi_gov_cascade_coverage(ran=True)
    REGISTRY.record_phi_gov_cascade_coverage(ran=False)
    snap = REGISTRY.snapshot()
    body = snap.to_prometheus_text()
    assert 'mullu_phi_gov_cascade_coverage_total{outcome="ran"} 1' in body
    assert 'mullu_phi_gov_cascade_coverage_total{outcome="skipped"} 1' in body
    assert snap.as_dict()["phi_gov_cascade_coverage"] == {"ran": 1, "skipped": 1}


def test_governed_create_records_skipped():
    """End-to-end: a create goes through _governed_write; the cascade is skipped
    (construct not yet in the graph), so coverage records 'skipped'. This is the
    live-path coverage gap, now observable."""
    from mcoi_runtime.app.routers.constructs._governance import _governed_write
    from mcoi_runtime.substrate.constructs import State
    from mcoi_runtime.substrate.registry_store import STORE

    state = STORE.get_or_create("cov-tenant")
    s = State(configuration={"x": 1})
    _governed_write(s, "create", depends_on=(), state=state)

    snap = REGISTRY.snapshot()
    assert snap.phi_gov_cascade_coverage.get("skipped", 0) >= 1
    assert snap.phi_gov_cascade_coverage.get("ran", 0) == 0
