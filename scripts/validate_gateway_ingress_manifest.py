#!/usr/bin/env python3
"""Validate the gateway ingress publication manifest.

Purpose: ensure the Kubernetes gateway ingress explicitly publishes the health
and runtime witness paths needed for deployment evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: k8s/mullu-gateway-ingress.yaml.
Invariants:
  - The ingress manifest must exist before public gateway readiness is claimed.
  - The host must be explicit and must not remain the example placeholder.
  - /health and /gateway/witness must route to the mullu-gateway service.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MANIFEST = Path("k8s") / "mullu-gateway-ingress.yaml"
PLACEHOLDER_HOSTS = {"gateway.example.com", "example.com"}
REQUIRED_PATHS = ("/health", "/gateway/witness")


@dataclass(frozen=True, slots=True)
class GatewayIngressValidation:
    """Validation result for one gateway ingress manifest."""

    manifest_path: Path
    host: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Return whether the ingress manifest satisfies hard checks."""
        return not self.errors


def validate_gateway_ingress_manifest(
    manifest_path: Path = DEFAULT_MANIFEST,
) -> GatewayIngressValidation:
    """Validate one gateway ingress manifest using a bounded text contract."""
    errors: list[str] = []
    warnings: list[str] = []
    if not manifest_path.exists():
        return GatewayIngressValidation(
            manifest_path=manifest_path,
            host="",
            errors=(f"missing gateway ingress manifest: {manifest_path}",),
            warnings=(),
        )

    manifest_text = manifest_path.read_text(encoding="utf-8")
    _require_literal(manifest_text, "kind: Ingress", "manifest kind must be Ingress", errors)
    _require_literal(manifest_text, "name: mullu-gateway", "ingress name must be mullu-gateway", errors)
    _require_literal(manifest_text, "secretName: mullu-gateway-tls", "TLS secret must be declared", errors)

    host = _extract_first_host(manifest_text)
    if not host:
        errors.append("ingress host is required")
    elif host in PLACEHOLDER_HOSTS:
        errors.append("ingress host must replace gateway.example.com before publication")
    elif "." not in host:
        errors.append("ingress host must be a fully qualified DNS name")

    for required_path in REQUIRED_PATHS:
        if f"path: {required_path}" not in manifest_text:
            errors.append(f"missing ingress route for {required_path}")
        path_block = _extract_path_block(manifest_text, required_path)
        if path_block and "name: mullu-gateway" not in path_block:
            errors.append(f"{required_path} must route to service mullu-gateway")
        if path_block and "number: 80" not in path_block:
            errors.append(f"{required_path} must route to service port 80")

    if "nginx.ingress.kubernetes.io/ssl-redirect: \"true\"" not in manifest_text:
        warnings.append("ingress should force TLS redirect")

    return GatewayIngressValidation(
        manifest_path=manifest_path,
        host=host,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _require_literal(
    text: str,
    literal: str,
    message: str,
    errors: list[str],
) -> None:
    if literal not in text:
        errors.append(message)


def _extract_first_host(manifest_text: str) -> str:
    match = re.search(r"^\s*-\s*host:\s*([^\s#]+)\s*$", manifest_text, re.MULTILINE)
    if match:
        return match.group(1).strip().strip('"').strip("'")
    match = re.search(r"^\s*-\s*([A-Za-z0-9.-]+\.[A-Za-z0-9.-]+)\s*$", manifest_text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_path_block(manifest_text: str, path: str) -> str:
    marker = f"path: {path}"
    start = manifest_text.find(marker)
    if start < 0:
        return ""
    next_path = manifest_text.find("\n          - path: ", start + len(marker))
    end = next_path if next_path >= 0 else len(manifest_text)
    return manifest_text[start:end]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse gateway ingress validation CLI arguments."""
    parser = argparse.ArgumentParser(description="Validate Mullu gateway ingress publication.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--allow-placeholder", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for gateway ingress manifest validation."""
    args = parse_args(argv)
    result = validate_gateway_ingress_manifest(Path(args.manifest))
    errors = list(result.errors)
    if args.allow_placeholder:
        errors = [
            error
            for error in errors
            if "gateway.example.com" not in error
        ]

    if errors:
        for error in errors:
            print(f"error: {error}")
        for warning in result.warnings:
            print(f"warning: {warning}")
        return 1

    print(f"gateway ingress manifest ok host={result.host}")
    for warning in result.warnings:
        print(f"warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
