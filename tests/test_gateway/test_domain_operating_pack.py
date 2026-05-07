"""Gateway domain operating pack tests.

Purpose: verify solution packs declare all governed operating artifacts.
Governance scope: schemas, policies, workflows, connectors, evals, approval
roles, evidence exports, dashboard views, activation blocking, and schema.
Dependencies: gateway.domain_operating_pack and schemas/domain_operating_pack.schema.json.
Invariants:
  - Candidate packs are activation-blocked.
  - High-risk domains require approval roles.
  - Built-in catalog includes the buyer-facing pack set.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from gateway.domain_operating_pack import (
    DomainOperatingPackCompiler,
    builtin_domain_operating_pack_specs,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "domain_operating_pack.schema.json"


def test_builtin_catalog_contains_core_domain_operating_packs() -> None:
    catalog = DomainOperatingPackCompiler().catalog(builtin_domain_operating_pack_specs())
    domains = {pack.domain for pack in catalog.packs}

    assert len(catalog.packs) == 7
    assert {"finance_ops", "customer_support", "compliance", "research", "healthcare_admin", "education", "manufacturing_ops"} == domains
    assert all(pack.activation_blocked for pack in catalog.packs)
    assert catalog.catalog_hash


def test_finance_ops_pack_declares_governed_solution_artifacts() -> None:
    spec = next(spec for spec in builtin_domain_operating_pack_specs() if spec.domain == "finance_ops")
    pack = DomainOperatingPackCompiler().compile(spec)

    assert "invoice.approval" in pack.workflows
    assert "payment.guard" in pack.workflows
    assert "tenant_boundary" in pack.policies
    assert "approval_required" in pack.evals
    assert "finance_admin" in pack.approval_roles
    assert "terminal_certificate_export" in pack.evidence_exports


def test_high_risk_pack_without_approval_roles_is_blocked_and_invalid() -> None:
    spec = replace(next(spec for spec in builtin_domain_operating_pack_specs() if spec.domain == "finance_ops"), approval_roles=())
    pack = DomainOperatingPackCompiler().compile(spec)
    validation = DomainOperatingPackCompiler().validate(pack)

    assert pack.activation_blocked is True
    assert "high_risk_domain_requires_approval_roles" in pack.blocked_reasons
    assert validation.accepted is False
    assert "high_risk_domain_requires_approval_roles" in validation.errors


def test_certified_pack_with_evidence_can_be_unblocked_by_spec() -> None:
    spec = replace(
        next(spec for spec in builtin_domain_operating_pack_specs() if spec.domain == "customer_support"),
        certification_status="certified",
        certification_evidence_refs=("change_certificate:pack-support", "eval_bundle:support"),
    )
    pack = DomainOperatingPackCompiler().compile(spec)
    validation = DomainOperatingPackCompiler().validate(pack)

    assert pack.activation_blocked is False
    assert pack.blocked_reasons == ()
    assert validation.accepted is True
    assert validation.reason == "domain_operating_pack_ready"


def test_domain_operating_pack_schema_exposes_solution_surface() -> None:
    pack = DomainOperatingPackCompiler().compile(builtin_domain_operating_pack_specs()[0])
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(schema["required"]).issubset(asdict(pack))
    assert schema["$id"] == "urn:mullusi:schema:domain-operating-pack:1"
    assert "finance_ops" in schema["properties"]["domain"]["enum"]
    assert pack.pack_hash
