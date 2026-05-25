#!/usr/bin/env python3
"""Emit a deployment upstream blocker receipt.

Purpose: preserve cross-repository API/DNS readiness blockers before gateway
DNS publication or deployment witness dispatch.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: argparse, JSON receipt output, and gateway URL host validation.
Invariants:
  - Emission never mutates DNS, GitHub variables, workflows, or secrets.
  - DNS publication is ready only when the upstream gate is SolvedVerified and
    both API provisioning and DNS publication are explicitly allowed.
  - Blocked upstream state remains machine-readable for closure planning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "deployment_upstream_blocker_receipt.json"
DEFAULT_GATEWAY_URL = "https://api.mullusi.com"
DEFAULT_UPSTREAM_REPOSITORY = "mullusi/mullusi-site"
DEFAULT_UPSTREAM_GATE = "api-production-readiness-gate"
DEFAULT_BLOCKERS = (
    "private_recovery_inventory_missing",
    "recovery_witness_not_promoted",
    "production_image_not_confirmed",
    "runtime_host_not_provisioned",
    "managed_postgres_not_provisioned",
    "schema_not_applied",
    "secret_store_not_bound",
    "deploy_env_check_not_ready",
    "release_preflight_not_ready",
    "persistence_check_not_ready",
    "host_firewall_not_configured",
    "tls_preflight_not_closed",
    "rollback_path_not_verified",
    "private_runtime_witness_not_ready",
    "dns_authority_not_verified",
    "runtime_witness_registry_has_no_closed_products",
)
DEFAULT_EVIDENCE_REFS = (
    "mullusi-site-pr-58",
    "mullusi-site-commit-d62895152902c3757c0df2538e4fdaa80624f2f5",
    "issue-330-comment-4530610366",
    "upstream-script:scripts/check-api-production-readiness.mjs",
)
DEFAULT_NEXT_ACTIONS = (
    "complete private recovery inventory outside Git",
    "promote upstream recovery witness after manual confirmations",
    "run upstream check-api-production-readiness with all required evidence flags",
    "provision runtime host, managed PostgreSQL, secret store, TLS, and rollback path",
    "publish api.mullusi.com DNS only after upstream readiness passes",
)
READY_NEXT_ACTIONS = (
    "continue with gateway DNS target binding and resolution receipts",
)


@dataclass(frozen=True, slots=True)
class DeploymentUpstreamBlockerReceipt:
    """Evidence for one upstream deployment blocker gate."""

    receipt_id: str
    target_gateway_host: str
    target_gateway_url: str
    upstream_repository: str
    upstream_gate: str
    upstream_state: str
    api_provisioning_allowed: bool
    dns_publication_allowed: bool
    ready: bool
    checked_at_utc: str
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    next_actions: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready upstream blocker receipt."""
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        payload["evidence_refs"] = list(self.evidence_refs)
        payload["next_actions"] = list(self.next_actions)
        return payload


