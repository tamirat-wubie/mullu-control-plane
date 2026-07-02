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
from software_dev.local_developer_workflow_v1.composition import (  # noqa: E402
    BLOCKED_EXTERNAL_EFFECTS,
    COMPOSITION_WORKFLOW_ID,
    TERMINAL_WAIT_STAGE_ID,
    build_foundation_workflow_composition_descriptor,
    build_foundation_workflow_composition_read_model,
    validate_foundation_workflow_composition,
)
from mcoi_runtime.contracts.workflow import StageType  # noqa: E402
from scripts.run_local_developer_workflow_v1 import main as run_main  # noqa: E402
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
