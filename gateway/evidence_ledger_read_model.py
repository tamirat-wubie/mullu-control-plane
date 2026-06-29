"""Gateway evidence-ledger read-model projection.

Purpose: build a Foundation Mode proof projection for the causal evidence
    continuity ledger without registering a live evidence write path.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.evidence_ledger.
Invariants:
  - Projection is read-only and local-fixture backed.
  - Projection is not live operator evidence, terminal closure, or authority.
  - Raw artifact payloads are not exposed through proof-only summaries.
  - Chain verification must pass before the route reports SolvedVerified.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from gateway.evidence_ledger import (
    EvidenceKind,
    EvidenceLedgerKernel,
    EvidenceLedgerError,
    ExpectedEvidenceProfile,
    ExposureViewType,
    RelationType,
    SourceAuthority,
)


DEFAULT_LEDGER_ID = "foundation-evidence-ledger-read-model"
DEFAULT_OBSERVED_AT = "2026-06-29T12:00:00+00:00"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPOSITORY_SOURCE_PATH = REPO_ROOT / "examples" / "evidence_ledger" / "foundation_evidence_source.json"


class EvidenceLedgerReadModelSourceError(ValueError):
    """Raised when the repository-local evidence source cannot be admitted."""


def build_foundation_evidence_ledger_read_model(
    *,
    generated_at: str = DEFAULT_OBSERVED_AT,
    clock: Callable[[], str] | None = None,
    source_path: Path = DEFAULT_REPOSITORY_SOURCE_PATH,
) -> dict[str, object]:
    """Return a deterministic proof-bound evidence-ledger read model.

    Input contract: optional timestamp and clock for deterministic tests.
    Output contract: JSON-serializable Foundation Mode projection. Error
    contract: raises if the kernel cannot produce a verified chain, making the
    route fail closed rather than emitting unsupported certainty.
    """

    source_payload = load_repository_evidence_source(source_path)
    source_observed_at = str(source_payload.get("observed_at") or generated_at)
    ledger = EvidenceLedgerKernel(
        ledger_id=DEFAULT_LEDGER_ID,
        clock=clock or (lambda: generated_at),
    )
    _register_sources_from_payload(ledger, source_payload)
    claim = _create_claim_from_payload(ledger, source_payload, generated_at=source_observed_at)
    evidence_results = tuple(_ingest_evidence_from_payload(ledger, record) for record in _evidence_records(source_payload))
    link_results = tuple(
        ledger.link_evidence(
            evidence_id=result.evidence.evidence_id,
            claim_id=claim.claim_id,
            relation_type=RelationType.SUPPORTS,
            rule_id="foundation-payment-support-rule-v1",
            weight=0.95,
            confidence=0.95,
            explanation="Local fixture evidence supports the demonstration payment claim.",
            actor_id="foundation-read-model",
        )
        for result in evidence_results
    )
    judgment = ledger.judge_claim(claim_id=claim.claim_id, verifier="foundation-read-model")
    proof_view = ledger.expose_claim(
        claim_id=claim.claim_id,
        actor_id="foundation-read-model",
        purpose="foundation_read_model",
        view_type=ExposureViewType.PROOF_ONLY,
    )
    audit = ledger.audit_claim(claim_id=claim.claim_id, actor_id="foundation-read-model")
    chain = ledger.verify_event_chain()
    outcome = "SolvedVerified" if chain.verified and judgment.new_judgment.value == "strongly_supported" else "SolvedUnverified"
    source_ref = _path_label(source_path)
    return {
        "route_id": "causal_evidence_continuity_ledger_read_model",
        "route_version": 1,
        "schema_version": 2,
        "status": outcome,
        "outcome": outcome,
        "read_only": True,
        "foundation_mode": True,
        "repository_local_source": True,
        "repository_source_ref": source_ref,
        "repository_source_hash": _source_hash(source_payload),
        "repository_source_loaded": True,
        "repository_source_observed_at": source_observed_at,
        "foundation_fixture_is_not_live_evidence": bool(source_payload.get("source_is_not_live_evidence") is True),
        "route_is_not_write_path": True,
        "route_is_not_terminal_closure": True,
        "external_effects_allowed": False,
        "raw_payloads_exposed": False,
        "generated_at": generated_at,
        "ledger": {
            "ledger_id": ledger.ledger_id,
            "rule_version": ledger.rule_version,
            "ontology_version": ledger.ontology_version,
            "source_registry_version": ledger.source_registry_version,
            "head_hash": chain.head_hash,
            "event_count": chain.event_count,
            "chain_verified": chain.verified,
            "chain_reason": chain.reason,
            "source_id": str(source_payload.get("source_id", "")),
            "source_version": int(source_payload.get("source_version", 0)),
        },
        "claim": {
            "claim_id": claim.claim_id,
            "claim_type": claim.claim_type,
            "subject": claim.subject,
            "judgment": judgment.new_judgment.value,
            "receipt_id": judgment.receipt_id,
            "missing_evidence": list(judgment.missing_evidence),
            "conflicts": list(judgment.conflicts),
            "confidence_limits": list(judgment.confidence_limits),
        },
        "evidence": {
            "accepted_count": sum(1 for result in evidence_results if result.accepted),
            "rejected_count": sum(1 for result in evidence_results if not result.accepted),
            "linked_count": sum(1 for result in link_results if result.accepted),
            "proof_summaries": list(proof_view.to_json_dict()["evidence_summaries"]),
        },
        "judgment_receipt": judgment.to_json_dict(),
        "proof_view": proof_view.to_json_dict(),
        "audit_receipt": asdict(audit),
        "validators": [
            "test_evidence_ledger_kernel",
            "test_evidence_ledger_read_model_route",
            "test_evidence_ledger_repository_source",
            "validate_sdlc_artifact",
            "validate_agents_governance",
        ],
        "invariants": {
            "evidence_is_not_truth": True,
            "claim_is_not_evidence": True,
            "judgment_receipt_required": True,
            "conflicts_checked": True,
            "missing_evidence_checked": True,
            "proof_view_redacts_raw_payload": True,
            "repository_local_source_loaded": True,
            "repository_source_is_not_write_path": bool(source_payload.get("source_is_not_write_path") is True),
            "append_only_hash_chain_verified": chain.verified,
        },
        "next_action": "Add an append-only repository-local source validator before any live evidence write path.",
    }


def load_repository_evidence_source(source_path: Path = DEFAULT_REPOSITORY_SOURCE_PATH) -> dict[str, Any]:
    """Load and validate the repository-local evidence source document."""

    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise EvidenceLedgerReadModelSourceError(f"repository_evidence_source_unreadable:{source_path}") from exc
    if not isinstance(payload, dict):
        raise EvidenceLedgerReadModelSourceError("repository_evidence_source_must_be_object")
    _require_true(payload, "foundation_mode")
    _require_true(payload, "repository_local_source")
    _require_true(payload, "source_is_not_live_evidence")
    _require_true(payload, "source_is_not_write_path")
    _require_true(payload, "source_is_not_terminal_closure")
    _required_text(payload, "source_id")
    _required_text(payload, "observed_at")
    _required_mapping(payload, "claim")
    if not _objects(payload.get("source_authorities")):
        raise EvidenceLedgerReadModelSourceError("source_authorities_required")
    if not _objects(payload.get("evidence_records")):
        raise EvidenceLedgerReadModelSourceError("evidence_records_required")
    return payload


def _register_sources_from_payload(ledger: EvidenceLedgerKernel, payload: Mapping[str, Any]) -> None:
    for source_record in _objects(payload.get("source_authorities")):
        try:
            source = SourceAuthority(
                source_id=_required_text(source_record, "source_id"),
                source_type=_required_text(source_record, "source_type"),
                authority_domains=tuple(str(value) for value in _list(source_record.get("authority_domains"))),
                forbidden_domains=tuple(str(value) for value in _list(source_record.get("forbidden_domains"))),
                reliability_score=float(source_record.get("reliability_score", 0.0)),
                verification_method=str(source_record.get("verification_method", "")),
                last_verified_at=str(source_record.get("last_verified_at", "")),
                authority_scope=str(source_record.get("authority_scope", "")),
            )
            ledger.register_source_authority(source, actor_id="foundation-read-model")
        except (EvidenceLedgerError, TypeError, ValueError) as exc:
            raise EvidenceLedgerReadModelSourceError("source_authority_record_invalid") from exc


def _create_claim_from_payload(
    ledger: EvidenceLedgerKernel,
    payload: Mapping[str, Any],
    *,
    generated_at: str,
):
    claim = _required_mapping(payload, "claim")
    profile = _required_mapping(claim, "expected_evidence_profile")
    try:
        return ledger.create_claim(
            claim_id=_required_text(claim, "claim_id"),
            claim_type=_required_text(claim, "claim_type"),
            proposition=_required_text(claim, "proposition"),
            subject=_required_text(claim, "subject"),
            scope=dict(_required_mapping(claim, "scope")),
            temporal_scope=dict(claim.get("temporal_scope") or {"valid_at": generated_at}),
            expected_evidence_profile=ExpectedEvidenceProfile(
                required_evidence_kinds=tuple(str(value) for value in _list(profile.get("required_evidence_kinds"))),
                optional_evidence_kinds=tuple(str(value) for value in _list(profile.get("optional_evidence_kinds"))),
                blocking_absences=tuple(str(value) for value in _list(profile.get("blocking_absences"))),
                minimum_independent_sources=int(profile.get("minimum_independent_sources", 1)),
                freshness_window_days=int(profile.get("freshness_window_days", 30)),
            ),
            actor_id="foundation-read-model",
            expiration_policy=dict(claim.get("expiration_policy") or {}),
        )
    except (EvidenceLedgerError, TypeError, ValueError) as exc:
        raise EvidenceLedgerReadModelSourceError("claim_record_invalid") from exc


def _ingest_evidence_from_payload(
    ledger: EvidenceLedgerKernel,
    record: Mapping[str, Any],
):
    try:
        return ledger.ingest_evidence(
            evidence_kind=_required_text(record, "evidence_kind"),
            source_id=_required_text(record, "source_id"),
            observer_id=_required_text(record, "observer_id"),
            capture_method=_required_text(record, "capture_method"),
            observed_at=_required_text(record, "observed_at"),
            raw_payload=dict(_required_mapping(record, "raw_payload")),
            canonical_payload=dict(_required_mapping(record, "canonical_payload")),
            ontology_type=_required_text(record, "ontology_type"),
            authority_domain=_required_text(record, "authority_domain"),
            actor_id="foundation-read-model",
            sensitivity_level=str(record.get("sensitivity_level", "restricted")),
            raw_reference=str(record.get("raw_reference", "")),
            canonical_reference=str(record.get("canonical_reference", "")),
        )
    except (EvidenceLedgerError, TypeError, ValueError) as exc:
        raise EvidenceLedgerReadModelSourceError("evidence_record_invalid") from exc


def _evidence_records(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(_objects(payload.get("evidence_records")))


def _source_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError(f"non-finite JSON constant is not permitted: {raw_constant}")


def _require_true(payload: Mapping[str, Any], field_name: str) -> None:
    if payload.get(field_name) is not True:
        raise EvidenceLedgerReadModelSourceError(f"{field_name}_must_be_true")


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise EvidenceLedgerReadModelSourceError(f"{field_name}_required")
    return value


def _required_mapping(payload: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, Mapping):
        raise EvidenceLedgerReadModelSourceError(f"{field_name}_must_be_object")
    return value


def _objects(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _list(value: object) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EvidenceLedgerReadModelSourceError("array_required")
    return value
