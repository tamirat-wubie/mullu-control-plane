#!/usr/bin/env python3
"""Validate the governed SDLC artifact contract.

Purpose: verify SDLC doctrine documents, strict schemas, canonical examples,
cross-artifact links, receipt bindings, and no-overclaim lifecycle invariants.
Governance scope: OCE field completeness, RAG artifact relationships, CDCV
stage causality, CQTE decidable gates, UWMA receipt anchoring, and PRS closure.
Dependencies: Python standard library and scripts/validate_schemas.py.
Invariants:
  - Validation is read-only and deterministic.
  - No raw private reasoning fields are admitted.
  - Effect-bearing gate decisions require UAO, causal trace, and receipt refs.
  - Release and deployment claims cannot exceed evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


SCHEMA_DIR = WORKSPACE_ROOT / "schemas"
EXAMPLE_DIR = WORKSPACE_ROOT / "examples" / "sdlc"
DOC_REQUIREMENTS: dict[Path, tuple[str, ...]] = {
    WORKSPACE_ROOT / "docs" / "SDLC.md": (
        "SDLC = UAO for software changes",
        "Effect-bearing SDLC action -> UAO required.",
        "sdlc_gate_decision_envelope",
        "sdlc_implementation_receipt",
        "sdlc_recovery_handoff_receipt",
        "sdlc_inventory_closure",
        "sdlc_workspace_preflight_closure",
        "sdlc_branch_ruleset_witness",
        "docs/main-protection-ruleset-witness.json",
        "scripts/validate_sdlc_pr_enforcement.py",
        "tests/test_validate_sdlc_pr_enforcement.py",
        "No closure without learning.",
    ),
    WORKSPACE_ROOT / "docs" / "SDLC_GOVERNANCE_POLICY.md": (
        "effect_bearing_sdlc_action",
        "Admission continuity rule:",
        "GovernanceBlocked",
    ),
    WORKSPACE_ROOT / "docs" / "SDLC_STATE_MACHINE.md": (
        "transition_allowed(s1 -> s2)",
        "sdlc_transition_receipt",
        "closed_failed_with_receipt",
    ),
    WORKSPACE_ROOT / "docs" / "SDLC_RELEASE_POLICY.md": (
        "Production claim is allowed when:",
        "deployment_witness = published",
        "sdlc_recovery_handoff_receipt",
        "incident_recovery_path_if_rollback_fails",
    ),
    WORKSPACE_ROOT / "docs" / "SDLC_SECURITY_REVIEW.md": (
        "unresolved_finding.severity in {critical, high} -> block_release",
        "receipt integrity test",
    ),
    WORKSPACE_ROOT / "docs" / "SDLC_PR_ENFORCEMENT.md": (
        "SDLC Governance Gate",
        "sdlc_branch_ruleset_witness",
        "docs/main-protection-ruleset-witness.json",
        "sdlc_workspace_preflight_closure",
        "rollback_or_incident_handoff",
    ),
}

PROHIBITED_PRIVATE_REASONING_FIELDS = {
    "chain_of_thought",
    "raw_chain_of_thought",
    "private_reasoning",
    "hidden_reasoning",
    "scratchpad",
}

REQUIRED_VALIDATORS = (
    "scripts/validate_sdlc_artifact.py",
    "scripts/validate_sdlc_state_machine.py",
    "scripts/validate_sdlc_release_readiness.py",
    "scripts/validate_sdlc_security_review.py",
    "scripts/validate_sdlc_pr_enforcement.py",
)
REQUIRED_VERIFICATION_COMMANDS = (
    "sdlc_artifact_validation",
    "sdlc_state_machine_validation",
    "sdlc_release_readiness_validation",
    "sdlc_security_review_validation",
    "sdlc_pr_enforcement_validation",
    "workspace_governance_preflight",
)
WORKSPACE_PREFLIGHT_RECEIPT_REF = "receipt://workspace/governance-preflight/001"
WORKSPACE_PREFLIGHT_RECEIPT_PATH = ".tmp/workspace-governance-preflight-receipt.json"
BRANCH_RULESET_WITNESS_PATH = "docs/main-protection-ruleset-witness.json"
GATE_BOUND_ARTIFACT_KINDS = (
    "change_request",
    "requirement",
    "design_decision",
    "work_plan",
    "implementation_receipt",
    "transition_receipt",
    "verification_receipt",
    "security_review",
    "release_candidate",
    "deployment_candidate",
    "recovery_handoff",
)
GATE_REF_PREFIX_BY_FIELD = {
    "uao_ref": "uao://",
    "causal_decision_trace_ref": "trace://",
    "receipt_ref": "receipt://",
}
PASSING_OUTCOMES = {"SolvedVerified", "SolvedUnverified"}
PRODUCTION_REQUIRED_STATUSES = {
    "deployment_witness": {"published"},
    "public_health": {"declared", "passing"},
    "runtime_conformance": {"passing"},
    "proof_verify_endpoint": {"reachable", "passing"},
    "audit_verify_endpoint": {"reachable", "passing"},
}


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    """Canonical SDLC artifact schema and example binding."""

    kind: str
    schema_name: str
    example_name: str
    schema_id: str
    title: str

    @property
    def schema_path(self) -> Path:
        return SCHEMA_DIR / self.schema_name

    @property
    def example_path(self) -> Path:
        return EXAMPLE_DIR / self.example_name


ARTIFACT_SPECS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec(
        "change_request",
        "sdlc_change_request.schema.json",
        "change_request_uao_validator.json",
        "urn:mullusi:schema:sdlc-change-request:1",
        "SDLC Change Request",
    ),
    ArtifactSpec(
        "requirement",
        "sdlc_requirement.schema.json",
        "requirement_uao_validator.json",
        "urn:mullusi:schema:sdlc-requirement:1",
        "SDLC Requirement",
    ),
    ArtifactSpec(
        "design_decision",
        "sdlc_design_decision.schema.json",
        "design_uao_validator.json",
        "urn:mullusi:schema:sdlc-design-decision:1",
        "SDLC Design Decision",
    ),
    ArtifactSpec(
        "work_plan",
        "sdlc_work_plan.schema.json",
        "work_plan_uao_validator.json",
        "urn:mullusi:schema:sdlc-work-plan:1",
        "SDLC Work Plan",
    ),
    ArtifactSpec(
        "implementation_receipt",
        "sdlc_implementation_receipt.schema.json",
        "implementation_uao_validator.json",
        "urn:mullusi:schema:sdlc-implementation-receipt:1",
        "SDLC Implementation Receipt",
    ),
    ArtifactSpec(
        "transition_receipt",
        "sdlc_transition_receipt.schema.json",
        "transition_uao_validator.json",
        "urn:mullusi:schema:sdlc-transition-receipt:1",
        "SDLC Transition Receipt",
    ),
    ArtifactSpec(
        "verification_receipt",
        "sdlc_verification_receipt.schema.json",
        "verification_uao_validator.json",
        "urn:mullusi:schema:sdlc-verification-receipt:1",
        "SDLC Verification Receipt",
    ),
    ArtifactSpec(
        "security_review",
        "sdlc_security_review.schema.json",
        "security_review_uao_validator.json",
        "urn:mullusi:schema:sdlc-security-review:1",
        "SDLC Security Review",
    ),
    ArtifactSpec(
        "release_candidate",
        "sdlc_release_candidate.schema.json",
        "release_candidate_uao_validator.json",
        "urn:mullusi:schema:sdlc-release-candidate:1",
        "SDLC Release Candidate",
    ),
    ArtifactSpec(
        "deployment_candidate",
        "sdlc_deployment_candidate.schema.json",
        "deployment_candidate_uao_validator.json",
        "urn:mullusi:schema:sdlc-deployment-candidate:1",
        "SDLC Deployment Candidate",
    ),
    ArtifactSpec(
        "recovery_handoff",
        "sdlc_recovery_handoff_receipt.schema.json",
        "recovery_handoff_uao_validator.json",
        "urn:mullusi:schema:sdlc-recovery-handoff-receipt:1",
        "SDLC Recovery Handoff Receipt",
    ),
    ArtifactSpec(
        "closure_receipt",
        "sdlc_closure_receipt.schema.json",
        "closure_uao_validator.json",
        "urn:mullusi:schema:sdlc-closure-receipt:1",
        "SDLC Closure Receipt",
    ),
)
ARTIFACT_SPEC_BY_KIND = {spec.kind: spec for spec in ARTIFACT_SPECS}
CANONICAL_SCHEMA_REFS = tuple(f"schemas/{spec.schema_name}" for spec in ARTIFACT_SPECS)
CANONICAL_EXAMPLE_REFS = tuple(f"examples/sdlc/{spec.example_name}" for spec in ARTIFACT_SPECS)
CANONICAL_INVENTORY_REFS = CANONICAL_SCHEMA_REFS + CANONICAL_EXAMPLE_REFS
REQUIRED_BRANCH_WITNESS_REFS = (BRANCH_RULESET_WITNESS_PATH,)


class SdlcArtifactError(ValueError):
    """Raised when an SDLC artifact cannot be loaded as a JSON object."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object artifact."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SdlcArtifactError(f"{label} must be a JSON object")
    return payload


