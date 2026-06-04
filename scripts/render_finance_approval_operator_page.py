#!/usr/bin/env python3
"""Render a static finance approval operator page.

Purpose: convert the redacted finance approval operator summary into a static
HTML page for bounded operator inspection.
Governance scope: finance approval packet readiness, chain readiness,
readiness blockers, artifact statuses, next actions, and claim boundaries.
Dependencies: scripts.produce_finance_approval_operator_summary and
scripts.validate_finance_approval_operator_summary_schema.
Invariants:
  - The source summary must validate before HTML is emitted.
  - Rendered text is HTML-escaped.
  - The page contains no JavaScript and performs no live adapter action.
  - Secret values are never read or serialized.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.produce_finance_approval_operator_summary import DEFAULT_OUTPUT as DEFAULT_SUMMARY  # noqa: E402
from scripts.produce_finance_approval_operator_summary import DEFAULT_SCHEMA  # noqa: E402
from scripts.validate_finance_approval_operator_summary_schema import (  # noqa: E402
    validate_finance_approval_operator_summary_schema,
)

DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_operator_page.html"


@dataclass(frozen=True, slots=True)
class FinanceOperatorPageRender:
    """Result metadata for one finance operator page render."""

    ok: bool
    errors: tuple[str, ...]
    summary_path: str
    schema_path: str
    output_path: str
    packet_id: str
    packet_ready: bool
    chain_ready: bool
    readiness_blocker_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def render_finance_approval_operator_page(
    *,
    summary_path: Path = DEFAULT_SUMMARY,
    schema_path: Path = DEFAULT_SCHEMA,
    output_path: Path = DEFAULT_OUTPUT,
) -> tuple[str, FinanceOperatorPageRender]:
    """Return static HTML for a validated finance operator summary."""
    validation = validate_finance_approval_operator_summary_schema(
        summary_path=summary_path,
        schema_path=schema_path,
    )
    if not validation.ok:
        return "", _render_result(
            ok=False,
            errors=validation.errors,
            summary_path=summary_path,
            schema_path=schema_path,
            output_path=output_path,
            summary={},
        )

    summary = _load_json_object(summary_path)
    rendered_html = _render_html(summary)
    return rendered_html, _render_result(
        ok=True,
        errors=(),
        summary_path=summary_path,
        schema_path=schema_path,
        output_path=output_path,
        summary=summary,
    )


def write_finance_approval_operator_page(rendered_html: str, output_path: Path) -> Path:
    """Write one static finance operator HTML page."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered_html, encoding="utf-8")
    return output_path


