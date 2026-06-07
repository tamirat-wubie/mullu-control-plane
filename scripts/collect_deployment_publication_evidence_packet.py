#!/usr/bin/env python3
"""Collect a non-effecting deployment publication evidence packet.

Purpose: compose gateway publication readiness, upstream blocker, DNS target,
DNS resolution, closure plan, schema validation, and dry-run dispatch evidence
into one reproducible packet.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: deployment publication receipt builders, validators, DNS
resolution, GitHub CLI metadata readers, and JSON packet output.
Invariants:
  - Collection never mutates DNS, GitHub workflows, ingress, deployment status,
    or secrets.
  - Secret checks record names and presence only.
  - Strict publication gates may fail closed while the packet itself is written.
  - The packet summary preserves every generated artifact path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.collect_gateway_dns_resolution_receipt import (  # noqa: E402
    collect_gateway_dns_resolution_receipt,
    write_gateway_dns_resolution_receipt,
)
from scripts.dispatch_deployment_witness import DEFAULT_REPOSITORY  # noqa: E402
from scripts.dispatch_gateway_publication import (  # noqa: E402
    DEFAULT_ARTIFACT_NAME,
    DEFAULT_WORKFLOW_FILE,
    build_gateway_publication_dispatch_plan,
)
from scripts.emit_deployment_upstream_blocker_receipt import (  # noqa: E402
    DEFAULT_BLOCKERS,
    DEFAULT_EVIDENCE_REFS,
    DEFAULT_GATEWAY_URL,
    DEFAULT_NEXT_ACTIONS,
    DEFAULT_UPSTREAM_GATE,
    DEFAULT_UPSTREAM_REPOSITORY,
    derive_receipt_inputs_from_upstream_readiness_report,
    emit_deployment_upstream_blocker_receipt,
    write_deployment_upstream_blocker_receipt,
)
from scripts.emit_gateway_dns_target_binding_receipt import (  # noqa: E402
    emit_gateway_dns_target_binding_receipt,
    write_gateway_dns_target_binding_receipt,
)
from scripts.plan_deployment_publication_closure import (  # noqa: E402
    plan_deployment_publication_closure,
    write_deployment_publication_closure_plan,
)
from scripts.report_gateway_publication_readiness import (  # noqa: E402
    report_gateway_publication_readiness,
    write_gateway_publication_readiness,
)
from scripts.validate_deployment_publication_closure_plan_schema import (  # noqa: E402
    validate_deployment_publication_closure_plan_schema,
    write_deployment_publication_closure_plan_schema_validation,
)
from scripts.validate_deployment_publication_evidence_packet import (  # noqa: E402
    validate_deployment_publication_evidence_packet,
    write_deployment_publication_evidence_packet_validation,
)
from scripts.validate_deployment_upstream_blocker_receipt import (  # noqa: E402
    validate_deployment_upstream_blocker_receipt,
    write_deployment_upstream_blocker_validation_report,
)
from scripts.validate_gateway_dns_resolution_receipt import (  # noqa: E402
    validate_gateway_dns_resolution_receipt,
    write_gateway_dns_resolution_validation_report,
)
from scripts.validate_gateway_dns_target_binding_receipt import (  # noqa: E402
    validate_gateway_dns_target_binding_receipt,
    write_gateway_dns_target_binding_validation_report,
)

PacketDnsResolver = Callable[[str], Iterable[tuple[int, str]]]
PublicationResolver = Callable[[str], tuple[str, ...]]


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


@dataclass(frozen=True, slots=True)
class DeploymentPublicationEvidencePacket:
    """Summary for a collected deployment publication evidence packet."""

    packet_id: str
    output_dir: str
    gateway_host: str
    gateway_url: str
    expected_environment: str
    ready: bool
    blockers: tuple[str, ...]
    artifacts: dict[str, str]
    validation_status: dict[str, bool]
    dispatch_command: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready evidence packet summary."""
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        payload["dispatch_command"] = list(self.dispatch_command)
        return payload


