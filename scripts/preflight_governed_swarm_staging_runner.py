#!/usr/bin/env python3
"""Preflight governed swarm staging witness runner readiness.

Purpose: emit a deterministic receipt proving the selected runner can provide
the local surfaces required by the governed swarm staging witness workflow.
Governance scope: runner placement, runtime bridge visibility, audit-store
visibility, and operator-supplied dispatch inputs.
Dependencies: standard library filesystem checks.
Invariants: no witness collection occurs here; every failed readiness check is
reported with causal context; the command exits non-zero when readiness is not
proved.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse


DEFAULT_OUTPUT = Path(".change_assurance") / "governed_swarm_staging_runner_preflight.json"


@dataclass(frozen=True, slots=True)
class RunnerPreflightCheck:
    """One governed swarm staging runner readiness check."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class RunnerPreflightReceipt:
    """Structured governed swarm staging runner preflight receipt."""

    receipt_id: str
    checked_at: str
    staging_url: str
    control_plane_commit: str
    runtime_path: str
    audit_store_path: str
    ready: bool
    outcome: str
    checks: tuple[RunnerPreflightCheck, ...]

    def to_json_dict(self) -> dict[str, object]:
        """Return a JSON-serializable receipt payload."""

        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def preflight_runner(
    *,
    staging_url: str,
    control_plane_commit: str,
    runtime_path: Path,
    audit_store_path: Path,
    clock: Callable[[], str] | None = None,
) -> RunnerPreflightReceipt:
    """Return a governed swarm staging runner readiness receipt."""

    checks = (
        _check_staging_url(staging_url),
        _check_control_plane_commit(control_plane_commit),
        _check_runtime_bridge(runtime_path),
        _check_audit_store_exists(audit_store_path),
        _check_audit_store_readable(audit_store_path),
    )
    ready = all(check.passed for check in checks)
    now = clock or _utc_now
    return RunnerPreflightReceipt(
        receipt_id=f"governed-swarm-runner-preflight-{secrets.token_hex(8)}",
        checked_at=now(),
        staging_url=staging_url,
        control_plane_commit=control_plane_commit,
        runtime_path=str(runtime_path),
        audit_store_path=str(audit_store_path),
        ready=ready,
        outcome="SolvedVerified" if ready else "AwaitingEvidence",
        checks=checks,
    )


def write_receipt(receipt: RunnerPreflightReceipt, output_path: Path) -> None:
    """Write a governed swarm staging runner preflight receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _check_staging_url(staging_url: str) -> RunnerPreflightCheck:
    parsed = urlparse(staging_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return RunnerPreflightCheck(
            name="staging_url",
            passed=False,
            detail="staging URL must include http or https scheme and host",
        )
    return RunnerPreflightCheck(name="staging_url", passed=True, detail=parsed.netloc)


def _check_control_plane_commit(control_plane_commit: str) -> RunnerPreflightCheck:
    value = control_plane_commit.strip()
    if not value:
        return RunnerPreflightCheck(
            name="control_plane_commit",
            passed=False,
            detail="deployed control-plane commit is required",
        )
    if len(value) < 7:
        return RunnerPreflightCheck(
            name="control_plane_commit",
            passed=False,
            detail="deployed control-plane commit must be at least 7 characters",
        )
    return RunnerPreflightCheck(name="control_plane_commit", passed=True, detail=value)


def _check_runtime_bridge(runtime_path: Path) -> RunnerPreflightCheck:
    bridge_path = runtime_path / "mcoi_runtime" / "swarm"
    if not bridge_path.is_dir():
        return RunnerPreflightCheck(
            name="runtime_bridge",
            passed=False,
            detail=f"runtime bridge directory missing: {bridge_path}",
        )
    return RunnerPreflightCheck(name="runtime_bridge", passed=True, detail=str(bridge_path))


def _check_audit_store_exists(audit_store_path: Path) -> RunnerPreflightCheck:
    if not audit_store_path.is_file():
        return RunnerPreflightCheck(
            name="audit_store_exists",
            passed=False,
            detail=f"audit JSONL file missing: {audit_store_path}",
        )
    return RunnerPreflightCheck(name="audit_store_exists", passed=True, detail=str(audit_store_path))


def _check_audit_store_readable(audit_store_path: Path) -> RunnerPreflightCheck:
    try:
        with audit_store_path.open("r", encoding="utf-8"):
            pass
    except OSError as exc:
        return RunnerPreflightCheck(
            name="audit_store_readable",
            passed=False,
            detail=f"audit JSONL file is not readable: {exc}",
        )
    return RunnerPreflightCheck(name="audit_store_readable", passed=True, detail=str(audit_store_path))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-url", required=True)
    parser.add_argument("--control-plane-commit", required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--audit-store-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    receipt = preflight_runner(
        staging_url=args.staging_url,
        control_plane_commit=args.control_plane_commit,
        runtime_path=args.runtime_path,
        audit_store_path=args.audit_store_path,
    )
    write_receipt(receipt, args.output)

    for check in receipt.checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"[{status}] {check.name}: {check.detail}")
    print(f"receipt: {args.output}")
    print(f"STATUS: {'passed' if receipt.ready else 'failed'}")
    return 0 if receipt.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
