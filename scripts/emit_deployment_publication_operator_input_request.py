#!/usr/bin/env python3
"""Emit missing operator inputs for deployment publication.

Purpose: translate a blocked deployment publication evidence packet into a
public-safe operator input request.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/deployment_publication_operator_input_request.schema.json
and deployment publication packet artifacts.
Invariants:
  - Report contains input names, blocker names, and next actions only.
  - Secret values, DNS target values, provider account details, IP addresses,
    and private host details are never serialized.
  - Publication remains blocked unless the source packet is ready.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_PACKET = REPO_ROOT / ".change_assurance" / "deployment_publication_evidence_packet.json"
DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "deployment_publication_operator_input_request.schema.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "deployment_publication_operator_input_request.json"
)


@dataclass(frozen=True, slots=True)
class DeploymentPublicationOperatorInput:
    """One missing operator input or evidence item."""

    input_id: str
    blocker: str
    input_kind: str
    required_name: str
    current_state: str
    evidence_source: str
    next_action: str


@dataclass(frozen=True, slots=True)
class DeploymentPublicationOperatorInputRequest:
    """Public-safe operator input request for deployment publication."""

    request_id: str
    packet_id: str
    gateway_host: str
    gateway_url: str
    ready: bool
    publication_allowed: bool
    solver_outcome: str
    proof_state: str
    required_inputs: tuple[DeploymentPublicationOperatorInput, ...]
    blocked_actions: tuple[str, ...]
    source_artifacts: dict[str, str]
    no_secret_values_serialized: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready request payload."""
        payload = asdict(self)
        payload["required_inputs"] = [asdict(item) for item in self.required_inputs]
        payload["blocked_actions"] = list(self.blocked_actions)
        return payload


def emit_deployment_publication_operator_input_request(
    *,
    packet_path: Path = DEFAULT_PACKET,
    schema_path: Path = DEFAULT_SCHEMA,
) -> DeploymentPublicationOperatorInputRequest:
    """Build one operator input request from a deployment publication packet."""
    packet = _load_json_object(packet_path, "deployment publication evidence packet")
    source_artifacts = _source_artifacts(packet, packet_path)
    upstream_receipt = _load_optional_artifact(
        source_artifacts.get("deployment_upstream_blocker_receipt", ""),
        "deployment upstream blocker receipt",
    )
    dns_target_receipt = _load_optional_artifact(
        source_artifacts.get("gateway_dns_target_binding_receipt", ""),
        "gateway DNS target binding receipt",
    )
    dns_resolution_receipt = _load_optional_artifact(
        source_artifacts.get("gateway_dns_resolution_receipt", ""),
        "gateway DNS resolution receipt",
    )
    required_inputs = _derive_required_inputs(
        packet=packet,
        upstream_receipt=upstream_receipt,
        dns_target_receipt=dns_target_receipt,
        dns_resolution_receipt=dns_resolution_receipt,
    )
    ready = packet.get("ready") is True
    request = DeploymentPublicationOperatorInputRequest(
        request_id=_request_id(packet, required_inputs),
        packet_id=str(packet.get("packet_id", "")),
        gateway_host=str(packet.get("gateway_host", "")),
        gateway_url=str(packet.get("gateway_url", "")),
        ready=ready,
        publication_allowed=ready and not required_inputs,
        solver_outcome="SolvedVerified" if ready else "AwaitingEvidence",
        proof_state="Pass" if ready else "Unknown",
        required_inputs=required_inputs,
        blocked_actions=_blocked_actions(ready),
        source_artifacts=source_artifacts,
        no_secret_values_serialized=True,
        next_action=_next_action(required_inputs, ready),
    )
    _validate_request_against_schema(request, schema_path)
    return request