def collect_deployment_publication_evidence_packet(
    *,
    output_dir: Path,
    gateway_url: str = DEFAULT_GATEWAY_URL,
    gateway_host: str = "",
    expected_environment: str = "pilot",
    upstream_readiness_report: Path | None = None,
    dns_record_type: str = "",
    dns_target: str = "",
    dns_provider: str = "",
    repository: str = DEFAULT_REPOSITORY,
    apply_ingress: bool = False,
    dispatch_witness: bool = False,
    skip_preflight_endpoint_probes: bool = False,
    runner: CommandRunner | None = None,
    publication_resolver: PublicationResolver | None = None,
    dns_resolver: PacketDnsResolver | None = None,
) -> DeploymentPublicationEvidencePacket:
    """Collect one read-only deployment publication evidence packet."""
    normalized_url = _require_gateway_url(gateway_url)
    normalized_host = _require_gateway_host(gateway_host or _host_from_gateway_url(normalized_url))
    normalized_environment = _require_expected_environment(expected_environment)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = _packet_paths(output_dir)
    readiness = report_gateway_publication_readiness(
        gateway_host=normalized_host,
        gateway_url=normalized_url,
        expected_environment=normalized_environment,
        repository=repository,
        apply_ingress=apply_ingress,
        dispatch_witness=dispatch_witness,
        skip_preflight_endpoint_probes=skip_preflight_endpoint_probes,
        runner=runner,
        resolver=publication_resolver,
    )
    write_gateway_publication_readiness(readiness, paths["gateway_publication_readiness"])

    upstream_inputs = (
        derive_receipt_inputs_from_upstream_readiness_report(upstream_readiness_report)
        if upstream_readiness_report
        else _default_upstream_inputs()
    )
    upstream_receipt = emit_deployment_upstream_blocker_receipt(
        target_gateway_url=normalized_url,
        upstream_repository=DEFAULT_UPSTREAM_REPOSITORY,
        upstream_gate=DEFAULT_UPSTREAM_GATE,
        upstream_state=str(upstream_inputs["upstream_state"]),
        api_provisioning_allowed=bool(upstream_inputs["api_provisioning_allowed"]),
        dns_publication_allowed=bool(upstream_inputs["dns_publication_allowed"]),
        blockers=tuple(str(item) for item in upstream_inputs["blockers"]),
        evidence_refs=tuple(str(item) for item in upstream_inputs["evidence_refs"]),
        next_actions=tuple(str(item) for item in upstream_inputs["next_actions"]),
    )
    write_deployment_upstream_blocker_receipt(
        upstream_receipt,
        paths["deployment_upstream_blocker_receipt"],
    )
    upstream_validation = validate_deployment_upstream_blocker_receipt(
        receipt_path=paths["deployment_upstream_blocker_receipt"],
        require_ready=True,
    )
    write_deployment_upstream_blocker_validation_report(
        upstream_validation,
        paths["deployment_upstream_blocker_validation"],
    )

    dns_target_receipt = emit_gateway_dns_target_binding_receipt(
        gateway_host=normalized_host,
        gateway_url=normalized_url,
        expected_environment=normalized_environment,
        record_type=dns_record_type,
        target=dns_target,
        provider=dns_provider,
    )
    write_gateway_dns_target_binding_receipt(
        dns_target_receipt,
        paths["gateway_dns_target_binding_receipt"],
    )
    dns_target_validation = validate_gateway_dns_target_binding_receipt(
        receipt_path=paths["gateway_dns_target_binding_receipt"],
        require_ready=True,
        expected_gateway_host=normalized_host,
        expected_gateway_url=normalized_url,
        expected_environment=normalized_environment,
    )
    write_gateway_dns_target_binding_validation_report(
        dns_target_validation,
        paths["gateway_dns_target_binding_validation"],
    )

    dns_resolution_receipt = collect_gateway_dns_resolution_receipt(
        host=normalized_host,
        resolver=dns_resolver,
    )
    write_gateway_dns_resolution_receipt(
        dns_resolution_receipt,
        paths["gateway_dns_resolution_receipt"],
    )
    dns_resolution_validation = validate_gateway_dns_resolution_receipt(
        receipt_path=paths["gateway_dns_resolution_receipt"],
        require_resolved=True,
    )
    write_gateway_dns_resolution_validation_report(
        dns_resolution_validation,
        paths["gateway_dns_resolution_validation"],
    )

    closure_plan = plan_deployment_publication_closure(
        readiness_path=paths["gateway_publication_readiness"],
        upstream_blocker_receipt_path=paths["deployment_upstream_blocker_receipt"],
        dns_target_binding_receipt_path=paths["gateway_dns_target_binding_receipt"],
        dns_resolution_receipt_path=paths["gateway_dns_resolution_receipt"],
    )
    write_deployment_publication_closure_plan(
        closure_plan,
        paths["deployment_publication_closure_plan"],
    )
    closure_plan_validation = validate_deployment_publication_closure_plan_schema(
        plan_path=paths["deployment_publication_closure_plan"],
    )
    write_deployment_publication_closure_plan_schema_validation(
        closure_plan_validation,
        paths["deployment_publication_closure_plan_schema_validation"],
    )

    dispatch_plan = build_gateway_publication_dispatch_plan(
        gateway_host=normalized_host,
        gateway_url=normalized_url,
        expected_environment=normalized_environment,
        apply_ingress=apply_ingress,
        dispatch_witness=dispatch_witness,
        skip_preflight_endpoint_probes=skip_preflight_endpoint_probes,
        repository=repository,
        workflow_file=DEFAULT_WORKFLOW_FILE,
        artifact_name=DEFAULT_ARTIFACT_NAME,
        download_dir=output_dir / "gateway-publication-witness",
    )
    _write_json(paths["gateway_publication_dispatch_plan"], _dispatch_plan_dict(dispatch_plan))

    validation_status = {
        "deployment_upstream_blocker": upstream_validation.valid,
        "gateway_dns_target_binding": dns_target_validation.valid,
        "gateway_dns_resolution": dns_resolution_validation.valid,
        "deployment_publication_closure_plan_schema": closure_plan_validation.ok,
    }
    artifact_labels = _artifact_labels(paths)
    packet = DeploymentPublicationEvidencePacket(
        packet_id=_packet_id(
            gateway_host=normalized_host,
            gateway_url=normalized_url,
            expected_environment=normalized_environment,
            blockers=closure_plan.blockers,
            validation_status=validation_status,
        ),
        output_dir=str(output_dir),
        gateway_host=normalized_host,
        gateway_url=normalized_url,
        expected_environment=normalized_environment,
        ready=not closure_plan.blockers and all(validation_status.values()),
        blockers=closure_plan.blockers,
        artifacts=artifact_labels,
        validation_status=validation_status,
        dispatch_command=tuple(dispatch_plan.dispatch_command),
    )
    _write_json(paths["deployment_publication_evidence_packet"], packet.as_dict())
    packet_validation = validate_deployment_publication_evidence_packet(
        packet_path=paths["deployment_publication_evidence_packet"],
    )
    write_deployment_publication_evidence_packet_validation(
        packet_validation,
        paths["deployment_publication_evidence_packet_validation"],
    )
    return packet


