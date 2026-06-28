#!/usr/bin/env python3
"""Reconcile terminal certificate candidate evidence against receipts.

Purpose: determine whether non-minting terminal certificate candidates have
their required evidence refs satisfied by validated receipt artifacts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: terminal certificate candidate set, optional live/proof receipt
files, and terminal evidence reconciliation schema.
Invariants:
  - This reconciler does not execute actions or mint terminal certificates.
  - Missing receipt evidence blocks minting readiness.
  - Receipt values are summarized by path and status only.
  - Secret values are never read or serialized.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.plan_general_agent_promotion_terminal_certificate_candidates import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_CANDIDATES,
    validate_general_agent_promotion_terminal_certificate_candidates,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "general_agent_promotion_terminal_evidence_reconciliation.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_terminal_evidence_reconciliation.json"
DEFAULT_GENERATED_AT = "2026-05-01T12:00:00+00:00"
DEFAULT_RECEIPT_PATHS = (
    REPO_ROOT / ".change_assurance" / "browser_live_receipt.json",
    REPO_ROOT / ".change_assurance" / "document_live_receipt.json",
    REPO_ROOT / ".change_assurance" / "voice_live_receipt.json",
    REPO_ROOT / ".change_assurance" / "email_calendar_live_receipt.json",
    REPO_ROOT / ".change_assurance" / "gateway_publication_receipt.json",
)
DEFAULT_CAPABILITY_IMPROVEMENT_PROOF_RECEIPT_GLOB = "capability_improvement_proof_receipt*.json"
CANDIDATE_SCHEMA_ID = "urn:mullusi:schema:general-agent-promotion-terminal-certificate-candidates:1"
TERMINAL_CERTIFICATE_SCHEMA_ID = "urn:mullusi:schema:terminal-closure-certificate:1"


@dataclass(frozen=True, slots=True)
class ReceiptEvidenceIndex:
    """Status-only evidence projection from receipt files."""

    matched_by_key: dict[str, str]
    missing_receipt_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReconciledTerminalCandidate:
    """One candidate evidence reconciliation result."""

    candidate_id: str
    source_action_id: str
    reconciliation_status: str
    ready_for_terminal_certificate_minting: bool
    evidence_required: tuple[str, ...]
    evidence_matched: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    blocked_reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready reconciliation data."""
        return {
            "candidate_id": self.candidate_id,
            "source_action_id": self.source_action_id,
            "reconciliation_status": self.reconciliation_status,
            "ready_for_terminal_certificate_minting": self.ready_for_terminal_certificate_minting,
            "certificate_minted": False,
            "execution_performed": False,
            "evidence_required": list(self.evidence_required),
            "evidence_matched": list(self.evidence_matched),
            "missing_evidence": list(self.missing_evidence),
            "receipt_refs": list(self.receipt_refs),
            "blocked_reasons": list(self.blocked_reasons),
        }


