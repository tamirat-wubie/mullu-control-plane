"""Tests for gateway ingress rendering.

Purpose: verify deterministic gateway host substitution and optional apply.
Governance scope: [OCE, CDCV, UWMA, PRS]
Dependencies: scripts.render_gateway_ingress.
Invariants:
  - The source template is not edited in place.
  - Rendered output validates without placeholder allowance.
  - kubectl apply is opt-in and bounded to the rendered manifest.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.render_gateway_ingress import main, render_gateway_ingress
from scripts.validate_gateway_ingress_manifest import validate_gateway_ingress_manifest


class FakeRunner:
    """Deterministic kubectl runner fixture."""

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
        assert check is True
        assert capture_output is True
        assert text is True
        return subprocess.CompletedProcess(command, 0, stdout="applied", stderr="")


class FailingRunner(FakeRunner):
    """Runner that fails with untrusted kubectl output."""

    def __call__(
        self,
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        raise subprocess.CalledProcessError(
            returncode=9,
            cmd=command,
            output="stdout-secret-token",
            stderr="stderr-secret-token",
        )


def test_render_gateway_ingress_writes_valid_output(tmp_path: Path) -> None:
    source_path = tmp_path / "source.yaml"
    output_path = tmp_path / "rendered.yaml"
    source_path.write_text(_template(), encoding="utf-8")

    result = render_gateway_ingress(
        gateway_host="gateway.mullusi.com",
        source_path=source_path,
        output_path=output_path,
    )
    validation = validate_gateway_ingress_manifest(output_path)

    assert result.host == "gateway.mullusi.com"
    assert result.output_path == output_path
    assert result.applied is False
    assert validation.ok is True
    assert "gateway.example.com" in source_path.read_text(encoding="utf-8")
    assert "gateway.mullusi.com" in output_path.read_text(encoding="utf-8")


def test_render_gateway_ingress_rejects_placeholder_host(tmp_path: Path) -> None:
    source_path = tmp_path / "source.yaml"
    source_path.write_text(_template(), encoding="utf-8")

    with pytest.raises(RuntimeError, match="replace gateway.example.com"):
        render_gateway_ingress(
            gateway_host="gateway.example.com",
            source_path=source_path,
            output_path=tmp_path / "rendered.yaml",
        )


def test_render_gateway_ingress_rejects_url_with_scheme(tmp_path: Path) -> None:
    source_path = tmp_path / "source.yaml"
    source_path.write_text(_template(), encoding="utf-8")

    with pytest.raises(RuntimeError, match="must not include URL scheme"):
        render_gateway_ingress(
            gateway_host="https://gateway.mullusi.com",
            source_path=source_path,
            output_path=tmp_path / "rendered.yaml",
        )


def test_render_gateway_ingress_applies_rendered_manifest(tmp_path: Path) -> None:
    source_path = tmp_path / "source.yaml"
    output_path = tmp_path / "rendered.yaml"
    source_path.write_text(_template(), encoding="utf-8")
    runner = FakeRunner()

    result = render_gateway_ingress(
        gateway_host="gateway.mullusi.com",
        source_path=source_path,
        output_path=output_path,
        apply=True,
        runner=runner,
    )

    assert result.applied is True
    assert runner.commands == [["kubectl", "apply", "-f", str(output_path)]]


def test_render_gateway_ingress_apply_failure_is_bounded(tmp_path: Path) -> None:
    source_path = tmp_path / "source.yaml"
    output_path = tmp_path / "rendered-private-path.yaml"
    source_path.write_text(_template(), encoding="utf-8")
    runner = FailingRunner()

    with pytest.raises(RuntimeError) as exc_info:
        render_gateway_ingress(
            gateway_host="gateway.mullusi.com",
            source_path=source_path,
            output_path=output_path,
            apply=True,
            runner=runner,
        )

    message = str(exc_info.value)
    assert message == "kubectl apply failed: exit_code=9"
    assert "stdout-secret-token" not in message
    assert "stderr-secret-token" not in message
    assert "rendered-private-path" not in message
    assert runner.commands == [["kubectl", "apply", "-f", str(output_path)]]


def test_cli_reports_missing_host(capsys) -> None:
    exit_code = main(["--gateway-host", ""])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "gateway ingress render failed" in captured.out
    assert "fully qualified" in captured.out or "invalid DNS" in captured.out


def _template() -> str:
    return """apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mullu-gateway
  namespace: mullu
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
    - hosts:
        - gateway.example.com
      secretName: mullu-gateway-tls
  rules:
    - host: gateway.example.com
      http:
        paths:
          - path: /health
            pathType: Exact
            backend:
              service:
                name: mullu-gateway
                port:
                  number: 80
          - path: /gateway/witness
            pathType: Exact
            backend:
              service:
                name: mullu-gateway
                port:
                  number: 80
"""
