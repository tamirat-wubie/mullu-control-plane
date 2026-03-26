#!/usr/bin/env python3
"""Deterministic release-status validation for the MCOI internal-alpha surface.

Validates:
  1. Required release, operator, and pilot governance documents exist.
  2. Shared schemas, contract parity, and canonical fixtures remain valid.
  3. Shipped artifacts and governed operational docs remain aligned with live inventories.
  4. A single release summary can be derived from live profiles, packs, schemas, and witnesses.

Usage:
  python scripts/validate_release_status.py
  python scripts/validate_release_status.py --strict
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_PATH = REPO_ROOT / "mcoi"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(MCOI_PATH) not in sys.path:
    sys.path.insert(0, str(MCOI_PATH))

from mcoi_runtime.app.policy_packs import PolicyPackRegistry
from mcoi_runtime.app.profiles import list_profiles
from scripts import validate_artifacts, validate_schemas


REQUIRED_RELEASE_DOCUMENTS: tuple[str, ...] = (
    "README.md",
    "RELEASE_NOTES_v0.1.md",
    "RELEASE_CHECKLIST_v0.1.md",
    "KNOWN_LIMITATIONS_v0.1.md",
    "SECURITY_MODEL_v0.1.md",
    "OPERATOR_GUIDE_v0.1.md",
    "PILOT_WORKFLOWS_v0.1.md",
    "PILOT_CHECKLIST_v0.1.md",
    "PILOT_OPERATIONS_GUIDE_v0.1.md",
)


@dataclass(frozen=True, slots=True)
class ReleaseStatusSummary:
    """Live governed inventory behind the release-status claim."""

    release_documents: tuple[str, ...]
    schema_files: tuple[str, ...]
    builtin_profiles: tuple[str, ...]
    policy_packs: tuple[str, ...]
    config_artifacts: tuple[str, ...]
    request_artifacts: tuple[str, ...]
    auxiliary_artifacts: tuple[str, ...]


def _sorted_names(paths: tuple[Path, ...] | list[Path]) -> tuple[str, ...]:
    return tuple(sorted(path.relative_to(REPO_ROOT).as_posix() for path in paths))


def discover_release_status_summary() -> ReleaseStatusSummary:
    """Collect the live governed inventory behind the release surface."""
    artifact_inventory = validate_artifacts.discover_example_inventory()
    schema_files = tuple(
        sorted(path.name for path in validate_schemas.SCHEMA_DIR.glob("*.schema.json"))
    )
    release_documents = tuple(
        document_name
        for document_name in REQUIRED_RELEASE_DOCUMENTS
        if (REPO_ROOT / document_name).exists()
    )
    builtin_profiles = tuple(sorted(list_profiles()))
    policy_packs = tuple(
        sorted(pack.pack_id for pack in PolicyPackRegistry().list_packs())
    )

    return ReleaseStatusSummary(
        release_documents=release_documents,
        schema_files=schema_files,
        builtin_profiles=builtin_profiles,
        policy_packs=policy_packs,
        config_artifacts=_sorted_names(list(artifact_inventory.config_paths)),
        request_artifacts=_sorted_names(list(artifact_inventory.request_paths)),
        auxiliary_artifacts=_sorted_names(list(artifact_inventory.auxiliary_paths)),
    )


def validate_release_status(*, strict: bool = False) -> tuple[ReleaseStatusSummary, list[str]]:
    """Validate the governed release surface and return live inventory plus errors."""
    errors: list[str] = []
    summary = discover_release_status_summary()

    missing_documents = tuple(
        document_name
        for document_name in REQUIRED_RELEASE_DOCUMENTS
        if document_name not in summary.release_documents
    )
    if missing_documents:
        errors.append(f"missing required release documents: {list(missing_documents)}")

    errors.extend(validate_schemas.validate_json_schemas())
    errors.extend(validate_schemas.check_contract_parity(strict=strict))
    errors.extend(validate_schemas.check_rust_contract_parity(strict=strict))
    errors.extend(validate_schemas.validate_canonical_fixtures(strict=strict))
    errors.extend(validate_schemas.check_python_fixture_round_trip())
    errors.extend(validate_artifacts.validate_example_artifacts(strict=strict))

    if strict:
        if not summary.schema_files:
            errors.append("release status requires at least one schema file")
        if not summary.builtin_profiles:
            errors.append("release status requires at least one built-in profile")
        if not summary.policy_packs:
            errors.append("release status requires at least one policy pack")
        if not summary.config_artifacts:
            errors.append("release status requires at least one config artifact")
        if not summary.request_artifacts:
            errors.append("release status requires at least one request artifact")

    return summary, errors


def main() -> None:
    strict = "--strict" in sys.argv
    summary, errors = validate_release_status(strict=strict)

    print("=== Release Status Summary ===")
    print(f"  release docs:       {len(summary.release_documents)}")
    print(f"  schemas:            {len(summary.schema_files)}")
    print(f"  builtin profiles:   {len(summary.builtin_profiles)}")
    print(f"  policy packs:       {len(summary.policy_packs)}")
    print(f"  config artifacts:   {len(summary.config_artifacts)}")
    print(f"  request artifacts:  {len(summary.request_artifacts)}")
    print(f"  auxiliary artifacts:{len(summary.auxiliary_artifacts):>4}")

    print("\n=== Live Inventory ===")
    print(f"  profiles: {', '.join(summary.builtin_profiles)}")
    print(f"  packs:    {', '.join(summary.policy_packs)}")

    print("\n=== Release Validation ===")
    if errors:
        print(f"\n{'=' * 40}")
        print(f"FAILED - {len(errors)} error(s):")
        for error in errors:
            print(f"  X {error}")
        sys.exit(1)

    print(f"\n{'=' * 40}")
    print("ALL RELEASE GATES PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
