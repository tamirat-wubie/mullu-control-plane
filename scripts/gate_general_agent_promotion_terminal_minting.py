#!/usr/bin/env python3
"""Gate terminal certificate minting authority for promotion candidates.

Purpose: convert terminal evidence reconciliation results into a non-executing
minting admission gate.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: terminal evidence reconciliation artifact, optional authority
reference, and terminal minting gate schema.
Invariants:
  - This gate does not execute actions or mint terminal closure certificates.
  - Reconciled evidence is necessary but not sufficient; authority is required.
  - Missing authority blocks minting readiness.
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

from scripts.reconcile_general_agent_promotion_terminal_evidence import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_RECONCILIATION,
    validate_general_agent_promotion_terminal_evidence_reconciliation,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "general_agent_promotion_terminal_minting_gate.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_terminal_minting_gate.json"
DEFAULT_GENERATED_AT = "2026-05-01T12:00:00+00:00"
RECONCILIATION_SCHEMA_ID = "urn:mullusi:schema:general-agent-promotion-terminal-evidence-reconciliation:1"
TERMINAL_CERTIFICATE_SCHEMA_ID = "urn:mullusi:schema:terminal-closure-certificate:1"


@dataclass(frozen=True, slots=True)
class TerminalMintingGateCandidate:
    """One terminal certificate minting gate candidate."""

    candidate_id: str
    source_action_id: str
    minting_gate_status: str
    ready_for_terminal_certificate_minting: bool
    authority_ref_present: bool
    receipt_refs: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    prospective_certificate_id: str

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready candidate gate data."""
        return {
            "candidate_id": self.candidate_id,
            "source_action_id": self.source_action_id,
            "minting_gate_status": self.minting_gate_status,
            "ready_for_terminal_certificate_minting": self.ready_for_terminal_certificate_minting,
            "certificate_minted": False,
            "execution_performed": False,
            "authority_ref_present": self.authority_ref_present,
            "receipt_refs": list(self.receipt_refs),
            "blocked_reasons": list(self.blocked_reasons),
            "prospective_certificate_id": self.prospective_certificate_id,
        }


@dataclass(frozen=True, slots=True)
class TerminalMintingGate:
    """Non-executing terminal certificate minting gate artifact."""

    schema_version: int
    minting_gate_id: str
    generated_at: str
    source_reconciliation_path: str
    source_reconciliation_id: str
    authority_ref_present: bool
    authority_ref: str | None
    ready_for_terminal_certificate_minting: bool
    candidate_count: int
    admitted_candidate_count: int
    blocked_candidate_count: int
    blocked_reasons: tuple[str, ...]
    candidates: tuple[TerminalMintingGateCandidate, ...]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready gate artifact."""
        return {
            "schema_version": self.schema_version,
            "minting_gate_id": self.minting_gate_id,
            "generated_at": self.generated_at,
            "source_reconciliation_path": self.source_reconciliation_path,
            "source_reconciliation_id": self.source_reconciliation_id,
            "authority_ref_present": self.authority_ref_present,
            "authority_ref": self.authority_ref,
            "ready_for_terminal_certificate_minting": self.ready_for_terminal_certificate_minting,
            "candidate_count": self.candidate_count,
            "admitted_candidate_count": self.admitted_candidate_count,
            "blocked_candidate_count": self.blocked_candidate_count,
            "blocked_reasons": list(self.blocked_reasons),
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "metadata": dict(self.metadata),
        }


def gate_general_agent_promotion_terminal_minting(
    *,
    reconciliation_path: Path = DEFAULT_RECONCILIATION,
    authority_ref: str | None = None,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> TerminalMintingGate:
    """Gate terminal certificate minting readiness without minting."""
    reconciliation = _load_json_object(reconciliation_path, "terminal evidence reconciliation")
    reconciliation_hash = _stable_hash(reconciliation)
    reconciliation_errors = validate_general_agent_promotion_terminal_evidence_reconciliation(reconciliation)
    authority = _optional_text(authority_ref)
    if reconciliation_errors:
        invalid_candidate = TerminalMintingGateCandidate(
            candidate_id="invalid-terminal-evidence-reconciliation",
            source_action_id="invalid-terminal-evidence-reconciliation",
            minting_gate_status="blocked_invalid_reconciliation",
            ready_for_terminal_certificate_minting=False,
            authority_ref_present=authority is not None,
            receipt_refs=(),
            blocked_reasons=tuple(f"terminal_evidence_reconciliation_invalid:{error}" for error in reconciliation_errors),
            prospective_certificate_id=_prospective_certificate_id("invalid-terminal-evidence-reconciliation"),
        )
        return _minting_gate(
            reconciliation_path=reconciliation_path,
            generated_at=generated_at,
            reconciliation=reconciliation,
            reconciliation_hash=reconciliation_hash,
            authority_ref=authority,
            candidates=(invalid_candidate,),
        )
    candidates = tuple(
        _gate_candidate(candidate, authority_ref=authority)
        for candidate in _reconciled_candidates(reconciliation)
    )
    return _minting_gate(
        reconciliation_path=reconciliation_path,
        generated_at=generated_at,
        reconciliation=reconciliation,
        reconciliation_hash=reconciliation_hash,
        authority_ref=authority,
        candidates=candidates,
    )


def write_general_agent_promotion_terminal_minting_gate(
    gate: TerminalMintingGate,
    output_path: Path,
) -> Path:
    """Write one terminal minting gate artifact."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(gate.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def validate_general_agent_promotion_terminal_minting_gate(
    gate: TerminalMintingGate | dict[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
) -> tuple[str, ...]:
    """Validate one terminal minting gate artifact against schema."""
    schema = _load_schema(schema_path)
    payload = gate.as_dict() if isinstance(gate, TerminalMintingGate) else gate
    return tuple(_validate_schema_instance(schema, payload))


