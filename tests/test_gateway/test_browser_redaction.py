"""Browser worker secret-redaction tests.

Tests: secret-bearing query/fragment values and value-shaped secrets in page
text are masked in worker observations, signed receipts, and responses, while
non-sensitive content, URL host/path, and domain allowlisting are preserved.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.browser_redaction import (  # noqa: E402
    MASK,
    redact_observation,
    redact_text_secrets,
    redact_url_query_secrets,
)
from gateway.browser_worker import (  # noqa: E402
    BrowserActionObservation,
    BrowserWorkerPolicy,
    browser_action_request_from_mapping,
    execute_browser_request,
)


class _SecretAdapter:
    """Adapter fixture that emits secret-bearing observations."""

    def __init__(self, *, network_requests, extracted_text="Mullusi docs", url_after=""):
        self._network_requests = network_requests
        self._extracted_text = extracted_text
        self._url_after = url_after

    def perform(self, request):
        return BrowserActionObservation(
            succeeded=True,
            url_before=request.url or "https://docs.mullusi.com",
            url_after=self._url_after or "https://docs.mullusi.com/after",
            screenshot_before_ref="evidence:screenshot-before",
            screenshot_after_ref="evidence:screenshot-after",
            extracted_text=self._extracted_text,
            network_requests=self._network_requests,
        )


def _request(**overrides):
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
    return browser_action_request_from_mapping(payload)


# --- URL query/fragment redaction ---


class TestRedactUrl:
    def test_token_value_masked(self):
        out = redact_url_query_secrets("https://docs.mullusi.com/cb?code=ABC123&q=hello")
        assert "ABC123" not in out
        assert "q=hello" in out
        assert "docs.mullusi.com/cb" in out

    def test_multiple_secret_params_masked(self):
        url = "https://x.io/p?access_token=t1&api_key=k2&password=p3&page=2"
        out = redact_url_query_secrets(url)
        for secret in ("t1", "k2", "p3"):
            assert secret not in out
        assert "page=2" in out

    def test_fragment_secrets_masked(self):
        # OAuth implicit flow places the token in the fragment.
        out = redact_url_query_secrets("https://x.io/cb#access_token=SECRET&state=ok")
        assert "SECRET" not in out
        assert "state=ok" in out

    def test_scheme_and_host_preserved(self):
        out = redact_url_query_secrets("https://docs.mullusi.com/a/b?token=z")
        assert out.startswith("https://docs.mullusi.com/a/b")

    def test_url_without_query_unchanged(self):
        url = "https://docs.mullusi.com/reference"
        assert redact_url_query_secrets(url) == url

    def test_empty_unchanged(self):
        assert redact_url_query_secrets("") == ""


# --- Text redaction ---


class TestRedactText:
    def test_card_number_masked(self):
        assert "4111" not in redact_text_secrets("pay 4111 1111 1111 1111 now")

    def test_ssn_masked(self):
        assert "123-45-6789" not in redact_text_secrets("ssn 123-45-6789")

    def test_plain_text_unchanged(self):
        text = "Mullusi reference text"
        assert redact_text_secrets(text) == text

    def test_empty_unchanged(self):
        assert redact_text_secrets("") == ""


# --- Observation redaction ---


class TestRedactObservation:
    def test_observation_urls_and_text_masked(self):
        obs = BrowserActionObservation(
            succeeded=True,
            url_before="https://x.io/login?password=p",
            url_after="https://x.io/cb?code=SECRET",
            extracted_text="card 4111 1111 1111 1111",
            network_requests=("https://api.x.io/v1?api_key=KEY", "https://x.io/plain"),
        )
        red = redact_observation(obs)
        assert "p" not in red.url_before.split("password=")[1]
        assert "SECRET" not in red.url_after
        assert "4111" not in red.extracted_text
        assert "KEY" not in red.network_requests[0]
        assert red.network_requests[1] == "https://x.io/plain"

    def test_non_sensitive_observation_unchanged(self):
        obs = BrowserActionObservation(
            succeeded=True,
            url_before="https://docs.mullusi.com",
            url_after="https://docs.mullusi.com/after",
            extracted_text="Mullusi docs",
            network_requests=("https://docs.mullusi.com/reference",),
        )
        assert redact_observation(obs) == obs


# --- Worker integration ---


class TestWorkerRedaction:
    def test_response_and_receipt_redacted(self):
        request = _request(request_id="browser-secret")
        adapter = _SecretAdapter(
            network_requests=("https://docs.mullusi.com/cb?code=LEAK",),
            extracted_text="SSN on file 123-45-6789",
        )
        response = execute_browser_request(
            request, adapter=adapter, policy=BrowserWorkerPolicy(),
        )
        # Page text scrubbed in both result and the hash that commits to it.
        assert "123-45-6789" not in response.result["extracted_text"]
        # Network URL secret masked but domain preserved (still allowlisted).
        assert "LEAK" not in response.result["network_requests"][0]
        assert "docs.mullusi.com/cb" in response.result["network_requests"][0]
        assert "LEAK" not in response.receipt.network_requests[0]
        assert response.status == "succeeded"

    def test_text_hash_commits_to_redacted_text(self):
        import hashlib

        request = _request(request_id="browser-hash")
        adapter = _SecretAdapter(
            network_requests=("https://docs.mullusi.com/reference",),
            extracted_text="card 4111 1111 1111 1111",
        )
        response = execute_browser_request(
            request, adapter=adapter, policy=BrowserWorkerPolicy(),
        )
        redacted = redact_text_secrets("card 4111 1111 1111 1111")
        expected = hashlib.sha256(redacted.encode("utf-8", errors="replace")).hexdigest()
        assert response.result["text_hash"] == expected

    def test_non_sensitive_flow_unaffected(self):
        request = _request(request_id="browser-clean")
        adapter = _SecretAdapter(
            network_requests=("https://docs.mullusi.com/reference",),
            extracted_text="Mullusi docs",
        )
        response = execute_browser_request(
            request, adapter=adapter, policy=BrowserWorkerPolicy(),
        )
        assert response.result["extracted_text"] == "Mullusi docs"
        assert response.result["network_requests"] == ["https://docs.mullusi.com/reference"]
        assert response.status == "succeeded"
        assert MASK  # sanity: mask constant exported
