"""Gateway low-code builder foundation.

Purpose: compile business-authored builder specs into deterministic governed
    manifests for agents, workflows, policies, capabilities, evals, and
    approval chains.
Governance scope: no-code artifact compilation, manifest completeness,
    high-risk approval gates, eval coverage, and activation blocking.
Dependencies: dataclasses, enum, typing, and command-spine canonical hashing.
Invariants:
  - Builder output is declarative only and cannot execute side effects.
  - Every compiled builder produces the canonical manifest set.
  - High-risk builders require approval roles, evals, receipts, and evidence.
  - Activation remains blocked until certification evidence is present.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any

from gateway.command_spine import canonical_hash


class BuilderArtifactKind(StrEnum):
    """Canonical artifacts emitted by the builder compiler."""

    AGENT = "agent.yaml"
    WORKFLOW = "workflow.yaml"
    POLICY = "policy.yaml"
    CAPABILITY = "capability.yaml"
    EVAL_SUITE = "eval_suite.yaml"
    APPROVAL_CHAIN = "approval_chain.yaml"


class BuilderRisk(StrEnum):
    """Builder risk tier."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BuilderStatus(StrEnum):
    """Compiled builder activation status."""

    DRAFT = "draft"
    CANDIDATE = "candidate"
    CERTIFIED = "certified"
    BLOCKED = "blocked"


_CANONICAL_ARTIFACTS = tuple(BuilderArtifactKind)
_HIGH_RISK = frozenset({BuilderRisk.HIGH, BuilderRisk.CRITICAL})
_REQUIRED_HIGH_RISK_EVALS = frozenset({"tenant_isolation", "approval_required", "prompt_injection", "evidence_integrity"})


@dataclass(frozen=True, slots=True)
class BuilderAppSpec:
    """Business-authored source spec for one governed builder app."""

    app_id: str
    display_name: str
    domain: str
    owner_team: str
    risk: BuilderRisk
    goals: tuple[str, ...]
    workflows: tuple[str, ...]
    connectors: tuple[str, ...]
    policies: tuple[str, ...]
    eval_suites: tuple[str, ...]
    approval_roles: tuple[str, ...]
    capability_scopes: tuple[str, ...]
    evidence_exports: tuple[str, ...]
    receipt_required: bool = True
    certification_evidence_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("app_id", "display_name", "domain", "owner_team"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.risk, BuilderRisk):
            raise ValueError("builder_risk_invalid")
        for field_name in ("goals", "workflows", "policies", "eval_suites", "capability_scopes", "evidence_exports"):
            object.__setattr__(self, field_name, _normalize_text_tuple(getattr(self, field_name), field_name))
        for field_name in ("connectors", "approval_roles", "certification_evidence_refs"):
            object.__setattr__(self, field_name, _normalize_text_tuple(getattr(self, field_name), field_name, allow_empty=True))
        if self.risk in _HIGH_RISK and not self.approval_roles:
            raise ValueError("high_risk_builder_requires_approval_roles")
        if self.risk in _HIGH_RISK and self.receipt_required is not True:
            raise ValueError("high_risk_builder_requires_receipts")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class BuilderManifestArtifact:
    """One deterministic compiled builder manifest."""

    artifact_id: str
    kind: BuilderArtifactKind
    path: str
    content: dict[str, Any]
    artifact_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.artifact_id, "artifact_id")
        if not isinstance(self.kind, BuilderArtifactKind):
            raise ValueError("builder_artifact_kind_invalid")
        _require_text(self.path, "path")
        if self.path != self.kind.value:
            raise ValueError("builder_artifact_path_must_match_kind")
        object.__setattr__(self, "content", dict(self.content))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class BuilderCompilation:
    """Compiled builder output and activation decision."""

    compilation_id: str
    app_id: str
    status: BuilderStatus
    artifacts: tuple[BuilderManifestArtifact, ...]
    activation_blocked: bool
    blocked_reasons: tuple[str, ...]
    certification_evidence_refs: tuple[str, ...]
    compiled_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.compilation_id, "compilation_id")
        _require_text(self.app_id, "app_id")
        if not isinstance(self.status, BuilderStatus):
            raise ValueError("builder_status_invalid")
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "blocked_reasons", _normalize_text_tuple(self.blocked_reasons, "blocked_reasons", allow_empty=True))
        object.__setattr__(self, "certification_evidence_refs", _normalize_text_tuple(self.certification_evidence_refs, "certification_evidence_refs", allow_empty=True))
        if {artifact.kind for artifact in self.artifacts} != set(_CANONICAL_ARTIFACTS):
            raise ValueError("canonical_builder_artifacts_required")
        if not self.activation_blocked and self.status != BuilderStatus.CERTIFIED:
            raise ValueError("activation_requires_certified_builder")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class BuilderCatalogSnapshot:
    """Operator read model for low-code builder outputs."""

    catalog_id: str
    compilations: tuple[BuilderCompilation, ...]
    total_apps: int
    activation_blocked_count: int
    certified_count: int
    canonical_artifact_count: int
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.catalog_id, "catalog_id")
        object.__setattr__(self, "compilations", tuple(self.compilations))
        for field_name in ("total_apps", "activation_blocked_count", "certified_count", "canonical_artifact_count"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name}_non_negative")

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


