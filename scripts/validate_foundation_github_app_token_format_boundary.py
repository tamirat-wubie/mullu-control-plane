#!/usr/bin/env python3
"""Validate the Foundation Mode GitHub App token-format boundary.

Purpose: keep GitHub App installation token handling compatible with opaque,
long, dot-containing ``ghs_`` tokens without storing live credentials.
Governance scope: GitHub App installation token assumptions, synthetic fixture
shape, repository scanner coverage, external-validation deferral, and
deployment blocking.
Dependencies: docs/FOUNDATION_GITHUB_APP_TOKEN_FORMAT_BOUNDARY.md and
examples/foundation_github_app_token_format_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - GitHub App installation tokens are opaque bearer strings.
  - Fixed token length, fixed suffix length, JWT parsing, short storage,
    committed real tokens, and deployment readiness remain blocked.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_GITHUB_APP_TOKEN_FORMAT_BOUNDARY.md"
DEFAULT_WITNESS_PATH = REPO_ROOT / "examples" / "foundation_github_app_token_format_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_github_app_token_format_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "fixed GitHub App installation token length",
    "fixed ghs suffix length",
    "JWT parsing of GitHub App installation tokens",
    "short token storage capacity",
    "real token fixture committed",
    "deployment readiness",
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "deployment_allowed",
    "fixed_length_validation_allowed",
    "github_app_token_format_boundary_state",
    "jwt_parsing_allowed",
    "minimum_storage_capacity_chars",
    "next_action",
    "real_tokens_committed",
    "schema_version",
    "solver_outcome",
    "stateless_override_header",
    "status",
    "synthetic_fixtures",
    "tokens_are_opaque",
    "witness_id",
}
EXPECTED_SYNTHETIC_KEYS = {
    "classic_opaque_shape",
    "stateless_long_shape",
}
REQUIRED_DOC_PHRASES = (
    "Foundation GitHub App Token Format Boundary",
    "GitHub App installation tokens are opaque bearer tokens.",
    "Witness packet: [`../examples/foundation_github_app_token_format_witness.awaiting_evidence.json`]",
    "Do not require `len(token) == 40`, `len(token) == 36`, or any other exact length.",
    "Do not reject dot separators inside a `ghs_` token.",
    "Do not parse GitHub App installation tokens as JWTs",
    "minimum_storage_capacity_chars=520",
    "real_tokens_committed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_github_app_token_format_boundary.py",
)
SCANNED_SUFFIXES = {
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
SCAN_EXCLUDED_PATHS = {
    Path("docs/FOUNDATION_GITHUB_APP_TOKEN_FORMAT_BOUNDARY.md"),
    Path("examples/foundation_github_app_token_format_witness.awaiting_evidence.json"),
    Path("scripts/validate_foundation_github_app_token_format_boundary.py"),
    Path("tests/test_validate_foundation_github_app_token_format_boundary.py"),
}
SCAN_EXCLUDED_PARTS = {
    ".claude",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".tmp",
    ".worktrees",
    "__pycache__",
    "mullu-control-plane",
    "mullu-control-plane-runtime-execution-mode-20260606",
    "node_modules",
}
SCAN_EXCLUDED_PREFIXES = (
    "mullu-control-plane-",
)
FORBIDDEN_SCAN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("fixed_ghs_suffix_regex", re.compile(r"ghs_[^\n]{0,24}\{(?:36|40)\}", re.IGNORECASE)),
    ("exact_ghs_fixture", re.compile(r"ghs_[A-Za-z0-9]{36}(?![A-Za-z0-9])")),
    ("short_storage_capacity", re.compile(r"github[^\n]{0,48}(?:token|installation)[^\n]{0,48}(?:varchar|char)\((?:36|40|255)\)", re.IGNORECASE)),
    ("fixed_token_length_check", re.compile(r"len\([^\n]*(?:token|github_app)[^\n]*\)\s*==\s*(?:36|40)", re.IGNORECASE)),
    ("installation_token_jwt_parse", re.compile(r"(?:jwt\.decode|parse_jwt|JWTAuthenticator)[^\n]{0,80}(?:ghs_|installation token|github app)", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class TokenFormatFinding:
    """One deterministic GitHub App token-format validation finding."""

    rule_id: str
    message: str


def load_text(path: Path, label: str) -> str:
    """Load one text artifact with explicit path errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit path and type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_doc_text(text: str) -> list[TokenFormatFinding]:
    """Return findings for missing GitHub App token-format documentation anchors."""

    findings: list[TokenFormatFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                TokenFormatFinding(
                    "github_app_token_format_doc_phrase_missing",
                    f"GitHub App token-format boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_witness(payload: dict[str, Any]) -> list[TokenFormatFinding]:
    """Return findings for GitHub App token-format witness drift."""

    findings: list[TokenFormatFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            TokenFormatFinding(
                "github_app_token_format_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "github_app_token_format_boundary_state": "ActiveLocalGuard",
        "tokens_are_opaque": True,
        "fixed_length_validation_allowed": False,
        "jwt_parsing_allowed": False,
        "minimum_storage_capacity_chars": 520,
        "real_tokens_committed": False,
        "deployment_allowed": False,
        "stateless_override_header": "X-GitHub-Stateless-S2S-Token",
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                TokenFormatFinding(
                    "github_app_token_format_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            TokenFormatFinding(
                "github_app_token_format_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "outside Git" not in next_action:
        findings.append(
            TokenFormatFinding(
                "github_app_token_format_next_action_invalid",
                "next_action must keep live token validation outside Git",
            )
        )
    findings.extend(validate_synthetic_fixtures(payload.get("synthetic_fixtures")))
    return findings


def validate_synthetic_fixtures(fixtures: object) -> list[TokenFormatFinding]:
    """Return findings for synthetic token fixture drift."""

    findings: list[TokenFormatFinding] = []
    if not isinstance(fixtures, dict):
        return [
            TokenFormatFinding(
                "github_app_token_format_fixtures_invalid",
                "synthetic_fixtures must be an object",
            )
        ]
    if set(fixtures) != EXPECTED_SYNTHETIC_KEYS:
        findings.append(
            TokenFormatFinding(
                "github_app_token_format_fixture_keys_invalid",
                f"synthetic_fixtures keys must be: {', '.join(sorted(EXPECTED_SYNTHETIC_KEYS))}",
            )
        )
    classic = fixtures.get("classic_opaque_shape")
    stateless = fixtures.get("stateless_long_shape")
    if not isinstance(classic, str) or not classic.startswith("ghs_") or "." in classic:
        findings.append(
            TokenFormatFinding(
                "github_app_token_format_classic_fixture_invalid",
                "classic_opaque_shape must be a synthetic opaque ghs_ string without dot separators",
            )
        )
    if not isinstance(stateless, str) or not stateless.startswith("ghs_") or "." not in stateless:
        findings.append(
            TokenFormatFinding(
                "github_app_token_format_stateless_fixture_invalid",
                "stateless_long_shape must be a synthetic ghs_ string with dot separators",
            )
        )
    elif len(stateless) < 520:
        findings.append(
            TokenFormatFinding(
                "github_app_token_format_stateless_fixture_too_short",
                "stateless_long_shape must prove support for at least 520 characters",
            )
        )
    return findings


def iter_scannable_files(repo_root: Path) -> list[Path]:
    """Return repository files eligible for token-format assumption scanning."""

    paths: list[Path] = []
    pending = [repo_root]
    while pending:
        current = pending.pop()
        try:
            children = tuple(current.iterdir())
        except OSError:
            continue
        for path in children:
            relative_path = path.relative_to(repo_root)
            if path.is_dir():
                if _skip_scan_directory(path, relative_path, repo_root):
                    continue
                pending.append(path)
                continue
            if not path.is_file():
                continue
            if any(part in SCAN_EXCLUDED_PARTS for part in relative_path.parts):
                continue
            if relative_path in SCAN_EXCLUDED_PATHS:
                continue
            if path.suffix.lower() not in SCANNED_SUFFIXES:
                continue
            paths.append(path)
    return sorted(paths)


def _skip_scan_directory(path: Path, relative_path: Path, repo_root: Path) -> bool:
    """Return whether a directory is outside this repository scan boundary."""

    if any(part in SCAN_EXCLUDED_PARTS for part in relative_path.parts):
        return True
    if any(part.startswith(SCAN_EXCLUDED_PREFIXES) for part in relative_path.parts):
        return True
    if path != repo_root and (path / ".git").exists():
        return True
    if path != repo_root and (path / ".git").is_file():
        return True
    return False


def validate_repository_scan(repo_root: Path = REPO_ROOT) -> list[TokenFormatFinding]:
    """Return findings for obvious fixed-length GitHub App token assumptions."""

    findings: list[TokenFormatFinding] = []
    for path in iter_scannable_files(repo_root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not _line_mentions_github_app_token_surface(line):
                continue
            for pattern_id, pattern in FORBIDDEN_SCAN_PATTERNS:
                if pattern.search(line):
                    relative_path = path.relative_to(repo_root).as_posix()
                    findings.append(
                        TokenFormatFinding(
                            "github_app_token_format_forbidden_repository_pattern",
                            f"{relative_path}:{line_number} contains forbidden {pattern_id}",
                        )
                    )
    return findings


def _line_mentions_github_app_token_surface(line: str) -> bool:
    lowered = line.lower()
    return "ghs_" in lowered or "github app" in lowered or "installation token" in lowered


def validate_foundation_github_app_token_format_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
    repo_root: Path = REPO_ROOT,
) -> list[TokenFormatFinding]:
    """Validate GitHub App token-format boundary artifacts and repository scan."""

    doc_text = load_text(doc_path, "GitHub App token-format boundary doc")
    witness_payload = load_json_object(witness_path, "GitHub App token-format witness")
    return [
        *validate_doc_text(doc_text),
        *validate_witness(witness_payload),
        *validate_repository_scan(repo_root),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate GitHub App token-format boundary artifacts and print status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode GitHub App token-format boundary.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_github_app_token_format_boundary(args.doc, args.witness, args.repo_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_github_app_token_format_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_github_app_token_format_doc")
    print("[PASS] foundation_github_app_token_format_witness")
    print("[PASS] foundation_github_app_token_format_repository_scan")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
