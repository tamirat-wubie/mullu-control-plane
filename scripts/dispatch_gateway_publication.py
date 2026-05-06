#!/usr/bin/env python3
"""Dispatch the governed gateway publication workflow.

Purpose: provide a local operator shortcut for the GitHub-side publication
workflow while preserving preflight, secret-presence, and artifact evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: GitHub CLI, .github/workflows/gateway-publication.yml.
Invariants:
  - Gateway host is explicit and fully qualified before dispatch.
  - Runtime witness, conformance, and deployment witness secret presence is
    checked by name, not value.
  - Kubeconfig secret presence is required only when ingress apply is requested.
  - Readiness-report handoff fails closed unless the report is ready and its
    required proof steps passed.
  - The gateway-publication-witness artifact is downloaded after completion.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from scripts.dispatch_deployment_witness import (
    DEFAULT_CONFORMANCE_SECRET_NAME as DEFAULT_DEPLOYMENT_CONFORMANCE_SECRET_NAME,
    DEFAULT_DEPLOYMENT_WITNESS_SECRET_NAME as DEFAULT_PUBLICATION_WITNESS_SECRET_NAME,
    DEFAULT_REPOSITORY,
    VALID_ENVIRONMENTS,
)
from scripts.render_gateway_ingress import PLACEHOLDER_HOST

DEFAULT_WORKFLOW_FILE = "gateway-publication.yml"
DEFAULT_WORKFLOW_NAME = "Gateway Publication Orchestration"
DEFAULT_RUNTIME_SECRET_NAME = "MULLU_RUNTIME_WITNESS_SECRET"
DEFAULT_CONFORMANCE_SECRET_NAME = DEFAULT_DEPLOYMENT_CONFORMANCE_SECRET_NAME
DEFAULT_DEPLOYMENT_WITNESS_SECRET_NAME = DEFAULT_PUBLICATION_WITNESS_SECRET_NAME
DEFAULT_KUBECONFIG_SECRET_NAME = "MULLU_KUBECONFIG_B64"
DEFAULT_ARTIFACT_NAME = "gateway-publication-witness"
DEFAULT_DOWNLOAD_DIR = Path(".change_assurance") / "gateway-publication-artifact"
DEFAULT_READINESS_REPORT = Path(".change_assurance") / "gateway_publication_readiness.json"
REQUIRED_READINESS_STEP_NAMES = frozenset(
    {
        "repository variables",
        "runtime witness secret",
        "runtime conformance secret",
        "deployment witness secret",
        "kubeconfig secret",
        "gateway publication workflow",
        "dns resolution",
    }
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
class GatewayPublicationDispatch:
    """Observed result of one gateway publication workflow dispatch."""

    run_id: int
    run_url: str
    status: str
    conclusion: str
    artifact_dir: Path


@dataclass(frozen=True, slots=True)
class GatewayPublicationDispatchInputs:
    """Validated inputs used for one gateway publication dispatch."""

    repository: str
    gateway_host: str
    gateway_url: str
    expected_environment: str
    apply_ingress: bool
    dispatch_witness: bool
    skip_preflight_endpoint_probes: bool


def dispatch_gateway_publication(
    *,
    gateway_host: str,
    expected_environment: str,
    gateway_url: str = "",
    apply_ingress: bool = False,
    dispatch_witness: bool = False,
    skip_preflight_endpoint_probes: bool = False,
    repository: str = DEFAULT_REPOSITORY,
    workflow_file: str = DEFAULT_WORKFLOW_FILE,
    workflow_name: str = DEFAULT_WORKFLOW_NAME,
    runtime_secret_name: str = DEFAULT_RUNTIME_SECRET_NAME,
    conformance_secret_name: str = DEFAULT_CONFORMANCE_SECRET_NAME,
    deployment_witness_secret_name: str = DEFAULT_DEPLOYMENT_WITNESS_SECRET_NAME,
    kubeconfig_secret_name: str = DEFAULT_KUBECONFIG_SECRET_NAME,
    artifact_name: str = DEFAULT_ARTIFACT_NAME,
    download_dir: Path = DEFAULT_DOWNLOAD_DIR,
    timeout_seconds: int = 900,
    poll_seconds: int = 10,
    runner: CommandRunner | None = None,
) -> GatewayPublicationDispatch:
    """Dispatch the gateway publication workflow and download its witness."""
    command_runner = runner or subprocess.run
    normalized_host = _require_gateway_host(gateway_host)
    normalized_gateway_url = _require_gateway_url(gateway_url) if gateway_url else ""
    _require_expected_environment(expected_environment)
    secrets = _read_secret_names(repository=repository, runner=command_runner)
    _require_named_secret(secrets=secrets, secret_name=runtime_secret_name)
    _require_named_secret(secrets=secrets, secret_name=conformance_secret_name)
    _require_named_secret(secrets=secrets, secret_name=deployment_witness_secret_name)
    if apply_ingress:
        _require_named_secret(secrets=secrets, secret_name=kubeconfig_secret_name)
    _require_active_workflow(
        repository=repository,
        workflow_file=workflow_file,
        workflow_name=workflow_name,
        runner=command_runner,
    )

    dispatched_at = _utc_now()
    command = [
        "gh",
        "workflow",
        "run",
        workflow_file,
        "--repo",
        repository,
        "--ref",
        "main",
        "--field",
        f"gateway_host={normalized_host}",
        "--field",
        f"expected_environment={expected_environment}",
        "--field",
        f"apply_ingress={_bool_field(apply_ingress)}",
        "--field",
        f"dispatch_witness={_bool_field(dispatch_witness)}",
        "--field",
        f"skip_preflight_endpoint_probes={_bool_field(skip_preflight_endpoint_probes)}",
    ]
    if normalized_gateway_url:
        command.extend(["--field", f"gateway_url={normalized_gateway_url}"])
    _run_checked(command_runner, command)

    run_id = _wait_for_dispatched_run(
        repository=repository,
        workflow_file=workflow_file,
        dispatched_at=dispatched_at,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
        runner=command_runner,
    )
    final_payload = _read_run(repository=repository, run_id=run_id, runner=command_runner)
    artifact_dir = _download_artifact(
        repository=repository,
        run_id=run_id,
        artifact_name=artifact_name,
        download_dir=download_dir,
        runner=command_runner,
    )
    return GatewayPublicationDispatch(
        run_id=run_id,
        run_url=str(final_payload.get("url", "")),
        status=str(final_payload.get("status", "")),
        conclusion=str(final_payload.get("conclusion", "")),
        artifact_dir=artifact_dir,
    )


def _require_gateway_host(gateway_host: str) -> str:
    host = gateway_host.strip().lower()
    if not host:
        raise RuntimeError("gateway host is required")
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


def _require_gateway_url(gateway_url: str) -> str:
    normalized = gateway_url.strip().rstrip("/")
    if not normalized:
        return ""
    if not normalized.startswith(("https://", "http://")):
        raise RuntimeError("gateway URL must start with http:// or https://")
    return normalized


def _require_expected_environment(expected_environment: str) -> None:
    if expected_environment not in VALID_ENVIRONMENTS:
        raise RuntimeError(
            f"expected environment must be one of {list(VALID_ENVIRONMENTS)}"
        )


def _read_secret_names(*, repository: str, runner: CommandRunner) -> frozenset[str]:
    completed = _run_checked(
        runner,
        ["gh", "secret", "list", "--repo", repository, "--json", "name"],
    )
    return frozenset(
        str(secret.get("name", ""))
        for secret in _json_list(completed.stdout, "gh secret list")
    )


def _require_named_secret(*, secrets: frozenset[str], secret_name: str) -> None:
    if secret_name not in secrets:
        raise RuntimeError(f"missing repository secret {secret_name}")


def _require_active_workflow(
    *,
    repository: str,
    workflow_file: str,
    workflow_name: str,
    runner: CommandRunner,
) -> None:
    completed = _run_checked(
        runner,
        ["gh", "workflow", "list", "--repo", repository, "--json", "name,path,state"],
    )
    workflows = _json_list(completed.stdout, "gh workflow list")
    for workflow in workflows:
        name = str(workflow.get("name", ""))
        path = str(workflow.get("path", ""))
        state = str(workflow.get("state", ""))
        if name == workflow_name or path.endswith(f"/{workflow_file}"):
            if state == "active":
                return
            raise RuntimeError(f"workflow {workflow_name} is not active: {state}")
    raise RuntimeError(f"workflow {workflow_name} was not found")


def _wait_for_dispatched_run(
    *,
    repository: str,
    workflow_file: str,
    dispatched_at: str,
    timeout_seconds: int,
    poll_seconds: int,
    runner: CommandRunner,
) -> int:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        completed = _run_checked(
            runner,
            [
                "gh",
                "run",
                "list",
                "--repo",
                repository,
                "--workflow",
                workflow_file,
                "--branch",
                "main",
                "--limit",
                "10",
                "--json",
                "databaseId,createdAt,status",
            ],
        )
        for run in _json_list(completed.stdout, "gh run list"):
            created_at = str(run.get("createdAt", ""))
            run_id = run.get("databaseId")
            if created_at >= dispatched_at and isinstance(run_id, int):
                _watch_run(repository=repository, run_id=run_id, runner=runner)
                return run_id
        time.sleep(max(1, poll_seconds))
    raise RuntimeError("timed out waiting for dispatched gateway publication run")


def _watch_run(*, repository: str, run_id: int, runner: CommandRunner) -> None:
    _run_checked(
        runner,
        ["gh", "run", "watch", str(run_id), "--repo", repository],
    )


def _read_run(
    *,
    repository: str,
    run_id: int,
    runner: CommandRunner,
) -> dict[str, Any]:
    completed = _run_checked(
        runner,
        [
            "gh",
            "run",
            "view",
            str(run_id),
            "--repo",
            repository,
            "--json",
            "databaseId,status,conclusion,url",
        ],
    )
    payload = _json_object(completed.stdout, "gh run view")
    conclusion = str(payload.get("conclusion", ""))
    if conclusion != "success":
        run_url = str(payload.get("url", ""))
        print(f"gateway publication workflow concluded {conclusion}: {run_url}")
    return payload


def _download_artifact(
    *,
    repository: str,
    run_id: int,
    artifact_name: str,
    download_dir: Path,
    runner: CommandRunner,
) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    _run_checked(
        runner,
        [
            "gh",
            "run",
            "download",
            str(run_id),
            "--repo",
            repository,
            "--name",
            artifact_name,
            "--dir",
            str(download_dir),
        ],
    )
    return download_dir


def _run_checked(
    runner: CommandRunner,
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    try:
        return runner(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("GitHub CLI executable 'gh' was not found") from exc
    except subprocess.CalledProcessError as exc:
        command_name = " ".join(command[:3])
        raise RuntimeError(f"command failed: {command_name}: exit_code={exc.returncode}") from exc


def _json_list(raw_text: str, command_name: str) -> list[dict[str, Any]]:
    parsed = _loads_json(raw_text, command_name)
    if not isinstance(parsed, list) or not all(
        isinstance(item, dict) for item in parsed
    ):
        raise RuntimeError(f"{command_name} did not return a JSON object list")
    return parsed


def _json_object(raw_text: str, command_name: str) -> dict[str, Any]:
    parsed = _loads_json(raw_text, command_name)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{command_name} did not return a JSON object")
    return parsed


def _loads_json(raw_text: str, command_name: str) -> Any:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{command_name} returned invalid JSON") from exc


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bool_field(value: bool) -> str:
    return str(value).lower()


def load_readiness_dispatch_inputs(
    readiness_report_path: Path,
    *,
    repository: str,
) -> GatewayPublicationDispatchInputs:
    """Load dispatch inputs from a ready gateway publication readiness report."""
    payload = _readiness_json_object(readiness_report_path)
    ready = _readiness_bool(payload, "ready")
    if not ready:
        raise RuntimeError(f"readiness report is not ready: {readiness_report_path}")
    _require_readiness_proof_steps(payload)

    report_repository = _readiness_string(payload, "repository")
    if report_repository != repository:
        raise RuntimeError("readiness report repository mismatch")

    return GatewayPublicationDispatchInputs(
        repository=repository,
        gateway_host=_readiness_string(payload, "gateway_host"),
        gateway_url=_readiness_string(payload, "gateway_url"),
        expected_environment=_readiness_string(payload, "expected_environment"),
        apply_ingress=_readiness_bool(payload, "apply_ingress"),
        dispatch_witness=_readiness_bool(payload, "dispatch_witness"),
        skip_preflight_endpoint_probes=_readiness_bool(
            payload,
            "skip_preflight_endpoint_probes",
        ),
    )


def _require_readiness_proof_steps(payload: dict[str, Any]) -> None:
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list):
        raise RuntimeError("readiness report proof steps must be a list")
    step_by_name = {
        str(step.get("name", "")): step
        for step in raw_steps
        if isinstance(step, dict)
    }
    missing = REQUIRED_READINESS_STEP_NAMES - set(step_by_name)
    failed = {
        name
        for name in REQUIRED_READINESS_STEP_NAMES & set(step_by_name)
        if step_by_name[name].get("passed") is not True
    }
    if missing or failed:
        raise RuntimeError("readiness report proof steps failed")


def _readiness_json_object(readiness_report_path: Path) -> dict[str, Any]:
    try:
        raw_text = readiness_report_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("failed to read readiness report") from exc
    parsed = _loads_json(raw_text, "gateway publication readiness report")
    if not isinstance(parsed, dict):
        raise RuntimeError("gateway publication readiness report was not a JSON object")
    return parsed


def _readiness_string(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"readiness report field {field_name} must be a string")
    return value.strip()


def _readiness_bool(payload: dict[str, Any], field_name: str) -> bool:
    value = payload.get(field_name)
    if not isinstance(value, bool):
        raise RuntimeError(f"readiness report field {field_name} must be a boolean")
    return value


def _cli_dispatch_inputs(args: argparse.Namespace) -> GatewayPublicationDispatchInputs:
    return GatewayPublicationDispatchInputs(
        repository=args.repo,
        gateway_host=args.gateway_host,
        gateway_url=args.gateway_url,
        expected_environment=args.expected_environment,
        apply_ingress=args.apply_ingress,
        dispatch_witness=args.dispatch_witness,
        skip_preflight_endpoint_probes=args.skip_preflight_endpoint_probes,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse gateway publication dispatch CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Dispatch the governed gateway publication workflow."
    )
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY))
    parser.add_argument("--gateway-host", default=os.environ.get("MULLU_GATEWAY_HOST", ""))
    parser.add_argument("--gateway-url", default=os.environ.get("MULLU_GATEWAY_URL", ""))
    parser.add_argument(
        "--expected-environment",
        choices=VALID_ENVIRONMENTS,
        default=os.environ.get("MULLU_EXPECTED_RUNTIME_ENV", "pilot"),
    )
    parser.add_argument("--apply-ingress", action="store_true")
    parser.add_argument("--dispatch-witness", action="store_true")
    parser.add_argument("--skip-preflight-endpoint-probes", action="store_true")
    parser.add_argument(
        "--readiness-report",
        default="",
        help=f"Dispatch from a ready report such as {DEFAULT_READINESS_REPORT}",
    )
    parser.add_argument("--workflow-file", default=DEFAULT_WORKFLOW_FILE)
    parser.add_argument("--workflow-name", default=DEFAULT_WORKFLOW_NAME)
    parser.add_argument("--runtime-secret-name", default=DEFAULT_RUNTIME_SECRET_NAME)
    parser.add_argument("--conformance-secret-name", default=DEFAULT_CONFORMANCE_SECRET_NAME)
    parser.add_argument("--deployment-witness-secret-name", default=DEFAULT_DEPLOYMENT_WITNESS_SECRET_NAME)
    parser.add_argument("--kubeconfig-secret-name", default=DEFAULT_KUBECONFIG_SECRET_NAME)
    parser.add_argument("--artifact-name", default=DEFAULT_ARTIFACT_NAME)
    parser.add_argument("--download-dir", default=str(DEFAULT_DOWNLOAD_DIR))
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=int, default=10)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for gateway publication workflow dispatch."""
    args = parse_args(argv)
    try:
        dispatch_inputs = (
            load_readiness_dispatch_inputs(
                Path(args.readiness_report),
                repository=args.repo,
            )
            if args.readiness_report
            else _cli_dispatch_inputs(args)
        )
        result = dispatch_gateway_publication(
            gateway_host=dispatch_inputs.gateway_host,
            gateway_url=dispatch_inputs.gateway_url,
            expected_environment=dispatch_inputs.expected_environment,
            apply_ingress=dispatch_inputs.apply_ingress,
            dispatch_witness=dispatch_inputs.dispatch_witness,
            skip_preflight_endpoint_probes=(
                dispatch_inputs.skip_preflight_endpoint_probes
            ),
            repository=dispatch_inputs.repository,
            workflow_file=args.workflow_file,
            workflow_name=args.workflow_name,
            runtime_secret_name=args.runtime_secret_name,
            conformance_secret_name=args.conformance_secret_name,
            deployment_witness_secret_name=args.deployment_witness_secret_name,
            kubeconfig_secret_name=args.kubeconfig_secret_name,
            artifact_name=args.artifact_name,
            download_dir=Path(args.download_dir),
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
    except RuntimeError as exc:
        message = str(exc)
        detail = ""
        if message.startswith("readiness report repository mismatch"):
            detail = "readiness report repository mismatch"
        elif message == "failed to read readiness report":
            detail = message
        print("gateway publication dispatch failed" + (f": {detail}" if detail else ""))
        return 1

    print(f"gateway publication run: {result.run_url}")
    print(f"run_id: {result.run_id}")
    print(f"status: {result.status}")
    print(f"conclusion: {result.conclusion}")
    print(f"artifact_dir: {result.artifact_dir}")
    return 0 if result.conclusion == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