class LowCodeBuilderCompiler:
    """Compile business app specs into governed builder manifests."""

    def __init__(self, *, catalog_id: str = "low-code-builder-catalog") -> None:
        self._catalog_id = catalog_id
        self._compilations: list[BuilderCompilation] = []

    def compile(self, spec: BuilderAppSpec) -> BuilderCompilation:
        """Compile one app spec into canonical activation-blocked manifests."""
        blocked_reasons = _blocked_reasons(spec)
        status = BuilderStatus.CERTIFIED if not blocked_reasons else BuilderStatus.BLOCKED
        artifacts = tuple(_stamp_artifact(artifact) for artifact in _artifacts_for(spec))
        compilation = BuilderCompilation(
            compilation_id="pending",
            app_id=spec.app_id,
            status=status,
            artifacts=artifacts,
            activation_blocked=bool(blocked_reasons),
            blocked_reasons=blocked_reasons,
            certification_evidence_refs=spec.certification_evidence_refs,
            metadata={
                "compiled_from": "builder_app_spec",
                "builder_is_declarative_only": True,
                "side_effect_execution_allowed": False,
                **spec.metadata,
            },
        )
        stamped = _stamp_compilation(compilation)
        self._compilations.append(stamped)
        return stamped

    def snapshot(self) -> BuilderCatalogSnapshot:
        """Return a stamped builder catalog snapshot."""
        compilations = tuple(sorted(self._compilations, key=lambda item: item.app_id))
        snapshot = BuilderCatalogSnapshot(
            catalog_id=self._catalog_id,
            compilations=compilations,
            total_apps=len(compilations),
            activation_blocked_count=sum(1 for item in compilations if item.activation_blocked),
            certified_count=sum(1 for item in compilations if item.status == BuilderStatus.CERTIFIED),
            canonical_artifact_count=sum(len(item.artifacts) for item in compilations),
        )
        payload = snapshot.to_json_dict()
        payload["snapshot_hash"] = ""
        return replace(snapshot, snapshot_hash=canonical_hash(payload))


def builder_catalog_snapshot_to_json_dict(snapshot: BuilderCatalogSnapshot) -> dict[str, Any]:
    """Return the public JSON-contract representation of builder state."""
    return snapshot.to_json_dict()


def _artifacts_for(spec: BuilderAppSpec) -> tuple[BuilderManifestArtifact, ...]:
    common = {
        "app_id": spec.app_id,
        "display_name": spec.display_name,
        "domain": spec.domain,
        "owner_team": spec.owner_team,
        "risk": spec.risk.value,
    }
    return (
        _artifact(spec, BuilderArtifactKind.AGENT, {**common, "goals": spec.goals, "capability_scopes": spec.capability_scopes}),
        _artifact(spec, BuilderArtifactKind.WORKFLOW, {**common, "workflows": spec.workflows, "connectors": spec.connectors}),
        _artifact(spec, BuilderArtifactKind.POLICY, {**common, "policies": spec.policies, "receipt_required": spec.receipt_required}),
        _artifact(spec, BuilderArtifactKind.CAPABILITY, {**common, "capability_scopes": spec.capability_scopes, "connectors": spec.connectors}),
        _artifact(spec, BuilderArtifactKind.EVAL_SUITE, {**common, "eval_suites": spec.eval_suites, "required_for_promotion": True}),
        _artifact(spec, BuilderArtifactKind.APPROVAL_CHAIN, {**common, "approval_roles": spec.approval_roles, "evidence_exports": spec.evidence_exports}),
    )


def _artifact(spec: BuilderAppSpec, kind: BuilderArtifactKind, content: dict[str, Any]) -> BuilderManifestArtifact:
    return BuilderManifestArtifact(
        artifact_id=f"{spec.app_id}:{kind.value}",
        kind=kind,
        path=kind.value,
        content={
            **content,
            "manifest_version": 1,
            "generated_by": "mullu_low_code_builder",
            "declarative_only": True,
        },
    )


def _blocked_reasons(spec: BuilderAppSpec) -> tuple[str, ...]:
    reasons: list[str] = []
    if not spec.certification_evidence_refs:
        reasons.append("certification_evidence_missing")
    if spec.risk in _HIGH_RISK:
        missing_evals = sorted(_REQUIRED_HIGH_RISK_EVALS.difference(spec.eval_suites))
        if missing_evals:
            reasons.append("high_risk_eval_coverage_missing")
        if "terminal_certificate_export" not in spec.evidence_exports:
            reasons.append("terminal_certificate_export_required")
        if not spec.approval_roles:
            reasons.append("approval_chain_required")
        if spec.receipt_required is not True:
            reasons.append("receipt_contract_required")
    return tuple(dict.fromkeys(reasons))


def _stamp_artifact(artifact: BuilderManifestArtifact) -> BuilderManifestArtifact:
    payload = artifact.to_json_dict()
    payload["artifact_hash"] = ""
    return replace(artifact, artifact_hash=canonical_hash(payload))


def _stamp_compilation(compilation: BuilderCompilation) -> BuilderCompilation:
    payload = compilation.to_json_dict()
    payload["compiled_hash"] = ""
    compiled_hash = canonical_hash(payload)
    return replace(compilation, compilation_id=f"builder-compilation-{compiled_hash[:16]}", compiled_hash=compiled_hash)


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _json_ready(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
