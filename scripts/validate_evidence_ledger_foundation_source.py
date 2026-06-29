#!/usr/bin/env python3
"""Validate the repository-local evidence-ledger foundation source.

Purpose: admit the Foundation Mode evidence source only when it remains local,
read-only, non-live, and semantically bound to declared source authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: jsonschema, schemas/evidence_ledger_foundation_source.schema.json,
and examples/evidence_ledger/foundation_evidence_source.json.
Invariants:
  - Validation is read-only.
  - Foundation markers must be true.
  - Required evidence kinds must be present in the repository source.
  - Evidence records must cite declared source authorities and allowed domains.
  - Secret-like values are rejected from the local fixture payload.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping

try:
    import jsonschema
except ImportError:  # pragma: no cover - exercised only in incomplete envs.
    jsonschema = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_PATH = REPO_ROOT / "examples" / "evidence_ledger" / "foundation_evidence_source.json"
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "evidence_ledger_foundation_source.schema.json"
REQUIRED_MARKERS = (
    "foundation_mode",
    "repository_local_source",
    "source_is_not_live_evidence",
    "source_is_not_write_path",
    "source_is_not_terminal_closure",
)
SECRET_KEY_PATTERN = re.compile(
    r"(?:password|secret|token|api[_-]?key|private[_-]?key|credential)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERN = re.compile(
    r"(?:BEGIN [A-Z ]*PRIVATE KEY|password\s*=|secret\s*=|token\s*=|api[_-]?key\s*=)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class FoundationSourceFinding:
    """One deterministic foundation evidence-source validation finding."""

    rule_id: str
    message: str


@dataclass(frozen=True, slots=True)
class FoundationSourceValidation:
    """Validation result for one repository-local evidence source."""

    ok: bool
    findings: tuple[FoundationSourceFinding, ...]
    source_path: Path
    schema_path: Path
    source_id: str
    source_version: int
    source_hash: str
    source_authority_count: int
    evidence_record_count: int
    required_evidence_kinds: tuple[str, ...]
    observed_evidence_kinds: tuple[str, ...]


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit parse and type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_evidence_ledger_foundation_source(
    *,
    source_path: Path = DEFAULT_SOURCE_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> FoundationSourceValidation:
    """Validate schema and semantic admission for one foundation source."""

    source_payload = load_json_object(source_path, "evidence-ledger foundation source")
    schema_payload = load_json_object(schema_path, "evidence-ledger foundation source schema")
    findings: list[FoundationSourceFinding] = []
    findings.extend(_validate_schema(source_payload, schema_payload))
    findings.extend(_validate_markers(source_payload))
    findings.extend(_validate_source_authorities(source_payload))
    findings.extend(_validate_claim_evidence_coverage(source_payload))
    findings.extend(_validate_secret_absence(source_payload))
    source_authorities = _objects(source_payload.get("source_authorities"))
    evidence_records = _objects(source_payload.get("evidence_records"))
    required_evidence_kinds = _required_evidence_kinds(source_payload)
    observed_evidence_kinds = tuple(sorted({str(record.get("evidence_kind", "")) for record in evidence_records}))
    return FoundationSourceValidation(
        ok=not findings,
        findings=tuple(findings),
        source_path=source_path,
        schema_path=schema_path,
        source_id=str(source_payload.get("source_id", "")),
        source_version=int(source_payload.get("source_version", 0)) if isinstance(source_payload.get("source_version"), int) else 0,
        source_hash=_source_hash(source_payload),
        source_authority_count=len(source_authorities),
        evidence_record_count=len(evidence_records),
        required_evidence_kinds=required_evidence_kinds,
        observed_evidence_kinds=observed_evidence_kinds,
    )


def _validate_schema(payload: Mapping[str, Any], schema: Mapping[str, Any]) -> list[FoundationSourceFinding]:
    if jsonschema is None:
        return [FoundationSourceFinding("jsonschema_dependency_missing", "jsonschema dependency is required")]
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    findings: list[FoundationSourceFinding] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.path)):
        path = ".".join(str(part) for part in error.path) or "<root>"
        findings.append(
            FoundationSourceFinding(
                "foundation_source_schema_violation",
                f"{path}: {error.message}",
            )
        )
    return findings


def _validate_markers(payload: Mapping[str, Any]) -> list[FoundationSourceFinding]:
    findings: list[FoundationSourceFinding] = []
    for marker in REQUIRED_MARKERS:
        if payload.get(marker) is not True:
            findings.append(
                FoundationSourceFinding(
                    "foundation_source_marker_invalid",
                    f"{marker} must be true",
                )
            )
    return findings


def _validate_source_authorities(payload: Mapping[str, Any]) -> list[FoundationSourceFinding]:
    findings: list[FoundationSourceFinding] = []
    source_records = _objects(payload.get("source_authorities"))
    evidence_records = _objects(payload.get("evidence_records"))
    source_ids: set[str] = set()
    authority_by_source: dict[str, Mapping[str, Any]] = {}
    for source in source_records:
        source_id = str(source.get("source_id", ""))
        if source_id in source_ids:
            findings.append(FoundationSourceFinding("foundation_source_authority_duplicate", f"duplicate source_id: {source_id}"))
        source_ids.add(source_id)
        authority_by_source[source_id] = source

    evidence_keys: set[tuple[str, str, str]] = set()
    for record in evidence_records:
        source_id = str(record.get("source_id", ""))
        evidence_kind = str(record.get("evidence_kind", ""))
        authority_domain = str(record.get("authority_domain", ""))
        evidence_key = (evidence_kind, source_id, authority_domain)
        if evidence_key in evidence_keys:
            findings.append(FoundationSourceFinding("foundation_source_evidence_duplicate", f"duplicate evidence record: {evidence_key}"))
        evidence_keys.add(evidence_key)
        source = authority_by_source.get(source_id)
        if source is None:
            findings.append(FoundationSourceFinding("foundation_source_evidence_unknown_source", f"evidence source is not declared: {source_id}"))
            continue
        allowed_domains = {str(value) for value in _strings(source.get("authority_domains"))}
        forbidden_domains = {str(value) for value in _strings(source.get("forbidden_domains"))}
        if authority_domain not in allowed_domains:
            findings.append(
                FoundationSourceFinding(
                    "foundation_source_authority_domain_uncovered",
                    f"{source_id} does not authorize domain: {authority_domain}",
                )
            )
        if authority_domain in forbidden_domains:
            findings.append(
                FoundationSourceFinding(
                    "foundation_source_forbidden_authority_domain",
                    f"{source_id} explicitly forbids domain: {authority_domain}",
                )
            )
    return findings


def _validate_claim_evidence_coverage(payload: Mapping[str, Any]) -> list[FoundationSourceFinding]:
    findings: list[FoundationSourceFinding] = []
    required_kinds = set(_required_evidence_kinds(payload))
    observed_kinds = {str(record.get("evidence_kind", "")) for record in _objects(payload.get("evidence_records"))}
    missing_kinds = sorted(required_kinds - observed_kinds)
    if missing_kinds:
        findings.append(
            FoundationSourceFinding(
                "foundation_source_required_evidence_missing",
                f"missing required evidence kinds: {', '.join(missing_kinds)}",
            )
        )

    minimum_independent_sources = _minimum_independent_sources(payload)
    observed_sources = {str(record.get("source_id", "")) for record in _objects(payload.get("evidence_records"))}
    if len(observed_sources) < minimum_independent_sources:
        findings.append(
            FoundationSourceFinding(
                "foundation_source_independent_sources_insufficient",
                f"requires {minimum_independent_sources} independent sources, observed {len(observed_sources)}",
            )
        )
    return findings


def _validate_secret_absence(payload: Mapping[str, Any]) -> list[FoundationSourceFinding]:
    findings: list[FoundationSourceFinding] = []
    for path, value in _walk_values(payload):
        path_label = ".".join(path)
        if path and SECRET_KEY_PATTERN.search(path[-1]):
            findings.append(FoundationSourceFinding("foundation_source_secret_key_forbidden", f"secret-like key rejected: {path_label}"))
        if isinstance(value, str) and SECRET_VALUE_PATTERN.search(value):
            findings.append(FoundationSourceFinding("foundation_source_secret_value_forbidden", f"secret-like value rejected: {path_label}"))
    return findings


def _required_evidence_kinds(payload: Mapping[str, Any]) -> tuple[str, ...]:
    claim = payload.get("claim")
    if not isinstance(claim, Mapping):
        return ()
    profile = claim.get("expected_evidence_profile")
    if not isinstance(profile, Mapping):
        return ()
    return tuple(str(value) for value in _strings(profile.get("required_evidence_kinds")))


def _minimum_independent_sources(payload: Mapping[str, Any]) -> int:
    claim = payload.get("claim")
    if not isinstance(claim, Mapping):
        return 1
    profile = claim.get("expected_evidence_profile")
    if not isinstance(profile, Mapping):
        return 1
    value = profile.get("minimum_independent_sources", 1)
    return value if isinstance(value, int) else 1


def _objects(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if isinstance(item, str))


def _walk_values(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk_values(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_values(child, (*path, str(index)))


def _source_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value rejected: {value}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    args = parser.parse_args(argv)

    result = validate_evidence_ledger_foundation_source(source_path=args.source, schema_path=args.schema)
    if result.ok:
        print("[PASS] evidence_ledger_foundation_source")
        print(f"source_id={result.source_id}")
        print(f"source_hash={result.source_hash}")
        print(f"source_authorities={result.source_authority_count}")
        print(f"evidence_records={result.evidence_record_count}")
        print("STATUS: passed")
        return 0

    print("[FAIL] evidence_ledger_foundation_source")
    for finding in result.findings:
        print(f"{finding.rule_id}: {finding.message}")
    print("STATUS: failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
