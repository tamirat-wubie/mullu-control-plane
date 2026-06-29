#!/usr/bin/env python3
"""Validate the public CI window operator command packet fixture.

Purpose: bind the no-execute public CI window command generator to a committed
example packet and detect schema, command, and manual-boundary drift.
Governance scope: Foundation Mode source-control visibility, public CI command
packets, operator execution boundary, secret exposure prevention, and
public-readiness separation.
Dependencies: examples/foundation_public_ci_window_operator_commands.example.json
and scripts.generate_public_ci_window_operator_commands.
Invariants:
  - Validation is read-only.
  - The fixture is a no-execute packet.
  - Live visibility commands require manual operator execution.
  - Fixture drift is reported without echoing raw secret-shaped text.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_public_ci_window_operator_commands import (  # noqa: E402
    BLOCKED_CLAIMS,
    EXPECTED_REPO,
    GENERATOR_ID,
    SECRET_SHAPED_FRAGMENTS,
    build_public_ci_window_operator_packet,
)


DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_public_ci_window_operator_commands.example.json"
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "branch",
    "commands",
    "generator_id",
    "head_sha",
    "no_execute",
    "pull_request",
    "receipt_path",
    "repo",
    "solver_outcome",
    "status",
    "window_id",
}
EXPECTED_COMMAND_KEYS = {
    "command",
    "live_effect_possible",
    "operator_execution_required",
    "phase",
    "purpose",
    "step_id",
}
EXPECTED_STEP_IDS = (
    "01_preflight_public_surface",
    "02_preflight_proprietary_boundary",
    "03_preflight_release_status",
    "04_open_visibility_manual",
    "05_observe_pr_checks",
    "06_observe_ci_health",
    "07_close_visibility_manual",
    "08_verify_private_surface",
)
EXPECTED_MANUAL_STEP_IDS = {
    "04_open_visibility_manual",
    "07_close_visibility_manual",
}


@dataclass(frozen=True)
class Finding:
    """A deterministic finding for the operator command packet validator."""

    rule_id: str
    message: str


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit path and type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return payload


def _contains_secret_shaped_text(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True).casefold()
    return any(fragment in text for fragment in SECRET_SHAPED_FRAGMENTS)


def _is_hex_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(char in "0123456789abcdef" for char in value)


def _pull_request_number(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    prefix = f"https://github.com/{EXPECTED_REPO}/pull/"
    if not value.startswith(prefix):
        return None
    pr_number = value.removeprefix(prefix)
    if not pr_number.isdigit():
        return None
    return pr_number


def _window_date_token(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"foundation_public_ci_window\.([0-9]{8})\.pr[0-9]+", value)
    if match is None:
        return None
    return match.group(1)


def _observed_at_from_window_id(window_id: Any) -> datetime | None:
    date_token = _window_date_token(window_id)
    if date_token is None:
        return None
    try:
        return datetime.strptime(date_token, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _expected_packet_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    observed_at = _observed_at_from_window_id(payload.get("window_id"))
    pr_number = _pull_request_number(payload.get("pull_request"))
    branch = payload.get("branch")
    head_sha = payload.get("head_sha")
    if observed_at is None or pr_number is None or not isinstance(branch, str) or not _is_hex_sha(head_sha):
        return None
    try:
        return build_public_ci_window_operator_packet(
            pull_request=pr_number,
            branch=branch,
            head_sha=head_sha,
            observed_at=observed_at,
            repo=EXPECTED_REPO,
        )
    except ValueError:
        return None


def validate_operator_command_packet(payload: dict[str, Any]) -> list[Finding]:
    """Validate a no-execute public CI window operator command packet."""

    findings: list[Finding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            Finding(
                "public_ci_window_operator_command_packet_root_keys_invalid",
                "root keys must match the public CI operator command packet contract",
            )
        )

    expected_values: dict[str, object] = {
        "generator_id": GENERATOR_ID,
        "repo": EXPECTED_REPO,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "no_execute": True,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                Finding("public_ci_window_operator_command_packet_value_invalid", f"{key} must equal {expected_value!r}")
            )

    pr_number = _pull_request_number(payload.get("pull_request"))
    if pr_number is None:
        findings.append(
            Finding(
                "public_ci_window_operator_command_packet_pull_request_invalid",
                "pull_request must be an exact repository pull request URL",
            )
        )
    elif payload.get("receipt_path") != f".change_assurance/public-ci-window-{pr_number}-receipt.json":
        findings.append(
            Finding(
                "public_ci_window_operator_command_packet_receipt_path_invalid",
                "receipt_path must bind to the pull request identity",
            )
        )

    window_id = payload.get("window_id")
    if pr_number is not None and window_id != f"foundation_public_ci_window.{_window_date_token(window_id)}.pr{pr_number}":
        findings.append(
            Finding(
                "public_ci_window_operator_command_packet_window_id_invalid",
                "window_id must bind a valid UTC date token and pull request identity",
            )
        )
    if _observed_at_from_window_id(window_id) is None:
        findings.append(
            Finding(
                "public_ci_window_operator_command_packet_window_date_invalid",
                "window_id must contain a valid YYYYMMDD UTC date token",
            )
        )

    if not isinstance(payload.get("branch"), str) or not payload["branch"].strip():
        findings.append(
            Finding("public_ci_window_operator_command_packet_branch_invalid", "branch must be a non-empty string")
        )
    if not _is_hex_sha(payload.get("head_sha")):
        findings.append(
            Finding(
                "public_ci_window_operator_command_packet_head_sha_invalid",
                "head_sha must be a 40-character lowercase hex SHA",
            )
        )
    if tuple(payload.get("blocked_claims") or ()) != BLOCKED_CLAIMS:
        findings.append(
            Finding(
                "public_ci_window_operator_command_packet_blocked_claims_invalid",
                "blocked_claims must preserve the Foundation Mode public-readiness denials",
            )
        )

    commands = payload.get("commands")
    if not isinstance(commands, list) or not all(isinstance(command, dict) for command in commands):
        findings.append(
            Finding(
                "public_ci_window_operator_command_packet_commands_invalid",
                "commands must be a list of command objects",
            )
        )
    else:
        if len(commands) != len(EXPECTED_STEP_IDS):
            findings.append(
                Finding(
                    "public_ci_window_operator_command_packet_command_count_invalid",
                    "commands must contain exactly eight ordered steps",
                )
            )
        for command in commands:
            if set(command) != EXPECTED_COMMAND_KEYS:
                findings.append(
                    Finding(
                        "public_ci_window_operator_command_packet_command_keys_invalid",
                        "command entries must contain only the expected command fields",
                    )
                )
        observed_step_ids = tuple(command.get("step_id") for command in commands)
        if observed_step_ids != EXPECTED_STEP_IDS:
            findings.append(
                Finding(
                    "public_ci_window_operator_command_packet_step_order_invalid",
                    "command step IDs must remain ordered and complete",
                )
            )
        manual_commands = [command for command in commands if command.get("live_effect_possible") is True]
        if {command.get("step_id") for command in manual_commands} != EXPECTED_MANUAL_STEP_IDS:
            findings.append(
                Finding(
                    "public_ci_window_operator_command_packet_manual_steps_invalid",
                    "only visibility open and close commands may be marked live-effecting",
                )
            )
        if any(command.get("operator_execution_required") is not True for command in manual_commands):
            findings.append(
                Finding(
                    "public_ci_window_operator_command_packet_manual_boundary_invalid",
                    "live-effecting visibility commands must require operator execution",
                )
            )
        if any(
            command.get("live_effect_possible") is not True
            and command.get("operator_execution_required") is not False
            for command in commands
        ):
            findings.append(
                Finding(
                    "public_ci_window_operator_command_packet_non_live_boundary_invalid",
                    "non-live commands must not require operator execution",
                )
            )

    if _contains_secret_shaped_text(payload):
        findings.append(
            Finding(
                "public_ci_window_operator_command_packet_secret_shaped_text_present",
                "packet must not contain raw secret-shaped text",
            )
        )

    expected_packet = _expected_packet_from_payload(payload)
    if expected_packet is None:
        findings.append(
            Finding(
                "public_ci_window_operator_command_packet_reference_invalid",
                "packet identity fields could not regenerate the reference command packet",
            )
        )
    elif payload != expected_packet:
        findings.append(
            Finding(
                "public_ci_window_operator_command_packet_drift",
                "packet must match the generator output for its pinned pull request, branch, SHA, and date",
            )
        )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate public CI window operator command packet fixture.")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH, help="Path to command packet JSON.")
    args = parser.parse_args(argv)

    try:
        payload = load_json_object(args.packet, "public CI window operator command packet")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] public_ci_window_operator_command_packet_load: {exc}")
        print("STATUS: failed")
        return 1

    findings = validate_operator_command_packet(payload)
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}")
        print("STATUS: failed")
        return 1

    print("[PASS] public_ci_window_operator_command_packet")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
