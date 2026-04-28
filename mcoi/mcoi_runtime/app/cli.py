"""Purpose: CLI entrypoint for the MCOI operator runtime.
Governance scope: operator-facing CLI only.
Dependencies: bootstrap, operator loop, console renderer, profiles, policy packs,
pilot scaffold generation.
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
from .pilot_init import PilotInitRequest, initialize_pilot
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

_SAFE_CONFIG_ERROR_PREFIXES = (
    "config values must be a mapping",
    "unknown config keys",
    "config values must be non-empty strings",
    "config values must be sequences of non-empty strings",
    "config values must contain at least one item",
    "config values must contain non-empty strings",
)

_REQUEST_REQUIRED_TEXT_ERROR = "request identity fields must be non-empty strings"
_REQUEST_PAYLOAD_OBJECT_ERROR = "request payload must be an object"
_REQUEST_UNSUPPORTED_FIELDS_ERROR = "unsupported request fields"
_REQUEST_TEMPLATE_OBJECT_ERROR = "request template must be an object"
_REQUEST_BINDINGS_REQUIRED_ERROR = "request bindings are required"
_REQUEST_BINDINGS_OBJECT_ERROR = "request bindings must be an object"


class CLIRequestPayloadError(ValueError):
    """Raised for request payload validation failures safe to echo locally."""

    def __init__(self, public_message: str) -> None:
        self.public_message = public_message
        super().__init__(public_message)


class CLIDemoError(RuntimeError):
    """Raised for bounded demo failures safe to echo locally."""

    def __init__(self, public_message: str) -> None:
        self.public_message = public_message
        super().__init__(public_message)


def _classify_cli_os_error(exc: OSError) -> str:
    """Return a bounded local file-access failure message."""
    exc_type = type(exc).__name__
    if isinstance(exc, PermissionError):
        return f"file access denied ({exc_type})"
    if isinstance(exc, FileNotFoundError):
        return f"file not found ({exc_type})"
    return f"file access error ({exc_type})"


def _classify_cli_value_error(exc: ValueError) -> str:
    """Preserve safe request-validation messages and bound everything else."""
    if isinstance(exc, CLIRequestPayloadError):
        return exc.public_message
    return f"invalid request payload ({type(exc).__name__})"


def _classify_profile_load_error(exc: ProfileLoadError) -> str:
    """Preserve known profile-load messages and bound everything else."""
    return exc.public_message


def _classify_request_contract_error(exc: RuntimeCoreInvariantError) -> str:
    """Return a bounded request contract failure message."""
    return f"request payload failed contract validation ({type(exc).__name__})"


def _classify_cli_http_error(exc: Exception) -> str:
    """Return a bounded HTTP or transport failure message."""
    import urllib.error

    if isinstance(exc, urllib.error.HTTPError):
        return f"http request failed ({exc.code})"
    if isinstance(exc, TimeoutError):
        return f"http request timed out ({type(exc).__name__})"
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, TimeoutError):
            return f"http request timed out ({type(reason).__name__})"
        if isinstance(reason, BaseException):
            return f"http transport failed ({type(reason).__name__})"
        return "http transport failed (URLError)"
    if isinstance(exc, json.JSONDecodeError):
        return f"invalid JSON response ({type(exc).__name__})"
    if isinstance(exc, OSError):
        return f"http transport failed ({type(exc).__name__})"
    return f"http request failed ({type(exc).__name__})"


def _classify_cli_json_error(exc: json.JSONDecodeError) -> str:
    """Return a bounded JSON parsing failure message."""
    return f"malformed JSON ({type(exc).__name__})"


def _classify_config_validation_error(exc: Exception) -> str:
    """Preserve safe config-contract messages and bound unexpected failures."""
    if isinstance(exc, (TypeError, ValueError)):
        message = str(exc)
        if any(message.startswith(prefix) for prefix in _SAFE_CONFIG_ERROR_PREFIXES):
            return message
    return f"invalid config file ({type(exc).__name__})"


def _load_demo_json_object(raw: bytes) -> dict[str, Any]:
    """Load a demo HTTP response body as a JSON object."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CLIDemoError(_classify_cli_http_error(exc)) from exc
    if not isinstance(payload, dict):
        raise CLIDemoError("invalid JSON response root")
    return payload


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
        raise CLIRequestPayloadError(_REQUEST_REQUIRED_TEXT_ERROR)
    return value


