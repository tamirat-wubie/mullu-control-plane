#!/usr/bin/env python3
"""Validate personal-assistant GitHub/Codex review projection evidence.

Purpose: prove GitHub/Codex review plans are schema-backed, no-effect
Personal Assistant projections.
Governance scope: operator-supplied PR evidence, Codex instruction drafting,
receipt conformance, private payload redaction, and Foundation Mode no-effect
boundaries.
Dependencies: personal-assistant GitHub/Codex runtime helpers, personal-
assistant receipt schema, and schema validators.
Invariants:
  - GitHub/Codex projections are not GitHub API calls.
  - Repository, PR, branch, issue, review, and deployment effects are denied.
  - Raw diffs, raw connector payloads, and secret-like values are rejected.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for candidate_path in (REPO_ROOT, MCOI_ROOT):
    if str(candidate_path) not in sys.path:
        sys.path.insert(0, str(candidate_path))

from mcoi_runtime.personal_assistant import (  # noqa: E402
    ConnectorProofRef,
    interpret_user_request,
    plan_github_codex_review,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_PROJECTION = REPO_ROOT / "examples" / "personal_assistant_github_codex_projection.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_github_codex_projection.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_SUBMITTED_AT = "2026-06-15T18:00:00+00:00"
RUNTIME_GENERATED_AT = "2026-06-15T18:05:00+00:00"

FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "execution_allowed",
        "live_connector_execution_allowed",
        "github_call_allowed",
        "repository_read_allowed",
        "repository_mutation_allowed",
        "pull_request_mutation_allowed",
        "branch_push_allowed",
        "issue_creation_allowed",
        "review_submission_allowed",
        "deployment_mutation_allowed",
        "system_of_record_write_allowed",
        "public_readiness_claim_allowed",
        "customer_readiness_claim_allowed",
        "nested_mind_live_activation_allowed",
    }
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"gho_[A-Za-z0-9]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)
RAW_PRIVATE_FIELD_NAMES = frozenset(
    {
        "raw_diff",
        "diff",
        "patch",
        "raw_patch",
        "raw_private_connector_payload",
        "raw_connector_payload",
        "connector_response",
        "authorization",
        "cookie",
        "token",
        "secret",
        "private_key",
        "credential",
        "credentials",
    }
)
ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "raw_diff_projection",
        "connector_payload_projection",
        "body_projection",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantGitHubCodexProjectionValidation:
    """Validation result for a GitHub/Codex projection evidence envelope."""

    valid: bool
    projection_path: str
    runtime_validated: bool
    projection_count: int
    receipt_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_github_codex_projection(
    *,
    projection_path: Path = DEFAULT_PROJECTION,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
    validate_runtime: bool = True,
) -> PersonalAssistantGitHubCodexProjectionValidation:
    """Validate a GitHub/Codex projection fixture and optional runtime envelope."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub/Codex projection schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    projection = _load_json_object(projection_path, "GitHub/Codex projection evidence", errors)
    assurance_outcome = ""
    if schema and projection:
        errors.extend(_validate_schema_instance(schema, projection))
    if projection:
        assurance = _mapping(projection.get("assurance"))
        assurance_outcome = str(assurance.get("outcome", ""))
        errors.extend(_validate_projection_semantics(projection, receipt_schema))
        _scan_private_or_secret_payload(projection, errors, path="$")

    runtime_validated = False
    if validate_runtime and schema:
        runtime_projection = build_runtime_github_codex_projection_evidence()
        runtime_errors = list(_validate_schema_instance(schema, runtime_projection))
        runtime_errors.extend(_validate_projection_semantics(runtime_projection, receipt_schema))
        _scan_private_or_secret_payload(runtime_projection, runtime_errors, path="$runtime")
        if runtime_errors:
            errors.extend(f"runtime {message}" for message in runtime_errors)
        runtime_validated = not runtime_errors

    return PersonalAssistantGitHubCodexProjectionValidation(
        valid=not errors,
        projection_path=_path_label(projection_path),
        runtime_validated=runtime_validated,
        projection_count=int(projection.get("projection_count", 0)) if isinstance(projection, dict) else 0,
        receipt_count=len(projection.get("receipt_ids", ())) if isinstance(projection, dict) else 0,
        assurance_outcome=assurance_outcome,
        errors=tuple(errors),
    )


