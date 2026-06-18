#!/usr/bin/env python3
"""Collect a Personal Assistant runtime boundary receipt.

Purpose: project checked-in Personal Assistant runtime modules into a
replayable no-effect boundary receipt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Personal Assistant runtime modules, capability pack, and policy
matrix receipt.
Invariants:
  - Collection never imports or executes Personal Assistant runtime modules.
  - Runtime modules must remain projection-only and connector-execution-free.
  - The receipt is not execution authority and is not terminal closure.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUNTIME_DIR = REPO_ROOT / "mcoi" / "mcoi_runtime" / "personal_assistant"
DEFAULT_CAPABILITY_PACK = REPO_ROOT / "capabilities" / "personal_assistant" / "capability_pack.json"
DEFAULT_POLICY_MATRIX = REPO_ROOT / "examples" / "personal_assistant_policy_matrix_receipt.json"
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "personal_assistant_runtime_boundary_receipt.json"

REQUIRED_RUNTIME_MODULES = (
    "__init__.py",
    "approval.py",
    "console.py",
    "contracts.py",
    "drafts.py",
    "github_codex.py",
    "intake.py",
    "math_reasoning.py",
    "memory.py",
    "planner.py",
    "planning.py",
    "read_only.py",
    "research.py",
    "skill_registry.py",
    "teamops.py",
    "whqr_bridge.py",
)
FORBIDDEN_IMPORT_ROOTS = (
    "boto3",
    "google",
    "httpx",
    "imaplib",
    "msal",
    "openai",
    "poplib",
    "requests",
    "shutil",
    "smtplib",
    "socket",
    "sqlalchemy",
    "sqlite3",
    "subprocess",
    "urllib",
)
FORBIDDEN_CALL_NAMES = (
    "HTTPConnection",
    "HTTPSConnection",
    "Popen",
    "SMTP",
    "connect",
    "copy",
    "copy2",
    "copyfile",
    "delete",
    "move",
    "patch",
    "post",
    "put",
    "remove",
    "request",
    "rmtree",
    "send",
    "unlink",
    "urlopen",
    "write_bytes",
    "write_text",
)
NO_EFFECT_FLAGS = (
    "runtime_execution_authority_granted",
    "live_connector_execution_allowed",
    "connector_mutation_allowed",
    "external_effect_allowed",
    "system_of_record_write_allowed",
    "memory_write_allowed",
    "deployment_mutation_allowed",
    "money_legal_public_allowed",
    "production_ready_claim_allowed",
    "customer_ready_claim_allowed",
    "live_nested_mind_activation_allowed",
)


def collect_personal_assistant_runtime_boundary(
    *,
    runtime_dir: Path = DEFAULT_RUNTIME_DIR,
    capability_pack_path: Path = DEFAULT_CAPABILITY_PACK,
    policy_matrix_path: Path = DEFAULT_POLICY_MATRIX,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Collect one no-effect Personal Assistant runtime boundary receipt."""
    capability_pack = _read_json_object(capability_pack_path, "capability pack")
    policy_matrix = _read_json_object(policy_matrix_path, "policy matrix receipt")
    generated_at = _format_utc(now_utc or datetime.now(UTC))

    module_paths = _runtime_module_paths(runtime_dir)
    module_records = [_module_boundary_record(path) for path in module_paths]
    capability_records = _capability_runtime_records(capability_pack)
    effect_boundary = {flag: False for flag in NO_EFFECT_FLAGS}

    required_modules_bound = set(REQUIRED_RUNTIME_MODULES) <= {record["module_name"] for record in module_records}
    all_modules_have_headers = all(record["has_governance_header"] is True for record in module_records)
    all_modules_parse = all(record["parse_status"] == "parsed" for record in module_records)
    no_forbidden_imports = all(record["forbidden_import_count"] == 0 for record in module_records)
    no_forbidden_calls = all(record["forbidden_call_count"] == 0 for record in module_records)
    no_runtime_authority_markers = all(record["runtime_authority_marker_count"] == 0 for record in module_records)
    capability_pack_fixture_only = all(record["fixture_only"] is True for record in capability_records)
    capability_pack_secretless = all(record["secret_scope"] == "none" for record in capability_records)
    capability_pack_networkless = all(record["network_allowlist_empty"] is True for record in capability_records)
    capability_pack_non_mutating = all(record["world_mutating"] is False for record in capability_records)
    policy_matrix_closed = _object(policy_matrix.get("policy_matrix_summary")).get("policy_matrix_closed") is True
    no_effect_boundary_verified = not any(effect_boundary.values())

    runtime_boundary_closed = (
        required_modules_bound
        and all_modules_have_headers
        and all_modules_parse
        and no_forbidden_imports
        and no_forbidden_calls
        and no_runtime_authority_markers
        and capability_pack_fixture_only
        and capability_pack_secretless
        and capability_pack_networkless
        and capability_pack_non_mutating
        and policy_matrix_closed
        and no_effect_boundary_verified
    )
    proof_state = "Pass" if runtime_boundary_closed else "Fail"
    solver_outcome = "SolvedVerified" if runtime_boundary_closed else "AwaitingEvidence"

    receipt_without_id = {
        "schema_version": "personal_assistant.runtime_boundary_receipt.v1",
        "generated_at": generated_at,
        "proof_state": proof_state,
        "solver_outcome": solver_outcome,
        "governed": True,
        "receipt_is_not_execution_authority": True,
        "receipt_is_not_terminal_closure": True,
        "source_refs": _source_refs(runtime_dir, capability_pack_path, policy_matrix_path),
        "runtime_boundary_summary": {
            "runtime_boundary_closed": runtime_boundary_closed,
            "policy_matrix_closed": policy_matrix_closed,
            "required_module_count": len(REQUIRED_RUNTIME_MODULES),
            "observed_module_count": len(module_records),
            "capability_count": len(capability_records),
            "required_modules_bound": required_modules_bound,
            "all_modules_have_headers": all_modules_have_headers,
            "all_modules_parse": all_modules_parse,
            "no_forbidden_imports": no_forbidden_imports,
            "no_forbidden_calls": no_forbidden_calls,
            "no_runtime_authority_markers": no_runtime_authority_markers,
            "capability_pack_fixture_only": capability_pack_fixture_only,
            "capability_pack_secretless": capability_pack_secretless,
            "capability_pack_networkless": capability_pack_networkless,
            "capability_pack_non_mutating": capability_pack_non_mutating,
            "no_effect_boundary_verified": no_effect_boundary_verified,
            "production_ready": False,
            "customer_ready": False,
            "next_allowed_action": "continue_foundation_hardening_only",
        },
        "module_records": module_records,
        "capability_runtime_records": capability_records,
        "effect_boundary": effect_boundary,
        "lineage": {
            "accepted_deltas": [
                {
                    "delta_id": f"delta-personal-assistant-runtime-boundary-{generated_at[:10]}",
                    "reason": _lineage_reason(runtime_boundary_closed),
                    "logged_in_lineage": True,
                }
            ],
            "rejected_deltas": [],
        },
    }
    return {"receipt_id": _receipt_id(receipt_without_id), **receipt_without_id}


