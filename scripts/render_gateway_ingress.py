#!/usr/bin/env python3
"""Render and optionally apply the gateway ingress manifest.

Purpose: replace the placeholder gateway host with a concrete DNS name,
validate publication readiness, and optionally apply the rendered manifest.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: k8s/mullu-gateway-ingress.yaml, kubectl when --apply is used.
Invariants:
  - The source manifest remains a template and is not edited in place.
  - The rendered manifest must validate without placeholder allowance.
  - kubectl apply is opt-in and receives only the rendered manifest path.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_gateway_ingress_manifest import (  # noqa: E402
    DEFAULT_MANIFEST,
    validate_gateway_ingress_manifest,
)

DEFAULT_OUTPUT = Path(".change_assurance") / "mullu-gateway-ingress.rendered.yaml"
PLACEHOLDER_HOST = "gateway.example.com"


class CommandRunner(Protocol):
    """Subprocess-compatible command execution contract."""

    def __call__(
        self,
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        """Run one command and return its completed process."""


@dataclass(frozen=True, slots=True)
class RenderedGatewayIngress:
    """Rendered gateway ingress output contract."""

    source_path: Path
    output_path: Path
    host: str
    applied: bool


def render_gateway_ingress(
    *,
    gateway_host: str,
    source_path: Path = DEFAULT_MANIFEST,
    output_path: Path = DEFAULT_OUTPUT,
    apply: bool = False,
    runner: CommandRunner | None = None,
) -> RenderedGatewayIngress:
    """Render the gateway ingress template and optionally apply it."""
    normalized_host = _require_gateway_host(gateway_host)
    if not source_path.exists():
        raise RuntimeError(f"missing gateway ingress source manifest: {source_path}")
    source_text = source_path.read_text(encoding="utf-8")
    if PLACEHOLDER_HOST not in source_text:
        raise RuntimeError(f"source manifest must contain placeholder host {PLACEHOLDER_HOST}")

    rendered_text = source_text.replace(PLACEHOLDER_HOST, normalized_host)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered_text, encoding="utf-8")

    validation = validate_gateway_ingress_manifest(output_path)
    if not validation.ok:
        raise RuntimeError(
            "rendered ingress manifest failed validation: "
            + "; ".join(validation.errors)
        )

    if apply:
        _apply_manifest(output_path=output_path, runner=runner or subprocess.run)

    return RenderedGatewayIngress(
        source_path=source_path,
        output_path=output_path,
        host=normalized_host,
        applied=apply,
    )


def _require_gateway_host(gateway_host: str) -> str:
    host = gateway_host.strip().lower()
    if host.startswith(("https://", "http://")):
        raise RuntimeError("gateway host must not include URL scheme")
    if "/" in host or ":" in host:
        raise RuntimeError("gateway host must not include path or port")
    if host == PLACEHOLDER_HOST:
        raise RuntimeError("gateway host must replace gateway.example.com")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", host):
        raise RuntimeError("gateway host contains invalid DNS characters")
    if "." not in host:
        raise RuntimeError("gateway host must be a fully qualified DNS name")
    return host


def _apply_manifest(*, output_path: Path, runner: CommandRunner) -> None:
    command = ["kubectl", "apply", "-f", str(output_path)]
    try:
        runner(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("kubectl executable was not found") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"kubectl apply failed: exit_code={exc.returncode}") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse gateway ingress render CLI arguments."""
    parser = argparse.ArgumentParser(description="Render the Mullu gateway ingress manifest.")
    parser.add_argument("--gateway-host", default=os.environ.get("MULLU_GATEWAY_HOST", ""))
    parser.add_argument("--source", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for ingress rendering and optional apply."""
    args = parse_args(argv)
    try:
        rendered = render_gateway_ingress(
            gateway_host=args.gateway_host,
            source_path=Path(args.source),
            output_path=Path(args.output),
            apply=args.apply,
        )
    except RuntimeError as exc:
        message = str(exc)
        detail = message if message.startswith("gateway host ") else ""
        print("gateway ingress render failed" + (f": {detail}" if detail else ""))
        return 1

    print(f"source_path: {rendered.source_path}")
    print(f"output_path: {rendered.output_path}")
    print(f"gateway_host: {rendered.host}")
    print(f"applied: {str(rendered.applied).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
