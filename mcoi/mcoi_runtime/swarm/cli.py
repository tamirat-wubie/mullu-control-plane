"""CLI adapter for governed swarm runtime operations.

Purpose: expose invoice swarm run, lookup, and listing commands over JSON input
and JSON response envelopes.
Governance scope: command-line boundary only; validation, persistence, proof,
and rejection semantics remain owned by InvoiceSwarmRuntime.
Dependencies: argparse, json, pathlib, and runtime API.
Invariants: commands do not bypass runtime validation and rejected runs return
nonzero exit status.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .runtime_api import InvoiceSwarmRuntime, RuntimeEnvelope


def build_parser() -> argparse.ArgumentParser:
    """Build the governed swarm CLI parser."""

    parser = argparse.ArgumentParser(prog="mcoi-swarm", description="Governed swarm runtime commands")
    parser.add_argument("--audit-store", required=True, help="Path to append-only swarm audit JSONL store")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run-invoice", help="Run a governed invoice swarm request")
    run_parser.add_argument("request", help="Inline JSON request or path to a JSON request file")

    get_parser = subparsers.add_parser("get-run", help="Read one persisted swarm run")
    get_parser.add_argument("run_id", help="Persisted swarm run identifier")

    subparsers.add_parser("list-runs", help="List persisted swarm runs")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and print one JSON response envelope."""

    parser = build_parser()
    args = parser.parse_args(argv)
    runtime = InvoiceSwarmRuntime.from_path(args.audit_store)
    if args.command == "run-invoice":
        envelope = runtime.run_invoice(_load_json_request(args.request))
    elif args.command == "get-run":
        envelope = runtime.get_run(args.run_id)
    elif args.command == "list-runs":
        envelope = runtime.list_runs()
    else:
        parser.error(f"unknown command: {args.command}")
    print(json.dumps(envelope.to_dict(), sort_keys=True, separators=(",", ":")))
    return 0 if envelope.ok else 1


def _load_json_request(value: str) -> dict[str, Any]:
    """Load an inline JSON object or a JSON object from disk."""

    stripped = value.strip()
    if stripped.startswith("{"):
        raw = stripped
    else:
        candidate = Path(value)
        raw = candidate.read_text(encoding="utf-8") if candidate.exists() else value
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("request JSON must be an object")
    return parsed


def _envelope_from_exception(exc: Exception) -> RuntimeEnvelope:
    """Build a governed rejection envelope for CLI parsing failures."""

    return RuntimeEnvelope(
        governed=True,
        ok=False,
        status="rejected",
        payload={},
        error=str(exc),
    )


def guarded_main(argv: Sequence[str] | None = None) -> int:
    """Run main while converting parser-adjacent errors into governed JSON."""

    try:
        return main(argv)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        envelope = _envelope_from_exception(exc)
        print(json.dumps(envelope.to_dict(), sort_keys=True, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(guarded_main())
