"""Cross-tenant IDOR regression for publish_event and finance packet creation.

publish_event injected events into a body-supplied tenant_id's stream
(cross-tenant event injection -> can trigger a victim tenant's webhooks/
workflows); create_finance_approval_packet created a finance case attributed to a
body-supplied tenant_id (cross-tenant case injection into a victim's approval
workflow). Both now call enforce_tenant_scope: an authenticated tenant may only
act under its own tenant; operator and unauthenticated/dev requests are
unaffected.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers.audit import EventPublishRequest, publish_event
from mcoi_runtime.app.routers.finance_approval import (
    FinancePacketCreateRequest,
    create_finance_approval_packet,
)


class _State:
    def __init__(self, ctx):
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx):
        self.state = _State(ctx)


def _authed_a() -> _Req:
    return _Req({"authenticated_tenant_id": "tenant-a"})


def test_publish_event_denies_cross_tenant():
    body = EventPublishRequest(event_type="case.created", tenant_id="tenant-b")
    with pytest.raises(HTTPException) as exc:
        publish_event(body, _authed_a())
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "cross_tenant_denied"


def test_create_finance_approval_packet_denies_cross_tenant():
    body = FinancePacketCreateRequest(
        case_id="c", tenant_id="tenant-b", actor_id="a", vendor_id="v",
        invoice_id="i", minor_units=100, source_evidence_ref="ref",
        actor_limit_minor_units=1000, tenant_limit_minor_units=10000,
    )
    with pytest.raises(HTTPException) as exc:
        create_finance_approval_packet(body, _authed_a())
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "cross_tenant_denied"
