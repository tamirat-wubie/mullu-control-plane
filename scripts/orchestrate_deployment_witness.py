#!/usr/bin/env python3
"""Orchestrate gateway publication and deployment witness collection.

Purpose: compose ingress rendering, deployment target provisioning, and optional
workflow dispatch into one governed operator command.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.render_gateway_ingress, scripts.provision_deployment_target,
scripts.preflight_deployment_witness, scripts.dispatch_deployment_witness,
kubectl when --apply-ingress is used, GitHub CLI for repository variables and
workflow dispatch.
Invariants:
  - Gateway host is validated before any repository variable is written.
  - Gateway URL is derived from the validated host unless explicitly provided.
  - Live cluster apply and workflow dispatch are explicit operator choices.
  - Dispatch can be gated by a fresh preflight report.
  - Mounted runtime and conformance secrets can witness presence without
    listing secrets.
  - Runtime witness and conformance secrets are never written to stdout.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from scripts.dispatch_deployment_witness import (
    DEFAULT_ARTIFACT_NAME,
    DEFAULT_CONFORMANCE_SECRET_NAME,
    DEFAULT_DOWNLOAD_DIR,
    DEFAULT_SECRET_NAME,
    DEFAULT_WORKFLOW_FILE,
    DEFAULT_WORKFLOW_NAME,
    DispatchResult,
    dispatch_deployment_witness,
)
from scripts.provision_deployment_target import (
    DEFAULT_REPOSITORY,
    VALID_ENVIRONMENTS,
    DeploymentTarget,
    provision_deployment_target,
)
from scripts.preflight_deployment_witness import (
    DEFAULT_OUTPUT as DEFAULT_PREFLIGHT_OUTPUT,
    DeploymentWitnessPreflight,
    JsonGetter,
    Resolver,
    preflight_deployment_witness,
    write_preflight_report,
)
from scripts.render_gateway_ingress import (
    DEFAULT_OUTPUT,
    RenderedGatewayIngress,
    render_gateway_ingress,
)


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
class DeploymentWitnessOrchestration:
    """Result of one governed deployment witness orchestration."""

    ingress: RenderedGatewayIngress
    target: DeploymentTarget
    preflight: DeploymentWitnessPreflight | None
    dispatch: DispatchResult | None


def orchestrate_deployment_witness(
    *,
    gateway_host: str,
    expected_environment: str,
    gateway_url: str = "",
    repository: str = DEFAULT_REPOSITORY,
    rendered_ingress_output: Path = DEFAULT_OUTPUT,
    apply_ingress: bool = False,
    dispatch: bool = False,
    require_preflight: bool = False,
    preflight_output: Path = DEFAULT_PREFLIGHT_OUTPUT,
    preflight_probe_endpoints: bool = True,
    workflow_file: str = DEFAULT_WORKFLOW_FILE,
    workflow_name: str = DEFAULT_WORKFLOW_NAME,
    secret_name: str = DEFAULT_SECRET_NAME,
    conformance_secret_name: str = DEFAULT_CONFORMANCE_SECRET_NAME,
    runtime_secret_present: bool = False,
    conformance_secret_present: bool = False,
    artifact_name: str = DEFAULT_ARTIFACT_NAME,
    download_dir: Path = DEFAULT_DOWNLOAD_DIR,
    timeout_seconds: int = 600,
    poll_seconds: int = 10,
    runner: CommandRunner | None = None,
    resolver: Resolver | None = None,
    json_getter: JsonGetter | None = None,
) -> DeploymentWitnessOrchestration:
    """Render ingress, bind target variables, and optionally dispatch evidence."""
    command_runner = runner or subprocess.run
    ingress = render_gateway_ingress(
        gateway_host=gateway_host,
        output_path=rendered_ingress_output,
        apply=apply_ingress,
        runner=command_runner,
    )
    resolved_gateway_url = gateway_url.strip().rstrip("/") or f"https://{ingress.host}"
    target = provision_deployment_target(
        gateway_url=resolved_gateway_url,
        expected_environment=expected_environment,
        repository=repository,
        runner=command_runner,
    )
    preflight_report = (
        preflight_deployment_witness(
            gateway_host=ingress.host,
            gateway_url=target.gateway_url,
            expected_environment=target.expected_environment,
            repository=repository,
            workflow_file=workflow_file,
            workflow_name=workflow_name,
            secret_name=secret_name,
            conformance_secret_name=conformance_secret_name,
            runtime_secret_present=runtime_secret_present,
            conformance_secret_present=conformance_secret_present,
            probe_endpoints=preflight_probe_endpoints,
            runner=command_runner,
            resolver=resolver,
            json_getter=json_getter,
        )
        if require_preflight
        else None
    )
    if preflight_report is not None:
        write_preflight_report(preflight_report, preflight_output)
        if not preflight_report.ready:
            failed_steps = [
                f"{step.name}: {step.detail}"
                for step in preflight_report.steps
                if not step.passed
            ]
            raise RuntimeError(
                "deployment witness preflight failed: " + "; ".join(failed_steps)
            )
    dispatch_result = (
        dispatch_deployment_witness(
            gateway_url=target.gateway_url,
            expected_environment=target.expected_environment,
            repository=repository,
            workflow_file=workflow_file,
            workflow_name=workflow_name,
            secret_name=secret_name,
            conformance_secret_name=conformance_secret_name,
            runtime_secret_present=runtime_secret_present,
            conformance_secret_present=conformance_secret_present,
            artifact_name=artifact_name,
            download_dir=download_dir,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
            runner=command_runner,
        )
        if dispatch
        else None
    )
    return DeploymentWitnessOrchestration(
        ingress=ingress,
        target=target,
        preflight=preflight_report,
        dispatch=dispatch_result,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse deployment witness orchestration CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Orchestrate gateway ingress, target variables, and witness dispatch."
    )
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY))
    parser.add_argument("--gateway-host", default=os.environ.get("MULLU_GATEWAY_HOST", ""))
    parser.add_argument("--gateway-url", default=os.environ.get("MULLU_GATEWAY_URL", ""))
    parser.add_argument(
        "--expected-environment",
        choices=VALID_ENVIRONMENTS,
        default=os.environ.get("MULLU_EXPECTED_RUNTIME_ENV", "pilot"),
    )
    parser.add_argument("--rendered-ingress-output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--apply-ingress", action="store_true")
    parser.add_argument("--dispatch", action="store_true")
    parser.add_argument("--require-preflight", action="store_true")
    parser.add_argument("--preflight-output", default=str(DEFAULT_PREFLIGHT_OUTPUT))
    parser.add_argument("--skip-preflight-endpoint-probes", action="store_true")
    parser.add_argument("--workflow-file", default=DEFAULT_WORKFLOW_FILE)
    parser.add_argument("--workflow-name", default=DEFAULT_WORKFLOW_NAME)
    parser.add_argument("--secret-name", default=DEFAULT_SECRET_NAME)
    parser.add_argument("--conformance-secret-name", default=DEFAULT_CONFORMANCE_SECRET_NAME)
    parser.add_argument("--accept-runtime-secret-env", action="store_true")
    parser.add_argument("--accept-conformance-secret-env", action="store_true")
    parser.add_argument("--artifact-name", default=DEFAULT_ARTIFACT_NAME)
    parser.add_argument("--download-dir", default=str(DEFAULT_DOWNLOAD_DIR))
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--poll-seconds", type=int, default=10)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for governed deployment witness orchestration."""
    args = parse_args(argv)
    try:
        orchestration = orchestrate_deployment_witness(
            gateway_host=args.gateway_host,
            gateway_url=args.gateway_url,
            expected_environment=args.expected_environment,
            repository=args.repo,
            rendered_ingress_output=Path(args.rendered_ingress_output),
            apply_ingress=args.apply_ingress,
            dispatch=args.dispatch,
            require_preflight=args.require_preflight,
            preflight_output=Path(args.preflight_output),
            preflight_probe_endpoints=not args.skip_preflight_endpoint_probes,
            workflow_file=args.workflow_file,
            workflow_name=args.workflow_name,
            secret_name=args.secret_name,
            conformance_secret_name=args.conformance_secret_name,
            runtime_secret_present=(
                args.accept_runtime_secret_env
                and bool(os.environ.get("MULLU_RUNTIME_WITNESS_SECRET"))
            ),
            conformance_secret_present=(
                args.accept_conformance_secret_env
                and bool(os.environ.get("MULLU_RUNTIME_CONFORMANCE_SECRET"))
            ),
            artifact_name=args.artifact_name,
            download_dir=Path(args.download_dir),
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
    except RuntimeError as exc:
        print(f"deployment witness orchestration failed: {exc}")
        return 1

    print(f"gateway_host: {orchestration.ingress.host}")
    print(f"rendered_ingress: {orchestration.ingress.output_path}")
    print(f"ingress_applied: {str(orchestration.ingress.applied).lower()}")
    print(f"repository: {orchestration.target.repository}")
    print(f"gateway_url: {orchestration.target.gateway_url}")
    print(f"expected_environment: {orchestration.target.expected_environment}")
    if orchestration.preflight is not None:
        print(f"preflight_ready: {str(orchestration.preflight.ready).lower()}")
    if orchestration.dispatch is None:
        print("deployment_witness_dispatch: skipped")
        return 0

    print(f"deployment_witness_run: {orchestration.dispatch.run_url}")
    print(f"run_id: {orchestration.dispatch.run_id}")
    print(f"conclusion: {orchestration.dispatch.conclusion}")
    print(f"artifact_dir: {orchestration.dispatch.artifact_dir}")
    return 0 if orchestration.dispatch.conclusion == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
