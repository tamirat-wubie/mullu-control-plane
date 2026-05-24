#!/usr/bin/env python3
"""Validate deployment publication closure plan schema conformance.

Purpose: keep deployment publication closure actions machine-checkable before
they are aggregated into promotion handoff plans.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: schemas/deployment_publication_closure_plan.schema.json and
.change_assurance/deployment_publication_closure_plan.json.
Invariants:
  - Deployment publication closure plans match the public protocol schema.
  - Action counts are derived from the action list, not trusted blindly.
  - Every blocker has an explicit closure action.
  - Production publication and status mutation actions require approval.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "deployment_publication_closure_plan.schema.json"
DEFAULT_PLAN = REPO_ROOT / ".change_assurance" / "deployment_publication_closure_plan.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "deployment_publication_closure_plan_schema_validation.json"


@dataclass(frozen=True, slots=True)
class DeploymentClosurePlanSchemaValidation:
    """Schema and semantic validation for one deployment closure plan."""

    ok: bool
    errors: tuple[str, ...]
    plan_path: str
    schema_path: str
    action_count: int
    approval_required_action_count: int
    blocker_count: int

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation report."""
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_deployment_publication_closure_plan_schema(
    *,
    plan_path: Path = DEFAULT_PLAN,
    schema_path: Path = DEFAULT_SCHEMA,
) -> DeploymentClosurePlanSchemaValidation:
    """Validate deployment closure plan schema and semantic consistency."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "deployment closure plan schema", errors)
    plan = _load_json_object(plan_path, "deployment closure plan", errors)
    if not schema or not plan:
        return _validation_result(
            plan_path=plan_path,
            schema_path=schema_path,
            errors=errors,
            actions=(),
            blockers=(),
        )

    errors.extend(_validate_schema_instance(schema, plan))
    actions = _actions(plan, errors)
    blockers = _blockers(plan, errors)
    if plan.get("action_count") != len(actions):
        errors.append("action_count does not match actions length")
    if plan.get("source_ready") is True and (actions or blockers):
        errors.append("source_ready deployment plan must not contain blockers or actions")
    if plan.get("source_ready") is False and blockers and not actions:
        errors.append("non-ready deployment plan requires closure actions")
    _validate_blocker_coverage(blockers=blockers, actions=actions, errors=errors)
    _validate_action_proof_contract(actions, errors)
    return _validation_result(
        plan_path=plan_path,
        schema_path=schema_path,
        errors=errors,
        actions=actions,
        blockers=blockers,
    )


def write_deployment_publication_closure_plan_schema_validation(
    validation: DeploymentClosurePlanSchemaValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic deployment closure plan schema validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_action_proof_contract(
    actions: tuple[dict[str, Any], ...],
    errors: list[str],
) -> None:
    for index, action in enumerate(actions):
        if action.get("approval_required") is not True:
            errors.append(f"deployment action {index} must require approval")
        if not action.get("evidence_required"):
            errors.append(f"deployment action {index} missing evidence_required")
        action_type = str(action.get("action_type", ""))
        evidence_required = {str(item) for item in action.get("evidence_required", ())}
        command = str(action.get("command", ""))
        if action_type == "publish-witness":
            required_evidence = {
                "gateway_publication_readiness.json",
                "gateway_publication_receipt.json",
                "deployment_witness.json",
                "operator_approval_ref",
            }
            missing_evidence = sorted(required_evidence - evidence_required)
            if missing_evidence:
                errors.append(
                    f"publish-witness action {index} evidence_required missing {missing_evidence}"
                )
            for token in ("publish_gateway_publication.py", "--dispatch-witness", "--dispatch"):
                if token not in command:
                    errors.append(f"publish-witness action {index} command missing token {token}")
        if action_type == "status-update":
            required_evidence = {
                "deployment_witness.json",
                "https_health_probe_receipt",
                "deployment_publication_closure_validation",
            }
            missing_evidence = sorted(required_evidence - evidence_required)
            if missing_evidence:
                errors.append(f"status-update action {index} evidence_required missing {missing_evidence}")
            if "DEPLOYMENT_STATUS.md" not in command:
                errors.append(f"status-update action {index} command missing DEPLOYMENT_STATUS.md")
        if action_type == "responsibility-debt-closure" and not any(
            evidence.endswith("_debt_clear") for evidence in evidence_required
        ):
            errors.append(f"responsibility-debt action {index} missing debt-clear evidence")
        if action_type == "secret-binding":
            if not any(evidence.startswith("gh_secret_list_presence:") for evidence in evidence_required):
                errors.append(f"secret-binding action {index} missing secret presence evidence")
            if "do not print or serialize" not in command:
                errors.append(f"secret-binding action {index} command missing no-secret-serialization guard")
        if action_type == "repository-variable-binding":
            if not any(evidence.startswith("gh_variable_list_presence:") for evidence in evidence_required):
                errors.append(f"repository-variable action {index} missing variable presence evidence")
        if action_type == "upstream-gate-closure":
            required_evidence = {
                "deployment_upstream_blocker_receipt",
                "deployment_upstream_blocker_validation",
                "upstream_recovery_completion_witness",
                "api_runtime_host_readiness",
                "dns_publication_authority",
            }
            missing_evidence = sorted(required_evidence - evidence_required)
            if missing_evidence:
                errors.append(
                    f"upstream-gate action {index} evidence_required missing {missing_evidence}"
                )
            for token in (
                "emit_deployment_upstream_blocker_receipt.py",
                "validate_deployment_upstream_blocker_receipt.py",
                "--require-ready",
            ):
                if token not in command:
                    errors.append(f"upstream-gate action {index} command missing token {token}")
        if action_type == "dns-verification" and "dns_resolution_receipt" not in evidence_required:
            errors.append(f"dns-verification action {index} missing dns_resolution_receipt")
        if action_type == "endpoint-verification" and not {
            "health_endpoint_receipt",
            "runtime_witness_receipt",
            "runtime_conformance_receipt",
        } <= evidence_required:
            errors.append(f"endpoint-verification action {index} missing endpoint evidence")
        if action_type == "workflow-repair" and "workflow_state_active" not in evidence_required:
            errors.append(f"workflow-repair action {index} missing workflow_state_active evidence")


def _validate_blocker_coverage(
    *,
    blockers: tuple[str, ...],
    actions: tuple[dict[str, Any], ...],
    errors: list[str],
) -> None:
    action_blockers = {str(action.get("blocker", "")) for action in actions}
    uncovered = tuple(blocker for blocker in blockers if blocker not in action_blockers)
    if uncovered:
        errors.append(f"deployment blockers missing closure actions: {list(uncovered)}")


def _validation_result(
    *,
    plan_path: Path,
    schema_path: Path,
    errors: list[str],
    actions: tuple[dict[str, Any], ...],
    blockers: tuple[str, ...],
) -> DeploymentClosurePlanSchemaValidation:
    return DeploymentClosurePlanSchemaValidation(
        ok=not errors,
        errors=tuple(errors),
        plan_path=str(plan_path),
        schema_path=str(schema_path),
        action_count=len(actions),
        approval_required_action_count=sum(
            1 for action in actions if action.get("approval_required") is True
        ),
        blocker_count=len(blockers),
    )


def _actions(plan: dict[str, Any], errors: list[str]) -> tuple[dict[str, Any], ...]:
    actions = plan.get("actions", ())
    if not isinstance(actions, list):
        errors.append("actions must be a list")
        return ()
    return tuple(action for action in actions if isinstance(action, dict))


def _blockers(plan: dict[str, Any], errors: list[str]) -> tuple[str, ...]:
    blockers = plan.get("blockers", ())
    if not isinstance(blockers, list):
        errors.append("blockers must be a list")
        return ()
    return tuple(str(blocker) for blocker in blockers)


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {path}")
        return {}
    try:
        payload = _loads_strict_json(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _loads_strict_json(raw: str) -> Any:
    return json.loads(raw, parse_constant=_reject_json_constant)


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse deployment closure plan schema validation arguments."""
    parser = argparse.ArgumentParser(description="Validate deployment closure plan schema.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for deployment closure plan schema validation."""
    args = parse_args(argv)
    validation = validate_deployment_publication_closure_plan_schema(
        plan_path=Path(args.plan),
        schema_path=Path(args.schema),
    )
    write_deployment_publication_closure_plan_schema_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("DEPLOYMENT PUBLICATION CLOSURE PLAN SCHEMA VALID")
    else:
        print(f"DEPLOYMENT PUBLICATION CLOSURE PLAN SCHEMA INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
