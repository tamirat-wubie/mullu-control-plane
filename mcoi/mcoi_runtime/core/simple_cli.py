"""CLI front door for simple governed platform actions.

Purpose: provide a small, readable command surface for users who only need to
check whether a task is ready, needs review, or is blocked.
Governance scope: command-line usability projection only; checks execute
through SimplePlatform and the MVK governance gate.
Dependencies: argparse, json, and simple platform facade.
Invariants: every command returns a governed outcome and failures are reported
with explicit causal context.
"""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .invariants import RuntimeCoreInvariantError
from .simple_platform import SimpleActionRequest, SimplePlatform


def build_parser() -> argparse.ArgumentParser:
    """Build the simple platform parser."""

    parser = argparse.ArgumentParser(
        prog="mullu",
        description="Simple governed platform actions",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Check a task before continuing")
    check_parser.add_argument("--goal", required=True, help="What the user wants to accomplish")
    check_parser.add_argument(
        "--action",
        required=True,
        choices=("view", "change", "send", "verify"),
        help="Plain action type",
    )
    check_parser.add_argument("--target", required=True, help="File, message, or artifact target")
    check_parser.add_argument("--allowed-area", required=True, help="Area the task is allowed to touch")
    check_parser.add_argument("--actor-id", default="local-user", help="User or surface checking the task")
    check_parser.add_argument("--json", action="store_true", help="Emit JSON instead of readable text")

    subparsers.add_parser("start", help="Show the simple platform task menu")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one simple platform command."""

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "start":
        print(_start_text())
        return 0
    if args.command == "check":
        check = SimplePlatform().check_action(
            SimpleActionRequest(
                goal=args.goal,
                action=args.action,
                target=args.target,
                allowed_area=args.allowed_area,
                actor_id=args.actor_id,
            )
        )
        if args.json:
            print(
                json.dumps(
                    _envelope(check.ok_to_continue, check.outcome, check.to_dict()),
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        else:
            print(_readable_check(check.to_dict()))
        return 0 if check.outcome == "ready" else 2
    parser.error(f"unknown command: {args.command}")
    return 1


def guarded_main(argv: Sequence[str] | None = None) -> int:
    """Run main while converting failures into governed output."""

    try:
        return main(argv)
    except (RuntimeCoreInvariantError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps(_envelope(False, "rejected", {}, error=str(exc)), sort_keys=True, separators=(",", ":")))
        return 1


def _readable_check(value: dict[str, object]) -> str:
    lines = [
        f"Outcome: {value['title']}",
        f"Message: {value['message']}",
        f"Next: {value['next_step']}",
        f"Proof: {value['proof_stamp_ref']}",
    ]
    blocked = value.get("blocked_reasons")
    review = value.get("review_reasons")
    if isinstance(blocked, list) and blocked:
        lines.append("Blocked reasons:")
        lines.extend(f"- {item}" for item in blocked)
    if isinstance(review, list) and review:
        lines.append("Review reasons:")
        lines.extend(f"- {item}" for item in review)
    return "\n".join(lines)


def _start_text() -> str:
    return "\n".join(
        (
            "Mullu simple mode",
            "Use one command before a task:",
            "mullu check --goal \"Review docs\" --action view --target docs/README.md --allowed-area docs/**",
            "Actions: view, change, send, verify",
            "Outcomes: Ready, Needs review, Blocked",
        )
    )


def _envelope(ok: bool, status: str, payload: dict[str, object], *, error: str = "") -> dict[str, object]:
    return {
        "governed": True,
        "ok": ok,
        "status": status,
        "payload": payload,
        "error": error,
    }


if __name__ == "__main__":
    raise SystemExit(guarded_main())
