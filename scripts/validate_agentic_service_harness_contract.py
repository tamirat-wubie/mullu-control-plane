#!/usr/bin/env python3
"""Validate the planning-only Agentic Service Harness contract examples.

Purpose: keep the first Mullusi Agentic Service Harness contract bounded to
planning, schema, receipt, approval, sandbox, and permission evidence before
any user-facing harness implementation starts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness.schema.json,
examples/agentic_service_harness.*.json, and scripts.validate_schemas.
Invariants:
  - Contract examples do not create UI, mutation endpoints, external adapter
    integrations, or default high-risk authority.
  - Branch-write and open-PR examples remain approval-gated and non-external.
  - Blocked high-risk actions include merge, deploy, DNS, secret, and
    destructive operations.
  - Examples serialize no secret values and expose no mutation route strings.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness.read_only.json",
    REPO_ROOT / "examples" / "agentic_service_harness.dry_run.json",
    REPO_ROOT / "examples" / "agentic_service_harness.branch_write_awaiting_approval.json",
    REPO_ROOT / "examples" / "agentic_service_harness.open_pr_awaiting_approval.json",
    REPO_ROOT / "examples" / "agentic_service_harness.blocked_high_risk.json",
)
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "agentic_service_harness_contract_validation.json"

EXPECTED_SCENARIOS = (
    "read_only_status",
    "dry_run_task",
    "branch_write_awaiting_approval",
    "open_pr_awaiting_approval",
    "blocked_high_risk_action",
)
EXPECTED_ROLES = ("viewer", "operator", "approver", "admin")
EXPECTED_ACTION_CLASSES = (
    "read_only",
    "dry_run",
    "write_to_branch",
    "open_pr",
    "blocked_high_risk",
)
BLOCKED_HIGH_RISK_ACTIONS = (
    "merge",
    "deploy",
    "dns_mutation",
    "secret_mutation",
    "destructive_operation",
)
VALID_LIFECYCLE_STATES = {
    "queued",
    "running",
    "awaiting_approval",
    "completed",
    "blocked",
    "cancelled",
}
TERMINAL_LIFECYCLE_STATES = {"completed", "blocked", "cancelled"}
EXPECTED_NON_GOALS = (
    "no_unrestricted_openclaw_automation",
    "no_claude_code_integration",
    "no_email_sending",
    "no_production_deploy_approval_by_default",
    "no_dns_mutation",
    "no_secret_mutation",
    "no_marketplace",
    "no_billing_requirement",
    "no_multi_agent_marketplace",
)
DENIAL_FLAGS = (
    "ui_created",
    "mutation_endpoints_admitted",
    "external_adapter_integrated",
    "default_high_risk_authority",
)
HIGH_RISK_PERMISSION_FLAGS = (
    "can_merge",
    "can_deploy",
    "can_mutate_dns",
    "can_mutate_secrets",
    "can_run_destructive_operations",
)
ALLOWED_SECRET_KEYS = {
    "can_mutate_secrets",
    "contains_secret_values",
    "no_secret_mutation",
    "secret_redaction_required",
    "secret_redaction_strategy",
    "secret_values_serialized",
}
FORBIDDEN_SECRET_KEY_TOKENS = (
    "access_token",
    "api_key",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "secret_value",
    "token",
)
FORBIDDEN_CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bsk-[A-Za-z0-9_=-]{8,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b")


@dataclass(frozen=True, slots=True)
class AgenticServiceHarnessContractValidation:
    """Schema and semantic validation for harness contract examples."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    scenario_count: int
    blocked_high_risk_action_count: int
    non_goal_count: int

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready validation report."""
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_contract(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> AgenticServiceHarnessContractValidation:
    """Validate all Agentic Service Harness contract examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "agentic service harness schema", errors)
    contracts: list[dict[str, Any]] = []

    for example_path in example_paths:
        contract = _load_json_object(
            example_path,
            f"agentic service harness example {_path_label(example_path)}",
            errors,
        )
        if not contract:
            continue
        contracts.append(contract)
        if schema:
            label = _path_label(example_path)
            errors.extend(
                f"{label}: {error}"
                for error in _validate_schema_instance(schema, contract)
            )
        _validate_contract_semantics(contract, errors, _path_label(example_path))

    _validate_scenario_coverage(contracts, errors)
    blocked_actions = _observed_blocked_high_risk_actions(contracts)
    non_goals = _observed_non_goals(contracts)
    return AgenticServiceHarnessContractValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        scenario_count=len({str(contract.get("scenario")) for contract in contracts}),
        blocked_high_risk_action_count=len(blocked_actions),
        non_goal_count=len(non_goals),
    )


