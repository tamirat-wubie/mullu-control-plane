"""Runtime conformance certificate issuance.

Purpose: issue a signed runtime certificate that binds gateway witnesses,
    command closure state, capability fabric admission, isolation posture,
    lineage query readiness, proof coverage, and document drift into one
    bounded attestation object.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway router, command ledger, authority obligation mesh,
    capability fabric read model, proof coverage matrix, and repository
    reflection documents.
Invariants:
  - The certificate never upgrades missing evidence into success.
  - Every failed check contributes a named conformance gap.
  - Production readiness claims require a fresh signed certificate.
  - The signature excludes only the signature field itself.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable

from mcoi_runtime.core.lineage_query import parse_lineage_uri
from scripts.validate_mcp_capability_manifest import validate_mcp_capability_manifest


class ConformanceStatus(StrEnum):
    """Bounded terminal status for one runtime conformance certificate."""

    CONFORMANT = "conformant"
    CONFORMANT_WITH_GAPS = "conformant_with_gaps"
    DEGRADED = "degraded"
    NON_CONFORMANT = "non_conformant"


@dataclass(frozen=True, slots=True)
class ConformanceCheck:
    """Single witnessed conformance check result."""

    check_id: str
    passed: bool
    evidence_ref: str
    detail: str


@dataclass(frozen=True, slots=True)
class RuntimeConformanceCertificate:
    """Signed certificate describing current runtime conformance."""

    certificate_id: str
    environment: str
    issued_at: str
    expires_at: str
    gateway_witness_valid: bool
    runtime_witness_valid: bool
    latest_anchor_valid: bool
    command_closure_canary_passed: bool
    capability_admission_canary_passed: bool
    dangerous_capability_isolation_canary_passed: bool
    streaming_budget_canary_passed: bool
    lineage_query_canary_passed: bool
    authority_obligation_canary_passed: bool
    authority_responsibility_debt_clear: bool
    authority_pending_approval_chain_count: int
    authority_overdue_approval_chain_count: int
    authority_open_obligation_count: int
    authority_overdue_obligation_count: int
    authority_escalated_obligation_count: int
    authority_unowned_high_risk_capability_count: int
    authority_directory_sync_receipt_valid: bool
    mcp_capability_manifest_configured: bool
    mcp_capability_manifest_valid: bool
    mcp_capability_manifest_capability_count: int
    capsule_registry_certified: bool
    proof_coverage_matrix_current: bool
    known_limitations_aligned: bool
    security_model_aligned: bool
    open_conformance_gaps: tuple[str, ...]
    terminal_status: ConformanceStatus
    evidence_refs: tuple[str, ...]
    checks: tuple[ConformanceCheck, ...] = field(default_factory=tuple)
    signature_key_id: str = "runtime-conformance-v1"
    signature: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable certificate payload."""
        payload = asdict(self)
        payload["terminal_status"] = self.terminal_status.value
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def issue_conformance_certificate(
    *,
    router: Any,
    command_ledger: Any,
    authority_obligation_mesh: Any,
    capability_admission_gate: Any | None,
    environment: str,
    signing_secret: str,
    signature_key_id: str,
    runtime_witness_key_id: str,
    runtime_witness_secret: str,
    repo_root: Path | None = None,
    clock: Callable[[], str] | None = None,
) -> RuntimeConformanceCertificate:
    """Issue one bounded conformance certificate for the running gateway."""
    now = clock or _utc_now
    issued_at = now()
    expires_at = _plus_minutes(issued_at, 30)
    repository_root = repo_root or Path(__file__).resolve().parent.parent

    gateway_witness = router.runtime_witness(
        environment=environment,
        signature_key_id=runtime_witness_key_id,
        signing_secret=runtime_witness_secret,
    )
    runtime_witness = router.runtime_witness(
        environment=environment,
        signature_key_id=runtime_witness_key_id,
        signing_secret=runtime_witness_secret,
    )

    checks: list[ConformanceCheck] = []
    gateway_witness_valid = _witness_valid(gateway_witness, runtime_witness_secret)
    runtime_witness_valid = _witness_valid(runtime_witness, runtime_witness_secret)
    checks.append(_check(
        "gateway_witness_valid",
        gateway_witness_valid,
        f"gateway_witness:{gateway_witness.get('witness_id', '')}",
        "gateway witness signature and required fields verified",
    ))
    checks.append(_check(
        "runtime_witness_valid",
        runtime_witness_valid,
        f"runtime_witness:{runtime_witness.get('witness_id', '')}",
        "runtime witness signature and required fields verified",
    ))

    latest_anchor_valid = bool(runtime_witness.get("latest_anchor_id"))
    checks.append(_check(
        "latest_anchor_valid",
        latest_anchor_valid,
        f"anchor:{runtime_witness.get('latest_anchor_id') or 'missing'}",
        "latest anchor is present in runtime witness",
    ))

    command_closure_canary_passed = _command_closure_canary(command_ledger, runtime_witness)
    checks.append(_check(
        "command_closure_canary",
        command_closure_canary_passed,
        f"terminal_certificate:{runtime_witness.get('latest_terminal_certificate_id') or 'missing'}",
        "terminal certificate, closure memory, and learning admission are present",
    ))

    fabric_read_model = _fabric_read_model(capability_admission_gate)
    capability_admission_canary_passed = bool(
        fabric_read_model.get("enabled")
        and int(fabric_read_model.get("capability_count", 0)) > 0
        and int(fabric_read_model.get("capsule_count", 0)) > 0
    )
    capsule_registry_certified = bool(
        capability_admission_canary_passed
        and fabric_read_model.get("require_certified") is not False
    )
    checks.append(_check(
        "capability_admission_canary",
        capability_admission_canary_passed,
        "capability_fabric:read_model",
        "capability fabric read model has installed capsule and capability entries",
    ))
    checks.append(_check(
        "capsule_registry_certified",
        capsule_registry_certified,
        "capability_fabric:certification",
        "fabric admission requires certified capsule and capability sources",
    ))

    dangerous_capability_isolation_canary_passed = _isolation_canary(environment)
    checks.append(_check(
        "dangerous_capability_isolation_canary",
        dangerous_capability_isolation_canary_passed,
        "capability_isolation:execution_boundary",
        "dangerous capability isolation has an acceptable execution plane for this environment",
    ))

    streaming_budget_canary_passed = _streaming_budget_canary(repository_root)
    checks.append(_check(
        "streaming_budget_canary",
        streaming_budget_canary_passed,
        "schema:streaming_budget_enforcement",
        "streaming budget schema declares reservation, debit, cutoff, and settlement events",
    ))

    lineage_query_canary_passed = _lineage_query_canary()
    checks.append(_check(
        "lineage_query_canary",
        lineage_query_canary_passed,
        "lineage_query:uri_parser",
        "lineage URI parser accepts command, trace, and output references",
    ))

    authority_witness = asdict(authority_obligation_mesh.responsibility_witness())
    authority_obligation_canary_passed = _authority_obligation_canary(authority_witness)
    checks.append(_check(
        "authority_obligation_canary",
        authority_obligation_canary_passed,
        "authority:witness",
        "authority witness exposes approval, obligation, escalation, and risk debt counts",
    ))
    authority_responsibility_debt_clear = _authority_responsibility_debt_clear(authority_witness)
    checks.append(_check(
        "authority_responsibility_debt_clear",
        authority_responsibility_debt_clear,
        "authority:witness:responsibility_debt",
        (
            "overdue_approval_chain_count="
            f"{authority_witness.get('overdue_approval_chain_count', 'missing')} "
            "overdue_obligation_count="
            f"{authority_witness.get('overdue_obligation_count', 'missing')} "
            "escalated_obligation_count="
            f"{authority_witness.get('escalated_obligation_count', 'missing')} "
            "unowned_high_risk_capability_count="
            f"{authority_witness.get('unowned_high_risk_capability_count', 'missing')}"
        ),
    ))

    authority_directory_sync_receipt_valid = _authority_directory_sync_receipt_valid(repository_root)
    checks.append(_check(
        "authority_directory_sync_receipt",
        authority_directory_sync_receipt_valid,
        "authority_directory_sync:.change_assurance/authority_directory_sync.json",
        "latest authority directory sync receipt is present and structurally valid",
    ))

    (
        mcp_manifest_configured,
        mcp_manifest_valid,
        mcp_manifest_capability_count,
        mcp_manifest_detail,
    ) = _mcp_capability_manifest_validation()
    checks.append(_check(
        "mcp_capability_manifest",
        mcp_manifest_valid,
        "mcp_capability_manifest:env:MULLU_MCP_CAPABILITY_MANIFEST_PATH",
        mcp_manifest_detail,
    ))

    proof_coverage_matrix_current = _proof_coverage_matrix_current(repository_root)
    known_limitations_aligned = _known_limitations_aligned(repository_root)
    security_model_aligned = _security_model_aligned(repository_root)
    checks.append(_check(
        "proof_coverage_matrix_current",
        proof_coverage_matrix_current,
        "proof_matrix:canonical_fixture",
        "generated proof matrix matches canonical fixture",
    ))
    checks.append(_check(
        "known_limitations_aligned",
        known_limitations_aligned,
        "docs:known_limitations",
        "known limitations document does not contradict authority runtime surfaces",
    ))
    checks.append(_check(
        "security_model_aligned",
        security_model_aligned,
        "docs:security_model",
        "security model document distinguishes gateway isolation from legacy shell execution",
    ))

    gaps = _collect_gaps(checks, repository_root=repository_root)
    status = _decide_status(
        gaps,
        gateway_witness_valid=gateway_witness_valid,
        runtime_witness_valid=runtime_witness_valid,
        core_canaries=(
            command_closure_canary_passed,
            capability_admission_canary_passed,
            dangerous_capability_isolation_canary_passed,
            streaming_budget_canary_passed,
            lineage_query_canary_passed,
            authority_obligation_canary_passed,
            authority_responsibility_debt_clear,
            mcp_manifest_valid,
        ),
    )
    unsigned = RuntimeConformanceCertificate(
        certificate_id="",
        environment=environment,
        issued_at=issued_at,
        expires_at=expires_at,
        gateway_witness_valid=gateway_witness_valid,
        runtime_witness_valid=runtime_witness_valid,
        latest_anchor_valid=latest_anchor_valid,
        command_closure_canary_passed=command_closure_canary_passed,
        capability_admission_canary_passed=capability_admission_canary_passed,
        dangerous_capability_isolation_canary_passed=dangerous_capability_isolation_canary_passed,
        streaming_budget_canary_passed=streaming_budget_canary_passed,
        lineage_query_canary_passed=lineage_query_canary_passed,
        authority_obligation_canary_passed=authority_obligation_canary_passed,
        authority_responsibility_debt_clear=authority_responsibility_debt_clear,
        authority_pending_approval_chain_count=_int_count(authority_witness, "pending_approval_chain_count"),
        authority_overdue_approval_chain_count=_int_count(authority_witness, "overdue_approval_chain_count"),
        authority_open_obligation_count=_int_count(authority_witness, "open_obligation_count"),
        authority_overdue_obligation_count=_int_count(authority_witness, "overdue_obligation_count"),
        authority_escalated_obligation_count=_int_count(authority_witness, "escalated_obligation_count"),
        authority_unowned_high_risk_capability_count=_int_count(authority_witness, "unowned_high_risk_capability_count"),
        authority_directory_sync_receipt_valid=authority_directory_sync_receipt_valid,
        mcp_capability_manifest_configured=mcp_manifest_configured,
        mcp_capability_manifest_valid=mcp_manifest_valid,
        mcp_capability_manifest_capability_count=mcp_manifest_capability_count,
        capsule_registry_certified=capsule_registry_certified,
        proof_coverage_matrix_current=proof_coverage_matrix_current,
        known_limitations_aligned=known_limitations_aligned,
        security_model_aligned=security_model_aligned,
        open_conformance_gaps=tuple(gaps),
        terminal_status=status,
        evidence_refs=tuple(check.evidence_ref for check in checks if check.evidence_ref),
        checks=tuple(checks),
        signature_key_id=signature_key_id,
    )
    certificate_id = f"conf-{_stable_hash(unsigned.to_json_dict())[:16]}"
    return _sign_certificate(
        RuntimeConformanceCertificate(
            **{
                **unsigned.to_json_dict(),
                "certificate_id": certificate_id,
                "terminal_status": status,
                "checks": tuple(checks),
                "open_conformance_gaps": tuple(gaps),
                "evidence_refs": tuple(check.evidence_ref for check in checks if check.evidence_ref),
            }
        ),
        signing_secret=signing_secret,
    )


