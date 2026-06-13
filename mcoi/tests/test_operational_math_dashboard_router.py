"""Purpose: verify operational mathematics dashboard routing.
Governance scope: read-only FastAPI projection for operational math receipt posture.
Dependencies: server TestClient and registered operational math observability source.
Invariants: the route is governed, JSON-safe, and never grants execution authority.
"""

from __future__ import annotations


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
