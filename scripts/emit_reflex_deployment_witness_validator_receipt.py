#!/usr/bin/env python3
"""Emit a Reflex deployment witness validator receipt.

Purpose: convert the CI JUnit result for Reflex deployment witness replay into
    a compact JSON receipt for release summaries and operator review.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: pytest JUnit XML, Reflex witness schema, Reflex witness validator.
Invariants:
  - Missing or malformed JUnit evidence fails closed.
  - Receipt identity is bound to the JUnit hash and validator evidence paths.
  - Passing receipts require zero JUnit failures and zero JUnit errors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JUNIT_PATH = Path(".change_assurance") / "reflex_deployment_witness_validator_junit.xml"
DEFAULT_RECEIPT_OUTPUT = Path(".change_assurance") / "reflex_deployment_witness_validator_receipt.json"
VALIDATOR_PATH = Path("scripts") / "validate_reflex_deployment_witness.py"
SCHEMA_PATH = Path("schemas") / "reflex_deployment_witness_envelope.schema.json"
TEST_PATH = Path("tests") / "test_validate_reflex_deployment_witness.py"
BOUNDED_JUNIT_REF = "provided-reflex-validator-junit"


@dataclass(frozen=True, slots=True)
class ReflexDeploymentWitnessValidatorReceipt:
    """Receipt for one Reflex deployment witness validator CI run."""

    receipt_id: str
    status: str
    validator: str
    schema: str
    test_suite: str
    junit_path: str
    junit_sha256: str
    test_count: int
    failure_count: int
    error_count: int
    skipped_count: int
    generated_at: str
    evidence_refs: tuple[str, ...]
    blockers: tuple[str, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready receipt payload."""
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        payload["blockers"] = list(self.blockers)
        return payload


def emit_reflex_deployment_witness_validator_receipt(
    *,
    junit_path: Path = DEFAULT_JUNIT_PATH,
    output_path: Path = DEFAULT_RECEIPT_OUTPUT,
    generated_at: str = "",
) -> ReflexDeploymentWitnessValidatorReceipt:
    """Emit and write one Reflex deployment witness validator receipt."""
    receipt = build_reflex_deployment_witness_validator_receipt(
        junit_path=junit_path,
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def build_reflex_deployment_witness_validator_receipt(
    *,
    junit_path: Path,
    generated_at: str,
) -> ReflexDeploymentWitnessValidatorReceipt:
    """Build one receipt from a pytest JUnit XML report."""
    blockers: list[str] = []
    test_count = 0
    failure_count = 0
    error_count = 0
    skipped_count = 0
    junit_hash = ""
    if not junit_path.exists():
        blockers.append("junit_missing")
    else:
        try:
            junit_bytes = junit_path.read_bytes()
            junit_hash = hashlib.sha256(junit_bytes).hexdigest()
            root = ElementTree.fromstring(junit_bytes)
            test_count = _xml_int(root, "tests")
            failure_count = _xml_int(root, "failures")
            error_count = _xml_int(root, "errors")
            skipped_count = _xml_int(root, "skipped")
        except (OSError, ElementTree.ParseError, ValueError):
            blockers.append("junit_unreadable")
    for evidence_path in (VALIDATOR_PATH, SCHEMA_PATH, TEST_PATH):
        if not (REPO_ROOT / evidence_path).exists():
            blockers.append(f"missing_evidence:{evidence_path.as_posix()}")
    if failure_count:
        blockers.append("junit_failures_present")
    if error_count:
        blockers.append("junit_errors_present")

    status = "passed" if not blockers else "failed"
    receipt_seed = {
        "status": status,
        "validator": VALIDATOR_PATH.as_posix(),
        "schema": SCHEMA_PATH.as_posix(),
        "test_suite": TEST_PATH.as_posix(),
        "junit_sha256": junit_hash,
        "test_count": test_count,
        "failure_count": failure_count,
        "error_count": error_count,
        "skipped_count": skipped_count,
    }
    receipt_id = f"reflex-witness-validator-receipt-{_stable_hash(receipt_seed)[:16]}"
    return ReflexDeploymentWitnessValidatorReceipt(
        receipt_id=receipt_id,
        status=status,
        validator=VALIDATOR_PATH.as_posix(),
        schema=SCHEMA_PATH.as_posix(),
        test_suite=TEST_PATH.as_posix(),
        junit_path=BOUNDED_JUNIT_REF,
        junit_sha256=junit_hash,
        test_count=test_count,
        failure_count=failure_count,
        error_count=error_count,
        skipped_count=skipped_count,
        generated_at=generated_at,
        evidence_refs=(
            f"junit:{BOUNDED_JUNIT_REF}",
            f"validator:{VALIDATOR_PATH.as_posix()}",
            f"schema:{SCHEMA_PATH.as_posix()}",
            f"tests:{TEST_PATH.as_posix()}",
        ),
        blockers=tuple(blockers),
    )


def _xml_int(root: ElementTree.Element, attribute: str) -> int:
    value = root.attrib.get(attribute, "0")
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{attribute} must be non-negative")
    return parsed


def _stable_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, default=DEFAULT_JUNIT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_RECEIPT_OUTPUT)
    parser.add_argument("--generated-at", default="")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Reflex deployment witness validator receipt emitter."""
    args = build_parser().parse_args(argv)
    receipt = emit_reflex_deployment_witness_validator_receipt(
        junit_path=args.junit,
        output_path=args.output,
        generated_at=args.generated_at,
    )
    payload = receipt.to_json_dict()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"{payload['status']}: {payload['receipt_id']}")
    return 0 if receipt.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