def _build_operator_request(
    payload: Mapping[str, Any],
    *,
    source_name: str,
) -> OperatorRequest:
    if not isinstance(payload, Mapping):
        raise CLIRequestPayloadError(_REQUEST_PAYLOAD_OBJECT_ERROR)

    unknown_keys = sorted(set(payload) - _REQUEST_ALLOWED_KEYS)
    if unknown_keys:
        raise CLIRequestPayloadError(_REQUEST_UNSUPPORTED_FIELDS_ERROR)

    template = payload.get("template")
    if not isinstance(template, Mapping):
        raise CLIRequestPayloadError(_REQUEST_TEMPLATE_OBJECT_ERROR)

    if "bindings" not in payload:
        raise CLIRequestPayloadError(_REQUEST_BINDINGS_REQUIRED_ERROR)

    bindings = payload.get("bindings")
    if not isinstance(bindings, Mapping):
        raise CLIRequestPayloadError(_REQUEST_BINDINGS_OBJECT_ERROR)

    resolved_bindings = _resolve_bindings(dict(payload))
    if not isinstance(resolved_bindings, Mapping):
        raise CLIRequestPayloadError(_REQUEST_BINDINGS_OBJECT_ERROR)

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
        raise CLIRequestPayloadError(_classify_request_contract_error(exc)) from exc


def _resolve_config(args: argparse.Namespace) -> AppConfig:
    """Resolve config from --profile or --config, with profile taking precedence."""
    if hasattr(args, "profile") and args.profile:
        try:
            result = load_profile(args.profile)
            return result.config
        except ProfileLoadError as exc:
            _fatal(_classify_profile_load_error(exc))
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
        _fatal(_classify_cli_value_error(exc))

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


def pilot_init_command(args: argparse.Namespace) -> int:
    """Scaffold a governed pilot bundle without live infrastructure mutation."""
    try:
        result = initialize_pilot(
            PilotInitRequest(
                tenant_id=args.tenant_id,
                pilot_name=args.name,
                output_dir=Path(args.output),
                policy_pack_id=args.policy_pack,
                policy_version=args.policy_version,
                max_cost=args.max_cost,
                max_calls=args.max_calls,
                force=args.force,
            )
        )
    except (OSError, ValueError) as exc:
        _fatal(f"pilot init failed: {type(exc).__name__}")

    print(json.dumps(result.to_dict(), sort_keys=True, indent=2))
    return 0


def pilot_command(args: argparse.Namespace) -> int:
    """Route pilot subcommands."""
    if getattr(args, "pilot_command", None) == "init":
        return pilot_init_command(args)
    _fatal("pilot subcommand is required")


def _load_json_object(*, content: str, kind: str, source_name: str) -> dict:
    """Load a JSON object and fail closed on malformed or non-object input."""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        _fatal(f"invalid {kind} JSON: {_classify_cli_json_error(exc)}")
    if not isinstance(payload, dict):
        _fatal(f"{kind} JSON root must be an object")
    return payload


def _load_config(path: str) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        _fatal("config file not found")
    try:
        content = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        _fatal(f"cannot read config file: {_classify_cli_os_error(exc)}")
    data = _load_json_object(content=content, kind="config", source_name=path)
    try:
        return AppConfig.from_mapping(data)
    except (TypeError, ValueError) as exc:
        _fatal(f"invalid config file: {_classify_config_validation_error(exc)}")


