"""Purpose: runtime registry for compiled governed capability fabric artifacts.
Governance scope: install compiled domain capsules, index admitted capabilities,
    preserve compiler artifacts, and expose query surfaces for command admission.
Dependencies: governed capability fabric contracts and runtime invariant helpers.
Invariants:
  - Failed compilations are never installed.
  - Strict admission requires warning-free certified compilation results.
  - Duplicate capsule or capability installation is rejected.
  - Registry install independently verifies artifact provenance and manifest
    relations before admitting capabilities.
  - Queries return immutable contract values or tuples only.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityRegistryEntry,
    CapsuleAdmissionStatus,
    CapsuleCompilationResult,
    CapsuleCompilerArtifact,
    CapsuleInstallationRecord,
    GovernedCapabilityRecord,
)

from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


class GovernedCapabilityRegistry:
    """Install and query compiled governed capability fabric artifacts."""

    def __init__(self, *, clock: Callable[[], str], require_certified: bool = True) -> None:
        if not isinstance(require_certified, bool):
            raise RuntimeCoreInvariantError("require_certified must be a boolean")
        self._clock = clock
        self._require_certified = require_certified
        self._installations: dict[str, CapsuleInstallationRecord] = {}
        self._capabilities: dict[str, CapabilityRegistryEntry] = {}
        self._capability_to_capsule: dict[str, str] = {}
        self._domain_to_capability_ids: dict[str, set[str]] = {}
        self._artifacts: dict[str, CapsuleCompilerArtifact] = {}
        self._capsule_to_artifact_ids: dict[str, tuple[str, ...]] = {}

    @property
    def capsule_count(self) -> int:
        return len(self._installations)

    @property
    def capability_count(self) -> int:
        return len(self._capabilities)

    @property
    def artifact_count(self) -> int:
        return len(self._artifacts)

    def install(
        self,
        result: CapsuleCompilationResult,
        registry_entries: tuple[CapabilityRegistryEntry, ...],
    ) -> CapsuleInstallationRecord:
        """Install a successful capsule compilation result into the registry."""
        now = self._clock()
        errors = self._admission_errors(result, registry_entries)
        if errors:
            return CapsuleInstallationRecord(
                installation_id=_installation_id(result.capsule_id, now),
                capsule_id=result.capsule_id,
                status=CapsuleAdmissionStatus.REJECTED,
                capability_ids=tuple(entry.capability_id for entry in registry_entries),
                artifact_ids=tuple(artifact.artifact_id for artifact in result.artifacts),
                warnings=result.warnings,
                errors=tuple(errors),
                installed_at=now,
            )

        capability_ids = tuple(entry.capability_id for entry in registry_entries)
        artifact_ids = tuple(artifact.artifact_id for artifact in result.artifacts)
        record = CapsuleInstallationRecord(
            installation_id=_installation_id(result.capsule_id, now),
            capsule_id=result.capsule_id,
            status=CapsuleAdmissionStatus.INSTALLED,
            capability_ids=capability_ids,
            artifact_ids=artifact_ids,
            warnings=result.warnings,
            errors=(),
            installed_at=now,
        )
        self._installations[result.capsule_id] = record
        self._capsule_to_artifact_ids[result.capsule_id] = artifact_ids
        for artifact in result.artifacts:
            self._artifacts[artifact.artifact_id] = artifact
        for entry in registry_entries:
            self._capabilities[entry.capability_id] = entry
            self._capability_to_capsule[entry.capability_id] = result.capsule_id
            self._domain_to_capability_ids.setdefault(entry.domain, set()).add(entry.capability_id)
        return record

    def get_capability(self, capability_id: str) -> CapabilityRegistryEntry:
        """Return an admitted capability by id."""
        capability_id = ensure_non_empty_text("capability_id", capability_id)
        entry = self._capabilities.get(capability_id)
        if entry is None:
            raise RuntimeCoreInvariantError("Unknown capability_id")
        return entry

    def capabilities_for_domain(self, domain: str) -> tuple[CapabilityRegistryEntry, ...]:
        """Return admitted capabilities for one domain, sorted by capability id."""
        domain = ensure_non_empty_text("domain", domain)
        capability_ids = sorted(self._domain_to_capability_ids.get(domain, set()))
        return tuple(self._capabilities[capability_id] for capability_id in capability_ids)

    def installation_for_capsule(self, capsule_id: str) -> CapsuleInstallationRecord:
        """Return the installation record for a capsule."""
        capsule_id = ensure_non_empty_text("capsule_id", capsule_id)
        record = self._installations.get(capsule_id)
        if record is None:
            raise RuntimeCoreInvariantError("Unknown capsule_id")
        return record

    def artifacts_for_capsule(self, capsule_id: str) -> tuple[CapsuleCompilerArtifact, ...]:
        """Return compiler artifacts installed for a capsule."""
        capsule_id = ensure_non_empty_text("capsule_id", capsule_id)
        artifact_ids = self._capsule_to_artifact_ids.get(capsule_id)
        if artifact_ids is None:
            raise RuntimeCoreInvariantError("Unknown capsule_id")
        return tuple(self._artifacts[artifact_id] for artifact_id in artifact_ids)

    def capsule_for_capability(self, capability_id: str) -> str:
        """Return the owning capsule id for an admitted capability."""
        capability_id = ensure_non_empty_text("capability_id", capability_id)
        capsule_id = self._capability_to_capsule.get(capability_id)
        if capsule_id is None:
            raise RuntimeCoreInvariantError("Unknown capability_id")
        return capsule_id

    def read_model(self) -> dict[str, Any]:
        """Return a deterministic operator read model for installed fabric state."""
        installations = tuple(
            self._installations[capsule_id].to_json_dict()
            for capsule_id in sorted(self._installations)
        )
        capabilities = tuple(
            {
                **self._capabilities[capability_id].to_json_dict(),
                "capsule_id": self._capability_to_capsule[capability_id],
            }
            for capability_id in sorted(self._capabilities)
        )
        governed_capability_records = tuple(
            GovernedCapabilityRecord.from_registry_entry(self._capabilities[capability_id]).to_json_dict()
            for capability_id in sorted(self._capabilities)
        )
        domains = tuple(
            {
                "domain": domain,
                "capability_ids": tuple(sorted(capability_ids)),
            }
            for domain, capability_ids in sorted(self._domain_to_capability_ids.items())
        )
        return {
            "require_certified": self._require_certified,
            "capsule_count": self.capsule_count,
            "capability_count": self.capability_count,
            "artifact_count": self.artifact_count,
            "installations": installations,
            "capabilities": capabilities,
            "governed_capability_records": governed_capability_records,
            "domains": domains,
        }

    def _admission_errors(
        self,
        result: CapsuleCompilationResult,
        registry_entries: tuple[CapabilityRegistryEntry, ...],
    ) -> list[str]:
        errors: list[str] = []
        if not result.succeeded:
            errors.append("compilation did not succeed")
        if self._require_certified and result.warnings:
            errors.append("strict admission requires certified capsule and capabilities")
        if result.capsule_id in self._installations:
            errors.append(f"capsule already installed: {result.capsule_id}")

        artifact_ids = [artifact.artifact_id for artifact in result.artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            errors.append("compilation result contains duplicate artifact ids")
        for artifact in result.artifacts:
            if artifact.source_capsule_id != result.capsule_id:
                errors.append(
                    f"artifact source capsule mismatch: {artifact.artifact_id} has "
                    f"{artifact.source_capsule_id}, expected {result.capsule_id}"
                )

        capability_ids = [entry.capability_id for entry in registry_entries]
        if len(capability_ids) != len(set(capability_ids)):
            errors.append("install request contains duplicate capability ids")
        for capability_id in capability_ids:
            if capability_id in self._capabilities:
                errors.append(f"capability already installed: {capability_id}")

        manifest_capability_ids = _manifest_capability_ids(result)
        if manifest_capability_ids is None:
            errors.append("compilation result is missing capability registry manifest")
        elif tuple(capability_ids) != manifest_capability_ids:
            errors.append("install request capability ids do not match compilation manifest")
        errors.extend(_manifest_entry_relation_errors(result, registry_entries))
        errors.extend(_obligation_owner_relation_errors(result, registry_entries))
        return errors


def _installation_id(capsule_id: str, installed_at: str) -> str:
    return stable_identifier(
        "capsule-installation",
        {
            "capsule_id": capsule_id,
            "installed_at": installed_at,
        },
    )


def _manifest_capability_ids(result: CapsuleCompilationResult) -> tuple[str, ...] | None:
    for artifact in result.artifacts:
        if artifact.artifact_type == "capability_registry_manifest":
            capability_ids = artifact.payload.get("capability_ids")
            if not isinstance(capability_ids, (list, tuple)):
                return None
            return tuple(str(capability_id) for capability_id in capability_ids)
    return None


def _manifest_entry_relation_errors(
    result: CapsuleCompilationResult,
    registry_entries: tuple[CapabilityRegistryEntry, ...],
) -> list[str]:
    errors: list[str] = []
    manifest_entries = _manifest_registry_entries(result)
    if manifest_entries is None:
        errors.append("capability registry manifest is missing registry entries")
        return errors
    if len(manifest_entries) != len(registry_entries):
        errors.append("capability registry manifest entry count does not match install request")
        return errors

    requested_entries = {entry.capability_id: entry for entry in registry_entries}
    for raw_entry in manifest_entries:
        if not isinstance(raw_entry, Mapping):
            errors.append("capability registry manifest entry must be an object")
            continue
        capability_id = str(raw_entry.get("capability_id", ""))
        requested = requested_entries.get(capability_id)
        if requested is None:
            errors.append(f"capability registry manifest contains unrequested capability: {capability_id}")
            continue
        if raw_entry.get("domain") != requested.domain:
            errors.append(
                f"capability registry manifest domain mismatch: {capability_id} has "
                f"{raw_entry.get('domain')}, expected {requested.domain}"
            )
        if raw_entry.get("version") != requested.version:
            errors.append(
                f"capability registry manifest version mismatch: {capability_id} has "
                f"{raw_entry.get('version')}, expected {requested.version}"
            )
    return errors


def _obligation_owner_relation_errors(
    result: CapsuleCompilationResult,
    registry_entries: tuple[CapabilityRegistryEntry, ...],
) -> list[str]:
    owner_team = _obligation_manifest_owner_team(result)
    if owner_team is None:
        return ["compilation result is missing obligation template manifest owner team"]
    errors: list[str] = []
    for entry in registry_entries:
        if entry.obligation_model.owner_team != owner_team:
            errors.append(
                f"capability owner team mismatch: {entry.capability_id} has "
                f"{entry.obligation_model.owner_team}, expected {owner_team}"
            )
    return errors


def _manifest_registry_entries(result: CapsuleCompilationResult) -> tuple[Mapping[str, Any], ...] | None:
    for artifact in result.artifacts:
        if artifact.artifact_type == "capability_registry_manifest":
            registry_entries = artifact.payload.get("registry_entries")
            if not isinstance(registry_entries, (list, tuple)):
                return None
            return tuple(entry for entry in registry_entries if isinstance(entry, Mapping))
    return None


def _obligation_manifest_owner_team(result: CapsuleCompilationResult) -> str | None:
    for artifact in result.artifacts:
        if artifact.artifact_type == "obligation_template_manifest":
            owner_team = artifact.payload.get("owner_team")
            if not isinstance(owner_team, str) or not owner_team:
                return None
            return owner_team
    return None
