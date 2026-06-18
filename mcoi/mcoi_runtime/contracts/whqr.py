"""Purpose: typed WHQR semantic query contract for governed meaning before MIL execution.
Governance scope: side-effect-free question roles, connectors, modality, and split gate outcomes.
Dependencies: Python dataclasses, enums, JSON, and hashing.
Invariants: truth, norm, and evidence are separate; WHQR expressions are immutable and canonically serialized.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping, Sequence, TypeAlias, TypeVar
import hashlib
import json


WHQR_VERSION = "0.1.0"
SEMANTICS_HASH = (
    "sha256:a11656674c84e7dde0a0351af3805e2362429c570a97f256ff6ffded1698dc88"
)
_EnumT = TypeVar("_EnumT", bound=StrEnum)


class WHRole(StrEnum):
    # Additive vocabulary only: split-gate semantics are unchanged, so
    # SEMANTICS_HASH is intentionally NOT bumped (bumping would invalidate
    # every already-persisted WHQR document hash for no semantic gain).
    WHO = "who"
    WHAT = "what"
    WHY = "why"
    WHEN = "when"
    WHERE = "where"
    HOW = "how"
    WHICH = "which"
    HOW_MUCH = "how_much"
    UNDER_WHAT_CONDITIONS = "under_what_conditions"
    WHOM = "whom"
    WHOSE = "whose"
    HOW_MANY = "how_many"
    HOW_LONG = "how_long"
    HOW_OFTEN = "how_often"
    WHAT_IF = "what_if"
    WHY_NOT = "why_not"
    WHAT_ELSE = "what_else"
    SO_WHAT = "so_what"
    BY_WHAT_MEANS = "by_what_means"
    ACCORDING_TO_WHOM = "according_to_whom"


class LogicalOp(StrEnum):
    AND = "and"
    OR = "or"
    NOT = "not"
    IMPLIES = "implies"
    IFF = "iff"
    XOR = "xor"


class Connector(StrEnum):
    BECAUSE = "because"
    THEREFORE = "therefore"
    DESPITE = "despite"
    UNLESS = "unless"
    UNTIL = "until"
    WHILE = "while"
    BEFORE = "before"
    AFTER = "after"
    GIVEN = "given"
    ASSUMING = "assuming"


class TruthGate(StrEnum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class NormGate(StrEnum):
    PERMITTED = "permitted"
    FORBIDDEN = "forbidden"
    ESCALATE = "escalate"
    REQUIRES_APPROVAL = "requires_approval"


class EvidenceGate(StrEnum):
    PROVEN = "proven"
    UNPROVEN = "unproven"
    STALE = "stale"
    CONTRADICTED = "contradicted"
    BUDGET_UNKNOWN = "budget_unknown"
    FORBIDDEN_UNKNOWN = "forbidden_unknown"


class Adverb(StrEnum):
    ALWAYS = "always"
    NEVER = "never"
    OFTEN = "often"
    SOMETIMES = "sometimes"
    RARELY = "rarely"
    CERTAINLY = "certainly"
    POSSIBLY = "possibly"
    NECESSARILY = "necessarily"


class Quantifier(StrEnum):
    EXISTS = "exists"
    FORALL = "forall"
    EXACTLY_ONE = "exactly_one"
    AT_LEAST_N = "at_least_n"
    LATEST = "latest"
    CURRENT = "current"
    AUTHORIZED = "authorized"


ADVERB_THRESHOLDS: Mapping[Adverb, tuple[float, float]] = {
    Adverb.ALWAYS: (1.0, 1.0),
    Adverb.CERTAINLY: (0.99, 1.0),
    Adverb.OFTEN: (0.70, 1.0),
    Adverb.SOMETIMES: (0.30, 1.0),
    Adverb.RARELY: (0.0, 0.10),
    Adverb.NEVER: (0.0, 0.0),
    Adverb.POSSIBLY: (0.01, 1.0),
    Adverb.NECESSARILY: (1.0, 1.0),
}


def _require_text(value: str, name: str) -> str:
    if not isinstance(value, str) or value == "" or value.strip() == "":
        raise ValueError(f"{name} must be a non-empty string and must not be blank")
    return value


def _is_sha256_digest_ref(value: str) -> bool:
    prefix = "sha256:"
    if not value.startswith(prefix):
        return False
    digest = value.removeprefix(prefix)
    return len(digest) == 64 and all(char in "0123456789abcdef" for char in digest)


def _freeze_metadata(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be a mapping")
    rows: dict[str, Any] = {}
    for key, value in metadata.items():
        rows[_require_text(key, "metadata key")] = _freeze_metadata_value(value)
    return MappingProxyType(dict(sorted(rows.items(), key=lambda item: item[0])))


def _freeze_metadata_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_metadata(value)
    if isinstance(value, tuple):
        return tuple(_freeze_metadata_value(item) for item in value)
    if isinstance(value, list):
        return tuple(_freeze_metadata_value(item) for item in value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("metadata value must be a finite number")
        return value
    raise ValueError("metadata value must be canonical JSON-compatible")


def _require_whqr_expr(value: Any, name: str) -> None:
    if not isinstance(value, (WHQRNode, LogicalExpr, ConnectorExpr)):
        raise ValueError(f"{name} must be a WHQR expression")


def _require_optional_text(value: Any, name: str) -> None:
    if value is not None:
        _require_text(value, name)


def _require_metadata_tree(metadata: Any, name: str) -> None:
    if not isinstance(metadata, Mapping):
        raise ValueError(f"{name} metadata must be a mapping")
    if not isinstance(metadata, MappingProxyType):
        raise ValueError(f"{name} metadata must be immutable")
    for key, value in metadata.items():
        _require_text(key, "metadata key")
        _require_metadata_value_tree(value, name)


def _require_metadata_value_tree(value: Any, name: str) -> None:
    if isinstance(value, Mapping):
        _require_metadata_tree(value, name)
        return
    if isinstance(value, tuple):
        for item in value:
            _require_metadata_value_tree(item, name)
        return
    if isinstance(value, list):
        raise ValueError(f"{name} metadata value must be immutable")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{name} metadata value must be a finite number")
        return
    raise ValueError(f"{name} metadata value must be canonical JSON-compatible")


def _require_whqr_expr_tree(value: Any, name: str) -> None:
    _require_whqr_expr(value, name)
    if isinstance(value, WHQRNode):
        if not isinstance(value.role, WHRole):
            raise ValueError(f"{name}.role must be a WHRole value")
        _require_text(value.target, f"{name}.target")
        _require_optional_text(value.node_id, f"{name}.node_id")
        _require_optional_text(value.scope, f"{name}.scope")
        if value.modality is not None and not isinstance(value.modality, Adverb):
            raise ValueError(f"{name}.modality must be an Adverb value")
        _require_optional_text(value.expected_type, f"{name}.expected_type")
        if value.quantifier is not None and not isinstance(value.quantifier, Quantifier):
            raise ValueError(f"{name}.quantifier must be a Quantifier value")
        _require_optional_text(value.entity_ref, f"{name}.entity_ref")
        _require_optional_text(value.evidence_ref, f"{name}.evidence_ref")
        _require_metadata_tree(value.metadata, name)
        return
    if isinstance(value, LogicalExpr):
        if not isinstance(value.op, LogicalOp):
            raise ValueError(f"{name}.op must be a LogicalOp value")
        if not isinstance(value.args, tuple):
            raise ValueError(f"{name}.args must be an immutable tuple")
        if not value.args:
            raise ValueError(f"{name}.args must contain at least one WHQR expression")
        if value.op == LogicalOp.NOT and len(value.args) != 1:
            raise ValueError(f"{name}.not requires exactly one WHQR expression")
        if value.op != LogicalOp.NOT and len(value.args) < 2:
            raise ValueError(f"{name}.logical operators except not require at least two WHQR expressions")
        for index, arg in enumerate(value.args):
            _require_whqr_expr_tree(arg, f"{name}.args[{index}]")
        return
    if not isinstance(value.connector, Connector):
        raise ValueError(f"{name}.connector must be a Connector value")
    _require_whqr_expr_tree(value.left, f"{name}.left")
    _require_whqr_expr_tree(value.right, f"{name}.right")


def _require_mapping_payload(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _require_allowed_keys(value: Mapping[str, Any], name: str, allowed: set[str]) -> None:
    unknown = sorted(str(key) for key in value.keys() if key not in allowed)
    if unknown:
        raise ValueError(f"{name} contains unknown fields: {','.join(unknown)}")


def _enum_from_payload(enum_type: type[_EnumT], value: Any, name: str) -> _EnumT:
    text = _require_text(value, name)
    try:
        return enum_type(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be a known {enum_type.__name__} value") from exc


def _optional_enum_from_payload(enum_type: type[_EnumT], value: Any, name: str) -> _EnumT | None:
    if value is None:
        return None
    return _enum_from_payload(enum_type, value, name)


def _optional_text_from_payload(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, name)


def _metadata_from_payload(value: Any | None, name: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    return _require_mapping_payload(value, name)


def _expr_from_payload(value: Any, name: str) -> WHQRExpr:
    payload = _require_mapping_payload(value, name)
    if "role" in payload:
        _require_allowed_keys(
            payload,
            name,
            {
                "role",
                "target",
                "node_id",
                "scope",
                "modality",
                "expected_type",
                "quantifier",
                "entity_ref",
                "evidence_ref",
                "metadata",
            },
        )
        return WHQRNode(
            role=_enum_from_payload(WHRole, payload.get("role"), f"{name}.role"),
            target=_require_text(payload.get("target"), f"{name}.target"),
            node_id=_optional_text_from_payload(payload.get("node_id"), f"{name}.node_id"),
            scope=_optional_text_from_payload(payload.get("scope"), f"{name}.scope"),
            modality=_optional_enum_from_payload(Adverb, payload.get("modality"), f"{name}.modality"),
            expected_type=_optional_text_from_payload(payload.get("expected_type"), f"{name}.expected_type"),
            quantifier=_optional_enum_from_payload(Quantifier, payload.get("quantifier"), f"{name}.quantifier"),
            entity_ref=_optional_text_from_payload(payload.get("entity_ref"), f"{name}.entity_ref"),
            evidence_ref=_optional_text_from_payload(payload.get("evidence_ref"), f"{name}.evidence_ref"),
            metadata=_metadata_from_payload(payload.get("metadata"), f"{name}.metadata"),
        )
    if "op" in payload:
        _require_allowed_keys(payload, name, {"op", "args"})
        args_payload = payload.get("args")
        if not isinstance(args_payload, list):
            raise ValueError(f"{name}.args must be a list")
        return LogicalExpr(
            op=_enum_from_payload(LogicalOp, payload.get("op"), f"{name}.op"),
            args=tuple(_expr_from_payload(arg, f"{name}.args[{index}]") for index, arg in enumerate(args_payload)),
        )
    if "connector" in payload:
        _require_allowed_keys(payload, name, {"connector", "left", "right"})
        return ConnectorExpr(
            connector=_enum_from_payload(Connector, payload.get("connector"), f"{name}.connector"),
            left=_expr_from_payload(payload.get("left"), f"{name}.left"),
            right=_expr_from_payload(payload.get("right"), f"{name}.right"),
        )
    raise ValueError(f"{name} must declare a WHQR expression kind")


@dataclass(frozen=True, slots=True)
class WHQRNode:
    role: WHRole
    target: str
    node_id: str | None = None
    scope: str | None = None
    modality: Adverb | None = None
    expected_type: str | None = None
    quantifier: Quantifier | None = None
    entity_ref: str | None = None
    evidence_ref: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.role, WHRole):
            raise ValueError("role must be a WHRole value")
        object.__setattr__(self, "target", _require_text(self.target, "target"))
        if self.node_id is not None:
            object.__setattr__(self, "node_id", _require_text(self.node_id, "node_id"))
        if self.scope is not None:
            object.__setattr__(self, "scope", _require_text(self.scope, "scope"))
        if self.modality is not None and not isinstance(self.modality, Adverb):
            raise ValueError("modality must be an Adverb value")
        if self.expected_type is not None:
            object.__setattr__(
                self,
                "expected_type",
                _require_text(self.expected_type, "expected_type"),
            )
        if self.quantifier is not None and not isinstance(self.quantifier, Quantifier):
            raise ValueError("quantifier must be a Quantifier value")
        if self.entity_ref is not None:
            object.__setattr__(self, "entity_ref", _require_text(self.entity_ref, "entity_ref"))
        if self.evidence_ref is not None:
            object.__setattr__(self, "evidence_ref", _require_text(self.evidence_ref, "evidence_ref"))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class LogicalExpr:
    op: LogicalOp
    args: Sequence[WHQRExpr]

    def __post_init__(self) -> None:
        if not isinstance(self.op, LogicalOp):
            raise ValueError("op must be a LogicalOp value")
        args = tuple(self.args)
        if not args:
            raise ValueError("args must contain at least one WHQR expression")
        if self.op == LogicalOp.NOT and len(args) != 1:
            raise ValueError("not requires exactly one WHQR expression")
        if self.op != LogicalOp.NOT and len(args) < 2:
            raise ValueError("logical operators except not require at least two WHQR expressions")
        for arg in args:
            _require_whqr_expr(arg, "args")
        object.__setattr__(self, "args", args)


@dataclass(frozen=True, slots=True)
class ConnectorExpr:
    connector: Connector
    left: WHQRExpr
    right: WHQRExpr

    def __post_init__(self) -> None:
        if not isinstance(self.connector, Connector):
            raise ValueError("connector must be a Connector value")
        _require_whqr_expr(self.left, "left")
        _require_whqr_expr(self.right, "right")


WHQRExpr: TypeAlias = WHQRNode | LogicalExpr | ConnectorExpr


@dataclass(frozen=True, slots=True)
class GateResult:
    truth: TruthGate
    norm: NormGate | None = None
    evidence: EvidenceGate | None = None
    reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.truth, TruthGate):
            raise ValueError("truth must be a TruthGate value")
        if self.norm is not None and not isinstance(self.norm, NormGate):
            raise ValueError("norm must be a NormGate value")
        if self.evidence is not None and not isinstance(self.evidence, EvidenceGate):
            raise ValueError("evidence must be an EvidenceGate value")
        if self.reason is not None:
            object.__setattr__(self, "reason", _require_text(self.reason, "reason"))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class WHQRDocument:
    root: WHQRExpr
    whqr_version: str = WHQR_VERSION
    semantics_hash: str = SEMANTICS_HASH
    source_ref: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        root: WHQRExpr | None = None,
        *,
        expr: WHQRExpr | None = None,
        whqr_version: str = WHQR_VERSION,
        semantics_hash: str = SEMANTICS_HASH,
        source_ref: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if root is not None and expr is not None:
            raise ValueError("root and expr cannot both be provided")
        value = root if root is not None else expr
        if not isinstance(value, (WHQRNode, LogicalExpr, ConnectorExpr)):
            raise ValueError("root must be a WHQR expression")
        object.__setattr__(self, "root", value)
        object.__setattr__(self, "whqr_version", _require_text(whqr_version, "whqr_version"))
        object.__setattr__(self, "semantics_hash", _require_text(semantics_hash, "semantics_hash"))
        if not _is_sha256_digest_ref(semantics_hash):
            raise ValueError("semantics_hash must be sha256:<64 lowercase hex>")
        if (whqr_version, semantics_hash) != (WHQR_VERSION, SEMANTICS_HASH):
            raise ValueError("whqr_version and semantics_hash must match the canonical WHQR semantics")
        if source_ref is not None:
            object.__setattr__(self, "source_ref", _require_text(source_ref, "source_ref"))
        else:
            object.__setattr__(self, "source_ref", None)
        object.__setattr__(self, "metadata", _freeze_metadata({} if metadata is None else metadata))

    @property
    def expr(self) -> WHQRExpr:
        return self.root

    @classmethod
    def from_canonical_json(
        cls,
        payload: str,
        *,
        expected_canonical_hash: str | None = None,
    ) -> WHQRDocument:
        text = _require_text(payload, "payload")
        try:
            document_payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("WHQR canonical JSON payload must be valid JSON") from exc
        document_map = _require_mapping_payload(document_payload, "payload")
        _require_allowed_keys(
            document_map,
            "payload",
            {"root", "whqr_version", "semantics_hash", "source_ref", "metadata"},
        )
        document = cls(
            root=_expr_from_payload(document_map.get("root"), "payload.root"),
            whqr_version=_require_text(document_map.get("whqr_version"), "payload.whqr_version"),
            semantics_hash=_require_text(document_map.get("semantics_hash"), "payload.semantics_hash"),
            source_ref=_optional_text_from_payload(document_map.get("source_ref"), "payload.source_ref"),
            metadata=_metadata_from_payload(document_map.get("metadata"), "payload.metadata"),
        )
        canonical_payload = document.canonical_json()
        if canonical_payload != text:
            raise ValueError("WHQR replay payload must match deterministic canonical JSON")
        document.verify_semantics(expected_canonical_hash=expected_canonical_hash)
        return document

    def canonical_json(self) -> str:
        try:
            return json.dumps(
                _canonical(self),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("WHQR document must serialize to deterministic canonical JSON") from exc

    def canonical_hash(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def verify_semantics(self, *, expected_canonical_hash: str | None = None) -> str:
        if self.whqr_version != WHQR_VERSION:
            raise ValueError("WHQR replay semantic version mismatch")
        if self.semantics_hash != SEMANTICS_HASH:
            raise ValueError("WHQR replay semantics hash mismatch")
        _require_whqr_expr_tree(self.root, "root")
        _require_optional_text(self.source_ref, "source_ref")
        _require_metadata_tree(self.metadata, "document")
        canonical_hash = self.canonical_hash()
        if expected_canonical_hash is not None:
            expected = _require_text(expected_canonical_hash, "expected_canonical_hash")
            if not _is_sha256_digest_ref(expected):
                raise ValueError("expected_canonical_hash must be sha256:<64 lowercase hex>")
            if canonical_hash != expected:
                raise ValueError("WHQR replay canonical hash mismatch")
        return canonical_hash


def _canonical(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {_require_text(key, "canonical mapping key"): _canonical(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if is_dataclass(value):
        return {
            field.name: _canonical(getattr(value, field.name))
            for field in fields(value)
            if getattr(value, field.name) is not None and getattr(value, field.name) != {}
        }
    return value
