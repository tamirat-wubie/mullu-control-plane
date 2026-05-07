"""Validate the compliance alignment matrix.

Purpose: keep framework mappings evidence-backed without claiming certification.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: JSON fixture and repository evidence files.
Invariants: every capability maps all target frameworks, evidence files exist, and certification claims remain false.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = REPO_ROOT / "tests" / "fixtures" / "compliance_alignment_matrix.json"
TARGET_FRAMEWORKS = frozenset({"SOC2", "HIPAA", "EU_ACT", "ISO_IEC_42001"})


def load_matrix(path: Path = MATRIX_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_matrix(matrix: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    claim_boundary = matrix.get("claim_boundary", {})
    if claim_boundary.get("certification_claimed") is not False:
        errors.append("claim_boundary.certification_claimed must be false")
    if claim_boundary.get("statement") != "alignment_only":
        errors.append("claim_boundary.statement must be alignment_only")
    if claim_boundary.get("review_required_before_external_publication") is not True:
        errors.append("external publication review must be required")

    source_frameworks = {source.get("framework") for source in matrix.get("source_refs", [])}
    missing_source_frameworks = TARGET_FRAMEWORKS - source_frameworks
    if missing_source_frameworks:
        errors.append(f"missing source refs: {sorted(missing_source_frameworks)}")

    seen_capability_ids: set[str] = set()
    for capability in matrix.get("capabilities", []):
        capability_id = capability.get("capability_id", "")
        if not capability_id:
            errors.append("capability_id is required")
            continue
        if capability_id in seen_capability_ids:
            errors.append(f"duplicate capability_id: {capability_id}")
        seen_capability_ids.add(capability_id)

        evidence_files = capability.get("evidence_files", [])
        if not evidence_files:
            errors.append(f"{capability_id}: evidence_files required")
        for evidence_file in evidence_files:
            if not (REPO_ROOT / evidence_file).exists():
                errors.append(f"{capability_id}: missing evidence file {evidence_file}")

        mapped_frameworks = {mapping.get("framework") for mapping in capability.get("mappings", [])}
        missing_frameworks = TARGET_FRAMEWORKS - mapped_frameworks
        extra_frameworks = mapped_frameworks - TARGET_FRAMEWORKS
        if missing_frameworks:
            errors.append(f"{capability_id}: missing framework mappings {sorted(missing_frameworks)}")
        if extra_frameworks:
            errors.append(f"{capability_id}: unknown framework mappings {sorted(extra_frameworks)}")

        for mapping in capability.get("mappings", []):
            if not mapping.get("control_area"):
                errors.append(f"{capability_id}: mapping control_area required")
            if not mapping.get("alignment"):
                errors.append(f"{capability_id}: mapping alignment required")

    if not matrix.get("capabilities"):
        errors.append("at least one capability mapping is required")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the canonical matrix JSON.")
    args = parser.parse_args()

    matrix = load_matrix()
    errors = validate_matrix(matrix)
    if errors:
        for error in errors:
            print(error)
        return 1
    if args.json:
        print(json.dumps(matrix, indent=2, sort_keys=True))
    else:
        print(
            "compliance alignment matrix ok: "
            f"{len(matrix['capabilities'])} capabilities, {len(TARGET_FRAMEWORKS)} frameworks"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