def load_document_text(document_path: Path) -> str:
    """Load an SDLC doctrine document."""

    if not document_path.exists():
        raise FileNotFoundError(f"missing SDLC document: {document_path}")
    if not document_path.is_file():
        raise IsADirectoryError(f"SDLC document path is not a file: {document_path}")
    return document_path.read_text(encoding="utf-8")


def load_example_records() -> dict[str, dict[str, Any]]:
    """Load the canonical SDLC example chain keyed by artifact kind."""

    return {
        spec.kind: load_json_object(spec.example_path, f"SDLC {spec.kind} example")
        for spec in ARTIFACT_SPECS
    }


def validate_schema_artifact(schema: dict[str, Any], spec: ArtifactSpec) -> list[str]:
    """Return deterministic schema artifact validation errors."""

    errors: list[str] = []
    if schema.get("$id") != spec.schema_id:
        errors.append(f"{spec.schema_name}: schema $id is invalid")
    if schema.get("title") != spec.title:
        errors.append(f"{spec.schema_name}: schema title is invalid")
    if schema.get("type") != "object":
        errors.append(f"{spec.schema_name}: schema root type must be object")
    if schema.get("additionalProperties") is not False:
        errors.append(f"{spec.schema_name}: schema root must close additional properties")
    required_fields = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required_fields, list):
        errors.append(f"{spec.schema_name}: schema required must be a list")
    if not isinstance(properties, dict):
        errors.append(f"{spec.schema_name}: schema properties must be an object")
    if isinstance(required_fields, list) and isinstance(properties, dict):
        for field_name in required_fields:
            if field_name not in properties:
                errors.append(f"{spec.schema_name}: required field has no property: {field_name}")
    return errors


