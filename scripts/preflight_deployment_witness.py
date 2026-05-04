#!/usr/bin/env python3
"""Preflight deployment witness readiness without dispatching the workflow.

Purpose: verify DNS, GitHub runtime inputs, workflow readiness, and gateway
endpoint contracts before an operator applies ingress or dispatches evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: GitHub CLI for repository metadata, DNS resolution, standard
library HTTP client for endpoint probes.
Invariants:
  - Runtime witness and conformance secret values are never read or printed.
  - Mounted runtime and conformance secrets can witness presence without listing
    secrets.
  - Workflow dispatch is never performed by this preflight.
  - Each readiness transition is represented as an explicit step.
  - Endpoint probes are opt-out and report bounded failure detail.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
import urllib.error
import urllib.request

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.collect_deployment_witness import REQUIRED_CONFORMANCE_FIELDS, REQUIRED_WITNESS_FIELDS  # noqa: E402
from scripts.dispatch_deployment_witness import (  # noqa: E402
    DEFAULT_CONFORMANCE_SECRET_NAME,
    DEFAULT_EXPECTED_ENVIRONMENT_VARIABLE,
    DEFAULT_GATEWAY_URL_VARIABLE,
    DEFAULT_REPOSITORY,
    DEFAULT_SECRET_NAME,
    DEFAULT_WORKFLOW_FILE,
    DEFAULT_WORKFLOW_NAME,
    VALID_ENVIRONMENTS,
)
from scripts.render_gateway_ingress import PLACEHOLDER_HOST  # noqa: E402
from scripts.validate_mcp_capability_manifest import validate_mcp_capability_manifest  # noqa: E402

DEFAULT_OUTPUT = Path(".change_assurance") / "deployment_witness_preflight.json"


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
JsonGetter = Callable[[str], tuple[int, dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class PreflightStep:
    """One deployment witness readiness step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class DeploymentWitnessPreflight:
    """Structured deployment witness preflight report."""

    repository: str
    gateway_host: str
    gateway_url: str
    expected_environment: str
    ready: bool
    steps: tuple[PreflightStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable preflight payload."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def preflight_deployment_witness(
    *,
    gateway_host: str,
    expected_environment: str,
    gateway_url: str = "",
    repository: str = DEFAULT_REPOSITORY,
    workflow_file: str = DEFAULT_WORKFLOW_FILE,
    workflow_name: str = DEFAULT_WORKFLOW_NAME,
    secret_name: str = DEFAULT_SECRET_NAME,
    conformance_secret_name: str = DEFAULT_CONFORMANCE_SECRET_NAME,
    runtime_secret_present: bool = False,
    conformance_secret_present: bool = False,
    mcp_capability_manifest_path: str = "",
    probe_endpoints: bool = True,
    runner: CommandRunner | None = None,
    resolver: Resolver | None = None,
    json_getter: JsonGetter | None = None,
) -> DeploymentWitnessPreflight:
    """Verify deployment witness readiness without mutating remote state."""
    command_runner = runner or subprocess.run
    dns_resolver = resolver or _resolve_host
    endpoint_getter = json_getter or _get_json
    normalized_host = _require_gateway_host(gateway_host)
    normalized_url = _require_gateway_url(gateway_url or f"https://{normalized_host}")
    _require_expected_environment(expected_environment)

    steps = [
        _check_dns(host=normalized_host, resolver=dns_resolver),
        _check_repository_variables(
            repository=repository,
            gateway_url=normalized_url,
            expected_environment=expected_environment,
            runner=command_runner,
        ),
        _check_secret(
            repository=repository,
            secret_name=secret_name,
            secret_present=runtime_secret_present,
            step_name="runtime witness secret",
            runner=command_runner,
        ),
        _check_secret(
            repository=repository,
            secret_name=conformance_secret_name,
            secret_present=conformance_secret_present,
            step_name="runtime conformance secret",
            runner=command_runner,
        ),
        _check_workflow(
            repository=repository,
            workflow_file=workflow_file,
            workflow_name=workflow_name,
            runner=command_runner,
        ),
    ]
    if mcp_capability_manifest_path.strip():
        steps.append(_check_mcp_capability_manifest(Path(mcp_capability_manifest_path)))
    if probe_endpoints:
        steps.extend(
            (
                _check_health_endpoint(gateway_url=normalized_url, json_getter=endpoint_getter),
                _check_runtime_witness_endpoint(
                    gateway_url=normalized_url,
                    expected_environment=expected_environment,
                    json_getter=endpoint_getter,
                ),
                _check_runtime_conformance_endpoint(
                    gateway_url=normalized_url,
                    expected_environment=expected_environment,
                    json_getter=endpoint_getter,
                ),
            )
        )

    return DeploymentWitnessPreflight(
        repository=repository,
        gateway_host=normalized_host,
        gateway_url=normalized_url,
        expected_environment=expected_environment,
        ready=all(step.passed for step in steps),
        steps=tuple(steps),
    )