def _packet_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "gateway_publication_readiness": output_dir / "gateway_publication_readiness.json",
        "deployment_upstream_blocker_receipt": output_dir / "deployment_upstream_blocker_receipt.json",
        "deployment_upstream_blocker_validation": output_dir
        / "deployment_upstream_blocker_receipt_validation.json",
        "gateway_dns_target_binding_receipt": output_dir / "gateway_dns_target_binding_receipt.json",
        "gateway_dns_target_binding_validation": output_dir
        / "gateway_dns_target_binding_receipt_validation.json",
        "gateway_dns_resolution_receipt": output_dir / "gateway_dns_resolution_receipt.json",
        "gateway_dns_resolution_validation": output_dir
        / "gateway_dns_resolution_receipt_validation.json",
        "deployment_publication_closure_plan": output_dir / "deployment_publication_closure_plan.json",
        "deployment_publication_closure_plan_schema_validation": output_dir
        / "deployment_publication_closure_plan_schema_validation.json",
        "gateway_publication_dispatch_plan": output_dir / "gateway_publication_dispatch_plan.json",
        "deployment_publication_evidence_packet": output_dir
        / "deployment_publication_evidence_packet.json",
        "deployment_publication_evidence_packet_validation": output_dir
        / "deployment_publication_evidence_packet_validation.json",
    }


def _artifact_labels(paths: dict[str, Path]) -> dict[str, str]:
    return {name: str(path) for name, path in sorted(paths.items())}


def _default_upstream_inputs() -> dict[str, Any]:
    return {
        "upstream_state": "AwaitingEvidence",
        "api_provisioning_allowed": False,
        "dns_publication_allowed": False,
        "blockers": DEFAULT_BLOCKERS,
        "evidence_refs": DEFAULT_EVIDENCE_REFS,
        "next_actions": DEFAULT_NEXT_ACTIONS,
    }


