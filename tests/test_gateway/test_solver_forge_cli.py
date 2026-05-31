"""Tests for the solver-forge CLI."""

from __future__ import annotations

import argparse
import json

from gateway.solver_forge_cli import build_parser, main


def _subcommand_choices() -> set[str]:
    parser = build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


def test_cli_has_no_promotion_subcommand():
    choices = _subcommand_choices()
    assert choices == {"list-capsules", "list-benchmarks", "run", "forge-input"}
    for forbidden in ("promote", "install", "certify", "deploy", "register"):
        assert forbidden not in choices


def test_list_benchmarks(capsys):
    assert main(["list-benchmarks"]) == 0
    out = capsys.readouterr().out
    assert "invoice_duplicate_detection.v1" in out


def test_list_capsules_all_and_filtered(capsys):
    assert main(["list-capsules"]) == 0
    full = capsys.readouterr().out
    assert "capsule:graph_match.vendor_amount_proximity.v1" in full

    assert main(["list-capsules", "--family", "graph_match"]) == 0
    filtered = capsys.readouterr().out
    assert "graph_match" in filtered
    assert "capsule:rule_based.exact_field_match.v1" not in filtered


def test_list_capsules_by_domain_includes_general(capsys):
    assert main(["list-capsules", "--domain", "document_verification"]) == 0
    out = capsys.readouterr().out
    # domain-tagged capsule present...
    assert "capsule:rule_based.exact_field_match.v1" in out
    # ...and an untagged general-purpose capsule is included too.
    assert "capsule:human_review_gate.approval.v1" in out


def test_run_text_reports_winner(capsys):
    assert main(["run", "invoice_duplicate_detection.v1"]) == 0
    out = capsys.readouterr().out
    assert "Winners (1):" in out
    assert "graph_match" in out
    assert "Passed non-winners (1):" in out
    assert "Baseline compromised: False" in out


def test_run_json_is_machine_readable(capsys):
    assert main(["run", "invoice_duplicate_detection.v1", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["winners"]) == 1
    assert payload["winners"][0]["method_families"] == ["graph_match"]
    assert payload["primary_metric_id"] == "f1_score"
    assert len(payload["passed_non_winners"]) == 1


def test_run_unknown_benchmark_errors(capsys):
    assert main(["run", "does-not-exist"]) == 1
    assert "error" in capsys.readouterr().out


def test_run_writes_ledger_file(tmp_path, capsys):
    out_path = tmp_path / "ledger.json"
    assert main(["run", "invoice_duplicate_detection.v1", "--ledger-out", str(out_path)]) == 0
    capsys.readouterr()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    # baseline + 2 candidates recorded, append-only.
    assert len(data["records"]) == 3


def test_forge_input_preview_is_read_only(capsys):
    rc = main(
        [
            "forge-input",
            "invoice_duplicate_detection.v1",
            "--capability-id",
            "finance.duplicate_invoice_guard.v1",
            "--owner-team",
            "finance-platform",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "PREVIEW ONLY" in out
    payload = json.loads(out[out.index("{") :])
    assert payload["domain"] == "document_verification"
    assert payload["solver_forge_provenance"]["primary_metric_id"] == "f1_score"
