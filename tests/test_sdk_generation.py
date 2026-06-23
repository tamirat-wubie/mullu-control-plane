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
import os
import subprocess
import sys
from pathlib import Path

from scripts.generate_sdks import load_generators, run_generators
from scripts.export_openapi import export_openapi


REPO_ROOT = Path(__file__).resolve().parents[1]
OPENAPI_SOURCE_SPEC = REPO_ROOT / "sdk" / "openapi" / "mullu.openapi.json"
WORK_ASSISTANT_DASHBOARD_ROUTE = "/api/v1/personal-assistant/work-assistant/dashboard/read-model"


def _assert_openapi_section_matches(
    checked_in_spec: dict[str, object],
    exported_spec: dict[str, object],
    section_name: str,
) -> None:
    checked_in_section = checked_in_spec[section_name]
    exported_section = exported_spec[section_name]
    if not isinstance(checked_in_section, dict) or not isinstance(exported_section, dict):
        assert checked_in_section == exported_section
        return

    checked_in_keys = set(checked_in_section)
    exported_keys = set(exported_section)
    missing = sorted(exported_keys - checked_in_keys)
    extra = sorted(checked_in_keys - exported_keys)

    assert missing == [], f"{section_name} missing from checked-in OpenAPI spec: {missing[:10]}"
    assert extra == [], f"{section_name} extra in checked-in OpenAPI spec: {extra[:10]}"
    if checked_in_section != exported_section:
        first_changed = next(
            key for key in sorted(checked_in_keys)
            if checked_in_section[key] != exported_section[key]
        )
        raise AssertionError(f"{section_name} entry drifted in checked-in OpenAPI spec: {first_changed}")


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
    spec = json.loads(OPENAPI_SOURCE_SPEC.read_text(encoding="utf-8"))

    assert spec["info"]["title"] == "Mullu Platform"
    assert spec["info"]["version"] == "3.13.0"
    assert "/api/v1/replay/{trace_id}/determinism" in spec["paths"]
    assert "/api/v1/cases/{case_id}/step-handoffs/view" in spec["paths"]
    assert WORK_ASSISTANT_DASHBOARD_ROUTE in spec["paths"]
    assert "/software/receipts/dashboard" in spec["paths"]
    assert "/software/receipts/sdlc/dashboard" in spec["paths"]
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
    assert WORK_ASSISTANT_DASHBOARD_ROUTE in payload["paths"]
    assert WORK_ASSISTANT_DASHBOARD_ROUTE in spec["paths"]
    assert "/software/receipts/dashboard" in payload["paths"]
    assert "/software/receipts/sdlc/dashboard" in payload["paths"]
    assert len(payload["paths"]) >= 50


def test_openapi_exporter_includes_work_assistant_dashboard_route(tmp_path: Path) -> None:
    output_path = tmp_path / "mullu.openapi.json"

    exported_spec = export_openapi(output_path)
    operation = exported_spec["paths"][WORK_ASSISTANT_DASHBOARD_ROUTE]["get"]

    assert operation["summary"] == "Governed Work Assistant Operator Dashboard Read Model"
    assert operation["responses"]["200"]["description"] == "Successful Response"
    assert WORK_ASSISTANT_DASHBOARD_ROUTE in json.loads(output_path.read_text(encoding="utf-8"))["paths"]


def test_checked_in_openapi_source_matches_runtime_export(tmp_path: Path) -> None:
    output_path = tmp_path / "mullu.openapi.json"
    exported_spec = export_openapi(output_path)
    checked_in_spec = json.loads(OPENAPI_SOURCE_SPEC.read_text(encoding="utf-8"))

    assert checked_in_spec["info"] == exported_spec["info"]
    _assert_openapi_section_matches(checked_in_spec, exported_spec, "paths")
    _assert_openapi_section_matches(
        checked_in_spec["components"],
        exported_spec["components"],
        "schemas",
    )


def test_openapi_exporter_cli_writes_software_receipt_paths(tmp_path: Path) -> None:
    output_path = tmp_path / "mullu.openapi.json"
    env = dict(os.environ)
    env["MULLU_ENV"] = "local_dev"
    env["MULLU_DB_BACKEND"] = "memory"

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "export_openapi.py"),
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    report = json.loads(result.stdout)
    assert WORK_ASSISTANT_DASHBOARD_ROUTE in payload["paths"]
    assert "/software/receipts/dashboard" in payload["paths"]
    assert "/software/receipts/sdlc/dashboard" in payload["paths"]
    assert "/software/receipts/private-pilot/operator-view" in payload["paths"]
    assert "/software/receipts/private-pilot/operator-view/view" in payload["paths"]
    assert report["governed"] is True