@dataclass(frozen=True, slots=True)
class TerminalEvidenceReconciliation:
    """Terminal evidence reconciliation artifact."""

    schema_version: int
    reconciliation_id: str
    generated_at: str
    source_candidate_path: str
    source_candidate_set_id: str
    ready_for_terminal_certificate_minting: bool
    candidate_count: int
    reconciled_candidate_count: int
    blocked_candidate_count: int
    missing_evidence_count: int
    blocked_reasons: tuple[str, ...]
    candidates: tuple[ReconciledTerminalCandidate, ...]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready reconciliation artifact."""
        return {
            "schema_version": self.schema_version,
            "reconciliation_id": self.reconciliation_id,
            "generated_at": self.generated_at,
            "source_candidate_path": self.source_candidate_path,
            "source_candidate_set_id": self.source_candidate_set_id,
            "ready_for_terminal_certificate_minting": self.ready_for_terminal_certificate_minting,
            "candidate_count": self.candidate_count,
            "reconciled_candidate_count": self.reconciled_candidate_count,
            "blocked_candidate_count": self.blocked_candidate_count,
            "missing_evidence_count": self.missing_evidence_count,
            "blocked_reasons": list(self.blocked_reasons),
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "metadata": dict(self.metadata),
        }


def reconcile_general_agent_promotion_terminal_evidence(
    *,
    candidate_path: Path = DEFAULT_CANDIDATES,
    receipt_paths: tuple[Path, ...] | None = None,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> TerminalEvidenceReconciliation:
    """Reconcile terminal candidate evidence against receipt files."""
    candidates = _load_json_object(candidate_path, "terminal certificate candidates")
    candidate_hash = _stable_hash(candidates)
    candidate_errors = validate_general_agent_promotion_terminal_certificate_candidates(candidates)
    if candidate_errors:
        invalid_result = ReconciledTerminalCandidate(
            candidate_id="invalid-terminal-certificate-candidates",
            source_action_id="invalid-terminal-certificate-candidates",
            reconciliation_status="blocked_invalid_candidates",
            ready_for_terminal_certificate_minting=False,
            evidence_required=(),
            evidence_matched=(),
            missing_evidence=(),
            receipt_refs=(),
            blocked_reasons=tuple(f"terminal_certificate_candidates_invalid:{error}" for error in candidate_errors),
        )
        return _reconciliation_plan(
            candidate_path=candidate_path,
            generated_at=generated_at,
            candidates=candidates,
            candidate_hash=candidate_hash,
            results=(invalid_result,),
            receipt_index=ReceiptEvidenceIndex({}, ()),
        )
    effective_receipt_paths = receipt_paths if receipt_paths is not None else _default_receipt_paths()
    receipt_index = _receipt_evidence_index(effective_receipt_paths)
    results = tuple(_reconcile_candidate(candidate, receipt_index) for candidate in _candidate_items(candidates))
    return _reconciliation_plan(
        candidate_path=candidate_path,
        generated_at=generated_at,
        candidates=candidates,
        candidate_hash=candidate_hash,
        results=results,
        receipt_index=receipt_index,
    )


def write_general_agent_promotion_terminal_evidence_reconciliation(
    reconciliation: TerminalEvidenceReconciliation,
    output_path: Path,
) -> Path:
    """Write one terminal evidence reconciliation artifact."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(reconciliation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def validate_general_agent_promotion_terminal_evidence_reconciliation(
    reconciliation: TerminalEvidenceReconciliation | dict[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
) -> tuple[str, ...]:
    """Validate one terminal evidence reconciliation artifact against schema."""
    schema = _load_schema(schema_path)
    payload = reconciliation.as_dict() if isinstance(reconciliation, TerminalEvidenceReconciliation) else reconciliation
    return tuple(_validate_schema_instance(schema, payload))


def _path_label(path: Path) -> str:
    """Return a terminal-evidence path label without host-local ancestry."""
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _reconcile_candidate(
    candidate: dict[str, Any],
    receipt_index: ReceiptEvidenceIndex,
) -> ReconciledTerminalCandidate:
    evidence_required = _string_tuple(candidate.get("evidence_required", ()))
    evidence_matched: list[str] = []
    missing_evidence: list[str] = []
    receipt_refs: list[str] = []
    for evidence_key in evidence_required:
        receipt_ref = receipt_index.matched_by_key.get(evidence_key)
        if receipt_ref:
            evidence_matched.append(evidence_key)
            receipt_refs.append(receipt_ref)
        else:
            missing_evidence.append(evidence_key)
    blocked_reasons = tuple(f"missing_evidence:{evidence_key}" for evidence_key in missing_evidence)
    ready = not missing_evidence
    return ReconciledTerminalCandidate(
        candidate_id=_field_text(candidate, "candidate_id", "unknown-candidate"),
        source_action_id=_field_text(candidate, "source_action_id", "unknown-action"),
        reconciliation_status="reconciled" if ready else "blocked_missing_evidence",
        ready_for_terminal_certificate_minting=ready,
        evidence_required=evidence_required,
        evidence_matched=tuple(evidence_matched),
        missing_evidence=tuple(missing_evidence),
        receipt_refs=tuple(dict.fromkeys(receipt_refs)),
        blocked_reasons=blocked_reasons,
    )


def _receipt_evidence_index(receipt_paths: tuple[Path, ...]) -> ReceiptEvidenceIndex:
    matched: dict[str, str] = {}
    missing_paths: list[str] = []
    for path in receipt_paths:
        if not path.exists():
            missing_paths.append(_path_label(path))
            continue
        receipt = _load_json_object(path, "receipt")
        receipt_ref = _path_label(path)
        _index_deployment_publication_evidence_packet(receipt, receipt_ref, matched)
        _index_deployment_publication_receipt(receipt, receipt_ref, matched)
        if not _receipt_passed(receipt):
            continue
        basename = path.name
        matched[basename] = receipt_ref
        _index_capability_improvement_proof_receipt(receipt, receipt_ref, matched)
        adapter_id = str(receipt.get("adapter_id", ""))
        if adapter_id == "document.production_parsers" and receipt.get("production_parser_ids"):
            matched["production_parser_registry_receipt"] = receipt_ref
        if adapter_id == "browser.playwright" and receipt.get("sandboxed_worker") is True:
            matched["browser_sandbox_evidence_receipt"] = receipt_ref
        if adapter_id == "voice.openai":
            matched["voice_live_receipt"] = receipt_ref
        if adapter_id == "communication.email_calendar_worker":
            matched["email_calendar_live_receipt"] = receipt_ref
    return ReceiptEvidenceIndex(matched_by_key=matched, missing_receipt_paths=tuple(missing_paths))