def validate_document_contract() -> list[str]:
    """Validate required SDLC doctrine terms."""

    errors: list[str] = []
    for document_path, required_terms in DOC_REQUIREMENTS.items():
        document_text = load_document_text(document_path)
        for required_term in required_terms:
            if required_term not in document_text:
                errors.append(f"{_receipt_path_label(document_path)} missing required term: {required_term}")
    return errors


def validate_artifact_record(kind: str, record: dict[str, Any]) -> list[str]:
    """Validate one SDLC artifact against schema and semantic rules."""

    spec = ARTIFACT_SPEC_BY_KIND[kind]
    schema = _load_schema(spec.schema_path)
    errors = [f"{kind}: {error}" for error in _validate_schema_instance(schema, record)]
    errors.extend(f"{kind}: {error}" for error in _validate_no_private_reasoning_fields(record, kind))
    if kind in GATE_BOUND_ARTIFACT_KINDS:
        errors.extend(_validate_effect_gate_refs(kind, record))

    if kind == "design_decision":
        errors.extend(_validate_design_decision(record))
    elif kind == "work_plan":
        errors.extend(_validate_work_plan(record))
    elif kind == "implementation_receipt":
        errors.extend(_validate_implementation_receipt(record))
    elif kind == "verification_receipt":
        errors.extend(_validate_verification_receipt(record))
    elif kind == "security_review":
        errors.extend(validate_security_review_record(record, strict=False))
    elif kind == "release_candidate":
        errors.extend(validate_release_candidate_record(record, strict=False))
    elif kind == "deployment_candidate":
        errors.extend(validate_deployment_candidate_record(record, strict=False))
    elif kind == "recovery_handoff":
        errors.extend(_validate_recovery_handoff(record))
    elif kind == "closure_receipt":
        errors.extend(_validate_closure_receipt(record))
    return errors


