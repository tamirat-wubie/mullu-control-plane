#!/usr/bin/env python3
"""Validate GitHub App installation token format compatibility.

Purpose: prevent fixed-length assumptions before GitHub App installation tokens
move to the longer stateless ghs_ format.
Governance scope: local repository scan, synthetic fixtures, docs, workflow
configuration, and token-format compatibility guardrails.
Invariants:
  - Validation is read-only.
  - Real tokens are not required and must not be committed.
  - GitHub App installation tokens are treated as opaque strings.
  - Fixed token length, fixed ghs suffix length, JWT parsing, and short storage
    assumptions are blocked.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable


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
REQUIRED_DOC_PHRASES = (
    "Foundation GitHub App Token Format Boundary",
    "tokens are opaque bearer tokens",
    "must not assume a fixed token length",
    "X-GitHub-Stateless-S2S-Token: enabled",
    "minimum_storage_capacity_chars=520",
    "python scripts/validate_github_app_token_format_boundary.py",
)

TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsx",
    ".lock",
    ".md",
    ".mjs",
    ".py",
    ".rst",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
SCAN_DIRS = (".", ".github", "config", "docs", "examples", "mcoi", "scripts", "src", "tests")
SKIP_DIR_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tmp",
    "__pycache__",
    "node_modules",
    "site-packages",
    "venv",
}
SELF_ALLOWED_PATHS = {
    Path("docs/FOUNDATION_GITHUB_APP_TOKEN_FORMAT_BOUNDARY.md"),
    Path("examples/foundation_github_app_token_format_witness.awaiting_evidence.json"),
    Path("scripts/validate_github_app_token_format_boundary.py"),
}

FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "exact_len_40_or_36",
        re.compile(r"\blen\s*\([^\)]*(?:token|github_token|installation_token)[^\)]*\)\s*(?:==|!=|<=|<)\s*(?:36|40)\b", re.IGNORECASE),
    ),
    (
        "javascript_exact_length_40_or_36",
        re.compile(r"\b(?:token|githubToken|installationToken)\s*\.\s*length\s*(?:===|==|!==|!=|<=|<)\s*(?:36|40)\b", re.IGNORECASE),
    ),
    (
        "fixed_ghs_suffix_regex",
        re.compile(r"ghs_\[A-Za-z0-9[_\\\\\]A-Za-z0-9\^\$\-]*\]\{(?:36|40)\}", re.IGNORECASE),
    ),
    (
        "fixed_ghs_dotless_regex",
        re.compile(r"ghs_.*\{(?:36|40)\}.*(?:\$|\\z)", re.IGNORECASE),
    ),
    (
        "short_storage_varchar",
        re.compile(r"\b(?:github_)?(?:app_)?(?:installation_)?token\b[^\n]{0,80}\b(?:varchar|char|string)\s*\(\s*(?:36|40|64|128|255)\s*\)", re.IGNORECASE),
    ),
    (
        "short_schema_max_length",
        re.compile(r"\b(?:github_)?(?:app_)?(?:installation_)?token\b[^\n]{0,160}\bmax(?:imum)?[_-]?length\b\s*[:=]\s*(?:36|40|64|128|255)\b", re.IGNORECASE),
    ),
    (
        "fixed_mask_or_slice_40",
        re.compile(r"\b(?:token|github_token|installation_token)\s*(?:\[\s*:\s*40\s*\]|\.substring\(\s*0\s*,\s*40\s*\)|\.slice\(\s*0\s*,\s*40\s*\))", re.IGNORECASE),
    ),
    (
        "jwt_decode_installation_token",
        re.compile(r"\b(?:jwt|decode_jwt|jwt_decode|jsonwebtoken)\b[^\n]{0,120}\b(?:installation[_-]?token|github[_-]?app[_-]?token|ghs_)\b", re.IGNORECASE),
    ),
)

REAL_TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "possible_real_classic_ghs_token",
        re.compile(r"\bghs_[A-Za-z0-9_]{36}\b"),
    ),
    (
        "possible_real_stateless_ghs_token",
        re.compile(r"\bghs_[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"),
    ),
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic token-format compatibility finding."""

    rule_id: str
    message: str


