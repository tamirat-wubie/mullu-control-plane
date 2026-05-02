"""Tests for the public Mullu Governance Protocol manifest.

Purpose: verify the open schema surface is complete and the runtime remains outside the public contract boundary.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: protocol manifest validator and public schemas.
Invariants: every schema is indexed once, URNs match, and runtime paths are non-contract surfaces.
"""
from __future__ import annotations

from scripts.validate_protocol_manifest import (
    CLOSED_SURFACE,
    OPEN_SURFACE,
    PROTOCOL_ID,
    load_manifest,
    validate_protocol_manifest,
)


def test_protocol_manifest_is_valid() -> None:
    manifest = load_manifest()
    errors = validate_protocol_manifest(manifest)

    assert errors == []
    assert manifest["protocol_id"] == PROTOCOL_ID
    assert manifest["protocol_name"] == "Mullu Governance Protocol"
    assert manifest["protocol_uri_scheme"] == "mgp://"
    assert len(manifest["schemas"]) == 28


def test_protocol_manifest_defines_open_and_closed_surfaces() -> None:
    manifest = load_manifest()
    claim_boundary = manifest["claim_boundary"]

    assert claim_boundary["open_surface"] == OPEN_SURFACE
    assert claim_boundary["closed_surface"] == CLOSED_SURFACE
    assert claim_boundary["reference_runtime"] == "mullu-control-plane"
    assert claim_boundary["third_party_implementation_allowed"] is True
    assert manifest["compatibility"]["runtime_private_modules_are_not_protocol_contracts"] is True


def test_protocol_manifest_urns_match_schema_files() -> None:
    manifest = load_manifest()

    for entry in manifest["schemas"]:
        assert entry["path"].startswith("schemas/")
        assert entry["urn"].startswith("urn:mullusi:schema:")
        assert entry["schema_id"]
        assert entry["surface"]


def test_protocol_manifest_rejects_missing_schema_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = manifest["schemas"][:-1]

    errors = validate_protocol_manifest(manifest)

    assert any("manifest missing public schemas" in error for error in errors)


def test_protocol_manifest_rejects_runtime_as_open_schema() -> None:
    manifest = load_manifest()
    manifest["schemas"].append(
        {
            "schema_id": "runtime-core",
            "path": "mcoi/mcoi_runtime/core/runtime.py",
            "urn": "urn:mullusi:schema:runtime-core:1",
            "surface": "runtime",
        }
    )

    errors = validate_protocol_manifest(manifest)

    assert any("manifest references non-public schemas" in error for error in errors)
    assert any("schema path must start with schemas/" in error for error in errors)
