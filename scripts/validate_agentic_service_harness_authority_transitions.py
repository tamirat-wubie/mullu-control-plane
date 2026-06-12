#!/usr/bin/env python3
"""Validate planning-only Agentic Service Harness authority transitions.

Purpose: prove the first harness fixtures expose only governed authority
states before UI, mutation endpoints, persistence adapters, external adapter
execution, branch writes, pull-request creation, or high-risk actions are
implemented.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: examples/agentic_service_harness.*.json and
scripts.validate_agentic_service_harness_contract.
Invariants:
  - Read-only and dry-run scenarios remain non-effectful.
  - Branch-write and open-PR scenarios remain awaiting explicit approval.
  - High-risk actions remain blocked by default.
  - Repository write authority, external effects, terminal closure, and changed
    file claims are not admitted by fixture transitions.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_contract import (  # noqa: E402
    BLOCKED_HIGH_RISK_ACTIONS,
    DEFAULT_EXAMPLES,
    EXPECTED_SCENARIOS,
    validate_agentic_service_harness_contract,
)


DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_authority_transition_validation.json"
)

AUTHORITY_RULES: dict[str, dict[str, Any]] = {
    "read_only_status": {
        "action_class": "read_only",
        "mode": "read_only",
        "allowed_statuses": {"contract_only", "ready_read_only"},
        "policy_result": "allowed_read_only",
        "solver_outcome": "AwaitingEvidence",
        "risk_level": "low",
        "gate_status": None,
        "repository_scope": "read_only",
    },
    "dry_run_task": {
        "action_class": "dry_run",
        "mode": "dry_run",
        "allowed_statuses": {"contract_only", "ready_dry_run"},
        "policy_result": "allowed_dry_run",
        "solver_outcome": "AwaitingEvidence",
        "risk_level": "low",
        "gate_status": None,
        "repository_scope": "dry_run",
    },
    "branch_write_awaiting_approval": {
        "action_class": "write_to_branch",
        "mode": "branch_write",
        "allowed_statuses": {"awaiting_approval"},
        "policy_result": "awaiting_approval",
        "solver_outcome": "AwaitingEvidence",
        "risk_level": "medium",
        "gate_status": "pending",
        "repository_scope": "write_to_branch",
    },
    "open_pr_awaiting_approval": {
        "action_class": "open_pr",
        "mode": "open_pr",
        "allowed_statuses": {"awaiting_approval"},
        "policy_result": "awaiting_approval",
        "solver_outcome": "AwaitingEvidence",
        "risk_level": "high",
        "gate_status": "pending",
        "repository_scope": "open_pr",
    },
    "blocked_high_risk_action": {
        "action_class": "blocked_high_risk",
        "mode": "read_only",
        "allowed_statuses": {"blocked"},
        "policy_result": "blocked_high_risk",
        "solver_outcome": "GovernanceBlocked",
        "risk_level": "critical",
        "gate_status": "blocked",
        "repository_scope": "read_only",
    },
}
EFFECT_ACTION_CLASSES = {"write_to_branch", "open_pr"}
APPROVAL_GATE_STATUSES = {"pending", "blocked"}


@dataclass(frozen=True, slots=True)
class AgenticServiceHarnessAuthorityTransitionValidation:
    """Validation report for harness authority transition fixtures."""

    ok: bool
    errors: tuple[str, ...]
    source_paths: tuple[str, ...]
    scenario_count: int
    transition_count: int
    blocked_high_risk_action_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["source_paths"] = list(self.source_paths)
        return payload


def validate_agentic_service_harness_authority_transitions(
    *,
    source_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> AgenticServiceHarnessAuthorityTransitionValidation:
    """Validate governed authority states for harness contract fixtures."""
    errors: list[str] = []
    source_validation = validate_agentic_service_harness_contract(
        example_paths=tuple(source_paths)
    )
    errors.extend(f"source contract: {error}" for error in source_validation.errors)

    observed_scenarios: set[str] = set()
    transition_count = 0
    blocked_actions: set[str] = set()
    for source_path in source_paths:
        contract = _load_json_object(
            source_path,
            f"harness authority source {_path_label(source_path)}",
            errors,
        )
        if not contract:
            continue
        scenario = str(contract.get("scenario", ""))
        label = _path_label(source_path)
        observed_scenarios.add(scenario)
        transition_count += _validate_contract_authority_state(contract, errors, label)
        for run in _objects(contract.get("agent_runs")):
            blocked_actions.update(str(action) for action in run.get("blocked_actions", ()))

    missing = sorted(set(EXPECTED_SCENARIOS) - observed_scenarios)
    extra = sorted(observed_scenarios - set(EXPECTED_SCENARIOS))
    if missing:
        errors.append(f"authority scenarios missing {missing}")
    if extra:
        errors.append(f"authority scenarios unknown {extra}")

    return AgenticServiceHarnessAuthorityTransitionValidation(
        ok=not errors,
        errors=tuple(errors),
        source_paths=tuple(_path_label(path) for path in source_paths),
        scenario_count=len(observed_scenarios),
        transition_count=transition_count,
        blocked_high_risk_action_count=len(
            blocked_actions & set(BLOCKED_HIGH_RISK_ACTIONS)
        ),
    )


def write_authority_transition_validation(
    validation: AgenticServiceHarnessAuthorityTransitionValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic authority transition validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_contract_authority_state(
    contract: dict[str, Any],
    errors: list[str],
    label: str,
) -> int:
    scenario = str(contract.get("scenario", ""))
    rule = AUTHORITY_RULES.get(scenario)
    if rule is None:
        errors.append(f"{label}: missing authority rule for scenario {scenario!r}")
        return 0

    tasks = _objects(contract.get("agent_tasks"))
    runs = _objects(contract.get("agent_runs"))
    receipts = _objects(contract.get("receipts"))
    summaries = _objects(contract.get("result_summaries"))
    gates = _objects(contract.get("approval_gates"))
    repositories = _objects(contract.get("repository_connections"))
    adapters = _objects(contract.get("agent_adapters"))

    if len(tasks) != 1:
        errors.append(f"{label}: expected exactly one agent task")
    if len(runs) != 1:
        errors.append(f"{label}: expected exactly one agent run")
    if len(receipts) != 1:
        errors.append(f"{label}: expected exactly one receipt")
    if len(summaries) != 1:
        errors.append(f"{label}: expected exactly one result summary")

    task = tasks[0] if tasks else {}
    run = runs[0] if runs else {}
    receipt = receipts[0] if receipts else {}
    summary = summaries[0] if summaries else {}

    _validate_status(contract.get("status"), rule, errors, label, "contract.status")
    _validate_status(task.get("status"), rule, errors, label, "agent_task.status")
    _validate_status(run.get("status"), rule, errors, label, "agent_run.status")
    if task.get("action_class") != rule["action_class"]:
        errors.append(f"{label}: agent_task.action_class must be {rule['action_class']}")
    if task.get("mode") != rule["mode"]:
        errors.append(f"{label}: agent_task.mode must be {rule['mode']}")
    if run.get("mode") != rule["mode"]:
        errors.append(f"{label}: agent_run.mode must be {rule['mode']}")
    if receipt.get("mode") != rule["mode"]:
        errors.append(f"{label}: receipt.mode must be {rule['mode']}")
    if task.get("risk_level") != rule["risk_level"]:
        errors.append(f"{label}: agent_task.risk_level must be {rule['risk_level']}")
    if receipt.get("risk_level") != rule["risk_level"]:
        errors.append(f"{label}: receipt.risk_level must be {rule['risk_level']}")
    if receipt.get("policy_result") != rule["policy_result"]:
        errors.append(f"{label}: receipt.policy_result must be {rule['policy_result']}")
    if contract.get("solver_outcome") != rule["solver_outcome"]:
        errors.append(f"{label}: solver_outcome must be {rule['solver_outcome']}")
    _validate_receipt_effects(receipt, errors, label, rule["action_class"])
    _validate_summary(summary, errors, label, rule)
    _validate_gate_binding(task, run, gates, errors, label, rule)
    _validate_repository_scope(repositories, errors, label, rule["repository_scope"])
    _validate_adapter_authority(adapters, errors, label, rule)
    _validate_blocked_high_risk_actions(run, errors, label, rule)
    _validate_permission_closure(contract.get("permission_model"), errors, label)
    return 1 if tasks and runs and receipts else 0


def _validate_status(
    observed: Any,
    rule: dict[str, Any],
    errors: list[str],
    label: str,
    field_label: str,
) -> None:
    if observed not in rule["allowed_statuses"]:
        expected = sorted(rule["allowed_statuses"])
        errors.append(f"{label}: {field_label} must be one of {expected}")


def _validate_receipt_effects(
    receipt: dict[str, Any],
    errors: list[str],
    label: str,
    action_class: str,
) -> None:
    files_changed = receipt.get("files_changed")
    if not isinstance(files_changed, dict):
        errors.append(f"{label}: receipt.files_changed must be an object")
        return
    if files_changed.get("changed_file_count") != 0:
        errors.append(f"{label}: receipt changed_file_count must remain 0")
    if files_changed.get("changed_file_refs"):
        errors.append(f"{label}: receipt changed_file_refs must remain empty")
    if action_class == "write_to_branch" and files_changed.get("diff_refs"):
        errors.append(f"{label}: branch write awaiting approval cannot carry diffs")
    if action_class in EFFECT_ACTION_CLASSES and receipt.get("commands_run"):
        errors.append(f"{label}: effect-awaiting receipt cannot claim commands run")
    if receipt.get("receipt_is_not_terminal_closure") is not True:
        errors.append(f"{label}: receipt must remain non-terminal")


def _validate_summary(
    summary: dict[str, Any],
    errors: list[str],
    label: str,
    rule: dict[str, Any],
) -> None:
    if summary.get("changed_file_count") != 0:
        errors.append(f"{label}: summary changed_file_count must remain 0")
    action_class = rule["action_class"]
    blockers = set(str(item) for item in summary.get("blockers", ()))
    if action_class in EFFECT_ACTION_CLASSES and "approval_required" not in blockers:
        errors.append(f"{label}: effect action summary must list approval_required")
    if action_class == "open_pr" and "branch_evidence_required" not in blockers:
        errors.append(f"{label}: open_pr summary must list branch_evidence_required")
    if action_class == "blocked_high_risk":
        if summary.get("outcome") != "GovernanceBlocked":
            errors.append(f"{label}: blocked high-risk summary must be GovernanceBlocked")
    elif summary.get("outcome") != "AwaitingEvidence":
        errors.append(f"{label}: non-terminal summary must be AwaitingEvidence")


def _validate_gate_binding(
    task: dict[str, Any],
    run: dict[str, Any],
    gates: tuple[dict[str, Any], ...],
    errors: list[str],
    label: str,
    rule: dict[str, Any],
) -> None:
    required_gate_ids = list(task.get("required_approval_gate_ids", ()))
    run_gate_ids = list(run.get("approval_gate_ids", ()))
    expected_gate_status = rule["gate_status"]
    if expected_gate_status is None:
        if required_gate_ids:
            errors.append(f"{label}: read-only authority cannot require approval gates")
        if run_gate_ids:
            errors.append(f"{label}: read-only run cannot carry approval gates")
        if gates:
            errors.append(f"{label}: read-only authority cannot define approval gates")
        return

    if required_gate_ids != run_gate_ids:
        errors.append(f"{label}: task and run approval gate ids must match")
    if len(gates) != len(required_gate_ids):
        errors.append(f"{label}: approval gate count must match required gate ids")
    for gate in gates:
        gate_id = str(gate.get("gate_id"))
        if gate_id not in required_gate_ids:
            errors.append(f"{label}: approval gate {gate_id} is not required")
        if gate.get("status") != expected_gate_status:
            errors.append(f"{label}: gate {gate_id} status must be {expected_gate_status}")
        if gate.get("status") not in APPROVAL_GATE_STATUSES:
            errors.append(f"{label}: gate {gate_id} cannot be terminal or approved")
        if gate.get("action_class") != rule["action_class"]:
            errors.append(f"{label}: gate {gate_id} action_class must match task")
        if gate.get("run_id") != run.get("run_id"):
            errors.append(f"{label}: gate {gate_id} run_id must match run")
        if gate.get("approval_required") is not True:
            errors.append(f"{label}: gate {gate_id} must require approval")
        if gate.get("self_approval_allowed") is not False:
            errors.append(f"{label}: gate {gate_id} must block self approval")
        if gate.get("permits_external_effect") is not False:
            errors.append(f"{label}: gate {gate_id} must not permit external effect")


def _validate_repository_scope(
    repositories: tuple[dict[str, Any], ...],
    errors: list[str],
    label: str,
    repository_scope: str,
) -> None:
    if not repositories:
        errors.append(f"{label}: repository connection required")
    for repository in repositories:
        if repository.get("permission_scope") != repository_scope:
            errors.append(f"{label}: repository permission_scope must be {repository_scope}")
        if repository.get("write_authority_enabled") is not False:
            errors.append(f"{label}: repository write authority must remain false")
        if repository.get("secret_values_serialized") is not False:
            errors.append(f"{label}: repository secret serialization must remain false")


def _validate_adapter_authority(
    adapters: tuple[dict[str, Any], ...],
    errors: list[str],
    label: str,
    rule: dict[str, Any],
) -> None:
    if not adapters:
        errors.append(f"{label}: agent adapter required")
    for adapter in adapters:
        if adapter.get("external_adapter_integrated") is not False:
            errors.append(f"{label}: adapter integration must remain false")
        if rule["action_class"] in EFFECT_ACTION_CLASSES:
            if adapter.get("authority_class") != "approval_required":
                errors.append(f"{label}: effect adapter authority must require approval")
        elif rule["action_class"] == "blocked_high_risk":
            if adapter.get("authority_class") != "blocked":
                errors.append(f"{label}: high-risk adapter authority must be blocked")
        elif adapter.get("authority_class") != "read_only":
            errors.append(f"{label}: non-effect adapter authority must be read_only")


def _validate_blocked_high_risk_actions(
    run: dict[str, Any],
    errors: list[str],
    label: str,
    rule: dict[str, Any],
) -> None:
    observed = set(str(item) for item in run.get("blocked_actions", ()))
    expected = set(BLOCKED_HIGH_RISK_ACTIONS)
    if rule["action_class"] == "blocked_high_risk":
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        if missing:
            errors.append(f"{label}: blocked high-risk run missing {missing}")
        if extra:
            errors.append(f"{label}: blocked high-risk run has unknown {extra}")
    elif observed:
        errors.append(f"{label}: non-high-risk run cannot list blocked actions")


def _validate_permission_closure(
    permission_model: Any,
    errors: list[str],
    label: str,
) -> None:
    if not isinstance(permission_model, dict):
        errors.append(f"{label}: permission_model must be an object")
        return
    for flag_name in (
        "can_merge",
        "can_deploy",
        "can_mutate_dns",
        "can_mutate_secrets",
        "can_run_destructive_operations",
    ):
        if permission_model.get(flag_name) is not False:
            errors.append(f"{label}: permission_model.{flag_name} must remain false")


def _objects(collection: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(collection, list):
        return ()
    return tuple(item for item in collection if isinstance(item, dict))


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse harness authority transition validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate planning-only harness authority transitions."
    )
    parser.add_argument("--source", action="append", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for harness authority transition validation."""
    args = parse_args(argv)
    source_paths = (
        tuple(Path(source) for source in args.source)
        if args.source
        else DEFAULT_EXAMPLES
    )
    validation = validate_agentic_service_harness_authority_transitions(
        source_paths=source_paths,
    )
    write_authority_transition_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS AUTHORITY TRANSITIONS VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS AUTHORITY TRANSITIONS INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
