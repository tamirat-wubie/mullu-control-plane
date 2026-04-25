"""Purpose: verify SDK generation is driven by OpenAPI.

Governance scope: SDK generator manifest, deterministic OpenAPI export helper,
and dry-run generator command visibility.
Dependencies: scripts/export_openapi.py, scripts/generate_sdks.py, and SDK
configuration files.
Invariants: SDK clients are generated from the OpenAPI spec; generator commands
are explicit; dry-run execution is side-effect free.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_sdks import load_generators, run_generators
from scripts.export_openapi import export_openapi


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_sdk_generation_manifest_declares_python_and_typescript() -> None:
    manifest = json.loads((REPO_ROOT / "sdk" / "sdk-generation.json").read_text(encoding="utf-8"))
    languages = {item["language"] for item in manifest["generators"]}

    assert manifest["governed"] is True
    assert manifest["source_spec"] == "sdk/openapi/mullu.openapi.json"
    assert languages == {"python", "typescript"}


def test_sdk_generators_are_openapi_sourced() -> None:
    generators = load_generators()
    command_text = "\n".join(" ".join(generator.command) for generator in generators)

    assert len(generators) == 2
    assert all(generator.spec_path.name == "mullu.openapi.json" for generator in generators)
    assert "sdk/openapi/mullu.openapi.json" in command_text
    assert all("generate" in generator.command or "@hey-api/openapi-ts" in generator.command for generator in generators)


def test_sdk_generator_configs_exist() -> None:
    python_config = REPO_ROOT / "sdk" / "python" / "openapi-python-client.yaml"
    typescript_config = REPO_ROOT / "sdk" / "typescript" / "openapi-ts.config.ts"
    typescript_package = REPO_ROOT / "sdk" / "typescript" / "package.json"

    assert python_config.exists()
    assert typescript_config.exists()
    assert typescript_package.exists()
    assert "package_name_override: mullu_client" in python_config.read_text(encoding="utf-8")
    assert "@hey-api/openapi-ts" in typescript_package.read_text(encoding="utf-8")


def test_openapi_source_spec_is_exported_for_sdk_generation() -> None:
    spec = json.loads((REPO_ROOT / "sdk" / "openapi" / "mullu.openapi.json").read_text(encoding="utf-8"))

    assert spec["info"]["title"] == "Mullu Platform"
    assert spec["info"]["version"] == "3.13.0"
    assert "/api/v1/replay/{trace_id}/determinism" in spec["paths"]
    assert len(spec["paths"]) >= 200


def test_sdk_generation_dry_run_reports_commands_without_executing() -> None:
    results = run_generators(dry_run=True)

    assert len(results) == 2
    assert all(result["dry_run"] is True for result in results)
    assert all(result["command"] for result in results)
    assert {result["language"] for result in results} == {"python", "typescript"}


def test_openapi_exporter_writes_deterministic_spec(tmp_path: Path) -> None:
    output_path = tmp_path / "mullu.openapi.json"

    spec = export_openapi(output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_path.exists()
    assert payload["info"]["title"] == "Mullu Platform"
    assert payload["paths"] == spec["paths"]
    assert len(payload["paths"]) >= 50
