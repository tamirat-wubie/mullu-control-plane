#!/usr/bin/env python3
"""Collect a bounded LDAP directory export.

Purpose: invoke a credentialed ldapsearch command for users and groups, parse
bounded LDIF output, and write a local export consumed by
scripts/ldap_authority_directory_adapter.py.
Governance scope: source evidence, dependency and credential blockers,
credential-safe errors, and separation between LDAP identity evidence collection
and authority mapping.
Dependencies: standard-library subprocess, JSON, argparse, pathlib.
Invariants:
  - Bind passwords are never printed or written to the export.
  - Only explicitly requested user and group searches are collected.
  - The collector writes identity evidence only; it never creates authority.
  - LDAP command failure reasons are bounded before operator output.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_PATH = Path(".change_assurance") / "ldap_directory_export.json"
DEFAULT_USER_ATTRIBUTES = ("dn", "uid", "cn", "mail")
DEFAULT_GROUP_ATTRIBUTES = ("dn", "cn", "member")


@dataclass(frozen=True, slots=True)
class LdapCollectionSummary:
    """Bounded summary for one LDAP export collection."""

    source_ref: str
    collected_at: str
    user_count: int
    group_count: int


def collect_ldap_directory_export(
    *,
    ldap_uri: str,
    bind_dn: str,
    bind_password: str,
    user_base_dn: str,
    group_base_dn: str,
    user_filter: str = "(objectClass=person)",
    group_filter: str = "(objectClass=groupOfNames)",
    user_attributes: tuple[str, ...] = DEFAULT_USER_ATTRIBUTES,
    group_attributes: tuple[str, ...] = DEFAULT_GROUP_ATTRIBUTES,
    ldapsearch_binary: str = "ldapsearch",
    clock: Any | None = None,
) -> dict[str, Any]:
    """Collect LDAP users and groups into one local export payload."""
    normalized_uri = ldap_uri.strip()
    normalized_bind_dn = bind_dn.strip()
    normalized_bind_password = bind_password.strip()
    normalized_user_base = user_base_dn.strip()
    normalized_group_base = group_base_dn.strip()
    if not normalized_uri.startswith(("ldap://", "ldaps://")):
        raise ValueError("ldap_uri must be ldap or ldaps")
    if not normalized_bind_dn:
        raise ValueError("bind_dn is required")
    if not normalized_bind_password:
        raise ValueError("bind_password is required")
    if not normalized_user_base:
        raise ValueError("user_base_dn is required")
    if not normalized_group_base:
        raise ValueError("group_base_dn is required")
    collected_at = (clock or _utc_now)()
    directory_ref = _directory_ref(normalized_uri)

    users_ldif = _run_ldapsearch(
        ldapsearch_binary=ldapsearch_binary,
        ldap_uri=normalized_uri,
        bind_dn=normalized_bind_dn,
        bind_password=normalized_bind_password,
        base_dn=normalized_user_base,
        ldap_filter=user_filter,
        attributes=user_attributes,
    )
    groups_ldif = _run_ldapsearch(
        ldapsearch_binary=ldapsearch_binary,
        ldap_uri=normalized_uri,
        bind_dn=normalized_bind_dn,
        bind_password=normalized_bind_password,
        base_dn=normalized_group_base,
        ldap_filter=group_filter,
        attributes=group_attributes,
    )
    users = tuple(_user_record(entry) for entry in _parse_ldif_entries(users_ldif))
    groups = tuple(_group_record(entry) for entry in _parse_ldif_entries(groups_ldif))
    summary = LdapCollectionSummary(
        source_ref=f"ldap://{directory_ref}/export/{collected_at}",
        collected_at=collected_at,
        user_count=len(users),
        group_count=len(groups),
    )
    return {
        "source_system": "ldap_search",
        "directory_ref": directory_ref,
        "source_ref": summary.source_ref,
        "collected_at": summary.collected_at,
        "summary": asdict(summary),
        "users": users,
        "groups": groups,
    }


def write_ldap_export(payload: dict[str, Any], output_path: Path) -> Path:
    """Write one LDAP export JSON document."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _run_ldapsearch(
    *,
    ldapsearch_binary: str,
    ldap_uri: str,
    bind_dn: str,
    bind_password: str,
    base_dn: str,
    ldap_filter: str,
    attributes: tuple[str, ...],
) -> str:
    password_file = _write_password_file(bind_password)
    command = [
        ldapsearch_binary,
        "-LLL",
        "-x",
        "-H",
        ldap_uri,
        "-D",
        bind_dn,
        "-y",
        str(password_file),
        "-b",
        base_dn,
        ldap_filter,
        *tuple(attribute for attribute in attributes if attribute != "dn"),
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise ValueError("ldapsearch dependency unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("LDAP search timed out") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError("LDAP search failed") from exc
    finally:
        try:
            password_file.unlink(missing_ok=True)
        except OSError:
            pass
    return completed.stdout


def _parse_ldif_entries(ldif: str) -> tuple[dict[str, list[str]], ...]:
    entries: list[dict[str, list[str]]] = []
    current: dict[str, list[str]] = {}
    previous_key = ""
    for raw_line in ldif.splitlines():
        line = raw_line.rstrip("\r")
        if not line:
            if current:
                entries.append(current)
                current = {}
                previous_key = ""
            continue
        if line.startswith("#"):
            continue
        if line.startswith(" "):
            if not previous_key:
                raise ValueError("LDAP LDIF continuation has no field")
            current[previous_key][-1] += line[1:]
            continue
        if ":" not in line:
            raise ValueError("LDAP LDIF line must contain field separator")
        key, value = line.split(":", 1)
        normalized_key = key.strip().lower()
        if not normalized_key:
            raise ValueError("LDAP LDIF field name is required")
        if value.startswith(":"):
            raise ValueError("LDAP LDIF base64 values are not supported")
        current.setdefault(normalized_key, []).append(value.lstrip())
        previous_key = normalized_key
    if current:
        entries.append(current)
    return tuple(entries)


def _user_record(entry: dict[str, list[str]]) -> dict[str, Any]:
    dn = _single_required(entry, "dn")
    return {
        "dn": dn,
        "uid": _single_optional(entry, "uid", fallback=dn),
        "cn": _single_optional(entry, "cn", fallback=dn),
        "mail": _single_optional(entry, "mail", fallback=""),
        "active": True,
    }


def _group_record(entry: dict[str, list[str]]) -> dict[str, Any]:
    dn = _single_required(entry, "dn")
    return {
        "dn": dn,
        "cn": _single_optional(entry, "cn", fallback=dn),
        "display_name": _single_optional(entry, "cn", fallback=dn),
        "members": tuple(member for member in entry.get("member", ()) if member.strip()),
    }


def _single_required(entry: dict[str, list[str]], key: str) -> str:
    value = _single_optional(entry, key, fallback="")
    if not value:
        raise ValueError(f"LDAP {key} is required")
    return value


def _single_optional(entry: dict[str, list[str]], key: str, *, fallback: str) -> str:
    values = entry.get(key, ())
    for value in values:
        if value.strip():
            return value.strip()
    return fallback


def _directory_ref(ldap_uri: str) -> str:
    return (
        ldap_uri.removeprefix("ldaps://")
        .removeprefix("ldap://")
        .strip("/")
        or "ldap-directory"
    )


def _write_password_file(bind_password: str) -> Path:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(bind_password)
        handle.write("\n")
        return Path(handle.name)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _attributes(raw_value: str, default: tuple[str, ...]) -> tuple[str, ...]:
    values = tuple(item.strip() for item in raw_value.split(",") if item.strip())
    return values or default


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the LDAP export collector CLI contract."""
    parser = argparse.ArgumentParser(description="Collect LDAP users and groups into a local export JSON.")
    parser.add_argument("--ldap-uri", required=True, help="LDAP URI, for example ldaps://directory.example.com")
    parser.add_argument("--bind-dn", default=os.environ.get("MULLU_LDAP_BIND_DN", ""))
    parser.add_argument("--bind-password", default=os.environ.get("MULLU_LDAP_BIND_PASSWORD", ""))
    parser.add_argument("--user-base-dn", required=True)
    parser.add_argument("--group-base-dn", required=True)
    parser.add_argument("--user-filter", default="(objectClass=person)")
    parser.add_argument("--group-filter", default="(objectClass=groupOfNames)")
    parser.add_argument("--user-attributes", default=",".join(DEFAULT_USER_ATTRIBUTES))
    parser.add_argument("--group-attributes", default=",".join(DEFAULT_GROUP_ATTRIBUTES))
    parser.add_argument("--ldapsearch-binary", default="ldapsearch")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for live LDAP export collection."""
    args = parse_args(argv)
    try:
        payload = collect_ldap_directory_export(
            ldap_uri=args.ldap_uri,
            bind_dn=args.bind_dn,
            bind_password=args.bind_password,
            user_base_dn=args.user_base_dn,
            group_base_dn=args.group_base_dn,
            user_filter=args.user_filter,
            group_filter=args.group_filter,
            user_attributes=_attributes(args.user_attributes, DEFAULT_USER_ATTRIBUTES),
            group_attributes=_attributes(args.group_attributes, DEFAULT_GROUP_ATTRIBUTES),
            ldapsearch_binary=args.ldapsearch_binary,
        )
        written = write_ldap_export(payload, args.output)
        print(f"LDAP directory export written: {written}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"LDAP directory export failed: {_bounded_error_reason(exc)}", file=sys.stderr)
        return 2


def _bounded_error_reason(exc: OSError | ValueError) -> str:
    if isinstance(exc, OSError):
        return "output_unavailable"
    message = str(exc)
    if message in {
        "ldap_uri must be ldap or ldaps",
        "bind_dn is required",
        "bind_password is required",
        "user_base_dn is required",
        "group_base_dn is required",
        "ldapsearch dependency unavailable",
        "LDAP search timed out",
        "LDAP search failed",
        "LDAP LDIF continuation has no field",
        "LDAP LDIF line must contain field separator",
        "LDAP LDIF field name is required",
        "LDAP LDIF base64 values are not supported",
        "LDAP dn is required",
    }:
        return message
    return "invalid_ldap_directory_export"


if __name__ == "__main__":
    raise SystemExit(main())
