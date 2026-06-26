#!/usr/bin/env python3
"""Validate the governance normalization map.

Purpose: keep repeated governance doctrine routed to canonical local sources,
validators, tests, and workspace preflight checks.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, docs/GOVERNANCE_NORMALIZATION_MAP.md,
AGENTS.md, canonical governance docs, validators, and tests.
Invariants:
  - Validation is read-only and deterministic.
  - The map does not claim documentation completeness, deployment readiness, or
    public launch readiness.
  - Each mapped governance surface has source, validator, and test artifacts.
  - Mfidel atomicity and no Unicode normalization remain explicit.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAP_PATH = WORKSPACE_ROOT / "docs" / "GOVERNANCE_NORMALIZATION_MAP.md"


@dataclass(frozen=True, slots=True)
class CanonicalSurface:
    """One canonical governance surface that must stay linked."""

    surface_id: str
    source_path: str
    validator_path: str
    test_path: str
    source_anchor: str


@dataclass(frozen=True, slots=True)
class NormalizationFinding:
    """One deterministic governance normalization finding."""

    rule_id: str
    message: str


CANONICAL_SURFACES: tuple[CanonicalSurface, ...] = (
    CanonicalSurface(
        "agents_policy",
        "AGENTS.md",
        "scripts/validate_agents_governance.py",
        "tests/test_validate_agents_governance.py",
        "Use \"symbolic intelligence\" terminology exclusively.",
    ),
    CanonicalSurface(
        "foundation_mode",
        "docs/FOUNDATION_MODE.md",
        "scripts/validate_foundation_mode.py",
        "tests/test_validate_foundation_mode.py",
        "Foundation Mode means the project is being prepared carefully",
    ),
    CanonicalSurface(
        "phi_platform",
        "docs/PHI_CANONICAL_SPEC.md",
        "scripts/validate_phi_gps_v3_platform_spec.py",
        "tests/test_validate_phi_gps_v3_platform_spec.py",
        "Phi2-GPS v3 is accepted as an additive engineering platform",
    ),
    CanonicalSurface(
        "universal_action_orchestration",
        "docs/UNIVERSAL_ACTION_ORCHESTRATION.md",
        "scripts/validate_universal_action_orchestration.py",
        "tests/test_validate_universal_action_orchestration.py",
        "Every canonical UAO record must expose a `life_meaning_judgment`.",
    ),
    CanonicalSurface(
        "mfidel_substrate",
        "docs/85_mfidel_substrate_conformance_receipt_contract.md",
        "scripts/validate_mfidel_substrate_conformance_receipt.py",
        "tests/test_validate_mfidel_substrate_conformance_receipt.py",
        "each fidel is atomic; no Unicode normalization, decomposition, or recomposition is admitted",
    ),
    CanonicalSurface(
        "software_delivery",
        "docs/SDLC.md",
        "scripts/validate_sdlc_artifact.py",
        "tests/test_validate_sdlc_artifact.py",
        "SDLC = UAO for software changes",
    ),
    CanonicalSurface(
        "workspace_preflight",
        "docs/workspace-governance-witness.json",
        "scripts/run_workspace_governance_checks.py",
        "tests/test_run_workspace_governance_checks.py",
        "control_plane_workspace_governance_witness_001",
    ),
)

REQUIRED_MAP_PHRASES: tuple[str, ...] = (
    "Governance Normalization Map",
    "Status: Foundation Mode",
    "The normalization chain is:",
    "operator instruction -> AGENTS.md -> canonical doctrine docs",
    "The purpose is to prevent repeated governance text from becoming multiple",
    "Mfidel text handling remains exact-preservation only",
    "python scripts/validate_governance_normalization_map.py",
    "python scripts/run_workspace_governance_checks.py --check governance_normalization_map",
    "docs/workspace-governance-witness.json",
)

FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("documentation_complete", re.compile(r"\bdocumentation\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("public_launch_ready", re.compile(r"\bpublic\s+launch\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment[- ]ready\b", re.IGNORECASE)),
    ("customer_ready", re.compile(r"\bcustomer\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_clearance_claim", re.compile(r"\blegal\s+clearance\s+(?:is\s+)?complete\b", re.IGNORECASE)),
)


def load_text(path: Path, label: str) -> str:
    """Load one text artifact with explicit path errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def validate_governance_normalization_map(
    map_path: Path = DEFAULT_MAP_PATH,
    surfaces: tuple[CanonicalSurface, ...] = CANONICAL_SURFACES,
) -> list[NormalizationFinding]:
    """Validate the governance normalization map and mapped artifacts."""

    map_text = load_text(map_path, "governance normalization map")
    return [
        *validate_map_text(map_text, surfaces),
        *validate_canonical_surface_artifacts(surfaces),
    ]


