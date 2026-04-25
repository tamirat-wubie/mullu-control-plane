"""Tests for gateway ingress publication validation.

Purpose: verify public gateway ingress evidence requirements before DNS
publication is claimed.
Governance scope: [OCE, CDCV, UWMA, PRS]
Dependencies: scripts.validate_gateway_ingress_manifest.
Invariants:
  - Placeholder hosts fail closed unless explicitly allowed by CLI.
  - Health and runtime witness paths must route to mullu-gateway.
  - Valid hosts pass when required witness routes are present.
"""

from __future__ import annotations

from pathlib import Path

from scripts.validate_gateway_ingress_manifest import (
    main,
    validate_gateway_ingress_manifest,
)


def test_validate_gateway_ingress_manifest_rejects_placeholder_host() -> None:
    result = validate_gateway_ingress_manifest()

    assert result.ok is False
    assert result.host == "gateway.example.com"
    assert any("gateway.example.com" in error for error in result.errors)


def test_validate_gateway_ingress_manifest_accepts_concrete_host(tmp_path: Path) -> None:
    manifest_path = tmp_path / "ingress.yaml"
    manifest_path.write_text(
        _manifest("gateway.mullusi.com"),
        encoding="utf-8",
    )

    result = validate_gateway_ingress_manifest(manifest_path)

    assert result.ok is True
    assert result.host == "gateway.mullusi.com"
    assert result.errors == ()


def test_validate_gateway_ingress_manifest_requires_witness_route(tmp_path: Path) -> None:
    manifest_path = tmp_path / "ingress.yaml"
    manifest_path.write_text(
        _manifest("gateway.mullusi.com").replace(
            "          - path: /gateway/witness\n",
            "          - path: /not-witness\n",
        ),
        encoding="utf-8",
    )

    result = validate_gateway_ingress_manifest(manifest_path)

    assert result.ok is False
    assert "missing ingress route for /gateway/witness" in result.errors
    assert result.host == "gateway.mullusi.com"


def test_cli_allows_placeholder_for_repository_validation(capsys) -> None:
    exit_code = main(["--allow-placeholder"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "gateway ingress manifest ok" in captured.out
    assert "gateway.example.com" in captured.out


def _manifest(host: str) -> str:
    return f"""apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mullu-gateway
  namespace: mullu
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
    - hosts:
        - {host}
      secretName: mullu-gateway-tls
  rules:
    - host: {host}
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