def write_preflight_report(report: DeploymentWitnessPreflight, output_path: Path) -> Path:
    """Write one deployment witness preflight report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


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
    if "." not in host:
        raise RuntimeError("gateway host must be a fully qualified DNS name")
    return host


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


def _check_dns(*, host: str, resolver: Resolver) -> PreflightStep:
    try:
        addresses = resolver(host)
    except OSError as exc:
        return PreflightStep("dns resolution", False, f"failed:{exc}")
    if not addresses:
        return PreflightStep("dns resolution", False, "no addresses")
    return PreflightStep("dns resolution", True, f"addresses={list(addresses)}")


def _check_repository_variables(
    *,
    repository: str,
    gateway_url: str,
    expected_environment: str,
    runner: CommandRunner,
) -> PreflightStep:
    completed = _run_checked(
        runner,
        ["gh", "variable", "list", "--repo", repository, "--json", "name,value"],
    )
    variables = {
        str(variable.get("name", "")): str(variable.get("value", ""))
        for variable in _json_list(completed.stdout, "gh variable list")
    }
    mismatches: list[str] = []
    if variables.get(DEFAULT_GATEWAY_URL_VARIABLE, "").rstrip("/") != gateway_url:
        mismatches.append(DEFAULT_GATEWAY_URL_VARIABLE)
    if variables.get(DEFAULT_EXPECTED_ENVIRONMENT_VARIABLE, "") != expected_environment:
        mismatches.append(DEFAULT_EXPECTED_ENVIRONMENT_VARIABLE)
    if mismatches:
        return PreflightStep("repository variables", False, f"mismatched={mismatches}")
    return PreflightStep("repository variables", True, "matched")


def _check_secret(
    *,
    repository: str,
    secret_name: str,
    secret_present: bool,
    step_name: str,
    runner: CommandRunner,
) -> PreflightStep:
    if secret_present:
        return PreflightStep(step_name, True, "present:mounted-environment")
    completed = _run_checked(
        runner,
        ["gh", "secret", "list", "--repo", repository, "--json", "name"],
    )
    names = {str(secret.get("name", "")) for secret in _json_list(completed.stdout, "gh secret list")}
    if secret_name not in names:
        return PreflightStep(step_name, False, f"missing={secret_name}")
    return PreflightStep(step_name, True, "present")


def _check_workflow(
    *,
    repository: str,
    workflow_file: str,
    workflow_name: str,
    runner: CommandRunner,
) -> PreflightStep:
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
            return PreflightStep(
                "deployment witness workflow",
                state == "active",
                f"state={state}",
            )
    return PreflightStep("deployment witness workflow", False, "missing")


def _check_mcp_capability_manifest(manifest_path: Path) -> PreflightStep:
    result = validate_mcp_capability_manifest(manifest_path)
    detail = (
        f"valid={result.ok} capabilities={len(result.capability_ids)} "
        f"ownership={len(result.ownership_resource_refs)} "
        f"approval_policies={len(result.approval_policy_ids)} "
        f"escalation_policies={len(result.escalation_policy_ids)} "
        f"errors={list(result.errors)}"
    )
    return PreflightStep("mcp capability manifest", result.ok, detail)


def _check_health_endpoint(*, gateway_url: str, json_getter: JsonGetter) -> PreflightStep:
    status, payload = json_getter(f"{gateway_url}/health")
    body_status = str(payload.get("status", ""))
    return PreflightStep(
        "gateway health endpoint",
        status == 200 and body_status == "healthy",
        f"status={status} body_status={body_status}",
    )


def _check_runtime_witness_endpoint(
    *,
    gateway_url: str,
    expected_environment: str,
    json_getter: JsonGetter,
) -> PreflightStep:
    status, payload = json_getter(f"{gateway_url}/gateway/witness")
    missing_fields = [field for field in REQUIRED_WITNESS_FIELDS if field not in payload]
    runtime_status = str(payload.get("runtime_status", ""))
    gateway_status = str(payload.get("gateway_status", ""))
    runtime_environment = str(payload.get("environment", ""))
    responsibility_debt_clear = payload.get("responsibility_debt_clear") is True
    passed = (
        status == 200
        and not missing_fields
        and runtime_status == "healthy"
        and gateway_status in {"healthy", "degraded"}
        and responsibility_debt_clear
        and runtime_environment == expected_environment
    )
    return PreflightStep(
        "gateway runtime witness endpoint",
        passed,
        (
            f"status={status} runtime_status={runtime_status} "
            f"gateway_status={gateway_status} environment={runtime_environment} "
            f"responsibility_debt_clear={responsibility_debt_clear} "
            f"missing={missing_fields}"
        ),
    )


def _check_runtime_conformance_endpoint(
    *,
    gateway_url: str,
    expected_environment: str,
    json_getter: JsonGetter,
) -> PreflightStep:
    status, payload = json_getter(f"{gateway_url}/runtime/conformance")
    missing_fields = [field for field in REQUIRED_CONFORMANCE_FIELDS if field not in payload]
    terminal_status = str(payload.get("terminal_status", ""))
    runtime_environment = str(payload.get("environment", ""))
    fresh = _certificate_fresh(str(payload.get("expires_at", "")))
    mcp_manifest_configured = bool(payload.get("mcp_capability_manifest_configured"))
    mcp_manifest_valid = bool(payload.get("mcp_capability_manifest_valid"))
    mcp_manifest_passed = (not mcp_manifest_configured) or mcp_manifest_valid
    plan_bundle_passed = bool(payload.get("capability_plan_bundle_canary_passed"))
    passed = (
        status == 200
        and not missing_fields
        and terminal_status in {"conformant", "conformant_with_gaps"}
        and bool(payload.get("gateway_witness_valid"))
        and bool(payload.get("runtime_witness_valid"))
        and bool(payload.get("authority_responsibility_debt_clear"))
        and mcp_manifest_passed
        and plan_bundle_passed
        and runtime_environment == expected_environment
        and fresh
    )
    return PreflightStep(
        "runtime conformance endpoint",
        passed,
        (
            f"status={status} terminal_status={terminal_status} "
            f"environment={runtime_environment} fresh={fresh} "
            f"responsibility_debt_clear={bool(payload.get('authority_responsibility_debt_clear'))} "
            f"mcp_manifest_configured={mcp_manifest_configured} "
            f"mcp_manifest_valid={mcp_manifest_valid} "
            f"plan_bundle_passed={plan_bundle_passed} "
            f"missing={missing_fields}"
        ),
    )


def _certificate_fresh(expires_at: str) -> bool:
    try:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires > datetime.now(timezone.utc)


def _resolve_host(host: str) -> tuple[str, ...]:
    addresses = {
        str(result[4][0])
        for result in socket.getaddrinfo(host, None)
        if result[4] and result[4][0]
    }
    return tuple(sorted(addresses))


def _get_json(url: str) -> tuple[int, dict[str, Any]]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, _loads_json(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _loads_json(exc.read())
    except (urllib.error.URLError, TimeoutError):
        return 0, {}


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
    parsed = _loads_text_json(raw_text, command_name)
    if not isinstance(parsed, list) or not all(
        isinstance(item, dict) for item in parsed
    ):
        raise RuntimeError(f"{command_name} did not return a JSON object list")
    return parsed


def _loads_text_json(raw_text: str, command_name: str) -> Any:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{command_name} returned invalid JSON") from exc


def _loads_json(raw: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse deployment witness preflight CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Preflight deployment witness readiness without dispatch."
    )
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY))
    parser.add_argument("--gateway-host", default=os.environ.get("MULLU_GATEWAY_HOST", ""))
    parser.add_argument("--gateway-url", default=os.environ.get("MULLU_GATEWAY_URL", ""))
    parser.add_argument(
        "--expected-environment",
        choices=VALID_ENVIRONMENTS,
        default=os.environ.get("MULLU_EXPECTED_RUNTIME_ENV", "pilot"),
    )
    parser.add_argument("--workflow-file", default=DEFAULT_WORKFLOW_FILE)
    parser.add_argument("--workflow-name", default=DEFAULT_WORKFLOW_NAME)
    parser.add_argument("--secret-name", default=DEFAULT_SECRET_NAME)
    parser.add_argument("--conformance-secret-name", default=DEFAULT_CONFORMANCE_SECRET_NAME)
    parser.add_argument("--accept-runtime-secret-env", action="store_true")
    parser.add_argument("--accept-conformance-secret-env", action="store_true")
    parser.add_argument(
        "--mcp-capability-manifest",
        default=os.environ.get("MULLU_MCP_CAPABILITY_MANIFEST_PATH", ""),
    )
    parser.add_argument("--skip-endpoint-probes", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for deployment witness preflight."""
    args = parse_args(argv)
    try:
        report = preflight_deployment_witness(
            gateway_host=args.gateway_host,
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
            mcp_capability_manifest_path=args.mcp_capability_manifest,
            probe_endpoints=not args.skip_endpoint_probes,
        )
    except RuntimeError as exc:
        print(f"deployment witness preflight failed: {exc}")
        return 1

    output_path = write_preflight_report(report, Path(args.output))
    print(f"preflight_report: {output_path}")
    print(f"gateway_host: {report.gateway_host}")
    print(f"gateway_url: {report.gateway_url}")
    print(f"expected_environment: {report.expected_environment}")
    print(f"ready: {str(report.ready).lower()}")
    for step in report.steps:
        print(f"step: {step.name} passed={str(step.passed).lower()} detail={step.detail}")
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
