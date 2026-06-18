#!/usr/bin/env python3
"""Validate the code-change physics packet contract.

Purpose: verify the three-lane physics doctrine, schema, example packet,
documentation anchors, and agentic-control code-change planning evidence bind
together without granting execution authority.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS, Foundation Mode, and
software-development planning boundaries.
Dependencies: docs/CODE_CHANGE_PHYSICS.md,
schemas/code_change_physics_packet.schema.json,
examples/code_change_physics_packet.foundation.json, and
scripts/validate_schemas.py.
Invariants:
  - Validation is read-only and deterministic.
  - The packet is advisory; it cannot authorize live effects.
  - Governance, creative, and repair physics lanes are all present.
  - Selected paths must reference a candidate and preserve evidence needs.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_DOC_PATH = WORKSPACE_ROOT / "docs" / "CODE_CHANGE_PHYSICS.md"
DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "code_change_physics_packet.schema.json"
DEFAULT_PACKET_PATH = WORKSPACE_ROOT / "examples" / "code_change_physics_packet.foundation.json"
CODE_AUTOMATION_DOC_PATH = WORKSPACE_ROOT / "docs" / "20_code_automation_plane.md"
LOGIC_GOVERNANCE_DOC_PATH = WORKSPACE_ROOT / "docs" / "60_logic_governance_application.md"
SOLVER_FORGE_DOC_PATH = WORKSPACE_ROOT / "docs" / "66_solver_forge_loop.md"
SCHEMA_README_PATH = WORKSPACE_ROOT / "schemas" / "README.md"
AGENTIC_CONTROL_PACK_PATH = WORKSPACE_ROOT / "capabilities" / "agentic_control" / "capability_pack.json"

REQUIRED_DOC_PHRASES = (
    "Code Governance Physics",
    "Code Creative Physics",
    "Code Repair Physics",
    "Physics terms are planning symbols, not execution permission.",
    "The packet discovers safer paths; it does not bypass governance gates.",
    "CodeChangePhysicsPacket",
    "python scripts/validate_code_change_physics_packet.py",
)
REQUIRED_CROSS_DOC_PHRASES: dict[Path, tuple[str, ...]] = {
    CODE_AUTOMATION_DOC_PATH: (
        "CodeChangePhysicsPacket",
        "physics planning failed",
    ),
    LOGIC_GOVERNANCE_DOC_PATH: (
        "CodeChangePhysicsPacket",
        "Code Governance Physics",
        "Code Creative Physics",
        "Code Repair Physics",
    ),
    SOLVER_FORGE_DOC_PATH: (
        "CodeChangePhysicsPacket",
        "creative physics",
    ),
    SCHEMA_README_PATH: (
        "code_change_physics_packet.schema.json",
    ),
}
REQUIRED_LANES = {"governance_physics", "creative_physics", "repair_physics"}
REQUIRED_CONSERVATION_INVARIANTS = {
    "no_unapproved_authority",
    "smallest_safe_change",
    "proof_need_declared",
    "repair_path_named",
}
CREATIVE_PATH_KINDS = {
    "indirect",
    "draft_only",
    "approval_queue",
    "simulation",
    "sandbox_probe",
    "smallest_safe_pr",
    "repair_first",
}


@dataclass(frozen=True, slots=True)
class PhysicsFinding:
    """One deterministic code-change physics validation finding."""

    rule_id: str
    message: str


def load_text(path: Path, label: str) -> str:
    """Load one text artifact with explicit path errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit path and type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_doc_text(text: str) -> list[PhysicsFinding]:
    """Return findings for missing doctrine anchors."""

    findings: list[PhysicsFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                PhysicsFinding(
                    "code_change_physics_doc_phrase_missing",
                    f"code-change physics doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_cross_doc_anchors() -> list[PhysicsFinding]:
    """Return findings for docs or README surfaces that drift from the packet."""

    findings: list[PhysicsFinding] = []
    for path, phrases in REQUIRED_CROSS_DOC_PHRASES.items():
        text = load_text(path, _workspace_label(path))
        for phrase in phrases:
            if phrase not in text:
                findings.append(
                    PhysicsFinding(
                        "code_change_physics_cross_doc_phrase_missing",
                        f"{_workspace_label(path)} missing required phrase: {phrase}",
                    )
                )
    return findings


def validate_packet_schema(schema: dict[str, Any], packet: dict[str, Any]) -> list[PhysicsFinding]:
    """Return findings for JSON schema validation failures."""

    return [
        PhysicsFinding("code_change_physics_schema_invalid", error)
        for error in _validate_schema_instance(schema, packet)
    ]


def validate_packet_semantics(packet: dict[str, Any]) -> list[PhysicsFinding]:
    """Return semantic findings beyond the structural JSON schema."""

    findings: list[PhysicsFinding] = []
    lanes = packet.get("lanes", {})
    if set(lanes) != REQUIRED_LANES:
        findings.append(
            PhysicsFinding(
                "code_change_physics_lane_set_invalid",
                "packet must contain exactly governance, creative, and repair physics lanes",
            )
        )
    for lane_key, lane_payload in lanes.items():
        if isinstance(lane_payload, dict) and lane_payload.get("lane_id") != lane_key:
            findings.append(
                PhysicsFinding(
                    "code_change_physics_lane_id_mismatch",
                    f"lane key {lane_key} must match lane_id",
                )
            )

    force_lane_ids = {
        force_term.get("lane_id")
        for force_term in packet.get("force_terms", [])
        if isinstance(force_term, dict)
    }
    missing_force_lanes = REQUIRED_LANES - force_lane_ids
    if missing_force_lanes:
        findings.append(
            PhysicsFinding(
                "code_change_physics_force_lane_missing",
                f"force_terms missing lanes: {sorted(missing_force_lanes)}",
            )
        )

    candidate_paths = {
        candidate.get("path_id"): candidate
        for candidate in packet.get("candidate_paths", [])
        if isinstance(candidate, dict)
    }
    selected_path = packet.get("selected_path", {})
    selected_path_id = selected_path.get("path_id") if isinstance(selected_path, dict) else None
    selected_candidate = candidate_paths.get(selected_path_id)
    if selected_candidate is None:
        findings.append(
            PhysicsFinding(
                "code_change_physics_selected_path_unknown",
                "selected_path.path_id must reference a candidate path",
            )
        )
    elif packet.get("status") == "validated" and selected_candidate.get("requires_live_effect") is True:
        findings.append(
            PhysicsFinding(
                "code_change_physics_selected_live_effect_invalid",
                "validated planning packets cannot select a live-effect path",
            )
        )

    if isinstance(selected_path, dict) and selected_path.get("execution_authority_granted") is not False:
        findings.append(
            PhysicsFinding(
                "code_change_physics_execution_authority_invalid",
                "selected_path.execution_authority_granted must be false",
            )
        )

    creative_path_count = sum(
        1
        for candidate in candidate_paths.values()
        if candidate.get("path_kind") in CREATIVE_PATH_KINDS and candidate.get("requires_live_effect") is False
    )
    if creative_path_count < 1:
        findings.append(
            PhysicsFinding(
                "code_change_physics_creative_path_missing",
                "packet must include at least one non-live creative path",
            )
        )

    observed_invariants = {
        check.get("invariant")
        for check in packet.get("conservation_checks", [])
        if isinstance(check, dict) and check.get("status") == "passed"
    }
    missing_invariants = REQUIRED_CONSERVATION_INVARIANTS - observed_invariants
    if missing_invariants:
        findings.append(
            PhysicsFinding(
                "code_change_physics_conservation_check_missing",
                f"passed conservation checks missing invariants: {sorted(missing_invariants)}",
            )
        )

    return findings


def validate_agentic_control_binding(pack_payload: dict[str, Any]) -> list[PhysicsFinding]:
    """Return findings if the code-change planning capability lacks packet evidence."""

    capabilities = pack_payload.get("capabilities")
    if not isinstance(capabilities, list):
        return [
            PhysicsFinding(
                "code_change_physics_capability_pack_invalid",
                "agentic-control capability pack must contain a capabilities array",
            )
        ]
    code_change_entry = next(
        (
            item
            for item in capabilities
            if isinstance(item, dict) and item.get("capability_id") == "agentic_control.code_change.plan"
        ),
        None,
    )
    if not isinstance(code_change_entry, dict):
        return [
            PhysicsFinding(
                "code_change_physics_capability_missing",
                "agentic_control.code_change.plan capability is missing",
            )
        ]
    required_evidence = code_change_entry.get("evidence_model", {}).get("required_evidence", [])
    if "code_change_physics_packet" not in required_evidence:
        return [
            PhysicsFinding(
                "code_change_physics_capability_evidence_missing",
                "agentic_control.code_change.plan must require code_change_physics_packet evidence",
            )
        ]
    return []


def validate_code_change_physics_packet(
    doc_path: Path = DEFAULT_DOC_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
    capability_pack_path: Path = AGENTIC_CONTROL_PACK_PATH,
) -> list[PhysicsFinding]:
    """Validate all code-change physics artifacts."""

    doc_text = load_text(doc_path, "code-change physics doc")
    schema = _load_schema(schema_path)
    packet = load_json_object(packet_path, "code-change physics packet")
    pack_payload = load_json_object(capability_pack_path, "agentic-control capability pack")
    return [
        *validate_doc_text(doc_text),
        *validate_cross_doc_anchors(),
        *validate_packet_schema(schema, packet),
        *validate_packet_semantics(packet),
        *validate_agentic_control_binding(pack_payload),
    ]


def build_validation_report(
    doc_path: Path = DEFAULT_DOC_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
    capability_pack_path: Path = AGENTIC_CONTROL_PACK_PATH,
) -> dict[str, Any]:
    """Build a machine-readable validation report."""

    try:
        findings = validate_code_change_physics_packet(
            doc_path=doc_path,
            schema_path=schema_path,
            packet_path=packet_path,
            capability_pack_path=capability_pack_path,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        findings = [
            PhysicsFinding(
                "code_change_physics_load_failed",
                _sanitize_error(exc),
            )
        ]
    valid = not findings
    checks = (
        "code_change_physics_doc",
        "code_change_physics_cross_doc_anchors",
        "code_change_physics_schema",
        "code_change_physics_packet_semantics",
        "code_change_physics_capability_binding",
    )
    return {
        "receipt_id": "code_change_physics_packet_validation_receipt",
        "terminal_closure_required": True,
        "receipt_is_not_terminal_closure": True,
        "valid": valid,
        "status": "passed" if valid else "failed",
        "schema_path": _workspace_label(schema_path),
        "packet_path": _workspace_label(packet_path),
        "document_path": _workspace_label(doc_path),
        "capability_pack_path": _workspace_label(capability_pack_path),
        "checks": [{"name": check_name, "passed": valid} for check_name in checks],
        "check_count": len(checks),
        "error_count": len(findings),
        "errors": [
            {"rule_id": finding.rule_id, "message": finding.message}
            for finding in findings
        ],
    }


def write_validation_report(report: dict[str, Any], receipt_path: Path) -> Path:
    """Persist a validation receipt under the workspace."""

    resolved_path = receipt_path if receipt_path.is_absolute() else WORKSPACE_ROOT / receipt_path
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved_path


def _workspace_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _sanitize_error(exc: BaseException) -> str:
    message = str(exc)
    for path in (
        DEFAULT_DOC_PATH,
        DEFAULT_SCHEMA_PATH,
        DEFAULT_PACKET_PATH,
        AGENTIC_CONTROL_PACK_PATH,
        CODE_AUTOMATION_DOC_PATH,
        LOGIC_GOVERNANCE_DOC_PATH,
        SOLVER_FORGE_DOC_PATH,
        SCHEMA_README_PATH,
    ):
        message = message.replace(str(path), _workspace_label(path))
        message = message.replace(str(path.resolve(strict=False)), _workspace_label(path))
    return message


def main(argv: list[str] | None = None) -> int:
    """Validate code-change physics artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate code-change physics packet artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--capability-pack", type=Path, default=AGENTIC_CONTROL_PACK_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    parser.add_argument("--receipt-path", type=Path, help="optional path to persist the validation receipt")
    args = parser.parse_args(argv)

    report = build_validation_report(args.doc, args.schema, args.packet, args.capability_pack)
    if args.receipt_path is not None:
        write_validation_report(report, args.receipt_path)
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0 if report["valid"] else 1

    if not report["valid"]:
        for error in report["errors"]:
            sys.stderr.write(f"[FAIL] {error['rule_id']}: {error['message']}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    for check in report["checks"]:
        sys.stdout.write(f"[PASS] {check['name']}\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
