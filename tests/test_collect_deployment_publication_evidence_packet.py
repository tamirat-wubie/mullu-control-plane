"""Tests for deployment publication evidence packet collection.

Purpose: prove deployment publication evidence can be collected into one
non-effecting packet.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.collect_deployment_publication_evidence_packet.
Invariants:
  - Packet collection does not dispatch workflows or mutate DNS.
  - Not-ready upstream, DNS target, and DNS resolution gates remain explicit.
  - CLI failure output is bounded and does not leak host-local paths.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_deployment_publication_evidence_packet import (  # noqa: E402
    collect_deployment_publication_evidence_packet,
    main,
)


class FakeRunner:
    """Fake GitHub CLI metadata runner."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(
        self,
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        if command[:3] == ["gh", "variable", "list"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    [
                        {"name": "MULLU_GATEWAY_URL", "value": "https://api.mullusi.com"},
                        {"name": "MULLU_EXPECTED_RUNTIME_ENV", "value": "pilot"},
                    ]
                ),
                stderr="",
            )
        if command[:3] == ["gh", "secret", "list"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    [
                        {"name": "MULLU_RUNTIME_WITNESS_SECRET"},
                        {"name": "MULLU_RUNTIME_CONFORMANCE_SECRET"},
                        {"name": "MULLU_DEPLOYMENT_WITNESS_SECRET"},
                    ]
                ),
                stderr="",
            )
        if command[:3] == ["gh", "workflow", "list"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    [
                        {
                            "name": "Gateway Publication",
                            "path": ".github/workflows/gateway-publication.yml",
                            "state": "active",
                        }
                    ]
                ),
                stderr="",
            )
        raise AssertionError(f"unexpected command: {command}")


def test_collect_deployment_publication_evidence_packet_writes_not_ready_bundle(
    tmp_path: Path,
) -> None:
    upstream_report = tmp_path / "upstream_api_readiness.json"
    upstream_report.write_text(
        json.dumps(
            {
                "apiProductionReadinessState": "Blocked",
                "solverOutcome": "AwaitingEvidence",
                "apiProvisioningAllowed": False,
                "apiDnsPublicationAllowed": False,
                "blockers": ["recovery_witness_not_ready"],
            }
        ),
        encoding="utf-8",
    )
    runner = FakeRunner()

    packet = collect_deployment_publication_evidence_packet(
        output_dir=tmp_path / "packet",
        gateway_url="https://api.mullusi.com",
        expected_environment="pilot",
        upstream_readiness_report=upstream_report,
        dispatch_witness=True,
        runner=runner,
        publication_resolver=lambda _host: (),
        dns_resolver=_unresolved_dns,
    )
    packet_path = tmp_path / "packet" / "deployment_publication_evidence_packet.json"
    packet_validation_path = (
        tmp_path / "packet" / "deployment_publication_evidence_packet_validation.json"
    )
    closure_plan_path = tmp_path / "packet" / "deployment_publication_closure_plan.json"
    dispatch_plan_path = tmp_path / "packet" / "gateway_publication_dispatch_plan.json"
    upstream_validation_path = (
        tmp_path / "packet" / "deployment_upstream_blocker_receipt_validation.json"
    )

    assert packet.ready is False
    assert packet.gateway_host == "api.mullusi.com"
    assert packet.blockers == (
        "deployment_dns_not_verified",
        "deployment_upstream_api_gate_not_ready",
    )
    assert packet.validation_status["deployment_publication_closure_plan_schema"] is True
    assert packet.validation_status["deployment_upstream_blocker"] is False
    assert packet.validation_status["gateway_dns_target_binding"] is False
    assert packet.validation_status["gateway_dns_resolution"] is False
    assert packet_path.exists()
    assert packet_validation_path.exists()
    assert closure_plan_path.exists()
    assert dispatch_plan_path.exists()
    assert upstream_validation_path.exists()
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)

    summary = json.loads(packet_path.read_text(encoding="utf-8"))
    packet_validation = json.loads(packet_validation_path.read_text(encoding="utf-8"))
    closure_plan = json.loads(closure_plan_path.read_text(encoding="utf-8"))
    dispatch_plan = json.loads(dispatch_plan_path.read_text(encoding="utf-8"))
    upstream_validation = json.loads(upstream_validation_path.read_text(encoding="utf-8"))

    assert summary["packet_id"].startswith("deployment-publication-evidence-packet-")
    assert summary["ready"] is False
    assert "deployment_publication_closure_plan" in summary["artifacts"]
    assert "deployment_publication_evidence_packet_validation" in summary["artifacts"]
    assert packet_validation["valid"] is True
    assert packet_validation["ready"] is False
    assert "recovery_witness_not_ready" in (
        tmp_path / "packet" / "deployment_upstream_blocker_receipt.json"
    ).read_text(encoding="utf-8")
    assert closure_plan["action_count"] == 2
    assert closure_plan["plan_id"].startswith("deployment-publication-closure-plan-")
    assert "--upstream-readiness-report" in closure_plan["actions"][1]["command"]
    assert dispatch_plan["dispatch_witness"] is True
    assert "dispatch_witness=true" in dispatch_plan["dispatch_command"]
    assert upstream_validation["ready"] is False
    assert upstream_validation["valid"] is False
    assert "require ready: not-ready" in upstream_validation["errors"]


def test_collect_deployment_publication_evidence_packet_cli_bounds_invalid_url(
    tmp_path: Path,
    capsys,
) -> None:
    exit_code = main(
        [
            "--output-dir",
            str(tmp_path / "packet"),
            "--gateway-url",
            "http://api.mullusi.com",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["packet_written"] is False
    assert payload["ready"] is False
    assert payload["error"] == "gateway URL must include https scheme and host"
    assert str(tmp_path) not in captured.out
    assert captured.err == ""


def _unresolved_dns(_host: str) -> tuple[tuple[int, str], ...]:
    raise OSError("bounded resolver failure")