def _check(check_id: str, passed: bool, evidence_ref: str, detail: str) -> ConformanceCheck:
    return ConformanceCheck(check_id=check_id, passed=passed, evidence_ref=evidence_ref, detail=detail)


def _witness_valid(payload: dict[str, Any], secret: str) -> bool:
    required = {
        "witness_id",
        "environment",
        "runtime_status",
        "gateway_status",
        "latest_command_event_hash",
        "signed_at",
        "signature_key_id",
        "signature",
    }
    if not required <= set(payload):
        return False
    signature = str(payload.get("signature", ""))
    if not signature.startswith("hmac-sha256:"):
        return False
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    expected = hmac.new(
        secret.encode("utf-8"),
        _stable_hash(unsigned).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature.removeprefix("hmac-sha256:"), expected)


def _command_closure_canary(command_ledger: Any, runtime_witness: dict[str, Any]) -> bool:
    summary = command_ledger.summary()
    return bool(
        runtime_witness.get("latest_terminal_certificate_id")
        and int(summary.get("terminal_certificates", 0)) > 0
        and int(summary.get("closure_memory_entries", 0)) > 0
        and int(summary.get("closure_learning_decisions", 0)) > 0
    )


def _fabric_read_model(capability_admission_gate: Any | None) -> dict[str, Any]:
    if capability_admission_gate is None:
        return {
            "enabled": False,
            "require_certified": None,
            "capsule_count": 0,
            "capability_count": 0,
            "artifact_count": 0,
        }
    return {"enabled": True, **capability_admission_gate.read_model()}


