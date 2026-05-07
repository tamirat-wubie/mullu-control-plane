"""Purpose: verify connector invocation receipt contract invariants.
Governance scope: external connector observation evidence typing only.
Dependencies: pytest and connector effect contracts.
Invariants: receipts bind request/response hashes, connector identity, status, and evidence references.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.connector_effects import ConnectorInvocationReceipt
from mcoi_runtime.contracts.integration import ConnectorStatus


def _receipt(**overrides: object) -> ConnectorInvocationReceipt:
    defaults = {
        "receipt_id": "connector-receipt-1",
        "result_id": "result-1",
        "connector_id": "connector-1",
        "provider": "http",
        "method": "GET",
        "url_hash": "url-hash",
        "request_hash": "request-hash",
        "response_digest": "response-digest",
        "status": ConnectorStatus.SUCCEEDED,
        "evidence_ref": "connector-invocation:connector-1:receipt-1",
        "started_at": "2026-03-19T00:00:00+00:00",
        "finished_at": "2026-03-19T00:00:01+00:00",
        "status_code": 200,
        "metadata": {"effect_class": "external_read"},
    }
    defaults.update(overrides)
    return ConnectorInvocationReceipt(**defaults)


def test_connector_invocation_receipt_accepts_hashed_evidence() -> None:
    receipt = _receipt()

    assert receipt.status is ConnectorStatus.SUCCEEDED
    assert receipt.method == "GET"
    assert receipt.url_hash == "url-hash"
    assert receipt.request_hash == "request-hash"
    assert receipt.response_digest == "response-digest"


def test_connector_invocation_receipt_rejects_missing_request_hash() -> None:
    with pytest.raises(ValueError, match="^request_hash must be a non-empty string$") as exc_info:
        _receipt(request_hash="")

    message = str(exc_info.value)
    assert "request_hash" in message
    assert "request-hash" not in message
    assert "non-empty" in message


def test_connector_invocation_receipt_rejects_invalid_status_code() -> None:
    with pytest.raises(ValueError, match="^status_code must be an integer when provided$"):
        _receipt(status_code="200")

    failed = _receipt(
        status=ConnectorStatus.FAILED,
        status_code=None,
        error_code="blocked_private_address",
        response_digest="none",
    )
    assert failed.status is ConnectorStatus.FAILED
    assert failed.error_code == "blocked_private_address"