def build_runtime_github_codex_projection_evidence() -> dict[str, Any]:
    """Build deterministic blocked and review-ready GitHub/Codex projections."""
    blocked = plan_github_codex_review(
        _github_codex_intent("pa_request_github_codex_projection_blocked_001"),
        generated_at=RUNTIME_GENERATED_AT,
        repository_ref="tamirat-wubie/mullu-control-plane",
        pull_request_ref="",
        change_summary="Operator asked for a PR review but did not provide changed-file or evidence refs.",
        changed_files=(),
        risk_notes=("evidence set incomplete",),
        blocking_questions=("changed_files_missing",),
        evidence_refs=(),
    )
    review_ready = plan_github_codex_review(
        _github_codex_intent("pa_request_github_codex_projection_ready_001"),
        generated_at=RUNTIME_GENERATED_AT,
        repository_ref="tamirat-wubie/mullu-control-plane",
        pull_request_ref="PR-1771",
        change_summary="Adds a no-effect TeamOps shared-inbox preview route and projection schema.",
        changed_files=(
            "gateway/server.py",
            "schemas/personal_assistant_teamops_projection.schema.json",
            "scripts/validate_personal_assistant_teamops_projection.py",
            "tests/test_validate_personal_assistant_teamops_projection.py",
        ),
        risk_notes=(
            "public route must deny provider calls",
            "receipts must record actions not taken",
        ),
        blocking_questions=(),
        evidence_refs=(
            "proof://github/pr/1771",
            "proof://ci/main/5d50c928376c2493015567b9dc6b7ea1e902778e",
        ),
    )
    return build_github_codex_projection_evidence_envelope(
        generated_at=RUNTIME_GENERATED_AT,
        projections=(
            ("pa_github_codex_projection_item_blocked_001", blocked.as_dict()),
            ("pa_github_codex_projection_item_ready_001", review_ready.as_dict()),
        ),
    )


def build_github_codex_projection_evidence_envelope(
    *,
    generated_at: str,
    projections: tuple[tuple[str, Mapping[str, Any]], ...],
) -> dict[str, Any]:
    """Build a schema-shaped no-effect envelope around GitHub/Codex plans."""
    items: list[dict[str, Any]] = []
    projection_ids: list[str] = []
    receipt_ids: list[str] = []
    connectors: list[str] = []
    has_awaiting_evidence = False
    for projection_id, projection in projections:
        plan = _mapping(projection.get("plan"))
        receipt = _mapping(projection.get("receipt"))
        projection_ids.append(projection_id)
        receipt_id = str(receipt.get("receipt_id", ""))
        if receipt_id and receipt_id not in receipt_ids:
            receipt_ids.append(receipt_id)
        for connector in receipt.get("connectors_used", ()):
            if isinstance(connector, str) and connector not in connectors:
                connectors.append(connector)
        if receipt.get("outcome") == "AwaitingEvidence":
            has_awaiting_evidence = True
        items.append(
            {
                "projection_id": projection_id,
                "request_id": str(projection.get("request_id", "")),
                "skill_id": str(projection.get("skill_id", "")),
                "plan_type": str(plan.get("plan_type", "")),
                "plan": dict(plan),
                "receipt": dict(receipt),
            }
        )
    return {
        "projection_set_id": "pa_github_codex_projection_foundation_001",
        "generated_at": generated_at,
        "governed": True,
        "source_projection": "operator_supplied_github_codex_evidence",
        "projection_count": len(items),
        "projection_ids": projection_ids,
        "receipt_ids": receipt_ids,
        "connectors_used": connectors,
        "projections": items,
        "effect_boundary": {
            "github_codex_review_records_allowed": True,
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "github_call_allowed": False,
            "repository_read_allowed": False,
            "repository_mutation_allowed": False,
            "pull_request_mutation_allowed": False,
            "branch_push_allowed": False,
            "issue_creation_allowed": False,
            "review_submission_allowed": False,
            "deployment_mutation_allowed": False,
            "system_of_record_write_allowed": False,
            "public_readiness_claim_allowed": False,
            "customer_readiness_claim_allowed": False,
            "nested_mind_live_activation_allowed": False,
        },
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "raw_diff_projection": "forbidden",
            "body_projection": "redacted_summary",
        },
        "assurance": {
            "assurance_id": "personal_assistant_github_codex_projection_no_effect_assurance",
            "outcome": "AwaitingEvidence" if has_awaiting_evidence else "SolvedVerified",
            "foundation_only": True,
            "ready_for_live_connector_execution": False,
            "ready_for_repository_mutation": False,
            "ready_for_merge_claim": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "github_codex_projection_is_not_github_call",
                "no_repository_read",
                "no_repository_mutation",
                "no_pull_request_mutation",
                "no_branch_push",
                "no_issue_creation",
                "no_review_submission",
                "no_deployment",
                "no_secret_value_serialization",
                "no_raw_diff_serialization",
            ],
            "blocking_reasons": ["blocked_projection_awaiting_evidence"] if has_awaiting_evidence else [],
            "next_action": "send the drafted Codex instruction separately only after operator review",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "github_codex_review_evidence_only",
            "runtime_boundary": "github_codex_projection_does_not_call_github",
            "live_connector_execution_allowed": False,
            "github_call_allowed": False,
            "repository_mutation_allowed": False,
            "pull_request_mutation_allowed": False,
            "deployment_mutation_allowed": False,
            "system_of_record_write_allowed": False,
        },
    }


