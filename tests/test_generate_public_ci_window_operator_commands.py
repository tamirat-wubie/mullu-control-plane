"""Tests for the public CI window operator command generator.

Purpose: prove generated command packets are local-only, explicit about live
effects, and bounded to Foundation Mode public CI windows.
Governance scope: source-control visibility, operator execution boundary,
public-readiness separation, and secret exposure prevention.
Dependencies: scripts.generate_public_ci_window_operator_commands.
Invariants: commands are generated but never executed; visibility mutation
commands require operator execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_public_ci_window_operator_commands import (  # noqa: E402
    build_public_ci_window_operator_packet,
    main,
)


def _packet() -> dict[str, object]:
    return build_public_ci_window_operator_packet(
        pull_request="2380",
        branch="codex/public-ci-window-visibility-restoration-20260628",
        head_sha="331adc8c851b48a754643a9ac33c706c9365071c",
        observed_at=datetime(2026, 6, 28, 18, 14, 48, tzinfo=timezone.utc),
    )


def test_public_ci_window_command_packet_is_no_execute() -> None:
    packet = _packet()
    commands = packet["commands"]

    assert packet["no_execute"] is True
    assert packet["status"] == "AwaitingEvidence"
    assert packet["window_id"] == "foundation_public_ci_window.20260628.pr2380"
    assert isinstance(commands, list)
    assert len(commands) == 8


def test_public_ci_window_command_packet_marks_visibility_mutations_manual() -> None:
    packet = _packet()
    commands = packet["commands"]
    live_commands = [command for command in commands if command["live_effect_possible"]]

    assert len(live_commands) == 2
    assert all(command["operator_execution_required"] is True for command in live_commands)
    assert live_commands[0]["command"] == "gh repo edit tamirat-wubie/mullu-control-plane --visibility public"
    assert live_commands[1]["command"] == "gh repo edit tamirat-wubie/mullu-control-plane --visibility private"


def test_public_ci_window_command_packet_preserves_boundary_commands() -> None:
    packet = _packet()
    command_text = "\n".join(command["command"] for command in packet["commands"])

    assert "python scripts/validate_public_repository_surface.py --local-only" in command_text
    assert "python scripts/validate_proprietary_boundary.py" in command_text
    assert "python scripts/validate_release_status.py" in command_text
    assert "gh pr checks 2380" in command_text
    assert "production deployment" in packet["blocked_claims"]


def test_public_ci_window_command_packet_rejects_secret_shaped_input() -> None:
    try:
        build_public_ci_window_operator_packet(
            pull_request="2380",
            branch="codex/client_secret-branch",
            head_sha="331adc8c851b48a754643a9ac33c706c9365071c",
            observed_at=datetime(2026, 6, 28, 18, 14, 48, tzinfo=timezone.utc),
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "inputs must not contain raw secret-shaped text"
    assert "client_secret-branch" not in message
    assert "331adc8c851b48a754643a9ac33c706c9365071c" not in message


def test_public_ci_window_command_packet_rejects_invalid_head_sha() -> None:
    try:
        build_public_ci_window_operator_packet(
            pull_request="2380",
            branch="codex/public-ci-window-visibility-restoration-20260628",
            head_sha="not-a-sha",
            observed_at=datetime(2026, 6, 28, 18, 14, 48, tzinfo=timezone.utc),
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "head_sha must be a 40-character lowercase hex SHA"
    assert "not-a-sha" not in message
    assert "public-ci-window-visibility" not in message


def test_public_ci_window_command_generator_cli_passes(capsys) -> None:
    exit_code = main(
        [
            "--pull-request",
            "2380",
            "--branch",
            "codex/public-ci-window-visibility-restoration-20260628",
            "--head-sha",
            "331adc8c851b48a754643a9ac33c706c9365071c",
        ]
    )
    streams = capsys.readouterr()
    payload_text, status_text = streams.out.rsplit("\nSTATUS: passed", 1)
    packet = json.loads(payload_text)

    assert exit_code == 0
    assert status_text.strip() == ""
    assert packet["no_execute"] is True
    assert packet["pull_request"].endswith("/2380")
    assert streams.err == ""
