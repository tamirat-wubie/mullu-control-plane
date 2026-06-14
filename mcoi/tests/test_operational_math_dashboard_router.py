"""Purpose: verify operational mathematics dashboard routing.
Governance scope: read-only FastAPI projection for operational math receipt posture.
Dependencies: server TestClient and registered operational math observability source.
Invariants: the route is governed, JSON-safe, and never grants execution authority.
"""

from __future__ import annotations

from mcoi_runtime.app.routers.ops.summaries import build_operational_math_dashboard_payload


class FakeMetrics:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def inc(self, name: str) -> None:
        self.calls.append(name)


class FakeObservability:
    def __init__(self, projection: object) -> None:
        self.projection = projection

    def collect(self, source_name: str) -> object:
        return self.projection


def test_operational_math_dashboard_route_exposes_read_only_projection(test_client) -> None:
    response = test_client.get("/api/v1/dashboard/operational-math")
    payload = response.json()
    projection = payload["operational_math"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert projection["source"] == "operational_math"
    assert projection["governed"] is True
    assert projection["total_receipts"] >= 0
    assert projection["requires_operator_review"] in (True, False)
    assert payload["telemetry"]["source_available"] is True
    assert payload["telemetry"]["source_health"] == "normal"
    assert payload["requires_operator_review"] in (True, False)


def test_operational_math_dashboard_payload_marks_review_signal() -> None:
    metrics = FakeMetrics()

    payload = build_operational_math_dashboard_payload(
        observability=FakeObservability(
            {
                "source": "operational_math",
                "governed": True,
                "requires_operator_review": True,
                "review_signal_count": 1,
            }
        ),
        metrics=metrics,
    )

    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["requires_operator_review"] is True
    assert payload["telemetry"]["source_available"] is True
    assert payload["telemetry"]["source_health"] == "normal"
    assert payload["telemetry"]["reason_refs"] == ["operational_math_receipt_review_required"]
    assert metrics.calls == ["requests_governed"]


def test_operational_math_dashboard_payload_marks_missing_source_degraded() -> None:
    payload = build_operational_math_dashboard_payload(
        observability=FakeObservability({"error": "observability source unavailable"}),
    )

    assert payload["operational_math"]["error"] == "observability source unavailable"
    assert payload["telemetry"]["source_available"] is False
    assert payload["telemetry"]["source_health"] == "degraded"
    assert payload["requires_operator_review"] is True
    assert payload["telemetry"]["reason_refs"] == ["operational_math_observability_source_degraded"]


def test_operational_math_dashboard_payload_bounds_non_object_projection() -> None:
    payload = build_operational_math_dashboard_payload(
        observability=FakeObservability(["not", "a", "mapping"]),
    )

    assert payload["operational_math"]["error"] == "observability source returned non-object"
    assert payload["telemetry"]["source_available"] is False
    assert payload["telemetry"]["source_health"] == "degraded"
    assert payload["requires_operator_review"] is True
    assert payload["execution_allowed"] is False
