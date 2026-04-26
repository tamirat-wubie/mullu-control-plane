#!/usr/bin/env python3
"""Collect live runtime conformance evidence.

Purpose: probe a gateway conformance endpoint and persist the latest signed
runtime conformance certificate for deployment and operator review.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: standard-library HTTP client and `/runtime/conformance`.
Invariants:
  - Missing endpoint evidence is recorded as a failed collection.
  - HMAC verification is explicit when a conformance secret is supplied.
  - Production readiness is not inferred from an unsigned or expired certificate.
  - Conformance status requires embedded gateway and runtime witness validity.
  - Output preserves the original certificate payload plus collection witness.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import urllib.error
import urllib.request

DEFAULT_GATEWAY_URL = "http://localhost:8001"
DEFAULT_OUTPUT_PATH = Path(".change_assurance") / "runtime_conformance_certificate.json"
REQUIRED_CERTIFICATE_FIELDS = (
    "certificate_id",
    "environment",
    "issued_at",
    "expires_at",
    "gateway_witness_valid",
    "runtime_witness_valid",
    "terminal_status",
    "open_conformance_gaps",
    "evidence_refs",
    "signature_key_id",
    "signature",
)
ACCEPTED_CONFORMANCE_STATUSES = frozenset({"conformant", "conformant_with_gaps"})


@dataclass(frozen=True, slots=True)
class CollectionStep:
    """One causal collection step for a runtime conformance certificate."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class RuntimeConformanceCollection:
    """Persisted wrapper around a live conformance certificate."""

    collection_id: str
    collected_at: str
    gateway_url: str
    endpoint_status: int
    certificate_status: str
    signature_status: str
    certificate: dict[str, Any]
    steps: tuple[CollectionStep, ...]
    errors: tuple[str, ...] = field(default_factory=tuple)

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable collection payload."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def collect_runtime_conformance(
    *,
    gateway_url: str,
    conformance_secret: str = "",
    expected_environment: str = "",
    clock: Callable[[], str] | None = None,
) -> RuntimeConformanceCollection:
    """Probe `/runtime/conformance` and return a bounded collection witness."""
    collected_at = (clock or _utc_now)()
    gateway_base = gateway_url.rstrip("/")
    steps: list[CollectionStep] = []
    errors: list[str] = []

    endpoint_status, certificate = _get_json(f"{gateway_base}/runtime/conformance")
    missing_fields = tuple(field for field in REQUIRED_CERTIFICATE_FIELDS if field not in certificate)
    endpoint_passed = endpoint_status == 200 and not missing_fields
    steps.append(CollectionStep(
        name="runtime conformance endpoint",
        passed=endpoint_passed,
        detail=f"status={endpoint_status} missing={list(missing_fields)}",
    ))
    if not endpoint_passed:
        errors.append("runtime conformance endpoint did not return a complete certificate")

    environment_passed = True
    if expected_environment:
        environment_passed = str(certificate.get("environment", "")) == expected_environment
        steps.append(CollectionStep(
            name="runtime environment",
            passed=environment_passed,
            detail=f"expected={expected_environment} observed={certificate.get('environment', '')}",
        ))
    if not environment_passed:
        errors.append("runtime conformance environment did not match expected value")

    freshness_passed = _certificate_fresh(
        expires_at=str(certificate.get("expires_at", "")),
        observed_at=collected_at,
    )
    steps.append(CollectionStep(
        name="runtime conformance freshness",
        passed=freshness_passed,
        detail=f"expires_at={certificate.get('expires_at', '')} fresh={freshness_passed}",
    ))
    if not freshness_passed:
        errors.append("runtime conformance certificate was expired or malformed")

    certificate_status = str(certificate.get("terminal_status", "missing"))
    status_passed = certificate_status in ACCEPTED_CONFORMANCE_STATUSES
    steps.append(CollectionStep(
        name="runtime conformance terminal status",
        passed=status_passed,
        detail=f"terminal_status={certificate_status}",
    ))
    if not status_passed:
        errors.append("runtime conformance terminal status was not acceptable")

    witness_validity_passed = bool(certificate.get("gateway_witness_valid")) and bool(
        certificate.get("runtime_witness_valid")
    )
    steps.append(CollectionStep(
        name="runtime conformance witness validity",
        passed=witness_validity_passed,
        detail=(
            f"gateway_witness_valid={bool(certificate.get('gateway_witness_valid'))} "
            f"runtime_witness_valid={bool(certificate.get('runtime_witness_valid'))}"
        ),
    ))
    if not witness_validity_passed:
        errors.append("runtime conformance embedded witness validity failed")

    signature_status, signature_passed = _verify_certificate_signature(certificate, conformance_secret)
    steps.append(CollectionStep(
        name="runtime conformance signature",
        passed=signature_passed,
        detail=signature_status,
    ))
    if not signature_passed:
        errors.append("runtime conformance signature was not verified")

    collection_seed = {
        "gateway_url": gateway_base,
        "collected_at": collected_at,
        "certificate_id": certificate.get("certificate_id", ""),
        "terminal_status": certificate_status,
    }
    return RuntimeConformanceCollection(
        collection_id=f"runtime-conformance-collection-{_stable_hash(collection_seed)[:16]}",
        collected_at=collected_at,
        gateway_url=gateway_base,
        endpoint_status=endpoint_status,
        certificate_status=certificate_status,
        signature_status=signature_status,
        certificate=certificate,
        steps=tuple(steps),
        errors=tuple(errors),
    )