def _index_deployment_publication_receipt(
    receipt: dict[str, Any],
    receipt_ref: str,
    matched: dict[str, str],
) -> None:
    """Index validated deployment publication receipts by closure evidence key."""
    receipt_id = str(receipt.get("receipt_id", ""))
    if receipt_id.startswith("gateway-dns-target-binding-"):
        if receipt.get("ready") is True:
            matched["gateway_dns_target_binding_receipt"] = receipt_ref
        if receipt.get("valid") is True and receipt.get("ready") is True:
            matched["gateway_dns_target_binding_validation"] = receipt_ref
        return
    if receipt_id.startswith("gateway-dns-resolution-"):
        if receipt.get("resolved") is True or receipt.get("valid") is True:
            matched["dns_resolution_receipt"] = receipt_ref
        if receipt.get("valid") is True:
            matched["dns_resolution_receipt_validation"] = receipt_ref
        return
    if receipt.get("ready") is True and (
        receipt_id.startswith("deployment-witness-preflight-")
        or ("gateway_url" in receipt and "expected_environment" in receipt)
    ):
        matched["deployment_witness_preflight"] = receipt_ref


def _index_deployment_publication_evidence_packet(
    receipt: dict[str, Any],
    receipt_ref: str,
    matched: dict[str, str],
) -> None:
    """Index a ready deployment publication packet by upstream closure keys."""
    if not str(receipt.get("packet_id", "")).startswith("deployment-publication-evidence-packet-"):
        return
    if receipt.get("ready") is not True:
        return
    blockers = receipt.get("blockers")
    if not isinstance(blockers, list) or blockers:
        return
    validation_status = receipt.get("validation_status")
    if not isinstance(validation_status, dict):
        return
    required_validations = (
        "deployment_publication_closure_plan_schema",
        "deployment_upstream_blocker",
        "gateway_dns_resolution",
        "gateway_dns_target_binding",
    )
    if any(validation_status.get(validation) is not True for validation in required_validations):
        return
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict):
        return
    required_artifacts = (
        "deployment_upstream_blocker_receipt",
        "deployment_upstream_blocker_validation",
        "gateway_dns_resolution_receipt",
        "gateway_dns_resolution_validation",
        "gateway_dns_target_binding_receipt",
        "gateway_dns_target_binding_validation",
        "gateway_publication_readiness",
    )
    if any(not str(artifacts.get(artifact, "")).strip() for artifact in required_artifacts):
        return
    for evidence_key in (
        "upstream_api_production_readiness_report",
        "deployment_upstream_blocker_receipt",
        "deployment_upstream_blocker_validation",
        "upstream_recovery_completion_witness",
        "api_runtime_host_readiness",
        "dns_publication_authority",
    ):
        matched[evidence_key] = receipt_ref


def _index_capability_improvement_proof_receipt(
    receipt: dict[str, Any],
    receipt_ref: str,
    matched: dict[str, str],
) -> None:
    """Index a safe capability-improvement proof receipt by evidence key."""
    if receipt.get("receipt_type") != "capability_improvement_proof_receipt":
        return
    metadata = receipt.get("metadata")
    if not isinstance(metadata, dict):
        return
    if metadata.get("proof_is_not_execution") is not True:
        return
    if metadata.get("capability_activation_performed") is not False:
        return
    if metadata.get("registry_mutated") is not False:
        return
    if metadata.get("terminal_certificates_minted") is not False:
        return
    if metadata.get("secret_values_serialized") is not False:
        return
    for evidence_key in _string_tuple(receipt.get("evidence_keys", ())):
        matched[evidence_key] = receipt_ref


