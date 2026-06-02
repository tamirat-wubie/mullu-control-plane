"""Tests for governed HTTP JSON request body support.

Purpose: verify that POST JSON bodies are deterministic, bounded, and
receipt-bound without storing raw request bodies.
Governance scope: HttpConnector transport hardening only.
"""

from __future__ import annotations

import hashlib
import json
import unittest.mock as mock

from mcoi_runtime.adapters.http_connector import HttpConnector, HttpConnectorConfig
from mcoi_runtime.contracts._shared_enums import EffectClass, TrustClass
from mcoi_runtime.contracts.integration import ConnectorDescriptor, ConnectorStatus


def _clock() -> str:
    return "2026-01-01T00:00:00+00:00"


def _descriptor() -> ConnectorDescriptor:
    return ConnectorDescriptor(
        connector_id="conn-json",
        name="json connector",
        provider="test-provider",
        effect_class=EffectClass.EXTERNAL_WRITE,
        trust_class=TrustClass.BOUNDED_EXTERNAL,
        credential_scope_id="scope-json",
        enabled=True,
    )


def _fake_response(body: bytes = b"ok"):
    response = mock.MagicMock()
    response.status = 200
    response.headers = {"Content-Type": "text/plain"}
    response.read.side_effect = [body, b""]
    response.__enter__ = lambda s: s
    response.__exit__ = mock.MagicMock(return_value=False)
    return response


def _body_digest(body: object) -> str:
    encoded = json.dumps(
        body,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _expected_request_hash(*, url: str, method: str, body_digest: str) -> str:
    payload = {
        "url": url,
        "method": method,
        "headers": [],
        "body_digest": body_digest,
    }
    return hashlib.sha256(str(payload).encode("utf-8", errors="replace")).hexdigest()


def _invoke_with_fake_opener(connector: HttpConnector, request: dict):
    fake_opener = mock.MagicMock()
    fake_opener.open = mock.MagicMock(return_value=_fake_response())
    with (
        mock.patch(
            "mcoi_runtime.adapters.http_connector._resolve_and_check",
            return_value=(False, "93.184.216.34"),
        ),
        mock.patch(
            "mcoi_runtime.adapters.http_connector._build_pinned_opener",
            return_value=fake_opener,
        ),
    ):
        result = connector.invoke(_descriptor(), request)
    return result, fake_opener


def test_post_json_body_is_encoded_deterministically_and_digested() -> None:
    connector = HttpConnector(
        clock=_clock,
        config=HttpConnectorConfig(
            allowed_methods=("GET", "POST"),
            allowed_content_types=("text/plain",),
            allowed_headers=("Authorization",),
        ),
    )

    body = {"z": 1, "a": [True, None, "x"]}
    result, fake_opener = _invoke_with_fake_opener(
        connector,
        {
            "url": "https://example.com/submit",
            "method": "POST",
            "headers": {"Authorization": "Bearer secret", "X-Ignore": "drop"},
            "json_body": body,
        },
    )

    encoded = json.dumps(
        body,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    sent_request = fake_opener.open.call_args.args[0]

    assert result.status is ConnectorStatus.SUCCEEDED
    assert sent_request.data == encoded
    assert sent_request.get_header("Content-type") == "application/json"
    assert sent_request.get_header("Authorization") == "Bearer secret"
    assert sent_request.get_header("X-ignore") is None
    assert result.metadata["request_body_digest"] == digest
    receipt = result.metadata["connector_receipt"]
    assert receipt["method"] == "POST"
    assert receipt["url_hash"] != "https://example.com/submit"
    assert digest not in receipt["request_hash"]
    assert "json_body" not in receipt


def test_json_body_is_rejected_for_get() -> None:
    connector = HttpConnector(clock=_clock)

    result = connector.invoke(
        _descriptor(),
        {"url": "https://example.com/read", "method": "GET", "json_body": {"x": 1}},
    )

    assert result.status is ConnectorStatus.FAILED
    assert result.error_code == "json_body_not_allowed_for_method:GET"


def test_json_body_requires_allowed_post_method() -> None:
    connector = HttpConnector(clock=_clock, config=HttpConnectorConfig(allowed_methods=("GET",)))

    result = connector.invoke(
        _descriptor(),
        {"url": "https://example.com/submit", "method": "POST", "json_body": {"x": 1}},
    )

    assert result.status is ConnectorStatus.FAILED
    assert result.error_code == "method_not_allowed:POST"


def test_json_body_too_large_is_rejected_before_network() -> None:
    connector = HttpConnector(
        clock=_clock,
        config=HttpConnectorConfig(allowed_methods=("POST",), max_request_body_bytes=8),
    )

    result = connector.invoke(
        _descriptor(),
        {"url": "https://example.com/submit", "method": "POST", "json_body": {"payload": "too-long"}},
    )

    assert result.status is ConnectorStatus.FAILED
    assert result.error_code is not None
    assert result.error_code.startswith("json_body_too_large:")


def test_json_body_must_be_deterministic_json() -> None:
    connector = HttpConnector(clock=_clock, config=HttpConnectorConfig(allowed_methods=("POST",)))

    result = connector.invoke(
        _descriptor(),
        {"url": "https://example.com/submit", "method": "POST", "json_body": {"bad": {"set"}}},
    )

    assert result.status is ConnectorStatus.FAILED
    assert result.error_code == "json_body must be deterministic JSON"


def test_json_body_digest_is_bound_to_content_type_failure_receipt() -> None:
    connector = HttpConnector(
        clock=_clock,
        config=HttpConnectorConfig(
            allowed_methods=("POST",),
            allowed_content_types=("application/json",),
        ),
    )
    body = {"action": "submit", "amount": 42}

    result, _fake_opener = _invoke_with_fake_opener(
        connector,
        {
            "url": "https://example.com/submit",
            "method": "POST",
            "json_body": body,
        },
    )

    digest = _body_digest(body)
    receipt = result.metadata["connector_receipt"]

    assert result.status is ConnectorStatus.FAILED
    assert result.error_code == "content_type_not_allowed:text/plain"
    assert receipt["request_hash"] == _expected_request_hash(
        url="https://example.com/submit",
        method="POST",
        body_digest=digest,
    )
    assert "json_body" not in receipt


def test_json_body_digest_is_bound_to_response_size_failure_receipt() -> None:
    connector = HttpConnector(
        clock=_clock,
        config=HttpConnectorConfig(
            allowed_methods=("POST",),
            allowed_content_types=("text/plain",),
            max_response_bytes=1,
        ),
    )
    body = {"action": "submit", "amount": 42}

    result, _fake_opener = _invoke_with_fake_opener(
        connector,
        {
            "url": "https://example.com/submit",
            "method": "POST",
            "json_body": body,
        },
    )

    digest = _body_digest(body)
    receipt = result.metadata["connector_receipt"]

    assert result.status is ConnectorStatus.FAILED
    assert result.error_code == "response_too_large:2"
    assert receipt["request_hash"] == _expected_request_hash(
        url="https://example.com/submit",
        method="POST",
        body_digest=digest,
    )
    assert "json_body" not in receipt
