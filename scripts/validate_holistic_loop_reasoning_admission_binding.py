#!/usr/bin/env python3
"""Validate holistic loop reasoning admission binding.

Purpose: prove the operator wholistic reasoning direction is bound to existing
Reasoning Integrity Mesh and holistic loop evidence without granting runtime
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: binding schema, Foundation example, SDLC sidecars, source
artifact digests, and scripts/validate_schemas.py.
Invariants:
  - Validation is read-only and deterministic.
  - Runtime reasoning authority remains denied.
  - Runtime promotion remains AwaitingEvidence until required evidence exists.
  - Terminal closure and success claims are not admitted by this binding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "holistic_loop_reasoning_admission_binding.schema.json"
DEFAULT_FIXTURE_PATH = WORKSPACE_ROOT / "examples" / "holistic_loop_reasoning_admission_binding.foundation.json"
REQUIREMENT_PATH = (
    WORKSPACE_ROOT
    / "examples"
    / "sdlc"
    / "requirement_holistic_loop_reasoning_admission_binding_20260626.json"
)
DESIGN_PATH = (
    WORKSPACE_ROOT
    / "examples"
    / "sdlc"
    / "design_holistic_loop_reasoning_admission_binding_20260626.json"
)
SECURITY_REVIEW_PATH = (
    WORKSPACE_ROOT
    / "examples"
    / "sdlc"
    / "security_review_holistic_loop_reasoning_admission_binding_20260626.json"
)

REQUIRED_RUNTIME_PROMOTION_EVIDENCE = (
    "evidence://wholistic-reasoning/uao-admission",
    "evidence://wholistic-reasoning/operator-approval",
    "evidence://wholistic-reasoning/runtime-execution-design",
    "evidence://wholistic-reasoning/rollback-recovery",
    "evidence://wholistic-reasoning/live-run-receipts",
    "evidence://wholistic-reasoning/terminal-closure-review",
)
DENIED_AUTHORITY_FIELDS = (
    "runtime_reasoning_allowed",
    "loop_registration_allowed",
    "loop_status_transition_allowed",
    "mutation_route_allowed",
    "connector_call_allowed",
    "external_model_execution_allowed",
    "network_call_allowed",
    "secret_access_allowed",
    "filesystem_write_allowed",
    "receipt_append_allowed",
    "dashboard_ui_allowed",
    "task_creation_allowed",
    "live_adapter_execution_allowed",
    "canonical_state_mutation_allowed",
    "learning_update_allowed",
    "raw_reasoning_persistence_allowed",
    "private_reasoning_export_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
EXPECTED_SOURCE_DIGESTS = {
    "docs/reasoning/MULLU_REASONING_INTEGRITY_MESH.md": "f5ee0f4c0f02d00a407f3650089d347bed9064d8440a20e626f6d1e4be32ecd1",
    "governance/reasoning_method_registry.yaml": "79ab0627348ae515883d45feb1b23087d74855a6091cc112a55d2bf94c97d0e5",
    "governance/judgment_integrity_gate.yaml": "940784b9d9b93fc193add9670762006e031e12d8f08c3234b0898dd04c9d0bfb",
    "governance/weakness_taxonomy.yaml": "0fba1e1852537497165c680ac1078deced0d2ef08c59e4fc534c7a5609af737a",
    "governance/reasoning_edge_case_forge.yaml": "669db48559b3c31d06b74e4a23a096c2c6cf8f6a6f42493c1d2afa69018930f3",
    "scripts/validate_reasoning_integrity_mesh.py": "e7fa13f992c6536b70445c7fc92af45a5c4d0ef834a03cc619b05ab481f7419f",
    "tests/governance/test_reasoning_integrity_mesh.py": "27bedfc58f26b07fddb7d90861f9b291d6cc5f6926361264c70c454a3ba6e35a",
    "docs/HOLISTIC_LOOP_ENGINEERING_KERNEL.md": "34d45e1e7ee7f23e6f5575417b690e38d45abc34ce19da901a81a0a0dd4d36ca",
    "schemas/holistic_loop_read_model.schema.json": "77e06b23989af91087f07e687d0684eafad69c8b776699600c94666427309688",
    "scripts/validate_holistic_loop_read_model.py": "f702c6bf13eb014ede6fa7dbb430be27e280e2cad483101d98e23c85e270af03",
    "scripts/validate_holistic_loop_extension_admission.py": "7cd148f46d30314c72a8273e0378371e4a586aa5ea840be289075e0490d63c31",
    "scripts/validate_holistic_loop_kernel_freeze.py": "81aba6759e752fdebb97a0b1267a39bcdaf8ba764f4e8209085a927b508e9e64",
    "scripts/validate_holistic_loop_http_surface.py": "76aa201ecc639d8580880cd4a9b23e1525b9096be8f32ea6a8173987f81aaed6",
}
EXPECTED_EVIDENCE_REFS = (
    "schemas/holistic_loop_reasoning_admission_binding.schema.json",
    "examples/holistic_loop_reasoning_admission_binding.foundation.json",
    "scripts/validate_holistic_loop_reasoning_admission_binding.py",
    "tests/test_validate_holistic_loop_reasoning_admission_binding.py",
    "docs/99_holistic_loop_reasoning_admission_binding.md",
    "examples/sdlc/requirement_holistic_loop_reasoning_admission_binding_20260626.json",
    "examples/sdlc/design_holistic_loop_reasoning_admission_binding_20260626.json",
    "examples/sdlc/security_review_holistic_loop_reasoning_admission_binding_20260626.json",
)


class HolisticLoopReasoningAdmissionError(ValueError):
    """Raised when a binding artifact cannot be loaded as a JSON object."""


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit artifact context."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {workspace_display_path(path)}")
    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_json_constant)
    if not isinstance(payload, dict):
        raise HolisticLoopReasoningAdmissionError(f"{label} must be a JSON object")
    return payload


def reject_json_constant(raw_constant: str) -> None:
    """Reject non-finite JSON constants with explicit source context."""

    raise ValueError(f"non-finite JSON constant is not permitted: {raw_constant}")


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest for one normalized text file."""

    raw_content = path.read_bytes()
    normalized_content = raw_content.replace(b"\r\n", b"\n")
    return hashlib.sha256(normalized_content).hexdigest()


