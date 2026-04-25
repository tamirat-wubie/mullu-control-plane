#!/usr/bin/env python3
"""Report governed gateway publication readiness.

Purpose: emit a deterministic readiness report before dispatching the gateway
publication workflow.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: GitHub CLI repository metadata and DNS resolution.
Invariants:
  - Gateway host is derived from explicit input or repository variables.
  - Runtime witness and kubeconfig secrets are checked by name only.
  - Workflow dispatch is never performed by this reporter.
  - The next operator command is emitted from validated values.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import socket
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

from scripts.dispatch_deployment_witness import (
    DEFAULT_EXPECTED_ENVIRONMENT_VARIABLE,
    DEFAULT_GATEWAY_URL_VARIABLE,
    DEFAULT_REPOSITORY,
    VALID_ENVIRONMENTS,
)
from scripts.dispatch_gateway_publication import (
    DEFAULT_KUBECONFIG_SECRET_NAME,
    DEFAULT_RUNTIME_SECRET_NAME,
    DEFAULT_WORKFLOW_FILE,
    DEFAULT_WORKFLOW_NAME,
)
from scripts.render_gateway_ingress import PLACEHOLDER_HOST

DEFAULT_OUTPUT = Path(".change_assurance") / "gateway_publication_readiness.json"


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


Resolver = Callable[[str], tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class ReadinessStep:
    """One gateway publication readiness step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class GatewayPublicationReadiness:
    """Structured readiness report for the gateway publication shortcut."""

    repository: str
    gateway_host: str
    gateway_host_source: str
    gateway_url: str
    gateway_url_source: str
    expected_environment: str
    expected_environment_source: str
    apply_ingress: bool
    dispatch_witness: bool
    skip_preflight_endpoint_probes: bool
    ready: bool
    next_command: str
    steps: tuple[ReadinessStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable readiness payload."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


@dataclass(frozen=True, slots=True)
class ResolvedInputs:
    """Normalized publication inputs with causal source labels."""

    gateway_host: str
    gateway_host_source: str
    gateway_url: str
    gateway_url_source: str
    expected_environment: str
    expected_environment_source: str
    variables: dict[str, str]


def report_gateway_publication_readiness(
    *,
    gateway_host: str = "",
    gateway_url: str = "",
    expected_environment: str = "",
    repository: str = DEFAULT_REPOSITORY,
    apply_ingress: bool = False,
    dispatch_witness: bool = False,
    skip_preflight_endpoint_probes: bool = False,
    workflow_file: str = DEFAULT_WORKFLOW_FILE,
    workflow_name: str = DEFAULT_WORKFLOW_NAME,
    runtime_secret_name: str = DEFAULT_RUNTIME_SECRET_NAME,
    kubeconfig_secret_name: str = DEFAULT_KUBECONFIG_SECRET_NAME,
    runner: CommandRunner | None = None,
    resolver: Resolver | None = None,
) -> GatewayPublicationReadiness:
    """Verify gateway publication readiness without mutating remote state."""
    command_runner = runner or subprocess.run
    dns_resolver = resolver or _resolve_host
    resolved = _resolve_inputs(
        gateway_host=gateway_host,
        gateway_url=gateway_url,
        expected_environment=expected_environment,
        repository=repository,
        runner=command_runner,
    )

    secret_names = _read_secret_names(repository=repository, runner=command_runner)
    steps = [
        _check_repository_variables(resolved=resolved),
        _check_secret(
            step_name="runtime witness secret",
            secret_name=runtime_secret_name,
            required=True,
            secrets=secret_names,
        ),
        _check_secret(
            step_name="kubeconfig secret",
            secret_name=kubeconfig_secret_name,
            required=apply_ingress,
            secrets=secret_names,
        ),
        _check_workflow(
            repository=repository,
            workflow_file=workflow_file,
            workflow_name=workflow_name,
            runner=command_runner,
        ),
        _check_dns(host=resolved.gateway_host, resolver=dns_resolver),
    ]
    next_command = _build_next_command(
        gateway_host=resolved.gateway_host,
        gateway_url=resolved.gateway_url,
        expected_environment=resolved.expected_environment,
        apply_ingress=apply_ingress,
        dispatch_witness=dispatch_witness,
        skip_preflight_endpoint_probes=skip_preflight_endpoint_probes,
    )

    return GatewayPublicationReadiness(
        repository=repository,
        gateway_host=resolved.gateway_host,
        gateway_host_source=resolved.gateway_host_source,
        gateway_url=resolved.gateway_url,
        gateway_url_source=resolved.gateway_url_source,
        expected_environment=resolved.expected_environment,
        expected_environment_source=resolved.expected_environment_source,
        apply_ingress=apply_ingress,
        dispatch_witness=dispatch_witness,
        skip_preflight_endpoint_probes=skip_preflight_endpoint_probes,
        ready=all(step.passed for step in steps),
        next_command=next_command,
        steps=tuple(steps),
    )


def write_gateway_publication_readiness(
    report: GatewayPublicationReadiness,
    output_path: Path,
) -> Path:
    """Write one gateway publication readiness report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _resolve_inputs(
    *,
    gateway_host: str,
    gateway_url: str,
    expected_environment: str,
    repository: str,
    runner: CommandRunner,
) -> ResolvedInputs:
    variables_required = not gateway_host.strip() or not expected_environment.strip()
    variables = (
        _read_repository_variables(repository=repository, runner=runner)
        if variables_required
        else {}
    )
    normalized_gateway_url = _normalize_gateway_url(gateway_url)

    if gateway_host.strip():
        normalized_gateway_host = _require_gateway_host(gateway_host)
        gateway_host_source = "explicit-host"
    elif normalized_gateway_url:
        normalized_gateway_host = _derive_host_from_url(normalized_gateway_url)
        gateway_host_source = "explicit-url"
    else:
        normalized_gateway_url = _normalize_gateway_url(
            variables.get(DEFAULT_GATEWAY_URL_VARIABLE, "")
        )
        normalized_gateway_host = _derive_host_from_url(normalized_gateway_url)
        gateway_host_source = "repository-variable"

    if normalized_gateway_url:
        gateway_url_source = (
            "explicit-url"
            if gateway_url.strip()
            else "repository-variable"
        )
    else:
        normalized_gateway_url = f"https://{normalized_gateway_host}"
        gateway_url_source = "derived-from-host"

    if expected_environment.strip():
        resolved_environment = expected_environment.strip()
        environment_source = "explicit-environment"
    else:
        resolved_environment = (
            variables.get(DEFAULT_EXPECTED_ENVIRONMENT_VARIABLE, "").strip() or "pilot"
        )
        environment_source = (
            "repository-variable"
            if variables.get(DEFAULT_EXPECTED_ENVIRONMENT_VARIABLE, "").strip()
            else "default"
        )
    _require_expected_environment(resolved_environment)

    return ResolvedInputs(
        gateway_host=normalized_gateway_host,
        gateway_host_source=gateway_host_source,
        gateway_url=normalized_gateway_url,
        gateway_url_source=gateway_url_source,
        expected_environment=resolved_environment,
        expected_environment_source=environment_source,
        variables=variables,
    )


def _check_repository_variables(*, resolved: ResolvedInputs) -> ReadinessStep:
    if not resolved.variables:
        return ReadinessStep("repository variables", True, "not-required")

    required_mismatches: list[str] = []
    advisory_mismatches: list[str] = []
    variable_gateway_url = resolved.variables.get(DEFAULT_GATEWAY_URL_VARIABLE, "")
    variable_environment = resolved.variables.get(DEFAULT_EXPECTED_ENVIRONMENT_VARIABLE, "")
    _append_variable_mismatch(
        mismatches=(
            required_mismatches
            if resolved.gateway_url_source == "repository-variable"
            else advisory_mismatches
        ),
        variable_name=DEFAULT_GATEWAY_URL_VARIABLE,
        actual=variable_gateway_url.rstrip("/"),
        expected=resolved.gateway_url,
    )
    _append_variable_mismatch(
        mismatches=(
            required_mismatches
            if resolved.expected_environment_source == "repository-variable"
            else advisory_mismatches
        ),
        variable_name=DEFAULT_EXPECTED_ENVIRONMENT_VARIABLE,
        actual=variable_environment,
        expected=resolved.expected_environment,
    )
    if required_mismatches:
        return ReadinessStep(
            "repository variables",
            False,
            f"mismatched={required_mismatches}",
        )
    if advisory_mismatches:
        return ReadinessStep(
            "repository variables",
            True,
            f"not-required advisory_mismatched={advisory_mismatches}",
        )
    return ReadinessStep("repository variables", True, "matched")


def _append_variable_mismatch(
    *,
    mismatches: list[str],
    variable_name: str,
    actual: str,
    expected: str,
) -> None:
    if actual != expected:
        mismatches.append(variable_name)


def _check_secret(
    *,
    step_name: str,
    secret_name: str,
    required: bool,
    secrets: frozenset[str],
) -> ReadinessStep:
    if not required:
        return ReadinessStep(step_name, True, "not-required")
    if secret_name not in secrets:
        return ReadinessStep(step_name, False, f"missing={secret_name}")
    return ReadinessStep(step_name, True, "present")


def _check_workflow(
    *,
    repository: str,
    workflow_file: str,
    workflow_name: str,
    runner: CommandRunner,
) -> ReadinessStep:
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
            return ReadinessStep(
                "gateway publication workflow",
                state == "active",
                f"state={state}",
            )
    return ReadinessStep("gateway publication workflow", False, "missing")


def _check_dns(*, host: str, resolver: Resolver) -> ReadinessStep:
    try:
        addresses = resolver(host)
    except OSError as exc:
        return ReadinessStep("dns resolution", False, f"failed:{exc}")
    if not addresses:
        return ReadinessStep("dns resolution", False, "no addresses")
    return ReadinessStep("dns resolution", True, f"addresses={list(addresses)}")


def _build_next_command(
    *,
    gateway_host: str,
    gateway_url: str,
    expected_environment: str,
    apply_ingress: bool,
    dispatch_witness: bool,
    skip_preflight_endpoint_probes: bool,
) -> str:
    command = [
        "python",
        "scripts/dispatch_gateway_publication.py",
        "--gateway-host",
        gateway_host,
        "--gateway-url",
        gateway_url,
        "--expected-environment",
        expected_environment,
    ]
    if apply_ingress:
        command.append("--apply-ingress")
    if dispatch_witness:
        command.append("--dispatch-witness")
    if skip_preflight_endpoint_probes:
        command.append("--skip-preflight-endpoint-probes")
    return " ".join(shlex.quote(part) for part in command)


def _normalize_gateway_url(gateway_url: str) -> str:
    normalized = gateway_url.strip().rstrip("/")
    if not normalized:
        return ""
    if not normalized.startswith(("https://", "http://")):
        raise RuntimeError("gateway URL must start with http:// or https://")
    return normalized


def _derive_host_from_url(gateway_url: str) -> str:
    if not gateway_url:
        raise RuntimeError("gateway host or gateway URL is required")
    parsed = urlparse(gateway_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("gateway URL must include scheme and hostname")
    return _require_gateway_host(parsed.hostname)


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


def _read_secret_names(*, repository: str, runner: CommandRunner) -> frozenset[str]:
    completed = _run_checked(
        runner,
        ["gh", "secret", "list", "--repo", repository, "--json", "name"],
    )
    return frozenset(
        str(secret.get("name", ""))
        for secret in _json_list(completed.stdout, "gh secret list")
    )


def _resolve_host(host: str) -> tuple[str, ...]:
    addresses = {
        str(result[4][0])
        for result in socket.getaddrinfo(host, None)
        if result[4] and result[4][0]
    }
    return tuple(sorted(addresses))


def _run_checked(
    runner: CommandRunner,
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    try:
        return runner(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("GitHub CLI executable 'gh' was not found") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        stdout = exc.stdout.strip() if exc.stdout else ""
        detail = stderr or stdout or f"exit code {exc.returncode}"
        raise RuntimeError(f"command failed: {' '.join(command)}: {detail}") from exc


def _json_list(raw_text: str, command_name: str) -> list[dict[str, Any]]:
    parsed = _loads_json(raw_text, command_name)
    if not isinstance(parsed, list) or not all(
        isinstance(item, dict) for item in parsed
    ):
        raise RuntimeError(f"{command_name} did not return a JSON object list")
    return parsed


def _loads_json(raw_text: str, command_name: str) -> Any:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{command_name} returned invalid JSON") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse gateway publication readiness CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Report gateway publication readiness without dispatch."
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
    parser.add_argument("--workflow-file", default=DEFAULT_WORKFLOW_FILE)
    parser.add_argument("--workflow-name", default=DEFAULT_WORKFLOW_NAME)
    parser.add_argument("--runtime-secret-name", default=DEFAULT_RUNTIME_SECRET_NAME)
    parser.add_argument("--kubeconfig-secret-name", default=DEFAULT_KUBECONFIG_SECRET_NAME)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for gateway publication readiness reporting."""
    args = parse_args(argv)
    try:
        report = report_gateway_publication_readiness(
            gateway_host=args.gateway_host,
            gateway_url=args.gateway_url,
            expected_environment=args.expected_environment,
            repository=args.repo,
            apply_ingress=args.apply_ingress,
            dispatch_witness=args.dispatch_witness,
            skip_preflight_endpoint_probes=args.skip_preflight_endpoint_probes,
            workflow_file=args.workflow_file,
            workflow_name=args.workflow_name,
            runtime_secret_name=args.runtime_secret_name,
            kubeconfig_secret_name=args.kubeconfig_secret_name,
        )
    except RuntimeError as exc:
        print(f"gateway publication readiness failed: {exc}")
        return 1

    output_path = write_gateway_publication_readiness(report, Path(args.output))
    print(f"readiness_report: {output_path}")
    print(f"gateway_host: {report.gateway_host}")
    print(f"gateway_url: {report.gateway_url}")
    print(f"expected_environment: {report.expected_environment}")
    print(f"ready: {str(report.ready).lower()}")
    print(f"next_command: {report.next_command}")
    for step in report.steps:
        print(f"step: {step.name} passed={str(step.passed).lower()} detail={step.detail}")
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