def _dispatch_plan_dict(dispatch_plan: Any) -> dict[str, Any]:
    return {
        "artifact_dir": str(dispatch_plan.artifact_dir),
        "artifact_name": dispatch_plan.artifact_name,
        "apply_ingress": dispatch_plan.apply_ingress,
        "dispatch_command": list(dispatch_plan.dispatch_command),
        "dispatch_witness": dispatch_plan.dispatch_witness,
        "expected_environment": dispatch_plan.expected_environment,
        "gateway_host": dispatch_plan.gateway_host,
        "gateway_url": dispatch_plan.gateway_url,
        "repository": dispatch_plan.repository,
        "skip_preflight_endpoint_probes": dispatch_plan.skip_preflight_endpoint_probes,
        "workflow_file": dispatch_plan.workflow_file,
    }


def _packet_id(
    *,
    gateway_host: str,
    gateway_url: str,
    expected_environment: str,
    blockers: tuple[str, ...],
    validation_status: dict[str, bool],
) -> str:
    material = {
        "gateway_host": gateway_host,
        "gateway_url": gateway_url,
        "expected_environment": expected_environment,
        "blockers": blockers,
        "validation_status": validation_status,
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"deployment-publication-evidence-packet-{digest[:16]}"


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _require_gateway_url(gateway_url: str) -> str:
    parsed = urlparse(gateway_url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError("gateway URL must include https scheme and host")
    if parsed.port or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise RuntimeError("gateway URL must not include port, path, query, or fragment")
    return f"https://{_require_gateway_host(parsed.hostname)}"


def _host_from_gateway_url(gateway_url: str) -> str:
    parsed = urlparse(gateway_url)
    if not parsed.hostname:
        raise RuntimeError("gateway URL host is required")
    return parsed.hostname


def _require_gateway_host(gateway_host: str) -> str:
    host = gateway_host.strip().lower()
    if not host:
        raise RuntimeError("gateway host is required")
    if "/" in host or ":" in host or host.startswith(("http://", "https://")):
        raise RuntimeError("gateway host must be a DNS host without scheme, path, or port")
    if "." not in host:
        raise RuntimeError("gateway host must be a fully qualified DNS name")
    return host


def _require_expected_environment(expected_environment: str) -> str:
    normalized = expected_environment.strip().lower()
    if normalized not in {"pilot", "production"}:
        raise RuntimeError("expected environment must be pilot or production")
    return normalized


def _socket_packet_resolver(host: str) -> tuple[tuple[int, str], ...]:
    return tuple(
        (result[0], str(result[4][0]))
        for result in socket.getaddrinfo(host, None)
        if result[4] and result[4][0]
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse deployment publication evidence packet arguments."""
    parser = argparse.ArgumentParser(description="Collect deployment publication evidence packet.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gateway-url", default=DEFAULT_GATEWAY_URL)
    parser.add_argument("--gateway-host", default="")
    parser.add_argument("--expected-environment", default="pilot")
    parser.add_argument("--upstream-readiness-report", default="")
    parser.add_argument("--dns-record-type", default="")
    parser.add_argument("--dns-target", default="")
    parser.add_argument("--dns-provider", default="")
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--apply-ingress", action="store_true")
    parser.add_argument("--dispatch-witness", action="store_true")
    parser.add_argument("--skip-preflight-endpoint-probes", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for evidence packet collection."""
    args = parse_args(argv)
    try:
        packet = collect_deployment_publication_evidence_packet(
            output_dir=Path(args.output_dir),
            gateway_url=args.gateway_url,
            gateway_host=args.gateway_host,
            expected_environment=args.expected_environment,
            upstream_readiness_report=(
                Path(args.upstream_readiness_report)
                if args.upstream_readiness_report
                else None
            ),
            dns_record_type=args.dns_record_type,
            dns_target=args.dns_target,
            dns_provider=args.dns_provider,
            repository=args.repository,
            apply_ingress=args.apply_ingress,
            dispatch_witness=args.dispatch_witness,
            skip_preflight_endpoint_probes=args.skip_preflight_endpoint_probes,
            dns_resolver=_socket_packet_resolver,
        )
    except RuntimeError as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "error": str(exc),
                        "packet_written": False,
                        "ready": False,
                        "status": "failed",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print("deployment publication evidence packet collection failed")
        return 1
    if args.json:
        print(json.dumps(packet.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"deployment publication evidence packet written: {packet.packet_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
