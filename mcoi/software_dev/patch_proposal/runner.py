"""Build a standalone patch proposal / diff proposal draft.

Purpose: generate a reusable safe diff preview, test plan, rollback plan, risk
classification, and approval boundary before any repository file write.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Local Developer Workflow git observation helpers and schema
validation.
Invariants:
  - Proposal artifacts never apply patches or write source files.
  - Proposal approval is review-only and cannot authorize execution.
  - Branch push, PR creation, merge, deployment, connector calls, and live
    execution remain disabled.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from software_dev.local_developer_workflow_v1.runner import (
    DEFAULT_OBJECTIVE,
    FORBIDDEN_EFFECTS,
    WORKFLOW_ID,
    collect_git_repository_status,
)


SCHEMA_VERSION = 1
CAPABILITY_ID = "software_dev.github_patch_proposal.draft"
ARTIFACT_FILENAME = "software_dev_patch_proposal_draft.json"
MODE = "foundation"
DEFAULT_WORKFLOW_RUN_ID = "patch_proposal_draft.foundation.preview"
DEFAULT_PATCH_PLAN_REF = "software_dev.github_patch_plan.draft"
DEFAULT_REQUESTED_AT = "2026-07-02T00:00:00+00:00"
VALIDATOR_COMMANDS = (
    "python scripts/validate_patch_proposal_draft.py --strict",
    "python -m pytest tests/test_patch_proposal_draft.py -q",
)
BLOCKED_EFFECTS = (
    "file_write",
    "test_execution",
    "branch_push",
    "pull_request_create",
    "merge",
    "deploy",
    "connector_call",
    "external_write",
    "live_execution",
)


class PatchProposalDraftError(ValueError):
    """Raised when a patch proposal draft cannot be built or validated."""


@dataclass(frozen=True, slots=True)
class PatchProposalDraftValidation:
    """Validation report for a patch proposal draft."""

    ok: bool
    errors: tuple[str, ...]
    proposal_id: str
    capability_id: str
    proposal_status: str
    artifact_path: str

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-ready validation data."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def collect_patch_proposal_draft(
    *,
    repo_root: Path,
    objective: str = DEFAULT_OBJECTIVE,
    target_files: Sequence[str] = (),
    patch_plan_ref: str = DEFAULT_PATCH_PLAN_REF,
    workflow_run_id: str = DEFAULT_WORKFLOW_RUN_ID,
    requested_at: str = DEFAULT_REQUESTED_AT,
) -> dict[str, Any]:
    """Collect read-only repo status and build one patch proposal draft."""

    repo_status = collect_git_repository_status(repo_root)
    return build_patch_proposal_draft(
        repo_status=repo_status,
        objective=objective,
        target_files=target_files,
        patch_plan_ref=patch_plan_ref,
        workflow_run_id=workflow_run_id,
        requested_at=requested_at,
    )


def build_patch_proposal_draft(
    *,
    repo_status: Mapping[str, Any],
    objective: str,
    target_files: Sequence[str] = (),
    patch_plan_ref: str = DEFAULT_PATCH_PLAN_REF,
    workflow_run_id: str = DEFAULT_WORKFLOW_RUN_ID,
    requested_at: str = DEFAULT_REQUESTED_AT,
) -> dict[str, Any]:
    """Return a safe patch proposal draft without source mutation."""

    normalized_objective = _required_text(objective, "objective")
    normalized_patch_plan_ref = _required_text(patch_plan_ref, "patch_plan_ref")
    files_likely_to_change = _files_likely_to_change(repo_status, target_files)
    risk = _risk(files_likely_to_change, bool(repo_status.get("dirty")))
    proposal = {
        "schema_version": SCHEMA_VERSION,
        "proposal_id": f"patch_proposal_draft.{_digest({'objective': normalized_objective, 'files': files_likely_to_change})[:16]}.foundation.v1",
        "capability_id": CAPABILITY_ID,
        "workflow_id": WORKFLOW_ID,
        "workflow_run_id": _required_text(workflow_run_id, "workflow_run_id"),
        "mode": MODE,
        "proposal_status": "preview_only",
        "proposal_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "patch_objective": normalized_objective,
        "patch_plan_ref": normalized_patch_plan_ref,
        "files_likely_to_change": files_likely_to_change,
        "safe_diff_preview": [
            _diff_preview_entry(file_path=file_path, objective=normalized_objective)
            for file_path in files_likely_to_change
        ],
        "test_plan": {
            "tests_executed": False,
            "commands": [
                "python scripts/validate_patch_proposal_draft.py --strict",
                "python -m pytest tests/test_patch_proposal_draft.py -q",
            ],
            "required_before_completion_claim": [
                "target file evidence",
                "operator approval for file write",
                "post-write test receipt",
            ],
        },
        "rollback_plan": {
            "rollback_required": True,
            "rollback_strategy": "discard proposal artifact; no source mutation has occurred",
            "commands": [
                "Remove-Item -LiteralPath '.change_assurance/software_dev_patch_proposal_draft.json' -Force"
            ],
            "rollback_executed": False,
        },
        "risk": risk,
        "approval": {
            "approval_needed": True,
            "approval_status": "pending",
            "approval_boundary": "review_patch_proposal_only",
            "approval_does_not_authorize_file_write": True,
        },
        "blocked_effects": list(BLOCKED_EFFECTS),
        "effect_boundary": dict(FORBIDDEN_EFFECTS),
        "source_refs": {
            "repo_branch": str(repo_status.get("branch") or "unknown"),
            "repo_dirty": str(bool(repo_status.get("dirty"))).lower(),
            "patch_plan_ref": normalized_patch_plan_ref,
            "builder": "python scripts/run_patch_proposal_draft.py",
            "schema": "schemas/software_dev_patch_proposal.schema.json",
        },
        "validators": list(VALIDATOR_COMMANDS),
        "created_at": requested_at,
        "proposal_hash": "",
    }
    proposal["proposal_hash"] = _digest(proposal)
    return proposal


def validate_patch_proposal_draft(
    proposal: Mapping[str, Any],
    *,
    artifact_path: Path = Path("<generated>"),
) -> PatchProposalDraftValidation:
    """Validate no-authority patch proposal semantics."""

    errors: list[str] = []
    if proposal.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version_mismatch")
    if proposal.get("capability_id") != CAPABILITY_ID:
        errors.append("capability_id_mismatch")
    if proposal.get("proposal_status") != "preview_only":
        errors.append("proposal_status_must_be_preview_only")
    if proposal.get("proposal_is_not_execution_authority") is not True:
        errors.append("proposal_must_not_be_execution_authority")
    if proposal.get("live_execution_enabled") is not False:
        errors.append("live_execution_enabled_must_be_false")
    _validate_effect_boundary(proposal, errors)
    _validate_diff_preview(proposal, errors)
    _validate_test_and_rollback(proposal, errors)
    approval = proposal.get("approval", {})
    if not isinstance(approval, Mapping):
        errors.append("approval_must_be_object")
    else:
        if approval.get("approval_needed") is not True:
            errors.append("approval_needed_must_be_true")
        if approval.get("approval_does_not_authorize_file_write") is not True:
            errors.append("approval_must_not_authorize_file_write")
    if tuple(proposal.get("blocked_effects", ())) != BLOCKED_EFFECTS:
        errors.append("blocked_effects_must_match_canonical_order")
    expected_hash = _digest({**dict(proposal), "proposal_hash": ""})
    if proposal.get("proposal_hash") != expected_hash:
        errors.append("proposal_hash_mismatch")
    return PatchProposalDraftValidation(
        ok=not errors,
        errors=tuple(errors),
        proposal_id=str(proposal.get("proposal_id") or ""),
        capability_id=str(proposal.get("capability_id") or ""),
        proposal_status=str(proposal.get("proposal_status") or ""),
        artifact_path=_path_label(artifact_path),
    )


def write_patch_proposal_draft(proposal: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic patch proposal draft artifact."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dict(proposal), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _files_likely_to_change(repo_status: Mapping[str, Any], target_files: Sequence[str]) -> list[str]:
    explicit_files = [str(item).strip().replace("\\", "/") for item in target_files if str(item).strip()]
    status_files = [str(item).strip().replace("\\", "/") for item in repo_status.get("changed_files", ()) if str(item).strip()]
    files = list(dict.fromkeys(explicit_files + status_files))
    return files[:20] or ["AwaitingEvidence:target_files"]


def _diff_preview_entry(*, file_path: str, objective: str) -> dict[str, Any]:
    return {
        "file_path": file_path,
        "preview_only": True,
        "applied": False,
        "change_intent": "prepare_patch_boundary_before_file_write",
        "unified_diff_preview": (
            f"diff --git a/{file_path} b/{file_path}\n"
            "--- preview-only\n"
            "+++ preview-only\n"
            "@@\n"
            f"+ proposed objective: {objective}\n"
        ),
    }


def _risk(files_likely_to_change: Sequence[str], dirty: bool) -> dict[str, Any]:
    if files_likely_to_change == ["AwaitingEvidence:target_files"]:
        risk_level = "unknown"
        factors = ["target_files_missing"]
    elif len(files_likely_to_change) > 10:
        risk_level = "high"
        factors = ["wide_file_surface"]
    elif dirty:
        risk_level = "medium"
        factors = ["working_tree_has_existing_changes"]
    else:
        risk_level = "low"
        factors = ["clean_working_tree_preview_only"]
    return {
        "risk_level": risk_level,
        "risk_factors": factors,
        "risk_reduction": [
            "inspect target files before write approval",
            "run tests after any approved mutation",
            "record rollback receipt before completion claim",
        ],
    }


def _validate_effect_boundary(proposal: Mapping[str, Any], errors: list[str]) -> None:
    boundary = proposal.get("effect_boundary")
    if not isinstance(boundary, Mapping):
        errors.append("effect_boundary_must_be_object")
        return
    enabled = sorted(key for key, value in boundary.items() if value is not False)
    if enabled:
        errors.append(f"effect_boundary_enabled:{','.join(enabled)}")


def _validate_diff_preview(proposal: Mapping[str, Any], errors: list[str]) -> None:
    previews = proposal.get("safe_diff_preview")
    if not isinstance(previews, list) or not previews:
        errors.append("safe_diff_preview_must_be_non_empty")
        return
    for preview in previews:
        if not isinstance(preview, Mapping):
            errors.append("safe_diff_preview_entry_must_be_object")
            continue
        if preview.get("preview_only") is not True:
            errors.append("safe_diff_preview_entry_must_be_preview_only")
        if preview.get("applied") is not False:
            errors.append("safe_diff_preview_entry_must_not_be_applied")


def _validate_test_and_rollback(proposal: Mapping[str, Any], errors: list[str]) -> None:
    test_plan = proposal.get("test_plan", {})
    rollback_plan = proposal.get("rollback_plan", {})
    if not isinstance(test_plan, Mapping):
        errors.append("test_plan_must_be_object")
    elif test_plan.get("tests_executed") is not False:
        errors.append("tests_executed_must_be_false")
    if not isinstance(rollback_plan, Mapping):
        errors.append("rollback_plan_must_be_object")
    else:
        if rollback_plan.get("rollback_required") is not True:
            errors.append("rollback_required_must_be_true")
        if rollback_plan.get("rollback_executed") is not False:
            errors.append("rollback_executed_must_be_false")


def _required_text(value: object, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise PatchProposalDraftError(f"{field_name}_required")
    return normalized


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(Path.cwd().resolve(strict=False)).as_posix()
    except ValueError:
        return str(path)
