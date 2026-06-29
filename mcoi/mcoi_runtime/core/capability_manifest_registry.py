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
from mcoi_runtime.core.causal_repair import (
    EffectClass as CausalRepairEffectClass,
    ReversibilityClass as CausalRepairReversibilityClass,
    SnapshotQuality as CausalRepairSnapshotQuality,
)
from mcoi_runtime.core.repair_template_registry import (
    RepairTemplateRegistry,
    RepairTemplateRegistryError,
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
        errors: list[str] = []
        manifest: CapabilityManifest | None = None
        payload: Mapping[str, Any] | None = None

        try:
            environment = _require_manifest_text(environment, "environment").strip()
        except ValueError as exc:
            environment = ""
            errors.append(f"manifest_parse_error:{exc}")

        try:
            _require_inside_repo(self._repo_root, source_path)
            payload = _load_manifest_payload(source_path)
            manifest = CapabilityManifest.from_mapping(payload)
        except (KeyError, TypeError, ValueError, RuntimeCoreInvariantError, json.JSONDecodeError) as exc:
            errors.append(f"manifest_parse_error:{exc}")

        capability_id = ""
        if isinstance(payload, Mapping):
            capability_id = _optional_manifest_text(payload.get("capability_id"))
        if manifest is not None:
            capability_id = manifest.capability_id
            try:
                errors.extend(
                    self._validation_errors(
                        manifest,
                        environment=environment,
                        hot_reload=hot_reload,
                        source_path=source_path,
                    )
                )
            except RuntimeCoreInvariantError as exc:
                errors.append(f"manifest_validation_error:{exc}")

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
        abi_coverage = _capability_abi_coverage_records(admissions)
        return {
            "manifest_count": len(manifests),
            "admission_count": len(admissions),
            "capability_ids": tuple(manifest["capability_id"] for manifest in manifests),
            "manifests": manifests,
            "admissions": admissions,
            "capability_abi_coverage_status": _capability_abi_coverage_status(abi_coverage),
            "capability_abi_covered_count": sum(
                1 for record in abi_coverage if record["coverage_status"] == "covered"
            ),
            "capability_abi_blocked_count": sum(
                1 for record in abi_coverage if record["coverage_status"] == "blocked"
            ),
            "capability_abi_coverage": abi_coverage,
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
        if hot_reload:
            errors.extend(_hot_reload_metadata_errors(manifest, environment=environment))
        errors.extend(_repair_template_metadata_errors(manifest))
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
        for schema_path in sorted((self._repo_root / "schemas").rglob("*.schema.json")):
            try:
                payload = json.loads(schema_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise RuntimeCoreInvariantError(
                    f"schema_registry_malformed:{_relative_ref(self._repo_root, schema_path)}"
                ) from exc
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


def _require_manifest_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_manifest_text(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return ""


def _has_test_or_proof_evidence(evidence_refs: tuple[str, ...]) -> bool:
    return any(
        ref.startswith(("tests/", "mcoi/tests/", "proof://"))
        for ref in evidence_refs
    )


def _capability_abi_coverage_records(admissions: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for admission in admissions:
        manifest = admission.get("manifest")
        if isinstance(manifest, Mapping):
            records.append(_admitted_capability_abi_record(admission, manifest))
        else:
            records.append(_rejected_capability_abi_record(admission))
    return tuple(sorted(records, key=lambda record: (str(record["capability_id"]), str(record["source_ref"]))))


def _admitted_capability_abi_record(
    admission: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "capability_id": _manifest_record_text(manifest.get("capability_id"), "capability:unknown"),
        "source_ref": _manifest_record_text(admission.get("source_ref"), "source:unknown"),
        "admission_status": "admitted",
        "coverage_status": "covered",
        "reason": "manifest_admitted",
        "maturity": _manifest_record_text(manifest.get("maturity"), "unknown"),
        "risk": _manifest_record_text(manifest.get("risk"), "unknown"),
        "effect_bearing": manifest.get("effect_bearing") is True,
        "sandbox_required": manifest.get("sandbox_required") is True,
        "rollback_required": manifest.get("rollback_required") is True,
        "input_schema_ref": _manifest_record_text(manifest.get("input_schema_ref"), "schema:unknown"),
        "output_schema_ref": _manifest_record_text(manifest.get("output_schema_ref"), "schema:unknown"),
        "receipt_contract_ref": _manifest_record_text(manifest.get("receipt_contract_ref"), "receipt:unknown"),
        "required_gates": _manifest_record_tuple(manifest.get("required_gates", ())),
        "policy_refs": _manifest_record_tuple(manifest.get("policy_refs", ())),
        "evidence_refs": _manifest_record_tuple(manifest.get("evidence_refs", ())),
        "errors": (),
        "warnings": _manifest_record_tuple(admission.get("warnings", ())),
    }


def _rejected_capability_abi_record(admission: Mapping[str, Any]) -> dict[str, Any]:
    errors = _manifest_record_tuple(admission.get("errors", ()))
    return {
        "capability_id": _manifest_record_text(admission.get("capability_id"), "capability:unknown"),
        "source_ref": _manifest_record_text(admission.get("source_ref"), "source:unknown"),
        "admission_status": "rejected",
        "coverage_status": "blocked",
        "reason": "manifest_rejected",
        "maturity": "unknown",
        "risk": "unknown",
        "effect_bearing": False,
        "sandbox_required": False,
        "rollback_required": False,
        "input_schema_ref": "schema:unknown",
        "output_schema_ref": "schema:unknown",
        "receipt_contract_ref": "receipt:unknown",
        "required_gates": (),
        "policy_refs": (),
        "evidence_refs": _manifest_record_tuple((admission.get("source_ref", ""), admission.get("admission_id", ""))),
        "errors": errors,
        "warnings": _manifest_record_tuple(admission.get("warnings", ())),
    }


def _capability_abi_coverage_status(records: tuple[dict[str, Any], ...]) -> str:
    if not records:
        return "empty"
    statuses = {str(record.get("coverage_status", "")) for record in records}
    if statuses == {"covered"}:
        return "complete"
    if "covered" in statuses:
        return "partial"
    return "blocked"


def _manifest_record_text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _manifest_record_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if not isinstance(value, (tuple, list)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _hot_reload_metadata_errors(manifest: CapabilityManifest, *, environment: str) -> tuple[str, ...]:
    metadata = manifest.metadata
    allowed_environments = metadata.get("hot_reload_allowed_environments") if isinstance(metadata, Mapping) else None
    errors: list[str] = []
    if isinstance(allowed_environments, (str, bytes)) or not isinstance(allowed_environments, (tuple, list)):
        errors.append("hot_reload_allowed_environments_required")
    else:
        normalized_allowed: list[str] = []
        for index, item in enumerate(allowed_environments):
            if not isinstance(item, str) or not item.strip():
                errors.append(f"hot_reload_allowed_environments_invalid:{index}")
                continue
            normalized_allowed.append(item.strip())
        if not normalized_allowed:
            errors.append("hot_reload_allowed_environments_required")
        elif environment not in normalized_allowed:
            errors.append(f"hot_reload_environment_not_allowed:{environment}")
    if environment == "production" and metadata.get("production_hot_reload_allowed") is not True:
        errors.append("production_hot_reload_denied_by_manifest_metadata")
    return tuple(errors)


def _repair_template_metadata_errors(manifest: CapabilityManifest) -> tuple[str, ...]:
    metadata = manifest.metadata
    if not isinstance(metadata, Mapping):
        return ("causal_repair_metadata_invalid",)
    keys = {
        "causal_repair_template_domain",
        "causal_repair_template_action_type",
        "causal_repair_effect_class",
        "causal_repair_reversibility_class",
        "causal_repair_snapshot_quality",
        "causal_repair_template_evidence",
        "causal_repair_external_confirmation_refs",
    }
    if not any(key in metadata for key in keys):
        return ()
    errors: list[str] = []
    domain = _metadata_required_text(
        metadata,
        "causal_repair_template_domain",
        errors,
    )
    action_type = _metadata_required_text(
        metadata,
        "causal_repair_template_action_type",
        errors,
    )
    if domain is None or action_type is None:
        return tuple(errors)

    try:
        template = RepairTemplateRegistry.default_registry().get_template(
            domain,
            action_type,
        )
    except RepairTemplateRegistryError:
        errors.append(f"causal_repair_template_unknown:{domain}.{action_type}")
        return tuple(errors)

    effect_class = _metadata_optional_enum(
        metadata,
        "causal_repair_effect_class",
        CausalRepairEffectClass,
        errors,
    )
    if effect_class is not None and effect_class.value != template.effect_class.value:
        errors.append("causal_repair_effect_class_mismatch")
    reversibility_class = _metadata_optional_enum(
        metadata,
        "causal_repair_reversibility_class",
        CausalRepairReversibilityClass,
        errors,
    )
    if (
        reversibility_class is not None
        and reversibility_class.value != template.reversibility_class.value
    ):
        errors.append("causal_repair_reversibility_class_mismatch")

    snapshot_quality = metadata.get("causal_repair_snapshot_quality")
    if snapshot_quality is not None:
        if isinstance(snapshot_quality, bool) or not isinstance(snapshot_quality, int):
            errors.append("causal_repair_snapshot_quality_invalid")
        else:
            try:
                quality = CausalRepairSnapshotQuality(snapshot_quality)
            except ValueError:
                errors.append("causal_repair_snapshot_quality_invalid")
            else:
                if quality < template.snapshot_quality_minimum:
                    errors.append("causal_repair_snapshot_quality_below_template_minimum")

    evidence = _metadata_text_tuple(
        metadata,
        "causal_repair_template_evidence",
        errors,
        required=bool(template.required_evidence),
    )
    if evidence is not None:
        missing_evidence = tuple(
            item for item in template.required_evidence if item not in evidence
        )
        if missing_evidence:
            errors.append(
                "causal_repair_template_evidence_missing:"
                + ",".join(missing_evidence)
            )
    _metadata_text_tuple(
        metadata,
        "causal_repair_external_confirmation_refs",
        errors,
        required=False,
    )
    return tuple(errors)


def _metadata_required_text(
    metadata: Mapping[str, Any],
    key: str,
    errors: list[str],
) -> str | None:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{key}_required")
        return None
    return value.strip()


def _metadata_optional_enum(
    metadata: Mapping[str, Any],
    key: str,
    enum_type: type,
    errors: list[str],
) -> Any | None:
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{key}_invalid")
        return None
    try:
        return enum_type(value)
    except ValueError:
        errors.append(f"{key}_invalid")
        return None


def _metadata_text_tuple(
    metadata: Mapping[str, Any],
    key: str,
    errors: list[str],
    *,
    required: bool,
) -> tuple[str, ...] | None:
    value = metadata.get(key)
    if value is None:
        if required:
            errors.append(f"{key}_required")
        return None
    if isinstance(value, str):
        if not value.strip():
            errors.append(f"{key}_invalid")
            return None
        return (value.strip(),)
    if not isinstance(value, (tuple, list)):
        errors.append(f"{key}_invalid")
        return None
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{key}_invalid:{index}")
            continue
        result.append(item.strip())
    if required and not result:
        errors.append(f"{key}_required")
    return tuple(result)
