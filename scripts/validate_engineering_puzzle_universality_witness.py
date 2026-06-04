#!/usr/bin/env python3
"""Validate the engineering puzzle empirical universality witness set.

Purpose: replay governed witness cases for the engineering puzzle rule that
survival must block optimization when L2 fails.
Governance scope: local witness validation for the engineering-puzzle kernel
only; no live provider or external engineering claim is made.
Dependencies: examples/engineering_puzzle_universality_witness_set.json and
mcoi_runtime engineering puzzle contracts.
Invariants: every witness case is explicit, every replay stops at L2_survival,
L5_optimization is not evaluated after failed survival, and failures are
reported with bounded causal context.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = REPO_ROOT / "mcoi"
DEFAULT_WITNESS_PATH = REPO_ROOT / "examples" / "engineering_puzzle_universality_witness_set.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / ".change_assurance" / "engineering_puzzle_universality_witness.json"
MINIMUM_CASE_COUNT = 5
EXPECTED_CLAIM = "survival_before_optimization_universality"
EXPECTED_KERNEL_RULE = "not Pass(L2_survival) => Block(L5_optimization)"
EXPECTED_VERDICT = "SafeHalt"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from mcoi_runtime.contracts.engineering_puzzle import (  # noqa: E402
    CandidateArrangement,
    FILTER_STACK_LEVELS,
    FilterLevel,
)
from mcoi_runtime.core.engineering_puzzle_kernel import evaluate_filter_stack  # noqa: E402


@dataclass(frozen=True, slots=True)
class UniversalityWitnessValidation:
    """Validation report for the engineering puzzle universality witness set."""

    witness_path: str
    passed: bool
    case_count: int
    domains: tuple[str, ...]
    report_hash: str
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "governed": True,
            "witness_path": self.witness_path,
            "passed": self.passed,
            "case_count": self.case_count,
            "domains": list(self.domains),
            "report_hash": self.report_hash,
            "errors": list(self.errors),
        }


def validate_witness_set(
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> UniversalityWitnessValidation:
    """Validate one engineering puzzle universality witness set."""

    errors: list[str] = []
    payload = _load_json_object(witness_path, errors)
    cases = payload.get("cases", []) if isinstance(payload, Mapping) else []
    domains: tuple[str, ...] = ()

    if isinstance(payload, Mapping):
        errors.extend(_validate_root_contract(payload))
    if not isinstance(cases, list):
        errors.append("cases must be a list")
        cases = []

    domains_seen: set[str] = set()
    case_ids_seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            errors.append(f"cases[{index}] must be an object")
            continue
        case_id = _text(case, "case_id")
        domain = _text(case, "domain")
        if case_id in case_ids_seen:
            errors.append(f"{case_id}: duplicate case_id")
        if domain in domains_seen:
            errors.append(f"{case_id}: duplicate domain {domain}")
        if case_id:
            case_ids_seen.add(case_id)
        if domain:
            domains_seen.add(domain)
        errors.extend(_validate_case_contract(case, index))
        errors.extend(_replay_case(case, index))

    if len(cases) < MINIMUM_CASE_COUNT:
        errors.append(f"case_count below floor: {len(cases)} < {MINIMUM_CASE_COUNT}")

    domains = tuple(sorted(domains_seen))
    report_seed = {
        "witness_hash": _stable_hash(payload) if isinstance(payload, Mapping) else "",
        "case_count": len(cases),
        "domains": list(domains),
        "errors": sorted(errors),
    }
    return UniversalityWitnessValidation(
        witness_path=str(witness_path),
        passed=not errors,
        case_count=len(cases),
        domains=domains,
        report_hash=_stable_hash(report_seed),
        errors=tuple(errors),
    )


def write_report(path: Path, report: UniversalityWitnessValidation) -> None:
    """Write a deterministic validation report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json_object(path: Path, errors: list[str]) -> Mapping[str, Any]:
    if not path.exists():
        errors.append(f"missing witness set: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON at {path}: {exc.msg}")
        return {}
    if not isinstance(payload, Mapping):
        errors.append("witness root must be an object")
        return {}
    return payload