def _render_html(summary: dict[str, Any]) -> str:
    status_class = "ready" if summary["packet_ready"] and summary["chain_ready"] else "blocked"
    status_label = "Ready" if status_class == "ready" else "Blocked"
    artifact_rows = "\n".join(
        _table_row(label, status) for label, status in sorted(summary["artifact_statuses"].items())
    )
    blockers = _list_items(summary["readiness_blockers"])
    next_actions = _list_items(summary["next_actions"])
    claim_boundaries = _list_items(summary["must_not_claim"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mullusi Finance Approval Operator Page</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1c2730;
      --muted: #5d6873;
      --line: #cfd7df;
      --panel: #f7f9fb;
      --ready: #176b3a;
      --blocked: #9f3328;
      --accent: #1f5f8b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #ffffff;
      color: var(--ink);
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.45;
    }}
    main {{
      width: min(1120px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0 40px;
    }}
    header {{
      border-bottom: 2px solid var(--line);
      margin-bottom: 22px;
      padding-bottom: 18px;
    }}
    h1, h2 {{
      margin: 0;
      letter-spacing: 0;
    }}
    h1 {{ font-size: 28px; }}
    h2 {{ font-size: 18px; margin-bottom: 10px; }}
    section {{
      border: 1px solid var(--line);
      margin-top: 16px;
      padding: 16px;
      background: var(--panel);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #ffffff;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ width: 28%; color: var(--muted); font-weight: 700; }}
    code {{
      display: block;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #ffffff;
      border: 1px solid var(--line);
      padding: 10px;
    }}
    ul {{ margin: 0; padding-left: 20px; }}
    li + li {{ margin-top: 6px; }}
    .status {{
      display: inline-block;
      margin-top: 8px;
      padding: 4px 8px;
      border: 1px solid currentColor;
      font-weight: 700;
    }}
    .ready {{ color: var(--ready); }}
    .blocked {{ color: var(--blocked); }}
    .meta {{ color: var(--muted); margin: 8px 0 0; }}
    .boundary {{ border-color: var(--blocked); }}
    .boundary h2 {{ color: var(--blocked); }}
    a {{ color: var(--accent); }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Mullusi Finance Approval Operator Page</h1>
      <p class="meta">Static read-only rendering of a validated redacted operator summary.</p>
      <span class="status {status_class}">{_escape(status_label)}</span>
    </header>
    <section>
      <h2>Packet And Chain Readiness</h2>
      <table>
        <tbody>
          {_table_row("Summary id", summary["summary_id"])}
          {_table_row("Checked at", summary["checked_at"])}
          {_table_row("Packet id", summary["packet_id"])}
          {_table_row("Packet status", summary["packet_status"])}
          {_table_row("Packet ok", _bool_text(summary["packet_ok"]))}
          {_table_row("Packet ready", _bool_text(summary["packet_ready"]))}
          {_table_row("Chain ok", _bool_text(summary["chain_ok"]))}
          {_table_row("Chain ready", _bool_text(summary["chain_ready"]))}
          {_table_row("Promotion mode", summary["promotion_mode"])}
        </tbody>
      </table>
    </section>
    <section>
      <h2>Strict Promotion Command</h2>
      <code>{_escape(summary["strict_promotion_command"])}</code>
    </section>
    <section>
      <h2>Readiness Blockers</h2>
      <ul>
        {blockers}
      </ul>
    </section>
    <section>
      <h2>Artifact Statuses</h2>
      <table>
        <tbody>
          {artifact_rows}
        </tbody>
      </table>
    </section>
    <section>
      <h2>Next Actions</h2>
      <ul>
        {next_actions}
      </ul>
    </section>
    <section class="boundary">
      <h2>Must Not Claim</h2>
      <ul>
        {claim_boundaries}
      </ul>
    </section>
  </main>
</body>
</html>
"""


def _render_result(
    *,
    ok: bool,
    errors: tuple[str, ...],
    summary_path: Path,
    schema_path: Path,
    output_path: Path,
    summary: dict[str, Any],
) -> FinanceOperatorPageRender:
    readiness_blockers = summary.get("readiness_blockers", [])
    return FinanceOperatorPageRender(
        ok=ok,
        errors=errors,
        summary_path=_path_label(summary_path),
        schema_path=_path_label(schema_path),
        output_path=_path_label(output_path),
        packet_id=str(summary.get("packet_id", "")),
        packet_ready=summary.get("packet_ready") is True,
        chain_ready=summary.get("chain_ready") is True,
        readiness_blocker_count=len(readiness_blockers) if isinstance(readiness_blockers, list) else 0,
    )


def _table_row(label: object, value: object) -> str:
    return f"<tr><th>{_escape(label)}</th><td>{_escape(value)}</td></tr>"


def _list_items(values: list[Any]) -> str:
    if not values:
        return "<li>none</li>"
    return "\n        ".join(f"<li>{_escape(value)}</li>" for value in values)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("finance operator summary root must be an object")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance operator page rendering arguments."""
    parser = argparse.ArgumentParser(description="Render the finance approval operator page.")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance operator page rendering."""
    args = parse_args(argv)
    output_path = Path(args.output)
    rendered_html, render = render_finance_approval_operator_page(
        summary_path=Path(args.summary),
        schema_path=Path(args.schema),
        output_path=output_path,
    )
    if render.ok:
        write_finance_approval_operator_page(rendered_html, output_path)
    if args.json:
        print(json.dumps(render.as_dict(), indent=2, sort_keys=True))
    elif render.ok:
        print(f"FINANCE OPERATOR PAGE RENDERED output={render.output_path}")
    else:
        print(f"FINANCE OPERATOR PAGE BLOCKED errors={list(render.errors)}")
    return 0 if render.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
