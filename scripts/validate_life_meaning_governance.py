#!/usr/bin/env python3
"""Validate the Mullu Life-Meaning Governance Kernel surface.

Purpose: verify doctrine docs, schema, examples, runtime kernel parity, and
Foundation Mode claim boundaries for LifeMeaningJudgment.
Governance scope: OCE completeness, RAG doctrine-to-runtime binding, CDCV
kernel decision causality, CQTE decidable examples, UWMA evidence references,
and PRS validation reporting.
Dependencies: Python standard library, scripts.validate_schemas, and
mcoi_runtime life-meaning contracts.
Invariants:
  - Required docs, schema, examples, contract, and kernel exist.
  - Examples validate against schemas/life_meaning_judgment.schema.json.
  - Runtime kernel decisions match canonical examples.
  - Unknown life with irreversible action escalates.
  - Finance examples do not claim live payment execution.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MCOI_ROOT = REPO_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from mcoi_runtime.contracts.life_meaning import (  # noqa: E402
    AffectedSymbol,
    BoundaryState,
    Delta,
    ImpactLevel,
)
from mcoi_runtime.core.life_meaning_governance import judge_life_meaning  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


SCHEMA_PATH = REPO_ROOT / "schemas" / "life_meaning_judgment.schema.json"
AGENTS_PATH = REPO_ROOT / "AGENTS.md"
DOC_PATHS = (
    REPO_ROOT / "docs" / "UNIVERSAL_SYMBOL_CONTINUITY_DOCTRINE.md",
    REPO_ROOT / "docs" / "MEANING_THROUGH_FEELING_THEORY.md",
    REPO_ROOT / "docs" / "LIFE_MEANING_GOVERNANCE_KERNEL.md",
    REPO_ROOT / "docs" / "CODEX_LIFE_MEANING_GOVERNANCE_NOTICE.md",
)
RUNTIME_PATHS = (
    REPO_ROOT / "mcoi" / "mcoi_runtime" / "contracts" / "life_meaning.py",
    REPO_ROOT / "mcoi" / "mcoi_runtime" / "core" / "life_meaning_governance.py",
)
EXAMPLE_PATHS = (
    REPO_ROOT / "examples" / "life_meaning_judgment.local_proof.json",
    REPO_ROOT / "examples" / "life_meaning_judgment.finance_payment.json",
    REPO_ROOT / "examples" / "life_meaning_judgment.deployment.json",
    REPO_ROOT / "examples" / "life_meaning_judgment.unknown_life_environment.json",
)
REQUIRED_AGENTS_TERMS = (
    "## Life-Meaning Governance",
    "Effect-bearing work must consider affected symbols",
    "Where impact is unknown and action is irreversible",
    "not automatically classified as life or feeling observers",
)
REQUIRED_DOC_TERMS = (
    "Mullu Life-Meaning Governance Kernel",
    "Meaning-Through-Feeling Theory",
    "Universal Symbol Continuity Doctrine",
    "LifeMeaningJudgment",
    "Expansion never outranks life safety",
)
PROHIBITED_UNBOUNDED_CLAIMS = (
    "life-safe certified",
    "deployment ready",
    "customer ready",
    "production ethical readiness achieved",
    "legal clearance achieved",
    "expansion ready",
)
PROHIBITED_FINANCE_PAYMENT_CLAIMS = (
    "live payment executed",
    "bank settlement completed",
    "payment sent",
    "autonomous payment execution",
)


@dataclass(frozen=True, slots=True)
class LifeMeaningGovernanceValidation:
    """Validation result for the Life-Meaning Governance Kernel surface."""

    ok: bool
    errors: tuple[str, ...]


def validate_life_meaning_governance() -> LifeMeaningGovernanceValidation:
    """Return validation result for the life-meaning governance artifacts."""

    errors: list[str] = []
    schema = _load_json_object(SCHEMA_PATH, "life-meaning judgment schema", errors)
    for path in (*DOC_PATHS, *RUNTIME_PATHS):
        if not path.is_file():
            errors.append(f"missing required artifact: {_rel(path)}")
    if not AGENTS_PATH.is_file():
        errors.append("missing required artifact: AGENTS.md")

    if schema:
        _validate_schema_contract(schema, errors)
        for example_path in EXAMPLE_PATHS:
            example = _load_json_object(example_path, "life-meaning example", errors)
            if example:
                errors.extend(
                    f"{_rel(example_path)}: {error}"
                    for error in _validate_schema_instance(schema, example)
                )
                _validate_example_kernel_parity(example_path, example, errors)
    else:
        for example_path in EXAMPLE_PATHS:
            if not example_path.is_file():
                errors.append(f"missing required artifact: {_rel(example_path)}")

    _validate_agents_notice(errors)
    _validate_doc_terms_and_claims(errors)
    _validate_example_semantics(errors)
    return LifeMeaningGovernanceValidation(ok=not errors, errors=tuple(errors))


def _validate_schema_contract(schema: dict[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:life-meaning-judgment:1":
        errors.append("life-meaning judgment schema $id is invalid")
    if schema.get("title") != "LifeMeaningJudgment":
        errors.append("life-meaning judgment schema title is invalid")
    required = schema.get("required", [])
    for field_name in (
        "judgment_id",
        "action_id",
        "decision",
        "affected_symbols",
        "life_impact",
        "feeling_impact",
        "meaning_impact",
        "truth_preserved",
        "dignity_boundary",
        "consent_required",
        "consent_present",
        "love_delta",
        "resonance_delta",
        "domination_risk",
        "justice_repair_required",
        "continuity_delta",
        "irreversible",
        "reasons",
        "evidence_refs",
        "approval_required",
        "rollback_required",
    ):
        if field_name not in required:
            errors.append(f"life-meaning judgment schema missing required field: {field_name}")


def _validate_agents_notice(errors: list[str]) -> None:
    if not AGENTS_PATH.is_file():
        return
    agents_text = AGENTS_PATH.read_text(encoding="utf-8")
    for required_term in REQUIRED_AGENTS_TERMS:
        if required_term not in agents_text:
            errors.append(f"AGENTS.md missing Life-Meaning Governance term: {required_term}")


def _validate_doc_terms_and_claims(errors: list[str]) -> None:
    combined_text = ""
    for doc_path in DOC_PATHS:
        if doc_path.is_file():
            combined_text += "\n" + doc_path.read_text(encoding="utf-8")
    for required_term in REQUIRED_DOC_TERMS:
        if required_term not in combined_text:
            errors.append(f"life-meaning doctrine missing required term: {required_term}")
    lowered = combined_text.lower()
    for prohibited_claim in PROHIBITED_UNBOUNDED_CLAIMS:
        if prohibited_claim in lowered:
            errors.append(f"life-meaning doctrine contains unbounded claim: {prohibited_claim}")


def _validate_example_semantics(errors: list[str]) -> None:
    local_proof = _load_json_object(
        REPO_ROOT / "examples" / "life_meaning_judgment.local_proof.json",
        "local proof life-meaning example",
        errors,
    )
    if local_proof and local_proof.get("decision") != "pass":
        errors.append("local proof life-meaning example must pass")

    unknown_environment = _load_json_object(
        REPO_ROOT / "examples" / "life_meaning_judgment.unknown_life_environment.json",
        "unknown life environment example",
        errors,
    )
    if unknown_environment:
        if unknown_environment.get("decision") != "escalate":
            errors.append("unknown life irreversible example must escalate")
        if unknown_environment.get("irreversible") is not True:
            errors.append("unknown life environment example must be irreversible")
        if unknown_environment.get("life_impact") != "unknown":
            errors.append("unknown life environment example must keep life impact unknown")

    finance_payment = _load_json_object(
        REPO_ROOT / "examples" / "life_meaning_judgment.finance_payment.json",
        "finance payment life-meaning example",
        errors,
    )
    if finance_payment:
        finance_text = json.dumps(finance_payment, sort_keys=True).lower()
        for prohibited_claim in PROHIBITED_FINANCE_PAYMENT_CLAIMS:
            if prohibited_claim in finance_text:
                errors.append(f"finance payment example claims live payment: {prohibited_claim}")


def _validate_example_kernel_parity(
    example_path: Path,
    example: dict[str, Any],
    errors: list[str],
) -> None:
    try:
        judgment = judge_life_meaning(
            action_id=str(example["action_id"]),
            affected_symbols=tuple(
                AffectedSymbol(
                    symbol_id=str(symbol["symbol_id"]),
                    symbol_kind=str(symbol["symbol_kind"]),
                    life_status=str(symbol["life_status"]),
                    feeling_status=str(symbol["feeling_status"]),
                    meaning_bearing=str(symbol["meaning_bearing"]),
                    fragility_level=int(symbol["fragility_level"]),
                    agency_level=int(symbol["agency_level"]),
                )
                for symbol in example["affected_symbols"]
            ),
            life_impact=ImpactLevel(str(example["life_impact"])),
            feeling_impact=ImpactLevel(str(example["feeling_impact"])),
            meaning_impact=ImpactLevel(str(example["meaning_impact"])),
            truth_preserved=example["truth_preserved"] is True,
            dignity_boundary=BoundaryState(str(example["dignity_boundary"])),
            consent_present=example["consent_present"] is True,
            love_delta=Delta(str(example["love_delta"])),
            resonance_delta=Delta(str(example["resonance_delta"])),
            domination_risk=example["domination_risk"] is True,
            continuity_delta=Delta(str(example["continuity_delta"])),
            irreversible=example["irreversible"] is True,
            evidence_refs=tuple(str(ref) for ref in example["evidence_refs"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"{_rel(example_path)} failed kernel parity construction: {exc}")
        return

    generated = judgment.as_dict()
    for field_name in (
        "decision",
        "consent_required",
        "approval_required",
        "rollback_required",
        "justice_repair_required",
    ):
        if generated[field_name] != example.get(field_name):
            errors.append(
                f"{_rel(example_path)} {field_name} drifted from deterministic kernel: "
                f"expected={generated[field_name]!r} observed={example.get(field_name)!r}"
            )
    if tuple(generated["reasons"]) != tuple(example.get("reasons", [])):
        errors.append(f"{_rel(example_path)} reasons drifted from deterministic kernel")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"missing {label}: {_rel(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{_rel(path)} is invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{_rel(path)} must contain a JSON object")
        return {}
    return payload


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON validation result")
    args = parser.parse_args(argv)

    validation = validate_life_meaning_governance()
    if args.json:
        print(
            json.dumps(
                {"ok": validation.ok, "errors": list(validation.errors)},
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for error in validation.errors:
            print(f"[FAIL] {error}")
        print("STATUS: passed" if validation.ok else "STATUS: failed")
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
