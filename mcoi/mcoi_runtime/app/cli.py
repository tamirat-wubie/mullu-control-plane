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
import sys
from pathlib import Path

from .bootstrap import bootstrap_runtime
from .config import AppConfig
from .console import (
    render_execution_summary,
    render_run_summary,
)
from .operator_loop import OperatorLoop, OperatorRequest
from .policy_packs import PolicyPackRegistry
from .profiles import ProfileLoadError, load_profile, list_profiles
from .view_models import ExecutionSummaryView, RunSummaryView


def _resolve_config(args: argparse.Namespace) -> AppConfig:
    """Resolve config from --profile or --config, with profile taking precedence."""
    if hasattr(args, "profile") and args.profile:
        try:
            result = load_profile(args.profile)
            return result.config
        except ProfileLoadError as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(1)
    if hasattr(args, "config") and args.config:
        return _load_config(args.config)
    return AppConfig()


def run_command(args: argparse.Namespace) -> int:
    """Execute a single operator request from a JSON file or inline JSON."""
    config = _resolve_config(args)
    runtime = bootstrap_runtime(config=config)
    loop = OperatorLoop(runtime=runtime)

    request_data = _load_request(args.request)
    request = OperatorRequest(
        request_id=request_data.get("request_id", "cli-request"),
        subject_id=request_data.get("subject_id", "cli-operator"),
        goal_id=request_data.get("goal_id", "cli-goal"),
        template=request_data.get("template", {}),
        bindings=request_data.get("bindings", {}),
    )

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


def _load_config(path: str) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        print(f"error: config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return AppConfig.from_mapping(data)


def _load_request(source: str) -> dict:
    if source.startswith("{"):
        return json.loads(source)
    path = Path(source)
    if not path.exists():
        print(f"error: request file not found: {source}", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcoi",
        description="MCOI Operator Runtime CLI",
    )
    parser.add_argument("--config", help="Path to config JSON file")
    parser.add_argument("--profile", help="Named configuration profile (e.g., local-dev, safe-readonly)")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Execute a single operator request")
    run_parser.add_argument("request", help="JSON file path or inline JSON string")

    subparsers.add_parser("status", help="Show runtime status")
    subparsers.add_parser("profiles", help="List available configuration profiles")
    subparsers.add_parser("packs", help="List available policy packs")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    commands = {
        "run": run_command,
        "status": status_command,
        "profiles": profiles_command,
        "packs": packs_command,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