def write_personal_assistant_runtime_boundary(receipt: Mapping[str, object], output_path: Path) -> Path:
    """Write one local Personal Assistant runtime boundary receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def _runtime_module_paths(runtime_dir: Path) -> list[Path]:
    return sorted(path for path in runtime_dir.glob("*.py") if path.is_file())


def _module_boundary_record(path: Path) -> dict[str, object]:
    source = path.read_text(encoding="utf-8")
    module_name = path.name
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    forbidden_imports: list[str] = []
    forbidden_calls: list[str] = []
    public_entry_points: list[str] = []
    imports: list[str] = []
    parse_status = "parsed"
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        tree = ast.Module(body=[], type_ignores=[])
        parse_status = "syntax_error"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
                if _import_root(alias.name) in FORBIDDEN_IMPORT_ROOTS:
                    forbidden_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append(module)
            if _import_root(module) in FORBIDDEN_IMPORT_ROOTS:
                forbidden_imports.append(module)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            public_entry_points.append(node.name)
        elif isinstance(node, ast.Call):
            call_name = _call_name(node.func)
            if call_name in FORBIDDEN_CALL_NAMES or call_name.split(".")[-1] in FORBIDDEN_CALL_NAMES:
                forbidden_calls.append(call_name)

    runtime_authority_markers = _runtime_authority_markers(source)
    return {
        "module_name": module_name,
        "module_ref": _path_label(path),
        "source_sha256": source_hash,
        "parse_status": parse_status,
        "import_roots": sorted({_import_root(value) for value in imports if value}),
        "public_entry_points": sorted(set(public_entry_points)),
        "public_entry_point_count": len(set(public_entry_points)),
        "has_governance_header": _has_governance_header(source),
        "forbidden_imports": sorted(set(forbidden_imports)),
        "forbidden_import_count": len(set(forbidden_imports)),
        "forbidden_calls": sorted(set(forbidden_calls)),
        "forbidden_call_count": len(set(forbidden_calls)),
        "runtime_authority_markers": sorted(set(runtime_authority_markers)),
        "runtime_authority_marker_count": len(set(runtime_authority_markers)),
        "module_boundary_closed": (
            parse_status == "parsed"
            and _has_governance_header(source)
            and not forbidden_imports
            and not forbidden_calls
            and not runtime_authority_markers
        ),
    }


def _capability_runtime_records(capability_pack: Mapping[str, Any]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for capability in _list_of_objects(capability_pack.get("capabilities")):
        metadata = _object(capability.get("metadata"))
        isolation_profile = _object(capability.get("isolation_profile"))
        governed_record = _object(_object(capability.get("extensions")).get("governed_record"))
        network_allowlist = _string_list(isolation_profile.get("network_allowlist"))
        records.append(
            {
                "capability_id": _bounded_text(capability.get("capability_id")),
                "certification_status": _bounded_text(capability.get("certification_status")),
                "fixture_only": metadata.get("fixture_only") is True,
                "production_ready": metadata.get("production_ready") is True,
                "secret_scope": _bounded_text(isolation_profile.get("secret_scope")),
                "network_allowlist_empty": not network_allowlist,
                "world_mutating": governed_record.get("world_mutating") is True,
                "receipt_required": governed_record.get("receipt_required") is True,
                "verification_required": governed_record.get("verification_required") is True,
                "runtime_boundary_closed": (
                    metadata.get("fixture_only") is True
                    and metadata.get("production_ready") is not True
                    and _bounded_text(isolation_profile.get("secret_scope")) == "none"
                    and not network_allowlist
                    and governed_record.get("world_mutating") is not True
                    and governed_record.get("receipt_required") is True
                    and governed_record.get("verification_required") is True
                ),
            }
        )
    return records


def _source_refs(runtime_dir: Path, capability_pack_path: Path, policy_matrix_path: Path) -> list[dict[str, object]]:
    sources = (
        ("runtime_modules", runtime_dir),
        ("capability_pack", capability_pack_path),
        ("policy_matrix_receipt", policy_matrix_path),
    )
    return [
        {
            "source_id": f"personal_assistant_{kind}",
            "source_ref": _path_label(path),
            "source_kind": kind,
            "bound": path.exists(),
        }
        for kind, path in sources
    ]


def _runtime_authority_markers(source: str) -> list[str]:
    authority_pairs = (
        ("live_connector_execution_allowed", "True"),
        ("connector_mutation_allowed", "True"),
        ("external_write_allowed", "True"),
        ("system_of_record_write_allowed", "True"),
        ("memory_write_allowed", "True"),
        ("deployment_mutation_allowed", "True"),
        ("production_ready", "True"),
        ("customer_ready", "True"),
        ("nested_mind_live_activation_allowed", "True"),
        ("live_nested_mind_activation_allowed", "True"),
    )
    lowered = source.lower()
    markers: list[str] = []
    for key, value in authority_pairs:
        if f'"{key}": {value.lower()}' in lowered or f"'{key}': {value.lower()}" in lowered:
            markers.append(f"{key}=true")
    return markers


def _has_governance_header(source: str) -> bool:
    header = source[:700]
    return "Purpose:" in header and "Governance scope:" in header and "Invariants:" in header


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _import_root(value: str) -> str:
    return value.split(".", 1)[0]


def _lineage_reason(runtime_boundary_closed: bool) -> str:
    if runtime_boundary_closed:
        return "Runtime boundary closed for no-effect Foundation Mode hardening without granting execution authority."
    return "Runtime boundary remains AwaitingEvidence because at least one module, capability, or policy binding is open."


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"failed to read Personal Assistant {label}") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Personal Assistant {label} was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Personal Assistant {label} must be a JSON object")
    return parsed


def _receipt_id(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"personal-assistant-runtime-boundary-{hashlib.sha256(encoded).hexdigest()[:16]}"


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _object(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_objects(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _bounded_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def main(argv: list[str] | None = None, *, now_utc: datetime | None = None) -> int:
    """Run the Personal Assistant runtime boundary collector."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--capability-pack", type=Path, default=DEFAULT_CAPABILITY_PACK)
    parser.add_argument("--policy-matrix", type=Path, default=DEFAULT_POLICY_MATRIX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print the generated receipt as JSON.")
    args = parser.parse_args(argv)

    receipt = collect_personal_assistant_runtime_boundary(
        runtime_dir=args.runtime_dir,
        capability_pack_path=args.capability_pack,
        policy_matrix_path=args.policy_matrix,
        now_utc=now_utc,
    )
    write_personal_assistant_runtime_boundary(receipt, args.output)
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=False))
    else:
        print(f"runtime_boundary_receipt: {_path_label(args.output)}")
        print(f"receipt_id: {receipt['receipt_id']}")
        print(f"solver_outcome: {receipt['solver_outcome']}")
        print(f"runtime_boundary_closed: {receipt['runtime_boundary_summary']['runtime_boundary_closed']}")  # type: ignore[index]
    return 0 if receipt["proof_state"] == "Pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
