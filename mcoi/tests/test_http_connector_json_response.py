"""Purpose: verify transient JSON response support for the governed HTTP connector.
Governance scope: HTTP transport boundary and connector receipt invariants.
Dependencies: pytest, unittest.mock, http_connector adapter.
Invariants:
  - Response bodies are parsed transiently and are not persisted raw.
  - JSON request bodies are bounded and represented by digest only in receipts.
  - Existing HttpConnector.invoke behavior remains result-only.
"""

from __future__ import annotations

from unittest import mock

from mcoi_runtime.adapters.http_connector import HttpConnector, HttpConnectorConfig
from mcoi_runtime.contracts.integration import (
    ConnectorDescriptor,
    ConnectorStatus,
    EffectClass,
    TrustClass,
)


def _clock() -> str:
    return "2026-01-01T00:00:00+00:00"


def _descriptor() -> ConnectorDescriptor:
    return ConnectorDescriptor(
        connector_id="json-http-test",
        name="JSON HTTP test",
        provider="test",
        effect_class=EffectClass.EXTERNAL_WRITE,
        trust_class=TrustClass.BOUNDED_EXTERNAL,
        credential_scope_id="test:write",
        enabled=True,
    )


def _fake_response(
    *,
    body: bytes,
    content_type: str = "application/json",
    status: int = 200,
) -> mock.MagicMock:
    response = mock.MagicMock()
    response.status = status
    response.headers = {"Content-Type": content_type}
    response.read.side_effect = [body, b""]
    response.__enter__ = lambda value: value
    response.__exit__ = mock.MagicMock(return_value=False)
    return response


def _invoke_with_response(
    connector: HttpConnector,
    request: dict[str, object],
    response: mock.MagicMock,
):
    fake_opener = mock.MagicMock()
    fake_opener.open = mock.MagicMock(return_value=response)
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
        return connector.invoke_json(_descriptor(), request), fake_opener


def test_json_response_is_parsed_transiently() -> None:
    connector = HttpConnector(
        clock=_clock,
        config=HttpConnectorConfig(
            allowed_methods=("POST",),
            allowed_content_types=("application/json",),
            allowed_headers=("Authorization",),
            max_request_body_bytes=1024,
        ),
    )

    outcome, fake_opener = _invoke_with_response(
        connector,
        {
            "url": "https://nested.example/minds/root/proposals",
            "method": "POST",
            "headers": {"Authorization": "Bearer secret", "X-Blocked": "x"},
            "json_body": {"kind": "record_observation", "ops": [{"op": "set"}]},
        },
        _fake_response(body=b'{"status":"accepted","sequence":1}'),
    )

    opened_request = fake_opener.open.call_args.args[0]
    receipt = outcome.connector_result.metadata["connector_receipt"]

    assert outcome.connector_result.status is ConnectorStatus.SUCCEEDED
    assert outcome.json_payload == {"status": "accepted", "sequence": 1}
    assert opened_request.data == b'{"kind":"record_observation","ops":[{"op":"set"}]}'
    assert opened_request.headers["Authorization"] == "Bearer secret"
    receipt_text = str(receipt)
    assert "X-blocked" not in opened_request.headers
    assert receipt["request_hash"]
    assert "record_observation" not in receipt_text
    assert "Bearer secret" not in receipt_text


def test_connector_result_metadata_has_digest_not_raw_body() -> None:
    connector = HttpConnector(clock=_clock)

    outcome, _fake_opener = _invoke_with_response(
        connector,
        {"url": "https://nested.example/status", "method": "GET"},
        _fake_response(body=b'{"visible":"typed-only"}'),
    )

    metadata_text = str(outcome.connector_result.metadata)
    receipt_text = str(outcome.connector_result.metadata["connector_receipt"])
    assert outcome.connector_result.response_digest != "none"
    assert "typed-only" not in metadata_text
    assert "typed-only" not in receipt_text
    assert "response_digest" in outcome.connector_result.metadata["connector_receipt"]


def test_connector_result_metadata_hashes_url_query_secrets() -> None:
    connector = HttpConnector(clock=_clock)

    outcome, _fake_opener = _invoke_with_response(
        connector,
        {"url": "https://nested.example/status?token=secret-query-token", "method": "GET"},
        _fake_response(body=b'{"status":"ok"}'),
    )

    metadata = outcome.connector_result.metadata
    metadata_text = str(metadata)
    receipt_text = str(metadata["connector_receipt"])

    assert outcome.connector_result.status is ConnectorStatus.SUCCEEDED
    assert "url_hash" in metadata
    assert "url" not in metadata
    assert "secret-query-token" not in metadata_text
    assert "secret-query-token" not in receipt_text


def test_invalid_json_response_returns_failed_outcome() -> None:
    connector = HttpConnector(clock=_clock)

    outcome, _fake_opener = _invoke_with_response(
        connector,
        {"url": "https://nested.example/status", "method": "GET"},
        _fake_response(body=b"{not-json"),
    )

    assert outcome.connector_result.status is ConnectorStatus.FAILED
    assert outcome.connector_result.error_code is not None
    assert "invalid_json_response" in outcome.connector_result.error_code
    assert outcome.json_payload == {}


def test_non_json_content_type_fails_when_json_required() -> None:
    connector = HttpConnector(clock=_clock)

    outcome, _fake_opener = _invoke_with_response(
        connector,
        {"url": "https://nested.example/status", "method": "GET"},
        _fake_response(body=b'{"status":"ok"}', content_type="text/plain"),
    )

    assert outcome.connector_result.status is ConnectorStatus.FAILED
    assert outcome.connector_result.error_code is not None
    assert "json_content_type_required:text/plain" in outcome.connector_result.error_code
    assert outcome.json_payload == {}


def test_oversized_response_uses_existing_response_size_guard() -> None:
    connector = HttpConnector(
        clock=_clock,
        config=HttpConnectorConfig(max_response_bytes=4),
    )

    outcome, _fake_opener = _invoke_with_response(
        connector,
        {"url": "https://nested.example/status", "method": "GET"},
        _fake_response(body=b"12345"),
    )

    assert outcome.connector_result.status is ConnectorStatus.FAILED
    assert outcome.connector_result.error_code is not None
    assert "response_too_large" in outcome.connector_result.error_code
    assert outcome.json_payload == {}


def test_existing_invoke_behavior_remains_connector_result_only() -> None:
    connector = HttpConnector(clock=_clock)
    response = _fake_response(body=b'{"status":"ok"}')
    fake_opener = mock.MagicMock()
    fake_opener.open = mock.MagicMock(return_value=response)
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
        result = connector.invoke(
            _descriptor(),
            {"url": "https://nested.example/status", "method": "GET"},
        )

    assert result.status is ConnectorStatus.SUCCEEDED
    assert not hasattr(result, "json_payload")
    assert '{"status":"ok"}' not in str(result.metadata)