def validate_security_review_record(record: dict[str, Any], *, strict: bool) -> list[str]:
    """Validate SDLC security review semantics."""

    errors: list[str] = []
    open_high_findings = [
        finding
        for finding in record.get("findings", [])
        if isinstance(finding, dict)
        and finding.get("severity") in {"critical", "high"}
        and finding.get("status") == "open"
    ]
    if open_high_findings and record.get("release_blocked") is not True:
        errors.append("security_review: unresolved critical/high findings must block release")
    if not open_high_findings and record.get("release_blocked") is True:
        errors.append("security_review: release_blocked true requires unresolved critical/high finding")
    if strict and "none" not in record.get("impact_categories", []) and not record.get("required_checks"):
        errors.append("security_review: strict mode requires checks for non-none impact categories")
    failed_checks = [
        check
        for check in record.get("required_checks", [])
        if isinstance(check, dict) and check.get("status") == "failed"
    ]
    if failed_checks:
        errors.append("security_review: failed required checks must be resolved before release")
    if strict and not record.get("security_receipts"):
        errors.append("security_review: strict mode requires security receipts")
    if record.get("receipt_ref") and record.get("receipt_ref") not in record.get("security_receipts", []):
        errors.append("security_review: receipt_ref must be included in security_receipts")
    return errors


def validate_release_candidate_record(record: dict[str, Any], *, strict: bool) -> list[str]:
    """Validate SDLC release readiness semantics."""

    errors: list[str] = []
    security_status = record.get("security_status", {})
    if record.get("tests_passed") is not True:
        errors.append("release_candidate: tests_passed must be true")
    if isinstance(security_status, dict):
        if security_status.get("critical_open") != 0:
            errors.append("release_candidate: critical_open must be zero")
        if security_status.get("high_open") != 0:
            errors.append("release_candidate: high_open must be zero")
        if security_status.get("status") == "blocked":
            errors.append("release_candidate: blocked security status cannot release")
    if record.get("evidence_bound_claims") is not True:
        errors.append("release_candidate: evidence_bound_claims must be true")
    if not record.get("rollback_plan"):
        errors.append("release_candidate: rollback_plan is required")
    if record.get("release_receipt") != record.get("receipt_ref"):
        errors.append("release_candidate: release_receipt must match receipt_ref")
    release_notes = str(record.get("release_notes", "")).lower()
    if record.get("deployment_status") != "published" and "production" in release_notes:
        errors.append("release_candidate: non-published release notes must not claim production")
    if strict and record.get("docs_updated") is not True:
        errors.append("release_candidate: strict mode requires docs_updated true")
    return errors


def validate_deployment_candidate_record(record: dict[str, Any], *, strict: bool) -> list[str]:
    """Validate SDLC deployment readiness semantics."""

    errors: list[str] = []
    if record.get("public_production_claim") is True:
        if record.get("environment") != "production":
            errors.append("deployment_candidate: production claim requires production environment")
        for field_name, allowed_statuses in PRODUCTION_REQUIRED_STATUSES.items():
            probe = record.get(field_name)
            status = probe.get("status") if isinstance(probe, dict) else None
            if status not in allowed_statuses:
                errors.append(f"deployment_candidate: production claim requires {field_name} evidence")
    else:
        public_health = record.get("public_health")
        if isinstance(public_health, dict) and public_health.get("status") == "declared":
            errors.append("deployment_candidate: declared public health requires public_production_claim true")
    if record.get("rollback_ready") is not True:
        errors.append("deployment_candidate: rollback_ready must be true")
    if strict and record.get("secrets_ready") is not True:
        errors.append("deployment_candidate: strict mode requires secrets_ready true")
    if strict and record.get("database_ready") is not True:
        errors.append("deployment_candidate: strict mode requires database_ready true")
    return errors


