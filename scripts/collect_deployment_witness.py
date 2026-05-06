#!/usr/bin/env python3
"""Collect live gateway deployment evidence.

Purpose: probe a declared gateway endpoint and emit a bounded deployment
witness without implying production readiness when evidence is missing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: standard-library HTTP client and gateway runtime witness contract.
Invariants:
  - Deployment health is claimed only when health, runtime witness, and
    runtime conformance certificate pass.
  - Public health proof records the probed endpoint, HTTP status, and body digest.
  - Missing or malformed endpoint evidence is recorded as a failed witness.
  - HMAC verification is explicit for runtime and conformance signatures.
  - Output is structured JSON suitable for repository status reflection.
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

DEFAULT_OUTPUT_PATH = Path(".change_assurance") / "deployment_witness.json"
DEFAULT_GATEWAY_URL = "http://localhost:8001"
REQUIRED_WITNESS_FIELDS = (
    "witness_id",
    "environment",
    "runtime_status",
    "gateway_status",
    "responsibility_debt_clear",
    "latest_command_event_hash",
    "latest_terminal_certificate_id",
    "signed_at",
    "signature_key_id",
    "signature",
)
REQUIRED_CONFORMANCE_FIELDS = (
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
    "proof_coverage_declared_routes_classified",
)


@dataclass(frozen=True, slots=True)
class ProbeStep:
    """One causal step in live deployment witness collection."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class DeploymentWitness:
    """Structured output contract for live deployment evidence."""

    witness_id: str
    collected_at: str
    gateway_url: str
    public_health_endpoint: str
    health_http_status: int
    health_response_digest: str
    deployment_claim: str
    health_status: str
    runtime_witness_status: str
    signature_status: str
    conformance_status: str
    conformance_signature_status: str
    latest_conformance_certificate_id: str
    latest_terminal_certificate_id: str | None
    latest_command_event_hash: str
    runtime_witness_id: str
    runtime_environment: str
    runtime_signature_key_id: str
    runtime_responsibility_debt_clear: bool
    authority_responsibility_debt_clear: bool
    authority_pending_approval_chain_count: int
    authority_overdue_approval_chain_count: int
    authority_open_obligation_count: int
    authority_overdue_obligation_count: int
    authority_escalated_obligation_count: int
    authority_unowned_high_risk_capability_count: int
    steps: tuple[ProbeStep, ...]
    errors: tuple[str, ...] = field(default_factory=tuple)

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable witness payload."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def collect_deployment_witness(
    *,
    gateway_url: str,
    witness_secret: str = "",
    conformance_secret: str = "",
    deployment_witness_secret: str = "",
    expected_environment: str = "",
    require_production_evidence: bool = False,
    clock: Callable[[], str] | None = None,
) -> DeploymentWitness:
    """Probe one live gateway and return a deployment witness."""
    gateway_base = gateway_url.rstrip("/")
    collected_at = (clock or _utc_now)()
    steps: list[ProbeStep] = []
    errors: list[str] = []

    public_health_endpoint = f"{gateway_base}/health"
    health_status, health_payload, health_response_digest = _probe_health(gateway_base)
    health_passed = health_status == 200 and health_payload.get("status") == "healthy"
    steps.append(
        ProbeStep(
            name="gateway health",
            passed=health_passed,
            detail=(
                f"endpoint={public_health_endpoint} status={health_status} "
                f"body_status={health_payload.get('status', '')} "
                f"response_digest={health_response_digest}"
            ),
        )
    )
    if not health_passed:
        errors.append("gateway health did not report healthy")

    witness_status, runtime_payload = _probe_runtime_witness(gateway_base)
    missing_fields = tuple(field for field in REQUIRED_WITNESS_FIELDS if field not in runtime_payload)
    runtime_status = str(runtime_payload.get("runtime_status", ""))
    gateway_status = str(runtime_payload.get("gateway_status", ""))
    runtime_responsibility_debt_clear = runtime_payload.get("responsibility_debt_clear") is True
    runtime_passed = (
        witness_status == 200
        and not missing_fields
        and runtime_status == "healthy"
        and gateway_status in {"healthy", "degraded"}
        and runtime_responsibility_debt_clear
    )
    steps.append(
        ProbeStep(
            name="gateway runtime witness",
            passed=runtime_passed,
            detail=(
                f"status={witness_status} runtime_status={runtime_status} "
                f"gateway_status={gateway_status} "
                f"responsibility_debt_clear={runtime_responsibility_debt_clear} "
                f"missing={list(missing_fields)}"
            ),
        )
    )
    if not runtime_passed:
        errors.append("gateway runtime witness is missing required healthy evidence")

    environment_passed = True
    runtime_environment = str(runtime_payload.get("environment", ""))
    if expected_environment:
        environment_passed = runtime_environment == expected_environment
        steps.append(
            ProbeStep(
                name="runtime environment",
                passed=environment_passed,
                detail=f"expected={expected_environment} observed={runtime_environment}",
            )
        )
        if not environment_passed:
            errors.append("runtime environment did not match expected value")

    signature_status, signature_passed = _verify_runtime_signature(runtime_payload, witness_secret)
    steps.append(
        ProbeStep(
            name="runtime witness signature",
            passed=signature_passed,
            detail=signature_status,
        )
    )
    if not signature_passed:
        errors.append("runtime witness signature was not verified")

    conformance_endpoint_status, conformance_payload = _probe_runtime_conformance(gateway_base)
    missing_conformance_fields = tuple(
        field for field in REQUIRED_CONFORMANCE_FIELDS if field not in conformance_payload
    )
    conformance_status = str(conformance_payload.get("terminal_status", ""))
    conformance_environment = str(conformance_payload.get("environment", ""))
    conformance_fresh = _certificate_fresh(
        expires_at=str(conformance_payload.get("expires_at", "")),
        observed_at=collected_at,
    )
    mcp_manifest_configured = bool(conformance_payload.get("mcp_capability_manifest_configured"))
    mcp_manifest_valid = bool(conformance_payload.get("mcp_capability_manifest_valid"))
    mcp_manifest_passed = (not mcp_manifest_configured) or mcp_manifest_valid
    plan_bundle_passed = bool(conformance_payload.get("capability_plan_bundle_canary_passed"))
    physical_worker_canary_passed = bool(conformance_payload.get("physical_worker_canary_passed"))
    physical_worker_canary_evidence_count = _int_count(
        conformance_payload,
        "physical_worker_canary_evidence_count",
    )
    failed_core_canaries = _failed_boolean_fields(
        conformance_payload,
        CORE_CONFORMANCE_BOOL_FIELDS,
    )
    core_canaries_passed = not failed_core_canaries
    conformance_passed = (
        conformance_endpoint_status == 200
        and not missing_conformance_fields
        and conformance_status in ACCEPTED_CONFORMANCE_STATUSES
        and bool(conformance_payload.get("gateway_witness_valid"))
        and bool(conformance_payload.get("runtime_witness_valid"))
        and core_canaries_passed
        and runtime_responsibility_debt_clear
        and bool(conformance_payload.get("authority_responsibility_debt_clear"))
        and mcp_manifest_passed
        and plan_bundle_passed
        and physical_worker_canary_passed
        and physical_worker_canary_evidence_count >= 3
        and conformance_fresh
    )
    if expected_environment:
        conformance_passed = conformance_passed and conformance_environment == expected_environment
    steps.append(
        ProbeStep(
            name="runtime conformance certificate",
            passed=conformance_passed,
            detail=(
                f"status={conformance_endpoint_status} terminal_status={conformance_status} "
                f"environment={conformance_environment} fresh={conformance_fresh} "
                f"responsibility_debt_clear={bool(conformance_payload.get('authority_responsibility_debt_clear'))} "
                f"mcp_manifest_configured={mcp_manifest_configured} "
                f"mcp_manifest_valid={mcp_manifest_valid} "
                f"plan_bundle_passed={plan_bundle_passed} "
                f"physical_worker_canary_passed={physical_worker_canary_passed} "
                f"physical_worker_canary_evidence_count={physical_worker_canary_evidence_count} "
                "proof_route_unclassified_count="
                f"{_int_count(conformance_payload, 'proof_coverage_unclassified_route_count')} "
                f"failed_core_canaries={list(failed_core_canaries)} "
                f"missing={list(missing_conformance_fields)}"
            ),
        )
    )
    if not conformance_passed:
        errors.append("runtime conformance certificate is missing acceptable production evidence")

    conformance_signature_status, conformance_signature_passed = _verify_hmac_signature(
        conformance_payload,
        conformance_secret,
        missing_secret_status="skipped:no_conformance_secret",
        missing_signature_status="failed:missing_hmac_sha256_signature",
    )
    steps.append(
        ProbeStep(
            name="runtime conformance signature",
            passed=conformance_signature_passed,
            detail=conformance_signature_status,
        )
    )
    if not conformance_signature_passed:
        errors.append("runtime conformance signature was not verified")

    if require_production_evidence:
        production_status, production_payload = _probe_production_evidence_witness(gateway_base)
        production_signature_status, production_signature_passed = _verify_signed_claim(
            production_payload,
            deployment_witness_secret,
            missing_secret_status="skipped:no_deployment_witness_secret",
            missing_signature_status="failed:missing_hmac_sha256_signature",
        )
        production_evidence_passed = (
            production_status == 200
            and production_signature_passed
            and not production_payload.get("checks_missing", ())
        )
        steps.append(
            ProbeStep(
                name="production evidence witness",
                passed=production_evidence_passed,
                detail=(
                    f"status={production_status} signature={production_signature_status} "
                    f"deployment_id={production_payload.get('deployment_id', '')} "
                    f"checks_missing={list(production_payload.get('checks_missing', ())) }"
                ),
            )
        )
        if not production_evidence_passed:
            errors.append("production evidence witness is missing required closure")

        capability_status, capability_payload = _probe_capability_evidence(gateway_base)
        capability_evidence_passed = (
            capability_status == 200
            and capability_payload.get("enabled") is True
            and _int_count(capability_payload, "capability_count") > 0
        )
        steps.append(
            ProbeStep(
                name="capability evidence endpoint",
                passed=capability_evidence_passed,
                detail=(
                    f"status={capability_status} enabled={capability_payload.get('enabled')} "
                    f"capability_count={_int_count(capability_payload, 'capability_count')}"
                ),
            )
        )
        if not capability_evidence_passed:
            errors.append("capability evidence endpoint is missing certified capability evidence")

        audit_status, audit_payload = _probe_audit_verification(gateway_base)
        audit_verification_passed = audit_status == 200 and audit_payload.get("valid") is True
        steps.append(
            ProbeStep(
                name="audit verification endpoint",
                passed=audit_verification_passed,
                detail=(
                    f"status={audit_status} valid={audit_payload.get('valid')} "
                    f"reason={audit_payload.get('reason', '')} "
                    f"entries_checked={_int_count(audit_payload, 'entries_checked')}"
                ),
            )
        )
        if not audit_verification_passed:
            errors.append("audit verification endpoint did not verify latest anchor")

        proof_status, proof_payload = _probe_proof_verification(gateway_base)
        proof_verification_passed = proof_status == 200 and proof_payload.get("valid") is True
        steps.append(
            ProbeStep(
                name="proof verification endpoint",
                passed=proof_verification_passed,
                detail=(
                    f"status={proof_status} valid={proof_payload.get('valid')} "
                    f"terminal_status={proof_payload.get('terminal_status', '')} "
                    f"checks_missing={list(proof_payload.get('checks_missing', ())) }"
                ),
            )
        )
        if not proof_verification_passed:
            errors.append("proof verification endpoint did not close all checks")

    claim_passed = all(step.passed for step in steps)
    deployment_claim = "published" if claim_passed else "not-published"
    latest_terminal_certificate_id = runtime_payload.get("latest_terminal_certificate_id")
    latest_terminal_certificate_id = (
        str(latest_terminal_certificate_id)
        if latest_terminal_certificate_id is not None
        else None
    )
    witness_seed = {
        "gateway_url": gateway_base,
        "public_health_endpoint": public_health_endpoint,
        "health_response_digest": health_response_digest,
        "collected_at": collected_at,
        "deployment_claim": deployment_claim,
        "runtime_witness_id": str(runtime_payload.get("witness_id", "")),
        "conformance_certificate_id": str(conformance_payload.get("certificate_id", "")),
        "latest_command_event_hash": str(runtime_payload.get("latest_command_event_hash", "")),
    }
    return DeploymentWitness(
        witness_id=f"deployment-witness-{_stable_hash(witness_seed)[:16]}",
        collected_at=collected_at,
        gateway_url=gateway_base,
        public_health_endpoint=public_health_endpoint,
        health_http_status=health_status,
        health_response_digest=health_response_digest,
        deployment_claim=deployment_claim,
        health_status=str(health_payload.get("status", "")),
        runtime_witness_status=runtime_status,
        signature_status=signature_status,
        conformance_status=conformance_status,
        conformance_signature_status=conformance_signature_status,
        latest_conformance_certificate_id=str(conformance_payload.get("certificate_id", "")),
        latest_terminal_certificate_id=latest_terminal_certificate_id,
        latest_command_event_hash=str(runtime_payload.get("latest_command_event_hash", "")),
        runtime_witness_id=str(runtime_payload.get("witness_id", "")),
        runtime_environment=runtime_environment,
        runtime_signature_key_id=str(runtime_payload.get("signature_key_id", "")),
        runtime_responsibility_debt_clear=runtime_responsibility_debt_clear,
        authority_responsibility_debt_clear=bool(
            conformance_payload.get("authority_responsibility_debt_clear")
        ),
        authority_pending_approval_chain_count=_int_count(
            conformance_payload,
            "authority_pending_approval_chain_count",
        ),
        authority_overdue_approval_chain_count=_int_count(
            conformance_payload,
            "authority_overdue_approval_chain_count",
        ),
        authority_open_obligation_count=_int_count(
            conformance_payload,
            "authority_open_obligation_count",
        ),
        authority_overdue_obligation_count=_int_count(
            conformance_payload,
            "authority_overdue_obligation_count",
        ),
        authority_escalated_obligation_count=_int_count(
            conformance_payload,
            "authority_escalated_obligation_count",
        ),
        authority_unowned_high_risk_capability_count=_int_count(
            conformance_payload,
            "authority_unowned_high_risk_capability_count",
        ),
        steps=tuple(steps),
        errors=tuple(errors),
    )


