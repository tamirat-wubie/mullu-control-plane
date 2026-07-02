"""Build Local Developer Workflow v1 preview artifacts.

Purpose: turn a repository-local task into repo status, patch-plan draft,
diff proposal, test plan, receipt, approval request, and PR command preview
artifacts without mutating source files or external systems.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: local git read-only status commands and GitHub patch-plan draft
contracts.
Invariants:
  - Artifacts are projection-only and never execution authority.
  - Repo status collection is read-only.
  - Diff and PR commands are previews only.
  - File write, branch push, PR creation, merge, deployment, connector writes,
    and live execution remain false in every authority boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

from gateway.github_operations_workroom import (
    GitHubPatchPlanDraftRequest,
    build_github_patch_plan_draft_receipt,
    evaluate_github_patch_plan_draft,
)


SCHEMA_VERSION = 1
WORKFLOW_ID = "mullu.local_developer_workflow.v1"
WORKFLOW_RUN_ID = "local_developer_workflow_v1.foundation.preview"
MODE = "foundation"
DEFAULT_OBJECTIVE = (
    "Draft a local developer workflow change candidate with patch plan, diff "
    "proposal, test plan, approval request, and PR command preview."
)
DEFAULT_REQUESTED_AT = "2026-07-02T00:00:00+00:00"
DEFAULT_ACTOR_ID = "operator.local"
DEFAULT_WORKSPACE_ID = "mullusi.local.control_studio"
DEFAULT_REPOSITORY_REF = "local:mullu-control-plane"
DEFAULT_TARGET_BRANCH = "main"
DEFAULT_CANDIDATE_BRANCH = "codex/local-developer-workflow-v1-preview"
DEFAULT_PR_BODY_PATH = ".change_assurance/local_developer_workflow_v1_pr_body.md"
ARTIFACT_FILENAMES = {
    "repo_status": "local_developer_workflow_v1_repo_status.json",
    "patch_plan": "local_developer_workflow_v1_patch_plan.json",
    "diff_proposal": "local_developer_workflow_v1_diff_proposal.json",
    "test_plan": "local_developer_workflow_v1_test_plan.json",
    "receipt": "local_developer_workflow_v1_receipt.json",
    "approval_request": "local_developer_workflow_v1_approval_request.json",
    "pr_command_preview": "local_developer_workflow_v1_pr_command_preview.json",
}
FORBIDDEN_EFFECTS = {
    "file_write_performed": False,
    "source_mutation_performed": False,
    "test_process_executed": False,
    "branch_created": False,
    "branch_push_performed": False,
    "pull_request_created": False,
    "merge_performed": False,
    "deployment_performed": False,
    "connector_call_performed": False,
    "external_write_performed": False,
    "live_execution_enabled": False,
}
VALIDATOR_COMMANDS = (
    "python scripts/validate_local_developer_workflow_v1.py --strict",
    "python -m pytest tests/test_local_developer_workflow_v1.py -q",
)


class LocalDeveloperWorkflowV1Error(ValueError):
    """Raised when Local Developer Workflow v1 artifacts cannot be projected."""


@dataclass(frozen=True, slots=True)
class LocalDeveloperWorkflowV1Validation:
    """Validation report for Local Developer Workflow v1 artifacts."""

    ok: bool
    errors: tuple[str, ...]
    workflow_id: str
    workflow_run_id: str
    status: str
    artifact_paths: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation report."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def collect_git_repository_status(repo_root: Path) -> dict[str, Any]:
    """Collect read-only git status evidence for the local repository."""

    resolved_root = repo_root.resolve(strict=False)
    status_result = _run_git(resolved_root, ("status", "--short", "--branch"))
    branch_result = _run_git(resolved_root, ("branch", "--show-current"))
    top_level_result = _run_git(resolved_root, ("rev-parse", "--show-toplevel"))
    changed_result = _run_git(resolved_root, ("diff", "--name-only"))
    staged_result = _run_git(resolved_root, ("diff", "--cached", "--name-only"))
    status_lines = _lines(status_result["stdout"])
    changed_files = tuple(dict.fromkeys(_lines(changed_result["stdout"]) + _lines(staged_result["stdout"])))
    return {
        "repo_root": str(resolved_root),
        "git_top_level": top_level_result["stdout"].strip(),
        "branch": branch_result["stdout"].strip() or "unknown",
        "status_lines": status_lines,
        "changed_files": list(changed_files),
        "dirty": bool(status_lines[1:] or changed_files),
        "commands": {
            "status": status_result,
            "branch": branch_result,
            "top_level": top_level_result,
            "changed": changed_result,
            "staged": staged_result,
        },
    }


def build_local_developer_workflow_v1_artifacts(
    *,
    repo_root: Path,
    objective: str = DEFAULT_OBJECTIVE,
    actor_id: str = DEFAULT_ACTOR_ID,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    repository_ref: str = DEFAULT_REPOSITORY_REF,
    requested_at: str = DEFAULT_REQUESTED_AT,
    target_branch: str = DEFAULT_TARGET_BRANCH,
    candidate_branch: str = DEFAULT_CANDIDATE_BRANCH,
    pr_body_path: str = DEFAULT_PR_BODY_PATH,
    repo_status: Mapping[str, Any] | None = None,
    artifact_filenames: Mapping[str, str] = ARTIFACT_FILENAMES,
) -> dict[str, dict[str, Any]]:
    """Return the seven Local Developer Workflow v1 projection artifacts.

    Input contract: repository root plus bounded local task objective. Optional
    repo_status can be supplied by tests or prior observation.
    Output contract: JSON-serializable artifacts keyed by canonical artifact id.
    Error contract: raises LocalDeveloperWorkflowV1Error for missing objective,
    invalid artifact filename maps, or failed semantic construction.
    """

    normalized_objective = _required_text(objective, "objective")
    _require_artifact_filenames(artifact_filenames)
    observed_status = dict(repo_status or collect_git_repository_status(repo_root))
    evidence_refs = _evidence_refs(observed_status)
    evidence_summaries = _evidence_summaries(observed_status)
    verification_expectations = _verification_expectations()
    patch_request = GitHubPatchPlanDraftRequest(
        actor_id=actor_id,
        workspace_id=workspace_id,
        repo=repository_ref,
        objective=normalized_objective,
        evidence_refs=tuple(evidence_refs),
        evidence_summaries=tuple(evidence_summaries),
        verification_expectations=tuple(verification_expectations),
        surface_event_id=f"{WORKFLOW_RUN_ID}.patch_plan_request",
        requested_at=requested_at,
    )
    patch_draft = evaluate_github_patch_plan_draft(request=patch_request, clock=lambda: requested_at)
    patch_receipt = build_github_patch_plan_draft_receipt(
        request=patch_request,
        draft=patch_draft,
        occurred_at=requested_at,
    )
    repo_status_artifact = _repo_status_artifact(
        repo_status=observed_status,
        objective=normalized_objective,
        repository_ref=repository_ref,
        requested_at=requested_at,
    )
    patch_plan_artifact = _patch_plan_artifact(
        request=patch_request.to_json_dict(),
        draft=patch_draft.to_json_dict(),
        receipt=patch_receipt.to_json_dict(),
    )
    diff_proposal = _diff_proposal_artifact(
        repo_status=observed_status,
        objective=normalized_objective,
        patch_plan_id=patch_draft.plan_id,
    )
    test_plan = _test_plan_artifact(
        objective=normalized_objective,
        patch_plan_id=patch_draft.plan_id,
        diff_proposal_id=str(diff_proposal["diff_proposal_id"]),
    )
    approval_request = _approval_request_artifact(
        objective=normalized_objective,
        patch_plan_id=patch_draft.plan_id,
        diff_proposal_id=str(diff_proposal["diff_proposal_id"]),
        test_plan_id=str(test_plan["test_plan_id"]),
    )
    pr_command_preview = _pr_command_preview_artifact(
        objective=normalized_objective,
        candidate_branch=candidate_branch,
        target_branch=target_branch,
        pr_body_path=pr_body_path,
        approval_request_id=str(approval_request["approval_request_id"]),
    )
    receipt = _receipt_artifact(
        repo_status_artifact=repo_status_artifact,
        patch_plan=patch_plan_artifact,
        diff_proposal=diff_proposal,
        test_plan=test_plan,
        approval_request=approval_request,
        pr_command_preview=pr_command_preview,
        artifact_filenames=artifact_filenames,
        requested_at=requested_at,
    )
    return {
        "repo_status": repo_status_artifact,
        "patch_plan": patch_plan_artifact,
        "diff_proposal": diff_proposal,
        "test_plan": test_plan,
        "receipt": receipt,
        "approval_request": approval_request,
        "pr_command_preview": pr_command_preview,
    }


def write_local_developer_workflow_v1_artifacts(
    artifacts: Mapping[str, Mapping[str, Any]],
    output_dir: Path,
    *,
    artifact_filenames: Mapping[str, str] = ARTIFACT_FILENAMES,
) -> dict[str, Path]:
    """Write the seven workflow artifacts to a local output directory."""

    _require_artifact_filenames(artifact_filenames)
    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: dict[str, Path] = {}
    for artifact_name, filename in artifact_filenames.items():
        payload = artifacts.get(artifact_name)
        if not isinstance(payload, Mapping):
            raise LocalDeveloperWorkflowV1Error(f"missing artifact payload {artifact_name}")
        output_path = output_dir / filename
        output_path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written_paths[artifact_name] = output_path
    return written_paths


def validate_local_developer_workflow_v1_artifacts(
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
    artifact_paths: Mapping[str, Path] | None = None,
) -> LocalDeveloperWorkflowV1Validation:
    """Validate Local Developer Workflow v1 no-mutation semantics."""

    errors: list[str] = []
    missing_artifacts = tuple(key for key in ARTIFACT_FILENAMES if key not in artifacts)
    if missing_artifacts:
        errors.append(f"missing_artifacts:{','.join(missing_artifacts)}")
    workflow_run_ids = set()
    for artifact_name, artifact in artifacts.items():
        if not isinstance(artifact, Mapping):
            errors.append(f"{artifact_name}:artifact_must_be_object")
            continue
        if artifact.get("workflow_id") != WORKFLOW_ID:
            errors.append(f"{artifact_name}:workflow_id_mismatch")
        workflow_run_id = str(artifact.get("workflow_run_id") or "")
        if not workflow_run_id:
            errors.append(f"{artifact_name}:workflow_run_id_missing")
        else:
            workflow_run_ids.add(workflow_run_id)
    if len(workflow_run_ids) > 1:
        errors.append("workflow_run_id_mismatch")
    _validate_no_effect_boundary(artifacts, errors)
    _validate_stage_links(artifacts, errors)
    _validate_pr_preview(artifacts.get("pr_command_preview", {}), errors)
    receipt = artifacts.get("receipt", {})
    if isinstance(receipt, Mapping):
        if receipt.get("status") != "AwaitingEvidence":
            errors.append("receipt:status_must_be_AwaitingEvidence")
        if receipt.get("execution_performed") is not False:
            errors.append("receipt:execution_performed_must_be_false")
        if receipt.get("receipt_hash") != _digest({**dict(receipt), "receipt_hash": ""}):
            errors.append("receipt:receipt_hash_mismatch")
    artifact_path_labels = {
        key: _path_label(path)
        for key, path in (artifact_paths or {}).items()
    }
    return LocalDeveloperWorkflowV1Validation(
        ok=not errors,
        errors=tuple(errors),
        workflow_id=WORKFLOW_ID,
        workflow_run_id=next(iter(workflow_run_ids), ""),
        status=str(receipt.get("status") or "") if isinstance(receipt, Mapping) else "",
        artifact_paths=artifact_path_labels,
    )


def _repo_status_artifact(
    *,
    repo_status: Mapping[str, Any],
    objective: str,
    repository_ref: str,
    requested_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": f"{WORKFLOW_RUN_ID}.repo_status",
        "workflow_id": WORKFLOW_ID,
        "workflow_run_id": WORKFLOW_RUN_ID,
        "mode": MODE,
        "objective": objective,
        "repository_ref": repository_ref,
        "read_only_observation": True,
        "live_execution_enabled": False,
        "branch": str(repo_status.get("branch") or "unknown"),
        "dirty": bool(repo_status.get("dirty")),
        "changed_files": [str(item) for item in repo_status.get("changed_files", ())],
        "status_lines": [str(item) for item in repo_status.get("status_lines", ())],
        "observed_at": requested_at,
        "source_refs": {
            "git_status_command": "git status --short --branch",
            "git_diff_name_only_command": "git diff --name-only",
        },
        "effect_boundary": dict(FORBIDDEN_EFFECTS),
    }


def _patch_plan_artifact(
    *,
    request: Mapping[str, Any],
    draft: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": f"{WORKFLOW_RUN_ID}.patch_plan",
        "workflow_id": WORKFLOW_ID,
        "workflow_run_id": WORKFLOW_RUN_ID,
        "mode": MODE,
        "patch_plan_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "request": dict(request),
        "draft": dict(draft),
        "receipt": dict(receipt),
        "effect_boundary": dict(FORBIDDEN_EFFECTS),
    }


def _diff_proposal_artifact(
    *,
    repo_status: Mapping[str, Any],
    objective: str,
    patch_plan_id: str,
) -> dict[str, Any]:
    changed_files = [str(item) for item in repo_status.get("changed_files", ())]
    likely_files = changed_files[:12] or ["AwaitingEvidence:target_files"]
    preview_rows = [
        {
            "file_path": file_path,
            "change_intent": "review_candidate_change_boundary_before_any_file_write",
            "unified_diff_preview": (
                f"diff --git a/{file_path} b/{file_path}\n"
                "--- preview-only\n"
                "+++ preview-only\n"
                "@@\n"
                f"+ proposed objective: {objective}\n"
            ),
        }
        for file_path in likely_files
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "diff_proposal_id": f"{WORKFLOW_RUN_ID}.diff_proposal",
        "workflow_id": WORKFLOW_ID,
        "workflow_run_id": WORKFLOW_RUN_ID,
        "mode": MODE,
        "proposal_status": "preview_only",
        "diff_is_not_applied": True,
        "live_execution_enabled": False,
        "patch_plan_id": patch_plan_id,
        "files_likely_to_change": likely_files,
        "safe_diff_preview": preview_rows,
        "risk_level": "medium" if changed_files else "unknown_until_target_files_supplied",
        "approval_needed": True,
        "rollback_plan": "discard preview artifact; no source file mutation has occurred",
        "effect_boundary": dict(FORBIDDEN_EFFECTS),
    }


def _test_plan_artifact(
    *,
    objective: str,
    patch_plan_id: str,
    diff_proposal_id: str,
) -> dict[str, Any]:
    commands = list(_verification_expectations())
    return {
        "schema_version": SCHEMA_VERSION,
        "test_plan_id": f"{WORKFLOW_RUN_ID}.test_plan",
        "workflow_id": WORKFLOW_ID,
        "workflow_run_id": WORKFLOW_RUN_ID,
        "mode": MODE,
        "objective": objective,
        "patch_plan_id": patch_plan_id,
        "diff_proposal_id": diff_proposal_id,
        "test_plan_is_not_execution_authority": True,
        "tests_executed": False,
        "live_execution_enabled": False,
        "commands": commands,
        "minimum_assertions": [
            "patch_plan remains draft-only",
            "diff proposal is not applied",
            "PR command preview never executes",
        ],
        "effect_boundary": dict(FORBIDDEN_EFFECTS),
    }


def _approval_request_artifact(
    *,
    objective: str,
    patch_plan_id: str,
    diff_proposal_id: str,
    test_plan_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "approval_request_id": f"{WORKFLOW_RUN_ID}.approval_request",
        "workflow_id": WORKFLOW_ID,
        "workflow_run_id": WORKFLOW_RUN_ID,
        "mode": MODE,
        "approval_request_is_not_execution_authority": True,
        "approval_required": True,
        "approval_status": "pending",
        "live_execution_enabled": False,
        "decision_prompt": "Approve review of the local patch proposal bundle only; do not approve file writes or external PR execution.",
        "allowed_decisions": ["approve_review_only", "request_more_evidence", "reject"],
        "default_decision": "request_more_evidence",
        "objective": objective,
        "source_refs": {
            "patch_plan_id": patch_plan_id,
            "diff_proposal_id": diff_proposal_id,
            "test_plan_id": test_plan_id,
        },
        "effects_still_forbidden_after_approval": [
            "file_write",
            "branch_push",
            "pull_request_create",
            "merge",
            "deploy",
            "connector_write",
        ],
        "effect_boundary": dict(FORBIDDEN_EFFECTS),
    }


def _pr_command_preview_artifact(
    *,
    objective: str,
    candidate_branch: str,
    target_branch: str,
    pr_body_path: str,
    approval_request_id: str,
) -> dict[str, Any]:
    title = _bounded_title(objective)
    return {
        "schema_version": SCHEMA_VERSION,
        "preview_id": f"{WORKFLOW_RUN_ID}.pr_command_preview",
        "workflow_id": WORKFLOW_ID,
        "workflow_run_id": WORKFLOW_RUN_ID,
        "mode": MODE,
        "preview_status": "preview_rendered_execution_blocked",
        "preview_only": True,
        "execution_performed": False,
        "live_execution_enabled": False,
        "approval_required_before_execution": True,
        "approval_request_id": approval_request_id,
        "candidate_branch": candidate_branch,
        "target_branch": target_branch,
        "command_preview": [
            {
                "command_id": "push_branch_preview",
                "effect": "push_branch",
                "command": f"git push -u origin {candidate_branch}",
                "execution_allowed": False,
            },
            {
                "command_id": "open_pr_preview",
                "effect": "open_external_pr",
                "command": (
                    f"gh pr create --title '{title}' --body-file '{pr_body_path}' "
                    f"--head {candidate_branch} --base {target_branch}"
                ),
                "execution_allowed": False,
            },
        ],
        "blocked_reason": "external_pr_execution_requires_separate_approval_witness",
        "effect_boundary": dict(FORBIDDEN_EFFECTS),
    }


def _receipt_artifact(
    *,
    repo_status_artifact: Mapping[str, Any],
    patch_plan: Mapping[str, Any],
    diff_proposal: Mapping[str, Any],
    test_plan: Mapping[str, Any],
    approval_request: Mapping[str, Any],
    pr_command_preview: Mapping[str, Any],
    artifact_filenames: Mapping[str, str],
    requested_at: str,
) -> dict[str, Any]:
    source_refs = {
        "repo_status": str(repo_status_artifact["artifact_id"]),
        "patch_plan": str(patch_plan["artifact_id"]),
        "diff_proposal": str(diff_proposal["diff_proposal_id"]),
        "test_plan": str(test_plan["test_plan_id"]),
        "approval_request": str(approval_request["approval_request_id"]),
        "pr_command_preview": str(pr_command_preview["preview_id"]),
    }
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": f"{WORKFLOW_RUN_ID}.receipt",
        "workflow_id": WORKFLOW_ID,
        "workflow_run_id": WORKFLOW_RUN_ID,
        "mode": MODE,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "receipt_is_not_execution_authority": True,
        "execution_performed": False,
        "live_execution_enabled": False,
        "artifact_filenames": dict(artifact_filenames),
        "source_refs": source_refs,
        "causal_trace": [
            "Observed repository status with read-only git commands.",
            "Drafted patch plan from bounded local evidence.",
            "Rendered safe diff proposal without applying it.",
            "Rendered test plan without running commands.",
            "Prepared operator approval request.",
            "Rendered PR command preview with execution blocked.",
        ],
        "validators": list(VALIDATOR_COMMANDS),
        "effect_boundary": dict(FORBIDDEN_EFFECTS),
        "created_at": requested_at,
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = _digest(receipt)
    return receipt


def _validate_no_effect_boundary(
    artifacts: Mapping[str, Mapping[str, Any]],
    errors: list[str],
) -> None:
    for artifact_name, artifact in artifacts.items():
        boundary = artifact.get("effect_boundary") if isinstance(artifact, Mapping) else None
        if not isinstance(boundary, Mapping):
            errors.append(f"{artifact_name}:effect_boundary_missing")
            continue
        enabled = sorted(key for key, value in boundary.items() if value is not False)
        if enabled:
            errors.append(f"{artifact_name}:effect_boundary_enabled:{','.join(enabled)}")
        if artifact.get("live_execution_enabled") is not False:
            errors.append(f"{artifact_name}:live_execution_enabled_must_be_false")


def _validate_stage_links(
    artifacts: Mapping[str, Mapping[str, Any]],
    errors: list[str],
) -> None:
    patch_plan = artifacts.get("patch_plan", {})
    diff_proposal = artifacts.get("diff_proposal", {})
    test_plan = artifacts.get("test_plan", {})
    approval = artifacts.get("approval_request", {})
    receipt = artifacts.get("receipt", {})
    if not all(isinstance(item, Mapping) for item in (patch_plan, diff_proposal, test_plan, approval, receipt)):
        errors.append("stage_artifacts_must_be_objects")
        return
    draft = patch_plan.get("draft", {})
    patch_plan_id = str(draft.get("plan_id") or "") if isinstance(draft, Mapping) else ""
    if diff_proposal.get("patch_plan_id") != patch_plan_id:
        errors.append("diff_proposal:patch_plan_id_mismatch")
    if test_plan.get("patch_plan_id") != patch_plan_id:
        errors.append("test_plan:patch_plan_id_mismatch")
    if approval.get("source_refs", {}).get("test_plan_id") != test_plan.get("test_plan_id"):
        errors.append("approval_request:test_plan_link_mismatch")
    if receipt.get("source_refs", {}).get("approval_request") != approval.get("approval_request_id"):
        errors.append("receipt:approval_request_link_mismatch")


def _validate_pr_preview(artifact: Mapping[str, Any], errors: list[str]) -> None:
    if not isinstance(artifact, Mapping):
        errors.append("pr_command_preview:artifact_must_be_object")
        return
    if artifact.get("preview_only") is not True:
        errors.append("pr_command_preview:preview_only_must_be_true")
    if artifact.get("execution_performed") is not False:
        errors.append("pr_command_preview:execution_performed_must_be_false")
    commands = artifact.get("command_preview")
    if not isinstance(commands, list) or len(commands) != 2:
        errors.append("pr_command_preview:must_render_two_preview_commands")
        return
    for command in commands:
        if not isinstance(command, Mapping):
            errors.append("pr_command_preview:command_must_be_object")
            continue
        if command.get("execution_allowed") is not False:
            errors.append("pr_command_preview:preview_command_execution_allowed")


def _run_git(repo_root: Path, args: Sequence[str]) -> dict[str, Any]:
    command = ("git", *args)
    completed = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "command": " ".join(command),
        "return_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr[-800:],
        "read_only": True,
    }


def _evidence_refs(repo_status: Mapping[str, Any]) -> list[str]:
    refs = ["local-git://status-short", "local-git://diff-name-only"]
    if repo_status.get("dirty"):
        refs.append("local-git://working-tree-dirty")
    return refs


def _evidence_summaries(repo_status: Mapping[str, Any]) -> list[str]:
    branch = str(repo_status.get("branch") or "unknown")
    changed_files = [str(item) for item in repo_status.get("changed_files", ())]
    status = "dirty" if repo_status.get("dirty") else "clean"
    return [
        f"Local repository branch {branch} is {status}; changed file count={len(changed_files)}.",
        "No source files, branches, pull requests, connectors, or external systems were mutated.",
    ]


def _verification_expectations() -> tuple[str, ...]:
    return (
        "python scripts/validate_local_developer_workflow_v1.py --strict",
        "python -m pytest tests/test_local_developer_workflow_v1.py -q",
        "python scripts/validate_capability_closure_runner.py --strict",
    )


def _require_artifact_filenames(artifact_filenames: Mapping[str, str]) -> None:
    if tuple(artifact_filenames) != tuple(ARTIFACT_FILENAMES):
        raise LocalDeveloperWorkflowV1Error("artifact filenames must use canonical keys and order")
    for key, filename in artifact_filenames.items():
        if not isinstance(filename, str) or not filename.endswith(".json"):
            raise LocalDeveloperWorkflowV1Error(f"{key}: artifact filename must end with .json")


def _required_text(value: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise LocalDeveloperWorkflowV1Error(f"{field_name} is required")
    return normalized


def _bounded_title(value: str, limit: int = 72) -> str:
    normalized = " ".join(value.split())
    return normalized if len(normalized) <= limit else normalized[: limit - 3].rstrip() + "..."


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


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