def validate_map_text(
    map_text: str,
    surfaces: tuple[CanonicalSurface, ...] = CANONICAL_SURFACES,
) -> list[NormalizationFinding]:
    """Return findings for the normalization map body."""

    findings: list[NormalizationFinding] = []
    for phrase in REQUIRED_MAP_PHRASES:
        if phrase not in map_text:
            findings.append(
                NormalizationFinding(
                    "normalization_map_phrase_missing",
                    f"normalization map missing required phrase: {phrase}",
                )
            )
    for surface in surfaces:
        for value in (surface.surface_id, surface.source_path, surface.validator_path, surface.test_path):
            if value not in map_text:
                findings.append(
                    NormalizationFinding(
                        "normalization_map_surface_missing",
                        f"normalization map missing surface value: {value}",
                    )
                )
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(map_text):
            findings.append(
                NormalizationFinding(
                    "normalization_map_forbidden_promotion",
                    f"normalization map contains forbidden promotion phrase: {rule_id}",
                )
            )
    return findings


def validate_canonical_surface_artifacts(
    surfaces: tuple[CanonicalSurface, ...] = CANONICAL_SURFACES,
) -> list[NormalizationFinding]:
    """Return findings for missing mapped artifacts or source anchors."""

    findings: list[NormalizationFinding] = []
    observed_surface_ids = [surface.surface_id for surface in surfaces]
    if len(set(observed_surface_ids)) != len(observed_surface_ids):
        findings.append(
            NormalizationFinding("normalization_surface_duplicate", "surface ids must be unique")
        )
    for surface in surfaces:
        for label, relative_path in (
            ("source", surface.source_path),
            ("validator", surface.validator_path),
            ("test", surface.test_path),
        ):
            artifact_path = WORKSPACE_ROOT / relative_path
            if not artifact_path.is_file():
                findings.append(
                    NormalizationFinding(
                        "normalization_surface_artifact_missing",
                        f"{surface.surface_id} {label} artifact missing: {relative_path}",
                    )
                )
        source_path = WORKSPACE_ROOT / surface.source_path
        if source_path.is_file():
            source_text = source_path.read_text(encoding="utf-8")
            if surface.source_anchor not in source_text:
                findings.append(
                    NormalizationFinding(
                        "normalization_surface_anchor_missing",
                        f"{surface.surface_id} source anchor missing: {surface.source_anchor}",
                    )
                )
    return findings


def main(argv: list[str] | None = None) -> int:
    """Validate the governance normalization map and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate governance normalization map.")
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_governance_normalization_map(args.map)
    except OSError as exc:
        sys.stderr.write(f"[FAIL] load-normalization-map: {exc}\nSTATUS: failed\n")
        return 1

    if findings:
        for finding in findings:
            sys.stderr.write(f"[FAIL] {finding.rule_id}: {finding.message}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] governance_normalization_map\n")
    sys.stdout.write("[PASS] governance_normalization_sources\n")
    sys.stdout.write("[PASS] governance_normalization_preflight_binding\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