def emit_deployment_upstream_blocker_receipt(
    *,
    target_gateway_url: str,
    upstream_repository: str,
    upstream_gate: str,
    upstream_state: str,
    api_provisioning_allowed: bool,
    dns_publication_allowed: bool,
    blockers: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    next_actions: tuple[str, ...],
    now_utc: datetime | None = None,
) -> DeploymentUpstreamBlockerReceipt:
    """Build a deterministic deployment upstream blocker receipt."""
    normalized_url = _require_gateway_url(target_gateway_url)
    normalized_host = _host_from_gateway_url(normalized_url)
    normalized_repository = _require_repository(upstream_repository)
    normalized_gate = _require_nonempty(upstream_gate, "upstream gate")
    normalized_state = _require_upstream_state(upstream_state)
    normalized_blockers = _unique_nonempty(blockers)
    normalized_evidence_refs = _unique_nonempty(evidence_refs)
    normalized_next_actions = _unique_nonempty(next_actions)
    ready = (
        normalized_state == "SolvedVerified"
        and api_provisioning_allowed
        and dns_publication_allowed
        and not normalized_blockers
    )
    if not ready and not normalized_blockers:
        raise RuntimeError("blocked upstream receipt requires at least one blocker")
    if ready and normalized_blockers:
        raise RuntimeError("ready upstream receipt must not carry blockers")
    checked_at = _format_utc(now_utc or datetime.now(UTC))
    receipt_material = {
        "target_gateway_host": normalized_host,
        "target_gateway_url": normalized_url,
        "upstream_repository": normalized_repository,
        "upstream_gate": normalized_gate,
        "upstream_state": normalized_state,
        "api_provisioning_allowed": api_provisioning_allowed,
        "dns_publication_allowed": dns_publication_allowed,
        "ready": ready,
        "blockers": normalized_blockers,
        "evidence_refs": normalized_evidence_refs,
        "next_actions": normalized_next_actions,
    }
    digest = hashlib.sha256(
        json.dumps(receipt_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return DeploymentUpstreamBlockerReceipt(
        receipt_id=f"deployment-upstream-blocker-{digest[:16]}",
        target_gateway_host=normalized_host,
        target_gateway_url=normalized_url,
        upstream_repository=normalized_repository,
        upstream_gate=normalized_gate,
        upstream_state=normalized_state,
        api_provisioning_allowed=api_provisioning_allowed,
        dns_publication_allowed=dns_publication_allowed,
        ready=ready,
        checked_at_utc=checked_at,
        blockers=normalized_blockers,
        evidence_refs=normalized_evidence_refs,
        next_actions=normalized_next_actions,
    )


def write_deployment_upstream_blocker_receipt(
    receipt: DeploymentUpstreamBlockerReceipt,
    output_path: Path,
) -> Path:
    """Write one deployment upstream blocker receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _require_gateway_url(gateway_url: str) -> str:
    parsed = urlparse(gateway_url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError("target gateway URL must include https scheme and host")
    if parsed.port or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise RuntimeError("target gateway URL must not include port, path, query, or fragment")
    normalized_host = _require_gateway_host(parsed.hostname)
    return f"https://{normalized_host}"


def _host_from_gateway_url(gateway_url: str) -> str:
    parsed = urlparse(gateway_url)
    if not parsed.hostname:
        raise RuntimeError("target gateway URL host is required")
    return _require_gateway_host(parsed.hostname)


def _require_gateway_host(host: str) -> str:
    normalized_host = host.strip().lower()
    if not normalized_host or not _is_dns_name(normalized_host) or "." not in normalized_host:
        raise RuntimeError("target gateway host must be a fully qualified DNS name")
    return normalized_host


def _is_dns_name(value: str) -> bool:
    if not value or len(value) > 253:
        return False
    labels = value.split(".")
    if any(not label or len(label) > 63 for label in labels):
        return False
    return all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)


def _require_repository(repository: str) -> str:
    normalized = repository.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", normalized):
        raise RuntimeError("upstream repository must use owner/name form")
    return normalized


def _require_upstream_state(upstream_state: str) -> str:
    normalized = upstream_state.strip()
    allowed = {"SolvedVerified", "AwaitingEvidence", "GovernanceBlocked", "SafeHalt"}
    if normalized not in allowed:
        raise RuntimeError("upstream state must use the solver outcome taxonomy")
    return normalized


def _require_nonempty(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise RuntimeError(f"{label} is required")
    return normalized


def _unique_nonempty(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse deployment upstream blocker receipt arguments."""
    parser = argparse.ArgumentParser(description="Emit a deployment upstream blocker receipt.")
    parser.add_argument(
        "--target-gateway-url",
        default=os.environ.get("MULLU_GATEWAY_URL", DEFAULT_GATEWAY_URL),
    )
    parser.add_argument("--upstream-repository", default=DEFAULT_UPSTREAM_REPOSITORY)
    parser.add_argument("--upstream-gate", default=DEFAULT_UPSTREAM_GATE)
    parser.add_argument(
        "--upstream-state",
        default="AwaitingEvidence",
        choices=("SolvedVerified", "AwaitingEvidence", "GovernanceBlocked", "SafeHalt"),
    )
    parser.add_argument("--api-provisioning-allowed", action="store_true")
    parser.add_argument("--dns-publication-allowed", action="store_true")
    parser.add_argument("--blocker", action="append", default=[])
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--next-action", action="append", default=[])
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    *,
    now_utc: datetime | None = None,
) -> int:
    """CLI entry point for deployment upstream blocker receipt emission."""
    args = parse_args(argv)
    ready_requested = (
        args.upstream_state == "SolvedVerified"
        and args.api_provisioning_allowed
        and args.dns_publication_allowed
    )
    blockers = tuple(args.blocker) if args.blocker else (() if ready_requested else DEFAULT_BLOCKERS)
    evidence_refs = tuple(args.evidence_ref) if args.evidence_ref else DEFAULT_EVIDENCE_REFS
    next_actions = tuple(args.next_action) if args.next_action else (READY_NEXT_ACTIONS if ready_requested else DEFAULT_NEXT_ACTIONS)
    try:
        receipt = emit_deployment_upstream_blocker_receipt(
            target_gateway_url=args.target_gateway_url,
            upstream_repository=args.upstream_repository,
            upstream_gate=args.upstream_gate,
            upstream_state=args.upstream_state,
            api_provisioning_allowed=args.api_provisioning_allowed,
            dns_publication_allowed=args.dns_publication_allowed,
            blockers=blockers,
            evidence_refs=evidence_refs,
            next_actions=next_actions,
            now_utc=now_utc,
        )
    except RuntimeError as exc:
        print(f"deployment upstream blocker receipt emission failed: {exc}", file=sys.stderr)
        return 1
    output_path = write_deployment_upstream_blocker_receipt(receipt, Path(args.output))
    if args.json:
        print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"deployment_upstream_blocker_receipt: {output_path}")
        print(f"target_gateway_host: {receipt.target_gateway_host}")
        print(f"upstream_state: {receipt.upstream_state}")
        print(f"ready: {str(receipt.ready).lower()}")
    return 0 if receipt.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
