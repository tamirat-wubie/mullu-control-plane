"""Purpose: plan approval-gated pull-request candidates from app task graphs.
Governance scope: local branch/commit candidates, review packet generation,
    approval request creation, and GitHub PR-open payload admission.
Dependencies: hashlib, json, app-builder contracts, PR-candidate contracts,
    and review contracts.
Invariants:
  - This module is side-effect free and never runs git or GitHub commands.
  - Local git command candidates exclude push and other network git effects.
  - GitHub PR-open payloads are unavailable until review approval is attached.
  - Candidate evidence binds graph, receipts, quality gates, and review packet.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, replace
from hashlib import sha256
from typing import Any

from mcoi_runtime.contracts.app_builder import AppTaskGraph, AppTaskRisk
from mcoi_runtime.contracts.pr_candidate import LocalGitCommandCandidate, PullRequestBranchCandidate, PullRequestCandidateBundle, PullRequestCandidateStatus, PullRequestCommitCandidate, PullRequestOpenIntent, PullRequestReviewPacket
from mcoi_runtime.contracts.review import ReviewDecision, ReviewRequest, ReviewScope, ReviewScopeType


_GITHUB_OPEN_PR_CAPABILITY = "github.open_pull_request"


def build_pull_request_candidate(
    graph: AppTaskGraph,
    *,
    repository: str,
    base_branch: str = "main",
    candidate_branch: str = "",
    title: str = "",
    software_receipt_refs: tuple[str, ...],
    quality_gate_refs: tuple[str, ...],
) -> PullRequestCandidateBundle:
    """Build a pull-request candidate bundle from an app task graph."""
    if not isinstance(graph, AppTaskGraph):
        raise ValueError("graph must be an AppTaskGraph")
    repository_name = repository.strip()
    if not repository_name:
        raise ValueError("repository must be non-empty")
    if not software_receipt_refs:
        raise ValueError("software_receipt_refs must contain at least one item")
    if not quality_gate_refs:
        raise ValueError("quality_gate_refs must contain at least one item")
    branch_name = candidate_branch.strip() or _default_branch_name(graph)
    pr_title = title.strip() or f"{graph.app_name}: governed app-builder candidate"
    affected_files = _all_affected_files(graph)
    risk_flags = _risk_flags(graph)
    approval_request_id = f"review-pr-{_hash_payload({'graph': graph.graph_id, 'branch': branch_name})[:16]}"
    branch_candidate = PullRequestBranchCandidate(
        branch_name=branch_name,
        base_branch=base_branch,
        create_command=LocalGitCommandCandidate("git-branch-candidate", "create local branch candidate from current reviewed worktree state", ("git", "checkout", "-b", branch_name), True, {"network_effect": False}),
        rollback_command=LocalGitCommandCandidate("git-branch-rollback", "return operator to base branch if candidate is rejected", ("git", "checkout", base_branch), metadata={"network_effect": False}),
    )
    commit_message = f"Add {graph.app_name} app-builder candidate"
    commit_candidate = PullRequestCommitCandidate(
        commit_message=commit_message,
        affected_files=affected_files,
        receipt_refs=software_receipt_refs,
        quality_gate_refs=quality_gate_refs,
        local_commands=(
            LocalGitCommandCandidate("git-stage-candidate-files", "stage only files declared by the app task graph", ("git", "add", "--", *affected_files), metadata={"file_count": len(affected_files), "network_effect": False}),
            LocalGitCommandCandidate("git-commit-candidate", "create local commit candidate after gates and review packet are ready", ("git", "commit", "-m", commit_message), metadata={"network_effect": False}),
        ),
    )
    packet_body = _review_packet_markdown(graph, repository_name, base_branch, branch_name, pr_title, affected_files, quality_gate_refs, software_receipt_refs, risk_flags)
    review_packet = PullRequestReviewPacket(
        packet_id=f"pr-review-packet-{_hash_payload(packet_body)[:16]}",
        title=pr_title,
        summary=f"Governed PR candidate for {graph.app_name}",
        affected_files=affected_files,
        quality_gate_refs=quality_gate_refs,
        receipt_refs=software_receipt_refs,
        risk_flags=risk_flags,
        rollback_plan=(f"git checkout {base_branch}", f"delete local branch {branch_name} only after confirming no work is needed", "do not push or open a pull request when review is rejected"),
        markdown_body=packet_body,
        metadata={"graph_id": graph.graph_id, "task_count": len(graph.tasks), "approval_request_id": approval_request_id},
    )
    open_intent = PullRequestOpenIntent(
        intent_id=f"pr-open-intent-{_hash_payload({'packet': review_packet.packet_id})[:16]}",
        repository=repository_name,
        title=pr_title,
        body=packet_body,
        base_branch=base_branch,
        head_branch=branch_name,
        capability_id=_GITHUB_OPEN_PR_CAPABILITY,
        approval_request_id=approval_request_id,
        requires_approval=True,
        world_mutating=True,
        execution_allowed=False,
        metadata={"review_packet_id": review_packet.packet_id, "github_effect": "open_pull_request", "separate_governed_capability_required": True},
    )
    return PullRequestCandidateBundle(
        candidate_id=f"pr-candidate-{_hash_payload({'graph': graph.graph_id, 'intent': open_intent.intent_id})[:16]}",
        status=PullRequestCandidateStatus.APPROVAL_REQUIRED,
        repository=repository_name,
        branch_candidate=branch_candidate,
        commit_candidate=commit_candidate,
        review_packet=review_packet,
        open_intent=open_intent,
        evidence_refs=tuple(dict.fromkeys((f"app_task_graph:{graph.graph_id}", f"review_packet:{review_packet.packet_id}", f"approval_request:{approval_request_id}", *software_receipt_refs, *quality_gate_refs))),
        metadata={"local_git_push_allowed": False, "github_open_requires_approval": True, "direct_deployment_allowed": False, "github_capability_id": _GITHUB_OPEN_PR_CAPABILITY},
    )


def create_pull_request_review_request(candidate: PullRequestCandidateBundle, *, requester_id: str, requested_at: str, expires_at: str | None = None) -> ReviewRequest:
    """Create the human review request required before PR opening."""
    if not isinstance(candidate, PullRequestCandidateBundle):
        raise ValueError("candidate must be a PullRequestCandidateBundle")
    return ReviewRequest(
        request_id=candidate.open_intent.approval_request_id,
        requester_id=requester_id,
        scope=ReviewScope(ReviewScopeType.SOFTWARE_RECEIPT_CHAIN, candidate.candidate_id, f"Approve pull-request candidate {candidate.candidate_id}"),
        reason="Pull-request opening is a world-mutating GitHub effect and requires review approval.",
        requested_at=requested_at,
        expires_at=expires_at,
        metadata={"repository": candidate.repository, "review_packet_id": candidate.review_packet.packet_id, "pr_open_intent_id": candidate.open_intent.intent_id, "github_capability_id": candidate.open_intent.capability_id},
    )


def apply_pull_request_review_decision(candidate: PullRequestCandidateBundle, decision: ReviewDecision) -> PullRequestCandidateBundle:
    """Attach a review decision and return the next PR-candidate state."""
    if decision.request_id != candidate.open_intent.approval_request_id:
        raise ValueError("review_decision_request_mismatch")
    if decision.is_approved:
        intent = replace(candidate.open_intent, execution_allowed=True, approval_decision_id=decision.decision_id, metadata={**dict(candidate.open_intent.metadata), "approval_status": decision.status.value})
        return replace(candidate, status=PullRequestCandidateStatus.APPROVED_FOR_OPEN, open_intent=intent, evidence_refs=tuple(dict.fromkeys((*candidate.evidence_refs, f"review_decision:{decision.decision_id}"))))
    intent = replace(candidate.open_intent, execution_allowed=False, approval_decision_id="", metadata={**dict(candidate.open_intent.metadata), "approval_status": decision.status.value})
    return replace(candidate, status=PullRequestCandidateStatus.BLOCKED, open_intent=intent, evidence_refs=tuple(dict.fromkeys((*candidate.evidence_refs, f"review_decision:{decision.decision_id}"))))


def github_pull_request_open_payload(candidate: PullRequestCandidateBundle) -> dict[str, Any]:
    """Return the governed GitHub PR-open payload after approval only."""
    if candidate.status is not PullRequestCandidateStatus.APPROVED_FOR_OPEN:
        raise ValueError("pull_request_candidate_not_approved")
    if not candidate.open_intent.execution_allowed:
        raise ValueError("pull_request_open_intent_not_executable")
    return {"capability_id": candidate.open_intent.capability_id, "repository": candidate.repository, "base_branch": candidate.open_intent.base_branch, "head_branch": candidate.open_intent.head_branch, "title": candidate.open_intent.title, "body": candidate.open_intent.body, "approval_request_id": candidate.open_intent.approval_request_id, "approval_decision_id": candidate.open_intent.approval_decision_id, "review_packet_id": candidate.review_packet.packet_id}


def _all_affected_files(graph: AppTaskGraph) -> tuple[str, ...]:
    files: list[str] = []
    for task in graph.tasks:
        for file_path in task.affected_files:
            if file_path not in files:
                files.append(file_path)
    return tuple(files)


def _risk_flags(graph: AppTaskGraph) -> tuple[str, ...]:
    flags = [f"high_risk_task:{task.task_id}" for task in graph.tasks if task.risk is AppTaskRisk.HIGH]
    return tuple(flags) or ("risk_profile:no_high_risk_tasks",)


def _default_branch_name(graph: AppTaskGraph) -> str:
    return f"mullu/app-builder-{_slug(graph.app_name)}-{_hash_payload({'graph_id': graph.graph_id})[:8]}"


def _review_packet_markdown(graph: AppTaskGraph, repository: str, base_branch: str, head_branch: str, title: str, affected_files: tuple[str, ...], quality_gate_refs: tuple[str, ...], software_receipt_refs: tuple[str, ...], risk_flags: tuple[str, ...]) -> str:
    return "\n".join((
        f"# {title}", "", "## Scope", f"- Repository: {repository}", f"- Base branch: {base_branch}", f"- Candidate branch: {head_branch}", f"- App task graph: {graph.graph_id}", "", "## Tasks", *[f"- {task.task_id}: {task.title}" for task in graph.tasks], "", "## Affected Files", *[f"- {file_path}" for file_path in affected_files], "", "## Quality Gates", *[f"- {gate_ref}" for gate_ref in quality_gate_refs], "", "## Software Receipts", *[f"- {receipt_ref}" for receipt_ref in software_receipt_refs], "", "## Risk Flags", *[f"- {risk_flag}" for risk_flag in risk_flags], "", "## Guardrails", "- Local git push is not allowed by this candidate.", "- Opening a GitHub pull request requires approval.", "- Production deployment is out of scope."))


def _slug(value: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", value.lower())) or "app"


def _hash_payload(payload: Any) -> str:
    return sha256(json.dumps(_json_ready(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _json_ready(value: Any) -> Any:
    if hasattr(value, "to_json_dict"):
        return value.to_json_dict()
    if hasattr(value, "__dataclass_fields__"):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
