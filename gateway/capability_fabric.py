"""Gateway Capability Fabric Loader.

Purpose: Builds an optional registry-backed command capability admission gate
    for gateway command execution.
Governance scope: environment-gated domain capsule loading, capsule pack
    loading, capability pack loading, capability registry installation, and
    command admission gate construction.
Dependencies: governed capability fabric contracts, compiler, registry, and
    command admission core.
Invariants:
  - Fabric admission is disabled unless explicitly enabled.
  - Enabled fabric admission requires at least one capsule JSON source and at
    least one capability JSON source.
  - Installed capabilities are resolved from explicit capsule references.
  - Failed compilation or installation fails gateway startup instead of running
    with a partial capability fabric.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityRegistryEntry,
    DomainCapsule,
)
from mcoi_runtime.core.command_capability_admission import CommandCapabilityAdmissionGate
from mcoi_runtime.core.domain_capsule_compiler import DomainCapsuleCompiler
from mcoi_runtime.core.governed_capability_registry import GovernedCapabilityRegistry


def build_capability_admission_gate_from_env(
    *,
    clock: Callable[[], str],
) -> CommandCapabilityAdmissionGate | None:
    """Build a gateway capability admission gate from environment configuration."""
    if not _truthy(os.environ.get("MULLU_CAPABILITY_FABRIC_ADMISSION_ENABLED", "")):
        return None

    capsule_path = os.environ.get("MULLU_CAPABILITY_FABRIC_CAPSULE_PATH", "").strip()
    capsule_pack_path = os.environ.get("MULLU_CAPABILITY_FABRIC_CAPSULE_PACK_PATH", "").strip()
    capability_path = os.environ.get("MULLU_CAPABILITY_FABRIC_CAPABILITY_PATH", "").strip()
    capability_pack_path = os.environ.get("MULLU_CAPABILITY_FABRIC_CAPABILITY_PACK_PATH", "").strip()
    if not (capsule_path or capsule_pack_path) or not (capability_path or capability_pack_path):
        raise ValueError("fabric admission requires capsule JSON source and capability JSON source")

    require_certified = not _falsey(os.environ.get("MULLU_CAPABILITY_FABRIC_REQUIRE_CERTIFIED", "true"))
    capsules = _load_capsule_sources(capsule_path=capsule_path, capsule_pack_path=capsule_pack_path)
    loaded_capabilities = _load_capability_sources(
        capability_path=capability_path,
        capability_pack_path=capability_pack_path,
    )

    compiler = DomainCapsuleCompiler(clock=clock)
    registry = GovernedCapabilityRegistry(clock=clock, require_certified=require_certified)
    for capsule in capsules:
        capabilities = _capabilities_referenced_by_capsule(capsule, loaded_capabilities)
        compilation = compiler.compile(capsule, capabilities)
        if not compilation.succeeded:
            raise ValueError(f"fabric capsule compilation failed for {capsule.capsule_id}: {list(compilation.errors)}")
        installation = registry.install(compilation, capabilities)
        if installation.errors:
            raise ValueError(f"fabric capsule installation failed for {capsule.capsule_id}: {list(installation.errors)}")

    return CommandCapabilityAdmissionGate(registry=registry, clock=clock)


def _load_object(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"fabric JSON root must be an object: {path}")
    return payload


def _load_capsule_sources(*, capsule_path: str, capsule_pack_path: str) -> tuple[DomainCapsule, ...]:
    capsules: list[DomainCapsule] = []
    if capsule_path:
        capsules.append(DomainCapsule.from_mapping(_load_object(Path(capsule_path))))
    if capsule_pack_path:
        capsules.extend(_load_capsule_pack(Path(capsule_pack_path)))
    return tuple(capsules)


def _load_capsule_pack(path: Path) -> tuple[DomainCapsule, ...]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        raw_capsules = payload.get("capsules")
    elif isinstance(payload, list):
        raw_capsules = payload
    else:
        raise ValueError(f"fabric capsule pack root must be an object or array: {path}")
    if not isinstance(raw_capsules, list):
        raise ValueError(f"fabric capsule pack must contain a capsules array: {path}")
    capsules: list[DomainCapsule] = []
    for index, raw_capsule in enumerate(raw_capsules):
        if not isinstance(raw_capsule, dict):
            raise ValueError(f"fabric capsule pack entry must be an object: {path} capsules[{index}]")
        capsules.append(DomainCapsule.from_mapping(raw_capsule))
    return tuple(capsules)


def _load_capability_sources(
    *,
    capability_path: str,
    capability_pack_path: str,
) -> tuple[CapabilityRegistryEntry, ...]:
    entries: list[CapabilityRegistryEntry] = []
    if capability_path:
        entries.append(CapabilityRegistryEntry.from_mapping(_load_object(Path(capability_path))))
    if capability_pack_path:
        entries.extend(_load_capability_pack(Path(capability_pack_path)))
    return tuple(entries)


def _load_capability_pack(path: Path) -> tuple[CapabilityRegistryEntry, ...]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        raw_capabilities = payload.get("capabilities")
    elif isinstance(payload, list):
        raw_capabilities = payload
    else:
        raise ValueError(f"fabric capability pack root must be an object or array: {path}")
    if not isinstance(raw_capabilities, list):
        raise ValueError(f"fabric capability pack must contain a capabilities array: {path}")
    entries: list[CapabilityRegistryEntry] = []
    for index, raw_capability in enumerate(raw_capabilities):
        if not isinstance(raw_capability, dict):
            raise ValueError(f"fabric capability pack entry must be an object: {path} capabilities[{index}]")
        entries.append(CapabilityRegistryEntry.from_mapping(raw_capability))
    return tuple(entries)


def _capabilities_referenced_by_capsule(
    capsule: DomainCapsule,
    entries: tuple[CapabilityRegistryEntry, ...],
) -> tuple[CapabilityRegistryEntry, ...]:
    by_id: dict[str, CapabilityRegistryEntry] = {}
    duplicates: list[str] = []
    for entry in entries:
        if entry.capability_id in by_id:
            duplicates.append(entry.capability_id)
        by_id[entry.capability_id] = entry
    if duplicates:
        raise ValueError(f"fabric capability source contains duplicate capability ids: {duplicates}")

    missing = [capability_id for capability_id in capsule.capability_refs if capability_id not in by_id]
    if missing:
        raise ValueError(f"fabric capsule references missing capabilities: {missing}")
    return tuple(by_id[capability_id] for capability_id in capsule.capability_refs)


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _falsey(value: str) -> bool:
    return value.strip().lower() in {"0", "false", "no", "off"}
