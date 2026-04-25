#!/usr/bin/env python3
"""Publish gateway publication through readiness-report handoff.

Purpose: provide one governed operator command that writes a readiness report
before optionally dispatching the gateway publication workflow from that report.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.report_gateway_publication_readiness and
scripts.dispatch_gateway_publication.
Invariants:
  - Readiness evidence is written before any workflow dispatch.
  - Workflow dispatch requires the explicit --dispatch flag.
  - Dispatch inputs are reloaded from the written readiness report.
  - Dispatch re-validates secret names and workflow state before mutation.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from scripts.dispatch_deployment_witness import DEFAULT_REPOSITORY, VALID_ENVIRONMENTS
from scripts.dispatch_gateway_publication import (
    DEFAULT_ARTIFACT_NAME,
    DEFAULT_DOWNLOAD_DIR,
    DEFAULT_KUBECONFIG_SECRET_NAME,
    DEFAULT_READINESS_REPORT,
    DEFAULT_RUNTIME_SECRET_NAME,
    DEFAULT_WORKFLOW_FILE,
    DEFAULT_WORKFLOW_NAME,
    CommandRunner,
    GatewayPublicationDispatch,
    dispatch_gateway_publication,
    load_readiness_dispatch_inputs,
)
from scripts.report_gateway_publication_readiness import (
    GatewayPublicationReadiness,
    Resolver,
    report_gateway_publication_readiness,
    write_gateway_publication_readiness,
)


@dataclass(frozen=True, slots=True)
class GatewayPublicationPublish:
    """Observed result for one readiness-to-dispatch publication attempt."""

    readiness_report_path: Path
    readiness: GatewayPublicationReadiness
    dispatch_requested: bool
    dispatch: GatewayPublicationDispatch | None


def publish_gateway_publication(
    *,
    gateway_host: str = "",
    gateway_url: str = "",
    expected_environment: str = "",
    repository: str = DEFAULT_REPOSITORY,
    apply_ingress: bool = False,
    dispatch_witness: bool = False,
    skip_preflight_endpoint_probes: bool = False,
    dispatch: bool = False,
    readiness_report_path: Path = DEFAULT_READINESS_REPORT,
    workflow_file: str = DEFAULT_WORKFLOW_FILE,
    workflow_name: str = DEFAULT_WORKFLOW_NAME,
    runtime_secret_name: str = DEFAULT_RUNTIME_SECRET_NAME,
    kubeconfig_secret_name: str = DEFAULT_KUBECONFIG_SECRET_NAME,
    artifact_name: str = DEFAULT_ARTIFACT_NAME,
    download_dir: Path = DEFAULT_DOWNLOAD_DIR,
    timeout_seconds: int = 900,
    poll_seconds: int = 10,
    runner: CommandRunner | None = None,
    resolver: Resolver | None = None,
) -> GatewayPublicationPublish:
    """Write publication readiness, then optionally dispatch from that report."""
    command_runner = runner or subprocess.run
    readiness = report_gateway_publication_readiness(
        gateway_host=gateway_host,
        gateway_url=gateway_url,
        expected_environment=expected_environment,
        repository=repository,
        apply_ingress=apply_ingress,
        dispatch_witness=dispatch_witness,
        skip_preflight_endpoint_probes=skip_preflight_endpoint_probes,
        workflow_file=workflow_file,
        workflow_name=workflow_name,
        runtime_secret_name=runtime_secret_name,
        kubeconfig_secret_name=kubeconfig_secret_name,
        runner=command_runner,
        resolver=resolver,
    )
    write_gateway_publication_readiness(readiness, readiness_report_path)

    if not readiness.ready or not dispatch:
        return GatewayPublicationPublish(
            readiness_report_path=readiness_report_path,
            readiness=readiness,
            dispatch_requested=dispatch,
            dispatch=None,
        )

    dispatch_inputs = load_readiness_dispatch_inputs(
        readiness_report_path,
        repository=repository,
    )
    dispatch_result = dispatch_gateway_publication(
        gateway_host=dispatch_inputs.gateway_host,
        gateway_url=dispatch_inputs.gateway_url,
        expected_environment=dispatch_inputs.expected_environment,
        apply_ingress=dispatch_inputs.apply_ingress,
        dispatch_witness=dispatch_inputs.dispatch_witness,
        skip_preflight_endpoint_probes=(
            dispatch_inputs.skip_preflight_endpoint_probes
        ),
        repository=dispatch_inputs.repository,
        workflow_file=workflow_file,
        workflow_name=workflow_name,
        runtime_secret_name=runtime_secret_name,
        kubeconfig_secret_name=kubeconfig_secret_name,
        artifact_name=artifact_name,
        download_dir=download_dir,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
        runner=command_runner,
    )
    return GatewayPublicationPublish(
        readiness_report_path=readiness_report_path,
        readiness=readiness,
        dispatch_requested=dispatch,
        dispatch=dispatch_result,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse gateway publication publish CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Report gateway publication readiness, then optionally dispatch."
    )
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY))
    parser.add_argument("--gateway-host", default=os.environ.get("MULLU_GATEWAY_HOST", ""))
    parser.add_argument("--gateway-url", default=os.environ.get("MULLU_GATEWAY_URL", ""))
    parser.add_argument(
        "--expected-environment",
        choices=VALID_ENVIRONMENTS,
        default=os.environ.get("MULLU_EXPECTED_RUNTIME_ENV", ""),
    )
    parser.add_argument("--apply-ingress", action="store_true")
    parser.add_argument("--dispatch-witness", action="store_true")
    parser.add_argument("--skip-preflight-endpoint-probes", action="store_true")
    parser.add_argument("--dispatch", action="store_true")
    parser.add_argument("--readiness-report-output", default=str(DEFAULT_READINESS_REPORT))
    parser.add_argument("--workflow-file", default=DEFAULT_WORKFLOW_FILE)
    parser.add_argument("--workflow-name", default=DEFAULT_WORKFLOW_NAME)
    parser.add_argument("--runtime-secret-name", default=DEFAULT_RUNTIME_SECRET_NAME)
    parser.add_argument("--kubeconfig-secret-name", default=DEFAULT_KUBECONFIG_SECRET_NAME)
    parser.add_argument("--artifact-name", default=DEFAULT_ARTIFACT_NAME)
    parser.add_argument("--download-dir", default=str(DEFAULT_DOWNLOAD_DIR))
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=int, default=10)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for readiness-to-dispatch gateway publication."""
    args = parse_args(argv)
    try:
        result = publish_gateway_publication(
            gateway_host=args.gateway_host,
            gateway_url=args.gateway_url,
            expected_environment=args.expected_environment,
            repository=args.repo,
            apply_ingress=args.apply_ingress,
            dispatch_witness=args.dispatch_witness,
            skip_preflight_endpoint_probes=args.skip_preflight_endpoint_probes,
            dispatch=args.dispatch,
            readiness_report_path=Path(args.readiness_report_output),
            workflow_file=args.workflow_file,
            workflow_name=args.workflow_name,
            runtime_secret_name=args.runtime_secret_name,
            kubeconfig_secret_name=args.kubeconfig_secret_name,
            artifact_name=args.artifact_name,
            download_dir=Path(args.download_dir),
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
    except RuntimeError as exc:
        print(f"gateway publication publish failed: {exc}")
        return 1

    _print_publish_result(result)
    if not result.readiness.ready:
        return 1
    if result.dispatch_requested and result.dispatch:
        return 0 if result.dispatch.conclusion == "success" else 1
    return 0


def _print_publish_result(result: GatewayPublicationPublish) -> None:
    readiness = result.readiness
    print(f"readiness_report: {result.readiness_report_path}")
    print(f"gateway_host: {readiness.gateway_host}")
    print(f"gateway_url: {readiness.gateway_url}")
    print(f"expected_environment: {readiness.expected_environment}")
    print(f"ready: {str(readiness.ready).lower()}")
    print(f"dispatch_requested: {str(result.dispatch_requested).lower()}")
    print(
        "handoff_command: "
        f"python scripts/dispatch_gateway_publication.py "
        f"--readiness-report {result.readiness_report_path}"
    )
    for step in readiness.steps:
        print(f"step: {step.name} passed={str(step.passed).lower()} detail={step.detail}")
    if result.dispatch:
        print(f"gateway publication run: {result.dispatch.run_url}")
        print(f"run_id: {result.dispatch.run_id}")
        print(f"status: {result.dispatch.status}")
        print(f"conclusion: {result.dispatch.conclusion}")
        print(f"artifact_dir: {result.dispatch.artifact_dir}")


if __name__ == "__main__":
    raise SystemExit(main())
