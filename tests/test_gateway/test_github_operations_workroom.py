"""GitHub Operations Workroom projection tests.

Purpose: verify the first GitHub Workroom path is governed, deterministic, and
    read-only before live adapter authority exists.
Governance scope: local PR safety intake projection only.
Dependencies: gateway workroom projection and universal capability contracts.
Invariants:
  - Workroom projection emits universal event, policy, episode, receipt, memory gate.
  - Merge, deploy, branch deletion, and comment writes are blocked.
  - Missing evidence fails closed before a non-blocked receipt can be emitted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
import urllib.request

import pytest
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import gateway.server as gateway_server  # noqa: E402
from gateway.github_operations_workroom import (  # noqa: E402
    GitHubReadOnlyEvidenceFetcher,
    GitHubReadOnlyEvidenceAdmissionRequest,
    GITHUB_PR_SAFETY_CAPABILITY_ID,
    admit_github_read_only_evidence_collection,
    build_github_read_only_evidence_fetch_receipt,
    GitHubPrSafetyWorkroomRequest,
    build_pr_safety_projection_from_github_fetch_receipt,
    build_github_pr_safety_workroom_projection,
    build_github_pr_safety_workroom_read_model,
    evaluate_github_pr_safety_judgment,
)
from gateway.server import create_gateway_app  # noqa: E402
from mcoi_runtime.contracts.universal_capability_fabric import (  # noqa: E402
    CAUSAL_EPISODE_STAGE_ORDER,
    FabricMemoryClass,
    FabricMemoryDecisionStatus,
    FabricPolicyDecision,
    FabricRiskClass,
)


class StubPlatform:
    """Minimal platform fixture for gateway app construction."""

    def process_message(self, message, tenant_id: str, identity_id: str):  # noqa: ANN001
        return {
            "response": "ok",
            "tenant_id": tenant_id,
            "identity_id": identity_id,
        }


class FakeGitHubResponse:
    """Minimal context-manager response for urllib-backed fetcher tests."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> "FakeGitHubResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        return None

    def read(self) -> bytes:
        return self._payload


class FakeGitHubUrlopen:
    """Deterministic fake GitHub transport that records outbound requests."""

    def __init__(self) -> None:
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> FakeGitHubResponse:
        self.requests.append(request)
        path = request.full_url.removeprefix("https://api.github.com")
        if path == "/repos/tamiratl/mullu-control-plane/pulls/42":
            if request.headers.get("Accept") == "application/vnd.github.v3.diff":
                return FakeGitHubResponse(b"diff --git a/a.py b/a.py\n")
            return FakeGitHubResponse(
                json.dumps(
                    {
                        "number": 42,
                        "state": "open",
                        "draft": False,
                        "merged": False,
                        "mergeable": True,
                        "changed_files": 2,
                        "commits": 3,
                        "head": {"ref": "feature/pr-42", "sha": "a" * 40},
                        "base": {"ref": "main"},
                    }
                ).encode("utf-8")
            )
        if path == "/repos/tamiratl/mullu-control-plane/pulls/42/files":
            return FakeGitHubResponse(
                json.dumps(
                    [
                        {"filename": "gateway/github_operations_workroom.py"},
                        {"filename": "tests/test_gateway/test_github_operations_workroom.py"},
                    ]
                ).encode("utf-8")
            )
        if path == f"/repos/tamiratl/mullu-control-plane/commits/{'a' * 40}/check-runs":
            return FakeGitHubResponse(
                json.dumps(
                    {
                        "total_count": 2,
                        "check_runs": [
                            {"name": "tests", "status": "completed", "conclusion": "success"},
                            {"name": "lint", "status": "completed", "conclusion": "success"},
                        ],
                    }
                ).encode("utf-8")
            )
        raise AssertionError(f"unexpected GitHub request path: {path}")


def _clock() -> str:
    return "2026-06-28T12:00:00+00:00"


