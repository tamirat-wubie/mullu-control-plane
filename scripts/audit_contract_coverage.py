#!/usr/bin/env python3
"""Audit contract coverage: find ContractRecord / frozen dataclasses and classify test status.

Scans mcoi/mcoi_runtime/contracts/*.py (excluding __init__.py, _base.py, _shared_enums.py)
for classes with frozen=True or inheriting ContractRecord, then checks mcoi/tests/*.py
for references to those class names.

Classification:
  TESTED        - class name appears in a test file alongside round_trip/serialize/deserialize
  IMPORTED_ONLY - class name appears in a test file but without serialization tests
  UNTESTED      - class name not found in any test file

Exit code: 1 if any UNTESTED contracts exist, 0 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = REPO_ROOT / "mcoi" / "mcoi_runtime" / "contracts"
TESTS_DIR = REPO_ROOT / "mcoi" / "tests"

EXCLUDE_FILES = {"__init__.py", "_base.py", "_shared_enums.py"}

# Patterns to detect frozen dataclasses and ContractRecord subclasses
FROZEN_DC_RE = re.compile(r"@dataclass\(.*frozen\s*=\s*True.*\)\s*\nclass\s+(\w+)")
CONTRACT_INHERIT_RE = re.compile(r"class\s+(\w+)\(.*ContractRecord.*\)")

# Patterns that indicate a serialization round-trip test
ROUND_TRIP_KEYWORDS = re.compile(
    r"round.?trip|serialize_record|deserialize_record|serialize|deserialize|"
    r"to_json|from_json|to_dict|to_json_dict",
    re.IGNORECASE,
)


def find_contract_classes() -> dict[str, str]:
    """Return {ClassName: source_file} for all contract record classes."""
    classes: dict[str, str] = {}
    for py_file in sorted(CONTRACTS_DIR.glob("*.py")):
        if py_file.name in EXCLUDE_FILES:
            continue
        content = py_file.read_text(encoding="utf-8")
        for match in FROZEN_DC_RE.finditer(content):
            name = match.group(1)
            classes[name] = py_file.name
        for match in CONTRACT_INHERIT_RE.finditer(content):
            name = match.group(1)
            classes[name] = py_file.name
    return classes


def classify_coverage(
    contract_classes: dict[str, str],
) -> dict[str, list[str]]:
    """Classify each contract class as TESTED, IMPORTED_ONLY, or UNTESTED."""
    tested: list[str] = []
    imported_only: list[str] = []
    untested: list[str] = []

    # Pre-read all test files
    test_contents: dict[str, str] = {}
    if TESTS_DIR.exists():
        for tf in TESTS_DIR.glob("*.py"):
            test_contents[tf.name] = tf.read_text(encoding="utf-8")

    all_test_text = "\n".join(test_contents.values())

    for cls_name in sorted(contract_classes):
        if cls_name not in all_test_text:
            untested.append(cls_name)
            continue

        # Check if the class appears near serialization keywords in any test file
        has_round_trip = False
        for _fname, content in test_contents.items():
            if cls_name in content and ROUND_TRIP_KEYWORDS.search(content):
                has_round_trip = True
                break

        if has_round_trip:
            tested.append(cls_name)
        else:
            imported_only.append(cls_name)

    return {"TESTED": tested, "IMPORTED_ONLY": imported_only, "UNTESTED": untested}


def main() -> int:
    contract_classes = find_contract_classes()
    if not contract_classes:
        print("No contract classes found.")
        return 0

    print(f"Found {len(contract_classes)} contract record classes.\n")

    result = classify_coverage(contract_classes)

    for category in ("TESTED", "IMPORTED_ONLY", "UNTESTED"):
        items = result[category]
        print(f"--- {category} ({len(items)}) ---")
        for cls_name in items:
            src = contract_classes[cls_name]
            print(f"  {cls_name:50s}  ({src})")
        print()

    total = len(contract_classes)
    tested_count = len(result["TESTED"])
    imported_count = len(result["IMPORTED_ONLY"])
    untested_count = len(result["UNTESTED"])

    print(f"Summary: {tested_count} tested, {imported_count} imported-only, {untested_count} untested / {total} total")

    if untested_count > 0:
        print(f"\nExit code 1: {untested_count} untested contract(s) found.")
        return 1

    print("\nAll contracts have test coverage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