def _reconciliation_plan(
    *,
    candidate_path: Path,
    generated_at: str,
    candidates: dict[str, Any],
    candidate_hash: str,
    results: tuple[ReconciledTerminalCandidate, ...],
    receipt_index: ReceiptEvidenceIndex,
) -> TerminalEvidenceReconciliation:
    reconciled_count = sum(1 for result in results if result.reconciliation_status == "reconciled")
    blocked_count = len(results) - reconciled_count
    missing_evidence_count = sum(len(result.missing_evidence) for result in results)
    blocked_reasons = tuple(
        sorted(
            {
                reason
                for result in results
                for reason in result.blocked_reasons
            }
        )
    )
    material = {
        "generated_at": generated_at,
        "candidate_hash": candidate_hash,
        "results": [result.as_dict() for result in results],
        "receipt_keys": sorted(receipt_index.matched_by_key),
    }
    digest = _stable_hash(material)
    return TerminalEvidenceReconciliation(
        schema_version=1,
        reconciliation_id=f"general-agent-promotion-terminal-evidence-reconciliation-{digest[:16]}",
        generated_at=generated_at,
        source_candidate_path=_path_label(candidate_path),
        source_candidate_set_id=_field_text(candidates, "candidate_set_id", "invalid-terminal-candidate-set"),
        ready_for_terminal_certificate_minting=bool(results) and blocked_count == 0,
        candidate_count=len(results),
        reconciled_candidate_count=reconciled_count,
        blocked_candidate_count=blocked_count,
        missing_evidence_count=missing_evidence_count,
        blocked_reasons=blocked_reasons,
        candidates=results,
        metadata={
            "reconciliation_is_not_execution": True,
            "terminal_certificates_minted": False,
            "secret_values_serialized": False,
            "source_candidate_hash": candidate_hash,
            "candidate_schema_id": CANDIDATE_SCHEMA_ID,
            "terminal_certificate_schema_id": TERMINAL_CERTIFICATE_SCHEMA_ID,
        },
    )


def _candidate_items(candidates: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    items = candidates.get("candidates", ())
    if not isinstance(items, list):
        return ()
    return tuple(item for item in items if isinstance(item, dict))


def _receipt_passed(receipt: dict[str, Any]) -> bool:
    blockers = receipt.get("blockers", ())
    return (
        receipt.get("status") == "passed"
        and receipt.get("verification_status") == "passed"
        and (not isinstance(blockers, list) or not blockers)
    )


def _field_text(payload: dict[str, Any], field_name: str, fallback: str) -> str:
    value = str(payload.get(field_name, "")).strip()
    return value or fallback


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} file missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return payload


def _receipt_paths_from_args(raw_paths: list[str]) -> tuple[Path, ...]:
    if not raw_paths:
        return _default_receipt_paths()
    return tuple(Path(raw_path) for raw_path in raw_paths if raw_path.strip())


def _default_receipt_paths() -> tuple[Path, ...]:
    proof_receipt_paths = tuple(
        sorted(
            (REPO_ROOT / ".change_assurance").glob(DEFAULT_CAPABILITY_IMPROVEMENT_PROOF_RECEIPT_GLOB)
        )
    )
    return tuple(dict.fromkeys(DEFAULT_RECEIPT_PATHS + proof_receipt_paths))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse terminal evidence reconciliation arguments."""
    parser = argparse.ArgumentParser(description="Reconcile terminal certificate candidate evidence.")
    parser.add_argument("--candidates", default=str(DEFAULT_CANDIDATES))
    parser.add_argument("--receipt", action="append", default=[])
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for terminal evidence reconciliation."""
    args = parse_args(argv)
    reconciliation = reconcile_general_agent_promotion_terminal_evidence(
        candidate_path=Path(args.candidates),
        receipt_paths=_receipt_paths_from_args(args.receipt),
        generated_at=args.generated_at,
    )
    schema_errors = validate_general_agent_promotion_terminal_evidence_reconciliation(
        reconciliation,
        Path(args.schema),
    )
    write_general_agent_promotion_terminal_evidence_reconciliation(reconciliation, Path(args.output))
    payload = reconciliation.as_dict() | {"schema_valid": not schema_errors, "schema_errors": list(schema_errors)}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif schema_errors:
        for error in schema_errors:
            print(f"error: {error}")
    else:
        print(
            "GENERAL AGENT PROMOTION TERMINAL EVIDENCE RECONCILIATION WRITTEN "
            f"ready={reconciliation.ready_for_terminal_certificate_minting} "
            f"reconciled={reconciliation.reconciled_candidate_count} blocked={reconciliation.blocked_candidate_count}"
        )
    if schema_errors and args.strict:
        return 2
    if args.require_ready and not reconciliation.ready_for_terminal_certificate_minting:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