def _request() -> GitHubPrSafetyWorkroomRequest:
    return GitHubPrSafetyWorkroomRequest(
        actor_id="operator:tamirat",
        workspace_id="workspace:mullusi-control-plane",
        repo="tamiratl/mullu-control-plane",
        pull_request_number=42,
        surface_event_id="dashboard-request-42",
        occurred_at="2026-06-28T11:59:00+00:00",
        evidence_refs=(
            "github:pr:42:diff@2026-06-28T11:58:00Z",
            "github:pr:42:checks@2026-06-28T11:58:30Z",
            "github:pr:42:files@2026-06-28T11:58:45Z",
        ),
    )


def test_github_pr_safety_workroom_projection_is_read_only_and_draft_only() -> None:
    projection = build_github_pr_safety_workroom_projection(_request(), clock=_clock)

    assert projection.event.intent == "REVIEW_PR_MERGE_SAFETY"
    assert projection.event.risk_class is FabricRiskClass.CLASS_1_PREPARE
    assert projection.policy.decision is FabricPolicyDecision.ALLOW_DRAFT_ONLY
    assert projection.authority.decision is FabricPolicyDecision.ALLOW_DRAFT_ONLY
    assert projection.connector_write_performed is False
    assert "github.read.diff" in projection.policy.allowed_tools
    assert "post_github_comment_without_write_admission" in projection.policy.blocked_actions
    assert "merge_pull_request_without_explicit_approval" in projection.receipt.actions_blocked
    assert projection.receipt.policy_decision is FabricPolicyDecision.ALLOW_DRAFT_ONLY
    assert projection.receipt.final_judgment.startswith("Awaiting live PR evidence")


def test_github_pr_safety_projection_uses_stable_event_identity() -> None:
    first_projection = build_github_pr_safety_workroom_projection(_request(), clock=_clock)
    second_projection = build_github_pr_safety_workroom_projection(_request(), clock=_clock)

    assert first_projection.event.event_id == second_projection.event.event_id
    assert first_projection.event.idempotency_key == second_projection.event.idempotency_key
    assert first_projection.receipt.receipt_id == second_projection.receipt.receipt_id
    assert first_projection.memory_gate.audit_ref == first_projection.receipt.receipt_id


def test_github_pr_safety_projection_preserves_causal_episode_order() -> None:
    projection = build_github_pr_safety_workroom_projection(_request(), clock=_clock)

    assert tuple(step.stage for step in projection.episode.steps) == CAUSAL_EPISODE_STAGE_ORDER
    assert projection.episode.capability_id == GITHUB_PR_SAFETY_CAPABILITY_ID
    assert projection.episode.steps[0].reason.startswith("Actor requested")
    assert projection.episode.steps[-1].reason == "Store receipt metadata only under project scope."


def test_github_pr_safety_projection_memory_gate_stores_receipt_metadata_only() -> None:
    projection = build_github_pr_safety_workroom_projection(_request(), clock=_clock)

    assert projection.memory_gate.memory_class is FabricMemoryClass.RECEIPT
    assert projection.memory_gate.status is FabricMemoryDecisionStatus.STORE
    assert projection.memory_gate.durable is True
    assert projection.memory_gate.validated is True
    assert projection.memory_gate.scope_ref == "project:workspace:mullusi-control-plane:tamiratl/mullu-control-plane"
    assert "private discussion is excluded" in projection.memory_gate.reasons[0]


def test_github_pr_safety_projection_rejects_missing_evidence() -> None:
    with pytest.raises(ValueError, match="evidence_refs must contain"):
        GitHubPrSafetyWorkroomRequest(
            actor_id="operator:tamirat",
            workspace_id="workspace:mullusi-control-plane",
            repo="tamiratl/mullu-control-plane",
            pull_request_number=42,
            surface_event_id="dashboard-request-42",
            occurred_at="2026-06-28T11:59:00+00:00",
            evidence_refs=(),
        )


