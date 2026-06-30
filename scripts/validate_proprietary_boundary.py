#!/usr/bin/env python3
"""Validate Mullusi proprietary boundary invariants.

Purpose: fail closed when ownership notice, package metadata, code ownership,
or obsolete license wording drifts away from the Mullusi proprietary boundary.
Governance scope: repository-local license, NOTICE, CODEOWNERS, package
metadata, Rust crate metadata, and scanned source/document text.
Dependencies: Python standard library, LICENSE, NOTICE, .github/CODEOWNERS,
Rust crate Cargo.toml files, mcoi/pyproject.toml, and sdk/typescript/package.json.
Invariants:
  - Proprietary ownership notice names Tamirat Wubie and Mullusi.
  - License metadata is explicit and non-permissive.
  - Boundary files require the Mullusi owner review account.
  - Obsolete free/public-license grant wording cannot re-enter the repo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OWNER = "@tamirat-wubie"

NOTICE_PATH = REPO_ROOT / "NOTICE"
CODEOWNERS_PATH = REPO_ROOT / ".github" / "CODEOWNERS"
PYPROJECT_PATH = REPO_ROOT / "mcoi" / "pyproject.toml"
TYPESCRIPT_PACKAGE_PATH = REPO_ROOT / "sdk" / "typescript" / "package.json"
RUST_CRATES_DIR = REPO_ROOT / "maf" / "rust" / "crates"

NOTICE_REQUIRED_LITERALS = (
    "Mullusi Proprietary Notice",
    "Copyright (c) 2026 Tamirat Wubie and Mullusi.",
    "All rights reserved.",
    "proprietary works invented by Tamirat Wubie",
    "governed for authorized use under the Mullusi company boundary",
    "not free for public use",
    "No rights are granted except by explicit written agreement with Mullusi",
)

CODEOWNER_REQUIRED_RULES = (
    f"/LICENSE {OWNER}",
    f"/NOTICE {OWNER}",
    f"/GITHUB_SURFACE.md {OWNER}",
    f"/STATUS.md {OWNER}",
    f"/docs/PRODUCT_BOUNDARY.md {OWNER}",
    f"/mcoi/pyproject.toml {OWNER}",
    f"/sdk/typescript/package.json {OWNER}",
    f"/maf/rust/crates/*/Cargo.toml {OWNER}",
    f"/scripts/validate_public_repository_surface.py {OWNER}",
    f"/scripts/validate_proprietary_boundary.py {OWNER}",
    f"/.github/workflows/ci.yml {OWNER}",
    f"/.github/CODEOWNERS {OWNER}",
)

PYPROJECT_REQUIRED_LITERAL = 'license = { text = "Mullusi Proprietary. All rights reserved." }'
TYPESCRIPT_REQUIRED_LICENSE = "UNLICENSED"
RUST_REQUIRED_LICENSE = 'license = "LicenseRef-Mullusi-Proprietary"'

FORBIDDEN_TEXT_PATTERNS = (
    "MIT" + " License",
    "Permission is hereby " + "granted",
    "free" + " of charge",
    'license = "' + "MIT" + '"',
    '"license": "' + "MIT" + '"',
    "open" + " source",
    "artificial " + "intelligence",
    "A" + "I assistant",
    "A" + "I agent",
    "A" + "I-generated",
    "Mullu " + "A" + "I",
    "Mulu " + "A" + "I",
)
SCANNED_SUFFIXES = frozenset(
    {
        ".cfg",
        ".cmd",
        ".env",
        ".ini",
        ".json",
        ".md",
        ".ps1",
        ".py",
        ".rs",
        ".sh",
        ".toml",
        ".ts",
        ".tsx",
        ".yaml",
        ".yml",
    }
)

EXCLUDED_DIR_NAMES = frozenset(
    {
        ".claude",
        ".git",
        ".hypothesis",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "node_modules",
        "target",
        "tmp",
        ".tmp",
        ".worktrees",
        ".change_assurance",
    }
)
EXCLUDED_DIR_PREFIXES = (
    "mullu-control-plane",
)


def _relative(path: Path) -> str:
    """Return a stable repository-relative path for diagnostics."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _read_text(path: Path) -> tuple[str | None, str | None]:
    """Read a text file with explicit error reporting."""
    try:
        return path.read_text(encoding="utf-8"), None
    except OSError as exc:
        return None, f"{_relative(path)} cannot be read: {exc}"
    except UnicodeDecodeError as exc:
        return None, f"{_relative(path)} is not utf-8 text: {exc}"


def validate_required_literals(
    *,
    path: Path,
    required_literals: tuple[str, ...],
    label: str,
) -> list[str]:
    """Validate that a text artifact contains all required literals."""
    content, read_error = _read_text(path)
    if read_error:
        return [read_error]
    if content is None:
        return [f"{label} content unavailable"]

    missing = [literal for literal in required_literals if literal not in content]
    if missing:
        return [f"{label} missing required literals: {', '.join(missing)}"]
    return []


