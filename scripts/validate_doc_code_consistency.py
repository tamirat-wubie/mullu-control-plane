#!/usr/bin/env python3
"""
Doc/Code Consistency Check — Anti-Fabrication Gate.

Scans documentation for references that must resolve in code:
  Check 1 — Environment-variable flags must be referenced in code.
  Check 2 — Module path references must point to real files.
  Check 3 — 25-construct names must exist in the implemented tier files.

Designed to run in CI as part of the release-status gate. A doc-only PR that
introduces an unwired flag or a non-existent module path fails the check.

This is the structural enforcement of the lesson recorded in
mcoi/mcoi_runtime/migration/PHASE_2_NOTES.md — fabrications get caught by the
system, not by audit instinct.

Exit codes:
  0  All checks pass
  1  At least one fabrication detected
  2  Internal error (could not scan)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent

DOC_GLOBS = (
    "*.md",
    "docs/**/*.md",
    "mcoi/mcoi_runtime/migration/*.md",
)

CODE_GLOBS = (
    "mcoi/mcoi_runtime/**/*.py",
    "maf/**/*.rs",
    "scripts/*.py",
    "tests/**/*.py",
    "mcoi/tests/**/*.py",
)

# Flags follow ALL_CAPS_WITH_UNDERSCORES, length >= 3.
#
# We catch the MUSIA_MODE class of fabrication: shell-style flag usage in docs
# that promises behavior the code does not deliver. We DO NOT catch spec-level
# identifiers in formal notation (e.g. `flags : subset of {ARCHIVE_MODE, ...}`)
# because those are specifications, not behavioral claims.
#
# Trigger forms:
#   - `FOO_MODE=value` (assignment in shell or doc)
#   - `export FOO_MODE`
#   - `$FOO_MODE` (shell reference)
#   - In a fenced bash code block (handled separately)
FLAG_PATTERN = re.compile(
    r"(?:export\s+|\$|^|\s)([A-Z][A-Z0-9_]{2,}_MODE)\s*="
)
FLAG_BASH_BLOCK_PATTERN = re.compile(
    r"```bash\b[^`]*?\b([A-Z][A-Z0-9_]{2,}_MODE)\b[^`]*?```",
    re.DOTALL,
)

# Module path references like `mcoi/mcoi_runtime/foo/bar.py` or
# `mcoi_runtime.foo.bar`. We pick up backtick-quoted forms in docs.
PYTHON_PATH_PATTERN = re.compile(
    r"`([a-z_][a-z0-9_]*(?:[/.][a-z_][a-z0-9_]*)+\.py)`"
)

# 25-construct names in TitleCase, referenced in narrative prose with backticks.
CONSTRUCT_NAMES = frozenset({
    # Tier 1
    "State", "Change", "Causation", "Constraint", "Boundary",
    # Tier 2
    "Pattern", "Transformation", "Composition", "Interaction", "Conservation",
    # Tier 3
    "Coupling", "Synchronization", "Resonance", "Equilibrium", "Emergence",
    # Tier 4
    "Source", "Binding", "Validation", "Evolution", "Integrity",
    # Tier 5
    "Observation", "Inference", "Decision", "Execution", "Learning",
})


def _gather(globs: Iterable[str]) -> list[Path]:
    seen: set[Path] = set()
    for pattern in globs:
        for path in REPO_ROOT.glob(pattern):
            if path.is_file():
                seen.add(path)
    return sorted(seen)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _all_code_text() -> str:
    chunks: list[str] = []
    for path in _gather(CODE_GLOBS):
        chunks.append(_read(path))
    return "\n".join(chunks)


def check_flags(doc_files: list[Path], code_text: str) -> list[str]:
    """Every _MODE flag used as a shell flag in docs must appear in code."""
    failures: list[str] = []
    seen_per_doc: dict[Path, set[str]] = {}
    for doc in doc_files:
        text = _read(doc)
        flags_in_doc: set[str] = set()
        # Form 1: assignment style (FOO_MODE=value)
        for m in FLAG_PATTERN.finditer(text):
            flags_in_doc.add(m.group(1))
        # Form 2: anywhere inside a fenced bash block
        for m in FLAG_BASH_BLOCK_PATTERN.finditer(text):
            flags_in_doc.add(m.group(1))
        seen_per_doc[doc] = flags_in_doc
        for flag in flags_in_doc:
            if not re.search(rf"\b{re.escape(flag)}\b", code_text):
                failures.append(
                    f"FLAG: {doc.relative_to(REPO_ROOT)} references unwired flag '{flag}'"
                )
    return failures


# Search prefixes to resolve doc-relative module references.
# Doc authors often write paths like `core/mfidel_matrix.py` meaning
# `mcoi/mcoi_runtime/core/mfidel_matrix.py`. We try the most-specific roots
# first so a real fabrication still fails, but a sloppy-but-valid reference
# resolves.
PATH_RESOLUTION_PREFIXES: tuple[str, ...] = (
    "",
    "mcoi/",
    "mcoi/mcoi_runtime/",
    "mcoi/mcoi_runtime/app/",
)


def check_module_paths(doc_files: list[Path]) -> list[str]:
    """Every Python module path referenced in docs must exist somewhere."""
    failures: list[str] = []
    for doc in doc_files:
        text = _read(doc)
        for match in PYTHON_PATH_PATTERN.finditer(text):
            path_str = match.group(1)
            if "/" not in path_str:
                continue  # only path forms are validated
            resolved = False
            for prefix in PATH_RESOLUTION_PREFIXES:
                if (REPO_ROOT / f"{prefix}{path_str}").exists():
                    resolved = True
                    break
            if not resolved:
                failures.append(
                    f"PATH: {doc.relative_to(REPO_ROOT)} references nonexistent module '{path_str}'"
                )
    return failures


def check_constructs(doc_files: list[Path], code_text: str) -> list[str]:
    """Every 25-construct name referenced in MUSIA docs must exist as a class."""
    failures: list[str] = []
    construct_class_pattern = {
        name: re.compile(rf"^class {name}\b", re.MULTILINE)
        for name in CONSTRUCT_NAMES
    }
    for doc in doc_files:
        # Only check MUSIA-related docs (others may use these as plain words)
        if "MUSIA" not in doc.name and "musia" not in doc.name.lower():
            # Allow PHASE_2_NOTES and migration docs to use construct names freely
            if "PHASE" not in doc.name and "MIGRATION" not in doc.name:
                continue
        text = _read(doc)
        for name in CONSTRUCT_NAMES:
            # Look for backticked references like `Transformation`
            if re.search(rf"`{name}`", text):
                if not construct_class_pattern[name].search(code_text):
                    failures.append(
                        f"CONSTRUCT: {doc.relative_to(REPO_ROOT)} "
                        f"references '{name}' but no `class {name}` in code"
                    )
    return failures


BASELINE_PATH = REPO_ROOT / "scripts" / "doc_code_consistency_baseline.txt"


def _load_baseline() -> set[str]:
    """Pre-existing failures recorded at v4.1.0 introduction. Listed here so
    new fabrications break CI while inherited debt does not. Each line in
    the baseline is one failure string verbatim. Empty lines and # comments
    are ignored.
    """
    if not BASELINE_PATH.exists():
        return set()
    out: set[str] = set()
    for raw in BASELINE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line)
    return out


def main() -> int:
    doc_files = _gather(DOC_GLOBS)
    if not doc_files:
        print("ERROR: no doc files found; check DOC_GLOBS configuration", file=sys.stderr)
        return 2

    code_text = _all_code_text()
    if not code_text:
        print("ERROR: no code text collected; check CODE_GLOBS configuration", file=sys.stderr)
        return 2

    all_failures: list[str] = []
    all_failures.extend(check_flags(doc_files, code_text))
    all_failures.extend(check_module_paths(doc_files))
    all_failures.extend(check_constructs(doc_files, code_text))

    # Filter out pre-existing failures the baseline acknowledges
    baseline = _load_baseline()
    new_failures = [f for f in all_failures if f not in baseline]
    deferred = [f for f in all_failures if f in baseline]

    if new_failures:
        print("Doc/code consistency check FAILED:", file=sys.stderr)
        for f in new_failures:
            print(f"  {f}", file=sys.stderr)
        if deferred:
            print(
                f"\n  ({len(deferred)} pre-existing issues deferred via baseline)",
                file=sys.stderr,
            )
        return 1

    print(
        f"Doc/code consistency check PASSED ({len(doc_files)} docs scanned, "
        f"{len(deferred)} deferred via baseline)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
