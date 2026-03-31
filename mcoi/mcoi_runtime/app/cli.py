"""Purpose: CLI entrypoint for the MCOI operator runtime.
Governance scope: operator-facing CLI only.
Dependencies: bootstrap, operator loop, console renderer, profiles, policy packs.
Invariants:
  - CLI is a thin shell over the operator loop.
  - No hidden behavior beyond what the operator loop provides.
  - All output is through the console renderer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, NoReturn

from .bootstrap import bootstrap_runtime
from .config import AppConfig
from .console import (
    render_execution_summary,
    render_run_summary,
)
from .operator_models import OperatorRequest
from .operator_loop import OperatorLoop
from .policy_packs import PolicyPackRegistry
from .profiles import ProfileLoadError, load_profile, list_profiles
from .view_models import ExecutionSummaryView, RunSummaryView
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


_REQUEST_ALLOWED_KEYS = frozenset(
    {
        "request_id",
        "subject_id",
        "goal_id",
        "template",
        "bindings",
    }
)


def _fatal(message: str) -> NoReturn:
    """Print a CLI error and terminate deterministically."""
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def _runtime_bindings() -> dict[str, str]:
    """Return explicit runtime bindings exposed by the CLI.

    These bindings keep shipped example requests portable across environments
    without weakening template validation or adapter boundaries.
    """
    interpreter = os.environ.get("MCOI_PYTHON_EXECUTABLE", sys.executable)
    return {"python_executable": interpreter}


def _resolve_bindings(request_data: dict) -> object:
    """Merge caller bindings with explicit CLI runtime bindings.

    If the supplied payload is malformed, preserve it so the operator-loop
    validation path still fails explicitly.
    """
    bindings = request_data.get("bindings", {})
    if bindings is None:
        return _runtime_bindings()
    if not isinstance(bindings, dict):
        return bindings
    merged = _runtime_bindings()
    merged.update(bindings)
    return merged


def _required_text_field(
    payload: Mapping[str, Any],
    *,
    field_name: str,
    kind: str,
    source_name: str,
) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{kind} field '{field_name}' must be a non-empty string in {source_name}")
    return value


def _build_operator_request(
    payload: Mapping[str, Any],
    *,
    source_name: str,
) -> OperatorRequest:
    if not isinstance(payload, Mapping):
        raise ValueError(f"request payload must be an object in {source_name}")

    unknown_keys = sorted(set(payload) - _REQUEST_ALLOWED_KEYS)
    if unknown_keys:
        joined = ", ".join(unknown_keys)
        raise ValueError(f"unsupported request fields in {source_name}: {joined}")

    template = payload.get("template")
    if not isinstance(template, Mapping):
        raise ValueError(f"request field 'template' must be an object in {source_name}")

    if "bindings" not in payload:
        raise ValueError(f"request field 'bindings' is required in {source_name}")

    bindings = payload.get("bindings")
    if not isinstance(bindings, Mapping):
        raise ValueError(f"request field 'bindings' must be an object in {source_name}")

    resolved_bindings = _resolve_bindings(dict(payload))
    if not isinstance(resolved_bindings, Mapping):
        raise ValueError(f"request field 'bindings' must be an object in {source_name}")

    try:
        return OperatorRequest(
            request_id=_required_text_field(
                payload,
                field_name="request_id",
                kind="request",
                source_name=source_name,
            ),
            subject_id=_required_text_field(
                payload,
                field_name="subject_id",
                kind="request",
                source_name=source_name,
            ),
            goal_id=_required_text_field(
                payload,
                field_name="goal_id",
                kind="request",
                source_name=source_name,
            ),
            template=template,
            bindings=resolved_bindings,
        )
    except RuntimeCoreInvariantError as exc:
        raise ValueError(str(exc)) from exc


def _resolve_config(args: argparse.Namespace) -> AppConfig:
    """Resolve config from --profile or --config, with profile taking precedence."""
    if hasattr(args, "profile") and args.profile:
        try:
            result = load_profile(args.profile)
            return result.config
        except ProfileLoadError as exc:
            _fatal(str(exc))
    if hasattr(args, "config") and args.config:
        return _load_config(args.config)
    return AppConfig()


def run_command(args: argparse.Namespace) -> int:
    """Execute a single operator request from a JSON file or inline JSON."""
    config = _resolve_config(args)
    runtime = bootstrap_runtime(config=config)
    loop = OperatorLoop(runtime=runtime)

    request_data = _load_request(args.request)
    request_source = "inline input" if args.request.lstrip().startswith(("{", "[")) else args.request
    try:
        request = _build_operator_request(request_data, source_name=request_source)
    except ValueError as exc:
        _fatal(str(exc))

    report = loop.run_step(request)

    run_view = RunSummaryView.from_report(report)
    print(render_run_summary(run_view))
    print()
    exec_view = ExecutionSummaryView.from_report(report)
    print(render_execution_summary(exec_view))

    return 0 if report.completed else 1


def status_command(args: argparse.Namespace) -> int:
    """Show runtime status."""
    config = _resolve_config(args)
    runtime = bootstrap_runtime(config=config)

    lines = [
        "=== MCOI Runtime Status ===",
        f"  executor_routes:    {', '.join(config.enabled_executor_routes)}",
        f"  observer_routes:    {', '.join(config.enabled_observer_routes)}",
        f"  planning_classes:   {', '.join(config.allowed_planning_classes)}",
        f"  providers:          {len(runtime.provider_registry.list_providers())}",
    ]
    print("\n".join(lines))
    return 0


def profiles_command(args: argparse.Namespace) -> int:
    """List available configuration profiles."""
    profiles = list_profiles()
    print("=== Available Profiles ===")
    for name in profiles:
        print(f"  {name}")
    return 0


def packs_command(args: argparse.Namespace) -> int:
    """List available policy packs."""
    registry = PolicyPackRegistry()
    packs = registry.list_packs()
    print("=== Available Policy Packs ===")
    for pack in packs:
        print(f"  {pack.pack_id}: {pack.name}")
        print(f"    {pack.description}")
        print(f"    rules: {len(pack.rules)}")
    return 0


def _load_json_object(*, content: str, kind: str, source_name: str) -> dict:
    """Load a JSON object and fail closed on malformed or non-object input."""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        _fatal(f"invalid {kind} JSON in {source_name}: {exc.msg}")
    if not isinstance(payload, dict):
        _fatal(f"{kind} JSON root must be an object in {source_name}")
    return payload


def _load_config(path: str) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        _fatal(f"config file not found: {path}")
    try:
        content = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        _fatal(f"cannot read config file {path}: {exc}")
    data = _load_json_object(content=content, kind="config", source_name=path)
    try:
        return AppConfig.from_mapping(data)
    except (TypeError, ValueError) as exc:
        _fatal(f"invalid config file {path}: {exc}")


def _load_request(source: str) -> dict:
    stripped_source = source.lstrip()
    if stripped_source.startswith("{") or stripped_source.startswith("["):
        return _load_json_object(content=source, kind="request", source_name="inline input")
    path = Path(source)
    if not path.exists():
        _fatal(f"request file not found: {source}")
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        _fatal(f"cannot read request file {source}: {exc}")
    return _load_json_object(content=content, kind="request", source_name=source)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcoi",
        description="MCOI Operator Runtime CLI",
    )
    parser.add_argument("--config", help="Path to config JSON file")
    profile_names = ", ".join(list_profiles())
    parser.add_argument(
        "--profile",
        help=f"Named configuration profile ({profile_names})",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Execute a single operator request")
    run_parser.add_argument("request", help="JSON file path or inline JSON string")

    subparsers.add_parser("status", help="Show runtime status")
    subparsers.add_parser("profiles", help="List available configuration profiles")
    subparsers.add_parser("packs", help="List available policy packs")
    subparsers.add_parser("init", help="Initialize a new Mullu project in current directory")
    subparsers.add_parser("demo", help="Run a governed demo showing allow/deny flow")

    return parser


def init_command(args: argparse.Namespace) -> int:
    """Initialize a new Mullu Control Plane project in the current directory."""
    import json as _json
    from pathlib import Path
    from hashlib import sha256

    config_path = Path("mullu.json")
    if config_path.exists():
        print(f"  mullu.json already exists in {Path.cwd()}")
        return 1

    api_key = f"mcp-{sha256(f'init:{Path.cwd()}:{__import__('time').time()}'.encode()).hexdigest()[:24]}"

    config = {
        "version": "1.0.0",
        "environment": "local_dev",
        "api_url": "http://localhost:8000",
        "api_key": api_key,
        "policy_pack": "default-safe",
        "database": "sqlite",
        "providers": {
            "default": "stub",
            "note": "Set ANTHROPIC_API_KEY or OPENAI_API_KEY for real providers",
        },
    }
    config_path.write_text(_json.dumps(config, indent=2) + "\n")

    print()
    print("  Mullu Control Plane initialized")
    print()
    print(f"  Config:     {config_path.resolve()}")
    print(f"  API URL:    {config['api_url']}")
    print(f"  API Key:    {api_key}")
    print(f"  Policy:     {config['policy_pack']}")
    print()
    print("  Next steps:")
    print("    uvicorn mcoi_runtime.app.server:app --port 8000")
    print("    mcoi demo")
    print()
    return 0


def demo_command(args: argparse.Namespace) -> int:
    """Run a quick governed demo — register agent, allow action, deny action."""
    import json as _json
    import urllib.request
    import urllib.error

    base = "http://localhost:8000"

    # Check server
    try:
        urllib.request.urlopen(f"{base}/health", timeout=3)
    except Exception:
        print(f"  Server not reachable at {base}")
        print("  Start with: uvicorn mcoi_runtime.app.server:app --port 8000")
        return 1

    def post(path: str, data: dict) -> tuple[int, dict]:
        body = _json.dumps(data).encode()
        req = urllib.request.Request(f"{base}{path}", data=body, headers={"Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            return resp.status, _json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, _json.loads(e.read().decode()) if e.fp else {}

    print()
    print("  Mullu Control Plane — Governed Agent Demo")
    print("  " + "=" * 45)

    # 1. Register agent
    code, data = post("/api/v1/agent/register", {
        "agent_name": "demo-agent",
        "capabilities": ["file_read", "shell_execute"],
    })
    agent_id = data.get("agent_id", "unknown")
    print(f"  [1] Register agent: {agent_id}")

    # 2. Request allowed action
    code, data = post("/api/v1/agent/action-request", {
        "agent_id": agent_id,
        "action_type": "file_read",
        "target": "/tmp/safe-file.txt",
        "tenant_id": "demo-tenant",
    })
    decision = data.get("decision", "unknown")
    print(f"  [2] Action request (file_read): {decision}")

    # 3. Submit result
    action_id = data.get("action_id", "")
    if action_id:
        post("/api/v1/agent/action-result", {
            "agent_id": agent_id,
            "action_id": action_id,
            "outcome": "success",
            "result": {"content": "file contents here"},
        })
        print("  [3] Action result submitted: success")

    # 4. Check audit trail
    try:
        resp = urllib.request.urlopen(f"{base}/api/v1/audit?action=agent.adapter.action_request&limit=5", timeout=5)
        audit = _json.loads(resp.read())
        print(f"  [4] Audit trail: {audit.get('count', 0)} governed actions recorded")
    except Exception:
        print("  [4] Audit trail: (check failed)")

    # 5. Heartbeat
    post("/api/v1/agent/heartbeat", {"agent_id": agent_id, "status": "healthy"})
    print("  [5] Heartbeat sent: healthy")

    print("  " + "=" * 45)
    print("  Demo complete. Agent governed, actions audited.")
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    commands = {
        "run": run_command,
        "status": status_command,
        "profiles": profiles_command,
        "packs": packs_command,
        "init": init_command,
        "demo": demo_command,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
