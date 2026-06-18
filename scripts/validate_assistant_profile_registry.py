#!/usr/bin/env python3
"""Validate assistant profile registry parity.

Purpose: keep assistant_profiles/*.default.yaml aligned with the runtime
assistant profile catalog without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: assistant_profiles/*.default.yaml and mcoi_runtime.assistant_kernel.
Invariants:
  - Every built-in assistant profile has exactly one registry file.
  - Registry files cannot silently drift from runtime policy fields.
  - Profile skill identifiers stay inside the profile-kind namespace.
  - Runtime profiles preserve the protected forbidden-capability floor.
  - Registry validation is read-only and deterministic.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for path in (REPO_ROOT, MCOI_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mcoi_runtime.assistant_kernel.identity import (  # noqa: E402
    PROTECTED_FORBIDDEN_CAPABILITIES,
    builtin_assistant_profiles,
)


DEFAULT_PROFILE_DIR = REPO_ROOT / "assistant_profiles"

SCALAR_PROFILE_FIELDS = (
    "assistant_id",
    "kind",
    "owner_scope",
    "tenant_scope",
    "role",
    "memory_policy",
    "approval_policy",
    "budget_policy",
    "external_send_policy",
    "data_retention_policy",
)
LIST_PROFILE_FIELDS = (
    "skill_ids",
    "allowed_capabilities",
    "forbidden_capabilities",
    "evidence_required",
    "escalation_path",
)
DECLARED_PROFILE_FIELDS = (*SCALAR_PROFILE_FIELDS, *LIST_PROFILE_FIELDS)
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


@dataclass(frozen=True, slots=True)
class AssistantProfileRegistryValidation:
    """Validation result for assistant profile registry parity."""

    valid: bool
    profile_dir: str
    profile_count: int
    runtime_profile_count: int
    profile_ids: tuple[str, ...]
    protected_forbidden_capabilities: tuple[str, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["profile_ids"] = list(self.profile_ids)
        rendered["protected_forbidden_capabilities"] = list(self.protected_forbidden_capabilities)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_assistant_profile_registry(
    *,
    profile_dir: Path = DEFAULT_PROFILE_DIR,
) -> AssistantProfileRegistryValidation:
    """Validate assistant profile YAML files against runtime built-in profiles."""
    errors: list[str] = []
    runtime_profiles = {profile.assistant_id: profile.to_dict() for profile in builtin_assistant_profiles()}
    profile_files = _profile_files(profile_dir, errors)
    parsed_profiles: dict[str, dict[str, Any]] = {}

    for path in profile_files:
        parsed = _load_profile_file(path, errors)
        if not parsed:
            continue
        assistant_id = str(parsed.get("assistant_id", ""))
        if not assistant_id:
            errors.append(f"{_path_label(path)}: assistant_id must be present")
            continue
        if assistant_id in parsed_profiles:
            errors.append(f"{assistant_id}: duplicate assistant profile registry file")
            continue
        parsed_profiles[assistant_id] = parsed
        if path.name != f"{assistant_id}.yaml":
            errors.append(f"{assistant_id}: filename must be {assistant_id}.yaml")
        _validate_profile_payload(path, parsed, errors)
        _scan_secret_like_values(parsed, errors, path=f"{_path_label(path)}")

    _validate_runtime_parity(parsed_profiles, runtime_profiles, errors)
    return AssistantProfileRegistryValidation(
        valid=not errors,
        profile_dir=_path_label(profile_dir),
        profile_count=len(parsed_profiles),
        runtime_profile_count=len(runtime_profiles),
        profile_ids=tuple(sorted(parsed_profiles)),
        protected_forbidden_capabilities=tuple(sorted(PROTECTED_FORBIDDEN_CAPABILITIES)),
        errors=tuple(errors),
    )


def _profile_files(profile_dir: Path, errors: list[str]) -> tuple[Path, ...]:
    try:
        files = tuple(sorted(profile_dir.glob("*.default.yaml")))
    except OSError as exc:
        errors.append(f"{_path_label(profile_dir)}: profile directory cannot be read: {exc}")
        return ()
    if not files:
        errors.append(f"{_path_label(profile_dir)}: no *.default.yaml profile files found")
    return files


def _load_profile_file(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{_path_label(path)}: cannot read profile file: {exc}")
        return {}
    try:
        parsed = parse_bounded_profile_yaml(raw_text)
    except ValueError as exc:
        errors.append(f"{_path_label(path)}: {exc}")
        return {}
    return parsed


def parse_bounded_profile_yaml(raw_text: str) -> dict[str, Any]:
    """Parse the bounded assistant profile YAML subset used by this registry."""
    parsed: dict[str, Any] = {}
    active_list_key: str | None = None
    for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
        if "\t" in raw_line:
            raise ValueError(f"line {line_number}: tabs are not admitted")
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw_line.startswith("  - "):
            if active_list_key is None:
                raise ValueError(f"line {line_number}: list item has no active key")
            item = raw_line[4:].strip()
            if not item:
                raise ValueError(f"line {line_number}: empty list item")
            parsed[active_list_key].append(item)
            continue
        if raw_line.startswith(" "):
            raise ValueError(f"line {line_number}: unsupported indentation")
        if ":" not in raw_line:
            raise ValueError(f"line {line_number}: expected key/value delimiter")
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"line {line_number}: empty key")
        if key in parsed:
            raise ValueError(f"line {line_number}: duplicate key {key}")
        if value:
            parsed[key] = value
            active_list_key = None
        else:
            parsed[key] = []
            active_list_key = key
    return parsed


def _validate_profile_payload(path: Path, payload: dict[str, Any], errors: list[str]) -> None:
    label = _path_label(path)
    unknown_fields = sorted(set(payload) - set(DECLARED_PROFILE_FIELDS))
    if unknown_fields:
        errors.append(f"{label}: unknown profile fields {unknown_fields}")
    missing_fields = [field for field in DECLARED_PROFILE_FIELDS if field not in payload]
    if missing_fields:
        errors.append(f"{label}: missing profile fields {missing_fields}")
    for field in SCALAR_PROFILE_FIELDS:
        if field in payload and not _is_non_empty_text(payload[field]):
            errors.append(f"{label}: {field} must be non-empty text")
    for field in LIST_PROFILE_FIELDS:
        if field in payload and not _is_non_empty_text_list(payload[field]):
            errors.append(f"{label}: {field} must contain non-empty text entries")
    _validate_skill_namespace(label, payload, errors)


def _validate_runtime_parity(
    registry_profiles: dict[str, dict[str, Any]],
    runtime_profiles: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    missing_files = sorted(set(runtime_profiles) - set(registry_profiles))
    unexpected_files = sorted(set(registry_profiles) - set(runtime_profiles))
    if missing_files:
        errors.append(f"missing assistant profile registry files for {missing_files}")
    if unexpected_files:
        errors.append(f"unexpected assistant profile registry files for {unexpected_files}")

    for assistant_id in sorted(set(runtime_profiles).intersection(registry_profiles)):
        registry = registry_profiles[assistant_id]
        runtime = runtime_profiles[assistant_id]
        for field in SCALAR_PROFILE_FIELDS:
            if registry.get(field) != runtime.get(field):
                errors.append(
                    f"{assistant_id}: {field} drift registry={registry.get(field)!r} runtime={runtime.get(field)!r}"
                )
        for field in ("skill_ids", "allowed_capabilities", "evidence_required", "escalation_path"):
            registry_values = tuple(registry.get(field, ()))
            runtime_values = tuple(runtime.get(field, ()))
            if registry_values != runtime_values:
                errors.append(f"{assistant_id}: {field} drift")
        registry_forbidden = tuple(registry.get("forbidden_capabilities", ()))
        expected_runtime_forbidden = _apply_protected_forbidden_capability_floor(registry_forbidden)
        runtime_forbidden = tuple(runtime.get("forbidden_capabilities", ()))
        if runtime_forbidden != expected_runtime_forbidden:
            errors.append(
                f"{assistant_id}: forbidden_capabilities drift after protected floor "
                f"registry={list(registry_forbidden)!r} runtime={list(runtime_forbidden)!r}"
            )


def _apply_protected_forbidden_capability_floor(capabilities: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*capabilities, *tuple(sorted(PROTECTED_FORBIDDEN_CAPABILITIES)))))


def _validate_skill_namespace(label: str, payload: dict[str, Any], errors: list[str]) -> None:
    kind = payload.get("kind")
    skill_ids = payload.get("skill_ids")
    if not isinstance(kind, str) or not isinstance(skill_ids, list):
        return
    namespace = f"skill.{kind}."
    mismatches = sorted(
        skill_id for skill_id in skill_ids if isinstance(skill_id, str) and not skill_id.startswith(namespace)
    )
    if mismatches:
        errors.append(f"{label}: skill_ids outside kind namespace {mismatches}")


def _is_non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_non_empty_text_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_is_non_empty_text(item) for item in value)


def _scan_secret_like_values(payload: Any, errors: list[str], *, path: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            _scan_secret_like_values(value, errors, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_secret_like_values(value, errors, path=f"{path}[{index}]")
    elif isinstance(payload, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(payload):
                errors.append(f"{path}: secret-like value must not be serialized")
                break


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse assistant profile registry validation arguments."""
    parser = argparse.ArgumentParser(description="Validate assistant profile registry parity.")
    parser.add_argument("--profiles-dir", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for assistant profile registry validation."""
    args = parse_args(argv)
    result = validate_assistant_profile_registry(profile_dir=Path(args.profiles_dir))
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "assistant profile registry ok "
            f"profiles={result.profile_count} protected_floor={len(result.protected_forbidden_capabilities)}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
