"""Gateway workflow mining tests.

Purpose: verify repeated human traces produce governed workflow drafts.
Governance scope: pattern evidence, approval projection, sandbox replay,
operator review, activation blocking, and schema contract.
Dependencies: gateway.workflow_mining and schemas/workflow_mining_report.schema.json.
Invariants:
  - Single observations do not become templates.
  - Draft activation remains blocked.
  - Risky side effects require approval rules.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from gateway.workflow_mining import HumanWorkflowTrace, WorkflowDraft, WorkflowMiningEngine

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "workflow_mining_report.schema.json"


def test_workflow_mining_detects_repeated_invoice_pattern() -> None:
    report = WorkflowMiningEngine().mine(tenant_id="tenant-a", traces=_invoice_traces())
    draft = report.drafts[0]

    assert len(report.patterns) == 1
    assert report.patterns[0].occurrence_count == 3
    assert draft.activation_blocked is True
    assert draft.operator_review_required is True
    assert draft.sandbox_replay_required is True
    assert draft.source_trace_ids == ("trace-1", "trace-2", "trace-3")


def test_workflow_mining_projects_governance_for_payment_pattern() -> None:
    report = WorkflowMiningEngine().mine(tenant_id="tenant-a", traces=_invoice_traces())
    draft = report.drafts[0]

    assert report.patterns[0].risk_tier == "high"
    assert "operator_approval_required" in draft.approval_rules
    assert "self_approval_denied" in draft.approval_rules
    assert "tenant_boundary" in draft.policy_requirements
    assert "approval_required" in draft.eval_cases
    assert any(stage.operation == "payment.dispatch" for stage in draft.stages)


def test_workflow_mining_ignores_singletons_and_other_tenants() -> None:
    traces = (
        *_invoice_traces(),
        HumanWorkflowTrace("trace-x", "tenant-a", "user-1", ("observe.ticket", "reply.send"), "2026-05-04T15:10:00Z", "done", ("ev-x",)),
        HumanWorkflowTrace("trace-y", "tenant-b", "user-2", ("receive.invoice", "payment.dispatch"), "2026-05-04T15:11:00Z", "done", ("ev-y",)),
    )
    report = WorkflowMiningEngine().mine(tenant_id="tenant-a", traces=traces, min_occurrences=3)

    assert report.trace_count == 4
    assert len(report.patterns) == 1
    assert len(report.drafts) == 1
    assert report.patterns[0].tenant_id == "tenant-a"


def test_workflow_mining_schema_exposes_draft_contract() -> None:
    report = WorkflowMiningEngine().mine(tenant_id="tenant-a", traces=_invoice_traces())
    payload = asdict(report)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:workflow-mining-report:1"
    assert schema["$defs"]["draft"]["properties"]["activation_blocked"]["const"] is True
    assert payload["drafts"][0]["draft_hash"]


def test_workflow_draft_rejects_unblocked_activation() -> None:
    with pytest.raises(ValueError, match="activation_must_be_blocked"):
        WorkflowDraft(
            draft_id="draft-1",
            tenant_id="tenant-a",
            name="unsafe",
            pattern_id="pattern-1",
            stages=(),
            policy_requirements=("tenant_boundary",),
            approval_rules=(),
            evidence_requirements=("evidence",),
            eval_cases=("replay",),
            sandbox_replay_required=True,
            operator_review_required=True,
            activation_blocked=False,
            source_trace_ids=("trace-1",),
        )


def _invoice_traces() -> tuple[HumanWorkflowTrace, ...]:
    operations = ("receive.invoice", "extract.fields", "check.vendor", "manager.approve", "payment.dispatch", "receipt.send")
    return tuple(
        HumanWorkflowTrace(
            trace_id=f"trace-{index}",
            tenant_id="tenant-a",
            actor_id="ap-clerk",
            operations=operations,
            observed_at=f"2026-05-04T15:0{index}:00Z",
            outcome="completed",
            evidence_refs=(f"evidence/invoice-{index}.json",),
        )
        for index in range(1, 4)
    )
