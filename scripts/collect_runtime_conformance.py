#!/usr/bin/env python3
"""Collect live runtime conformance evidence.

Purpose: probe a gateway conformance endpoint and persist the latest signed
runtime conformance certificate for deployment and operator review.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: standard-library HTTP client and `/runtime/conformance`.
Invariants:
  - Missing endpoint evidence is recorded as a failed collection.
  - Certificate schema validation happens before production acceptance.
  - HMAC verification is explicit when a conformance secret is supplied.
  - Production readiness is not inferred from an unsigned or expired certificate.
  - Production readiness requires embedded gateway and runtime witness validity.
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

from scripts.validate_schemas import _load_schema, _validate_schema_instance

DEFAULT_GATEWAY_URL = "http://localhost:8001"
DEFAULT_OUTPUT_PATH = Path(".change_assurance") / "runtime_conformance_certificate.json"
RUNTIME_CONFORMANCE_CERTIFICATE_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "schemas"
    / "runtime_conformance_certificate.schema.json"
)
REQUIRED_CERTIFICATE_FIELDS = (
    "certificate_id",
    "environment",
    "issued_at",
    "expires_at",
    "gateway_witness_valid",
    "runtime_witness_valid",
    "latest_anchor_valid",
    "command_closure_canary_passed",
    "capability_admission_canary_passed",
    "dangerous_capability_isolation_canary_passed",
    "streaming_budget_canary_passed",
    "lineage_query_canary_passed",
    "authority_obligation_canary_passed",
    "authority_responsibility_debt_clear",
    "authority_pending_approval_chain_count",
    "authority_overdue_approval_chain_count",
    "authority_open_obligation_count",
    "authority_overdue_obligation_count",
    "authority_escalated_obligation_count",
    "authority_unowned_high_risk_capability_count",
    "authority_directory_sync_receipt_valid",
    "mcp_capability_manifest_configured",
    "mcp_capability_manifest_valid",
    "mcp_capability_manifest_capability_count",
    "capability_plan_bundle_canary_passed",
    "capability_plan_bundle_count",
    "physical_worker_canary_passed",
    "physical_worker_canary_id",
    "physical_worker_canary_artifact_hash",
    "physical_worker_canary_evidence_count",
    "capsule_registry_certified",
    "proof_coverage_matrix_current",
    "proof_coverage_declared_routes_classified",
    "proof_coverage_declared_route_count",
    "proof_coverage_unclassified_route_count",
    "known_limitations_aligned",
    "security_model_aligned",
    "terminal_status",
    "open_conformance_gaps",
    "evidence_refs",
    "checks",
    "signature_key_id",
    "signature",
)
ACCEPTED_CONFORMANCE_STATUSES = frozenset({"conformant", "conformant_with_gaps"})
CORE_CONFORMANCE_BOOL_FIELDS = (
    "latest_anchor_valid",
    "command_closure_canary_passed",
    "capability_admission_canary_passed",
    "dangerous_capability_isolation_canary_passed",
    "streaming_budget_canary_passed",
    "lineage_query_canary_passed",
    "authority_obligation_canary_passed",
    "capsule_registry_certified",
    "physical_worker_canary_passed",
    "proof_coverage_matrix_current",
)


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
    authority_operator_secret: str = "",
    expected_environment: str = "",
    clock: Callable[[], str] | None = None,
) -> RuntimeConformanceCollection:
    """Probe `/runtime/conformance` and return a bounded collection witness."""
    collected_at = (clock or _utc_now)()
    gateway_base = gateway_url.rstrip("/")
    steps: list[CollectionStep] = []
    errors: list[str] = []

    authority_headers = (
        {"X-Mullu-Authority-Secret": authority_operator_secret}
        if authority_operator_secret
        else None
    )

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

    schema_errors = _validate_runtime_conformance_certificate_schema(certificate)
    schema_passed = endpoint_status == 200 and not schema_errors
    steps.append(CollectionStep(
        name="runtime conformance certificate schema",
        passed=schema_passed,
        detail=f"schema_error_count={len(schema_errors)}",
    ))
    if not schema_passed:
        errors.append("runtime conformance certificate schema validation failed")

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

    witness_validity_passed = (
        bool(certificate.get("gateway_witness_valid"))
        and bool(certificate.get("runtime_witness_valid"))
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

    failed_core_canaries = _failed_boolean_fields(certificate, CORE_CONFORMANCE_BOOL_FIELDS)
    core_canaries_passed = not failed_core_canaries
    steps.append(CollectionStep(
        name="runtime conformance core canaries",
        passed=core_canaries_passed,
        detail=f"failed={list(failed_core_canaries)}",
    ))
    if not core_canaries_passed:
        errors.append("runtime conformance core canaries did not all pass")

    declared_routes_classified = bool(certificate.get("proof_coverage_declared_routes_classified"))
    declared_route_count = _int_count(certificate, "proof_coverage_declared_route_count")
    unclassified_route_count = _int_count(certificate, "proof_coverage_unclassified_route_count")
    steps.append(CollectionStep(
        name="runtime conformance proof coverage route classification",
        passed=declared_routes_classified,
        detail=(
            f"classified={declared_routes_classified} "
            f"route_count={declared_route_count} "
            f"unclassified_route_count={unclassified_route_count}"
        ),
    ))
    if not declared_routes_classified:
        errors.append("runtime conformance proof coverage declared routes were not fully classified")

    responsibility_debt_passed = bool(certificate.get("authority_responsibility_debt_clear"))
    steps.append(CollectionStep(
        name="runtime conformance authority responsibility debt",
        passed=responsibility_debt_passed,
        detail=(
            f"clear={responsibility_debt_passed} "
            f"overdue_approval_chain_count={certificate.get('authority_overdue_approval_chain_count', 'missing')} "
            f"overdue_obligation_count={certificate.get('authority_overdue_obligation_count', 'missing')} "
            f"escalated_obligation_count={certificate.get('authority_escalated_obligation_count', 'missing')} "
            "unowned_high_risk_capability_count="
            f"{certificate.get('authority_unowned_high_risk_capability_count', 'missing')}"
        ),
    ))
    if not responsibility_debt_passed:
        errors.append("runtime conformance authority responsibility debt was not clear")

    mcp_manifest_configured = bool(certificate.get("mcp_capability_manifest_configured"))
    mcp_manifest_valid = bool(certificate.get("mcp_capability_manifest_valid"))
    mcp_manifest_passed = (not mcp_manifest_configured) or mcp_manifest_valid
    steps.append(CollectionStep(
        name="runtime conformance mcp capability manifest",
        passed=mcp_manifest_passed,
        detail=(
            f"configured={mcp_manifest_configured} "
            f"valid={mcp_manifest_valid} "
            f"capability_count={certificate.get('mcp_capability_manifest_capability_count', 'missing')}"
        ),
    ))
    if not mcp_manifest_passed:
        errors.append("runtime conformance MCP capability manifest was not valid")

    plan_bundle_passed = bool(certificate.get("capability_plan_bundle_canary_passed"))
    steps.append(CollectionStep(
        name="runtime conformance capability plan evidence bundle",
        passed=plan_bundle_passed,
        detail=(
            f"passed={plan_bundle_passed} "
            f"bundle_count={certificate.get('capability_plan_bundle_count', 'missing')}"
        ),
    ))
    if not plan_bundle_passed:
        errors.append("runtime conformance capability plan evidence bundle was not witnessed")

    physical_worker_canary_passed = bool(certificate.get("physical_worker_canary_passed"))
    physical_worker_canary_evidence_count = _int_count(certificate, "physical_worker_canary_evidence_count")
    physical_worker_canary_evidence_passed = (
        physical_worker_canary_passed
        and physical_worker_canary_evidence_count >= 3
        and bool(str(certificate.get("physical_worker_canary_artifact_hash", "")).strip())
    )
    steps.append(CollectionStep(
        name="runtime conformance physical worker canary",
        passed=physical_worker_canary_evidence_passed,
        detail=(
            f"passed={physical_worker_canary_passed} "
            f"canary_id={certificate.get('physical_worker_canary_id', 'missing')} "
            f"evidence_count={physical_worker_canary_evidence_count}"
        ),
    ))
    if not physical_worker_canary_evidence_passed:
        errors.append("runtime conformance physical worker canary was not witnessed")

    signature_status, signature_passed = _verify_certificate_signature(certificate, conformance_secret)
    steps.append(CollectionStep(
        name="runtime conformance signature",
        passed=signature_passed,
        detail=signature_status,
    ))
    if not signature_passed:
        errors.append("runtime conformance signature was not verified")

    approval_filter_status, approval_filter_payload = _get_json(
        f"{gateway_base}/authority/approval-chains?overdue=true&limit=1",
        headers=authority_headers,
    )
    approval_filter_passed = (
        approval_filter_status == 200
        and isinstance(approval_filter_payload.get("approval_chains"), list)
        and isinstance(approval_filter_payload.get("count"), int)
    )
    steps.append(CollectionStep(
        name="authority overdue approval chain read model",
        passed=approval_filter_passed,
        detail=(
            f"status={approval_filter_status} "
            f"count={approval_filter_payload.get('count', 'missing')}"
        ),
    ))
    if not approval_filter_passed:
        errors.append("authority overdue approval chain read model was not available")

    obligation_filter_status, obligation_filter_payload = _get_json(
        f"{gateway_base}/authority/obligations?overdue=true&limit=1",
        headers=authority_headers,
    )
    obligation_filter_passed = (
        obligation_filter_status == 200
        and isinstance(obligation_filter_payload.get("obligations"), list)
        and isinstance(obligation_filter_payload.get("count"), int)
    )
    steps.append(CollectionStep(
        name="authority overdue obligation read model",
        passed=obligation_filter_passed,
        detail=(
            f"status={obligation_filter_status} "
            f"count={obligation_filter_payload.get('count', 'missing')}"
        ),
    ))
    if not obligation_filter_passed:
        errors.append("authority overdue obligation read model was not available")

    ownership_status, ownership_payload = _get_json(
        f"{gateway_base}/authority/ownership?limit=1",
        headers=authority_headers,
    )
    ownership_passed = (
        ownership_status == 200
        and isinstance(ownership_payload.get("ownership"), list)
        and isinstance(ownership_payload.get("count"), int)
    )
    steps.append(CollectionStep(
        name="authority ownership read model",
        passed=ownership_passed,
        detail=f"status={ownership_status} count={ownership_payload.get('count', 'missing')}",
    ))
    if not ownership_passed:
        errors.append("authority ownership read model was not available")

    policy_status, policy_payload = _get_json(
        f"{gateway_base}/authority/policies?limit=1",
        headers=authority_headers,
    )
    policy_passed = (
        policy_status == 200
        and isinstance(policy_payload.get("approval_policies"), list)
        and isinstance(policy_payload.get("escalation_policies"), list)
        and isinstance(policy_payload.get("approval_count"), int)
        and isinstance(policy_payload.get("escalation_count"), int)
    )
    steps.append(CollectionStep(
        name="authority policy read model",
        passed=policy_passed,
        detail=(
            f"status={policy_status} "
            f"approval_count={policy_payload.get('approval_count', 'missing')} "
            f"escalation_count={policy_payload.get('escalation_count', 'missing')}"
        ),
    ))
    if not policy_passed:
        errors.append("authority policy read model was not available")

    responsibility_status, responsibility_payload = _get_json(
        f"{gateway_base}/authority/responsibility?limit=1",
        headers=authority_headers,
    )
    responsibility_passed = (
        responsibility_status == 200
        and isinstance(responsibility_payload.get("responsibility_debt_clear"), bool)
        and isinstance(responsibility_payload.get("authority_witness"), dict)
        and isinstance(responsibility_payload.get("priority_approval_chains"), list)
        and isinstance(responsibility_payload.get("priority_obligations"), list)
        and isinstance(responsibility_payload.get("priority_escalation_events"), list)
        and isinstance(responsibility_payload.get("evidence_refs"), list)
    )
    steps.append(CollectionStep(
        name="authority responsibility cockpit read model",
        passed=responsibility_passed,
        detail=(
            f"status={responsibility_status} "
            f"debt_clear={responsibility_payload.get('responsibility_debt_clear', 'missing')} "
            f"unresolved_obligation_count={responsibility_payload.get('unresolved_obligation_count', 'missing')}"
        ),
    ))
    if not responsibility_passed:
        errors.append("authority responsibility cockpit read model was not available")

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


def _get_json(url: str, *, headers: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
    request: str | urllib.request.Request
    request = urllib.request.Request(url, headers=headers or {}) if headers else url
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
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


def _failed_boolean_fields(payload: dict[str, Any], field_names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(field_name for field_name in field_names if payload.get(field_name) is not True)


def _int_count(payload: dict[str, Any], field_name: str) -> int:
    value = payload.get(field_name, 0)
    return value if isinstance(value, int) else 0


def _validate_runtime_conformance_certificate_schema(payload: dict[str, Any]) -> tuple[str, ...]:
    """Validate a collected conformance certificate against the public schema."""
    try:
        schema = _load_schema(RUNTIME_CONFORMANCE_CERTIFICATE_SCHEMA_PATH)
    except (OSError, json.JSONDecodeError):
        return ("runtime_conformance_certificate_schema_unavailable",)
    return tuple(_validate_schema_instance(schema, payload))


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
    parser.add_argument("--authority-operator-secret", default=os.environ.get("MULLU_AUTHORITY_OPERATOR_SECRET", ""))
    parser.add_argument("--expected-environment", default=os.environ.get("MULLU_EXPECTED_RUNTIME_ENV", ""))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for runtime conformance collection."""
    args = parse_args(argv)
    collection = collect_runtime_conformance(
        gateway_url=args.gateway_url,
        conformance_secret=args.conformance_secret,
        authority_operator_secret=args.authority_operator_secret,
        expected_environment=args.expected_environment,
    )
    output_path = write_runtime_conformance(collection, Path(args.output))
    print(f"runtime conformance certificate written: {output_path}")
    print(f"collection_id: {collection.collection_id}")
    print(f"certificate_status: {collection.certificate_status}")
    return 0 if all(step.passed for step in collection.steps) else 1


if __name__ == "__main__":
    raise SystemExit(main())
