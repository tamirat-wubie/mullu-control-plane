"""Purpose: verify minimal replay contract completeness rules for MCOI.
Governance scope: Milestone 1 contract invariant tests.
Dependencies: pytest and the MCOI replay contract layer.
Invariants: replay records require complete identifiers and stable modes.
"""

import pytest

from mcoi_runtime.contracts import ReplayMode, ReplayRecord


def test_replay_record_allows_minimal_complete_shape() -> None:
    record = ReplayRecord(
        replay_id="replay-1",
        trace_id="trace-1",
        source_hash="source-1",
        approved_effects=(),
        blocked_effects=(),
        mode=ReplayMode.OBSERVATION_ONLY,
        recorded_at="2026-03-18T12:00:00+00:00",
    )

    assert record.replay_id == "replay-1"
    assert record.mode is ReplayMode.OBSERVATION_ONLY
    assert record.to_dict()["approved_effects"] == []
    assert record.to_dict()["blocked_effects"] == []


@pytest.mark.parametrize("field_name", ["replay_id", "trace_id", "source_hash"])
def test_replay_record_rejects_blank_required_identifiers(field_name: str) -> None:
    payload = {
        "replay_id": "replay-1",
        "trace_id": "trace-1",
        "source_hash": "source-1",
        "approved_effects": (),
        "blocked_effects": (),
        "mode": ReplayMode.EFFECT_BEARING,
        "recorded_at": "2026-03-18T12:00:00+00:00",
    }
    payload[field_name] = ""

    assert payload["mode"] is ReplayMode.EFFECT_BEARING

    with pytest.raises(ValueError) as exc_info:
        ReplayRecord(**payload)

    assert field_name in str(exc_info.value)
    assert payload[field_name] == ""