def _validate_projection_semantics(
    projection: dict[str, Any],
    receipt_schema: dict[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    effect_boundary = _mapping(projection.get("effect_boundary"))
    if effect_boundary.get("github_codex_review_records_allowed") is not True:
        errors.append("effect_boundary.github_codex_review_records_allowed must be true")
    _require_false_fields(effect_boundary, FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    private_policy = _mapping(projection.get("private_payload_policy"))
    if private_policy.get("raw_private_payload_serialized") is not False:
        errors.append("private_payload_policy.raw_private_payload_serialized must be false")
    if private_policy.get("secret_values_serialized") is not False:
        errors.append("private_payload_policy.secret_values_serialized must be false")
    if private_policy.get("raw_diff_projection") != "forbidden":
        errors.append("private_payload_policy.raw_diff_projection must be forbidden")
    assurance = _mapping(projection.get("assurance"))
    for field_name in (
        "ready_for_live_connector_execution",
        "ready_for_repository_mutation",
        "ready_for_merge_claim",
        "ready_for_customer_readiness_claim",
    ):
        if assurance.get(field_name) is not False:
            errors.append(f"assurance.{field_name} must be false")

    items = projection.get("projections")
    if not isinstance(items, list):
        errors.append("projections must be a list")
        return tuple(errors)
    if projection.get("projection_count") != len(items):
        errors.append("projection_count must equal projections length")
    projection_ids: list[str] = []
    receipt_ids: list[str] = []
    seen_ready = False
    seen_blocked = False
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"projections[{index}] must be an object")
            continue
        projection_ids.append(str(item.get("projection_id", "")))
        plan = _mapping(item.get("plan"))
        gate = _mapping(plan.get("evidence_gate"))
        receipt = _mapping(item.get("receipt"))
        if receipt_schema:
            errors.extend(
                f"projections[{index}].receipt {message}"
                for message in _validate_schema_instance(receipt_schema, receipt)
            )
        errors.extend(
            f"projections[{index}].receipt {message}"
            for message in validate_personal_assistant_receipt_payload(receipt)
        )
        if item.get("skill_id") != "github.pr.summarize":
            errors.append(f"projections[{index}].skill_id must be github.pr.summarize")
        if plan.get("execution_allowed") is not False:
            errors.append(f"projections[{index}].plan.execution_allowed must be false")
        if plan.get("github_call_allowed") is not False:
            errors.append(f"projections[{index}].plan.github_call_allowed must be false")
        if plan.get("repository_mutation_allowed") is not False:
            errors.append(f"projections[{index}].plan.repository_mutation_allowed must be false")
        if plan.get("pull_request_mutation_allowed") is not False:
            errors.append(f"projections[{index}].plan.pull_request_mutation_allowed must be false")
        if plan.get("deployment_allowed") is not False:
            errors.append(f"projections[{index}].plan.deployment_allowed must be false")
        for field_name in (
            "github_call_performed",
            "repository_write_performed",
            "review_submission_performed",
            "deployment_performed",
        ):
            if gate.get(field_name) is not False:
                errors.append(f"projections[{index}].plan.evidence_gate.{field_name} must be false")
        for action in _required_actions_not_taken():
            if action not in receipt.get("actions_not_taken", ()):
                errors.append(f"projections[{index}].receipt.actions_not_taken must include {action}")
        metadata = _mapping(receipt.get("metadata"))
        if metadata.get("live_connector_execution_allowed") is not False:
            errors.append(f"projections[{index}].receipt.metadata.live_connector_execution_allowed must be false")
        if metadata.get("repository_mutation_allowed") is not False:
            errors.append(f"projections[{index}].receipt.metadata.repository_mutation_allowed must be false")
        if receipt.get("outcome") == "AwaitingEvidence":
            seen_blocked = True
        else:
            seen_ready = True
        receipt_id = receipt.get("receipt_id")
        if isinstance(receipt_id, str):
            receipt_ids.append(receipt_id)
    if not seen_ready:
        errors.append("projections must include a review-ready projection")
    if not seen_blocked:
        errors.append("projections must include a blocked projection")
    if projection.get("projection_ids") != projection_ids:
        errors.append("projection_ids must match projections order")
    if sorted(projection.get("receipt_ids", ())) != sorted(receipt_ids):
        errors.append("receipt_ids must match embedded receipts")
    return tuple(errors)


def _github_codex_intent(request_id: str):
    return interpret_user_request(
        "Review this GitHub pull request and draft the next Codex instruction.",
        request_id=request_id,
        submitted_at=RUNTIME_SUBMITTED_AT,
        connector_refs=(
            ConnectorProofRef(
                connector_id="connector:github:operator",
                connector_name="github",
                proof_state="Pass",
                private_data_allowed=True,
                scopes=("repo.read",),
            ),
        ),
    )


def _required_actions_not_taken() -> tuple[str, ...]:
    return (
        "github_not_called",
        "pull_request_not_opened",
        "pull_request_not_merged",
        "branch_not_pushed",
        "review_not_submitted",
        "deployment_not_started",
        "secret_values_not_serialized",
        "raw_diff_not_serialized",
    )


def _require_false_fields(payload: Mapping[str, Any], fields: frozenset[str], label: str, errors: list[str]) -> None:
    model = _mapping(payload)
    if not model:
        errors.append(f"{label} must be an object")
        return
    for field_name in sorted(fields):
        if model.get(field_name) is not False:
            errors.append(f"{label}.{field_name} must be false")


def _scan_private_or_secret_payload(payload: Any, errors: list[str], *, path: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key not in ALLOWED_POLICY_FIELD_NAMES and normalized_key in RAW_PRIVATE_FIELD_NAMES:
                errors.append(f"{path}.{key}: raw private or secret field is forbidden")
            _scan_private_or_secret_payload(value, errors, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, errors, path=f"{path}[{index}]")
    elif isinstance(payload, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(payload):
                errors.append(f"{path}: secret-like value must not be serialized")
                break


def _mapping(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append(f"{label} could not be read")
        return {}
    except json.JSONDecodeError:
        errors.append(f"{label} must be JSON")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return parsed


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse GitHub/Codex projection validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant GitHub/Codex projection evidence.")
    parser.add_argument("--projection", default=str(DEFAULT_PROJECTION))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--skip-runtime", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for GitHub/Codex projection validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_github_codex_projection(
        projection_path=Path(args.projection),
        schema_path=Path(args.schema),
        receipt_schema_path=Path(args.receipt_schema),
        validate_runtime=not args.skip_runtime,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant GitHub/Codex projection ok "
            f"projections={result.projection_count} receipts={result.receipt_count} "
            f"runtime_validated={result.runtime_validated}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
