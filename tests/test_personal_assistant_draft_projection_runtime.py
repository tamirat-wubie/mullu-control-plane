"""Tests for personal-assistant draft projection runtime envelopes.

Purpose: prove the runtime package composes draft-only email/calendar/task
projections into a governed no-effect envelope without relying on validator
script internals.
Governance scope: PR5 draft projection-set identity, approval separation,
receipt alignment, private payload redaction, and no execution authority.
Dependencies: mcoi_runtime.personal_assistant draft projection builders and
schema validation helpers.
Invariants:
  - Runtime envelope output validates against the draft projection schema.
  - Draft and receipt identities remain unique and aligned.
  - Approval drift, effect drift, raw private fields, and secret-like values
    are rejected before envelope emission.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_draft_projection,
    build_personal_assistant_draft_projection_envelope,
)
from scripts.validate_personal_assistant_draft_projection import _validate_projection_semantics
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
DRAFT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_draft_projection.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_draft_projection_envelope_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_draft_projection()
    draft_schema = _load_schema(DRAFT_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)

    assert _validate_schema_instance(draft_schema, envelope) == []
    assert _validate_projection_semantics(envelope, receipt_schema) == ()
    assert envelope["draft_count"] == 3
    assert envelope["draft_ids"] == [
        "pa_draft_projection_item_email_001",
        "pa_draft_projection_item_calendar_001",
        "pa_draft_projection_item_task_001",
    ]
    assert sorted(envelope["connectors_used"]) == ["gmail", "google_calendar"]
    assert envelope["effect_boundary"]["draft_preparation_allowed"] is True
    assert envelope["effect_boundary"]["execution_allowed"] is False
    assert envelope["approval_boundary"]["approval_required_before_external_action"] is True
    assert envelope["metadata"]["system_of_record_write_allowed"] is False


def test_runtime_draft_projection_envelope_rejects_empty_and_duplicate_drafts() -> None:
    envelope = build_default_personal_assistant_draft_projection()
    projection = _draft_payload(envelope, 0)

    with pytest.raises(PersonalAssistantInvariantError) as empty_exc:
        build_personal_assistant_draft_projection_envelope(
            generated_at="2026-06-14T00:02:00+00:00",
            drafts=(),
        )
    with pytest.raises(PersonalAssistantInvariantError) as duplicate_exc:
        build_personal_assistant_draft_projection_envelope(
            generated_at="2026-06-14T00:02:00+00:00",
            drafts=(
                ("pa_draft_projection_item_email_001", projection),
                ("pa_draft_projection_item_email_001", projection),
            ),
        )

    assert "at least one" in str(empty_exc.value)
    assert "duplicate draft_id" in str(duplicate_exc.value)
    assert "pa_draft_projection_item_email_001" in str(duplicate_exc.value)


def test_runtime_draft_projection_envelope_rejects_approval_and_receipt_drift() -> None:
    envelope = build_default_personal_assistant_draft_projection()
    projection = _draft_payload(envelope, 0)
    projection["draft"]["approval_required_before_send"] = False
    projection["receipt"]["approval_required"] = True

    with pytest.raises(PersonalAssistantInvariantError) as draft_exc:
        build_personal_assistant_draft_projection_envelope(
            generated_at="2026-06-14T00:02:00+00:00",
            drafts=(("pa_draft_projection_item_email_001", projection),),
        )

    projection = _draft_payload(envelope, 2)
    projection["receipt"]["metadata"]["memory_write_allowed"] = True
    with pytest.raises(PersonalAssistantInvariantError) as receipt_exc:
        build_personal_assistant_draft_projection_envelope(
            generated_at="2026-06-14T00:02:00+00:00",
            drafts=(("pa_draft_projection_item_task_001", projection),),
        )

    assert "approval_required_before_send must be true" in str(draft_exc.value)
    assert "receipt.metadata.memory_write_allowed must be false" in str(receipt_exc.value)
    assert "private mailbox" not in str(receipt_exc.value)


def test_runtime_draft_projection_envelope_rejects_raw_private_fields_and_secret_values() -> None:
    envelope = build_default_personal_assistant_draft_projection()
    raw_projection = _draft_payload(envelope, 0)
    secret_projection = _draft_payload(envelope, 2)
    raw_projection["draft"]["message_body"] = "private mailbox body"
    secret_projection["draft"]["task_goal"] = "rotate Bearer secret-worker-token"

    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        build_personal_assistant_draft_projection_envelope(
            generated_at="2026-06-14T00:02:00+00:00",
            drafts=(("pa_draft_projection_item_email_001", raw_projection),),
        )
    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_draft_projection_envelope(
            generated_at="2026-06-14T00:02:00+00:00",
            drafts=(("pa_draft_projection_item_task_001", secret_projection),),
        )

    assert "raw private or secret field is forbidden" in str(raw_exc.value)
    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "private mailbox body" not in str(raw_exc.value)


def _draft_payload(envelope: dict[str, object], index: int) -> dict[str, object]:
    drafts = envelope["drafts"]
    assert isinstance(drafts, list)
    item = copy.deepcopy(drafts[index])
    assert isinstance(item, dict)
    return {
        "request_id": item["request_id"],
        "skill_id": item["skill_id"],
        "draft": item["draft"],
        "receipt": item["receipt"],
    }
