#!/usr/bin/env python3
"""Validate deployment publication evidence packet summaries.

Purpose: keep one-command deployment publication evidence packets schema-backed
and semantically consistent before operators use them for issue or release
handoff.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/deployment_publication_evidence_packet.schema.json and
deployment publication evidence packet JSON.
Invariants:
  - Packet readiness equals blocker absence plus strict validation pass state.
  - All required artifact references are present.
  - Dispatch command is recorded as a plan only, not as a completed workflow
    proof.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_PACKET = REPO_ROOT / ".change_assurance" / "deployment_publication_evidence_packet.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "deployment_publication_evidence_packet.schema.json"
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "deployment_publication_evidence_packet_validation.json"
)
PACKET_ID_PATTERN = re.compile(r"^deployment-publication-evidence-packet-[0-9a-f]{16}$")
REQUIRED_ARTIFACTS = frozenset(
    {
        "deployment_publication_closure_plan",
        "deployment_publication_closure_plan_schema_validation",
        "deployment_publication_evidence_packet",
        "deployment_publication_evidence_packet_validation",
        "deployment_upstream_blocker_receipt",
        "deployment_upstream_blocker_validation",
        "gateway_dns_resolution_receipt",
        "gateway_dns_resolution_validation",
        "gateway_dns_target_binding_receipt",
        "gateway_dns_target_binding_validation",
        "gateway_publication_dispatch_plan",
        "gateway_publication_readiness",
    }
)


@dataclass(frozen=True, slots=True)
class DeploymentPublicationEvidencePacketValidation:
    """Validation result for one deployment publication evidence packet."""

    valid: bool
    ready: bool
    packet_path: str
    schema_path: str
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation result."""
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_deployment_publication_evidence_packet(
    *,
    packet_path: Path = DEFAULT_PACKET,
    schema_path: Path = DEFAULT_SCHEMA,
    require_ready: bool = False,
) -> DeploymentPublicationEvidencePacketValidation:
    """Validate one deployment publication evidence packet."""
    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("deployment publication evidence packet schema file missing")
    packet = _load_json_object(packet_path, "deployment publication evidence packet", errors)
    if schema and packet:
        errors.extend(_validate_schema_instance(schema, packet))
        _validate_semantics(packet, errors)
        if require_ready and packet.get("ready") is not True:
            errors.append("require ready: not-ready")
    ready = bool(packet.get("ready") is True) if packet else False
    return DeploymentPublicationEvidencePacketValidation(
        valid=not errors,
        ready=ready,
        packet_path=_path_label(packet_path),
        schema_path=_path_label(schema_path),
        errors=tuple(errors),
        next_action=_next_action(packet) if packet else "collect deployment publication evidence packet",
    )


def write_deployment_publication_evidence_packet_validation(
    validation: DeploymentPublicationEvidencePacketValidation,
    output_path: Path,
) -> Path:
    """Write one deployment publication evidence packet validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_semantics(packet: dict[str, Any], errors: list[str]) -> None:
    packet_id = str(packet.get("packet_id", ""))
    if not PACKET_ID_PATTERN.fullmatch(packet_id):
        errors.append("packet_id must match deployment-publication-evidence-packet pattern")
    artifacts = packet.get("artifacts", {})
    if isinstance(artifacts, dict):
        missing_artifacts = sorted(REQUIRED_ARTIFACTS - {str(key) for key in artifacts})
        if missing_artifacts:
            errors.append(f"artifacts missing required keys: {missing_artifacts}")
    validation_status = packet.get("validation_status", {})
    blockers = packet.get("blockers", [])
    expected_ready = (
        isinstance(blockers, list)
        and not blockers
        and isinstance(validation_status, dict)
        and all(validation_status.values())
    )
    if packet.get("ready") is not expected_ready:
        errors.append("ready must equal no blockers and all validation_status values true")
    dispatch_command = packet.get("dispatch_command", [])
    if not _is_dispatch_plan(dispatch_command):
        errors.append("dispatch_command must be a gateway-publication workflow dispatch plan")
    if "gh run download" in " ".join(str(part) for part in dispatch_command):
        errors.append("dispatch_command must not include artifact download")
    gateway_host = str(packet.get("gateway_host", ""))
    gateway_url = str(packet.get("gateway_url", ""))
    if gateway_url != f"https://{gateway_host}":
        errors.append("gateway_url must match gateway_host")


def _is_dispatch_plan(dispatch_command: Any) -> bool:
    if not isinstance(dispatch_command, list):
        return False
    command = [str(part) for part in dispatch_command]
    return len(command) >= 4 and command[:3] == ["gh", "workflow", "run"] and "gateway-publication.yml" in command


def _next_action(packet: dict[str, Any]) -> str:
    if packet.get("ready") is True:
        return "run deployment witness preflight before any approved dispatch"
    blockers = packet.get("blockers", [])
    if isinstance(blockers, list) and blockers:
        return f"close blocker: {blockers[0]}"
    return "inspect packet validation errors"


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    """Return a validation report path label without host-local ancestry."""
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse deployment publication evidence packet validation arguments."""
    parser = argparse.ArgumentParser(description="Validate deployment publication evidence packet.")
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for packet validation."""
    args = parse_args(argv)
    validation = validate_deployment_publication_evidence_packet(
        packet_path=Path(args.packet),
        schema_path=Path(args.schema),
        require_ready=args.require_ready,
    )
    write_deployment_publication_evidence_packet_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("deployment publication evidence packet valid")
    else:
        print(f"deployment publication evidence packet invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
