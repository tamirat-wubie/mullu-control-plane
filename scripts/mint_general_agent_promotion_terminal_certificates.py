#!/usr/bin/env python3
"""Mint terminal closure certificates from an admitted promotion minting gate.

Purpose: produce terminal closure certificate artifacts only after the
promotion terminal minting gate proves reconciled evidence and explicit
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: terminal minting gate artifact, terminal closure certificate
schema, and terminal certificate minting run schema.
Invariants:
  - A non-ready or invalid gate mints no certificates.
  - Every minted certificate validates against the public terminal closure
    certificate schema before the run is considered successful.
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

from scripts.gate_general_agent_promotion_terminal_minting import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_MINTING_GATE,
    validate_general_agent_promotion_terminal_minting_gate,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "general_agent_promotion_terminal_certificate_minting_run.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_terminal_certificate_minting_run.json"
DEFAULT_CERTIFICATE_DIR = REPO_ROOT / ".change_assurance" / "terminal_certificates"
DEFAULT_GENERATED_AT = "2026-05-01T12:00:00+00:00"
MINTING_GATE_SCHEMA_ID = "urn:mullusi:schema:general-agent-promotion-terminal-minting-gate:1"
MINTING_RUN_SCHEMA_ID = "urn:mullusi:schema:general-agent-promotion-terminal-certificate-minting-run:1"
TERMINAL_CERTIFICATE_SCHEMA_ID = "urn:mullusi:schema:terminal-closure-certificate:1"
TERMINAL_CERTIFICATE_SCHEMA = REPO_ROOT / "schemas" / "terminal_closure_certificate.schema.json"


@dataclass(frozen=True, slots=True)
class MintedTerminalCertificateRef:
    """Reference and validation result for one minted certificate."""

    candidate_id: str
    source_action_id: str
    certificate_id: str
    certificate_path: str
    schema_valid: bool
    validation_errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready certificate reference data."""
        return {
            "candidate_id": self.candidate_id,
            "source_action_id": self.source_action_id,
            "certificate_id": self.certificate_id,
            "certificate_path": self.certificate_path,
            "schema_valid": self.schema_valid,
            "validation_errors": list(self.validation_errors),
        }


@dataclass(frozen=True, slots=True)
class TerminalCertificateMintingRun:
    """Terminal certificate minting run artifact."""

    schema_version: int
    minting_run_id: str
    generated_at: str
    source_minting_gate_path: str
    source_minting_gate_id: str
    ready_gate_required: bool
    terminal_certificates_minted: bool
    certificate_count: int
    blocked_candidate_count: int
    blocked_reasons: tuple[str, ...]
    certificate_output_dir: str
    certificates: tuple[MintedTerminalCertificateRef, ...]
    metadata: dict[str, Any]

    @property
    def valid(self) -> bool:
        """Return whether the run minted only schema-valid certificates."""
        return not self.blocked_reasons and all(certificate.schema_valid for certificate in self.certificates)

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready minting run artifact."""
        return {
            "schema_version": self.schema_version,
            "minting_run_id": self.minting_run_id,
            "generated_at": self.generated_at,
            "source_minting_gate_path": self.source_minting_gate_path,
            "source_minting_gate_id": self.source_minting_gate_id,
            "ready_gate_required": self.ready_gate_required,
            "terminal_certificates_minted": self.terminal_certificates_minted,
            "certificate_count": self.certificate_count,
            "blocked_candidate_count": self.blocked_candidate_count,
            "blocked_reasons": list(self.blocked_reasons),
            "certificate_output_dir": self.certificate_output_dir,
            "certificates": [certificate.as_dict() for certificate in self.certificates],
            "metadata": dict(self.metadata),
        }


def mint_general_agent_promotion_terminal_certificates(
    *,
    minting_gate_path: Path = DEFAULT_MINTING_GATE,
    certificate_output_dir: Path = DEFAULT_CERTIFICATE_DIR,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> TerminalCertificateMintingRun:
    """Mint terminal closure certificates from a ready minting gate."""
    minting_gate = _load_json_object(minting_gate_path, "terminal minting gate")
    minting_gate_hash = _stable_hash(minting_gate)
    gate_errors = validate_general_agent_promotion_terminal_minting_gate(minting_gate)
    if gate_errors:
        return _minting_run(
            minting_gate_path=minting_gate_path,
            certificate_output_dir=certificate_output_dir,
            generated_at=generated_at,
            minting_gate=minting_gate,
            minting_gate_hash=minting_gate_hash,
            certificates=(),
            blocked_reasons=tuple(f"terminal_minting_gate_invalid:{error}" for error in gate_errors),
        )
    if minting_gate.get("ready_for_terminal_certificate_minting") is not True:
        return _minting_run(
            minting_gate_path=minting_gate_path,
            certificate_output_dir=certificate_output_dir,
            generated_at=generated_at,
            minting_gate=minting_gate,
            minting_gate_hash=minting_gate_hash,
            certificates=(),
            blocked_reasons=tuple(_blocked_reasons_from_gate(minting_gate)),
        )
    certificate_output_dir.mkdir(parents=True, exist_ok=True)
    certificates = tuple(
        _mint_certificate(candidate, minting_gate, certificate_output_dir, generated_at)
        for candidate in _admitted_candidates(minting_gate)
    )
    certificate_errors = tuple(
        f"terminal_certificate_invalid:{certificate.certificate_id}:{error}"
        for certificate in certificates
        for error in certificate.validation_errors
    )
    return _minting_run(
        minting_gate_path=minting_gate_path,
        certificate_output_dir=certificate_output_dir,
        generated_at=generated_at,
        minting_gate=minting_gate,
        minting_gate_hash=minting_gate_hash,
        certificates=certificates,
        blocked_reasons=certificate_errors,
    )


def write_general_agent_promotion_terminal_certificate_minting_run(
    run: TerminalCertificateMintingRun,
    output_path: Path,
) -> Path:
    """Write one terminal certificate minting run artifact."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(run.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def validate_general_agent_promotion_terminal_certificate_minting_run(
    run: TerminalCertificateMintingRun | dict[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
) -> tuple[str, ...]:
    """Validate one terminal certificate minting run artifact against schema."""
    schema = _load_schema(schema_path)
    payload = run.as_dict() if isinstance(run, TerminalCertificateMintingRun) else run
    return tuple(_validate_schema_instance(schema, payload))