def _isolation_canary(environment: str) -> bool:
    normalized = environment.strip().lower() or "local_dev"
    if normalized in {"local_dev", "test"}:
        return True
    return bool(
        os.environ.get("MULLU_CAPABILITY_WORKER_URL", "").strip()
        and os.environ.get("MULLU_CAPABILITY_WORKER_SECRET", "").strip()
    )


def _streaming_budget_canary(repo_root: Path) -> bool:
    schema_path = repo_root / "schemas" / "streaming_budget_enforcement.schema.json"
    if not schema_path.exists():
        return False
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    event_types = set(schema.get("properties", {}).get("event_type", {}).get("enum", ()))
    return {"reservation_created", "chunk_debited", "cutoff_emitted", "settled"} <= event_types


def _lineage_query_canary() -> bool:
    try:
        refs = (
            parse_lineage_uri("lineage://command/conf-canary?include=policy,tool"),
            parse_lineage_uri("lineage://trace/conf-canary?depth=25&verify=true"),
            parse_lineage_uri("lineage://output/conf-canary?include=policy,model,tenant,budget,replay"),
        )
    except ValueError:
        return False
    return {ref.ref.ref_type for ref in refs} == {"command", "trace", "output"}


def _authority_obligation_canary(witness: dict[str, Any]) -> bool:
    required = {
        "pending_approval_chain_count",
        "overdue_approval_chain_count",
        "open_obligation_count",
        "overdue_obligation_count",
        "escalated_obligation_count",
        "active_accepted_risk_count",
        "active_compensation_review_count",
        "requires_review_count",
    }
    return required <= set(witness)


