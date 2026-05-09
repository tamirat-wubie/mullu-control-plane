"""God-mode break-glass CLI.

Records a registration agreement against a god capability without going
through the HTTP surface. Used when the platform is offline or when the
operator wants an out-of-band consent record (e.g. during incident
response when the API is unreachable).

Usage:
    python scripts/god_mode_agree.py list
    python scripts/god_mode_agree.py describe replay mutate_recorder
    python scripts/god_mode_agree.py agree replay mutate_recorder \\
        --actor alice \\
        --justification "..." \\
        [--out path/to/agreement.json]
    python scripts/god_mode_agree.py state replay mutate_recorder

The CLI does NOT modify durable platform state — it operates against the
process-local registry seeded with the default capability proposals. Its
output is a JSON agreement record that the operator can attach to the
incident ticket as evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _bootstrap_paths() -> None:
    """Add `mcoi/` to sys.path so the runtime imports resolve."""
    here = Path(__file__).resolve().parent
    candidates = [here.parent / "mcoi", here.parent]
    for path in candidates:
        if (path / "mcoi_runtime").is_dir() and str(path) not in sys.path:
            sys.path.insert(0, str(path))


_bootstrap_paths()


# Imports must follow path bootstrapping.
from mcoi_runtime.contracts.god_mode import GodCapabilityState  # noqa: E402
from mcoi_runtime.core.god_mode_integration import (  # noqa: E402
    install_default_capabilities,
)
from mcoi_runtime.core.god_mode_registry import (  # noqa: E402
    GodModeRegistry,
    GodModeRegistryError,
)


def _build_registry() -> GodModeRegistry:
    registry = GodModeRegistry()
    install_default_capabilities(registry)
    return registry


def cmd_list(_args: argparse.Namespace) -> int:
    registry = _build_registry()
    by_module: dict[str, list[dict[str, object]]] = {}
    for cap in registry.list_capabilities():
        by_module.setdefault(cap.module, []).append(
            {
                "name": cap.name,
                "blast_radius": cap.blast_radius.value,
                "default_ttl_seconds": cap.default_ttl_seconds,
                "min_justification_chars": cap.min_justification_chars,
                "bypasses": list(cap.bypasses),
            }
        )
    print(json.dumps({"modules": by_module}, indent=2, sort_keys=True))
    return 0


def cmd_describe(args: argparse.Namespace) -> int:
    registry = _build_registry()
    try:
        cap = registry.get_capability(args.module, args.name)
    except GodModeRegistryError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "capability": cap.to_json_dict(),
                "state": registry.state_of(cap.module, cap.name).value,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def cmd_state(args: argparse.Namespace) -> int:
    registry = _build_registry()
    try:
        state = registry.state_of(args.module, args.name)
    except GodModeRegistryError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    # Process-local registry is always DORMANT — this is a read-only view.
    print(json.dumps({"state": state.value}))
    return 0 if state == GodCapabilityState.DORMANT else 0


def cmd_agree(args: argparse.Namespace) -> int:
    registry = _build_registry()
    if not registry.has_capability(args.module, args.name):
        print(
            json.dumps(
                {"error": f"unknown capability {args.module}.{args.name}"}
            ),
            file=sys.stderr,
        )
        return 2
    if not args.justification or len(args.justification.strip()) < 50:
        print(
            json.dumps(
                {"error": "justification must be at least 50 chars"}
            ),
            file=sys.stderr,
        )
        return 2
    try:
        agreement = registry.agree_to_register(
            module=args.module,
            name=args.name,
            actor_id=args.actor,
            justification=args.justification,
        )
    except GodModeRegistryError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    payload = {
        "agreement": agreement.to_json_dict(),
        "capability": registry.get_capability(args.module, args.name).to_json_dict(),
        "note": (
            "This agreement is process-local and does not arm the platform "
            "registry. Replay it against the running platform via "
            "POST /api/v1/god-mode/capabilities/{module}/{name}/agree-to-register."
        ),
    }
    body = json.dumps(payload, indent=2, sort_keys=True)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body, encoding="utf-8")
        print(json.dumps({"written": str(out_path)}))
    else:
        print(body)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="god_mode_agree",
        description="Offline break-glass CLI for god-mode agreements.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub_list = sub.add_parser("list", help="List all god capabilities, grouped by module")
    sub_list.set_defaults(func=cmd_list)

    sub_desc = sub.add_parser("describe", help="Show one capability descriptor")
    sub_desc.add_argument("module")
    sub_desc.add_argument("name")
    sub_desc.set_defaults(func=cmd_describe)

    sub_state = sub.add_parser("state", help="Show one capability state")
    sub_state.add_argument("module")
    sub_state.add_argument("name")
    sub_state.set_defaults(func=cmd_state)

    sub_agree = sub.add_parser("agree", help="Record a registration agreement")
    sub_agree.add_argument("module")
    sub_agree.add_argument("name")
    sub_agree.add_argument("--actor", required=True, help="Operator identity")
    sub_agree.add_argument(
        "--justification",
        required=True,
        help="Free-text justification (≥50 chars; some capabilities require more)",
    )
    sub_agree.add_argument("--out", help="Path to write the agreement JSON")
    sub_agree.set_defaults(func=cmd_agree)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