def test_github_pr_safety_read_model_degrades_without_evidence() -> None:
    read_model = build_github_pr_safety_workroom_read_model(
        actor_id="operator:tamirat",
        workspace_id="workspace:mullusi-control-plane",
        repo="tamiratl/mullu-control-plane",
        pull_request_number=42,
        surface_event_id="dashboard-request-42",
        occurred_at="2026-06-28T11:59:00+00:00",
        evidence_refs=(),
        clock=_clock,
    )

    assert read_model["status"] == "awaiting_evidence"
    assert read_model["outcome"] == "AwaitingEvidence"
    assert read_model["projection"] is None
    assert read_model["receipt"] is None
    assert read_model["raw_tool_surface_exposed"] is False
    assert read_model["effect_boundary"]["github_call_allowed"] is False
    assert read_model["live_read_admission"]["capability_id"] == "connector.github.read"
    assert read_model["live_read_admission"]["live_connector_read_admitted"] is True
    assert read_model["live_read_admission"]["live_connector_call_performed"] is False
    assert read_model["live_read_admission"]["write_authority_granted"] is False
    assert "github_pr_ci_status" in read_model["missing_evidence"]


def test_github_read_only_evidence_admission_blocks_write_authority() -> None:
    admission = admit_github_read_only_evidence_collection(
        GitHubReadOnlyEvidenceAdmissionRequest(
            actor_id="operator:tamirat",
            workspace_id="workspace:mullusi-control-plane",
            repo="tamiratl/mullu-control-plane",
            pull_request_number=42,
            requested_evidence_kinds=("pull_request", "diff", "checks"),
            requested_at="2026-06-28T11:59:00+00:00",
            surface_event_id="dashboard-request-42",
        ),
        clock=_clock,
    )

    assert admission.capability_id == "connector.github.read"
    assert admission.allowed_tools == ("connector_worker.github_read",)
    assert admission.allowed_networks == ("api.github.com",)
    assert admission.required_secret_scope == "oauth:github.read"
    assert admission.live_connector_read_admitted is True
    assert admission.live_connector_call_performed is False
    assert admission.write_authority_granted is False
    assert "post_github_comment_without_write_admission" in admission.blocked_actions
    assert admission.planned_evidence_refs[1].endswith("/diff")


def test_github_read_only_evidence_admission_rejects_unsupported_evidence_kind() -> None:
    with pytest.raises(ValueError, match="unsupported GitHub evidence kind"):
        GitHubReadOnlyEvidenceAdmissionRequest(
            actor_id="operator:tamirat",
            workspace_id="workspace:mullusi-control-plane",
            repo="tamiratl/mullu-control-plane",
            pull_request_number=42,
            requested_evidence_kinds=("comments",),
            requested_at="2026-06-28T11:59:00+00:00",
            surface_event_id="dashboard-request-42",
        )


def test_github_read_only_evidence_fetcher_collects_bounded_evidence_without_write_authority() -> None:
    admission = admit_github_read_only_evidence_collection(
        GitHubReadOnlyEvidenceAdmissionRequest(
            actor_id="operator:tamirat",
            workspace_id="workspace:mullusi-control-plane",
            repo="tamiratl/mullu-control-plane",
            pull_request_number=42,
            requested_evidence_kinds=("pull_request", "diff", "checks", "changed_files"),
            requested_at="2026-06-28T11:59:00+00:00",
            surface_event_id="dashboard-request-42",
        ),
        clock=_clock,
    )
    fake_urlopen = FakeGitHubUrlopen()

    result = GitHubReadOnlyEvidenceFetcher(
        access_token="github-token-not-returned",
        urlopen=fake_urlopen,
    ).fetch(admission, clock=_clock)

    assert result.capability_id == "connector.github.read"
    assert result.live_connector_call_performed is True
    assert result.write_authority_granted is False
    assert result.solver_outcome == "SolvedVerified"
    assert result.observed_pull_request["head_sha"] == "a" * 40
    assert result.observed_checks["conclusion_counts"] == {"success": 2}
    assert result.changed_files == (
        "gateway/github_operations_workroom.py",
        "tests/test_gateway/test_github_operations_workroom.py",
    )
    assert result.diff_digest.startswith("sha256:")
    assert set(result.payload_hashes) == {"pull_request", "diff", "checks", "changed_files"}
    assert "github-token-not-returned" not in json.dumps(result.to_json_dict(), sort_keys=True)
    assert len(fake_urlopen.requests) == 4
    assert all(request.get_method() == "GET" for request in fake_urlopen.requests)
    assert all(request.full_url.startswith("https://api.github.com/") for request in fake_urlopen.requests)


