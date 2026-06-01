"""Cross-tenant IDOR regression for the workflow execution endpoints.

The /execute, /workflow/*, /pipeline/execute, and /templates/execute handlers
ran a workflow/pipeline/action under the caller-supplied tenant_id, so a caller
could execute as another tenant -- consuming that tenant's budget, policy, and
guard-chain authorization. All now call enforce_tenant_scope: an authenticated
tenant may only execute under its own tenant; operator and unauthenticated/dev
requests are unaffected.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers.workflow import (
    ExecuteRequest,
    PipelineRequest,
    TemplateExecuteRequest,
    ToolWorkflowRequest,
    WorkflowRequest,
    execute,
    execute_pipeline,
    execute_traced_workflow,
    execute_workflow,
    execute_workflow_template,
    tool_augmented_workflow,
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
    (execute, ExecuteRequest(goal_id="g", action="a", tenant_id="tenant-b")),
    (execute_workflow, WorkflowRequest(task_id="t", description="d", tenant_id="tenant-b")),
    (execute_traced_workflow, WorkflowRequest(task_id="t", description="d", tenant_id="tenant-b")),
    (tool_augmented_workflow, ToolWorkflowRequest(prompt="p", tenant_id="tenant-b")),
    (execute_pipeline, PipelineRequest(steps=[], tenant_id="tenant-b")),
    (execute_workflow_template, TemplateExecuteRequest(template_id="t", params={}, tenant_id="tenant-b")),
]


@pytest.mark.parametrize("handler,req", _CASES, ids=[c[0].__name__ for c in _CASES])
def test_workflow_execute_denies_cross_tenant(handler, req):
    with pytest.raises(HTTPException) as exc:
        handler(req, _authed_a())
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "cross_tenant_denied"
