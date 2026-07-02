"""Tests for standalone patch proposal draft capability.

Purpose: prove Patch Proposal / Diff Proposal mode emits a reusable,
schema-backed, no-authority proposal artifact.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: software_dev.patch_proposal runner and CLIs.
Invariants: proposals are preview-only, not applied, not tested, and not
execution authority.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


_ROOT = Path(__file__).resolve().parent.parent
_MCOI_ROOT = _ROOT / "mcoi"
for import_root in (_ROOT, _MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from software_dev.patch_proposal.runner import (  # noqa: E402
    CAPABILITY_ID,
    build_patch_proposal_draft,
    validate_patch_proposal_draft,
    write_patch_proposal_draft,
)
from scripts.run_patch_proposal_draft import main as run_main  # noqa: E402
from scripts.validate_patch_proposal_draft import validate_patch_proposal_draft_file  # noqa: E402


FIXTURE_STATUS = {
    "branch": "codex/patch-proposal",
    "dirty": True,
    "changed_files": ["mcoi/software_dev/example.py"],
}


def test_patch_proposal_draft_builds_required_fields(tmp_path: Path) -> None:
    proposal = build_patch_proposal_draft(
        repo_status=FIXTURE_STATUS,
        objective="Add standalone patch proposal mode.",
    )
    path = write_patch_proposal_draft(proposal, tmp_path / "proposal.json")
    validation = validate_patch_proposal_draft(proposal, artifact_path=path)
    file_validation = validate_patch_proposal_draft_file(artifact_path=path)

    assert validation.ok is True
    assert file_validation.ok is True
    assert proposal["capability_id"] == CAPABILITY_ID
    assert proposal["proposal_status"] == "preview_only"
    assert proposal["files_likely_to_change"] == ["mcoi/software_dev/example.py"]
    assert proposal["safe_diff_preview"][0]["applied"] is False
    assert proposal["test_plan"]["tests_executed"] is False
    assert proposal["rollback_plan"]["rollback_required"] is True
    assert proposal["approval"]["approval_needed"] is True
    assert proposal["effect_boundary"]["file_write_performed"] is False


def test_patch_proposal_draft_accepts_explicit_target_files() -> None:
    proposal = build_patch_proposal_draft(
        repo_status={"branch": "main", "dirty": False, "changed_files": []},
        objective="Prepare focused proposal.",
        target_files=("docs/example.md", "tests/test_example.py"),
    )
    validation = validate_patch_proposal_draft(proposal)

    assert validation.ok is True
    assert proposal["files_likely_to_change"] == ["docs/example.md", "tests/test_example.py"]
    assert proposal["risk"]["risk_level"] == "low"
    assert len(proposal["safe_diff_preview"]) == 2


def test_patch_proposal_draft_rejects_authority_overclaim() -> None:
    proposal = build_patch_proposal_draft(
        repo_status=FIXTURE_STATUS,
        objective="Reject unsafe proposal.",
    )
    proposal["safe_diff_preview"][0]["applied"] = True
    proposal["test_plan"]["tests_executed"] = True
    proposal["effect_boundary"]["pull_request_created"] = True
    validation = validate_patch_proposal_draft(proposal)
    serialized = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "safe_diff_preview_entry_must_not_be_applied" in serialized
    assert "tests_executed_must_be_false" in serialized
    assert "effect_boundary_enabled:pull_request_created" in serialized


def test_patch_proposal_draft_cli_writes_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output_path = tmp_path / "proposal.json"
    exit_code = run_main([
        "--repo-root",
        str(_ROOT),
        "--target-file",
        "docs/example.md",
        "--output",
        str(output_path),
        "--strict",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert output_path.exists()
    assert payload["proposal_status"] == "preview_only"
