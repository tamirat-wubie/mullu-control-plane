"""Purpose: test the holistic loop read-model report script.
Governance scope: read-only reporting, evidence parsing, blocker exposure,
    and non-terminal closure boundary.
Dependencies: scripts.report_holistic_loop_read_model.
Invariants:
  - Default reports remain blocked by missing evidence.
  - Complete evidence can verify summaries without executing loop behavior.
  - Invalid evidence arguments fail explicitly.
"""

from __future__ import annotations

import json

from scripts import report_holistic_loop_read_model as reporter


def test_default_report_exposes_blocked_loop_summaries() -> None:
    report = reporter.build_report()
    loops = report["loops"]

    assert report["report_id"] == "holistic_loop_read_model"
    assert report["status"] == "blocked"
    assert report["loop_count"] == 4
    assert report["blocked_count"] == 4
    assert report["report_is_not_terminal_closure"] is True
    assert isinstance(loops, list)
    assert {loop["loop_id"] for loop in loops} == {
        "deployment_witness_loop",
        "runtime_conformance_loop",
        "cognitive_outcome_loop",
        "governed_code_change_loop",
    }
    assert all(loop["open_blockers"] for loop in loops)
    assert all(loop["evidence_bindings"] for loop in loops)
    assert all(
        {binding["evidence_ref"] for binding in loop["evidence_bindings"]}
        == set(loop["required_evidence"])
        for loop in loops
    )
    assert all(
        binding["read_only"] is True and binding["terminal_closure"] is False
        for loop in loops
        for binding in loop["evidence_bindings"]
    )


def test_report_accepts_complete_observed_evidence_refs() -> None:
    baseline = reporter.build_report()
    observed = {
        loop["loop_id"]: tuple(loop["required_evidence"])
        for loop in baseline["loops"]
        if isinstance(loop, dict)
    }
    report = reporter.build_report(observed_evidence_refs=observed)

    assert report["status"] == "verified"
    assert report["blocked_count"] == 0
    assert report["verified_count"] == 4
    assert all(loop["missing_evidence"] == [] for loop in report["loops"])
    assert all(loop["status"] == "verified" for loop in report["loops"])
    assert all(loop["evidence_bindings"] for loop in report["loops"])


def test_parse_evidence_refs_groups_repeatable_args() -> None:
    parsed = reporter.parse_evidence_refs(
        (
            "deployment_witness_loop=deployment_witness_published",
            "deployment_witness_loop=runtime_witness_valid",
            "runtime_conformance_loop=certificate_schema_valid",
        )
    )

    assert parsed["deployment_witness_loop"] == (
        "deployment_witness_published",
        "runtime_witness_valid",
    )
    assert parsed["runtime_conformance_loop"] == ("certificate_schema_valid",)
    assert len(parsed) == 2


def test_main_emits_json_report(capsys) -> None:  # noqa: ANN001
    exit_code = reporter.main(["--json", "--limit", "2"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["returned_count"] == 2
    assert payload["truncated"] is True
    assert payload["terminal_closure_required"] is True


def test_main_rejects_malformed_evidence_ref(capsys) -> None:  # noqa: ANN001
    exit_code = reporter.main(["--evidence-ref", "missing-separator"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "loop_id=evidence_ref" in captured.err
    assert "STATUS: failed" in captured.err
