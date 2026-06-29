"""Tests for the public CI window operator command packet validator.

Purpose: prove the committed no-execute command packet fixture remains bound
to generator output, manual visibility execution, and secret-safe diagnostics.
Governance scope: Foundation Mode public CI windows, operator command packet
drift, visibility mutation boundary, and public-readiness separation.
Dependencies: scripts.validate_public_ci_window_operator_command_packet.
Invariants: validation is read-only; live visibility commands require manual
operator execution; raw secret-shaped values are not echoed in findings.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_public_ci_window_operator_command_packet import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    load_json_object,
    main,
    validate_operator_command_packet,
)


def _packet() -> dict[str, object]:
    return load_json_object(DEFAULT_PACKET_PATH, "public CI window operator command packet")


def test_public_ci_window_operator_command_packet_fixture_passes() -> None:
    packet = _packet()
    findings = validate_operator_command_packet(packet)

    assert findings == []
    assert packet["no_execute"] is True
    assert packet["window_id"] == "foundation_public_ci_window.20260628.pr2380"
    assert len(packet["commands"]) == 8


def test_public_ci_window_operator_command_packet_cli_passes(capsys) -> None:
    exit_code = main([])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert "[PASS] public_ci_window_operator_command_packet" in streams.out
    assert "STATUS: passed" in streams.out
    assert streams.err == ""


def test_public_ci_window_operator_command_packet_rejects_fixture_drift() -> None:
    packet = _packet()
    packet["commands"][3]["purpose"] = "Manual visibility command without bounded CI purpose."

    findings = validate_operator_command_packet(packet)

    assert findings
    assert any(finding.rule_id == "public_ci_window_operator_command_packet_drift" for finding in findings)
    assert all("bounded CI purpose" not in finding.message for finding in findings)


def test_public_ci_window_operator_command_packet_rejects_extra_command_field() -> None:
    packet = _packet()
    packet["commands"][0]["raw_output"] = "private validator detail"

    findings = validate_operator_command_packet(packet)

    assert findings
    assert any(finding.rule_id == "public_ci_window_operator_command_packet_command_keys_invalid" for finding in findings)
    assert any(finding.rule_id == "public_ci_window_operator_command_packet_drift" for finding in findings)
    assert all("private validator detail" not in finding.message for finding in findings)


def test_public_ci_window_operator_command_packet_rejects_live_command_without_manual_gate() -> None:
    packet = _packet()
    packet["commands"][3]["operator_execution_required"] = False

    findings = validate_operator_command_packet(packet)

    assert findings
    assert any(
        finding.rule_id == "public_ci_window_operator_command_packet_manual_boundary_invalid"
        for finding in findings
    )
    assert any(finding.rule_id == "public_ci_window_operator_command_packet_drift" for finding in findings)


def test_public_ci_window_operator_command_packet_rejects_non_live_manual_gate() -> None:
    packet = _packet()
    packet["commands"][0]["operator_execution_required"] = True

    findings = validate_operator_command_packet(packet)

    assert findings
    assert any(
        finding.rule_id == "public_ci_window_operator_command_packet_non_live_boundary_invalid"
        for finding in findings
    )
    assert any(finding.rule_id == "public_ci_window_operator_command_packet_drift" for finding in findings)


def test_public_ci_window_operator_command_packet_rejects_secret_shaped_text() -> None:
    packet = _packet()
    packet["branch"] = "codex/client_secret-branch"

    findings = validate_operator_command_packet(packet)

    assert findings
    assert any(
        finding.rule_id == "public_ci_window_operator_command_packet_secret_shaped_text_present"
        for finding in findings
    )
    assert all("client_secret-branch" not in finding.message for finding in findings)


def test_public_ci_window_operator_command_packet_rejects_bad_window_date() -> None:
    packet = _packet()
    packet["window_id"] = "foundation_public_ci_window.20261340.pr2380"

    findings = validate_operator_command_packet(packet)

    assert findings
    assert any(finding.rule_id == "public_ci_window_operator_command_packet_window_date_invalid" for finding in findings)
    assert any(finding.rule_id == "public_ci_window_operator_command_packet_reference_invalid" for finding in findings)
    assert all("20261340" not in finding.message for finding in findings)


def test_public_ci_window_operator_command_packet_validation_has_no_side_effects() -> None:
    packet = _packet()
    before = copy.deepcopy(packet)

    findings = validate_operator_command_packet(packet)

    assert findings == []
    assert packet == before
    assert DEFAULT_PACKET_PATH.exists()
