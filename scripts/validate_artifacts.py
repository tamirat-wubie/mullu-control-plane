#!/usr/bin/env python3
"""Shipped artifact validation for MCOI example, pilot, and doc-linked JSON files.

Validates:
  1. Shipped config artifacts deserialize through AppConfig without silent key drift.
  2. Shipped request artifacts normalize through the governed CLI request contract.
  3. Request templates validate without executing adapters or mutating runtime state.
  4. Request action routes are admitted by their paired config artifact or by default config.
  5. Auxiliary pilot JSON artifacts remain inventory-bounded and contract-validated.
  6. Operator and pilot markdown references stay aligned with governed artifact inventory.

Usage:
  python scripts/validate_artifacts.py
  python scripts/validate_artifacts.py --strict
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_PATH = REPO_ROOT / "mcoi"
MCOI_EXAMPLES_DIR = MCOI_PATH / "examples"
PILOT_EXAMPLES_DIR = REPO_ROOT / "examples" / "pilots"

if str(MCOI_PATH) not in sys.path:
    sys.path.insert(0, str(MCOI_PATH))

from mcoi_runtime.app.cli import _build_operator_request
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.contracts.document import DocumentVerificationStatus
from mcoi_runtime.core.document import extract_json_fields, ingest_document, verify_extraction
from mcoi_runtime.core.template_validator import TemplateValidationError, TemplateValidator


@dataclass(frozen=True, slots=True)
class ExampleArtifactInventory:
    """Deterministic inventory of shipped JSON artifacts."""

    config_paths: tuple[Path, ...]
    request_paths: tuple[Path, ...]
    auxiliary_paths: tuple[Path, ...]
    pilot_directories: tuple[Path, ...]


AuxiliaryArtifactValidator = Callable[[Path], list[str]]


def _sort_paths(paths: list[Path]) -> tuple[Path, ...]:
    return tuple(sorted(paths, key=lambda path: path.relative_to(REPO_ROOT).as_posix()))


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _load_json_object(path: Path, *, kind: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{_relative_path(path)}: invalid {kind} JSON: {exc.msg}") from exc
    except OSError as exc:
        raise ValueError(f"{_relative_path(path)}: cannot read {kind} artifact: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"{_relative_path(path)}: {kind} JSON root must be an object")
    return payload


def _require_non_empty_text(value: Any, *, field_name: str, path: Path) -> list[str]:
    if isinstance(value, str) and value.strip():
        return []
    return [f"{_relative_path(path)}: field '{field_name}' must be a non-empty string"]


def _require_positive_int(value: Any, *, field_name: str, path: Path) -> list[str]:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return [f"{_relative_path(path)}: field '{field_name}' must be a positive integer"]
    return []


def _validate_document_to_action_input(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="pilot auxiliary")
    errors: list[str] = []
    expected_keys = ("task", "target", "retention_days", "notify_email")

    unknown_keys = sorted(set(payload) - set(expected_keys))
    if unknown_keys:
        errors.append(
            f"{_relative_path(path)}: unexpected auxiliary fields: {', '.join(unknown_keys)}"
        )

    missing_keys = tuple(key for key in expected_keys if key not in payload)
    if missing_keys:
        errors.append(
            f"{_relative_path(path)}: missing auxiliary fields: {', '.join(missing_keys)}"
        )
        return errors

    errors.extend(_require_non_empty_text(payload["task"], field_name="task", path=path))
    errors.extend(_require_non_empty_text(payload["target"], field_name="target", path=path))
    errors.extend(_require_positive_int(payload["retention_days"], field_name="retention_days", path=path))
    errors.extend(_require_non_empty_text(payload["notify_email"], field_name="notify_email", path=path))
    if errors:
        return errors

    content = path.read_text(encoding="utf-8")
    document_one = ingest_document(
        "pilot-document-to-action-input",
        _relative_path(path),
        content,
    )
    document_two = ingest_document(
        "pilot-document-to-action-input",
        _relative_path(path),
        content,
    )
    extraction = extract_json_fields(document_one, expected_keys)
    verification = verify_extraction(extraction, expected_keys)

    if document_one.fingerprint.content_hash != document_two.fingerprint.content_hash:
        errors.append(f"{_relative_path(path)}: document fingerprint must be deterministic")
    if extraction.extracted_count != len(expected_keys):
        errors.append(f"{_relative_path(path)}: extracted_count must equal expected field count")
    if extraction.missing_count != 0:
        errors.append(f"{_relative_path(path)}: extraction must not miss required pilot fields")
    if extraction.malformed_count != 0:
        errors.append(f"{_relative_path(path)}: extraction must not mark pilot fields malformed")
    if verification.status is not DocumentVerificationStatus.PASS:
        errors.append(f"{_relative_path(path)}: verification must pass for the shipped pilot document")

    return errors


AUXILIARY_PILOT_VALIDATORS: dict[str, AuxiliaryArtifactValidator] = {
    "examples/pilots/document_to_action/input_document.json": _validate_document_to_action_input,
}

DOCUMENT_ARTIFACT_EXPECTATIONS: dict[str, tuple[str, ...]] = {
    "OPERATOR_GUIDE_v0.1.md": (
        "mcoi/examples/config-local-dev.json",
        "mcoi/examples/config-safe-readonly.json",
        "mcoi/examples/request-echo.json",
        "mcoi/examples/request-with-bindings.json",
    ),
    "PILOT_WORKFLOWS_v0.1.md": (
        "examples/pilots/approval_gated_command/config.json",
        "examples/pilots/approval_gated_command/request.json",
        "examples/pilots/document_to_action/config.json",
        "examples/pilots/document_to_action/input_document.json",
        "examples/pilots/failure_escalation/config.json",
    ),
}

_DOC_ARTIFACT_PATTERN = re.compile(
    r"(mcoi/examples/[A-Za-z0-9._/-]+\.json|examples/pilots/[A-Za-z0-9._/-]+\.json)"
)


def discover_example_inventory() -> ExampleArtifactInventory:
    """Discover the governed shipped example inventory."""
    pilot_directories = (
        _sort_paths([path for path in PILOT_EXAMPLES_DIR.iterdir() if path.is_dir()])
        if PILOT_EXAMPLES_DIR.exists()
        else ()
    )
    config_paths = _sort_paths(
        list(MCOI_EXAMPLES_DIR.glob("config-*.json"))
        + [path / "config.json" for path in pilot_directories if (path / "config.json").exists()]
    )
    request_paths = _sort_paths(
        list(MCOI_EXAMPLES_DIR.glob("request-*.json"))
        + [path / "request.json" for path in pilot_directories if (path / "request.json").exists()]
    )
    auxiliary_paths = _sort_paths(
        [
            path
            for pilot_directory in pilot_directories
            for path in pilot_directory.glob("*.json")
            if path.name not in {"config.json", "request.json"}
        ]
    )
    return ExampleArtifactInventory(
        config_paths=config_paths,
        request_paths=request_paths,
        auxiliary_paths=auxiliary_paths,
        pilot_directories=pilot_directories,
    )


def validate_config_artifact(path: Path) -> list[str]:
    """Validate a shipped config artifact against the app config contract."""
    try:
        payload = _load_json_object(path, kind="config")
        AppConfig.from_mapping(payload)
    except ValueError as exc:
        return [f"{_relative_path(path)}: {exc}"]
    return []


def _load_request_config(request_path: Path) -> tuple[AppConfig | None, list[str]]:
    paired_config_path = request_path.parent / "config.json"
    if not paired_config_path.exists():
        return AppConfig(), []
    errors = validate_config_artifact(paired_config_path)
    if errors:
        return None, errors
    return AppConfig.from_mapping(_load_json_object(paired_config_path, kind="config")), []


def validate_request_artifact(path: Path) -> list[str]:
    """Validate a shipped request artifact against the CLI request and template contracts."""
    errors: list[str] = []

    try:
        payload = _load_json_object(path, kind="request")
        request = _build_operator_request(payload, source_name=_relative_path(path))
    except ValueError as exc:
        return [str(exc)]

    validator = TemplateValidator()
    try:
        validated_template = validator.validate(request.template, request.bindings)
    except TemplateValidationError as exc:
        errors.append(f"{_relative_path(path)}: invalid request template {exc.code}: {exc}")
        return errors

    config, config_errors = _load_request_config(path)
    errors.extend(config_errors)
    if config is None:
        return errors

    if validated_template.action_type.value not in config.enabled_executor_routes:
        errors.append(
            f"{_relative_path(path)}: action route '{validated_template.action_type.value}' "
            "is not enabled by the paired config"
        )

    return errors


def validate_auxiliary_artifact(path: Path, *, artifact_key: str | None = None) -> list[str]:
    """Validate one governed auxiliary pilot artifact."""
    validator_key = artifact_key or _relative_path(path)
    validator = AUXILIARY_PILOT_VALIDATORS.get(validator_key)
    if validator is None:
        return [f"{_relative_path(path)}: no auxiliary validator registered"]
    return validator(path)


def validate_document_artifact_reference_text(
    *,
    document_name: str,
    content: str,
    expected_paths: tuple[str, ...],
    governed_paths: set[str],
    strict: bool = False,
) -> list[str]:
    """Validate governed artifact references within one markdown document."""
    errors: list[str] = []
    referenced_paths = tuple(sorted(set(_DOC_ARTIFACT_PATTERN.findall(content))))

    missing_expected = sorted(set(expected_paths) - set(referenced_paths))
    if missing_expected:
        errors.append(
            f"{document_name}: missing governed artifact references {missing_expected}"
        )

    for referenced_path in referenced_paths:
        artifact_path = REPO_ROOT / referenced_path
        if referenced_path not in governed_paths:
            errors.append(
                f"{document_name}: references ungoverned artifact path {referenced_path}"
            )
        elif not artifact_path.exists():
            errors.append(
                f"{document_name}: references missing artifact path {referenced_path}"
            )

    if strict:
        unexpected_references = sorted(set(referenced_paths) - set(expected_paths))
        if unexpected_references:
            errors.append(
                f"{document_name}: unexpected governed artifact references {unexpected_references}"
            )

    return errors


def validate_documented_artifact_references(*, strict: bool = False) -> list[str]:
    """Validate markdown references to governed artifacts."""
    errors: list[str] = []
    inventory = discover_example_inventory()
    governed_paths = {
        _relative_path(path)
        for path in (
            list(inventory.config_paths)
            + list(inventory.request_paths)
            + list(inventory.auxiliary_paths)
        )
    }

    for document_name, expected_paths in DOCUMENT_ARTIFACT_EXPECTATIONS.items():
        document_path = REPO_ROOT / document_name
        if not document_path.exists():
            errors.append(f"{document_name}: documentation file not found")
            continue

        content = document_path.read_text(encoding="utf-8")
        errors.extend(
            validate_document_artifact_reference_text(
                document_name=document_name,
                content=content,
                expected_paths=expected_paths,
                governed_paths=governed_paths,
                strict=strict,
            )
        )

    return errors


def validate_example_artifacts(*, strict: bool = False) -> list[str]:
    """Validate the shipped example inventory."""
    inventory = discover_example_inventory()
    errors: list[str] = []

    if strict and not inventory.config_paths:
        errors.append("no shipped config artifacts discovered")
    if strict and not inventory.request_paths:
        errors.append("no shipped request artifacts discovered")
    if strict:
        expected_auxiliary = set(AUXILIARY_PILOT_VALIDATORS)
        actual_auxiliary = {_relative_path(path) for path in inventory.auxiliary_paths}
        missing_auxiliary = sorted(expected_auxiliary - actual_auxiliary)
        unexpected_auxiliary = sorted(actual_auxiliary - expected_auxiliary)
        if missing_auxiliary:
            errors.append(f"missing governed auxiliary pilot artifacts: {missing_auxiliary}")
        if unexpected_auxiliary:
            errors.append(f"unexpected auxiliary pilot artifacts: {unexpected_auxiliary}")

    for pilot_directory in inventory.pilot_directories:
        if not (pilot_directory / "config.json").exists():
            errors.append(
                f"{_relative_path(pilot_directory)}: pilot directory missing required config.json"
            )

    for config_path in inventory.config_paths:
        errors.extend(validate_config_artifact(config_path))

    for request_path in inventory.request_paths:
        errors.extend(validate_request_artifact(request_path))

    for auxiliary_path in inventory.auxiliary_paths:
        errors.extend(validate_auxiliary_artifact(auxiliary_path))

    errors.extend(validate_documented_artifact_references(strict=strict))

    return errors


def main() -> None:
    strict = "--strict" in sys.argv
    inventory = discover_example_inventory()

    print("=== Artifact Inventory ===")
    print(f"  config artifacts:  {len(inventory.config_paths)}")
    print(f"  request artifacts: {len(inventory.request_paths)}")
    print(f"  auxiliary files:   {len(inventory.auxiliary_paths)}")
    print(f"  pilot directories: {len(inventory.pilot_directories)}")

    print("\n=== Artifact Validation ===")
    errors = validate_example_artifacts(strict=strict)
    if errors:
        print(f"\n{'=' * 40}")
        print(f"FAILED - {len(errors)} error(s):")
        for error in errors:
            print(f"  X {error}")
        sys.exit(1)

    print(f"\n{'=' * 40}")
    print("ALL CHECKS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
