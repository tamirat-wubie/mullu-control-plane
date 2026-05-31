"""Physical promotion receipt store error-bounding tests.

Tests: when the receipt store raises a backend OSError (e.g. a filesystem
permission/path error), the HTTP 503 detail is a stable bounded code and does
NOT leak the raw exception text (which can contain internal filesystem paths).
The exception cause is still chained for server-side logs via ``from exc``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.server import create_gateway_app  # noqa: E402

_SENTINEL_PATH = "/var/secret-internal/promotion-receipts.jsonl"
_BOUNDED_DETAIL = "physical_promotion_receipt_store_unavailable"


class _StubPlatform:
    def process_message(self, message, tenant_id: str, identity_id: str):  # noqa: ANN001
        return {"response": "ok", "tenant_id": tenant_id, "identity_id": identity_id}


def _leaky_oserror(*_args, **_kwargs):
    raise OSError(f"[Errno 13] Permission denied: '{_SENTINEL_PATH}'")


def test_list_backend_error_detail_is_bounded(monkeypatch):
    app = create_gateway_app(platform=_StubPlatform())
    store = app.state.physical_capability_promotion_receipt_store
    monkeypatch.setattr(store, "list", _leaky_oserror)
    client = TestClient(app)

    response = client.get("/operator/physical-capability-promotion-receipts")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail == _BOUNDED_DETAIL
    assert _SENTINEL_PATH not in detail
    assert "Errno" not in detail


def test_emit_backend_error_detail_is_bounded(monkeypatch):
    app = create_gateway_app(platform=_StubPlatform())
    store = app.state.physical_capability_promotion_receipt_store
    monkeypatch.setattr(store, "append", _leaky_oserror)
    client = TestClient(app)

    response = client.post(
        "/operator/physical-capability-promotion-receipts",
        json={"use_fixture_refs": True, "recorded_at": "2026-05-06T12:00:00+00:00"},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail == _BOUNDED_DETAIL
    assert _SENTINEL_PATH not in detail