def write_deployment_witness(witness: DeploymentWitness, output_path: Path) -> Path:
    """Write one deployment witness JSON document."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(witness.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _probe_health(gateway_base: str) -> tuple[int, dict[str, Any], str]:
    status, payload, response_digest = _get_json_with_digest(f"{gateway_base}/health")
    return status, payload, response_digest


def _probe_runtime_witness(gateway_base: str) -> tuple[int, dict[str, Any]]:
    status, payload = _get_json(f"{gateway_base}/gateway/witness")
    return status, payload


def _probe_runtime_conformance(gateway_base: str) -> tuple[int, dict[str, Any]]:
    status, payload = _get_json(f"{gateway_base}/runtime/conformance")
    return status, payload


def _probe_production_evidence_witness(gateway_base: str) -> tuple[int, dict[str, Any]]:
    status, payload = _get_json(f"{gateway_base}/deployment/witness")
    return status, payload


def _probe_capability_evidence(gateway_base: str) -> tuple[int, dict[str, Any]]:
    status, payload = _get_json(f"{gateway_base}/capabilities/evidence")
    return status, payload


def _probe_audit_verification(gateway_base: str) -> tuple[int, dict[str, Any]]:
    status, payload = _get_json(f"{gateway_base}/audit/verify")
    return status, payload


def _probe_proof_verification(gateway_base: str) -> tuple[int, dict[str, Any]]:
    status, payload = _get_json(f"{gateway_base}/proof/verify")
    return status, payload


def _get_json(url: str) -> tuple[int, dict[str, Any]]:
    status, payload, _response_digest = _get_json_with_digest(url)
    return status, payload


def _get_json_with_digest(url: str) -> tuple[int, dict[str, Any], str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            raw = response.read()
            return response.status, _loads_json(raw), _response_digest(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, _loads_json(raw), _response_digest(raw)
    except urllib.error.URLError:
        return 0, {}, _response_digest(b"")
    except TimeoutError:
        return 0, {}, _response_digest(b"")


def _loads_json(raw: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _response_digest(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _verify_runtime_signature(payload: dict[str, Any], witness_secret: str) -> tuple[str, bool]:
    return _verify_hmac_signature(
        payload,
        witness_secret,
        missing_secret_status="skipped:no_witness_secret",
        missing_signature_status="failed:missing_hmac_sha256_signature",
    )


def _verify_hmac_signature(
    payload: dict[str, Any],
    secret: str,
    *,
    missing_secret_status: str,
    missing_signature_status: str,
) -> tuple[str, bool]:
    signature = str(payload.get("signature", ""))
    if not secret:
        return missing_secret_status, False
    if not signature.startswith("hmac-sha256:"):
        return missing_signature_status, False
    signed_payload = dict(payload)
    signed_payload.pop("signature", None)
    signature_payload = _stable_hash(signed_payload)
    expected = hmac.new(
        secret.encode("utf-8"),
        signature_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    observed = signature.removeprefix("hmac-sha256:")
    return ("verified", True) if hmac.compare_digest(expected, observed) else ("failed:mismatch", False)


def _verify_signed_claim(
    payload: dict[str, Any],
    secret: str,
    *,
    missing_secret_status: str,
    missing_signature_status: str,
) -> tuple[str, bool]:
    signature = str(payload.get("signature", ""))
    if not secret:
        return missing_secret_status, False
    if not signature.startswith("hmac-sha256:"):
        return missing_signature_status, False
    signed_payload = dict(payload)
    signed_payload.pop("signature", None)
    observed_claim_hash = str(signed_payload.pop("claim_hash", ""))
    expected_claim_hash = _stable_hash(signed_payload)
    if not hmac.compare_digest(observed_claim_hash, expected_claim_hash):
        return "failed:claim_hash_mismatch", False
    expected = hmac.new(
        secret.encode("utf-8"),
        expected_claim_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    observed = signature.removeprefix("hmac-sha256:")
    return ("verified", True) if hmac.compare_digest(expected, observed) else ("failed:mismatch", False)


def _failed_boolean_fields(payload: dict[str, Any], field_names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(field_name for field_name in field_names if payload.get(field_name) is not True)


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
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _int_count(payload: dict[str, Any], field_name: str) -> int:
    value = payload.get(field_name, 0)
    return value if isinstance(value, int) else 0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the deployment witness collector CLI contract."""
    parser = argparse.ArgumentParser(description="Collect live Mullu gateway deployment evidence.")
    parser.add_argument("--gateway-url", default=os.environ.get("MULLU_GATEWAY_URL", DEFAULT_GATEWAY_URL))
    parser.add_argument("--witness-secret", default=os.environ.get("MULLU_RUNTIME_WITNESS_SECRET", ""))
    parser.add_argument("--conformance-secret", default=os.environ.get("MULLU_RUNTIME_CONFORMANCE_SECRET", ""))
    parser.add_argument("--deployment-witness-secret", default=os.environ.get("MULLU_DEPLOYMENT_WITNESS_SECRET", ""))
    parser.add_argument("--expected-environment", default=os.environ.get("MULLU_EXPECTED_RUNTIME_ENV", ""))
    parser.add_argument(
        "--require-production-evidence",
        action="store_true",
        default=os.environ.get("MULLU_REQUIRE_PRODUCTION_EVIDENCE", "").strip().lower() in {"1", "true", "yes", "on"},
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for deployment witness collection."""
    args = parse_args(argv)
    witness = collect_deployment_witness(
        gateway_url=args.gateway_url,
        witness_secret=args.witness_secret,
        conformance_secret=args.conformance_secret,
        deployment_witness_secret=args.deployment_witness_secret,
        expected_environment=args.expected_environment,
        require_production_evidence=args.require_production_evidence,
    )
    output_path = write_deployment_witness(witness, Path(args.output))
    print(f"deployment witness written: {output_path}")
    print(f"witness_id: {witness.witness_id}")
    print(f"deployment_claim: {witness.deployment_claim}")
    return 0 if witness.deployment_claim == "published" else 1


if __name__ == "__main__":
    raise SystemExit(main())