def test_github_read_only_evidence_fetcher_rejects_unadmitted_write_authority() -> None:
    admission = admit_github_read_only_evidence_collection(
        GitHubReadOnlyEvidenceAdmissionRequest(
            actor_id="operator:tamirat",
            workspace_id="workspace:mullusi-control-plane",
            repo="tamiratl/mullu-control-plane",
            pull_request_number=42,
            requested_evidence_kinds=("pull_request",),
            requested_at="2026-06-28T11:59:00+00:00",
            surface_event_id="dashboard-request-42",
        ),
        clock=_clock,
    )
    tampered_payload = admission.to_dict()
    for tuple_field in (
        "requested_evidence_kinds",
        "planned_evidence_refs",
        "allowed_tools",
        "allowed_networks",
        "blocked_actions",
    ):
        tampered_payload[tuple_field] = tuple(tampered_payload[tuple_field])
    tampered_payload["write_authority_granted"] = True

    with pytest.raises(ValueError, match="write authority"):
        type(admission)(**tampered_payload)


def test_github_read_only_evidence_fetch_receipt_is_read_only_and_hash_bound() -> None:
    result = _fetch_result()

    receipt = build_github_read_only_evidence_fetch_receipt(
        result,
        actor_id="operator:tamirat",
        surface_event_id="dashboard-request-42",
        occurred_at="2026-06-28T12:01:00+00:00",
    )

    assert receipt.intent == "COLLECT_GITHUB_PR_READ_ONLY_EVIDENCE"
    assert receipt.risk_class is FabricRiskClass.CLASS_0_OBSERVE
    assert receipt.policy_decision.value == "allow_read_only"
    assert receipt.evidence_used == result.evidence_refs
    assert "performed_get_only_github_reads" in receipt.actions_taken
    assert "merge_pull_request_without_explicit_approval" in receipt.actions_blocked
    assert receipt.memory_update is FabricMemoryDecisionStatus.STORE
    assert receipt.partial_failure_reasons == ()


def test_github_fetch_receipt_feeds_pr_safety_projection_without_merge_authority() -> None:
    result = _fetch_result()
    fetch_receipt = build_github_read_only_evidence_fetch_receipt(
        result,
        actor_id="operator:tamirat",
        surface_event_id="dashboard-request-42",
        occurred_at="2026-06-28T12:01:00+00:00",
    )

    projection = build_pr_safety_projection_from_github_fetch_receipt(
        fetch_receipt=fetch_receipt,
        actor_id="operator:tamirat",
        workspace_id="workspace:mullusi-control-plane",
        repo="tamiratl/mullu-control-plane",
        pull_request_number=42,
        surface_event_id="dashboard-request-42-safety",
        occurred_at="2026-06-28T12:02:00+00:00",
        clock=_clock,
    )

    assert projection.event.trace_ref == fetch_receipt.receipt_id
    assert projection.event.context_refs[0] == fetch_receipt.receipt_id
    assert projection.receipt.policy_decision is FabricPolicyDecision.ALLOW_DRAFT_ONLY
    assert projection.receipt.final_judgment.startswith("Awaiting live PR evidence")
    assert "merge_pull_request_without_explicit_approval" in projection.receipt.actions_blocked
    assert projection.memory_gate.status is FabricMemoryDecisionStatus.STORE


def test_github_pr_safety_judgment_ready_for_review_without_merge_authority() -> None:
    result = _fetch_result()
    fetch_receipt = _fetch_receipt(result)

    judgment = evaluate_github_pr_safety_judgment(
        fetch_result=result,
        fetch_receipt=fetch_receipt,
        clock=_clock,
    )

    assert judgment.status == "ready_for_review"
    assert judgment.merge_authority_granted is False
    assert judgment.write_authority_granted is False
    assert judgment.required_next_action == "continue_human_or_governed_review_without_auto_merge"
    assert "required_read_only_evidence_present" in judgment.reasons
    assert fetch_receipt.receipt_id == judgment.evidence_refs[0]