def _path_label(path: Path) -> str:
    """Return a terminal-minting path label without host-local ancestry."""
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _gate_candidate(candidate: dict[str, Any], *, authority_ref: str | None) -> TerminalMintingGateCandidate:
    candidate_id = _field_text(candidate, "candidate_id", "unknown-candidate")
    source_action_id = _field_text(candidate, "source_action_id", "unknown-action")
    candidate_ready = candidate.get("ready_for_terminal_certificate_minting") is True
    authority_present = authority_ref is not None
    blocked_reasons: list[str] = []
    if not candidate_ready:
        blocked_reasons.append("terminal_evidence_reconciliation_not_ready")
        blocked_reasons.extend(_string_tuple(candidate.get("blocked_reasons", ())))
    if not authority_present:
        blocked_reasons.append("missing_terminal_minting_authority_ref")
    ready = candidate_ready and authority_present
    if ready:
        status = "admitted_for_terminal_certificate_minting"
    elif not candidate_ready:
        status = "blocked_reconciliation_not_ready"
    else:
        status = "blocked_missing_authority"
    return TerminalMintingGateCandidate(
        candidate_id=candidate_id,
        source_action_id=source_action_id,
        minting_gate_status=status,
        ready_for_terminal_certificate_minting=ready,
        authority_ref_present=authority_present,
        receipt_refs=_string_tuple(candidate.get("receipt_refs", ())),
        blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
        prospective_certificate_id=_prospective_certificate_id(candidate_id),
    )


def _minting_gate(
    *,
    reconciliation_path: Path,
    generated_at: str,
    reconciliation: dict[str, Any],
    reconciliation_hash: str,
    authority_ref: str | None,
    candidates: tuple[TerminalMintingGateCandidate, ...],
) -> TerminalMintingGate:
    admitted_count = sum(1 for candidate in candidates if candidate.ready_for_terminal_certificate_minting)
    blocked_count = len(candidates) - admitted_count
    blocked_reasons = tuple(
        sorted({reason for candidate in candidates for reason in candidate.blocked_reasons})
    )
    material = {
        "generated_at": generated_at,
        "reconciliation_hash": reconciliation_hash,
        "authority_ref_present": authority_ref is not None,
        "candidates": [candidate.as_dict() for candidate in candidates],
    }
    digest = _stable_hash(material)
    return TerminalMintingGate(
        schema_version=1,
        minting_gate_id=f"general-agent-promotion-terminal-minting-gate-{digest[:16]}",
        generated_at=generated_at,
        source_reconciliation_path=_path_label(reconciliation_path),
        source_reconciliation_id=_field_text(
            reconciliation,
            "reconciliation_id",
            "invalid-terminal-evidence-reconciliation",
        ),
        authority_ref_present=authority_ref is not None,
        authority_ref=authority_ref,
        ready_for_terminal_certificate_minting=bool(candidates) and blocked_count == 0,
        candidate_count=len(candidates),
        admitted_candidate_count=admitted_count,
        blocked_candidate_count=blocked_count,
        blocked_reasons=blocked_reasons,
        candidates=candidates,
        metadata={
            "minting_gate_is_not_execution": True,
            "terminal_certificates_minted": False,
            "secret_values_serialized": False,
            "source_reconciliation_hash": reconciliation_hash,
            "reconciliation_schema_id": RECONCILIATION_SCHEMA_ID,
            "terminal_certificate_schema_id": TERMINAL_CERTIFICATE_SCHEMA_ID,
            "authority_model": "explicit_operator_authority_required",
        },
    )


def _reconciled_candidates(reconciliation: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    candidates = reconciliation.get("candidates", ())
    if not isinstance(candidates, list):
        return ()
    return tuple(candidate for candidate in candidates if isinstance(candidate, dict))


def _field_text(payload: dict[str, Any], field_name: str, fallback: str) -> str:
    value = str(payload.get(field_name, "")).strip()
    return value or fallback


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _prospective_certificate_id(candidate_id: str) -> str:
    digest = _stable_hash({"candidate_id": candidate_id})
    return f"terminal-closure-certificate-{digest[:16]}"


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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse terminal minting gate arguments."""
    parser = argparse.ArgumentParser(description="Gate terminal certificate minting readiness.")
    parser.add_argument("--reconciliation", default=str(DEFAULT_RECONCILIATION))
    parser.add_argument("--authority-ref", default="")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for terminal minting gate planning."""
    args = parse_args(argv)
    gate = gate_general_agent_promotion_terminal_minting(
        reconciliation_path=Path(args.reconciliation),
        authority_ref=args.authority_ref,
        generated_at=args.generated_at,
    )
    schema_errors = validate_general_agent_promotion_terminal_minting_gate(gate, Path(args.schema))
    write_general_agent_promotion_terminal_minting_gate(gate, Path(args.output))
    payload = gate.as_dict() | {"schema_valid": not schema_errors, "schema_errors": list(schema_errors)}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif schema_errors:
        for error in schema_errors:
            print(f"error: {error}")
    else:
        print(
            "GENERAL AGENT PROMOTION TERMINAL MINTING GATE WRITTEN "
            f"ready={gate.ready_for_terminal_certificate_minting} "
            f"admitted={gate.admitted_candidate_count} blocked={gate.blocked_candidate_count}"
        )
    if schema_errors and args.strict:
        return 2
    if args.require_ready and not gate.ready_for_terminal_certificate_minting:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