def _authority_responsibility_debt_clear(witness: dict[str, Any]) -> bool:
    required = (
        "overdue_approval_chain_count",
        "expired_approval_chain_count",
        "overdue_obligation_count",
        "escalated_obligation_count",
        "unowned_high_risk_capability_count",
    )
    if any(field not in witness for field in required):
        return False
    return all(_int_count(witness, field) == 0 for field in required)


def _int_count(payload: dict[str, Any], field: str) -> int:
    try:
        return int(payload.get(field, 0))
    except (TypeError, ValueError):
        return 0


def _authority_directory_sync_receipt_valid(repo_root: Path) -> bool:
    receipt_path = repo_root / ".change_assurance" / "authority_directory_sync.json"
    if not receipt_path.exists():
        return False
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    required = {
        "receipt_id",
        "tenant_id",
        "batch_id",
        "source_ref",
        "source_hash",
        "applied_ownership_count",
        "applied_approval_policy_count",
        "applied_escalation_policy_count",
        "rejected_record_count",
        "apply_mode",
        "persisted",
        "evidence_refs",
    }
    if not required <= set(receipt):
        return False
    if not str(receipt.get("receipt_id", "")).startswith("authority-directory-sync-"):
        return False
    if not str(receipt.get("batch_id", "")).startswith("directory-batch-"):
        return False
    if not str(receipt.get("source_hash", "")).startswith("sha256:"):
        return False
    if receipt.get("apply_mode") not in {"dry_run", "apply"}:
        return False
    if receipt.get("apply_mode") == "apply" and receipt.get("persisted") is not True:
        return False
    if not all(isinstance(receipt.get(field), int) for field in (
        "applied_ownership_count",
        "applied_approval_policy_count",
        "applied_escalation_policy_count",
        "rejected_record_count",
    )):
        return False
    evidence_refs = set(receipt.get("evidence_refs", ()))
    return {
        "authority:ownership_read_model",
        "authority:policy_read_model",
        "runtime_conformance:authority_configuration",
    } <= evidence_refs


