"""Tests for the optional governed swarm FastAPI adapter.

Purpose: verify route contracts and handler envelopes without requiring FastAPI
as a core dependency.
Governance scope: HTTP-shaped adapter must preserve runtime validation,
persistence, lookup, and rejection semantics.
Dependencies: mcoi_runtime.swarm.fastapi_router.
Invariants: route specs are stable, handlers remain governed, and missing
FastAPI is explicit when router creation is requested.
"""

from __future__ import annotations

from mcoi_runtime.swarm import InvoiceSwarmRuntime, SwarmFastAPIAdapter, create_fastapi_router


def _payload(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "run_id": "run_http_invoice_001",
        "goal_id": "goal_http_invoice_001",
        "tenant_id": "tenant_a",
        "invoice_ref": "invoice_http_001",
        "invoice_amount_usd": "77.00",
        "vendor_verified": True,
        "duplicate_found": False,
        "budget_available": True,
        "policy_requires_approval": True,
        "human_approved": True,
    }
    value.update(overrides)
    return value


def test_fastapi_adapter_route_specs_are_stable() -> None:
    specs = SwarmFastAPIAdapter.route_specs()

    assert len(specs) == 3
    assert [(spec.method, spec.path, spec.handler_name) for spec in specs] == [
        ("POST", "/api/v1/swarm/invoice-runs", "run_invoice"),
        ("GET", "/api/v1/swarm/runs/{run_id}", "get_run"),
        ("GET", "/api/v1/swarm/runs", "list_runs"),
    ]
    assert all(spec.purpose for spec in specs)


def test_fastapi_adapter_handlers_preserve_governed_runtime_envelopes(tmp_path) -> None:
    runtime = InvoiceSwarmRuntime.from_path(tmp_path / "swarm-runs.jsonl")
    adapter = SwarmFastAPIAdapter(runtime)

    run_envelope = adapter.run_invoice(_payload())
    get_envelope = adapter.get_run("run_http_invoice_001")
    list_envelope = adapter.list_runs()

    assert run_envelope["governed"] is True
    assert run_envelope["ok"] is True
    assert run_envelope["status"] == "closed"
    assert get_envelope["payload"]["record"]["run_id"] == "run_http_invoice_001"
    assert list_envelope["payload"]["count"] == 1


def test_fastapi_adapter_rejections_do_not_persist(tmp_path) -> None:
    runtime = InvoiceSwarmRuntime.from_path(tmp_path / "swarm-runs.jsonl")
    adapter = SwarmFastAPIAdapter(runtime)

    envelope = adapter.run_invoice(_payload(run_id="run_bad", invoice_amount_usd="-1"))

    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "rejected"
    assert "invoice_amount_usd" in envelope["error"]
    assert runtime.audit_store.count == 0


def test_create_fastapi_router_reports_missing_dependency(tmp_path) -> None:
    runtime = InvoiceSwarmRuntime.from_path(tmp_path / "swarm-runs.jsonl")

    try:
        router = create_fastapi_router(runtime)
    except RuntimeError as exc:
        assert "FastAPI is required" in str(exc)
    else:
        assert router is not None
