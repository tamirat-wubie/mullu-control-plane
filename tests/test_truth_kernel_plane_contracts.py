"""Verify the Mullu Truth Kernel contract surface.

Purpose: keep MTK schemas, examples, and documentation aligned.
Governance scope: OCE field completeness, RAG schema-example-doc linkage, CDCV
truth mutation causality, CQTE exact-result boundary, and Mfidel atomicity.
Dependencies: jsonschema, MTK schemas, MTK examples, and docs/74_truth_kernel_plane.md.
Invariants: approximate or bounded outputs cannot mutate truth, and Mfidel
symbols remain atomic when present.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = WORKSPACE_ROOT / "schemas"
EXAMPLE_DIR = WORKSPACE_ROOT / "examples" / "truth_kernel"
DOCUMENT_PATH = WORKSPACE_ROOT / "docs" / "74_truth_kernel_plane.md"

TRUTH_CANDIDATE_SCHEMA_PATH = SCHEMA_DIR / "truth_candidate.schema.json"
KERNEL_PROOF_SCHEMA_PATH = SCHEMA_DIR / "kernel_proof.schema.json"
TRUTH_COMMIT_SCHEMA_PATH = SCHEMA_DIR / "truth_commit_candidate.schema.json"

TRUTH_CANDIDATE_EXAMPLE_PATH = (
    EXAMPLE_DIR / "truth_candidate.exact_constraint_addition.json"
)
KERNEL_PROOF_EXAMPLE_PATH = EXAMPLE_DIR / "kernel_proof.exact_projection.json"
RUST_KERNEL_PROOF_EXAMPLE_PATH = (
    EXAMPLE_DIR / "kernel_proof.rust_finite_projection.json"
)
TRUTH_COMMIT_EXAMPLE_PATH = (
    EXAMPLE_DIR / "truth_commit_candidate.exact_constraint_addition.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(path: Path) -> Draft202012Validator:
    schema = _load_json(path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_truth_kernel_schema_files_are_valid_and_named() -> None:
    schema_paths = (
        TRUTH_CANDIDATE_SCHEMA_PATH,
        KERNEL_PROOF_SCHEMA_PATH,
        TRUTH_COMMIT_SCHEMA_PATH,
    )

    schemas = [_load_json(path) for path in schema_paths]

    assert all(path.exists() for path in schema_paths)
    assert [schema["title"] for schema in schemas] == [
        "Mullu Truth Kernel Truth Candidate",
        "Mullu Truth Kernel Proof",
        "Mullu Truth Kernel Truth Commit Candidate",
    ]
    assert all(schema["$schema"].endswith("draft/2020-12/schema") for schema in schemas)
    assert all(schema["additionalProperties"] is False for schema in schemas)


def test_truth_kernel_examples_validate_against_schemas() -> None:
    pairs = (
        (TRUTH_CANDIDATE_SCHEMA_PATH, TRUTH_CANDIDATE_EXAMPLE_PATH),
        (KERNEL_PROOF_SCHEMA_PATH, KERNEL_PROOF_EXAMPLE_PATH),
        (TRUTH_COMMIT_SCHEMA_PATH, TRUTH_COMMIT_EXAMPLE_PATH),
    )

    for schema_path, example_path in pairs:
        _validator(schema_path).validate(_load_json(example_path))

    assert len(pairs) == 3
    assert all(example_path.exists() for _, example_path in pairs)
    assert all(_load_json(example_path) for _, example_path in pairs)


def test_truth_candidate_requires_mfidel_atomicity_when_mfidel_is_present() -> None:
    candidate = _load_json(TRUTH_CANDIDATE_EXAMPLE_PATH)
    invalid_candidate = copy.deepcopy(candidate)
    invalid_candidate["delta"]["includes_mfidel"] = True
    invalid_candidate["delta"]["mfidel_atomicity_preserved"] = False

    validator = _validator(TRUTH_CANDIDATE_SCHEMA_PATH)

    validator.validate(candidate)
    try:
        validator.validate(invalid_candidate)
    except ValidationError as exc:
        assert "True was expected" in exc.message
        assert list(exc.absolute_path)[-1] == "mfidel_atomicity_preserved"
        assert invalid_candidate["delta"]["includes_mfidel"] is True
    else:
        raise AssertionError("Mfidel-bearing truth candidate must preserve atomicity")


def test_kernel_proof_requires_exact_pass_for_truth_mutation_support() -> None:
    proof = _load_json(KERNEL_PROOF_EXAMPLE_PATH)
    invalid_proof = copy.deepcopy(proof)
    invalid_proof["result_kind"] = "ApproximateResult"

    validator = _validator(KERNEL_PROOF_SCHEMA_PATH)

    validator.validate(proof)
    try:
        validator.validate(invalid_proof)
    except ValidationError as exc:
        assert "'ExactResult' was expected" in exc.message
        assert invalid_proof["conclusion"]["supports_truth_mutation"] is True
        assert invalid_proof["proof_state"] == "Pass"
    else:
        raise AssertionError("Truth-mutation proof support requires ExactResult")


def test_rust_emitted_kernel_proof_fixture_validates_against_schema() -> None:
    proof = _load_json(RUST_KERNEL_PROOF_EXAMPLE_PATH)

    _validator(KERNEL_PROOF_SCHEMA_PATH).validate(proof)

    assert proof["proof_kind"] == "ProjectionProof"
    assert proof["proof_state"] == "Pass"
    assert proof["result_kind"] == "ExactResult"
    assert proof["conclusion"]["supports_truth_mutation"] is True
    assert "witness:sandbox-isolated" in proof["witness_refs"]
    assert proof["replay"]["deterministic"] is True


def test_truth_commit_requires_exact_pass_before_mutation() -> None:
    commit_candidate = _load_json(TRUTH_COMMIT_EXAMPLE_PATH)
    invalid_commit = copy.deepcopy(commit_candidate)
    invalid_commit["truth_admission"]["result_kind"] = "BoundedResult"

    validator = _validator(TRUTH_COMMIT_SCHEMA_PATH)

    validator.validate(commit_candidate)
    try:
        validator.validate(invalid_commit)
    except ValidationError as exc:
        assert "'ExactResult' was expected" in exc.message
        assert invalid_commit["truth_admission"]["mutation_allowed"] is True
        assert invalid_commit["truth_admission"]["proof_state"] == "Pass"
    else:
        raise AssertionError("Truth commit mutation requires exact pass proof")


def test_truth_candidate_requires_sandbox_isolation_for_mutation_boundary() -> None:
    candidate = _load_json(TRUTH_CANDIDATE_EXAMPLE_PATH)
    invalid_candidate = copy.deepcopy(candidate)
    invalid_candidate["admission_boundary"]["requires_sandbox_isolation"] = False

    validator = _validator(TRUTH_CANDIDATE_SCHEMA_PATH)

    validator.validate(candidate)
    try:
        validator.validate(invalid_candidate)
    except ValidationError as exc:
        assert "True was expected" in exc.message
        assert list(exc.absolute_path)[-1] == "requires_sandbox_isolation"
        assert invalid_candidate["admission_boundary"]["can_mutate_truth"] is True
    else:
        raise AssertionError("Truth mutation candidates must require sandbox isolation")


def test_truth_kernel_document_references_schemas_and_non_goals() -> None:
    document = DOCUMENT_PATH.read_text(encoding="utf-8")

    assert "Mullu Truth Kernel" in document
    assert "schemas/truth_candidate.schema.json" in document
    assert "schemas/kernel_proof.schema.json" in document
    assert "schemas/truth_commit_candidate.schema.json" in document
    assert "Promote approximate or bounded outputs into truth" in document
    assert "Mullusi is the company name" in document
