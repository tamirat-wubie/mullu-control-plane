"""Cross-tenant IDOR regression for the remaining execution endpoints.

execute_chain, queue_submit, invoke_tool, request_action, schedule_job, and
create_temporal_schedule ran/queued/scheduled an action under the caller-supplied
body tenant_id, consuming that tenant's budget, policy/guard-chain authorization,
queue, or schedule. All now call enforce_tenant_scope: an authenticated tenant
may only act under its own tenant; operator and unauthenticated/dev requests are
unaffected.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers.adapter import ActionRequest, request_action
from mcoi_runtime.app.routers.agent import (
    ChainRequest,
    QueueSubmitRequest,
    execute_chain,
    queue_submit,
)
from mcoi_runtime.app.routers.data.tools import ToolInvokeRequest, invoke_tool
from mcoi_runtime.app.routers.scheduler import ScheduleJobRequest, schedule_job
from mcoi_runtime.app.routers.temporal_scheduler import (
    TemporalScheduleRequest,
    create_temporal_schedule,
)


class _State:
    def __init__(self, ctx):
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx):
        self.state = _State(ctx)


def _authed_a() -> _Req:
    return _Req({"authenticated_tenant_id": "tenant-a"})


_CASES = [
    (execute_chain, ChainRequest(steps=[], tenant_id="tenant-b")),
    (queue_submit, QueueSubmitRequest(task_id="t", tenant_id="tenant-b")),
    (invoke_tool, ToolInvokeRequest(tool_id="t", tenant_id="tenant-b")),
    (request_action, ActionRequest(agent_id="a", action_type="x", target="y", tenant_id="tenant-b")),
    (schedule_job, ScheduleJobRequest(job_id="j", name="n", tenant_id="tenant-b")),
    (
        create_temporal_schedule,
        TemporalScheduleRequest(
            schedule_id="s", action_id="a", tenant_id="tenant-b", actor_id="ac",
            action_type="x", execute_at="2099-01-01T00:00:00+00:00",
        ),
    ),
]


@pytest.mark.parametrize("handler,req", _CASES, ids=[c[0].__name__ for c in _CASES])
def test_execution_endpoint_denies_cross_tenant(handler, req):
    with pytest.raises(HTTPException) as exc:
        handler(req, _authed_a())
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "cross_tenant_denied"
