"""Tests for TeamOps shared inbox observation routing receipt production.

Purpose: prove TeamOps shared inbox routing receipts compose live-probe evidence
into no-send assignment and approval obligations.
Governance scope: TeamOps routing, redacted observation inputs, no-effect
producer claims, assignment gating, and AwaitingEvidence defaults.
Dependencies: scripts.produce_team_ops_shared_inbox_observation_routing_receipt.
Invariants:
  - Blocked live-probe evidence keeps routing blocked.
  - Ready routing requires provider-observation identity, redacted observation
    hashes, and evidence refs.
  - Passed routing never creates drafts, sends messages, or mutates providers.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_team_ops_shared_inbox_observation_routing_receipt import (
    main,
    produce_team_ops_shared_inbox_observation_routing_receipt,
    write_team_ops_shared_inbox_observation_routing_receipt,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_observation_routing_receipt.schema.json"


def test_team_ops_shared_inbox_observation_routing_blocks_without_live_probe_ready(
    tmp_path: Path,
) -> None:
    live_probe_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    live_probe_path.write_text(json.dumps(_blocked_live_probe_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_observation_routing_receipt(
        live_probe_receipt_path=live_probe_path,
        schema_path=SCHEMA_PATH,
        routed_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.solver_outcome == "AwaitingEvidence"
    assert receipt.proof_state == "Unknown"
    assert receipt.live_probe_receipt_valid is True
    assert receipt.live_probe_receipt_ready is False
    assert receipt.provider_observation_receipt_valid is False
    assert receipt.external_send_allowed is False
    assert receipt.draft_created_by_producer is False
    assert receipt.external_mailbox_write_performed is False
    assert receipt.external_message_sent is False
    assert receipt.provider_mutation_performed is False
    assert receipt.blocked_until == ("live_probe_receipt_not_ready",)


def test_team_ops_shared_inbox_observation_routing_requires_redacted_observation(
    tmp_path: Path,
) -> None:
    live_probe_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    live_probe_path.write_text(json.dumps(_ready_live_probe_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_observation_routing_receipt(
        live_probe_receipt_path=live_probe_path,
        schema_path=SCHEMA_PATH,
        routed_at="2026-06-14T00:00:00+00:00",
    )

    assert receipt.status == "blocked"
    assert receipt.live_probe_receipt_ready is True
    assert receipt.provider_observation_receipt_valid is True
    assert receipt.observation_digest == ""
    assert receipt.message_digest == ""
    assert receipt.recipient_hashes == ()
    assert receipt.blocked_until == ("redacted_observation_missing",)


def test_team_ops_shared_inbox_observation_routing_accepts_assignment_plan(
    tmp_path: Path,
) -> None:
    live_probe_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    live_probe_path.write_text(json.dumps(_ready_live_probe_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_observation_routing_receipt(
        live_probe_receipt_path=live_probe_path,
        schema_path=SCHEMA_PATH,
        routed_at="2026-06-14T00:00:00+00:00",
        observation_digest="a" * 64,
        message_digest="b" * 64,
        thread_digest="c" * 64,
        subject_hash="d" * 64,
        sender_hash="e" * 64,
        recipient_hashes=("f" * 64,),
        classification="support_request",
        priority="high",
        owner_queue="support",
        assigned_owner_ref="principal:team-support-owner",
        evidence_refs=("team_ops_routing_observation:aaaaaaaaaaaaaaaa",),
    )

    assert receipt.status == "passed"
    assert receipt.solver_outcome == "SolvedVerified"
    assert receipt.proof_state == "Pass"
    assert receipt.provider_observation_receipt_ref.endswith("team_ops_shared_inbox_provider_observation_receipt.json")
    assert receipt.provider_observation_receipt_id.startswith(
        "teamops-shared-inbox-provider-observation-receipt-"
    )
    assert receipt.provider_observation_receipt_valid is True
    assert receipt.classification == "support_request"
    assert receipt.priority == "high"
    assert receipt.owner_queue == "support"
    assert receipt.assignment_required is True
    assert receipt.assigned_owner_ref == "principal:team-support-owner"
    assert receipt.approval_required_before_external_send is True
    assert receipt.external_send_allowed is False
    assert receipt.draft_created_by_producer is False
    assert receipt.blocked_until == ()


def test_team_ops_shared_inbox_observation_routing_blocks_unknown_classification(
    tmp_path: Path,
) -> None:
    live_probe_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    live_probe_path.write_text(json.dumps(_ready_live_probe_receipt()), encoding="utf-8")

    receipt = produce_team_ops_shared_inbox_observation_routing_receipt(
        live_probe_receipt_path=live_probe_path,
        schema_path=SCHEMA_PATH,
        routed_at="2026-06-14T00:00:00+00:00",
        observation_digest="a" * 64,
        message_digest="b" * 64,
        thread_digest="c" * 64,
        subject_hash="d" * 64,
        sender_hash="e" * 64,
        recipient_hashes=("f" * 64,),
        evidence_refs=("team_ops_routing_observation:aaaaaaaaaaaaaaaa",),
    )

    assert receipt.status == "blocked"
    assert receipt.provider_observation_receipt_valid is True
    assert receipt.classification == "unknown"
    assert receipt.owner_queue == "triage"
    assert receipt.blocked_until == ("routing_classification_missing",)


def test_team_ops_shared_inbox_observation_routing_rejects_secret_marker_ref(
    tmp_path: Path,
) -> None:
    live_probe_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    live_probe_path.write_text(json.dumps(_ready_live_probe_receipt()), encoding="utf-8")

    try:
        produce_team_ops_shared_inbox_observation_routing_receipt(
            live_probe_receipt_path=live_probe_path,
            schema_path=SCHEMA_PATH,
            routed_at="2026-06-14T00:00:00+00:00",
            observation_digest="a" * 64,
            message_digest="b" * 64,
            thread_digest="c" * 64,
            subject_hash="d" * 64,
            sender_hash="e" * 64,
            recipient_hashes=("f" * 64,),
            classification="support_request",
            owner_queue="support",
            assigned_owner_ref="client_secret=must-not-serialize",
            evidence_refs=("team_ops_routing_observation:aaaaaaaaaaaaaaaa",),
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "secret marker" in message
    assert "client_secret" in message
    assert "must-not-serialize" not in message


def test_team_ops_shared_inbox_observation_routing_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    live_probe_path = tmp_path / "team_ops_shared_inbox_live_probe_receipt.json"
    output_path = tmp_path / "team_ops_shared_inbox_observation_routing_receipt.json"
    live_probe_path.write_text(json.dumps(_ready_live_probe_receipt()), encoding="utf-8")
    receipt = produce_team_ops_shared_inbox_observation_routing_receipt(
        live_probe_receipt_path=live_probe_path,
        schema_path=SCHEMA_PATH,
        routed_at="2026-06-14T00:00:00+00:00",
    )

    written = write_team_ops_shared_inbox_observation_routing_receipt(receipt, output_path)
    exit_code = main(
        [
            "--live-probe-receipt",
            str(live_probe_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--routed-at",
            "2026-06-14T00:00:00+00:00",
            "--observation-digest",
            "a" * 64,
            "--message-digest",
            "b" * 64,
            "--thread-digest",
            "c" * 64,
            "--subject-hash",
            "d" * 64,
            "--sender-hash",
            "e" * 64,
            "--recipient-hash",
            "f" * 64,
            "--classification",
            "support_request",
            "--priority",
            "high",
            "--owner-queue",
            "support",
            "--assigned-owner-ref",
            "principal:team-support-owner",
            "--evidence-ref",
            "team_ops_routing_observation:aaaaaaaaaaaaaaaa",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["classification"] == "support_request"
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""


def _blocked_live_probe_receipt() -> dict[str, object]:
    return _base_live_probe_receipt() | {
        "operator_input_request_valid": True,
        "operator_input_probe_allowed": False,
        "status": "blocked",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "connector_id": "",
        "provider_operation": "",
        "provider_observation_receipt_ref": "",
        "provider_observation_receipt_id": "",
        "provider_observation_receipt_valid": False,
        "observed_message_count": 0,
        "response_digest": "",
        "evidence_refs": [],
        "live_probe_observation_bound": False,
        "blocked_until": ["operator_input_request_not_ready"],
        "recovery_actions": ["close TeamOps live-probe operator inputs before binding observation evidence"],
    }


def _ready_live_probe_receipt() -> dict[str, object]:
    return _base_live_probe_receipt() | {
        "operator_input_request_valid": True,
        "operator_input_probe_allowed": True,
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "connector_id": "gmail",
        "provider_operation": "email.search",
        "provider_observation_receipt_ref": ".change_assurance/team_ops_shared_inbox_provider_observation_receipt.json",
        "provider_observation_receipt_id": "teamops-shared-inbox-provider-observation-receipt-aaaaaaaaaaaaaaaa",
        "provider_observation_receipt_valid": True,
        "observed_message_count": 1,
        "response_digest": "a" * 64,
        "evidence_refs": ["team_ops_live_probe_observation:aaaaaaaaaaaaaaaa"],
        "live_probe_observation_bound": True,
        "blocked_until": [],
        "recovery_actions": [],
    }


def _base_live_probe_receipt() -> dict[str, object]:
    return {
        "receipt_id": "teamops-shared-inbox-live-probe-receipt-aaaaaaaaaaaaaaaa",
        "schema_version": 1,
        "workflow_id": "team_ops.shared_inbox_triage",
        "source_operator_input_request_ref": ".change_assurance/team_ops_shared_inbox_live_probe_operator_input_request.json",
        "source_authority_id": "teamops-live-probe-authority-aaaaaaaaaaaaaaaa",
        "checked_at": "2026-06-14T00:00:00+00:00",
        "query_hash": "b" * 64,
        "max_message_count": 12,
        "no_secret_values_serialized": True,
        "external_provider_call_performed_by_producer": False,
        "external_mailbox_write_performed": False,
        "external_message_sent": False,
        "provider_mutation_performed": False,
        "forbidden_effects_observed": False,
        "validation_commands": [
            "python scripts/validate_team_ops_shared_inbox_live_probe_receipt.py --require-ready",
            "python scripts/validate_schemas.py --strict",
        ],
    }