def validate_codeowners(path: Path = CODEOWNERS_PATH) -> list[str]:
    """Validate that proprietary boundary files require owner review."""
    content, read_error = _read_text(path)
    if read_error:
        return [read_error]
    if content is None:
        return ["CODEOWNERS content unavailable"]

    lines = {line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")}
    missing = [rule for rule in CODEOWNER_REQUIRED_RULES if rule not in lines]
    if missing:
        return [f"CODEOWNERS missing required owner rules: {', '.join(missing)}"]
    return []


def validate_pyproject_license(path: Path = PYPROJECT_PATH) -> list[str]:
    """Validate Python package license metadata."""
    content, read_error = _read_text(path)
    if read_error:
        return [read_error]
    if content is None:
        return ["pyproject content unavailable"]
    if PYPROJECT_REQUIRED_LITERAL not in content:
        return [f"{_relative(path)} missing proprietary license metadata"]
    return []


def validate_typescript_package(path: Path = TYPESCRIPT_PACKAGE_PATH) -> list[str]:
    """Validate TypeScript package non-publishable metadata."""
    content, read_error = _read_text(path)
    if read_error:
        return [read_error]
    if content is None:
        return ["TypeScript package content unavailable"]
    try:
        package = json.loads(content)
    except json.JSONDecodeError as exc:
        return [f"{_relative(path)} is not valid JSON: {exc}"]

    errors: list[str] = []
    if package.get("private") is not True:
        errors.append(f"{_relative(path)} must set private=true")
    if package.get("license") != TYPESCRIPT_REQUIRED_LICENSE:
        errors.append(f"{_relative(path)} must set license={TYPESCRIPT_REQUIRED_LICENSE}")
    return errors


def validate_rust_crate_licenses(crates_dir: Path = RUST_CRATES_DIR) -> list[str]:
    """Validate every Rust crate declares the Mullusi proprietary license ref."""
    errors: list[str] = []
    cargo_files = sorted(crates_dir.glob("*/Cargo.toml"))
    if not cargo_files:
        return [f"{_relative(crates_dir)} contains no crate Cargo.toml files"]

    for cargo_file in cargo_files:
        content, read_error = _read_text(cargo_file)
        if read_error:
            errors.append(read_error)
            continue
        if content is None or RUST_REQUIRED_LICENSE not in content:
            errors.append(f"{_relative(cargo_file)} missing {RUST_REQUIRED_LICENSE}")
    return errors


def iter_scannable_files(root: Path = REPO_ROOT) -> list[Path]:
    """Return repository files whose text content participates in boundary checks."""
    files: list[Path] = []
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            children = tuple(sorted(current.iterdir()))
        except OSError:
            continue
        for path in children:
            relative_path = path.relative_to(root)
            if path.is_dir():
                if _skip_scan_directory(path, relative_path, root):
                    continue
                pending.append(path)
                continue
            if not path.is_file():
                continue
            if any(part in EXCLUDED_DIR_NAMES for part in relative_path.parts):
                continue
            if path.suffix.lower() not in SCANNED_SUFFIXES:
                continue
            files.append(path)
    return sorted(files)


def _skip_scan_directory(path: Path, relative_path: Path, root: Path) -> bool:
    """Return whether a directory is outside the proprietary scan boundary."""
    if any(part in EXCLUDED_DIR_NAMES for part in relative_path.parts):
        return True
    if path != root and any(part.startswith(EXCLUDED_DIR_PREFIXES) for part in relative_path.parts):
        return True
    if path != root and (path / ".git").exists():
        return True
    return False


def scan_forbidden_text_patterns(
    *,
    root: Path = REPO_ROOT,
    forbidden_patterns: tuple[str, ...] = FORBIDDEN_TEXT_PATTERNS,
) -> list[str]:
    """Scan repository text for obsolete license or legacy product wording."""
    errors: list[str] = []
    for path in iter_scannable_files(root):
        content, read_error = _read_text(path)
        if read_error:
            errors.append(read_error)
            continue
        if content is None:
            errors.append(f"{_relative(path)} content unavailable")
            continue

        for pattern in forbidden_patterns:
            if pattern in content:
                errors.append(f"{_relative(path)} contains forbidden boundary text: {pattern}")
    return errors


def validate_proprietary_boundary() -> list[str]:
    """Validate the full Mullusi proprietary boundary contract."""
    errors: list[str] = []
    errors.extend(
        validate_required_literals(
            path=NOTICE_PATH,
            required_literals=NOTICE_REQUIRED_LITERALS,
            label="NOTICE",
        )
    )
    errors.extend(validate_codeowners())
    errors.extend(validate_pyproject_license())
    errors.extend(validate_typescript_package())
    errors.extend(validate_rust_crate_licenses())
    errors.extend(scan_forbidden_text_patterns())
    return errors


def main() -> int:
    """CLI entry point for proprietary boundary validation."""
    errors = validate_proprietary_boundary()
    print("=== Proprietary Boundary Validation ===")
    print(f"  notice:       {_relative(NOTICE_PATH)}")
    print(f"  codeowners:   {_relative(CODEOWNERS_PATH)}")
    print(f"  rust crates:  {len(sorted(RUST_CRATES_DIR.glob('*/Cargo.toml')))}")
    if errors:
        print("\nPROPRIETARY BOUNDARY GATES FAILED")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("\nALL PROPRIETARY BOUNDARY GATES PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
