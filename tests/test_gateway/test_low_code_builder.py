"""Gateway low-code builder tests.

Purpose: verify deterministic builder compilation into canonical governed
manifests.
Governance scope: agent, workflow, policy, capability, eval, approval-chain
manifests; activation blocking; high-risk safeguards; schema publication.
Dependencies: gateway.low_code_builder and low_code_builder_catalog schema.
Invariants:
  - Builder output is declarative only.
  - Every compilation emits exactly six canonical manifests.
  - High-risk builders require eval coverage, approvals, receipts, and evidence.
  - Snapshot output is schema-valid and hash-bearing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from gateway.low_code_builder import (
    BuilderArtifactKind,
    BuilderRisk,
    BuilderStatus,
    LowCodeBuilderCompiler,
    BuilderAppSpec,
    builder_catalog_snapshot_to_json_dict,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "low_code_builder_catalog.schema.json"


def test_builder_compiles_invoice_agent_into_canonical_manifests() -> None:
    compiler = LowCodeBuilderCompiler()
    compilation = compiler.compile(_finance_spec(certified=True))
    artifact_kinds = {artifact.kind for artifact in compilation.artifacts}

    assert compilation.status is BuilderStatus.CERTIFIED
    assert compilation.activation_blocked is False
    assert artifact_kinds == set(BuilderArtifactKind)
    assert len(compilation.artifacts) == 6
    assert all(artifact.path == artifact.kind.value for artifact in compilation.artifacts)
    assert all(artifact.content["declarative_only"] is True for artifact in compilation.artifacts)
    assert all(artifact.artifact_hash for artifact in compilation.artifacts)
    assert compilation.metadata["side_effect_execution_allowed"] is False


def test_candidate_builder_without_certification_evidence_is_blocked() -> None:
    compiler = LowCodeBuilderCompiler()
    compilation = compiler.compile(_finance_spec(certified=False))

    assert compilation.status is BuilderStatus.BLOCKED
    assert compilation.activation_blocked is True
    assert "certification_evidence_missing" in compilation.blocked_reasons
    assert compilation.certification_evidence_refs == ()
    assert compilation.compiled_hash


def test_high_risk_builder_requires_eval_coverage_and_terminal_export() -> None:
    compiler = LowCodeBuilderCompiler()
    spec = _finance_spec(
        certified=True,
        eval_suites=("tenant_isolation", "approval_required"),
        evidence_exports=("audit_bundle",),
    )
    compilation = compiler.compile(spec)

    assert compilation.activation_blocked is True
    assert "high_risk_eval_coverage_missing" in compilation.blocked_reasons
    assert "terminal_certificate_export_required" in compilation.blocked_reasons
    assert compilation.status is BuilderStatus.BLOCKED


def test_high_risk_builder_rejects_missing_approval_roles_at_source() -> None:
    with pytest.raises(ValueError, match="high_risk_builder_requires_approval_roles"):
        _finance_spec(certified=True, approval_roles=())


def test_builder_catalog_counts_blocked_and_certified_apps() -> None:
    compiler = LowCodeBuilderCompiler()
    compiler.compile(_finance_spec(certified=True))
    compiler.compile(_support_spec())
    snapshot = compiler.snapshot()

    assert snapshot.total_apps == 2
    assert snapshot.certified_count == 1
    assert snapshot.activation_blocked_count == 1
    assert snapshot.canonical_artifact_count == 12
    assert snapshot.snapshot_hash


def test_low_code_builder_schema_exposes_manifest_contract() -> None:
    compiler = LowCodeBuilderCompiler()
    compiler.compile(_finance_spec(certified=True))
    snapshot = compiler.snapshot()
    payload = builder_catalog_snapshot_to_json_dict(snapshot)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(payload)
    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:low-code-builder-catalog:1"
    assert "agent.yaml" in schema["$defs"]["artifact_kind"]["enum"]
    assert payload["compilations"][0]["metadata"]["builder_is_declarative_only"] is True
    assert payload["compilations"][0]["metadata"]["side_effect_execution_allowed"] is False


def _finance_spec(
    *,
    certified: bool,
    eval_suites: tuple[str, ...] = ("tenant_isolation", "approval_required", "prompt_injection", "evidence_integrity"),
    evidence_exports: tuple[str, ...] = ("audit_bundle", "receipt_export", "terminal_certificate_export"),
    approval_roles: tuple[str, ...] = ("finance_admin", "manager"),
) -> BuilderAppSpec:
    return BuilderAppSpec(
        app_id="invoice-approval-agent",
        display_name="Invoice Approval Agent",
        domain="finance_ops",
        owner_team="finance_ops",
        risk=BuilderRisk.HIGH,
        goals=("intake_invoice", "check_duplicate", "request_approval", "schedule_payment"),
        workflows=("invoice.approval", "payment.guard"),
        connectors=("quickbooks.create_bill", "gmail.send"),
        policies=("tenant_boundary", "budget_gate", "approval_required", "terminal_closure"),
        eval_suites=eval_suites,
        approval_roles=approval_roles,
        capability_scopes=("invoice.read", "payment.schedule", "email.compose"),
        evidence_exports=evidence_exports,
        receipt_required=True,
        certification_evidence_refs=("eval_bundle:finance", "deployment_witness:builder") if certified else (),
    )


def _support_spec() -> BuilderAppSpec:
    return BuilderAppSpec(
        app_id="support-triage-agent",
        display_name="Support Triage Agent",
        domain="customer_support",
        owner_team="support_ops",
        risk=BuilderRisk.MEDIUM,
        goals=("triage_ticket", "draft_response"),
        workflows=("ticket.triage",),
        connectors=("zendesk.ticket_read",),
        policies=("tenant_boundary", "policy_gate"),
        eval_suites=("tenant_isolation", "prompt_injection"),
        approval_roles=(),
        capability_scopes=("ticket.read", "response.draft"),
        evidence_exports=("audit_bundle",),
        receipt_required=True,
    )
