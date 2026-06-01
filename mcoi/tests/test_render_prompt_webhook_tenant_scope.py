"""Cross-tenant IDOR regression for render_prompt and webhook_subscribe.

render_prompt executed an LLM completion charged to a caller-supplied
budget_id/tenant_id (cross-tenant budget theft) and webhook_subscribe registered
a caller-controlled URL under a caller-supplied tenant_id (cross-tenant event
exfiltration). Both now call enforce_tenant_scope: an authenticated tenant can
only act under its own tenant, while operator and unauthenticated/dev requests
are unaffected.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers.agent import WebhookSubscribeRequest, webhook_subscribe
from mcoi_runtime.app.routers.data.prompts import PromptRenderRequest, render_prompt


class _State:
    def __init__(self, ctx):
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx):
        self.state = _State(ctx)


def _authed_a() -> _Req:
    return _Req({"authenticated_tenant_id": "tenant-a"})


def test_render_prompt_denies_cross_tenant_budget_use():
    body = PromptRenderRequest(
        template_id="t", variables={}, tenant_id="tenant-b", budget_id="victim", execute=True,
    )
    with pytest.raises(HTTPException) as exc:
        render_prompt(body, _authed_a())
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "cross_tenant_denied"


def test_webhook_subscribe_denies_cross_tenant_subscription():
    body = WebhookSubscribeRequest(
        subscription_id="s", tenant_id="tenant-b",
        url="https://attacker.example/hook", events=["case.created"],
    )
    with pytest.raises(HTTPException) as exc:
        webhook_subscribe(body, _authed_a())
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "cross_tenant_denied"