def validate_binding_payload(binding: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate the binding schema instance and semantic authority boundary."""

    errors = [f"schema: {error}" for error in _validate_schema_instance(schema, binding)]
    scope = binding.get("admission_scope", {})
    if scope.get("runtime_reasoning_claimed") is not False:
        errors.append("admission_scope.runtime_reasoning_claimed must be false")
    if scope.get("terminal_closure_claimed") is not False:
        errors.append("admission_scope.terminal_closure_claimed must be false")
    if binding.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence")
    errors.extend(validate_runtime_promotion_requirements(binding))
    errors.extend(validate_authority_denials(binding))
    errors.extend(validate_source_artifacts(binding))
    errors.extend(validate_contract_summary(binding))
    errors.extend(validate_evidence_refs(binding))
    return errors


def validate_runtime_promotion_requirements(binding: dict[str, Any]) -> list[str]:
    """Return errors when runtime promotion requirements drift."""

    errors: list[str] = []
    requirements = binding.get("admission_requirements", [])
    requirement_refs = tuple(
        requirement.get("requirement_ref")
        for requirement in requirements
        if isinstance(requirement, dict)
    )
    if requirement_refs != REQUIRED_RUNTIME_PROMOTION_EVIDENCE:
        errors.append("admission_requirements must match required runtime promotion evidence")
    blockers = tuple(binding.get("runtime_promotion_blockers", []))
    if blockers != REQUIRED_RUNTIME_PROMOTION_EVIDENCE:
        errors.append("runtime_promotion_blockers must match required runtime promotion evidence")
    for requirement in requirements:
        if not isinstance(requirement, dict):
            errors.append("admission requirement entries must be objects")
            continue
        ref = requirement.get("requirement_ref")
        if requirement.get("execution_allowed") is not False:
            errors.append(f"{ref} execution_allowed must be false")
        if requirement.get("satisfied") is not False:
            errors.append(f"{ref} satisfied must remain false")
        if requirement.get("required_for_runtime_promotion") is not True:
            errors.append(f"{ref} required_for_runtime_promotion must be true")
    return errors


def validate_authority_denials(binding: dict[str, Any]) -> list[str]:
    """Return errors when denied authority expands into runtime authority."""

    authority_boundary = binding.get("authority_boundary", {})
    errors: list[str] = []
    if authority_boundary.get("read_only") is not True:
        errors.append("authority_boundary.read_only must be true")
    if authority_boundary.get("foundation_evidence_only") is not True:
        errors.append("authority_boundary.foundation_evidence_only must be true")
    denied_authority = authority_boundary.get("denied_authority", [])
    observed_authority = tuple(
        item.get("authority_id")
        for item in denied_authority
        if isinstance(item, dict)
    )
    if observed_authority != DENIED_AUTHORITY_FIELDS:
        errors.append("denied authority ids must match the canonical denied authority set")
    for item in denied_authority:
        if not isinstance(item, dict):
            errors.append("denied authority entries must be objects")
            continue
        authority_id = item.get("authority_id")
        if item.get("allowed") is not False:
            errors.append(f"{authority_id} must remain denied")
    return errors


def validate_source_artifacts(binding: dict[str, Any]) -> list[str]:
    """Return errors when source artifact refs or digests drift."""

    errors: list[str] = []
    artifacts = binding.get("source_artifacts", [])
    observed = {
        artifact.get("path"): artifact.get("sha256")
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    if observed != EXPECTED_SOURCE_DIGESTS:
        errors.append("source artifact digest map must match expected source artifacts")
    for path_text, expected_digest in EXPECTED_SOURCE_DIGESTS.items():
        artifact_path = WORKSPACE_ROOT / path_text
        if not artifact_path.exists():
            errors.append(f"source artifact missing: {path_text}")
            continue
        actual_digest = sha256_file(artifact_path)
        if actual_digest != expected_digest:
            errors.append(f"source artifact digest drift: {path_text}")
    return errors


def validate_contract_summary(binding: dict[str, Any]) -> list[str]:
    """Return errors when declared counts drift from the binding body."""

    summary = binding.get("contract_summary", {})
    source_count = len(binding.get("source_artifacts", []))
    denied_count = len(binding.get("authority_boundary", {}).get("denied_authority", []))
    requirement_count = len(binding.get("admission_requirements", []))
    blocker_count = len(binding.get("runtime_promotion_blockers", []))
    satisfied_count = sum(
        1
        for requirement in binding.get("admission_requirements", [])
        if isinstance(requirement, dict) and requirement.get("satisfied") is True
    )
    expected_counts = {
        "source_artifact_count": source_count,
        "denied_authority_count": denied_count,
        "runtime_requirement_count": requirement_count,
        "satisfied_runtime_requirement_count": satisfied_count,
        "runtime_blocker_count": blocker_count,
        "runtime_claim_count": 0,
    }
    errors = [
        f"contract_summary.{field_name} must be {expected_value}"
        for field_name, expected_value in expected_counts.items()
        if summary.get(field_name) != expected_value
    ]
    if summary.get("read_only") is not True:
        errors.append("contract_summary.read_only must be true")
    if summary.get("receipt_is_not_terminal_closure") is not True:
        errors.append("contract_summary.receipt_is_not_terminal_closure must be true")
    return errors


def validate_evidence_refs(binding: dict[str, Any]) -> list[str]:
    """Return errors when evidence references drift."""

    observed = tuple(binding.get("evidence_refs", []))
    if observed != EXPECTED_EVIDENCE_REFS:
        return ["evidence_refs must match the expected admission binding artifact set"]
    return []


def validate_sdlc_sidecars() -> list[str]:
    """Validate the focused SDLC sidecars and cross-artifact links."""

    errors: list[str] = []
    requirement = load_json_object(REQUIREMENT_PATH, "holistic loop reasoning requirement")
    design = load_json_object(DESIGN_PATH, "holistic loop reasoning design")
    security = load_json_object(SECURITY_REVIEW_PATH, "holistic loop reasoning security review")
    sidecars = (
        ("requirement", WORKSPACE_ROOT / "schemas" / "sdlc_requirement.schema.json", requirement),
        ("design", WORKSPACE_ROOT / "schemas" / "sdlc_design_decision.schema.json", design),
        ("security_review", WORKSPACE_ROOT / "schemas" / "sdlc_security_review.schema.json", security),
    )
    for label, schema_path, payload in sidecars:
        schema = _load_schema(schema_path)
        errors.extend(f"{label}: {error}" for error in _validate_schema_instance(schema, payload))
    if design.get("requirement_id") != requirement.get("requirement_id"):
        errors.append("design.requirement_id must match requirement.requirement_id")
    expected_change_id = "holistic-loop-reasoning-admission-binding-20260626"
    if security.get("change_id") != expected_change_id:
        errors.append("security_review.change_id must match the admission binding change id")
    if security.get("release_blocked") is not False:
        errors.append("security_review.release_blocked must be false for read-only Foundation binding")
    if security.get("receipt_ref") not in security.get("security_receipts", []):
        errors.append("security_review.receipt_ref must be retained in security_receipts")
    return errors


def validate_contract(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
) -> list[str]:
    """Validate holistic loop reasoning admission binding artifacts."""

    schema = _load_schema(schema_path)
    binding = load_json_object(fixture_path, "holistic loop reasoning admission binding")
    errors = validate_binding_payload(binding, schema)
    errors.extend(validate_sdlc_sidecars())
    return errors


def validation_report(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
) -> dict[str, Any]:
    """Build a machine-readable validation receipt."""

    try:
        errors = validate_contract(schema_path=schema_path, fixture_path=fixture_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [f"load-holistic-loop-reasoning-admission-binding: {exc}"]
    return {
        "receipt_id": "holistic_loop_reasoning_admission_binding_validation",
        "status": "passed" if not errors else "blocked",
        "valid": not errors,
        "solver_outcome": "AwaitingEvidence",
        "runtime_promotion_evidence": list(REQUIRED_RUNTIME_PROMOTION_EVIDENCE),
        "denied_authority": list(DENIED_AUTHORITY_FIELDS),
        "receipt_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "errors": errors,
    }


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative path label."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return resolved_path.resolve(strict=False).relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    """Validate holistic loop reasoning admission binding artifacts."""

    parser = argparse.ArgumentParser(
        description="Validate holistic loop reasoning admission binding."
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH), help="schema path")
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE_PATH), help="binding fixture path")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    report = validation_report(schema_path=Path(args.schema), fixture_path=Path(args.fixture))
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0 if report["valid"] else 1
    if report["errors"]:
        for error in report["errors"]:
            sys.stderr.write(f"[BLOCKED] holistic-loop-reasoning-admission-binding: {error}\n")
        sys.stderr.write("STATUS: blocked\n")
        return 1
    sys.stdout.write("[PASS] holistic_loop_reasoning_admission_binding_schema_valid\n")
    sys.stdout.write("[PASS] holistic_loop_reasoning_admission_binding_denies_runtime_authority\n")
    sys.stdout.write("[PASS] holistic_loop_reasoning_admission_binding_requires_runtime_evidence\n")
    sys.stdout.write("[PASS] holistic_loop_reasoning_admission_binding_sdlc_artifacts_valid\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