def validate_example_chain(records: dict[str, dict[str, Any]] | None = None) -> list[str]:
    """Validate all canonical examples and their cross-artifact links."""

    loaded_records = load_example_records() if records is None else records
    errors: list[str] = []
    for kind, record in loaded_records.items():
        errors.extend(validate_artifact_record(kind, record))

    change_request = loaded_records["change_request"]
    requirement = loaded_records["requirement"]
    design = loaded_records["design_decision"]
    work_plan = loaded_records["work_plan"]
    implementation = loaded_records["implementation_receipt"]
    transition = loaded_records["transition_receipt"]
    verification = loaded_records["verification_receipt"]
    security_review = loaded_records["security_review"]
    release = loaded_records["release_candidate"]
    deployment = loaded_records["deployment_candidate"]
    recovery_handoff = loaded_records["recovery_handoff"]
    closure = loaded_records["closure_receipt"]

    request_id = change_request.get("request_id")
    if requirement.get("request_id") != request_id:
        errors.append("example_chain: requirement.request_id must match change request")
    if design.get("requirement_id") != requirement.get("requirement_id"):
        errors.append("example_chain: design.requirement_id must match requirement")
    if work_plan.get("design_id") != design.get("design_id"):
        errors.append("example_chain: work_plan.design_id must match design")
    if implementation.get("plan_id") != work_plan.get("plan_id"):
        errors.append("example_chain: implementation.plan_id must match work plan")
    if implementation.get("change_id") != request_id:
        errors.append("example_chain: implementation.change_id must match change request")
    if implementation.get("receipt_ref") not in transition.get("required_receipt_refs", []):
        errors.append("example_chain: transition must require implementation receipt")
    if implementation.get("receipt_ref") not in closure.get("receipts", []):
        errors.append("example_chain: closure must include implementation receipt")
    if "examples/sdlc/implementation_uao_validator.json" not in verification.get("coverage_refs", []):
        errors.append("example_chain: verification coverage must include implementation receipt artifact")
    if verification.get("change_id") != request_id:
        errors.append("example_chain: verification.change_id must match change request")
    if transition.get("change_id") != request_id:
        errors.append("example_chain: transition.change_id must match change request")
    if transition.get("required_receipt_refs"):
        for receipt_ref in transition.get("required_receipt_refs", []):
            if receipt_ref not in closure.get("receipts", []):
                errors.append("example_chain: closure must include transition required receipt")
    if security_review.get("change_id") != request_id:
        errors.append("example_chain: security_review.change_id must match change request")
    if request_id not in release.get("change_set", []):
        errors.append("example_chain: release.change_set must include change request")
    if release.get("security_status", {}).get("review_ref") != security_review.get("security_review_id"):
        errors.append("example_chain: release.security_status.review_ref must match security review")
    if deployment.get("release_id") != release.get("release_id"):
        errors.append("example_chain: deployment.release_id must match release")
    if recovery_handoff.get("change_id") != request_id:
        errors.append("example_chain: recovery_handoff.change_id must match change request")
    if recovery_handoff.get("terminal_closure_ref") != closure.get("closure_id"):
        errors.append("example_chain: recovery_handoff.terminal_closure_ref must match closure")
    if recovery_handoff.get("receipt_ref") not in closure.get("receipts", []):
        errors.append("example_chain: closure must include recovery handoff receipt")
    if "examples/sdlc/recovery_handoff_uao_validator.json" not in verification.get("coverage_refs", []):
        errors.append("example_chain: verification coverage must include recovery handoff receipt artifact")
    if WORKSPACE_PREFLIGHT_RECEIPT_PATH not in verification.get("coverage_refs", []):
        errors.append("example_chain: verification coverage must include workspace governance preflight receipt artifact")
    if WORKSPACE_PREFLIGHT_RECEIPT_REF not in closure.get("receipts", []):
        errors.append("example_chain: closure must include workspace governance preflight receipt")
    if closure.get("change_id") != request_id:
        errors.append("example_chain: closure.change_id must match change request")
    if verification.get("receipt_ref") not in closure.get("receipts", []):
        errors.append("example_chain: closure must include verification receipt")
    if release.get("release_receipt") not in closure.get("receipts", []):
        errors.append("example_chain: closure must include release receipt")
    for receipt_ref in security_review.get("security_receipts", []):
        if receipt_ref not in closure.get("receipts", []):
            errors.append("example_chain: closure must include security receipt")
    for gate_kind in GATE_BOUND_ARTIFACT_KINDS:
        gate_record = loaded_records[gate_kind]
        if gate_record.get("receipt_ref") not in closure.get("receipts", []):
            errors.append(f"example_chain: closure must include {gate_kind} receipt_ref")
        if gate_record.get("uao_ref") not in closure.get("uao_refs", []):
            errors.append(f"example_chain: closure must include {gate_kind} uao_ref")
        if gate_record.get("causal_decision_trace_ref") not in closure.get("causal_decision_trace_refs", []):
            errors.append(f"example_chain: closure must include {gate_kind} causal_decision_trace_ref")
    if release.get("deployment_status") == "not_published" and deployment.get("public_production_claim") is not False:
        errors.append("example_chain: not_published release cannot carry production claim")
    return errors