def _validate_root_contract(payload: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if payload.get("governed") is not True:
        errors.append("governed must be true")
    if _text(payload, "witness_set_id") != "engineering-puzzle-universality-witness-set.v1":
        errors.append("witness_set_id mismatch")
    if payload.get("claim") != EXPECTED_CLAIM:
        errors.append(f"claim must be {EXPECTED_CLAIM}")
    if payload.get("kernel_rule") != EXPECTED_KERNEL_RULE:
        errors.append("kernel_rule mismatch")
    source_refs = payload.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs:
        errors.append("source_refs must be a non-empty list")
    else:
        required_refs = {
            "docs/ENGINEERING_PUZZLE_KERNEL.md",
            "mcoi/mcoi_runtime/contracts/engineering_puzzle.py",
            "mcoi/mcoi_runtime/core/engineering_puzzle_kernel.py",
        }
        missing = sorted(required_refs - {str(item) for item in source_refs})
        if missing:
            errors.append(f"source_refs missing required refs: {missing}")
    return tuple(errors)


def _validate_case_contract(case: Mapping[str, Any], index: int) -> tuple[str, ...]:
    errors: list[str] = []
    case_ref = _case_ref(case, index)
    for field_name in (
        "case_id",
        "domain",
        "scenario",
        "survival_guard",
        "optimization_candidate",
    ):
        if not _text(case, field_name):
            errors.append(f"{case_ref}: {field_name} must be non-empty text")
    if case.get("expected_failed_level") != FilterLevel.L2_SURVIVAL.value:
        errors.append(f"{case_ref}: expected_failed_level must be {FilterLevel.L2_SURVIVAL.value}")
    if case.get("expected_optimization_blocked") is not True:
        errors.append(f"{case_ref}: expected_optimization_blocked must be true")
    if case.get("expected_verdict") != EXPECTED_VERDICT:
        errors.append(f"{case_ref}: expected_verdict must be {EXPECTED_VERDICT}")
    for field_name in ("model_evidence", "observation_evidence"):
        value = case.get(field_name)
        if not isinstance(value, list) or not value or not all(_non_empty_text(item) for item in value):
            errors.append(f"{case_ref}: {field_name} must be a non-empty text list")
    return tuple(errors)


def _replay_case(case: Mapping[str, Any], index: int) -> tuple[str, ...]:
    case_ref = _case_ref(case, index)
    candidate = CandidateArrangement(
        candidate_id=_text(case, "case_id") or f"case-{index}",
        state_delta={
            "domain": _text(case, "domain"),
            "optimization_candidate": _text(case, "optimization_candidate"),
        },
        filter_results={
            level: level is not FilterLevel.L2_SURVIVAL
            for level in FILTER_STACK_LEVELS
        },
        confidence=0.9,
        authority_ref="Phi_gov:engineering-puzzle-universality-witness",
        governance_certified=True,
        rollback_plan="preserve prior puzzle state when survival proof is absent",
        verification_plan="replay filter stack and assert L5_optimization is not evaluated",
        assumptions=("universality witness replay uses local deterministic filter stack",),
        unknowns=(),
        rejected_alternatives=("evaluate optimization after failed survival",),
        fragile=False,
        witness=None,
    )
    result = evaluate_filter_stack(candidate)
    errors: list[str] = []
    if result.passed is not False:
        errors.append(f"{case_ref}: replay unexpectedly passed")
    if result.failed_level != FilterLevel.L2_SURVIVAL:
        errors.append(f"{case_ref}: replay failed at {result.failed_level}, expected L2_survival")
    if FilterLevel.L5_OPTIMIZATION in result.evaluated_levels:
        errors.append(f"{case_ref}: replay evaluated L5_optimization after L2_survival failed")
    if tuple(result.evaluated_levels) != (
        FilterLevel.L0_FEASIBILITY,
        FilterLevel.L1_IDENTITY,
        FilterLevel.L2_SURVIVAL,
    ):
        errors.append(f"{case_ref}: replay evaluated unexpected filter prefix")
    return tuple(errors)


def _case_ref(case: Mapping[str, Any], index: int) -> str:
    return _text(case, "case_id") or f"cases[{index}]"


def _text(mapping: Mapping[str, Any], field_name: str) -> str:
    value = mapping.get(field_name)
    return value.strip() if isinstance(value, str) else ""


def _non_empty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _stable_hash(document: object) -> str:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{sha256(encoded.encode('utf-8')).hexdigest()}"


def main() -> int:
    """CLI entry point for engineering puzzle universality witness validation."""

    parser = argparse.ArgumentParser(
        description="Validate the engineering puzzle universality witness set.",
    )
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    report = validate_witness_set(args.witness)
    write_report(args.output, report)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
