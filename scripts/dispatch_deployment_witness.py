#!/usr/bin/env python3
"""Dispatch and collect the governed deployment witness workflow.

Purpose: turn the manual deployment witness workflow into one guarded operator
command that verifies required GitHub inputs before it requests live evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: GitHub CLI, .github/workflows/deployment-witness.yml.
Invariants:
  - Workflow dispatch requires an explicit gateway URL.
  - Workflow dispatch requires runtime witness and conformance repository
    secrets to exist.
  - Mounted runtime and conformance secrets can witness presence without
    listing secrets.
  - The selected workflow must be active before dispatch.
  - The deployment-witness artifact is downloaded after the run completes.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

DEFAULT_REPOSITORY = "tamirat-wubie/mullu-control-plane"
DEFAULT_WORKFLOW_FILE = "deployment-witness.yml"
DEFAULT_WORKFLOW_NAME = "Deployment Witness Collection"
DEFAULT_SECRET_NAME = "MULLU_RUNTIME_WITNESS_SECRET"
DEFAULT_CONFORMANCE_SECRET_NAME = "MULLU_RUNTIME_CONFORMANCE_SECRET"
DEFAULT_ARTIFACT_NAME = "deployment-witness"
DEFAULT_DOWNLOAD_DIR = Path(".change_assurance") / "deployment-witness-artifact"
DEFAULT_GATEWAY_URL_VARIABLE = "MULLU_GATEWAY_URL"
DEFAULT_EXPECTED_ENVIRONMENT_VARIABLE = "MULLU_EXPECTED_RUNTIME_ENV"
VALID_ENVIRONMENTS = ("pilot", "production")


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
class DispatchResult:
    """Observed result of one deployment witness workflow dispatch."""

    run_id: int
    run_url: str
    status: str
    conclusion: str
    artifact_dir: Path


def dispatch_deployment_witness(
    *,
    gateway_url: str,
    expected_environment: str,
    repository: str = DEFAULT_REPOSITORY,
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
) -> DispatchResult:
    """Dispatch the deployment witness workflow and download its artifact."""
    command_runner = runner or subprocess.run
    repository_variables = (
        _read_repository_variables(repository=repository, runner=command_runner)
        if not gateway_url or not expected_environment
        else {}
    )
    normalized_gateway_url = _require_gateway_url(
        gateway_url or repository_variables.get(DEFAULT_GATEWAY_URL_VARIABLE, "")
    )
    resolved_environment = (
        expected_environment
        or repository_variables.get(DEFAULT_EXPECTED_ENVIRONMENT_VARIABLE, "")
        or "pilot"
    )
    _require_expected_environment(resolved_environment)
    if not runtime_secret_present:
        _require_secret(repository=repository, secret_name=secret_name, runner=command_runner)
    if not conformance_secret_present:
        _require_secret(repository=repository, secret_name=conformance_secret_name, runner=command_runner)
    _require_active_workflow(
        repository=repository,
        workflow_file=workflow_file,
        workflow_name=workflow_name,
        runner=command_runner,
    )

    dispatched_at = _utc_now()
    _run_checked(
        command_runner,
        [
            "gh",
            "workflow",
            "run",
            workflow_file,
            "--repo",
            repository,
            "--ref",
            "main",
            "--field",
            f"gateway_url={normalized_gateway_url}",
            "--field",
            f"expected_environment={resolved_environment}",
        ],
    )
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
    return DispatchResult(
        run_id=run_id,
        run_url=str(final_payload.get("url", "")),
        status=str(final_payload.get("status", "")),
        conclusion=str(final_payload.get("conclusion", "")),
        artifact_dir=artifact_dir,
    )


def _require_gateway_url(gateway_url: str) -> str:
    normalized = gateway_url.strip().rstrip("/")
    if not normalized:
        raise RuntimeError("gateway URL is required")
    if not normalized.startswith(("https://", "http://")):
        raise RuntimeError("gateway URL must start with http:// or https://")
    return normalized


def _require_expected_environment(expected_environment: str) -> None:
    if expected_environment not in VALID_ENVIRONMENTS:
        raise RuntimeError(
            f"expected environment must be one of {list(VALID_ENVIRONMENTS)}"
        )


def _read_repository_variables(
    *,
    repository: str,
    runner: CommandRunner,
) -> dict[str, str]:
    completed = _run_checked(
        runner,
        ["gh", "variable", "list", "--repo", repository, "--json", "name,value"],
    )
    variables = _json_list(completed.stdout, "gh variable list")
    return {
        str(variable.get("name", "")): str(variable.get("value", ""))
        for variable in variables
    }


def _require_secret(
    *,
    repository: str,
    secret_name: str,
    runner: CommandRunner,
) -> None:
    completed = _run_checked(
        runner,
        ["gh", "secret", "list", "--repo", repository, "--json", "name"],
    )
    secrets = _json_list(completed.stdout, "gh secret list")
    names = {str(secret.get("name", "")) for secret in secrets}
    if secret_name not in names:
        raise RuntimeError(
            f"missing repository secret {secret_name}; configure it before dispatch"
        )


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
    raise RuntimeError("timed out waiting for dispatched deployment witness run")


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
        print(f"deployment witness workflow concluded {conclusion}: {run_url}")
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse deployment witness dispatch CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Dispatch the governed deployment witness workflow."
    )
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY))
    parser.add_argument("--gateway-url", default=os.environ.get("MULLU_GATEWAY_URL", ""))
    parser.add_argument(
        "--expected-environment",
        choices=VALID_ENVIRONMENTS,
        default=os.environ.get("MULLU_EXPECTED_RUNTIME_ENV", ""),
    )
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
    """CLI entry point for workflow dispatch and artifact collection."""
    args = parse_args(argv)
    try:
        result = dispatch_deployment_witness(
            gateway_url=args.gateway_url,
            expected_environment=args.expected_environment,
            repository=args.repo,
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
        print(f"deployment witness dispatch failed: {exc}")
        return 1

    print(f"deployment witness run: {result.run_url}")
    print(f"run_id: {result.run_id}")
    print(f"status: {result.status}")
    print(f"conclusion: {result.conclusion}")
    print(f"artifact_dir: {result.artifact_dir}")
    return 0 if result.conclusion == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