def test_github_pr_safety_judgment_blocks_draft_or_failing_checks() -> None:
    result = _fetch_result()
    blocked_result = _result_with(
        result,
        observed_pull_request={**result.observed_pull_request, "draft": True},
        observed_checks={"total_count": 1, "conclusion_counts": {"failure": 1}, "status_counts": {"completed": 1}},
    )
    fetch_receipt = _fetch_receipt(blocked_result)

    judgment = evaluate_github_pr_safety_judgment(
        fetch_result=blocked_result,
        fetch_receipt=fetch_receipt,
        clock=_clock,
    )

    assert judgment.status == "blocked"
    assert "pull_request_is_draft" in judgment.reasons
    assert "checks_not_passing:failure" in judgment.reasons
    assert judgment.merge_authority_granted is False


def test_github_pr_safety_judgment_needs_evidence_for_partial_fetch() -> None:
    result = _fetch_result()
    partial_result = _result_with(
        result,
        fetched_evidence_kinds=("pull_request", "changed_files"),
        evidence_refs=tuple(ref for ref in result.evidence_refs if not ref.endswith(("/diff", "/checks"))),
        payload_hashes={
            "pull_request": result.payload_hashes["pull_request"],
            "changed_files": result.payload_hashes["changed_files"],
        },
        observed_checks={"total_count": 0, "conclusion_counts": {}},
        diff_digest="",
        partial_failure_reasons=("diff:github_read_failed", "checks:missing_pull_request_head_sha"),
    )
    fetch_receipt = _fetch_receipt(partial_result)

    judgment = evaluate_github_pr_safety_judgment(
        fetch_result=partial_result,
        fetch_receipt=fetch_receipt,
        clock=_clock,
    )

    assert judgment.status == "needs_evidence"
    assert "missing_diff" in judgment.reasons
    assert "missing_checks" in judgment.reasons
    assert "partial_failure:diff:github_read_failed" in judgment.reasons
    assert judgment.required_next_action == "collect_missing_or_fresher_read_only_github_evidence"


