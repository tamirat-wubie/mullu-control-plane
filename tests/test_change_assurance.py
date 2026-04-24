"""Purpose: test governed evolution ChangeCommand assurance behavior.
Governance scope: verifies contract validation, deterministic diff
    classification, invariant failure paths, and certificate acceptance.
Dependencies: pytest and the MCOI change_assurance contract/core layers.
Invariants:
  - ChangeCommand records are frozen and explicit.
  - Sensitive system-law edits receive elevated risk and replay obligations.
  - Strict certification fails without required approval or rollback evidence.
  - Certificate acceptance is derived from all assurance gates.
"""

from types import MappingProxyType
from pathlib import Path

import pytest

import mcoi_runtime.core.change_assurance as change_assurance_core
from mcoi_runtime.contracts.change_assurance import (
    AssuranceDisposition,
    ChangeCommand,
    ChangeRisk,
    EvolutionChangeType,
)
from mcoi_runtime.core.change_assurance import (
    analyze_blast_radius,
    certificate_is_acceptable,
    certify_replay,
    check_invariants,
    classify_changed_files,
    create_certificate,
    discover_changed_files,
)


DT = "2026-04-24T12:00:00+00:00"


def _command(**overrides: object) -> ChangeCommand:
    values = {
        "change_id": "chg-1",
        "author_id": "dev@mullusi.com",
        "branch": "codex/change-assurance",
        "base_commit": "a" * 40,
        "head_commit": "b" * 40,
        "change_type": EvolutionChangeType.CAPABILITY,
        "risk": ChangeRisk.HIGH,
        "affected_files": ("skills/financial/skills/governed_payment.py",),
        "affected_contracts": (),
        "affected_capabilities": ("governed_payment",),
        "affected_invariants": ("no_dispatch_without_capability_passport",),
        "required_replays": ("approval_gated_command",),
        "requires_approval": True,
        "rollback_required": True,
        "created_at": DT,
        "metadata": {"base_ref": "main", "head_ref": "current"},
    }
    values.update(overrides)
    return ChangeCommand(**values)


def test_change_command_contract_is_explicit_and_frozen() -> None:
    command = _command()
    payload = command.to_json_dict()

    assert command.change_id == "chg-1"
    assert command.risk is ChangeRisk.HIGH
    assert command.affected_files == ("skills/financial/skills/governed_payment.py",)
    assert payload["change_type"] == "capability"
    assert isinstance(command.metadata, MappingProxyType)
    with pytest.raises(Exception):
        command.affected_files += ("extra.py",)  # type: ignore[misc]


def test_change_command_rejects_undefined_identity_and_enum_surfaces() -> None:
    with pytest.raises(ValueError):
        _command(change_id="")
    with pytest.raises(ValueError):
        _command(change_type="capability")
    with pytest.raises(ValueError):
        _command(risk="high")


def test_classifier_elevates_schema_capability_and_authority_changes() -> None:
    change_type, risk, contracts, capabilities, invariants, replays = classify_changed_files(
        (
            "schemas/policy_decision.schema.json",
            "gateway/authority.py",
            "skills/financial/skills/governed_payment.py",
        )
    )

    assert change_type is EvolutionChangeType.AUTHORITY
    assert risk is ChangeRisk.CRITICAL
    assert contracts == ("schemas/policy_decision.schema.json",)
    assert capabilities == ("governed_payment",)
    assert "no_approval_rule_change_without_second_approval" in invariants
    assert "approval_gated_command" in replays


def test_classifier_marks_command_spine_changes_as_critical_governance() -> None:
    change_type, risk, contracts, capabilities, invariants, replays = classify_changed_files(
        ("gateway/command_spine.py", "tests/test_gateway/test_command_spine.py")
    )

    assert change_type is EvolutionChangeType.POLICY
    assert risk is ChangeRisk.CRITICAL
    assert contracts == ()
    assert capabilities == ()
    assert "no_audit_proof_verification_or_command_spine_change_without_critical_risk" in invariants
    assert replays == ("approval_gated_command", "effect_reconciliation", "schema_round_trip")


def test_strict_invariants_fail_without_approval_and_rollback_evidence() -> None:
    command = _command()
    report = check_invariants(command, approval_id=None, strict=True)

    assert report.disposition is AssuranceDisposition.FAILED
    assert len(report.violations) == 2
    assert "approval_id" in report.violations[0]
    assert "rollback_plan_ref" in report.violations[1]


def test_certificate_acceptance_requires_all_gates() -> None:
    command = _command(metadata={"base_ref": "main", "head_ref": "current", "rollback_plan_ref": "runbook-1"})
    invariant_report = check_invariants(command, approval_id="approval-1", strict=True)
    replay_report = certify_replay(Path(__file__).resolve().parent.parent, command, strict=True)
    certificate = create_certificate(
        command,
        invariant_report,
        replay_report,
        approval_id="approval-1",
    )

    assert invariant_report.disposition is AssuranceDisposition.PASSED
    assert replay_report.executed_scenarios == ("approval_gated_command",)
    assert replay_report.scenario_results["approval_gated_command"] == "passed"
    assert replay_report.failure_reasons == ()
    assert certificate.rollback_plan_present is True
    assert certificate.approval_id == "approval-1"
    assert certificate_is_acceptable(certificate) is True


def test_blast_radius_binds_command_scope_and_evidence() -> None:
    command = _command()
    report = analyze_blast_radius(command)

    assert report.change_id == command.change_id
    assert report.affected_files_count == 1
    assert report.affected_capabilities == ("governed_payment",)
    assert report.requires_authority_review is True
    assert report.evidence_refs == ("change_command.json",)


def test_current_diff_includes_untracked_files_and_excludes_assurance_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_git(repo_root: object, args: list[str]) -> str:
        assert repo_root is not None
        if args == ["diff", "--name-only", "HEAD", "--"]:
            return "scripts/validate_release_status.py\n"
        if args == ["ls-files", "--others", "--exclude-standard"]:
            return "scripts/certify_change.py\n.change_assurance/release_certificate.json\n"
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setattr(change_assurance_core, "_run_git", fake_run_git)
    changed_files = discover_changed_files(repo_root=object(), base_ref="HEAD", head_ref="current")  # type: ignore[arg-type]

    assert changed_files == ("scripts/certify_change.py", "scripts/validate_release_status.py")
    assert ".change_assurance/release_certificate.json" not in changed_files
    assert len(changed_files) == 2


def test_strict_replay_fails_for_unregistered_required_scenario() -> None:
    command = _command(required_replays=("unknown_replay_scenario",))
    report = certify_replay(Path(__file__).resolve().parent.parent, command, strict=True)

    assert report.disposition is AssuranceDisposition.FAILED
    assert report.executed_scenarios == ()
    assert report.scenario_results["unknown_replay_scenario"] == "failed"
    assert "no deterministic replay runner" in report.failure_reasons[0]


def test_strict_replay_executes_provider_budget_restore_and_persistence_scenarios() -> None:
    required = (
        "provider_failure",
        "budget_exhaustion",
        "snapshot_restore",
        "state_persistence",
    )
    command = _command(required_replays=required)
    report = certify_replay(Path(__file__).resolve().parent.parent, command, strict=True)

    assert report.disposition is AssuranceDisposition.PASSED
    assert report.executed_scenarios == required
    assert report.skipped_scenarios == ()
    assert report.failure_reasons == ()
    assert report.scenario_results == {scenario_id: "passed" for scenario_id in required}
    assert "provider_failure" in report.evidence_refs