def validate_contract() -> list[str]:
    """Validate all SDLC docs, schemas, examples, and lifecycle links."""

    errors = validate_document_contract()
    for spec in ARTIFACT_SPECS:
        schema = _load_schema(spec.schema_path)
        errors.extend(validate_schema_artifact(schema, spec))
    errors.extend(validate_example_chain())
    return errors


def build_validation_report() -> dict[str, Any]:
    """Build a machine-readable SDLC validation receipt."""

    try:
        errors = validate_contract()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [f"load-sdlc-contract: {_sanitize_error(exc)}"]
    valid = not errors
    checks = (
        "sdlc_schema_contracts",
        "sdlc_example_artifacts",
        "sdlc_document_contracts",
        "sdlc_cross_artifact_links",
        "sdlc_inventory_closure",
        "sdlc_workspace_preflight_closure",
        "sdlc_gate_decision_envelopes",
        "sdlc_closure_ref_retention",
        "sdlc_recovery_handoff_retention",
        "sdlc_branch_ruleset_witness_closure",
        "sdlc_no_overclaim",
    )
    return {
        "receipt_id": "sdlc_artifact_validation_receipt",
        "terminal_closure_required": True,
        "receipt_is_not_terminal_closure": True,
        "valid": valid,
        "status": "passed" if valid else "failed",
        "schema_paths": [_receipt_path_label(spec.schema_path) for spec in ARTIFACT_SPECS],
        "example_paths": [_receipt_path_label(spec.example_path) for spec in ARTIFACT_SPECS],
        "document_paths": [_receipt_path_label(path) for path in DOC_REQUIREMENTS],
        "checks": [{"name": check_name, "passed": valid} for check_name in checks],
        "check_count": len(checks),
        "error_count": len(errors),
        "errors": errors,
    }


def write_validation_report(report: dict[str, Any], receipt_path: Path) -> Path:
    """Persist an SDLC validation receipt."""

    resolved_path = receipt_path if receipt_path.is_absolute() else WORKSPACE_ROOT / receipt_path
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved_path