def _mint_certificate(
    candidate: dict[str, Any],
    minting_gate: dict[str, Any],
    certificate_output_dir: Path,
    generated_at: str,
) -> MintedTerminalCertificateRef:
    candidate_id = _field_text(candidate, "candidate_id", "unknown-candidate")
    source_action_id = _field_text(candidate, "source_action_id", "unknown-action")
    certificate_id = _field_text(candidate, "prospective_certificate_id", _certificate_id(candidate_id))
    certificate = {
        "certificate_id": certificate_id,
        "command_id": source_action_id,
        "execution_id": candidate_id,
        "disposition": "committed",
        "verification_result_id": f"verification-{certificate_id}",
        "effect_reconciliation_id": _field_text(
            minting_gate,
            "source_reconciliation_id",
            "unknown-terminal-evidence-reconciliation",
        ),
        "evidence_refs": _certificate_evidence_refs(candidate, minting_gate),
        "closed_at": generated_at,
        "response_closure_ref": f"proof://terminal-minting-gate/{_field_text(minting_gate, 'minting_gate_id', 'unknown')}",
        "memory_entry_id": None,
        "compensation_outcome_id": None,
        "accepted_risk_id": None,
        "case_id": None,
        "graph_refs": [
            f"candidate:{candidate_id}",
            f"action:{source_action_id}",
            f"minting_gate:{_field_text(minting_gate, 'minting_gate_id', 'unknown')}",
        ],
        "metadata": {
            "source": "general_agent_promotion_terminal_certificate_minting_run",
            "terminal_proof": True,
            "source_candidate_id": candidate_id,
            "source_action_id": source_action_id,
            "source_minting_gate_id": _field_text(minting_gate, "minting_gate_id", "unknown"),
            "authority_ref": _field_text(minting_gate, "authority_ref", "unknown-authority"),
            "terminal_certificate_schema_id": TERMINAL_CERTIFICATE_SCHEMA_ID,
        },
    }
    certificate_path = certificate_output_dir / f"{certificate_id}.json"
    certificate_path.write_text(json.dumps(certificate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validation_errors = _validate_terminal_certificate(certificate)
    return MintedTerminalCertificateRef(
        candidate_id=candidate_id,
        source_action_id=source_action_id,
        certificate_id=certificate_id,
        certificate_path=str(certificate_path),
        schema_valid=not validation_errors,
        validation_errors=validation_errors,
    )


def _minting_run(
    *,
    minting_gate_path: Path,
    certificate_output_dir: Path,
    generated_at: str,
    minting_gate: dict[str, Any],
    minting_gate_hash: str,
    certificates: tuple[MintedTerminalCertificateRef, ...],
    blocked_reasons: tuple[str, ...],
) -> TerminalCertificateMintingRun:
    material = {
        "generated_at": generated_at,
        "minting_gate_hash": minting_gate_hash,
        "certificate_ids": [certificate.certificate_id for certificate in certificates],
        "blocked_reasons": list(blocked_reasons),
    }
    digest = _stable_hash(material)
    blocked_count = _blocked_count(minting_gate, blocked_reasons)
    return TerminalCertificateMintingRun(
        schema_version=1,
        minting_run_id=f"general-agent-promotion-terminal-certificate-minting-run-{digest[:16]}",
        generated_at=generated_at,
        source_minting_gate_path=str(minting_gate_path),
        source_minting_gate_id=_field_text(minting_gate, "minting_gate_id", "invalid-terminal-minting-gate"),
        ready_gate_required=True,
        terminal_certificates_minted=bool(certificates) and not blocked_reasons,
        certificate_count=len(certificates),
        blocked_candidate_count=blocked_count,
        blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
        certificate_output_dir=str(certificate_output_dir),
        certificates=certificates,
        metadata={
            "minting_executor_performed": bool(certificates),
            "secret_values_serialized": False,
            "source_minting_gate_hash": minting_gate_hash,
            "minting_gate_schema_id": MINTING_GATE_SCHEMA_ID,
            "minting_run_schema_id": MINTING_RUN_SCHEMA_ID,
            "terminal_certificate_schema_id": TERMINAL_CERTIFICATE_SCHEMA_ID,
        },
    )


def _blocked_count(minting_gate: dict[str, Any], blocked_reasons: tuple[str, ...]) -> int:
    if not blocked_reasons:
        return 0
    blocked_count = minting_gate.get("blocked_candidate_count")
    if isinstance(blocked_count, int) and blocked_count >= 0:
        return blocked_count
    return 1


def _blocked_reasons_from_gate(minting_gate: dict[str, Any]) -> tuple[str, ...]:
    blocked_reasons = _string_tuple(minting_gate.get("blocked_reasons", ()))
    if blocked_reasons:
        return blocked_reasons
    return ("terminal_minting_gate_not_ready",)


def _admitted_candidates(minting_gate: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    candidates = minting_gate.get("candidates", ())
    if not isinstance(candidates, list):
        return ()
    return tuple(
        candidate
        for candidate in candidates
        if isinstance(candidate, dict)
        and candidate.get("minting_gate_status") == "admitted_for_terminal_certificate_minting"
        and candidate.get("ready_for_terminal_certificate_minting") is True
    )


def _certificate_evidence_refs(candidate: dict[str, Any], minting_gate: dict[str, Any]) -> list[str]:
    refs = list(_string_tuple(candidate.get("receipt_refs", ())))
    refs.append(f"proof://terminal-minting-gate/{_field_text(minting_gate, 'minting_gate_id', 'unknown')}")
    refs.append(f"proof://terminal-evidence-reconciliation/{_field_text(minting_gate, 'source_reconciliation_id', 'unknown')}")
    return list(dict.fromkeys(refs))


def _validate_terminal_certificate(certificate: dict[str, Any]) -> tuple[str, ...]:
    schema = _load_schema(TERMINAL_CERTIFICATE_SCHEMA)
    return tuple(_validate_schema_instance(schema, certificate))


def _field_text(payload: dict[str, Any], field_name: str, fallback: str) -> str:
    value = payload.get(field_name)
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _certificate_id(candidate_id: str) -> str:
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
    """Parse terminal certificate minting arguments."""
    parser = argparse.ArgumentParser(description="Mint terminal closure certificates from a ready minting gate.")
    parser.add_argument("--gate", default=str(DEFAULT_MINTING_GATE))
    parser.add_argument("--certificate-dir", default=str(DEFAULT_CERTIFICATE_DIR))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-minted", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for terminal certificate minting."""
    args = parse_args(argv)
    run = mint_general_agent_promotion_terminal_certificates(
        minting_gate_path=Path(args.gate),
        certificate_output_dir=Path(args.certificate_dir),
        generated_at=args.generated_at,
    )
    schema_errors = validate_general_agent_promotion_terminal_certificate_minting_run(run, Path(args.schema))
    write_general_agent_promotion_terminal_certificate_minting_run(run, Path(args.output))
    payload = run.as_dict() | {"schema_valid": not schema_errors, "schema_errors": list(schema_errors)}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif schema_errors:
        for error in schema_errors:
            print(f"error: {error}")
    else:
        print(
            "GENERAL AGENT PROMOTION TERMINAL CERTIFICATES MINTED "
            f"minted={run.certificate_count} blocked={run.blocked_candidate_count}"
        )
    if schema_errors and args.strict:
        return 2
    if args.strict and run.blocked_reasons:
        return 2
    if args.require_minted and not run.terminal_certificates_minted:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