def _load_request(source: str) -> dict:
    stripped_source = source.lstrip()
    if stripped_source.startswith("{") or stripped_source.startswith("["):
        return _load_json_object(content=source, kind="request", source_name="inline input")
    path = Path(source)
    if not path.exists():
        _fatal("request file not found")
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        _fatal(f"cannot read request file: {_classify_cli_os_error(exc)}")
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
    pilot_parser = subparsers.add_parser("pilot", help="Pilot bring-up commands")
    pilot_subparsers = pilot_parser.add_subparsers(dest="pilot_command")
    pilot_init_parser = pilot_subparsers.add_parser("init", help="Scaffold a governed pilot bundle")
    pilot_init_parser.add_argument("--tenant-id", required=True, help="Pilot tenant identifier")
    pilot_init_parser.add_argument("--name", required=True, help="Human-readable pilot name")
    pilot_init_parser.add_argument("--output", default="pilot", help="Output directory")
    pilot_init_parser.add_argument("--policy-pack", default="default-safe", help="Policy pack id")
    pilot_init_parser.add_argument("--policy-version", default="v0.1", help="Policy version")
    pilot_init_parser.add_argument("--max-cost", type=float, default=100.0, help="Pilot budget cost limit")
    pilot_init_parser.add_argument("--max-calls", type=int, default=1000, help="Pilot budget call limit")
    pilot_init_parser.add_argument("--force", action="store_true", help="Overwrite existing scaffold files")

    # v4.25.0: migrate — DB schema migration ops surface
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="DB schema migration operations (sqlite). Postgres deployments "
             "apply migrations out-of-band via SQL files.",
    )
    migrate_subparsers = migrate_parser.add_subparsers(dest="migrate_command")

    migrate_status_parser = migrate_subparsers.add_parser(
        "status",
        help="Show current schema version + pending migrations",
    )
    migrate_status_parser.add_argument(
        "--db", required=True,
        help="Database URL (sqlite:///path/to/db.sqlite)",
    )

    migrate_history_parser = migrate_subparsers.add_parser(
        "history",
        help="Show applied migration history",
    )
    migrate_history_parser.add_argument(
        "--db", required=True,
        help="Database URL (sqlite:///path/to/db.sqlite)",
    )

    migrate_up_parser = migrate_subparsers.add_parser(
        "up",
        help="Apply all pending migrations",
    )
    migrate_up_parser.add_argument(
        "--db", required=True,
        help="Database URL (sqlite:///path/to/db.sqlite)",
    )
    migrate_up_parser.add_argument(
        "--dry-run", action="store_true",
        help="List pending migrations without applying them",
    )

    verify_ledger_parser = subparsers.add_parser(
        "verify-ledger",
        help="Verify the hash chain of an exported audit ledger (JSONL)",
    )
    verify_ledger_parser.add_argument(
        "input",
        help="Path to audit ledger JSONL file (one JSON entry per line)",
    )
    verify_ledger_parser.add_argument(
        "--from-sequence", type=int, default=None,
        help="Verify only entries with sequence >= N (slice mode)",
    )
    verify_ledger_parser.add_argument(
        "--to-sequence", type=int, default=None,
        help="Verify only entries with sequence <= N (slice mode)",
    )
    verify_ledger_parser.add_argument(
        "--anchor-hash", default=None,
        help=(
            "SHA-256 hex of the previous_hash that the first entry in the "
            "(optionally sliced) input must link to. Required for "
            "compliance-grade slice verification — without it, a fabricated "
            "self-consistent slice will pass. See docs/LEDGER_SPEC.md."
        ),
    )

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

    def _fail_step(step: int, label: str, message: str) -> int:
        print(f"  [{step}] {label}: failed ({message})")
        return 1

    def _is_success_status(code: int) -> bool:
        return 200 <= code < 300

    # Check server
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=3) as resp:
            resp.read()
    except Exception as exc:
        print(f"  Server not reachable at {base}: {_classify_cli_http_error(exc)}")
        print("  Start with: uvicorn mcoi_runtime.app.server:app --port 8000")
        return 1

    def post(path: str, data: dict) -> tuple[int, dict]:
        body = _json.dumps(data).encode()
        req = urllib.request.Request(f"{base}{path}", data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, _load_demo_json_object(resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read() if exc.fp else b"{}"
            if not body:
                return exc.code, {}
            try:
                return exc.code, _load_demo_json_object(body)
            except CLIDemoError as parse_exc:
                raise CLIDemoError(parse_exc.public_message) from exc
        except CLIDemoError:
            raise
        except Exception as exc:
            raise CLIDemoError(_classify_cli_http_error(exc)) from exc

    print()
    print("  Mullu Control Plane — Governed Agent Demo")
    print("  " + "=" * 45)

    # 1. Register agent
    try:
        code, data = post("/api/v1/agent/register", {
            "agent_name": "demo-agent",
            "capabilities": ["file_read", "shell_execute"],
        })
    except CLIDemoError as exc:
        return _fail_step(1, "Register agent", exc.public_message)
    if not _is_success_status(code):
        return _fail_step(1, "Register agent", f"http request failed ({code})")
    agent_id = data.get("agent_id", "")
    if not isinstance(agent_id, str) or not agent_id:
        return _fail_step(1, "Register agent", "invalid JSON response body")
    print(f"  [1] Register agent: {agent_id}")

    # 2. Request allowed action
    try:
        code, data = post("/api/v1/agent/action-request", {
            "agent_id": agent_id,
            "action_type": "file_read",
            "target": "/tmp/safe-file.txt",
            "tenant_id": "demo-tenant",
        })
    except CLIDemoError as exc:
        return _fail_step(2, "Action request (file_read)", exc.public_message)
    if not _is_success_status(code):
        return _fail_step(2, "Action request (file_read)", f"http request failed ({code})")
    decision = data.get("decision", "")
    if not isinstance(decision, str) or not decision:
        return _fail_step(2, "Action request (file_read)", "invalid JSON response body")
    print(f"  [2] Action request (file_read): {decision}")

    # 3. Submit result
    action_id = data.get("action_id", "")
    if not isinstance(action_id, str) or not action_id:
        return _fail_step(3, "Action result submission", "invalid JSON response body")
    try:
        code, _ = post("/api/v1/agent/action-result", {
            "agent_id": agent_id,
            "action_id": action_id,
            "outcome": "success",
            "result": {"content": "file contents here"},
        })
    except CLIDemoError as exc:
        return _fail_step(3, "Action result submission", exc.public_message)
    if not _is_success_status(code):
        return _fail_step(3, "Action result submission", f"http request failed ({code})")
    print("  [3] Action result submitted: success")

    # 4. Check audit trail
    try:
        with urllib.request.urlopen(
            f"{base}/api/v1/audit?action=agent.adapter.action_request&limit=5",
            timeout=5,
        ) as resp:
            audit = _load_demo_json_object(resp.read())
        print(f"  [4] Audit trail: {audit.get('count', 0)} governed actions recorded")
    except CLIDemoError as exc:
        print(f"  [4] Audit trail: check failed ({exc.public_message})")
    except Exception as exc:
        print(f"  [4] Audit trail: check failed ({_classify_cli_http_error(exc)})")

    # 5. Heartbeat
    try:
        code, _ = post("/api/v1/agent/heartbeat", {"agent_id": agent_id, "status": "healthy"})
    except CLIDemoError as exc:
        return _fail_step(5, "Heartbeat", exc.public_message)
    if not _is_success_status(code):
        return _fail_step(5, "Heartbeat", f"http request failed ({code})")
    print("  [5] Heartbeat sent: healthy")

    print("  " + "=" * 45)
    print("  Demo complete. Agent governed, actions audited.")
    print()
    return 0


def verify_ledger_command(args: argparse.Namespace) -> int:
    """Verify the hash chain of an exported audit ledger.

    G3 — external ledger verifier. Reads JSONL, recomputes hashes,
    checks chain linkage from genesis (or operator-supplied anchor for
    slice mode), and validates sequence monotonicity. Foundation of
    audit-trail integrity claims. See docs/LEDGER_SPEC.md.

    Exit codes (per LEDGER_SPEC.md):
      0 — chain valid
      1 — chain broken: previous_hash mismatch, entry_hash mismatch, or
          sequence gap (security event — investigate tamper)
      2 — input error: file missing, invalid JSON, non-object lines
      3 — schema corruption: missing fields, unknown schema version
          (writer bug — investigate writer)
    """
    from mcoi_runtime.governance.audit.trail import verify_chain_from_entries

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"error: file not found: {input_path}")
        return 2

    entries: list[dict[str, Any]] = []
    try:
        with input_path.open("r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError as exc:
                    print(f"error: invalid JSON at line {line_no}: {exc.msg}")
                    return 2
                if not isinstance(entry, dict):
                    print(f"error: line {line_no} is not a JSON object")
                    return 2
                entries.append(entry)
    except OSError as exc:
        print(f"error: cannot read {input_path}: {exc.strerror}")
        return 2

    # Optional sequence filter (verifies a contiguous slice).
    # NOTE: bare slice verification without --anchor-hash proves only
    # internal consistency of the slice, NOT that the slice belongs to
    # the real chain. See LEDGER_SPEC.md §"Slice verification".
    sliced = args.from_sequence is not None or args.to_sequence is not None
    if args.from_sequence is not None:
        entries = [e for e in entries if e.get("sequence", -1) >= args.from_sequence]
    if args.to_sequence is not None:
        entries = [e for e in entries if e.get("sequence", -1) <= args.to_sequence]

    # Determine anchor sequence (for slice mode the first entry's
    # sequence is whatever sequence the slice starts at, not 1).
    anchor_seq: int | None = None
    if args.anchor_hash is not None and entries:
        anchor_seq = entries[0].get("sequence")

    if sliced and args.anchor_hash is None:
        print(
            "warning: slice verification without --anchor-hash proves only "
            "internal consistency. See docs/LEDGER_SPEC.md."
        )

    result = verify_chain_from_entries(
        entries,
        anchor_hash=args.anchor_hash,
        anchor_sequence=anchor_seq,
    )

    if result.valid:
        print(f"OK  ledger verified — {result.entries_checked} entries, chain intact")
        return 0

    print(f"FAIL ledger verification failed")
    print(f"  entries_checked: {result.entries_checked}")
    print(f"  failure_sequence: {result.failure_sequence}")
    print(f"  failure_field: {result.failure_field}")
    print(f"  reason: {result.failure_reason}")

    # Split exit codes per LEDGER_SPEC.md:
    # schema corruption → exit 3 (writer bug)
    # everything else (sequence/previous_hash/entry_hash) → exit 1 (tamper)
    if result.failure_field == "schema":
        return 3
    return 1


def _open_sqlite_for_migrations(db_url: str):
    """Open a sqlite connection from a sqlite:///<path> URL.

    Returns the connection object (which already implements the
    DBConnection protocol the migration engine expects:
    execute / executescript / commit). Raises ValueError on bad URL,
    OSError on filesystem problems.
    """
    import sqlite3
    if not db_url.startswith("sqlite:///"):
        raise ValueError(
            "migrate CLI supports sqlite:///<path> URLs; postgres "
            "deployments apply migrations out-of-band"
        )
    path = db_url[len("sqlite:///"):]
    return sqlite3.connect(path)


def _migrate_engine_for_cli():
    """Build a MigrationEngine pre-loaded with platform migrations."""
    from datetime import datetime, timezone
    from mcoi_runtime.persistence.migrations import (
        create_platform_migration_engine,
    )
    return create_platform_migration_engine(
        clock=lambda: datetime.now(timezone.utc).isoformat(),
        dialect="sqlite",
    )


def migrate_command(args: argparse.Namespace) -> int:
    """v4.25.0: dispatch ``mcoi migrate {status,history,up}`` subcommands."""
    sub = getattr(args, "migrate_command", None)
    if sub is None:
        print("Usage: mcoi migrate {status|history|up} --db sqlite:///path")
        return 1

    try:
        conn = _open_sqlite_for_migrations(args.db)
    except ValueError as exc:
        print(f"error: {exc}")
        return 1
    except OSError:
        print("error: cannot open database file")
        return 1

    engine = _migrate_engine_for_cli()

    try:
        if sub == "status":
            current = engine.current_version(conn)
            pending = engine.pending(conn)
            print(f"current_version: {current}")
            print(f"registered: {engine.migration_count}")
            print(f"pending: {len(pending)}")
            for m in pending:
                print(f"  v{m.version} {m.name}")
            return 0

        elif sub == "history":
            hist = engine.history(conn)
            if not hist:
                print("(no migrations applied)")
                return 0
            for entry in hist:
                print(
                    f"v{entry['version']:>3} "
                    f"{entry['name']:<40} "
                    f"applied={entry['applied_at']} "
                    f"checksum={entry['checksum']}"
                )
            return 0

        elif sub == "up":
            pending = engine.pending(conn)
            if not pending:
                print("up to date — no pending migrations")
                return 0
            if args.dry_run:
                print(f"would apply {len(pending)} migration(s):")
                for m in pending:
                    print(f"  v{m.version} {m.name}")
                return 0
            results = engine.apply_all(conn)
            applied = [r for r in results if r.success]
            print(f"applied {len(applied)} migration(s):")
            for r in applied:
                print(f"  v{r.version} {r.name}")
            return 0

        else:
            print(f"error: unknown migrate subcommand {sub!r}")
            return 1
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    commands = {
        "run": run_command,
        "status": status_command,
        "profiles": profiles_command,
        "packs": packs_command,
        "pilot": pilot_command,
        "init": init_command,
        "demo": demo_command,
        "verify-ledger": verify_ledger_command,
        "migrate": migrate_command,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
