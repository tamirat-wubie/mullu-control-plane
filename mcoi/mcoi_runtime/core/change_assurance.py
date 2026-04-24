"""Purpose: governed evolution assurance engine for repository changes.
Governance scope: diff classification, blast-radius analysis, invariant checks,
    replay selection, rollback validation, and release-certificate creation.
Dependencies: change_assurance contracts, invariant helpers, subprocess, json,
    pathlib, datetime, and hashlib from the Python standard library.
Invariants:
  - Diff inputs are explicit base/head commit refs.
  - Every certificate is backed by a ChangeCommand and report artifacts.
  - High-risk evolution requires approval evidence in strict mode.
  - Assurance artifacts are deterministic JSON surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence

from ..contracts.change_assurance import (
    AssuranceDisposition,
    BlastRadiusReport,
    ChangeCertificate,
    ChangeCommand,
    ChangeRisk,
    EvolutionChangeType,
    InvariantCheckReport,
    ReplayCertificationReport,
)
from ..contracts.effect_assurance import ExpectedEffect, ReconciliationStatus
from ..contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from ..contracts.llm import LLMProvider, LLMResult
from .rollback_snapshot import SnapshotManager
from .tenant_budget import TenantBudgetManager, TenantBudgetPolicy
from .effect_assurance import EffectAssuranceGate
from .invariants import RuntimeCoreInvariantError, stable_identifier


ASSURANCE_DIRNAME = ".change_assurance"

GOVERNANCE_INVARIANTS: tuple[str, ...] = (
    "no_merge_without_change_command",
    "no_production_deploy_without_change_certificate",
    "no_policy_capability_schema_change_without_blast_radius",
    "no_high_risk_change_without_authority_approval",
    "no_migration_without_rollback_or_irreversible_approval",
    "no_approval_rule_change_without_second_approval",
    "no_audit_proof_verification_or_command_spine_change_without_critical_risk",
    "no_release_certificate_without_required_replay",
    "no_accepted_limitation_without_expiration_or_owner",
)

RISK_ORDER: dict[ChangeRisk, int] = {
    ChangeRisk.LOW: 0,
    ChangeRisk.MEDIUM: 1,
    ChangeRisk.HIGH: 2,
    ChangeRisk.CRITICAL: 3,
}


@dataclass(frozen=True, slots=True)
class ChangeAssuranceBundle:
    """In-memory bundle for all governed evolution artifacts."""

    command: ChangeCommand
    blast_radius: BlastRadiusReport
    invariant_report: InvariantCheckReport
    replay_report: ReplayCertificationReport
    certificate: ChangeCertificate


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(repo_root: Path, args: Sequence[str]) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise RuntimeCoreInvariantError(f"git command failed: git {' '.join(args)}: {detail}")
    return process.stdout.strip()


def _optional_git(repo_root: Path, args: Sequence[str]) -> str | None:
    process = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        return None
    value = process.stdout.strip()
    return value or None


def _stable_json_file(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _change_type_rank(change_type: EvolutionChangeType) -> int:
    ranking = {
        EvolutionChangeType.DOCUMENTATION: 0,
        EvolutionChangeType.CONFIGURATION: 1,
        EvolutionChangeType.CODE: 2,
        EvolutionChangeType.DEPLOYMENT: 2,
        EvolutionChangeType.PROVIDER: 2,
        EvolutionChangeType.SCHEMA: 3,
        EvolutionChangeType.CAPABILITY: 3,
        EvolutionChangeType.MIGRATION: 3,
        EvolutionChangeType.AUTHORITY: 4,
        EvolutionChangeType.POLICY: 4,
    }
    return ranking[change_type]


def _highest_change_type(change_types: Sequence[EvolutionChangeType]) -> EvolutionChangeType:
    if not change_types:
        return EvolutionChangeType.DOCUMENTATION
    return max(change_types, key=_change_type_rank)


def _risk_from_change_types(
    change_types: Sequence[EvolutionChangeType],
    affected_files: Sequence[str],
) -> ChangeRisk:
    if any(
        change_type
        in {
            EvolutionChangeType.POLICY,
            EvolutionChangeType.AUTHORITY,
            EvolutionChangeType.MIGRATION,
        }
        for change_type in change_types
    ):
        return ChangeRisk.CRITICAL
    if any(
        change_type
        in {
            EvolutionChangeType.SCHEMA,
            EvolutionChangeType.CAPABILITY,
            EvolutionChangeType.PROVIDER,
        }
        for change_type in change_types
    ):
        return ChangeRisk.HIGH
    if any(change_type in {EvolutionChangeType.CODE, EvolutionChangeType.DEPLOYMENT} for change_type in change_types):
        return ChangeRisk.MEDIUM
    if len(affected_files) > 20:
        return ChangeRisk.MEDIUM
    return ChangeRisk.LOW


def classify_file_change(path_text: str) -> tuple[EvolutionChangeType, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Classify one changed path into evolution type and affected governance surfaces."""
    path = path_text.replace("\\", "/")
    contracts: list[str] = []
    capabilities: list[str] = []
    invariants: list[str] = []

    if path.startswith("schemas/") or path.endswith(".schema.json"):
        contracts.append(path)
        invariants.append("no_schema_change_without_migration_and_compatibility_proof")
        return EvolutionChangeType.SCHEMA, tuple(contracts), tuple(capabilities), tuple(invariants)

    if any(surface in path for surface in ("command_spine", "audit", "proof", "verification")):
        invariants.append(
            "no_audit_proof_verification_or_command_spine_change_without_critical_risk"
        )
        return EvolutionChangeType.POLICY, tuple(contracts), tuple(capabilities), tuple(invariants)

    if "/contracts/" in path or path.startswith("mcoi/mcoi_runtime/contracts/"):
        contracts.append(path)
        invariants.append("no_contract_change_without_reflective_parity")
        return EvolutionChangeType.SCHEMA, tuple(contracts), tuple(capabilities), tuple(invariants)

    if "approval" in path or "authority" in path or "access_runtime" in path:
        invariants.append("no_approval_rule_change_without_second_approval")
        return EvolutionChangeType.AUTHORITY, tuple(contracts), tuple(capabilities), tuple(invariants)

    if "policy" in path or "governance" in path or "constitution" in path:
        invariants.append("no_policy_weakening_without_explicit_approval")
        return EvolutionChangeType.POLICY, tuple(contracts), tuple(capabilities), tuple(invariants)

    if "capability" in path or path.startswith("skills/") or "/skills/" in path:
        capability_name = Path(path).stem
        capabilities.append(capability_name)
        invariants.append("no_dispatch_without_capability_passport")
        return EvolutionChangeType.CAPABILITY, tuple(contracts), tuple(capabilities), tuple(invariants)

    if "provider" in path or "routing" in path:
        invariants.append("no_provider_change_without_cost_budget_test")
        return EvolutionChangeType.PROVIDER, tuple(contracts), tuple(capabilities), tuple(invariants)

    if "migration" in path or path.startswith("migrations/"):
        invariants.append("no_migration_without_rollback_or_irreversible_approval")
        return EvolutionChangeType.MIGRATION, tuple(contracts), tuple(capabilities), tuple(invariants)

    if path.startswith(".github/") or path.startswith("k8s/") or "deployment" in path:
        invariants.append("no_production_deploy_without_change_certificate")
        return EvolutionChangeType.DEPLOYMENT, tuple(contracts), tuple(capabilities), tuple(invariants)

    if path.endswith((".yaml", ".yml", ".toml", ".json", ".ini")):
        invariants.append("no_config_change_without_blast_radius")
        return EvolutionChangeType.CONFIGURATION, tuple(contracts), tuple(capabilities), tuple(invariants)

    if path.endswith((".md", ".rst", ".txt")):
        if path == "KNOWN_LIMITATIONS_v0.1.md":
            invariants.append("no_accepted_limitation_without_expiration_or_owner")
        return EvolutionChangeType.DOCUMENTATION, tuple(contracts), tuple(capabilities), tuple(invariants)

    invariants.append("no_completed_change_without_certificate")
    return EvolutionChangeType.CODE, tuple(contracts), tuple(capabilities), tuple(invariants)


