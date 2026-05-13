"""Purpose: governed loader and admission registry for capability manifests.
Governance scope: manifest parsing, schema reference resolution, environment
    admission, hot-reload denial, sandbox/rollback enforcement, and read models.
Dependencies: standard JSON/YAML loading, pathlib, and capability manifest contracts.
Invariants:
  - Invalid manifests produce rejected admissions with explicit errors.
  - Schema and receipt refs must resolve to repository files or schema URNs.
  - Effect-bearing capabilities require sandbox and rollback declarations.
  - Production hot reload is denied for effect-bearing capabilities.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.capability_manifest import (
    CapabilityManifest,
    CapabilityManifestAdmission,
    CapabilityManifestAdmissionStatus,
    CapabilityManifestMaturity,
    CapabilityManifestRisk,
)

from .invariants import RuntimeCoreInvariantError, stable_identifier


_PRODUCTION_MATURITY = frozenset(
    {
        CapabilityManifestMaturity.C6,
        CapabilityManifestMaturity.C7,
    }
)
_EFFECT_RISKS = frozenset(
    {
        CapabilityManifestRisk.MEDIUM,
        CapabilityManifestRisk.HIGH,
        CapabilityManifestRisk.CRITICAL,
    }
)


class CapabilityManifestRegistry:
    """Load and admit governed capability manifests."""

    def __init__(self, *, repo_root: Path, clock: Callable[[], str]) -> None:
        self._repo_root = repo_root.resolve()
        self._clock = clock
        self._manifests: dict[str, CapabilityManifest] = {}
        self._admissions: dict[str, CapabilityManifestAdmission] = {}

    @property
    def manifest_count(self) -> int:
        return len(self._manifests)

    def admit_directory(
        self,
        directory: Path,
        *,
        environment: str,
        hot_reload: bool = False,
    ) -> tuple[CapabilityManifestAdmission, ...]:
        """Admit all checked-in manifest files in deterministic path order."""
        manifest_paths = sorted(
            path
            for path in directory.iterdir()
            if path.name.endswith((".capability.json", ".capability.yaml", ".capability.yml"))
        )
        return tuple(
            self.admit_path(path, environment=environment, hot_reload=hot_reload)
            for path in manifest_paths
        )

    def admit_path(
        self,
        path: Path,
        *,
        environment: str,
        hot_reload: bool = False,
    ) -> CapabilityManifestAdmission:
        """Parse, validate, and conditionally admit one manifest path."""
        source_path = path.resolve()
        environment = str(environment).strip()
        errors: list[str] = []
        manifest: CapabilityManifest | None = None
        payload: Mapping[str, Any] | None = None

        try:
            _require_inside_repo(self._repo_root, source_path)
            payload = _load_manifest_payload(source_path)
            manifest = CapabilityManifest.from_mapping(payload)
        except (KeyError, TypeError, ValueError, RuntimeCoreInvariantError, json.JSONDecodeError) as exc:
            errors.append(f"manifest_parse_error:{exc}")

        capability_id = ""
        if isinstance(payload, Mapping):
            capability_id = str(payload.get("capability_id") or "")
        if manifest is not None:
            capability_id = manifest.capability_id
            errors.extend(
                self._validation_errors(
                    manifest,
                    environment=environment,
                    hot_reload=hot_reload,
                    source_path=source_path,
                )
            )

        status = CapabilityManifestAdmissionStatus.REJECTED if errors else CapabilityManifestAdmissionStatus.ADMITTED
        now = self._clock()
        admission = CapabilityManifestAdmission(
            admission_id=stable_identifier(
                "capability-manifest-admission",
                {
                    "source": _relative_ref(self._repo_root, source_path),
                    "environment": environment,
                    "hot_reload": hot_reload,
                    "admitted_at": now,
                },
            ),
            status=status,
            capability_id=capability_id or "unknown",
            environment=environment or "unknown",
            source_ref=_relative_ref(self._repo_root, source_path),
            manifest=manifest if status is CapabilityManifestAdmissionStatus.ADMITTED else None,
            errors=tuple(errors),
            warnings=(),
            admitted_at=now,
        )
        self._admissions[admission.admission_id] = admission
        if status is CapabilityManifestAdmissionStatus.ADMITTED and manifest is not None:
            self._manifests[manifest.capability_id] = manifest
        return admission

    def get_manifest(self, capability_id: str) -> CapabilityManifest:
        """Return one admitted manifest by capability id."""
        manifest = self._manifests.get(capability_id)
        if manifest is None:
            raise RuntimeCoreInvariantError("unknown capability manifest")
        return manifest

    def read_model(self) -> dict[str, Any]:
        """Return a deterministic operator read model for admitted manifests."""
        manifests = tuple(
            self._manifests[capability_id].to_json_dict()
            for capability_id in sorted(self._manifests)
        )
        admissions = tuple(
            self._admissions[admission_id].to_json_dict()
            for admission_id in sorted(self._admissions)
        )
        return {
            "manifest_count": len(manifests),
            "admission_count": len(admissions),
            "capability_ids": tuple(manifest["capability_id"] for manifest in manifests),
            "manifests": manifests,
            "admissions": admissions,
        }

    def _validation_errors(
        self,
        manifest: CapabilityManifest,
        *,
        environment: str,
        hot_reload: bool,
        source_path: Path,
    ) -> list[str]:
        errors: list[str] = []
        if not environment:
            errors.append("environment_required")
        elif environment not in manifest.allowed_environments:
            errors.append(f"environment_not_allowed:{environment}")
        if manifest.capability_id in self._manifests:
            errors.append(f"capability_manifest_already_admitted:{manifest.capability_id}")
        if manifest.effect_bearing and not manifest.sandbox_required:
            errors.append("effect_bearing_capability_requires_sandbox")
        if manifest.effect_bearing and not manifest.rollback_required:
            errors.append("effect_bearing_capability_requires_rollback")
        if manifest.effect_bearing and manifest.risk in _EFFECT_RISKS and not manifest.policy_refs:
            errors.append("effect_bearing_capability_requires_policy_refs")
        if hot_reload and environment == "production" and manifest.effect_bearing:
            errors.append("production_hot_reload_denied_for_effect_bearing_capability")
        if environment == "production" and manifest.maturity not in _PRODUCTION_MATURITY:
            errors.append("production_environment_requires_C6_or_C7_maturity")
        for field_name, schema_ref in (
            ("input_schema_ref", manifest.input_schema_ref),
            ("output_schema_ref", manifest.output_schema_ref),
            ("receipt_contract_ref", manifest.receipt_contract_ref),
        ):
            if not self._schema_ref_exists(schema_ref):
                errors.append(f"{field_name}_unresolved:{schema_ref}")
        if not _has_test_or_proof_evidence(manifest.evidence_refs):
            errors.append("test_or_proof_evidence_required")
        if source_path.name != _expected_manifest_filename(manifest.capability_id):
            errors.append("manifest_filename_must_match_capability_id")
        return errors

    def _schema_ref_exists(self, schema_ref: str) -> bool:
        if schema_ref.startswith("urn:"):
            return schema_ref in self._schema_ids()
        relative = Path(schema_ref)
        if relative.is_absolute() or ".." in relative.parts:
            return False
        candidate = (self._repo_root / relative).resolve()
        try:
            _require_inside_repo(self._repo_root, candidate)
        except RuntimeCoreInvariantError:
            return False
        return candidate.is_file()

    def _schema_ids(self) -> set[str]:
        schema_ids: set[str] = set()
        for schema_path in (self._repo_root / "schemas").rglob("*.schema.json"):
            try:
                payload = json.loads(schema_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            schema_id = payload.get("$id") if isinstance(payload, dict) else None
            if isinstance(schema_id, str):
                schema_ids.add(schema_id)
        return schema_ids


def _load_manifest_payload(path: Path) -> Mapping[str, Any]:
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
    elif path.suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeCoreInvariantError("YAML capability manifests require PyYAML") from exc
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        raise RuntimeCoreInvariantError("unsupported capability manifest file type")
    if not isinstance(payload, Mapping):
        raise RuntimeCoreInvariantError("capability manifest root must be an object")
    return payload


def _require_inside_repo(repo_root: Path, path: Path) -> None:
    try:
        path.relative_to(repo_root)
    except ValueError as exc:
        raise RuntimeCoreInvariantError("capability manifest path must stay inside repository") from exc


def _relative_ref(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _expected_manifest_filename(capability_id: str) -> str:
    return capability_id.replace(".", "_") + ".capability.json"


def _has_test_or_proof_evidence(evidence_refs: tuple[str, ...]) -> bool:
    return any(
        ref.startswith(("tests/", "mcoi/tests/", "proof://"))
        for ref in evidence_refs
    )