def write_runtime_conformance(collection: RuntimeConformanceCollection, output_path: Path) -> Path:
    """Write one runtime conformance collection JSON document."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(collection.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _get_json(url: str) -> tuple[int, dict[str, Any]]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, _loads_json(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _loads_json(exc.read())
    except urllib.error.URLError:
        return 0, {}
    except TimeoutError:
        return 0, {}


def _loads_json(raw: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _verify_certificate_signature(payload: dict[str, Any], conformance_secret: str) -> tuple[str, bool]:
    signature = str(payload.get("signature", ""))
    if not conformance_secret:
        return "skipped:no_conformance_secret", False
    if not signature.startswith("hmac-sha256:"):
        return "failed:missing_hmac_sha256_signature", False
    signed_payload = dict(payload)
    signed_payload.pop("signature", None)
    expected = hmac.new(
        conformance_secret.encode("utf-8"),
        _stable_hash(signed_payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    observed = signature.removeprefix("hmac-sha256:")
    return ("verified", True) if hmac.compare_digest(expected, observed) else ("failed:mismatch", False)


def _certificate_fresh(*, expires_at: str, observed_at: str) -> bool:
    try:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return expires > observed


def _stable_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the runtime conformance collector CLI contract."""
    parser = argparse.ArgumentParser(description="Collect live Mullu runtime conformance evidence.")
    parser.add_argument("--gateway-url", default=os.environ.get("MULLU_GATEWAY_URL", DEFAULT_GATEWAY_URL))
    parser.add_argument("--conformance-secret", default=os.environ.get("MULLU_RUNTIME_CONFORMANCE_SECRET", ""))
    parser.add_argument("--expected-environment", default=os.environ.get("MULLU_EXPECTED_RUNTIME_ENV", ""))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for runtime conformance collection."""
    args = parse_args(argv)
    collection = collect_runtime_conformance(
        gateway_url=args.gateway_url,
        conformance_secret=args.conformance_secret,
        expected_environment=args.expected_environment,
    )
    output_path = write_runtime_conformance(collection, Path(args.output))
    print(f"runtime conformance certificate written: {output_path}")
    print(f"collection_id: {collection.collection_id}")
    print(f"certificate_status: {collection.certificate_status}")
    return 0 if all(step.passed for step in collection.steps) else 1


if __name__ == "__main__":
    raise SystemExit(main())