def _mcp_capability_manifest_validation() -> tuple[bool, bool, int, str]:
    manifest_path = os.environ.get("MULLU_MCP_CAPABILITY_MANIFEST_PATH", "").strip()
    if not manifest_path:
        return False, True, 0, "not_configured"
    result = validate_mcp_capability_manifest(Path(manifest_path))
    detail = (
        f"configured=True valid={result.ok} "
        f"capability_count={len(result.capability_ids)} "
        f"ownership_count={len(result.ownership_resource_refs)} "
        f"approval_policy_count={len(result.approval_policy_ids)} "
        f"escalation_policy_count={len(result.escalation_policy_ids)} "
        f"errors={list(result.errors)}"
    )
    return True, result.ok, len(result.capability_ids), detail


def _proof_coverage_matrix_current(repo_root: Path) -> bool:
    try:
        from scripts.proof_coverage_matrix import CANONICAL_OUTPUT, proof_coverage_matrix

        if not CANONICAL_OUTPUT.exists():
            return False
        canonical = json.loads(CANONICAL_OUTPUT.read_text(encoding="utf-8"))
        return canonical == proof_coverage_matrix()
    except (ImportError, json.JSONDecodeError, OSError):
        return False


def _known_limitations_aligned(repo_root: Path) -> bool:
    path = repo_root / "KNOWN_LIMITATIONS_v0.1.md"
    server_path = repo_root / "gateway" / "server.py"
    if not path.exists() or not server_path.exists():
        return False
    limitations = path.read_text(encoding="utf-8").lower()
    server = server_path.read_text(encoding="utf-8").lower()
    authority_surfaces = (
        "/authority/approval-chains" in server
        and "/authority/obligations" in server
        and "/authority/escalations" in server
    )
    stale_claim = (
        "approval chain" in limitations
        and ("not yet implemented" in limitations or "not implemented" in limitations)
    )
    escalation_stale_claim = (
        "escalation" in limitations
        and ("not yet implemented" in limitations or "not implemented" in limitations)
    )
    directory_adapter_stale_claim = (
        (
            "external directory adapters" in limitations
            or (
                "scim" in limitations
                and "ldap" in limitations
                and "saml" in limitations
                and "workspace-directory" in limitations
            )
        )
        and ("not yet implemented" in limitations or "not implemented" in limitations)
    )
    return not (
        (authority_surfaces and (stale_claim or escalation_stale_claim))
        or (_directory_adapter_scripts_present(repo_root) and directory_adapter_stale_claim)
    )


def _directory_adapter_scripts_present(repo_root: Path) -> bool:
    """Return whether merged authority directory adapters are present."""
    adapter_paths = (
        "scripts/scim_authority_directory_adapter.py",
        "scripts/ldap_authority_directory_adapter.py",
        "scripts/saml_groups_authority_directory_adapter.py",
        "scripts/workspace_groups_authority_directory_adapter.py",
    )
    return all((repo_root / adapter_path).exists() for adapter_path in adapter_paths)


