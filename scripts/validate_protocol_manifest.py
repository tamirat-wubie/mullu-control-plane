"""Validate the public Mullu Governance Protocol manifest.

Purpose: ensure schemas are open and indexed while runtime implementation paths remain non-contract surfaces.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: schemas/mullu_governance_protocol.manifest.json and public JSON schemas.
Invariants: every public schema is listed once, URNs match file ids, and implementation paths stay closed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schemas"
MANIFEST_PATH = SCHEMA_DIR / "mullu_governance_protocol.manifest.json"
PROTOCOL_ID = "mullu-governance-protocol"
OPEN_SURFACE = "schemas_and_wire_contracts"
CLOSED_SURFACE = "runtime_implementation"
REQUIRED_NON_CONTRACT_PATHS = frozenset(
    {
        "mcoi/mcoi_runtime/core",
        "mcoi/mcoi_runtime/app",
        "gateway",
        "scripts",
    }
)


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_protocol_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("protocol_id") != PROTOCOL_ID:
        errors.append("protocol_id must be mullu-governance-protocol")
    if manifest.get("protocol_uri_scheme") != "mgp://":
        errors.append("protocol_uri_scheme must be mgp://")

    claim_boundary = manifest.get("claim_boundary", {})
    if claim_boundary.get("open_surface") != OPEN_SURFACE:
        errors.append("claim_boundary.open_surface must be schemas_and_wire_contracts")
    if claim_boundary.get("closed_surface") != CLOSED_SURFACE:
        errors.append("claim_boundary.closed_surface must be runtime_implementation")
    if claim_boundary.get("third_party_implementation_allowed") is not True:
        errors.append("third_party_implementation_allowed must be true")

    compatibility = manifest.get("compatibility", {})
    if compatibility.get("json_schema_draft") != "2020-12":
        errors.append("compatibility.json_schema_draft must be 2020-12")
    if compatibility.get("runtime_private_modules_are_not_protocol_contracts") is not True:
        errors.append("runtime private modules must not be protocol contracts")

    schema_entries = manifest.get("schemas", [])
    if not isinstance(schema_entries, list) or not schema_entries:
        errors.append("schemas must be a non-empty list")
        return errors

    entry_paths = [entry.get("path") for entry in schema_entries]
    if len(entry_paths) != len(set(entry_paths)):
        errors.append("schema paths must be unique")

    public_schema_paths = {
        f"schemas/{path.name}"
        for path in sorted(SCHEMA_DIR.glob("*.schema.json"))
    }
    missing_from_manifest = public_schema_paths - set(entry_paths)
    extra_in_manifest = set(entry_paths) - public_schema_paths
    if missing_from_manifest:
        errors.append(f"manifest missing public schemas: {sorted(missing_from_manifest)}")
    if extra_in_manifest:
        errors.append(f"manifest references non-public schemas: {sorted(extra_in_manifest)}")

    for entry in schema_entries:
        path_text = entry.get("path")
        urn = entry.get("urn")
        schema_id = entry.get("schema_id")
        surface = entry.get("surface")
        if not schema_id:
            errors.append("schema_id is required")
        if not surface:
            errors.append(f"{path_text}: surface is required")
        if not isinstance(path_text, str) or not path_text.startswith("schemas/"):
            errors.append(f"{path_text}: schema path must start with schemas/")
            continue
        schema_path = REPO_ROOT / path_text
        if not schema_path.exists():
            errors.append(f"{path_text}: schema file missing")
            continue
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{path_text}: unsupported JSON schema draft")
        if schema.get("$id") != urn:
            errors.append(f"{path_text}: manifest urn does not match schema $id")
        if not isinstance(urn, str) or not urn.startswith("urn:mullusi:schema:"):
            errors.append(f"{path_text}: urn must use urn:mullusi:schema")

    non_contract_paths = set(manifest.get("non_contract_paths", []))
    missing_non_contract_paths = REQUIRED_NON_CONTRACT_PATHS - non_contract_paths
    if missing_non_contract_paths:
        errors.append(f"missing non-contract paths: {sorted(missing_non_contract_paths)}")
    for path_text in non_contract_paths:
        if path_text.startswith("schemas/"):
            errors.append("schemas/ cannot be listed as a non-contract path")

    uri_schemes = {entry.get("scheme") for entry in manifest.get("uri_schemes", [])}
    for required_scheme in ("lineage://", "proof://", "mgp://"):
        if required_scheme not in uri_schemes:
            errors.append(f"missing uri scheme: {required_scheme}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the canonical manifest JSON.")
    args = parser.parse_args()

    manifest = load_manifest()
    errors = validate_protocol_manifest(manifest)
    if errors:
        for error in errors:
            print(error)
        return 1
    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(f"protocol manifest ok: {len(manifest['schemas'])} schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
