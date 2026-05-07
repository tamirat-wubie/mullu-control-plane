"""Browser worker contract tests.

Tests: signed restricted browser requests, domain policy, approval gates, and
receipt-bearing observations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.browser_worker import (  # noqa: E402
    BrowserActionObservation,
    BrowserWorkerPolicy,
    create_browser_worker_app,
    execute_browser_request,
    browser_action_request_from_mapping,
)
from gateway.capability_isolation import sign_capability_payload, verify_capability_signature  # noqa: E402


class FakeBrowserAdapter:
    """Browser adapter fixture that returns deterministic observations."""

    def __init__(
        self,
        *,
        network_requests: tuple[str, ...] = ("https://docs.mullusi.com/reference",),
        url_after: str = "",
        screenshot_before_ref: str = "evidence:screenshot-before",
        screenshot_after_ref: str = "evidence:screenshot-after",
    ) -> None:
        self.requests = []
        self._network_requests = network_requests
        self._url_after = url_after
        self._screenshot_before_ref = screenshot_before_ref
        self._screenshot_after_ref = screenshot_after_ref

    def perform(self, request):
        self.requests.append(request)
        return BrowserActionObservation(
            succeeded=True,
            url_before=request.url or str(request.metadata.get("url_before", "https://docs.mullusi.com")),
            url_after=self._url_after or request.url or "https://docs.mullusi.com/after",
            screenshot_before_ref=self._screenshot_before_ref,
            screenshot_after_ref=self._screenshot_after_ref,
            extracted_text="Mullusi docs",
            network_requests=self._network_requests,
        )


def _payload(**overrides) -> dict:
    payload = {
        "request_id": "browser-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "browser.open",
        "action": "browser.open",
        "url": "https://docs.mullusi.com/reference",
        "selector": "",
        "text": "",
        "approval_id": "",
        "metadata": {},
    }
    payload.update(overrides)
    return payload


def _body(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_browser_worker_executes_signed_open_request() -> None:
    secret = "browser-secret"
    adapter = FakeBrowserAdapter()
    app = create_browser_worker_app(adapter=adapter, signing_secret=secret)
    client = TestClient(app)
    body = _body(_payload())

    response = client.post(
        "/browser/execute",
        content=body,
        headers={"X-Mullu-Browser-Signature": sign_capability_payload(body, secret)},
    )

    assert response.status_code == 200
    assert verify_capability_signature(
        response.content,
        response.headers["X-Mullu-Browser-Response-Signature"],
        secret,
    )
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["receipt"]["capability_id"] == "browser.open"
    assert payload["receipt"]["url_after"] == "https://docs.mullusi.com/reference"
    assert payload["receipt"]["screenshot_after_ref"] == "evidence:screenshot-after"
    assert payload["receipt"]["forbidden_effects_observed"] is False
    assert payload["receipt"]["verification_status"] == "passed"
    assert payload["receipt"]["evidence_refs"][0].startswith("browser_action:")
    assert adapter.requests[0].tenant_id == "tenant-1"


def test_browser_worker_rejects_bad_signature() -> None:
    app = create_browser_worker_app(adapter=FakeBrowserAdapter(), signing_secret="browser-secret")
    client = TestClient(app)

    response = client.post(
        "/browser/execute",
        content=_body(_payload()),
        headers={"X-Mullu-Browser-Signature": "hmac-sha256:bad"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid browser request signature"


def test_browser_worker_blocks_disallowed_domain_before_adapter() -> None:
    secret = "browser-secret"
    adapter = FakeBrowserAdapter()
    app = create_browser_worker_app(adapter=adapter, signing_secret=secret)
    client = TestClient(app)
    body = _body(_payload(url="https://example.com", request_id="browser-request-domain"))

    response = client.post(
        "/browser/execute",
        content=body,
        headers={"X-Mullu-Browser-Signature": sign_capability_payload(body, secret)},
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "blocked"
    assert payload["error"] == "browser URL is outside allowed domains"
    assert payload["receipt"]["verification_status"] == "blocked"
    assert adapter.requests == []


def test_browser_worker_submit_requires_approval() -> None:
    request = browser_action_request_from_mapping(
        _payload(
            request_id="browser-request-submit",
            capability_id="browser.submit",
            action="browser.submit",
            url="",
            selector="form button[type=submit]",
            metadata={"url_before": "https://docs.mullusi.com/form"},
        )
    )

    response = execute_browser_request(
        request,
        adapter=FakeBrowserAdapter(),
        policy=BrowserWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "browser action requires approval"
    assert response.receipt.capability_id == "browser.submit"
    assert response.receipt.element_selector_hash
    assert response.receipt.verification_status == "blocked"


def test_browser_worker_submit_with_approval_executes() -> None:
    request = browser_action_request_from_mapping(
        _payload(
            request_id="browser-request-submit-approved",
            capability_id="browser.submit",
            action="browser.submit",
            url="",
            selector="form button[type=submit]",
            approval_id="approval-1",
            metadata={"url_before": "https://docs.mullusi.com/form"},
        )
    )

    response = execute_browser_request(
        request,
        adapter=FakeBrowserAdapter(),
        policy=BrowserWorkerPolicy(),
    )

    assert response.status == "succeeded"
    assert response.receipt.approval_id == "approval-1"
    assert response.receipt.verification_status == "passed"
    assert response.receipt.screenshot_after_ref == "evidence:screenshot-after"


def test_browser_worker_fails_forbidden_network_observation() -> None:
    request = browser_action_request_from_mapping(_payload(request_id="browser-request-network"))

    response = execute_browser_request(
        request,
        adapter=FakeBrowserAdapter(network_requests=("https://docs.mullusi.com", "https://example.com")),
        policy=BrowserWorkerPolicy(),
    )

    assert response.status == "failed"
    assert response.receipt.forbidden_effects_observed is True
    assert response.receipt.verification_status == "failed"
    assert response.receipt.network_requests == ("https://docs.mullusi.com", "https://example.com")


def test_browser_worker_fails_forbidden_url_after_observation() -> None:
    request = browser_action_request_from_mapping(_payload(request_id="browser-request-url-after"))

    response = execute_browser_request(
        request,
        adapter=FakeBrowserAdapter(url_after="https://example.com/redirect"),
        policy=BrowserWorkerPolicy(),
    )

    assert response.status == "failed"
    assert response.error == "browser verification failed"
    assert response.receipt.url_before == "https://docs.mullusi.com/reference"
    assert response.receipt.url_after == "https://example.com/redirect"
    assert response.receipt.forbidden_effects_observed is True
    assert response.receipt.verification_status == "failed"


def test_browser_worker_fails_missing_screenshot_evidence() -> None:
    request = browser_action_request_from_mapping(_payload(request_id="browser-request-no-screenshot"))

    response = execute_browser_request(
        request,
        adapter=FakeBrowserAdapter(screenshot_before_ref="", screenshot_after_ref=""),
        policy=BrowserWorkerPolicy(),
    )

    assert response.status == "failed"
    assert response.error == "browser observation missing screenshot evidence"
    assert response.receipt.screenshot_before_ref == ""
    assert response.receipt.screenshot_after_ref == ""
    assert response.receipt.forbidden_effects_observed is False
    assert response.receipt.verification_status == "failed"
