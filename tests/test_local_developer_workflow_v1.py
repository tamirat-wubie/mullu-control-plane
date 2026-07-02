"""Tests for Local Developer Workflow v1 preview artifacts.

Purpose: prove the local developer workflow bundle emits useful operator
artifacts without source mutation or external effect authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: software_dev.local_developer_workflow_v1 runner and CLIs.
Invariants: artifacts remain preview-only, linked, and no-authority.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

import pytest


_ROOT = Path(__file__).resolve().parent.parent
_MCOI_ROOT = _ROOT / "mcoi"
for import_root in (_ROOT, _MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from software_dev.local_developer_workflow_v1.runner import (  # noqa: E402
    ARTIFACT_FILENAMES,
    DEFAULT_OBJECTIVE,
    build_local_developer_workflow_v1_artifacts,
    validate_local_developer_workflow_v1_artifacts,
    write_local_developer_workflow_v1_artifacts,
)
from software_dev.local_developer_workflow_v1.closure_packet import (  # noqa: E402
    CLOSURE_PACKET_FILENAME,
    CLOSURE_PACKET_ID,
    LocalDeveloperWorkflowClosurePacketError,
    build_local_developer_workflow_closure_packet,
    validate_local_developer_workflow_closure_packet,
    write_local_developer_workflow_closure_packet,
)
from software_dev.local_developer_workflow_v1.command_preview_packet import (  # noqa: E402
    COMMAND_PREVIEW_PACKET_FILENAME,
    COMMAND_PREVIEW_PACKET_ID,
    build_local_developer_workflow_pr_command_preview_packet,
    validate_local_developer_workflow_pr_command_preview_packet,
    write_local_developer_workflow_pr_command_preview_packet,
)
from software_dev.local_developer_workflow_v1.pr_admission_packet import (  # noqa: E402
    PR_ADMISSION_PACKET_FILENAME,
    PR_ADMISSION_PACKET_ID,
    build_local_developer_workflow_pr_admission_packet,
    validate_local_developer_workflow_pr_admission_packet,
    write_local_developer_workflow_pr_admission_packet,
)
from software_dev.local_developer_workflow_v1.composition import (  # noqa: E402
    BLOCKED_EXTERNAL_EFFECTS,
    COMPOSITION_WORKFLOW_ID,
    TERMINAL_WAIT_STAGE_ID,
    build_foundation_workflow_composition_descriptor,
    build_foundation_workflow_composition_read_model,
    validate_foundation_workflow_composition,
)
from mcoi_runtime.contracts.workflow import StageType  # noqa: E402
from scripts.build_local_developer_workflow_closure_packet import main as build_closure_packet_main  # noqa: E402
from scripts.build_local_developer_workflow_pr_command_preview_packet import main as build_command_packet_main  # noqa: E402
from scripts.build_local_developer_workflow_pr_admission_packet import main as build_admission_packet_main  # noqa: E402
from scripts.run_local_developer_workflow_v1 import main as run_main  # noqa: E402
from scripts.validate_local_developer_workflow_closure_packet import main as validate_closure_packet_main  # noqa: E402
from scripts.validate_local_developer_workflow_pr_command_preview_packet import main as validate_command_packet_main  # noqa: E402
from scripts.validate_local_developer_workflow_pr_admission_packet import main as validate_admission_packet_main  # noqa: E402
from scripts.validate_local_developer_workflow_v1 import main as validate_main  # noqa: E402


FIXTURE_REPO_STATUS = {
    "repo_root": "C:/repo",
    "git_top_level": "C:/repo",
    "branch": "codex/local-workflow",
    "status_lines": ["## codex/local-workflow", " M scripts/example.py"],
    "changed_files": ["scripts/example.py", "tests/test_example.py"],
    "dirty": True,
    "commands": {},
}


def test_local_developer_workflow_v1_builds_all_preview_artifacts() -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
        objective=DEFAULT_OBJECTIVE,
    )
    validation = validate_local_developer_workflow_v1_artifacts(artifacts=artifacts)

    assert tuple(artifacts) == tuple(ARTIFACT_FILENAMES)
    assert validation.ok is True
    assert artifacts["repo_status"]["dirty"] is True
    assert artifacts["patch_plan"]["draft"]["status"] == "drafted"
    assert artifacts["diff_proposal"]["proposal_status"] == "preview_only"
    assert artifacts["test_plan"]["tests_executed"] is False
    assert artifacts["approval_request"]["approval_status"] == "pending"
    assert artifacts["pr_command_preview"]["preview_only"] is True
    assert artifacts["pr_command_preview"]["execution_performed"] is False
    assert artifacts["receipt"]["status"] == "AwaitingEvidence"


def test_local_developer_workflow_v1_writes_and_validates_artifacts(tmp_path: Path) -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
    )
    paths = write_local_developer_workflow_v1_artifacts(artifacts, tmp_path)
    loaded = {
        key: json.loads(path.read_text(encoding="utf-8"))
        for key, path in paths.items()
    }
    validation = validate_local_developer_workflow_v1_artifacts(
        artifacts=loaded,
        artifact_paths=paths,
    )

    assert set(paths) == set(ARTIFACT_FILENAMES)
    assert all(path.exists() for path in paths.values())
    assert validation.ok is True
    assert validation.artifact_paths["receipt"] == str(paths["receipt"])


def test_local_developer_workflow_v1_rejects_authority_overclaim() -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
    )
    artifacts["receipt"]["execution_performed"] = True
    artifacts["pr_command_preview"]["command_preview"][0]["execution_allowed"] = True
    artifacts["diff_proposal"]["effect_boundary"]["file_write_performed"] = True
    validation = validate_local_developer_workflow_v1_artifacts(artifacts=artifacts)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "execution_performed_must_be_false" in serialized_errors
    assert "preview_command_execution_allowed" in serialized_errors
    assert "effect_boundary_enabled:file_write_performed" in serialized_errors


def test_local_developer_workflow_v1_rejects_link_drift() -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
    )
    artifacts["test_plan"]["patch_plan_id"] = "drifted"
    artifacts["approval_request"]["source_refs"]["test_plan_id"] = "drifted"
    validation = validate_local_developer_workflow_v1_artifacts(artifacts=artifacts)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "test_plan:patch_plan_id_mismatch" in serialized_errors
    assert "approval_request:test_plan_link_mismatch" in serialized_errors


def test_local_developer_workflow_v1_cli_writes_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_main([
        "--output-dir",
        str(tmp_path),
        "--repo-root",
        str(_ROOT),
        "--strict",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["status"] == "AwaitingEvidence"
    assert sorted(payload["artifact_paths"]) == sorted(ARTIFACT_FILENAMES)
    assert payload["closure_packet_status"] == "AwaitingEvidence"
    assert Path(payload["closure_packet_path"]).exists()
    assert payload["command_preview_packet_status"] == "AwaitingEvidence"
    assert Path(payload["command_preview_packet_path"]).exists()
    assert payload["pr_admission_packet_decision"] == "blocked_waiting_external_execution_approval"
    assert Path(payload["pr_admission_packet_path"]).exists()


def test_local_developer_workflow_v1_validator_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
    )
    paths = write_local_developer_workflow_v1_artifacts(artifacts, tmp_path)
    output_path = tmp_path / "validation.json"
    exit_code = validate_main([
        "--repo-status",
        str(paths["repo_status"]),
        "--patch-plan",
        str(paths["patch_plan"]),
        "--diff-proposal",
        str(paths["diff_proposal"]),
        "--test-plan",
        str(paths["test_plan"]),
        "--receipt",
        str(paths["receipt"]),
        "--approval-request",
        str(paths["approval_request"]),
        "--pr-command-preview",
        str(paths["pr_command_preview"]),
        "--closure-packet",
        str(tmp_path / CLOSURE_PACKET_FILENAME),
        "--command-preview-packet",
        str(tmp_path / COMMAND_PREVIEW_PACKET_FILENAME),
        "--pr-admission-packet",
        str(tmp_path / PR_ADMISSION_PACKET_FILENAME),
        "--output",
        str(output_path),
        "--strict",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["ok"] is True
    assert saved["status"] == "AwaitingEvidence"
    assert saved["closure_packet_status"] == "not_present"
    assert saved["command_preview_packet_status"] == "not_present"
    assert saved["pr_admission_packet_decision"] == "not_present"


def test_foundation_workflow_composition_descriptor_is_valid() -> None:
    descriptor = build_foundation_workflow_composition_descriptor()
    validation = validate_foundation_workflow_composition(descriptor)
    stage_ids = tuple(stage.stage_id for stage in descriptor.stages)
    stage_types = {stage.stage_id: stage.stage_type for stage in descriptor.stages}

    assert validation.ok is True
    assert validation.errors == ()
    assert descriptor.workflow_id == COMPOSITION_WORKFLOW_ID
    assert stage_ids == (
        "select_capability_closure_lane",
        "draft_patch_proposal",
        "assemble_local_workflow_preview",
        "rehearse_safe_local_action",
        "project_operator_dashboard",
        "classify_causal_repair",
        "operator_review_gate",
        TERMINAL_WAIT_STAGE_ID,
    )
    assert stage_types["operator_review_gate"] is StageType.APPROVAL_GATE
    assert stage_types[TERMINAL_WAIT_STAGE_ID] is StageType.WAIT_FOR_EVENT


def test_foundation_workflow_composition_read_model_blocks_live_effects() -> None:
    read_model = build_foundation_workflow_composition_read_model()

    assert read_model["projection_only"] is True
    assert read_model["execution_performed"] is False
    assert read_model["external_effects_allowed"] is False
    assert read_model["grants_new_capability_authority"] is False
    assert tuple(read_model["blocked_external_effects"]) == BLOCKED_EXTERNAL_EFFECTS
    assert all(value is False for value in read_model["effect_boundary"].values())
    assert read_model["terminal_stage_id"] == TERMINAL_WAIT_STAGE_ID
    assert read_model["verification"]["valid"] is True
    assert read_model["rollback"]["rollback_execution_performed"] is False


def test_foundation_workflow_composition_rejects_terminal_halt_drift() -> None:
    descriptor = build_foundation_workflow_composition_descriptor()
    stages = list(descriptor.stages)
    terminal_index = next(index for index, stage in enumerate(stages) if stage.stage_id == TERMINAL_WAIT_STAGE_ID)
    stages[terminal_index] = replace(stages[terminal_index], stage_type=StageType.OBSERVATION)
    drifted = replace(descriptor, stages=tuple(stages))

    validation = validate_foundation_workflow_composition(drifted)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "terminal_stage_must_wait_for_event" in serialized_errors
    assert validation.terminal_stage_id == TERMINAL_WAIT_STAGE_ID


def test_local_developer_workflow_closure_packet_summarizes_next_proof_step() -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
    )
    packet = build_local_developer_workflow_closure_packet(artifacts=artifacts)
    validation = validate_local_developer_workflow_closure_packet(packet=packet, artifacts=artifacts)

    assert validation.ok is True
    assert packet["packet_id"] == CLOSURE_PACKET_ID
    assert packet["projection_only"] is True
    assert packet["execution_performed"] is False
    assert packet["external_effects_allowed"] is False
    assert packet["current_gate"]["gate_type"] == "approval_gate"
    assert packet["approval_boundary"]["approval_status"] == "pending"
    assert packet["approval_boundary"]["approval_does_not_authorize_execution"] is True
    assert packet["missing_evidence_refs"]
    assert "collect review-only operator decision" in packet["next_required_proof_step"]
    assert packet["rollback"]["rollback_executed"] is False
    assert all(command["execution_allowed"] is False for command in packet["command_preview"])


def test_local_developer_workflow_closure_packet_rejects_authority_overclaim() -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
    )
    packet = build_local_developer_workflow_closure_packet(artifacts=artifacts)
    packet["execution_performed"] = True
    packet["approval_boundary"]["approval_performed"] = True
    packet["rollback"]["rollback_executed"] = True
    packet["command_preview"][0]["execution_allowed"] = True

    validation = validate_local_developer_workflow_closure_packet(packet=packet, artifacts=artifacts)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "execution_performed_must_be_false" in serialized_errors
    assert "approval_performed_must_be_false" in serialized_errors
    assert "rollback_executed_must_be_false" in serialized_errors
    assert "command_preview[0]_execution_allowed_must_be_false" in serialized_errors
    assert "packet_hash_mismatch" in serialized_errors


def test_local_developer_workflow_closure_packet_rejects_dashboard_overclaim() -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
    )

    with pytest.raises(LocalDeveloperWorkflowClosurePacketError, match="operator_dashboard_execution_must_be_false"):
        build_local_developer_workflow_closure_packet(
            artifacts=artifacts,
            operator_dashboard={
                "projection_only": True,
                "execution_performed": True,
                "external_effects_allowed": False,
                "rows": [],
            },
        )


def test_local_developer_workflow_closure_packet_cli_builds_and_validates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
    )
    write_local_developer_workflow_v1_artifacts(artifacts, tmp_path)
    packet_path = tmp_path / CLOSURE_PACKET_FILENAME

    build_exit = build_closure_packet_main([
        "--artifact-dir",
        str(tmp_path),
        "--output",
        str(packet_path),
        "--strict",
        "--json",
    ])
    build_payload = json.loads(capsys.readouterr().out)
    validate_exit = validate_closure_packet_main([
        "--artifact-dir",
        str(tmp_path),
        "--packet",
        str(packet_path),
        "--output",
        str(tmp_path / "closure-packet-validation.json"),
        "--strict",
        "--json",
    ])
    validate_payload = json.loads(capsys.readouterr().out)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))

    assert build_exit == 0
    assert validate_exit == 0
    assert build_payload["ok"] is True
    assert validate_payload["ok"] is True
    assert packet["packet_id"] == CLOSURE_PACKET_ID
    assert packet["status"] == "AwaitingEvidence"
    assert packet["operator_dashboard"]["linked"] is False


def test_local_developer_workflow_pr_command_preview_packet_summarizes_review_commands() -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
    )
    closure_packet = build_local_developer_workflow_closure_packet(artifacts=artifacts)
    packet = build_local_developer_workflow_pr_command_preview_packet(
        artifacts=artifacts,
        closure_packet=closure_packet,
    )
    validation = validate_local_developer_workflow_pr_command_preview_packet(
        packet=packet,
        artifacts=artifacts,
        closure_packet=closure_packet,
    )

    assert validation.ok is True
    assert packet["packet_id"] == COMMAND_PREVIEW_PACKET_ID
    assert packet["projection_only"] is True
    assert packet["command_preview_is_review_only"] is True
    assert packet["execution_performed"] is False
    assert packet["external_effects_allowed"] is False
    assert packet["commands_rendered"] is True
    assert packet["command_count"] == 2
    assert packet["approval"]["approval_performed"] is False
    assert packet["approval"]["approval_does_not_authorize_execution"] is True
    assert [command["effect"] for command in packet["command_preview"]] == ["push_branch", "open_external_pr"]
    assert all(command["execution_allowed"] is False for command in packet["command_preview"])
    assert all(command["review_only"] is True for command in packet["command_preview"])


def test_local_developer_workflow_pr_command_preview_packet_rejects_authority_overclaim() -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
    )
    packet = build_local_developer_workflow_pr_command_preview_packet(artifacts=artifacts)
    packet["execution_performed"] = True
    packet["external_effects_allowed"] = True
    packet["approval"]["approval_performed"] = True
    packet["command_preview"][0]["execution_allowed"] = True

    validation = validate_local_developer_workflow_pr_command_preview_packet(
        packet=packet,
        artifacts=artifacts,
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "execution_performed_must_be_false" in serialized_errors
    assert "external_effects_allowed_must_be_false" in serialized_errors
    assert "approval_performed_must_be_false" in serialized_errors
    assert "command_preview[0]_execution_allowed_must_be_false" in serialized_errors
    assert "packet_hash_mismatch" in serialized_errors


def test_local_developer_workflow_pr_command_preview_packet_cli_builds_and_validates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
    )
    paths = write_local_developer_workflow_v1_artifacts(artifacts, tmp_path)
    closure_packet = build_local_developer_workflow_closure_packet(
        artifacts=artifacts,
        artifact_paths=paths,
    )
    closure_path = write_local_developer_workflow_closure_packet(
        closure_packet,
        tmp_path / CLOSURE_PACKET_FILENAME,
    )
    output_path = tmp_path / COMMAND_PREVIEW_PACKET_FILENAME

    build_exit = build_command_packet_main([
        "--artifact-dir",
        str(tmp_path),
        "--closure-packet",
        str(closure_path),
        "--output",
        str(output_path),
        "--strict",
        "--json",
    ])
    build_payload = json.loads(capsys.readouterr().out)
    validate_exit = validate_command_packet_main([
        "--artifact-dir",
        str(tmp_path),
        "--packet",
        str(output_path),
        "--closure-packet",
        str(closure_path),
        "--output",
        str(tmp_path / "command-preview-validation.json"),
        "--strict",
        "--json",
    ])
    validate_payload = json.loads(capsys.readouterr().out)
    packet = json.loads(output_path.read_text(encoding="utf-8"))

    assert build_exit == 0
    assert validate_exit == 0
    assert build_payload["ok"] is True
    assert validate_payload["ok"] is True
    assert packet["packet_id"] == COMMAND_PREVIEW_PACKET_ID
    assert packet["source_refs"]["closure_packet_id"] == CLOSURE_PACKET_ID


def test_local_developer_workflow_pr_admission_packet_blocks_external_execution() -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
    )
    closure_packet = build_local_developer_workflow_closure_packet(artifacts=artifacts)
    command_packet = build_local_developer_workflow_pr_command_preview_packet(
        artifacts=artifacts,
        closure_packet=closure_packet,
    )
    packet = build_local_developer_workflow_pr_admission_packet(
        artifacts=artifacts,
        command_preview_packet=command_packet,
        closure_packet=closure_packet,
    )
    validation = validate_local_developer_workflow_pr_admission_packet(
        packet=packet,
        artifacts=artifacts,
        command_preview_packet=command_packet,
        closure_packet=closure_packet,
    )

    assert validation.ok is True
    assert packet["packet_id"] == PR_ADMISSION_PACKET_ID
    assert packet["projection_only"] is True
    assert packet["local_command_review_evidence_present"] is True
    assert packet["admission_decision"] == "blocked_waiting_external_execution_approval"
    assert packet["execution_performed"] is False
    assert packet["external_effects_allowed"] is False
    assert packet["branch_write_allowed"] is False
    assert packet["pr_creation_allowed"] is False
    assert packet["candidate"]["command_preview_packet_id"] == COMMAND_PREVIEW_PACKET_ID
    assert packet["candidate"]["command_count"] == 2
    assert "branch_write" in packet["blocked_effects"]
    assert "pull_request_create" in packet["blocked_effects"]


def test_local_developer_workflow_pr_admission_packet_rejects_authority_overclaim() -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
    )
    command_packet = build_local_developer_workflow_pr_command_preview_packet(artifacts=artifacts)
    packet = build_local_developer_workflow_pr_admission_packet(
        artifacts=artifacts,
        command_preview_packet=command_packet,
    )
    packet["branch_write_allowed"] = True
    packet["pr_creation_allowed"] = True
    packet["external_effects_allowed"] = True
    packet["admission_decision"] = "approved"

    validation = validate_local_developer_workflow_pr_admission_packet(
        packet=packet,
        artifacts=artifacts,
        command_preview_packet=command_packet,
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "branch_write_allowed_must_be_false" in serialized_errors
    assert "pr_creation_allowed_must_be_false" in serialized_errors
    assert "external_effects_allowed_must_be_false" in serialized_errors
    assert "admission_decision_must_block_external_execution" in serialized_errors
    assert "packet_hash_mismatch" in serialized_errors


def test_local_developer_workflow_pr_admission_packet_cli_builds_and_validates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifacts = build_local_developer_workflow_v1_artifacts(
        repo_root=_ROOT,
        repo_status=FIXTURE_REPO_STATUS,
    )
    paths = write_local_developer_workflow_v1_artifacts(artifacts, tmp_path)
    closure_packet = build_local_developer_workflow_closure_packet(
        artifacts=artifacts,
        artifact_paths=paths,
    )
    closure_path = write_local_developer_workflow_closure_packet(
        closure_packet,
        tmp_path / CLOSURE_PACKET_FILENAME,
    )
    command_packet = build_local_developer_workflow_pr_command_preview_packet(
        artifacts=artifacts,
        closure_packet=closure_packet,
        artifact_paths=paths,
        closure_packet_path=closure_path,
    )
    command_path = write_local_developer_workflow_pr_command_preview_packet(
        command_packet,
        tmp_path / COMMAND_PREVIEW_PACKET_FILENAME,
    )
    output_path = tmp_path / PR_ADMISSION_PACKET_FILENAME

    build_exit = build_admission_packet_main([
        "--artifact-dir",
        str(tmp_path),
        "--command-preview-packet",
        str(command_path),
        "--closure-packet",
        str(closure_path),
        "--output",
        str(output_path),
        "--strict",
        "--json",
    ])
    build_payload = json.loads(capsys.readouterr().out)
    validate_exit = validate_admission_packet_main([
        "--artifact-dir",
        str(tmp_path),
        "--packet",
        str(output_path),
        "--command-preview-packet",
        str(command_path),
        "--closure-packet",
        str(closure_path),
        "--output",
        str(tmp_path / "pr-admission-validation.json"),
        "--strict",
        "--json",
    ])
    validate_payload = json.loads(capsys.readouterr().out)
    packet = json.loads(output_path.read_text(encoding="utf-8"))

    assert build_exit == 0
    assert validate_exit == 0
    assert build_payload["ok"] is True
    assert validate_payload["ok"] is True
    assert packet["packet_id"] == PR_ADMISSION_PACKET_ID
    assert packet["source_refs"]["command_preview_packet_id"] == COMMAND_PREVIEW_PACKET_ID
