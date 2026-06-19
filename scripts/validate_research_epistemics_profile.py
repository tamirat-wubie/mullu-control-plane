#!/usr/bin/env python3
"""Validate the WRE-A2 Research Epistemics Profile.

The validator is deterministic and read-only. It proves only the Foundation Mode
contract shape; it grants no research execution, retrieval, synthesis, memory,
truth-mutation, publication, medical, or self-modification authority.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "research_epistemics_profile.schema.json"
DEFAULT_PROFILE_PATH = WORKSPACE_ROOT / "examples" / "research_epistemics_profile.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:research-epistemics-profile:1"
EXPECTED_SCHEMA_TITLE = "WRE-A2 Research Epistemics Profile"
EXPECTED_PROFILE_VERSION = "wre_a2_research_epistemics.v1"

EXPECTED_COMPATIBILITY = {
    "whqr_contract_ref": "mcoi/mcoi_runtime/contracts/whqr.py",
    "claim_verification_ref": "gateway/claim_verification.py",
    "universal_evidence_graph_ref": "mcoi/mcoi_runtime/contracts/universal_evidence_graph.py",
    "research_runtime_ref": "mcoi/mcoi_runtime/contracts/research_runtime.py",
    "memory_mesh_ref": "mcoi/mcoi_runtime/contracts/memory_mesh.py",
    "source_conflict_map_ref": "schemas/research_source_conflict_map.schema.json",
    "truth_kernel_ref": "mcoi/mcoi_runtime/truth_kernel_adapter.py",
}
EXPECTED_CLAIM_TYPES = (
    "empirical",
    "causal",
    "predictive",
    "historical",
    "normative",
    "ontological",
    "symbolic_structural",
)
EXPECTED_DISPOSITIONS = (
    "validated_conclusion",
    "supported_hypothesis",
    "speculative_hypothesis",
    "competing_model",
    "unresolved_contradiction",
    "partial_result",
    "abstention",
    "safety_escalation",
)
EXPECTED_CONFIDENCE_DIMENSIONS = (
    "evidential",
    "logical",
    "provenance",
    "empirical",
    "temporal_applicability",
    "calibration",
    "action_safety",
)
DENIED_AUTHORITY_FIELDS = (
    "runtime_research_execution_allowed",
    "external_retrieval_allowed",
    "connector_calls_allowed",
    "answer_synthesis_authority",
    "memory_write_allowed",
    "truth_mutation_allowed",
    "publication_allowed",
    "medical_decision_authority",
    "autonomous_self_modification_allowed",
)
REQUIRED_EVIDENCE_REFS = (
    "docs/WRE_A2_RESEARCH_EPISTEMICS_PROFILE.md",
    "schemas/research_epistemics_profile.schema.json",
    "examples/research_epistemics_profile.foundation.json",
    "scripts/validate_research_epistemics_profile.py",
    "tests/test_validate_research_epistemics_profile.py",
)


class ResearchEpistemicsProfileError(ValueError):
    """Raised when a profile artifact cannot be loaded."""


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    resolved = path if path.is_absolute() else WORKSPACE_ROOT / path
    if not resolved.is_file():
        raise FileNotFoundError(f"missing {label}: {resolved}")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ResearchEpistemicsProfileError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title is invalid")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    if schema.get("additionalProperties") is not False:
        errors.append("schema root must close additional properties")
    return errors


def validate_research_epistemics_profile_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = list(_validate_schema_instance(schema_payload, record))
    if not isinstance(record, dict):
        return errors + ["research epistemics profile must be a JSON object"]

    if record.get("profile_version") != EXPECTED_PROFILE_VERSION:
        errors.append(f"profile_version must be {EXPECTED_PROFILE_VERSION}")
    if record.get("maturity") != "specified":
        errors.append("maturity must remain specified")
    if record.get("operating_mode") != "foundation_no_effect":
        errors.append("operating_mode must remain foundation_no_effect")

    compatibility = record.get("compatibility")
    if compatibility != EXPECTED_COMPATIBILITY:
        errors.append("compatibility refs must match existing repository substrates")

    epistemic = record.get("epistemic_contract")
    if not isinstance(epistemic, dict):
        errors.append("epistemic_contract must be an object")
    else:
        _require_exact_sequence(epistemic, "claim_types", EXPECTED_CLAIM_TYPES, errors)
        _require_exact_sequence(epistemic, "dispositions", EXPECTED_DISPOSITIONS, errors)
        _require_exact_sequence(
            epistemic,
            "confidence_dimensions",
            EXPECTED_CONFIDENCE_DIMENSIONS,
            errors,
        )
        required_true = (
            "truth_action_separation",
            "contradiction_preservation",
            "abstention_required",
            "source_lineage_required",
        )
        for field_name in required_true:
            if epistemic.get(field_name) is not True:
                errors.append(f"epistemic_contract.{field_name} must be true")
        for field_name in ("scalar_confidence_is_canonical", "truth_kernel_auto_promotion"):
            if epistemic.get(field_name) is not False:
                errors.append(f"epistemic_contract.{field_name} must be false")

    authority = record.get("authority_boundary")
    if not isinstance(authority, dict):
        errors.append("authority_boundary must be an object")
    else:
        for field_name in DENIED_AUTHORITY_FIELDS:
            if authority.get(field_name) is not False:
                errors.append(f"authority_boundary.{field_name} must be false")

    next_gate = record.get("next_gate")
    expected_gate = {
        "prerequisite": "cdg_rccm_pr_1960_green_and_merged",
        "runtime_contracts_allowed": False,
        "operator_review_required": True,
    }
    if next_gate != expected_gate:
        errors.append("next_gate must defer runtime contracts until PR #1960 is green and merged")

    evidence_refs = record.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        errors.append("evidence_refs must be a list")
    else:
        missing = [ref for ref in REQUIRED_EVIDENCE_REFS if ref not in evidence_refs]
        for ref in missing:
            errors.append(f"evidence_refs missing required ref: {ref}")

    return list(dict.fromkeys(errors))


def validate_research_epistemics_profile(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    profile_path: Path = DEFAULT_PROFILE_PATH,
) -> list[str]:
    schema = _load_schema(schema_path)
    profile = load_json_object(profile_path, "WRE-A2 Research Epistemics Profile")
    return validate_schema_artifact(schema) + validate_research_epistemics_profile_record(profile, schema)


def build_mutated_research_epistemics_profile(**updates: Any) -> dict[str, Any]:
    profile = deepcopy(load_json_object(DEFAULT_PROFILE_PATH, "WRE-A2 Research Epistemics Profile"))
    for dotted_key, value in updates.items():
        target: Any = profile
        parts = dotted_key.split("__")
        for part in parts[:-1]:
            target = target[int(part)] if isinstance(target, list) else target[part]
        final = parts[-1]
        if isinstance(target, list):
            target[int(final)] = value
        else:
            target[final] = value
    return profile


def _require_exact_sequence(
    container: dict[str, Any],
    field_name: str,
    expected: tuple[str, ...],
    errors: list[str],
) -> None:
    value = container.get(field_name)
    if not isinstance(value, list) or tuple(value) != expected:
        errors.append(f"epistemic_contract.{field_name} must match the canonical sequence")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors = validate_research_epistemics_profile(args.schema, args.profile)
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[PASS] research_epistemics_profile")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