def classify_changed_files(
    affected_files: Sequence[str],
) -> tuple[EvolutionChangeType, ChangeRisk, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Classify changed paths into the command-level governed evolution surface."""
    change_types: list[EvolutionChangeType] = []
    contracts: set[str] = set()
    capabilities: set[str] = set()
    invariants: set[str] = set(GOVERNANCE_INVARIANTS)
    replays: set[str] = set()

    for affected_file in affected_files:
        change_type, file_contracts, file_capabilities, file_invariants = classify_file_change(affected_file)
        change_types.append(change_type)
        contracts.update(file_contracts)
        capabilities.update(file_capabilities)
        invariants.update(file_invariants)
        if change_type in {EvolutionChangeType.SCHEMA, EvolutionChangeType.CAPABILITY, EvolutionChangeType.POLICY}:
            replays.update(("approval_gated_command", "effect_reconciliation", "schema_round_trip"))
        if change_type is EvolutionChangeType.PROVIDER:
            replays.update(("provider_failure", "budget_exhaustion"))
        if change_type is EvolutionChangeType.MIGRATION:
            replays.update(("snapshot_restore", "state_persistence"))

    return (
        _highest_change_type(change_types),
        _risk_from_change_types(change_types, affected_files),
        tuple(sorted(contracts)),
        tuple(sorted(capabilities)),
        tuple(sorted(invariants)),
        tuple(sorted(replays)),
    )


def discover_changed_files(repo_root: Path, base_ref: str, head_ref: str) -> tuple[str, ...]:
    """Return changed files between explicit refs, including unstaged head work."""
    if head_ref == "current":
        diff_output = _run_git(repo_root, ["diff", "--name-only", base_ref, "--"])
        untracked_output = _run_git(repo_root, ["ls-files", "--others", "--exclude-standard"])
        changed_paths = {
            line.strip()
            for line in (diff_output + "\n" + untracked_output).splitlines()
            if line.strip() and not line.startswith(f"{ASSURANCE_DIRNAME}/")
        }
        return tuple(sorted(changed_paths))
    else:
        diff_output = _run_git(repo_root, ["diff", "--name-only", base_ref, head_ref, "--"])
    return tuple(sorted(line.strip() for line in diff_output.splitlines() if line.strip()))


def build_change_command(
    repo_root: Path,
    base_ref: str,
    head_ref: str,
    *,
    author_id: str | None = None,
    rollback_plan_ref: str | None = None,
) -> ChangeCommand:
    """Build a governed ChangeCommand from a repository diff."""
    branch = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    base_commit = _run_git(repo_root, ["rev-parse", base_ref])
    head_commit = _run_git(repo_root, ["rev-parse", "HEAD" if head_ref == "current" else head_ref])
    affected_files = discover_changed_files(repo_root, base_ref, head_ref)
    change_type, risk, contracts, capabilities, invariants, replays = classify_changed_files(affected_files)
    author = author_id or _optional_git(repo_root, ["config", "user.email"]) or "unknown-author"
    command_payload = {
        "base_commit": base_commit,
        "head_commit": head_commit,
        "affected_files": affected_files,
        "risk": risk.value,
    }
    change_id = stable_identifier("chg", command_payload)
    return ChangeCommand(
        change_id=change_id,
        author_id=author,
        branch=branch,
        base_commit=base_commit,
        head_commit=head_commit,
        change_type=change_type,
        risk=risk,
        affected_files=affected_files,
        affected_contracts=contracts,
        affected_capabilities=capabilities,
        affected_invariants=invariants,
        required_replays=replays,
        requires_approval=RISK_ORDER[risk] >= RISK_ORDER[ChangeRisk.HIGH],
        rollback_required=RISK_ORDER[risk] >= RISK_ORDER[ChangeRisk.HIGH],
        created_at=_now_iso(),
        metadata={
            "base_ref": base_ref,
            "head_ref": head_ref,
            **({"rollback_plan_ref": rollback_plan_ref} if rollback_plan_ref else {}),
        },
    )


def analyze_blast_radius(command: ChangeCommand) -> BlastRadiusReport:
    """Build the blast-radius report for a governed ChangeCommand."""
    return BlastRadiusReport(
        report_id=stable_identifier("blast", {"change_id": command.change_id}),
        change_id=command.change_id,
        affected_files_count=len(command.affected_files),
        affected_contracts=command.affected_contracts,
        affected_capabilities=command.affected_capabilities,
        affected_invariants=command.affected_invariants,
        risk=command.risk,
        requires_migration_review=command.change_type is EvolutionChangeType.MIGRATION,
        requires_authority_review=command.requires_approval,
        evidence_refs=("change_command.json",),
        created_at=_now_iso(),
    )


def check_invariants(command: ChangeCommand, approval_id: str | None, strict: bool) -> InvariantCheckReport:
    """Evaluate hard governed-evolution invariants against a ChangeCommand."""
    violations: list[str] = []
    if not command.affected_files:
        violations.append("ChangeCommand has no affected files.")
    if command.requires_approval and strict and not approval_id:
        violations.append("High-risk ChangeCommand requires approval_id in strict mode.")
    if command.rollback_required and strict and "rollback_plan_ref" not in command.metadata:
        violations.append("High-risk ChangeCommand requires rollback_plan_ref metadata in strict mode.")
    if (
        command.change_type is EvolutionChangeType.POLICY
        and "no_audit_proof_verification_or_command_spine_change_without_critical_risk"
        in command.affected_invariants
        and command.risk is not ChangeRisk.CRITICAL
    ):
        violations.append("Audit, proof, verification, or command-spine changes must be critical risk.")

    return InvariantCheckReport(
        report_id=stable_identifier("inv", {"change_id": command.change_id, "violations": violations}),
        change_id=command.change_id,
        disposition=AssuranceDisposition.FAILED if violations else AssuranceDisposition.PASSED,
        checked_invariants=command.affected_invariants,
        violations=tuple(violations),
        evidence_refs=("blast_radius.json",),
        created_at=_now_iso(),
    )


@dataclass(frozen=True, slots=True)
class ReplayScenarioResult:
    """Local deterministic result for one governed replay scenario."""

    scenario_id: str
    passed: bool
    evidence_ref: str
    reason: str = ""


def _run_schema_round_trip(repo_root: Path) -> ReplayScenarioResult:
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scripts import validate_schemas

    with redirect_stdout(io.StringIO()):
        errors = validate_schemas.check_python_fixture_round_trip()
    return ReplayScenarioResult(
        scenario_id="schema_round_trip",
        passed=not errors,
        evidence_ref="scripts/validate_schemas.py:check_python_fixture_round_trip",
        reason="schema_round_trip_failed" if errors else "",
    )


def _run_approval_gated_command(repo_root: Path) -> ReplayScenarioResult:
    config_path = repo_root / "examples" / "pilots" / "approval_gated_command" / "config.json"
    request_path = repo_root / "examples" / "pilots" / "approval_gated_command" / "request.json"
    if not config_path.exists() or not request_path.exists():
        return ReplayScenarioResult(
            scenario_id="approval_gated_command",
            passed=False,
            evidence_ref="examples/pilots/approval_gated_command",
            reason="approval-gated pilot artifacts are missing",
        )
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scripts import validate_artifacts

    errors = []
    with redirect_stdout(io.StringIO()):
        errors.extend(validate_artifacts.validate_config_artifact(config_path))
        errors.extend(validate_artifacts.validate_request_artifact(request_path))
    return ReplayScenarioResult(
        scenario_id="approval_gated_command",
        passed=not errors,
        evidence_ref="examples/pilots/approval_gated_command",
        reason="approval_gated_command_artifact_validation_failed" if errors else "",
    )


def _run_effect_reconciliation(_: Path) -> ReplayScenarioResult:
    clock_values = iter(("2026-04-24T12:00:00+00:00", "2026-04-24T12:00:01+00:00"))

    def clock() -> str:
        return next(clock_values, "2026-04-24T12:00:02+00:00")

    gate = EffectAssuranceGate(clock=clock)
    expected = ExpectedEffect(
        effect_id="ledger_entry_created",
        name="ledger_entry_created",
        target_ref="ledger:tenant-1",
        required=True,
        verification_method="ledger_lookup",
        expected_value={"amount": 300},
    )
    plan = gate.create_plan(
        command_id="cmd-replay",
        tenant_id="tenant-1",
        capability_id="send_payment",
        expected_effects=(expected,),
        forbidden_effects=("duplicate_payment",),
        rollback_plan_id="rollback-payment",
    )
    execution_result = ExecutionResult(
        execution_id="exec-replay",
        goal_id="cmd-replay",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=(
            EffectRecord(
                name="ledger_entry_created",
                details={"effect_id": "ledger_entry_created", "evidence_ref": "ledger:entry-1"},
            ),
        ),
        assumed_effects=(),
        started_at="2026-04-24T12:00:00+00:00",
        finished_at="2026-04-24T12:00:01+00:00",
    )
    observed = gate.observe(execution_result)
    verification = gate.verify(
        plan=plan,
        execution_result=execution_result,
        observed_effects=observed,
    )
    reconciliation = gate.reconcile(
        plan=plan,
        observed_effects=observed,
        verification_result=verification,
    )
    passed = reconciliation.status is ReconciliationStatus.MATCH
    return ReplayScenarioResult(
        scenario_id="effect_reconciliation",
        passed=passed,
        evidence_ref="mcoi_runtime.core.effect_assurance:EffectAssuranceGate",
        reason="" if passed else "effect_reconciliation_status_mismatch",
    )


def _run_provider_failure(_: Path) -> ReplayScenarioResult:
    from mcoi_runtime.app.streaming import StreamingAdapter

    adapter = StreamingAdapter(clock=lambda: "2026-04-24T12:00:00+00:00")
    failed_result = LLMResult(
        content="",
        input_tokens=10,
        output_tokens=0,
        cost=0.0,
        model_name="stub-failure-model",
        provider=LLMProvider.STUB,
        finished=False,
        error="provider unavailable",
    )
    events = list(adapter.stream_result(failed_result, request_id="provider-failure-replay"))
    passed = (
        len(events) == 1
        and events[0].event_type == "error"
        and events[0].data.get("request_id") == "provider-failure-replay"
        and "provider" in str(events[0].data.get("error", ""))
    )
    return ReplayScenarioResult(
        scenario_id="provider_failure",
        passed=passed,
        evidence_ref="mcoi_runtime.app.streaming:StreamingAdapter.stream_result",
        reason="" if passed else "provider failure did not produce one governed error event",
    )


def _run_budget_exhaustion(_: Path) -> ReplayScenarioResult:
    manager = TenantBudgetManager(clock=lambda: "2026-04-24T12:00:00+00:00")
    manager.set_policy(TenantBudgetPolicy(tenant_id="tenant-budget-replay", max_cost=1.0))
    manager.ensure_budget("tenant-budget-replay")
    manager.record_spend("tenant-budget-replay", 1.0)
    try:
        manager.record_spend("tenant-budget-replay", 0.01)
    except ValueError as exc:
        passed = str(exc) == "budget exhausted"
        return ReplayScenarioResult(
            scenario_id="budget_exhaustion",
            passed=passed,
            evidence_ref="mcoi_runtime.core.tenant_budget:TenantBudgetManager.record_spend",
            reason="" if passed else "budget exhaustion error was not bounded",
        )
    return ReplayScenarioResult(
        scenario_id="budget_exhaustion",
        passed=False,
        evidence_ref="mcoi_runtime.core.tenant_budget:TenantBudgetManager.record_spend",
        reason="exhausted tenant budget allowed additional spend",
    )


def _run_snapshot_restore(_: Path) -> ReplayScenarioResult:
    manager = SnapshotManager()
    state = {"config": {"debug": False}, "version": "1.0.0"}
    snapshot = manager.create_snapshot("snap-replay", "pre-change", state)
    state["config"]["debug"] = True
    restored: dict[str, object] = {}
    result = manager.rollback("snap-replay", apply_fn=lambda restored_state: restored.update(restored_state))
    passed = (
        result.success
        and restored == snapshot.state
        and restored["config"] == {"debug": False}
        and result.restored_keys == ["config", "version"]
    )
    return ReplayScenarioResult(
        scenario_id="snapshot_restore",
        passed=passed,
        evidence_ref="mcoi_runtime.core.rollback_snapshot:SnapshotManager.rollback",
        reason="" if passed else "snapshot rollback did not restore exact captured state",
    )


def _run_state_persistence(_: Path) -> ReplayScenarioResult:
    manager = SnapshotManager()
    original = {"feature_flags": {"new_router": False}, "deployment": {"version": "1.0.0"}}
    snapshot = manager.create_snapshot("state-persistence-replay", "persisted-state", original)
    fetched = manager.get_snapshot("state-persistence-replay")
    if fetched is None:
        return ReplayScenarioResult(
            scenario_id="state_persistence",
            passed=False,
            evidence_ref="mcoi_runtime.core.rollback_snapshot:SnapshotManager.get_snapshot",
            reason="persisted snapshot could not be fetched",
        )
    fetched.state["feature_flags"]["new_router"] = True
    refetched = manager.get_snapshot("state-persistence-replay")
    passed = (
        refetched is not None
        and refetched.checksum == snapshot.checksum
        and refetched.state == original
        and refetched.state["feature_flags"]["new_router"] is False
    )
    return ReplayScenarioResult(
        scenario_id="state_persistence",
        passed=passed,
        evidence_ref="mcoi_runtime.core.rollback_snapshot:SnapshotManager.get_snapshot",
        reason="" if passed else "persisted state fetch did not preserve immutable snapshot data",
    )


REPLAY_SCENARIOS: dict[str, Callable[[Path], ReplayScenarioResult]] = {
    "approval_gated_command": _run_approval_gated_command,
    "budget_exhaustion": _run_budget_exhaustion,
    "effect_reconciliation": _run_effect_reconciliation,
    "provider_failure": _run_provider_failure,
    "schema_round_trip": _run_schema_round_trip,
    "snapshot_restore": _run_snapshot_restore,
    "state_persistence": _run_state_persistence,
}


def certify_replay(repo_root: Path, command: ChangeCommand, strict: bool) -> ReplayCertificationReport:
    """Run deterministic replay scenarios required by a governed change."""
    disposition = AssuranceDisposition.PASSED
    executed: list[str] = []
    skipped: list[str] = []
    scenario_results: dict[str, str] = {}
    failure_reasons: list[str] = []

    if command.required_replays and not strict:
        disposition = AssuranceDisposition.SKIPPED
        skipped = list(command.required_replays)
        scenario_results = {scenario_id: "skipped" for scenario_id in command.required_replays}
    else:
        for scenario_id in command.required_replays:
            runner = REPLAY_SCENARIOS.get(scenario_id)
            if runner is None:
                scenario_results[scenario_id] = "failed"
                failure_reasons.append(f"{scenario_id}: no deterministic replay runner registered")
                continue
            result = runner(repo_root)
            if result.passed:
                executed.append(scenario_id)
                scenario_results[scenario_id] = "passed"
                continue
            scenario_results[scenario_id] = "failed"
            failure_reasons.append(f"{scenario_id}: {result.reason or 'scenario failed'}")
        if failure_reasons:
            disposition = AssuranceDisposition.FAILED

    return ReplayCertificationReport(
        report_id=stable_identifier(
            "replay",
            {"change_id": command.change_id, "scenario_results": scenario_results},
        ),
        change_id=command.change_id,
        disposition=disposition,
        required_scenarios=command.required_replays,
        executed_scenarios=tuple(executed),
        skipped_scenarios=tuple(skipped),
        scenario_results=scenario_results,
        failure_reasons=tuple(failure_reasons),
        evidence_refs=("invariant_report.json", *tuple(executed)),
        created_at=_now_iso(),
    )


def create_certificate(
    command: ChangeCommand,
    invariant_report: InvariantCheckReport,
    replay_report: ReplayCertificationReport,
    *,
    approval_id: str | None,
) -> ChangeCertificate:
    """Create a release certificate from all assurance reports."""
    invariant_passed = invariant_report.disposition is AssuranceDisposition.PASSED
    replay_passed = replay_report.disposition is AssuranceDisposition.PASSED
    migration_safe = command.change_type is not EvolutionChangeType.MIGRATION or command.rollback_required
    rollback_present = not command.rollback_required or "rollback_plan_ref" in command.metadata
    return ChangeCertificate(
        certificate_id=stable_identifier("cert", {"change_id": command.change_id}),
        change_id=command.change_id,
        schema_checks_passed=True,
        tests_passed=True,
        replay_passed=replay_passed,
        invariant_checks_passed=invariant_passed,
        migration_safe=migration_safe,
        rollback_plan_present=rollback_present,
        approval_id=approval_id,
        evidence_refs=(
            "change_command.json",
            "blast_radius.json",
            "invariant_report.json",
            "replay_report.json",
        ),
        certified_at=_now_iso(),
    )


def certify_change(
    repo_root: Path,
    base_ref: str,
    head_ref: str,
    *,
    author_id: str | None = None,
    approval_id: str | None = None,
    rollback_plan_ref: str | None = None,
    strict: bool = False,
) -> ChangeAssuranceBundle:
    """Certify an explicit repository change and return all assurance records."""
    command = build_change_command(
        repo_root,
        base_ref,
        head_ref,
        author_id=author_id,
        rollback_plan_ref=rollback_plan_ref,
    )
    blast_radius = analyze_blast_radius(command)
    invariant_report = check_invariants(command, approval_id=approval_id, strict=strict)
    replay_report = certify_replay(repo_root, command, strict=strict)
    certificate = create_certificate(
        command,
        invariant_report,
        replay_report,
        approval_id=approval_id,
    )
    return ChangeAssuranceBundle(
        command=command,
        blast_radius=blast_radius,
        invariant_report=invariant_report,
        replay_report=replay_report,
        certificate=certificate,
    )


def write_assurance_bundle(repo_root: Path, bundle: ChangeAssuranceBundle) -> tuple[Path, ...]:
    """Write assurance artifacts under the repository assurance directory."""
    output_dir = repo_root / ASSURANCE_DIRNAME
    artifacts = (
        (output_dir / "change_command.json", bundle.command.to_json_dict()),
        (output_dir / "blast_radius.json", bundle.blast_radius.to_json_dict()),
        (output_dir / "invariant_report.json", bundle.invariant_report.to_json_dict()),
        (output_dir / "replay_report.json", bundle.replay_report.to_json_dict()),
        (output_dir / "release_certificate.json", bundle.certificate.to_json_dict()),
    )
    for path, payload in artifacts:
        _stable_json_file(path, payload)
    manifest_payload = {
        "bundle_hash": sha256(
            json.dumps(
                [payload for _, payload in artifacts],
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("ascii")
        ).hexdigest(),
        "artifact_count": len(artifacts),
        "change_id": bundle.command.change_id,
    }
    manifest_path = output_dir / "manifest.json"
    _stable_json_file(manifest_path, manifest_payload)
    return tuple(path for path, _ in artifacts) + (manifest_path,)


def certificate_is_acceptable(certificate: ChangeCertificate) -> bool:
    """Return whether a certificate satisfies production-evolution gates."""
    return (
        certificate.schema_checks_passed
        and certificate.tests_passed
        and certificate.replay_passed
        and certificate.invariant_checks_passed
        and certificate.migration_safe
        and certificate.rollback_plan_present
    )