def test_operator_github_operations_pr_safety_preview_endpoint_is_read_only() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.post(
        "/operator/github-operations/pr-safety/preview",
        json={
            "actor_id": "operator:tamirat",
            "workspace_id": "workspace:mullusi-control-plane",
            "repo": "tamiratl/mullu-control-plane",
            "pull_request_number": 42,
            "surface_event_id": "dashboard-request-42",
            "occurred_at": "2026-06-28T11:59:00+00:00",
            "evidence_refs": [
                "github:pr:42:diff@2026-06-28T11:58:00Z",
                "github:pr:42:checks@2026-06-28T11:58:30Z",
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    projection = payload["github_operations_workroom_projection"]
    assert payload["outcome"] == "AwaitingEvidence"
    assert payload["execution_allowed"] is False
    assert payload["effect_boundary"]["github_call_allowed"] is False
    assert payload["effect_boundary"]["pull_request_mutation_allowed"] is False
    assert projection["policy"]["decision"] == "allow_draft_only"
    assert projection["connector_write_performed"] is False
    assert "merge_pull_request_without_explicit_approval" in payload["receipt"]["actions_blocked"]


def test_operator_github_operations_pr_safety_preview_endpoint_fails_closed_without_evidence() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.post(
        "/operator/github-operations/pr-safety/preview",
        json={
            "repo": "tamiratl/mullu-control-plane",
            "pull_request_number": 42,
            "occurred_at": "2026-06-28T11:59:00+00:00",
            "evidence_refs": [],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "invalid_github_operations_pr_safety_preview"
    assert response.json()["detail"]["governed"] is True


def test_operator_github_read_only_evidence_admission_preview_endpoint() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.post(
        "/operator/github-operations/pr-safety/read-admission/preview",
        json={
            "actor_id": "operator:tamirat",
            "workspace_id": "workspace:mullusi-control-plane",
            "repo": "tamiratl/mullu-control-plane",
            "pull_request_number": 42,
            "requested_at": "2026-06-28T11:59:00+00:00",
            "surface_event_id": "dashboard-request-42",
            "requested_evidence_kinds": ["pull_request", "diff", "checks", "changed_files"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    admission = payload["github_read_only_evidence_admission"]
    assert payload["outcome"] == "AwaitingEvidence"
    assert payload["live_connector_call_performed"] is False
    assert payload["write_authority_granted"] is False
    assert admission["capability_id"] == "connector.github.read"
    assert admission["allowed_networks"] == ["api.github.com"]
    assert admission["required_secret_scope"] == "oauth:github.read"
    assert "delete_branch_without_explicit_approval" in admission["blocked_actions"]


def test_operator_github_read_only_evidence_admission_preview_endpoint_rejects_write_like_kind() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.post(
        "/operator/github-operations/pr-safety/read-admission/preview",
        json={
            "repo": "tamiratl/mullu-control-plane",
            "pull_request_number": 42,
            "requested_at": "2026-06-28T11:59:00+00:00",
            "requested_evidence_kinds": ["comment"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "invalid_github_read_only_evidence_admission_preview"


def test_operator_github_read_only_evidence_execution_endpoint_returns_receipts_without_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_urlopen = FakeGitHubUrlopen()

    def _fetcher_factory(**kwargs):  # noqa: ANN001
        return GitHubReadOnlyEvidenceFetcher(
            access_token=kwargs["access_token"],
            urlopen=fake_urlopen,
            timeout_seconds=kwargs["timeout_seconds"],
        )

    monkeypatch.setattr(gateway_server, "GitHubReadOnlyEvidenceFetcher", _fetcher_factory)
    monkeypatch.setenv("MULLU_GITHUB_WORKROOM_RECEIPT_DIR", str(tmp_path / "github-workroom-receipts"))
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.post(
        "/operator/github-operations/pr-safety/read-evidence",
        json={
            "actor_id": "operator:tamirat",
            "workspace_id": "workspace:mullusi-control-plane",
            "repo": "tamiratl/mullu-control-plane",
            "pull_request_number": 42,
            "requested_at": "2026-06-28T11:59:00+00:00",
            "surface_event_id": "dashboard-request-42",
            "requested_evidence_kinds": ["pull_request", "diff", "checks", "changed_files"],
            "access_token": "github-token-not-returned",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    encoded_payload = json.dumps(payload, sort_keys=True)
    assert "github-token-not-returned" not in encoded_payload
    assert payload["execution_allowed"] is True
    assert payload["live_connector_call_performed"] is True
    assert payload["write_authority_granted"] is False
    assert payload["merge_authority_granted"] is False
    assert payload["effect_boundary"]["github_call_allowed"] is True
    assert payload["effect_boundary"]["repository_read_allowed"] is True
    assert payload["effect_boundary"]["pull_request_mutation_allowed"] is False
    assert payload["github_read_only_evidence_receipt"]["policy_decision"] == "allow_read_only"
    storage = payload["github_read_only_evidence_receipt_storage"]
    storage_path = Path(storage["receipt_path"])
    assert storage_path.exists()
    stored_receipt_text = storage_path.read_text(encoding="utf-8")
    stored_payload = json.loads(stored_receipt_text)
    assert storage["token_persisted"] is False
    assert storage["write_authority_granted"] is False
    assert storage["payload_sha256"].startswith("sha256:")
    assert stored_payload["token_persisted"] is False
    assert stored_payload["write_authority_granted"] is False
    assert stored_payload["merge_authority_granted"] is False
    assert "github-token-not-returned" not in stored_receipt_text
    assert stored_payload["fetch_receipt"]["receipt_id"] == payload["github_read_only_evidence_receipt"]["receipt_id"]
    readback_response = client.get(
        f"/operator/github-operations/pr-safety/read-evidence/receipts/{storage_path.name}"
    )
    assert readback_response.status_code == 200
    readback_payload = readback_response.json()
    assert "github-token-not-returned" not in json.dumps(readback_payload, sort_keys=True)
    assert readback_payload["receipt_filename"] == storage_path.name
    assert readback_payload["token_persisted"] is False
    assert readback_payload["write_authority_granted"] is False
    assert readback_payload["merge_authority_granted"] is False
    assert readback_payload["bundle"]["fetch_receipt"]["receipt_id"] == stored_payload["fetch_receipt"]["receipt_id"]
    assert payload["github_pr_safety_projection"]["receipt"]["policy_decision"] == "allow_draft_only"
    assert payload["github_pr_safety_judgment"]["status"] == "ready_for_review"
    assert len(fake_urlopen.requests) == 4
    assert all(request.get_method() == "GET" for request in fake_urlopen.requests)
    assert all(request.full_url.startswith("https://api.github.com/") for request in fake_urlopen.requests)


def test_operator_github_read_only_evidence_execution_endpoint_rejects_empty_token() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.post(
        "/operator/github-operations/pr-safety/read-evidence",
        json={
            "repo": "tamiratl/mullu-control-plane",
            "pull_request_number": 42,
            "requested_at": "2026-06-28T11:59:00+00:00",
            "requested_evidence_kinds": ["pull_request"],
            "access_token": "",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "invalid_github_read_only_evidence_execution"
    assert response.json()["detail"]["governed"] is True


def test_operator_github_read_only_evidence_receipt_readback_rejects_path_like_name() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get("/operator/github-operations/pr-safety/read-evidence/receipts/..%5Csecret.json")

    assert response.status_code == 400
    assert response.json()["detail"]["governed"] is True


def test_operator_github_operations_pr_safety_read_model_endpoint_awaits_evidence() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get(
        "/operator/github-operations/pr-safety/read-model?repo=tamiratl/mullu-control-plane&pull_request_number=42"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "awaiting_evidence"
    assert payload["projection"] is None
    assert payload["execution_allowed"] is False
    assert payload["effect_boundary"]["github_call_allowed"] is False
    assert payload["effect_boundary"]["pull_request_mutation_allowed"] is False


def test_operator_github_operations_pr_safety_panel_renders_projection() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get(
        "/operator/github-operations/pr-safety",
        params={
            "repo": "tamiratl/mullu-control-plane",
            "pull_request_number": 42,
            "occurred_at": "2026-06-28T11:59:00+00:00",
            "surface_event_id": "dashboard-request-42",
            "evidence_refs": "github:pr:42:diff@2026-06-28T11:58:00Z,github:pr:42:checks@2026-06-28T11:58:30Z",
        },
    )

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Mullusi GitHub Operations Workroom" in response.text
    assert "projection_ready" in response.text
    assert "receipt:" in response.text
    assert "GitHub call allowed" in response.text
    assert "<code>false</code>" in response.text
    assert 'id="github-live-read-form"' in response.text
    assert 'type="password"' in response.text
    assert 'fetch("/operator/github-operations/pr-safety/read-evidence"' in response.text
    assert 'method: "POST"' in response.text
    assert 'tokenInput.value = "";' in response.text
    assert "merge_pull_request_without_explicit_approval" in response.text


def _fetch_result():
    admission = admit_github_read_only_evidence_collection(
        GitHubReadOnlyEvidenceAdmissionRequest(
            actor_id="operator:tamirat",
            workspace_id="workspace:mullusi-control-plane",
            repo="tamiratl/mullu-control-plane",
            pull_request_number=42,
            requested_evidence_kinds=("pull_request", "diff", "checks", "changed_files"),
            requested_at="2026-06-28T11:59:00+00:00",
            surface_event_id="dashboard-request-42",
        ),
        clock=_clock,
    )
    return GitHubReadOnlyEvidenceFetcher(
        access_token="github-token-not-returned",
        urlopen=FakeGitHubUrlopen(),
    ).fetch(admission, clock=_clock)


def _fetch_receipt(result):
    return build_github_read_only_evidence_fetch_receipt(
        result,
        actor_id="operator:tamirat",
        surface_event_id="dashboard-request-42",
        occurred_at="2026-06-28T12:01:00+00:00",
    )


def _result_with(result, **updates):
    payload = result.to_dict()
    for tuple_field in (
        "fetched_evidence_kinds",
        "evidence_refs",
        "changed_files",
        "blocked_actions",
        "partial_failure_reasons",
    ):
        payload[tuple_field] = tuple(payload[tuple_field])
    payload.update(updates)
    for tuple_field in (
        "fetched_evidence_kinds",
        "evidence_refs",
        "changed_files",
        "blocked_actions",
        "partial_failure_reasons",
    ):
        if tuple_field in payload:
            payload[tuple_field] = tuple(payload[tuple_field])
    return type(result)(**payload)
