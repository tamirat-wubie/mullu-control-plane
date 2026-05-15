"""Purpose: test approval-gated pull-request candidate planning.
Governance scope: local git command boundaries, review packet generation,
    review approval admission, and GitHub PR-open payload blocking.
Dependencies: pytest plus app-builder, PR-candidate, and review contracts.
Invariants:
  - PR candidates are planning receipts and never execute commands.
  - Local git command candidates reject push and other network git effects.
  - GitHub PR-open payloads are unavailable until approval is attached.
  - Approved candidates retain receipt and quality-gate evidence references.
"""

from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.app_builder import ProductSpec
from mcoi_runtime.contracts.pr_candidate import LocalGitCommandCandidate, PullRequestCandidateStatus, PullRequestOpenIntent
from mcoi_runtime.contracts.review import ReviewDecision, ReviewStatus
from mcoi_runtime.core.app_builder.pr_candidate import apply_pull_request_review_decision, build_pull_request_candidate, create_pull_request_review_request, github_pull_request_open_payload
from mcoi_runtime.core.app_builder.task_graph import build_app_task_graph


def _invoice_graph():
    return build_app_task_graph(ProductSpec("Invoice Dashboard", ("finance operator",), ("review invoices",), ("list invoices", "mark invoice paid"), ("production deployment",), ("tenant scoped access",)))


def _candidate():
    return build_pull_request_candidate(_invoice_graph(), repository="tamirat-wubie/mullu-control-plane", base_branch="main", software_receipt_refs=("software-receipt:patch-applied", "software-receipt:gates-passed"), quality_gate_refs=("gate:unit_tests", "gate:lint", "gate:review"))


def test_local_git_command_contract_rejects_push_and_invalid_refs() -> None:
    safe_command = LocalGitCommandCandidate("commit", "create local commit candidate", ("git", "commit", "-m", "Add governed candidate"), metadata={"network_effect": False})

    assert safe_command.command == ("git", "commit", "-m", "Add governed candidate")
    assert safe_command.purpose == "create local commit candidate"
    assert isinstance(safe_command.metadata, MappingProxyType)
    with pytest.raises(ValueError) as push_info:
        LocalGitCommandCandidate("push", "push branch", ("git", "push", "origin", "main"))
    with pytest.raises(ValueError) as exe_info:
        LocalGitCommandCandidate("shell", "run shell", ("powershell", "-Command", "git status"))
    with pytest.raises(ValueError) as intent_info:
        PullRequestOpenIntent("intent", "repo", "Title", "Body", "main", "../bad", "github.open_pull_request", "review-1")

    assert "denied_local_git_subcommand:push" in str(push_info.value)
    assert "local_git_command_must_start_with_git" in str(exe_info.value)
    assert "head_branch_invalid_git_ref" in str(intent_info.value)


def test_pull_request_candidate_rejects_git_ref_edge_cases_before_command_admission() -> None:
    graph = _invoice_graph()

    with pytest.raises(ValueError) as double_dot_info:
        build_pull_request_candidate(graph, repository="tamirat-wubie/mullu-control-plane", candidate_branch="feature..invoice", software_receipt_refs=("receipt:closed",), quality_gate_refs=("gate:unit_tests",))
    with pytest.raises(ValueError) as hidden_component_info:
        build_pull_request_candidate(graph, repository="tamirat-wubie/mullu-control-plane", candidate_branch="feature/.hidden", software_receipt_refs=("receipt:closed",), quality_gate_refs=("gate:unit_tests",))
    with pytest.raises(ValueError) as lock_component_info:
        build_pull_request_candidate(graph, repository="tamirat-wubie/mullu-control-plane", base_branch="release.lock/next", software_receipt_refs=("receipt:closed",), quality_gate_refs=("gate:unit_tests",))
    with pytest.raises(ValueError) as reflog_info:
        PullRequestOpenIntent("intent", "repo", "Title", "Body", "main", "feature@{invoice}", "github.open_pull_request", "review-1")

    assert "branch_name_invalid_git_ref" in str(double_dot_info.value)
    assert "branch_name_invalid_git_ref" in str(hidden_component_info.value)
    assert "base_branch_invalid_git_ref" in str(lock_component_info.value)
    assert "head_branch_invalid_git_ref" in str(reflog_info.value)


def test_build_pull_request_candidate_emits_review_packet_and_pending_intent() -> None:
    candidate = _candidate()
    command_ids = tuple(command.command_id for command in candidate.commit_candidate.local_commands)

    assert candidate.status is PullRequestCandidateStatus.APPROVAL_REQUIRED
    assert candidate.branch_candidate.branch_name.startswith("mullu/app-builder-invoice-dashboard-")
    assert candidate.branch_candidate.create_command.command[:3] == ("git", "checkout", "-b")
    assert command_ids == ("git-stage-candidate-files", "git-commit-candidate")
    assert candidate.open_intent.execution_allowed is False
    assert candidate.open_intent.requires_approval is True
    assert candidate.metadata["local_git_push_allowed"] is False
    assert "Local git push is not allowed by this candidate." in candidate.review_packet.markdown_body
    assert "software-receipt:gates-passed" in candidate.evidence_refs
    assert "gate:review" in candidate.evidence_refs


def test_review_request_and_approval_are_required_before_github_payload() -> None:
    candidate = _candidate()
    review_request = create_pull_request_review_request(candidate, requester_id="operator-1", requested_at="2026-05-07T12:00:00Z")
    decision = ReviewDecision("decision-approve", review_request.request_id, "reviewer-1", ReviewStatus.APPROVED, "2026-05-07T12:05:00Z", "Receipts and gates are complete.")

    with pytest.raises(ValueError) as blocked_info:
        github_pull_request_open_payload(candidate)
    approved = apply_pull_request_review_decision(candidate, decision)
    payload = github_pull_request_open_payload(approved)

    assert "pull_request_candidate_not_approved" in str(blocked_info.value)
    assert review_request.request_id == candidate.open_intent.approval_request_id
    assert review_request.metadata["review_packet_id"] == candidate.review_packet.packet_id
    assert approved.status is PullRequestCandidateStatus.APPROVED_FOR_OPEN
    assert approved.open_intent.execution_allowed is True
    assert payload["capability_id"] == "github.open_pull_request"
    assert payload["approval_decision_id"] == "decision-approve"
    assert payload["head_branch"] == approved.branch_candidate.branch_name


def test_rejected_review_blocks_pr_open_intent() -> None:
    candidate = _candidate()
    decision = ReviewDecision("decision-reject", candidate.open_intent.approval_request_id, "reviewer-1", ReviewStatus.REJECTED, "2026-05-07T12:10:00Z", "Residual risk needs another gate.")

    blocked = apply_pull_request_review_decision(candidate, decision)

    assert blocked.status is PullRequestCandidateStatus.BLOCKED
    assert blocked.open_intent.execution_allowed is False
    assert blocked.open_intent.approval_decision_id == ""
    assert "review_decision:decision-reject" in blocked.evidence_refs
    assert blocked.open_intent.metadata["approval_status"] == "rejected"
    with pytest.raises(ValueError) as payload_info:
        github_pull_request_open_payload(blocked)
    with pytest.raises(ValueError) as mismatch_info:
        apply_pull_request_review_decision(candidate, ReviewDecision("decision-wrong", "other-review", "reviewer-1", ReviewStatus.APPROVED, "2026-05-07T12:15:00Z"))

    assert "pull_request_candidate_not_approved" in str(payload_info.value)
    assert "review_decision_request_mismatch" in str(mismatch_info.value)