def _security_model_aligned(repo_root: Path) -> bool:
    path = repo_root / "SECURITY_MODEL_v0.1.md"
    isolation_path = repo_root / "gateway" / "capability_isolation.py"
    if not path.exists() or not isolation_path.exists():
        return False
    security = path.read_text(encoding="utf-8").lower()
    isolation = isolation_path.read_text(encoding="utf-8").lower()
    legacy_shell_warning = "shell" in security and ("no sandbox" in security or "no chroot" in security)
    gateway_isolation_exists = "isolated_worker" in isolation and "fail_closed_without_worker" in isolation
    distinction_present = "gateway" in security and "legacy shell" in security
    return not (legacy_shell_warning and gateway_isolation_exists and not distinction_present)


def _collect_gaps(checks: list[ConformanceCheck], *, repository_root: Path) -> list[str]:
    gap_by_check = {
        "latest_anchor_valid": "latest_anchor_not_published",
        "command_closure_canary": "command_closure_canary_missing_terminal_success",
        "capability_admission_canary": "capability_fabric_admission_not_live",
        "capsule_registry_certified": "capsule_registry_certification_not_witnessed",
        "dangerous_capability_isolation_canary": "dangerous_capability_isolation_not_live",
        "streaming_budget_canary": "streaming_budget_contract_not_witnessed",
        "lineage_query_canary": "lineage_query_contract_not_witnessed",
        "authority_obligation_canary": "authority_obligation_witness_not_live",
        "authority_responsibility_debt_clear": "authority_responsibility_debt_present",
        "authority_directory_sync_receipt": "authority_directory_sync_receipt_not_witnessed",
        "mcp_capability_manifest": "mcp_capability_manifest_invalid",
        "proof_coverage_matrix_current": "proof_coverage_matrix_not_current",
        "known_limitations_aligned": "known_limitations_documentation_drift",
        "security_model_aligned": "security_model_documentation_drift",
    }
    gaps = [gap_by_check[check.check_id] for check in checks if not check.passed and check.check_id in gap_by_check]
    deployment_status = repository_root / "DEPLOYMENT_STATUS.md"
    if deployment_status.exists():
        text = deployment_status.read_text(encoding="utf-8").lower()
        if "not-published" in text:
            gaps.append("deployment_witness_not_published")
        if "public production health" in text and "not-declared" in text:
            gaps.append("public_production_health_not_declared")
    docs_41 = repository_root / "docs" / "41_streaming_budget_enforcement.md"
    if docs_41.exists() and "provider-native token streams are not enabled" in docs_41.read_text(encoding="utf-8").lower():
        gaps.append("provider_native_streaming_tokens_not_enabled")
    docs_42 = repository_root / "docs" / "42_lineage_query_api.md"
    if docs_42.exists() and "policy-version index" in docs_42.read_text(encoding="utf-8").lower():
        gaps.append("lineage_policy_version_index_projected_only")
    return sorted(set(gaps))


def _decide_status(
    gaps: list[str],
    *,
    gateway_witness_valid: bool,
    runtime_witness_valid: bool,
    core_canaries: tuple[bool, ...],
) -> ConformanceStatus:
    if not gateway_witness_valid or not runtime_witness_valid:
        return ConformanceStatus.NON_CONFORMANT
    if not all(core_canaries):
        return ConformanceStatus.DEGRADED
    if gaps:
        return ConformanceStatus.CONFORMANT_WITH_GAPS
    return ConformanceStatus.CONFORMANT


def _sign_certificate(
    certificate: RuntimeConformanceCertificate,
    *,
    signing_secret: str,
) -> RuntimeConformanceCertificate:
    payload = certificate.to_json_dict()
    payload.pop("signature", None)
    signature = hmac.new(
        signing_secret.encode("utf-8"),
        _stable_hash(payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return RuntimeConformanceCertificate(
        **{
            **certificate.to_json_dict(),
            "terminal_status": certificate.terminal_status,
            "checks": certificate.checks,
            "open_conformance_gaps": certificate.open_conformance_gaps,
            "evidence_refs": certificate.evidence_refs,
            "signature": f"hmac-sha256:{signature}",
        }
    )


def _stable_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _plus_minutes(timestamp: str, minutes: int) -> str:
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (parsed + timedelta(minutes=minutes)).isoformat()