def write_deployment_publication_operator_input_request(
    request: DeploymentPublicationOperatorInputRequest,
    output_path: Path,
) -> Path:
    """Write one operator input request JSON report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(request.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _derive_required_inputs(
    *,
    packet: dict[str, Any],
    upstream_receipt: dict[str, Any],
    dns_target_receipt: dict[str, Any],
    dns_resolution_receipt: dict[str, Any],
) -> tuple[DeploymentPublicationOperatorInput, ...]:
    required_inputs: list[DeploymentPublicationOperatorInput] = []
    blockers = tuple(str(blocker) for blocker in packet.get("blockers", []) if str(blocker))
    if "deployment_dns_not_verified" in blockers:
        required_inputs.extend(_dns_target_inputs(dns_target_receipt))
        if dns_resolution_receipt.get("resolved") is not True:
            required_inputs.append(
                _operator_input(
                    blocker="deployment_dns_not_verified",
                    input_kind="public_dns_resolution",
                    required_name=f"DNS record for {packet.get('gateway_host', 'gateway host')}",
                    current_state=str(dns_resolution_receipt.get("error") or "unresolved"),
                    evidence_source="gateway_dns_resolution_receipt",
                    next_action=(
                        "publish the approved A, AAAA, or CNAME record, then rerun "
                        "collect_gateway_dns_resolution_receipt.py with require-resolved validation"
                    ),
                )
            )
    if "deployment_upstream_api_gate_not_ready" in blockers:
        required_inputs.extend(_upstream_inputs(upstream_receipt))
    return tuple(required_inputs)


def _dns_target_inputs(
    dns_target_receipt: dict[str, Any],
) -> tuple[DeploymentPublicationOperatorInput, ...]:
    required_inputs: list[DeploymentPublicationOperatorInput] = []
    missing_inputs = (
        ("MULLU_GATEWAY_DNS_TARGET", "dns_origin_target", "target"),
        ("MULLU_GATEWAY_DNS_RECORD_TYPE", "dns_record_type", "record_type"),
        ("MULLU_DNS_PROVIDER", "dns_provider", "provider"),
    )
    for required_name, input_kind, receipt_key in missing_inputs:
        if str(dns_target_receipt.get(receipt_key, "")).strip():
            continue
        required_inputs.append(
            _operator_input(
                blocker="deployment_dns_not_verified",
                input_kind=input_kind,
                required_name=required_name,
                current_state="missing",
                evidence_source="gateway_dns_target_binding_receipt",
                next_action=(
                    "bind this public-safe input outside the report, then rerun "
                    "emit_gateway_dns_target_binding_receipt.py with require-ready validation"
                ),
            )
        )
    return tuple(required_inputs)


def _upstream_inputs(
    upstream_receipt: dict[str, Any],
) -> tuple[DeploymentPublicationOperatorInput, ...]:
    required_inputs: list[DeploymentPublicationOperatorInput] = [
        _operator_input(
            blocker="deployment_upstream_api_gate_not_ready",
            input_kind="upstream_readiness_report",
            required_name="UPSTREAM_API_READINESS_REPORT",
            current_state="present_not_ready" if _has_upstream_report_ref(upstream_receipt) else "missing",
            evidence_source="deployment_upstream_blocker_receipt",
            next_action=(
                "rerun the upstream API production readiness reporter with all required "
                "evidence and require-ready validation"
            ),
        )
    ]
    for blocker in upstream_receipt.get("blockers", []):
        blocker_text = str(blocker)
        if not blocker_text:
            continue
        required_inputs.append(
            _operator_input(
                blocker="deployment_upstream_api_gate_not_ready",
                input_kind="upstream_evidence",
                required_name=_upstream_required_name(blocker_text),
                current_state="missing_or_not_ready",
                evidence_source="deployment_upstream_blocker_receipt",
                next_action="close this upstream evidence item before DNS publication",
            )
        )
    return tuple(required_inputs)


def _operator_input(
    *,
    blocker: str,
    input_kind: str,
    required_name: str,
    current_state: str,
    evidence_source: str,
    next_action: str,
) -> DeploymentPublicationOperatorInput:
    input_material = {
        "blocker": blocker,
        "input_kind": input_kind,
        "required_name": required_name,
        "current_state": current_state,
        "evidence_source": evidence_source,
    }
    digest = hashlib.sha256(
        json.dumps(input_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return DeploymentPublicationOperatorInput(
        input_id=f"deployment-publication-input-{digest[:12]}",
        blocker=blocker,
        input_kind=input_kind,
        required_name=required_name,
        current_state=current_state,
        evidence_source=evidence_source,
        next_action=next_action,
    )


def _upstream_required_name(blocker: str) -> str:
    if blocker.startswith("manual_evidence_missing:"):
        return blocker.split(":", 1)[1]
    return blocker


def _has_upstream_report_ref(upstream_receipt: dict[str, Any]) -> bool:
    return any(
        str(ref).startswith("upstream-readiness-report:")
        for ref in upstream_receipt.get("evidence_refs", [])
    )


def _blocked_actions(ready: bool) -> tuple[str, ...]:
    if ready:
        return ()
    return (
        "dns_publication",
        "gateway_publication_workflow_dispatch",
        "deployment_status_publication_claim",
    )


def _next_action(
    required_inputs: tuple[DeploymentPublicationOperatorInput, ...],
    ready: bool,
) -> str:
    if ready:
        return "run deployment witness preflight before approved publication dispatch"
    if required_inputs:
        return required_inputs[0].next_action
    return "inspect deployment publication packet blockers"


def _request_id(
    packet: dict[str, Any],
    required_inputs: tuple[DeploymentPublicationOperatorInput, ...],
) -> str:
    material = {
        "packet_id": packet.get("packet_id", ""),
        "gateway_host": packet.get("gateway_host", ""),
        "ready": packet.get("ready", False),
        "required_input_ids": [item.input_id for item in required_inputs],
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"deployment-publication-operator-input-request-{digest[:16]}"


def _source_artifacts(packet: dict[str, Any], packet_path: Path) -> dict[str, str]:
    artifacts = packet.get("artifacts", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
    source_artifacts = {
        key: str(value)
        for key, value in artifacts.items()
        if key
        in {
            "deployment_upstream_blocker_receipt",
            "gateway_dns_resolution_receipt",
            "gateway_dns_target_binding_receipt",
        }
    }
    source_artifacts["deployment_publication_evidence_packet"] = str(packet_path)
    return source_artifacts


def _load_optional_artifact(path_text: str, label: str) -> dict[str, Any]:
    if not path_text:
        return {"artifact_missing": True, "label": label}
    path = Path(path_text)
    if not path.exists():
        return {"artifact_missing": True, "label": label}
    return _load_json_object(path, label)


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except OSError as exc:
        raise RuntimeError(f"{label} file missing: {path}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"{label} JSON parse failed") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} JSON root must be an object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _validate_request_against_schema(
    request: DeploymentPublicationOperatorInputRequest,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, request.as_dict())
    if errors:
        raise RuntimeError(f"operator input request schema validation failed: {errors}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse operator input request arguments."""
    parser = argparse.ArgumentParser(description="Emit deployment publication operator input request.")
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for operator input request emission."""
    args = parse_args(argv)
    try:
        request = emit_deployment_publication_operator_input_request(
            packet_path=Path(args.packet),
            schema_path=Path(args.schema),
        )
        write_deployment_publication_operator_input_request(request, Path(args.output))
    except RuntimeError as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "error": str(exc),
                        "publication_allowed": False,
                        "request_written": False,
                        "solver_outcome": "AwaitingEvidence",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"deployment publication operator input request failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(request.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"deployment publication operator input request written: {request.request_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
