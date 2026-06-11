"""Purpose: verify HTTP response request-id witness middleware.
Governance scope: HTTP boundary witness tests only.
Dependencies: FastAPI test client and governed server bootstrap.
Invariants: request ids are server-owned, per-request, and present on bounded responses.
"""

from __future__ import annotations

from mcoi_runtime.app.server_http import REQUEST_ID_HEADER, REQUEST_ID_PREFIX


def _assert_request_id_shape(request_id: str) -> None:
    request_id_hex = request_id.removeprefix(REQUEST_ID_PREFIX)

    assert request_id.startswith(REQUEST_ID_PREFIX)
    assert len(request_id) == len(REQUEST_ID_PREFIX) + 32
    assert all(character in "0123456789abcdef" for character in request_id_hex)


def test_health_response_emits_request_unique_id(test_client) -> None:
    first_response = test_client.get("/health")
    second_response = test_client.get("/health")

    first_request_id = first_response.headers[REQUEST_ID_HEADER]
    second_request_id = second_response.headers[REQUEST_ID_HEADER]

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_request_id != second_request_id
    _assert_request_id_shape(first_request_id)
    _assert_request_id_shape(second_request_id)


def test_inbound_request_id_does_not_control_response_witness(test_client) -> None:
    spoofed_request_id = "req-client-controlled"
    response = test_client.get("/health", headers={REQUEST_ID_HEADER: spoofed_request_id})
    response_request_id = response.headers[REQUEST_ID_HEADER]

    assert response.status_code == 200
    assert response_request_id != spoofed_request_id
    assert response_request_id.startswith(REQUEST_ID_PREFIX)
    _assert_request_id_shape(response_request_id)


def test_governance_rejection_emits_request_id(test_client) -> None:
    response = test_client.post(
        "/api/v1/workflow/execute",
        content="{",
        headers={"content-type": "application/json"},
    )
    response_request_id = response.headers[REQUEST_ID_HEADER]
    body = response.json()

    assert response.status_code == 403
    assert body["governed"] is True
    assert body["guard"] == "request_body"
    assert response_request_id.startswith(REQUEST_ID_PREFIX)
    _assert_request_id_shape(response_request_id)


def test_cors_preflight_emits_request_id(test_client) -> None:
    response = test_client.options(
        "/health",
        headers={
            "Origin": "https://dashboard.mullusi.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    response_request_id = response.headers[REQUEST_ID_HEADER]

    assert response.status_code in {200, 400}
    assert REQUEST_ID_HEADER in response.headers
    assert response.headers.get("vary") == "Origin"
    _assert_request_id_shape(response_request_id)
