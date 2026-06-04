"""Tests for finance approval operator page rendering.

Purpose: prove the static finance operator HTML page is rendered only from a
validated redacted summary and preserves promotion guardrails.
Governance scope: finance operator page validation, HTML escaping, blocked
summary preservation, write behavior, and strict CLI blocking.
Dependencies: scripts.render_finance_approval_operator_page.
Invariants:
  - Invalid summaries fail closed before page emission.
  - Rendered values are escaped.
  - The page contains no JavaScript.
  - Must-not-claim boundaries remain visible.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.finance_approval_handoff_test_fixtures import (
    produce_finance_handoff_packet_from_sources,
    write_finance_handoff_sources,
)
from scripts.produce_finance_approval_operator_summary import produce_finance_approval_operator_summary
from scripts.render_finance_approval_operator_page import (
    main,
    render_finance_approval_operator_page,
    write_finance_approval_operator_page,
)
from scripts.validate_finance_approval_live_handoff_chain import (
    validate_finance_approval_live_handoff_chain,
    write_finance_live_handoff_chain_validation,
)

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "finance_approval_operator_summary.schema.json"


def test_finance_operator_page_renders_valid_blocked_summary(tmp_path: Path) -> None:
    summary_path = _write_summary(tmp_path, live_ready=False)
    output_path = tmp_path / "finance_operator_page.html"

    rendered_html, render = render_finance_approval_operator_page(
        summary_path=summary_path,
        schema_path=SCHEMA_PATH,
        output_path=output_path,
    )

    assert render.ok is True
    assert render.errors == ()
    assert render.output_path == output_path.name
    assert render.packet_ready is False
    assert render.chain_ready is False
    assert render.readiness_blocker_count >= 1
    assert "<script" not in rendered_html.lower()
    assert "Mullusi Finance Approval Operator Page" in rendered_html
    assert "proof-pilot-blocked" in rendered_html
    assert "live email delivery" in rendered_html
    assert "validate_finance_approval_live_handoff_chain.py" in rendered_html
    assert "--require-ready" in rendered_html


def test_finance_operator_page_escapes_summary_text(tmp_path: Path) -> None:
    summary_path = _write_summary(tmp_path, live_ready=False)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["readiness_blockers"][0] = "blocked <script>alert(1)</script>"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    rendered_html, render = render_finance_approval_operator_page(
        summary_path=summary_path,
        schema_path=SCHEMA_PATH,
        output_path=tmp_path / "finance_operator_page.html",
    )

    assert render.ok is True
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered_html
    assert "blocked <script>alert(1)</script>" not in rendered_html
    assert "<script" not in rendered_html.lower()


def test_finance_operator_page_rejects_invalid_summary_before_write(tmp_path: Path) -> None:
    summary_path = _write_summary(tmp_path, live_ready=False)
    output_path = tmp_path / "finance_operator_page.html"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["must_not_claim"].append("invented production claim")
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    rendered_html, render = render_finance_approval_operator_page(
        summary_path=summary_path,
        schema_path=SCHEMA_PATH,
        output_path=output_path,
    )

    assert rendered_html == ""
    assert render.ok is False
    assert output_path.exists() is False
    assert any("must_not_claim" in error for error in render.errors)


def test_finance_operator_page_writer_and_cli_emit_json(tmp_path: Path, capsys) -> None:
    summary_path = _write_summary(tmp_path, live_ready=False)
    output_path = tmp_path / "finance_operator_page.html"
    rendered_html, render = render_finance_approval_operator_page(
        summary_path=summary_path,
        schema_path=SCHEMA_PATH,
        output_path=output_path,
    )

    written = write_finance_approval_operator_page(rendered_html, output_path)
    exit_code = main(
        [
            "--summary",
            str(summary_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)

    assert render.ok is True
    assert written == output_path
    assert exit_code == 0
    assert output_path.exists() is True
    assert stdout_payload["ok"] is True
    assert stdout_payload["output_path"] == output_path.name
    assert stdout_payload["schema_path"] == "schemas/finance_approval_operator_summary.schema.json"
    assert str(tmp_path) not in captured.out


def test_finance_operator_page_cli_honors_strict_invalid_summary(tmp_path: Path, capsys) -> None:
    summary_path = _write_summary(tmp_path, live_ready=False)
    output_path = tmp_path / "finance_operator_page.html"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["promotion_mode"] = "live-email-handoff"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    exit_code = main(
        [
            "--summary",
            str(summary_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)

    assert exit_code == 2
    assert output_path.exists() is False
    assert stdout_payload["ok"] is False
    assert any("promotion_mode" in error for error in stdout_payload["errors"])


def _write_summary(tmp_path: Path, *, live_ready: bool) -> Path:
    paths = write_finance_handoff_sources(tmp_path, live_ready=live_ready)
    packet_path = tmp_path / "finance_handoff_packet.json"
    chain_path = tmp_path / "finance_handoff_chain.json"
    summary_path = tmp_path / "finance_operator_summary.json"
    packet_path.write_text(json.dumps(produce_finance_handoff_packet_from_sources(paths)), encoding="utf-8")
    chain = validate_finance_approval_live_handoff_chain(
        closure_run_path=paths["closure_run"],
        live_receipt_path=paths["live_receipt"],
        preflight_path=paths["preflight"],
        packet_path=packet_path,
    )
    write_finance_live_handoff_chain_validation(chain, chain_path)
    summary, errors = produce_finance_approval_operator_summary(packet_path=packet_path, chain_path=chain_path)
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    assert errors == ()
    return summary_path
