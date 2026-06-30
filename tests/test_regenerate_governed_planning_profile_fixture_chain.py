"""Tests for the governed-planning-profile fixture chain helper.

Purpose: verify deterministic fixture-chain drift detection and explicit
rewrite behavior for governed-planning-profile examples.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: scripts.regenerate_governed_planning_profile_fixture_chain and
checked-in governed-planning-profile JSON fixtures.
Invariants: default checks do not mutate fixtures, stale fixture reports name
the first causal mismatch, and explicit writes repair generated fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import regenerate_governed_planning_profile_fixture_chain as fixture_chain


def test_governed_planning_profile_fixture_chain_matches_checked_in_files() -> None:
    candidates = fixture_chain.build_governed_planning_profile_fixture_chain()
    evaluations = fixture_chain.evaluate_fixture_chain(candidates)
    summary = fixture_chain.build_summary(evaluations)

    assert len(candidates) == 10
    assert summary["status"] == "passed"
    assert summary["stale_count"] == 0
    assert summary["first_stale_fixture"] is None
    assert all(evaluation.matched for evaluation in evaluations)
    assert all(evaluation.action == "unchanged" for evaluation in evaluations)


def test_fixture_chain_reports_first_stale_fixture_without_writing(tmp_path: Path) -> None:
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_text('{"value": 0}\n', encoding="utf-8")
    second_path.write_text('{\n  "value": 2\n}\n', encoding="utf-8")
    candidates = (
        fixture_chain.FixtureCandidate("first", first_path, {"value": 1}),
        fixture_chain.FixtureCandidate("second", second_path, {"value": 2}),
    )

    evaluations = fixture_chain.evaluate_fixture_chain(candidates)
    first_stale = fixture_chain.first_stale_fixture(evaluations)
    summary = fixture_chain.build_summary(evaluations)

    assert first_stale is not None
    assert first_stale.fixture_id == "first"
    assert first_stale.path == first_path
    assert first_stale.action == "stale"
    assert first_path.read_text(encoding="utf-8") == '{"value": 0}\n'
    assert summary["status"] == "stale"
    assert summary["stale_count"] == 1


def test_fixture_chain_write_repairs_stale_fixture(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text('{"value": 0}\n', encoding="utf-8")
    candidates = (
        fixture_chain.FixtureCandidate(
            "fixture",
            fixture_path,
            {"nested": {"value": 1}},
        ),
    )

    write_evaluations = fixture_chain.evaluate_fixture_chain(candidates, write=True)
    check_evaluations = fixture_chain.evaluate_fixture_chain(candidates)
    rewritten_payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert write_evaluations[0].matched is True
    assert write_evaluations[0].action == "written"
    assert check_evaluations[0].matched is True
    assert check_evaluations[0].action == "unchanged"
    assert rewritten_payload == {"nested": {"value": 1}}


def test_fixture_chain_cli_json_reports_checked_fixture_state(capsys) -> None:
    exit_code = fixture_chain.main(["--check", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["fixture_count"] == 10
    assert payload["stale_count"] == 0
    assert payload["first_stale_fixture"] is None