def load_text(path: Path, label: str) -> str:
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    return path.read_text(encoding="utf-8-sig")


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    payload = json.loads(load_text(path, label))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def repo_relative(path: Path) -> Path:
    return path.resolve().relative_to(REPO_ROOT)


def iter_scannable_files() -> Iterable[Path]:
    seen: set[Path] = set()
    for dirname in SCAN_DIRS:
        root = REPO_ROOT / dirname
        if not root.exists():
            continue
        if root.is_file():
            candidates = (root,)
        else:
            candidates = root.rglob("*")
        for path in candidates:
            if not path.is_file():
                continue
            rel = repo_relative(path)
            if rel in seen:
                continue
            if any(part in SKIP_DIR_PARTS for part in rel.parts):
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"Dockerfile", "Makefile"}:
                continue
            seen.add(rel)
            yield path


def validate_doc(text: str) -> list[Finding]:
    findings: list[Finding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(Finding("github_app_token_doc_phrase_missing", f"missing doc phrase: {phrase}"))
    return findings


def validate_witness(payload: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    expected = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingExternalValidation",
        "github_app_token_format_boundary_state": "ActiveLocalGuard",
        "tokens_are_opaque": True,
        "fixed_length_validation_allowed": False,
        "jwt_parsing_allowed": False,
        "minimum_storage_capacity_chars": 520,
        "real_tokens_committed": False,
        "deployment_allowed": False,
        "stateless_override_header": "X-GitHub-Stateless-S2S-Token",
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            findings.append(Finding("github_app_token_witness_value_invalid", f"{key} must be {value!r}"))
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(Finding("github_app_token_blocked_claims_invalid", "blocked_claims drifted"))
    fixtures = payload.get("synthetic_fixtures")
    if not isinstance(fixtures, dict):
        findings.append(Finding("github_app_token_fixtures_invalid", "synthetic_fixtures must be an object"))
    else:
        classic = fixtures.get("classic_opaque_shape")
        stateless = fixtures.get("stateless_long_shape")
        if not isinstance(classic, str) or not classic.startswith("ghs_"):
            findings.append(Finding("github_app_token_classic_fixture_invalid", "classic fixture must be synthetic and ghs_-shaped"))
        if not isinstance(stateless, str) or not stateless.startswith("ghs_") or "." not in stateless or len(stateless) < 520:
            findings.append(Finding("github_app_token_stateless_fixture_invalid", "stateless fixture must be synthetic, dotted, and at least 520 characters"))
    return findings


def is_self_allowed(rel: Path) -> bool:
    return rel in SELF_ALLOWED_PATHS


def validate_repository_scan() -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_scannable_files():
        rel = repo_relative(path)
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        if not is_self_allowed(rel):
            for rule_id, pattern in FORBIDDEN_PATTERNS:
                if pattern.search(text):
                    findings.append(Finding(rule_id, f"{rel} contains a GitHub App token compatibility risk"))
        for rule_id, pattern in REAL_TOKEN_PATTERNS:
            for match in pattern.finditer(text):
                token = match.group(0)
                if "fixture" in token or "padding" in token:
                    continue
                findings.append(Finding(rule_id, f"{rel} contains a possible real GitHub token-shaped value"))
    return findings


def validate_all(doc_path: Path, witness_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(validate_doc(load_text(doc_path, "GitHub App token format boundary doc")))
    findings.extend(validate_witness(load_json_object(witness_path, "GitHub App token format witness")))
    findings.extend(validate_repository_scan())
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate GitHub App installation token format compatibility guardrails.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    findings = validate_all(args.doc, args.witness)
    if args.json:
        print(json.dumps({"ok": not findings, "findings": [finding.__dict__ for finding in findings]}, indent=2, sort_keys=True))
    elif findings:
        for finding in findings:
            print(f"{finding.rule_id}: {finding.message}", file=sys.stderr)
    else:
        print("GitHub App token format compatibility boundary validated")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