def write_agentic_service_harness_contract_validation(
    validation: AgenticServiceHarnessContractValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic harness contract validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_contract_semantics(
    contract: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    scenario = str(contract.get("scenario", "<missing>"))
    _validate_denial_flags(contract, errors, label)
    _validate_permission_model(contract, errors, label)
    _validate_repository_connections(contract, errors, label)
    _validate_agent_runs(contract, errors, label)
    _validate_non_goals(contract, errors, label)
    _validate_approval_gates(contract, errors, label)
    _validate_blocked_high_risk_scenario(contract, errors, label, scenario)
    _validate_sandbox_boundaries(contract, errors, label)
    _validate_secret_surface(contract, errors, label)
    _validate_no_mutation_route_strings(contract, errors, label)


def _validate_denial_flags(
    contract: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    for flag_name in DENIAL_FLAGS:
        if contract.get(flag_name) is not False:
            errors.append(f"{label}: {flag_name} must remain false")


def _validate_permission_model(
    contract: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    permission_model = contract.get("permission_model")
    if not isinstance(permission_model, dict):
        errors.append(f"{label}: permission_model must be an object")
        return

    _validate_complete_set(
        observed=permission_model.get("roles", ()),
        expected=EXPECTED_ROLES,
        label=f"{label}: permission_model.roles",
        errors=errors,
    )
    _validate_complete_set(
        observed=permission_model.get("action_classes", ()),
        expected=EXPECTED_ACTION_CLASSES,
        label=f"{label}: permission_model.action_classes",
        errors=errors,
    )
    _validate_complete_set(
        observed=permission_model.get("blocked_high_risk_actions", ()),
        expected=BLOCKED_HIGH_RISK_ACTIONS,
        label=f"{label}: permission_model.blocked_high_risk_actions",
        errors=errors,
    )
    for flag_name in HIGH_RISK_PERMISSION_FLAGS:
        if permission_model.get(flag_name) is not False:
            errors.append(f"{label}: permission_model.{flag_name} must remain false")


def _validate_repository_connections(
    contract: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    repositories = contract.get("repository_connections")
    if not isinstance(repositories, list) or not repositories:
        errors.append(f"{label}: repository_connections must be a non-empty list")
        return
    for repository in _objects(repositories):
        connection_id = repository.get("connection_id")
        repository_label = f"{label}: repository_connection {connection_id}"
        if repository.get("provider") != "github":
            errors.append(f"{repository_label} provider must be github")
        for ref_name in (
            "provider_repository_ref",
            "installation_ref",
            "credential_binding_ref",
            "revocation_evidence_ref",
        ):
            if not isinstance(repository.get(ref_name), str) or not repository.get(ref_name):
                errors.append(f"{repository_label} {ref_name} must be a non-empty ref")
        if repository.get("installation_state") not in {
            "presence_only",
            "active",
            "revoked",
            "requires_reauth",
        }:
            errors.append(f"{repository_label} installation_state is invalid")
        if repository.get("revocation_state") not in {
            "not_revoked",
            "revoked",
            "pending_revalidation",
        }:
            errors.append(f"{repository_label} revocation_state is invalid")
        if repository.get("secret_values_serialized") is not False:
            errors.append(f"{repository_label} secret_values_serialized must remain false")
        if repository.get("write_authority_enabled") is not False:
            errors.append(f"{repository_label} write_authority_enabled must remain false")
        permission_scopes = repository.get("permission_scopes")
        if not isinstance(permission_scopes, list) or not permission_scopes:
            errors.append(f"{repository_label} permission_scopes must be a non-empty list")
        elif any(str(scope).endswith("_write") for scope in permission_scopes):
            errors.append(f"{repository_label} permission_scopes must not include write scopes")


def _validate_non_goals(
    contract: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _validate_complete_set(
        observed=contract.get("non_goals", ()),
        expected=EXPECTED_NON_GOALS,
        label=f"{label}: non_goals",
        errors=errors,
    )


def _validate_approval_gates(
    contract: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    approval_gates = contract.get("approval_gates", ())
    if not isinstance(approval_gates, list):
        errors.append(f"{label}: approval_gates must be a list")
        return

    for index, gate in enumerate(approval_gates):
        if not isinstance(gate, dict):
            errors.append(f"{label}: approval_gates[{index}] must be an object")
            continue
        action_class = gate.get("action_class")
        if action_class not in {"write_to_branch", "open_pr"}:
            continue
        if gate.get("status") != "pending":
            errors.append(f"{label}: {action_class} gate {index} must stay pending")
        if gate.get("approval_required") is not True:
            errors.append(f"{label}: {action_class} gate {index} must require approval")
        if gate.get("self_approval_allowed") is not False:
            errors.append(f"{label}: {action_class} gate {index} must block self approval")
        if gate.get("permits_external_effect") is not False:
            errors.append(
                f"{label}: {action_class} gate {index} must not permit external effect"
            )


def _validate_agent_runs(
    contract: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    for run in _objects(contract.get("agent_runs", ())):
        run_label = f"{label}: agent_run {run.get('run_id')}"
        lifecycle_state = run.get("lifecycle_state")
        terminal_state = run.get("terminal_state")
        if lifecycle_state not in VALID_LIFECYCLE_STATES:
            errors.append(f"{run_label} lifecycle_state is invalid")
        if not isinstance(run.get("lifecycle_updated_at"), str) or not run.get("lifecycle_updated_at"):
            errors.append(f"{run_label} lifecycle_updated_at must be a non-empty timestamp")
        transition_receipt_refs = run.get("transition_receipt_refs")
        if not isinstance(transition_receipt_refs, list) or not transition_receipt_refs:
            errors.append(f"{run_label} transition_receipt_refs must be a non-empty list")
        if run.get("status") == "awaiting_approval" and lifecycle_state != "awaiting_approval":
            errors.append(f"{run_label} awaiting approval status must match lifecycle_state")
        if run.get("status") == "blocked" and lifecycle_state != "blocked":
            errors.append(f"{run_label} blocked status must match lifecycle_state")
        if lifecycle_state in TERMINAL_LIFECYCLE_STATES and terminal_state is not True:
            errors.append(f"{run_label} terminal lifecycle state must set terminal_state true")
        if lifecycle_state not in TERMINAL_LIFECYCLE_STATES and terminal_state is not False:
            errors.append(f"{run_label} non-terminal lifecycle state must set terminal_state false")


def _validate_blocked_high_risk_scenario(
    contract: dict[str, Any],
    errors: list[str],
    label: str,
    scenario: str,
) -> None:
    if scenario != "blocked_high_risk_action":
        return
    if contract.get("status") != "blocked":
        errors.append(f"{label}: blocked_high_risk_action status must be blocked")
    if contract.get("solver_outcome") != "GovernanceBlocked":
        errors.append(
            f"{label}: blocked_high_risk_action solver_outcome must be GovernanceBlocked"
        )
    for gate in _objects(contract.get("approval_gates", ())):
        if gate.get("action_class") == "blocked_high_risk" and gate.get("status") != "blocked":
            errors.append(f"{label}: blocked high-risk approval gate must stay blocked")
    for summary in _objects(contract.get("result_summaries", ())):
        if summary.get("outcome") != "GovernanceBlocked":
            errors.append(f"{label}: blocked high-risk result must be GovernanceBlocked")
    for run in _objects(contract.get("agent_runs", ())):
        _validate_complete_set(
            observed=run.get("blocked_actions", ()),
            expected=BLOCKED_HIGH_RISK_ACTIONS,
            label=f"{label}: blocked_high_risk agent_run.blocked_actions",
            errors=errors,
        )


def _validate_sandbox_boundaries(
    contract: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    for index, sandbox in enumerate(_objects(contract.get("workspace_sandboxes", ()))):
        if sandbox.get("production_mutation_allowed") is not False:
            errors.append(f"{label}: workspace_sandboxes[{index}] cannot mutate production")
        if sandbox.get("secret_redaction_required") is not True:
            errors.append(f"{label}: workspace_sandboxes[{index}] must require redaction")
        if not sandbox.get("command_allowlist"):
            errors.append(f"{label}: workspace_sandboxes[{index}] missing command allowlist")
        if not sandbox.get("path_allowlist"):
            errors.append(f"{label}: workspace_sandboxes[{index}] missing path allowlist")
        if not isinstance(sandbox.get("timeout_seconds"), int):
            errors.append(f"{label}: workspace_sandboxes[{index}] missing timeout budget")


def _validate_secret_surface(
    payload: Any,
    errors: list[str],
    label: str,
) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if (
            any(token in key_lower for token in FORBIDDEN_SECRET_KEY_TOKENS)
            and key_lower not in ALLOWED_SECRET_KEYS
        ):
            errors.append(f"{label}: forbidden secret-bearing key at {path}")
        if key_lower in {"secret_values_serialized", "contains_secret_values"} and value is not False:
            errors.append(f"{label}: {path} must be false")
        if isinstance(value, str):
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"{label}: credential-like value at {path}")
                    break


def _validate_no_mutation_route_strings(
    payload: Any,
    errors: list[str],
    label: str,
) -> None:
    for path, value in _walk_strings(payload):
        if MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string at {path}")


def _validate_scenario_coverage(
    contracts: Sequence[dict[str, Any]],
    errors: list[str],
) -> None:
    observed = [str(contract.get("scenario")) for contract in contracts]
    observed_set = set(observed)
    expected_set = set(EXPECTED_SCENARIOS)
    missing = sorted(expected_set - observed_set)
    extra = sorted(observed_set - expected_set)
    if missing:
        errors.append(f"scenario examples missing: {missing}")
    if extra:
        errors.append(f"scenario examples unknown: {extra}")
    if len(observed) != len(observed_set):
        errors.append("scenario examples must be unique")


def _observed_blocked_high_risk_actions(
    contracts: Sequence[dict[str, Any]],
) -> set[str]:
    observed: set[str] = set()
    for contract in contracts:
        permission_model = contract.get("permission_model")
        if isinstance(permission_model, dict):
            observed.update(str(item) for item in permission_model.get("blocked_high_risk_actions", ()))
        for run in _objects(contract.get("agent_runs", ())):
            observed.update(str(item) for item in run.get("blocked_actions", ()))
    return observed & set(BLOCKED_HIGH_RISK_ACTIONS)


def _observed_non_goals(contracts: Sequence[dict[str, Any]]) -> set[str]:
    observed: set[str] = set()
    for contract in contracts:
        observed.update(str(item) for item in contract.get("non_goals", ()))
    return observed & set(EXPECTED_NON_GOALS)


def _validate_complete_set(
    *,
    observed: Any,
    expected: Sequence[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(observed, list):
        errors.append(f"{label} must be a list")
        return
    observed_set = {str(item) for item in observed}
    expected_set = set(expected)
    missing = sorted(expected_set - observed_set)
    extra = sorted(observed_set - expected_set)
    if missing:
        errors.append(f"{label} missing {missing}")
    if extra:
        errors.append(f"{label} has unknown values {extra}")


def _objects(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _walk_json(payload: Any, path: str = "$") -> Iterable[tuple[str, str, Any]]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), value
            yield from _walk_json(value, child_path)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            yield from _walk_json(item, f"{path}[{index}]")


def _walk_strings(payload: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield from _walk_strings(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            yield from _walk_strings(item, f"{path}[{index}]")
    elif isinstance(payload, str):
        yield path, payload


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
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


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse harness contract validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate planning-only Agentic Service Harness contracts."
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", action="append", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for harness contract validation."""
    args = parse_args(argv)
    example_paths = (
        tuple(Path(example) for example in args.example)
        if args.example
        else DEFAULT_EXAMPLES
    )
    validation = validate_agentic_service_harness_contract(
        schema_path=Path(args.schema),
        example_paths=example_paths,
    )
    write_agentic_service_harness_contract_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS CONTRACT VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS CONTRACT INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
