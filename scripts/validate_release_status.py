#!/usr/bin/env python3
"""Deterministic release-status validation for the MCOI internal-alpha surface.

Validates:
  1. Required release, operator, and pilot governance documents exist.
  2. Shared schemas, contract parity, and canonical fixtures remain valid.
  3. Shipped artifacts and governed operational docs remain aligned with live inventories.
  4. The CI workflow still carries the required test and validation command gates.
  5. A single release summary can be derived from live profiles, packs, schemas, and witnesses.

Usage:
  python scripts/validate_release_status.py
  python scripts/validate_release_status.py --strict
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
import re

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

CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

REQUIRED_CI_LITERALS: tuple[str, ...] = (
    'branches: [main, "codex/*", "phase-*", "maf/*", "mcoi/*", "infra/*"]',
    'python -m pytest --tb=short -q -m "not soak"',
    'python -m pytest -m soak --tb=short -q',
    "cargo test",
    "cargo fmt -- --check",
    "cargo clippy -- -D warnings",
    "python scripts/validate_schemas.py",
    "python scripts/validate_artifacts.py",
    "python scripts/validate_schemas.py --strict",
    "python scripts/validate_artifacts.py --strict",
    "python scripts/validate_release_status.py",
    "python scripts/validate_release_status.py --strict",
)

METADATA_DOCUMENTS: tuple[str, ...] = (
    "RELEASE_NOTES_v0.1.md",
    "KNOWN_LIMITATIONS_v0.1.md",
    "SECURITY_MODEL_v0.1.md",
)

ACCEPTED_LIMITATION_EXPECTATIONS: dict[str, tuple[str, ...]] = {
    "registry_backend_limitation": (
        "make_dataclass",
    ),
    "coordination_persistence_limitation": (
        "Coordination state is in-memory only",
    ),
    "memory_persistence_limitation": (
        "Working and episodic memory persistence is explicit and opt-in",
        "does not auto-save or auto-restore",
    ),
    "http_connector_limitation": (
        "HTTP connector",
        "urllib",
    ),
    "auth_limitation": (
        "No Authentication or Authorization",
    ),
    "encryption_limitation": (
        "No Encryption at Rest",
    ),
}

SOURCE_HYGIENE_GLOBS: tuple[str, ...] = ("*.py", "*.rs", "*.toml", "*.yml", "*.yaml")
IGNORED_SOURCE_DIR_SEGMENTS: tuple[str, ...] = (
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "target",
)
PYTHON_BARE_EXCEPT_PATTERN = re.compile(r"^\s*except\s*:\s*$", re.MULTILINE)
LINE_COMMENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"#\s*(TODO|FIXME|HACK)\b"),
    re.compile(r"//\s*(TODO|FIXME|HACK)\b"),
    re.compile(r"/\*\s*(TODO|FIXME|HACK)\b"),
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
    ci_workflow_present: bool
    release_version: str | None
    release_date: str | None


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
        ci_workflow_present=CI_WORKFLOW_PATH.exists(),
        release_version=None,
        release_date=None,
    )


def validate_ci_workflow_text(content: str) -> list[str]:
    """Validate that the CI workflow carries the required release gates."""
    errors: list[str] = []

    missing_literals = tuple(
        literal for literal in REQUIRED_CI_LITERALS if literal not in content
    )
    if missing_literals:
        errors.append(f"ci workflow missing required literals: {list(missing_literals)}")

    return errors


def _extract_metadata_field(content: str, label: str) -> str | None:
    match = re.search(rf"^\*\*{re.escape(label)}:\*\*\s*(.+)$", content, re.MULTILINE)
    if match is None:
        return None
    return match.group(1).strip()


def validate_release_metadata_texts(metadata_texts: dict[str, str]) -> tuple[tuple[str | None, str | None], list[str]]:
    """Validate that release-surface docs carry aligned version and date metadata."""
    errors: list[str] = []
    extracted: dict[str, tuple[str | None, str | None]] = {}

    for document_name, content in metadata_texts.items():
        version = _extract_metadata_field(content, "Version")
        date = _extract_metadata_field(content, "Date")
        extracted[document_name] = (version, date)
        if version is None:
            errors.append(f"{document_name}: missing Version metadata")
        if date is None:
            errors.append(f"{document_name}: missing Date metadata")

    reference_version: str | None = None
    reference_date: str | None = None
    for document_name in METADATA_DOCUMENTS:
        version, date = extracted.get(document_name, (None, None))
        if version is not None and reference_version is None:
            reference_version = version
        if date is not None and reference_date is None:
            reference_date = date

    if reference_version is not None and "internal alpha" not in reference_version:
        errors.append(f"release metadata version must declare internal alpha: {reference_version}")

    for document_name, (version, date) in extracted.items():
        if reference_version is not None and version is not None and version != reference_version:
            errors.append(
                f"{document_name}: version metadata mismatch {version!r} != {reference_version!r}"
            )
        if reference_date is not None and date is not None and date != reference_date:
            errors.append(
                f"{document_name}: date metadata mismatch {date!r} != {reference_date!r}"
            )

    return (reference_version, reference_date), errors


def validate_release_limitation_coverage(
    *,
    known_limitations_text: str,
    security_model_text: str,
) -> list[str]:
    """Validate that accepted release limitations are anchored in supporting docs."""
    errors: list[str] = []
    limitation_sources = {
        "registry_backend_limitation": known_limitations_text,
        "coordination_persistence_limitation": known_limitations_text,
        "memory_persistence_limitation": known_limitations_text,
        "http_connector_limitation": known_limitations_text,
        "auth_limitation": security_model_text,
        "encryption_limitation": security_model_text,
    }

    for limitation_id, required_literals in ACCEPTED_LIMITATION_EXPECTATIONS.items():
        source = limitation_sources[limitation_id]
        missing_literals = tuple(literal for literal in required_literals if literal not in source)
        if missing_literals:
            errors.append(
                f"{limitation_id}: missing supporting literals {list(missing_literals)}"
            )

    return errors


def _iter_source_hygiene_paths() -> tuple[Path, ...]:
    paths: list[Path] = []
    for pattern in SOURCE_HYGIENE_GLOBS:
        for path in REPO_ROOT.rglob(pattern):
            if any(segment in IGNORED_SOURCE_DIR_SEGMENTS for segment in path.parts):
                continue
            if not path.is_file():
                continue
            paths.append(path)
    return tuple(sorted(set(paths)))


def scan_source_hygiene_text(path: Path, content: str) -> list[str]:
    """Scan one governed source file for release-checklist hygiene violations."""
    errors: list[str] = []
    relative_path = path.relative_to(REPO_ROOT).as_posix()

    if path.suffix == ".py" and PYTHON_BARE_EXCEPT_PATTERN.search(content):
        errors.append(f"{relative_path}: contains bare except clause")

    for pattern in LINE_COMMENT_PATTERNS:
        match = pattern.search(content)
        if match is not None:
            errors.append(
                f"{relative_path}: contains source hygiene marker {match.group(1)}"
            )
            break

    return errors


def validate_source_hygiene() -> list[str]:
    """Validate release-checklist hygiene claims across governed source files."""
    errors: list[str] = []
    for path in _iter_source_hygiene_paths():
        content = path.read_text(encoding="utf-8")
        errors.extend(scan_source_hygiene_text(path, content))
    return errors


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
    if not summary.ci_workflow_present:
        errors.append("missing required CI workflow: .github/workflows/ci.yml")
    else:
        ci_content = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
        errors.extend(validate_ci_workflow_text(ci_content))

    metadata_texts = {
        document_name: (REPO_ROOT / document_name).read_text(encoding="utf-8")
        for document_name in METADATA_DOCUMENTS
        if (REPO_ROOT / document_name).exists()
    }
    (release_version, release_date), metadata_errors = validate_release_metadata_texts(
        metadata_texts
    )
    errors.extend(metadata_errors)
    if len(metadata_texts) == len(METADATA_DOCUMENTS):
        errors.extend(
            validate_release_limitation_coverage(
                known_limitations_text=metadata_texts["KNOWN_LIMITATIONS_v0.1.md"],
                security_model_text=metadata_texts["SECURITY_MODEL_v0.1.md"],
            )
        )

    errors.extend(validate_source_hygiene())

    summary = ReleaseStatusSummary(
        release_documents=summary.release_documents,
        schema_files=summary.schema_files,
        builtin_profiles=summary.builtin_profiles,
        policy_packs=summary.policy_packs,
        config_artifacts=summary.config_artifacts,
        request_artifacts=summary.request_artifacts,
        auxiliary_artifacts=summary.auxiliary_artifacts,
        ci_workflow_present=summary.ci_workflow_present,
        release_version=release_version,
        release_date=release_date,
    )

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
    print(f"  ci workflow:        {'present' if summary.ci_workflow_present else 'missing'}")
    print(f"  release version:    {summary.release_version or 'missing'}")
    print(f"  release date:       {summary.release_date or 'missing'}")

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
