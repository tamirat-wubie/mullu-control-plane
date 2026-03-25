"""Purpose: verify shared schemas, Python contracts, and Rust types stay aligned.
Governance scope: cross-runtime conformance audit only.
Dependencies: schema validation script, shared schemas, Python contracts, and Rust shared types.
Invariants: canonical field names and enum values do not drift across runtimes.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import validate_schemas


def test_shared_schemas_are_well_formed() -> None:
    errors = validate_schemas.validate_json_schemas()
    assert isinstance(errors, list)
    assert len(errors) == 0
    assert errors == []


def test_python_contracts_match_shared_schemas_strictly() -> None:
    errors = validate_schemas.check_contract_parity(strict=True)
    assert isinstance(errors, list)
    assert len(errors) == 0
    assert errors == []


def test_rust_shared_types_match_shared_schemas_strictly() -> None:
    errors = validate_schemas.check_rust_contract_parity(strict=True)
    assert isinstance(errors, list)
    assert len(errors) == 0
    assert errors == []


def test_schema_boundary_exceptions_are_explicit_and_valid() -> None:
    errors = validate_schemas.check_schema_boundary_exceptions()
    assert isinstance(errors, list)
    assert len(errors) == 0
    assert errors == []


def test_canonical_shared_fixtures_match_shared_schemas_strictly() -> None:
    errors = validate_schemas.validate_canonical_fixtures(strict=True)
    assert isinstance(errors, list)
    assert len(errors) == 0
    assert errors == []


def test_python_contracts_round_trip_canonical_shared_fixtures_exactly() -> None:
    errors = validate_schemas.check_python_fixture_round_trip()
    assert isinstance(errors, list)
    assert len(errors) == 0
    assert errors == []