def _validate_effect_gate_refs(kind: str, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field_name, expected_prefix in GATE_REF_PREFIX_BY_FIELD.items():
        field_value = record.get(field_name)
        if not isinstance(field_value, str) or not field_value:
            errors.append(f"{kind}: {field_name} must be a non-empty string")
        elif not field_value.startswith(expected_prefix):
            errors.append(f"{kind}: {field_name} must use {expected_prefix} prefix")
    return errors


def _validate_design_decision(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if record.get("schema_changes") and not record.get("validator_changes"):
        errors.append("design_decision: schema changes require validator changes")
    errors.extend(
        _validate_ref_inventory(
            "design_decision",
            "schema_changes",
            record.get("schema_changes", []),
            CANONICAL_SCHEMA_REFS,
        )
    )
    missing_validators = set(REQUIRED_VALIDATORS) - set(record.get("validator_changes", []))
    if missing_validators:
        errors.append(f"design_decision: missing required validators: {sorted(missing_validators)}")
    return errors


def _validate_work_plan(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    steps = record.get("steps", [])
    if not isinstance(steps, list):
        return ["work_plan: steps must be a list"]
    observed_orders = [step.get("order") for step in steps if isinstance(step, dict)]
    if observed_orders != list(range(1, len(steps) + 1)):
        errors.append("work_plan: steps must use contiguous order values starting at 1")
    observed_order_set = set(observed_orders)
    for step in steps:
        if not isinstance(step, dict):
            continue
        order = step.get("order")
        for dependency in step.get("depends_on", []):
            if dependency not in observed_order_set:
                errors.append(f"work_plan: step {order} depends on unknown step {dependency}")
            if isinstance(order, int) and isinstance(dependency, int) and dependency >= order:
                errors.append(f"work_plan: step {order} dependency {dependency} must be earlier")
    missing_validators = set(REQUIRED_VALIDATORS) - set(record.get("required_validators", []))
    if missing_validators:
        errors.append(f"work_plan: missing required validators: {sorted(missing_validators)}")
    errors.extend(
        _validate_ref_inventory(
            "work_plan",
            "expected_artifacts",
            record.get("expected_artifacts", []),
            CANONICAL_INVENTORY_REFS,
        )
    )
    return errors


def _validate_implementation_receipt(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    changed_files = record.get("changed_files", [])
    if not isinstance(changed_files, list):
        return ["implementation_receipt: changed_files must be a list"]
    changed_file_paths = [
        changed_file.get("path")
        for changed_file in changed_files
        if isinstance(changed_file, dict) and isinstance(changed_file.get("path"), str)
    ]
    if len(changed_file_paths) != len(set(changed_file_paths)):
        errors.append("implementation_receipt: changed_files paths must be unique")
    for path_text in changed_file_paths:
        file_path = Path(path_text)
        if file_path.is_absolute() or ".." in file_path.parts:
            errors.append(f"implementation_receipt: changed file path must stay workspace-relative: {path_text}")

    changed_file_path_set = set(changed_file_paths)
    errors.extend(
        _validate_ref_inventory(
            "implementation_receipt",
            "changed_files",
            changed_file_paths,
            CANONICAL_INVENTORY_REFS,
        )
    )
    errors.extend(
        _validate_ref_inventory(
            "implementation_receipt",
            "changed_files",
            changed_file_paths,
            REQUIRED_BRANCH_WITNESS_REFS,
            requirement_label="required branch ruleset witness refs",
        )
    )
    errors.extend(
        _validate_ref_inventory(
            "implementation_receipt",
            "schema_changes",
            record.get("schema_changes", []),
            CANONICAL_SCHEMA_REFS,
        )
    )
    errors.extend(
        _validate_ref_inventory(
            "implementation_receipt",
            "documentation_changes",
            record.get("documentation_changes", []),
            REQUIRED_BRANCH_WITNESS_REFS,
            requirement_label="required branch ruleset witness refs",
        )
    )
    for field_name in ("schema_changes", "validator_changes", "test_changes", "documentation_changes"):
        for ref in record.get(field_name, []):
            if isinstance(ref, str) and ref not in changed_file_path_set:
                errors.append(f"implementation_receipt: {field_name} ref is not listed in changed_files: {ref}")

    if any(path.startswith("schemas/") for path in changed_file_paths) and not record.get("validator_changes"):
        errors.append("implementation_receipt: schema file changes require validator_changes")
    if any(path.startswith("tests/") for path in changed_file_paths) and not record.get("test_changes"):
        errors.append("implementation_receipt: test file changes require test_changes")
    if any(path.startswith("docs/") or path.startswith(".github/") for path in changed_file_paths) and not record.get(
        "documentation_changes",
    ):
        errors.append("implementation_receipt: documentation surface changes require documentation_changes")
    if not record.get("rollback_refs"):
        errors.append("implementation_receipt: rollback_refs are required")
    return errors


def _validate_verification_receipt(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    commands = record.get("commands", [])
    if record.get("tests_failed") == 0 and record.get("failed_checks"):
        errors.append("verification_receipt: failed_checks must be empty when tests_failed is zero")
    if record.get("tests_failed", 0) > 0 and not record.get("failed_checks"):
        errors.append("verification_receipt: failed checks are required when tests fail")
    for command in commands:
        if isinstance(command, dict) and command.get("status") != "passed":
            errors.append(f"verification_receipt: command did not pass: {command.get('name')}")
    observed_command_names = {item.get("name") for item in commands if isinstance(item, dict)}
    for validator_name in REQUIRED_VERIFICATION_COMMANDS:
        if not any(isinstance(item, dict) and item.get("name") == validator_name for item in commands):
            errors.append(f"verification_receipt: missing command {validator_name}")
    validator_outputs = record.get("validator_outputs", [])
    observed_output_names = {item.get("name") for item in validator_outputs if isinstance(item, dict)}
    missing_outputs = set(REQUIRED_VERIFICATION_COMMANDS) - observed_output_names
    if missing_outputs:
        errors.append(f"verification_receipt: missing validator outputs: {sorted(missing_outputs)}")
    stale_outputs = observed_output_names - observed_command_names
    if stale_outputs:
        errors.append(f"verification_receipt: validator outputs without commands: {sorted(stale_outputs)}")
    errors.extend(
        _validate_ref_inventory(
            "verification_receipt",
            "coverage_refs",
            record.get("coverage_refs", []),
            CANONICAL_EXAMPLE_REFS,
        )
    )
    errors.extend(
        _validate_ref_inventory(
            "verification_receipt",
            "coverage_refs",
            record.get("coverage_refs", []),
            REQUIRED_BRANCH_WITNESS_REFS,
            requirement_label="required branch ruleset witness refs",
        )
    )
    return errors


def _validate_recovery_handoff(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    rollback_state = record.get("rollback_state")
    incident_required = record.get("incident_handoff_required")
    incident_refs = record.get("incident_recovery_refs", [])
    accepted_risk_refs = record.get("accepted_risk_refs", [])
    if rollback_state in {"partial", "blocked"} and incident_required is not True:
        errors.append("recovery_handoff: partial or blocked rollback requires incident handoff")
    if accepted_risk_refs and incident_required is not True:
        errors.append("recovery_handoff: accepted risks require incident handoff")
    if incident_required is True and not incident_refs:
        errors.append("recovery_handoff: incident handoff requires incident recovery refs")
    if rollback_state != "not_required" and not record.get("rollback_refs"):
        errors.append("recovery_handoff: rollback refs are required unless rollback is not_required")
    for field_name in ("rollback_refs", "incident_recovery_refs", "accepted_risk_refs", "effect_boundary_refs"):
        values = record.get(field_name, [])
        if isinstance(values, list) and len(values) != len(set(values)):
            errors.append(f"recovery_handoff: {field_name} must not contain duplicates")
    return errors


def _validate_closure_receipt(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if record.get("terminal_state") == "closed_success" and record.get("outcome") not in PASSING_OUTCOMES:
        errors.append("closure_receipt: closed_success requires passing outcome")
    open_blockers = [
        blocker
        for blocker in record.get("known_remaining_blockers", [])
        if isinstance(blocker, dict) and blocker.get("status") == "open"
    ]
    if record.get("terminal_state") == "closed_success" and open_blockers:
        errors.append("closure_receipt: closed_success cannot carry open blockers")
    if not record.get("learning_notes"):
        errors.append("closure_receipt: learning_notes are required")
    if not record.get("uao_refs") or not record.get("causal_decision_trace_refs"):
        errors.append("closure_receipt: closure must bind UAO and causal decision trace refs")
    return errors


def _validate_ref_inventory(
    kind: str,
    field_name: str,
    observed_refs: Any,
    required_refs: tuple[str, ...],
    *,
    requirement_label: str = "canonical SDLC inventory refs",
) -> list[str]:
    if not isinstance(observed_refs, list):
        return []
    observed_ref_set = {ref for ref in observed_refs if isinstance(ref, str)}
    missing_refs = sorted(set(required_refs) - observed_ref_set)
    if not missing_refs:
        return []
    return [f"{kind}: {field_name} missing {requirement_label}: {missing_refs}"]


def _validate_no_private_reasoning_fields(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in PROHIBITED_PRIVATE_REASONING_FIELDS:
                errors.append(f"{path}.{key} is prohibited")
            errors.extend(_validate_no_private_reasoning_fields(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_validate_no_private_reasoning_fields(child, f"{path}[{index}]"))
    return errors


def _receipt_path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _sanitize_error(exc: BaseException) -> str:
    message = str(exc)
    for spec in ARTIFACT_SPECS:
        for path in (spec.schema_path, spec.example_path):
            message = message.replace(str(path), _receipt_path_label(path))
            message = message.replace(str(path.resolve(strict=False)), _receipt_path_label(path))
    for document_path in DOC_REQUIREMENTS:
        message = message.replace(str(document_path), _receipt_path_label(document_path))
        message = message.replace(str(document_path.resolve(strict=False)), _receipt_path_label(document_path))
    return message


def main(argv: list[str] | None = None) -> int:
    """Validate SDLC artifact contracts."""

    parser = argparse.ArgumentParser(description="Validate governed SDLC artifacts.")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    parser.add_argument("--receipt-path", type=Path, help="optional path to persist the SDLC validation receipt")
    args = parser.parse_args(argv)

    report = build_validation_report()
    if args.receipt_path is not None:
        write_validation_report(report, args.receipt_path)
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0 if report["valid"] else 1

    if not report["valid"]:
        for error in report["errors"]:
            sys.stderr.write(f"[FAIL] sdlc-artifact: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    for check in report["checks"]:
        sys.stdout.write(f"[PASS] {check['name']}\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
