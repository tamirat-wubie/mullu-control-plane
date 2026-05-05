"""Purpose: typed WHQR semantic query contract for governed meaning before MIL execution.
Governance scope: side-effect-free question roles, connectors, modality, and split gate outcomes.
Dependencies: Python dataclasses, enums, JSON, and hashing.
Invariants: truth, norm, and evidence are separate; WHQR expressions are immutable and canonically serialized.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping, Sequence, TypeAlias
import hashlib
import json


WHQR_VERSION = "0.1.0"
SEMANTICS_HASH = "sha256:whqr-v0.1.0-split-gates-side-effect-free"


class WHRole(StrEnum):
    WHO = "who"
    WHAT = "what"
    WHY = "why"
    WHEN = "when"
    WHERE = "where"
    HOW = "how"
    WHICH = "which"
    HOW_MUCH = "how_much"
    UNDER_WHAT_CONDITIONS = "under_what_conditions"


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
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _freeze_metadata(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be a mapping")
    rows: dict[str, Any] = {}
    for key, value in metadata.items():
        rows[_require_text(key, "metadata key")] = value
    return MappingProxyType(dict(sorted(rows.items(), key=lambda item: item[0])))


def _require_whqr_expr(value: Any, name: str) -> None:
    if not isinstance(value, (WHQRNode, LogicalExpr, ConnectorExpr)):
        raise ValueError(f"{name} must be a WHQR expression")


@dataclass(frozen=True, slots=True)
class WHQRNode:
    role: WHRole
    target: str
    scope: str | None = None
    modality: Adverb | None = None
    expected_type: str | None = None
    quantifier: Quantifier | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.role, WHRole):
            raise ValueError("role must be a WHRole value")
        object.__setattr__(self, "target", _require_text(self.target, "target"))
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
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        root: WHQRExpr | None = None,
        *,
        expr: WHQRExpr | None = None,
        whqr_version: str = WHQR_VERSION,
        semantics_hash: str = SEMANTICS_HASH,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        value = root if root is not None else expr
        if not isinstance(value, (WHQRNode, LogicalExpr, ConnectorExpr)):
            raise ValueError("root must be a WHQR expression")
        object.__setattr__(self, "root", value)
        object.__setattr__(self, "whqr_version", _require_text(whqr_version, "whqr_version"))
        object.__setattr__(self, "semantics_hash", _require_text(semantics_hash, "semantics_hash"))
        if not semantics_hash.startswith("sha256:"):
            raise ValueError("semantics_hash must start with sha256:")
        object.__setattr__(self, "metadata", _freeze_metadata(metadata or {}))

    @property
    def expr(self) -> WHQRExpr:
        return self.root

    def canonical_json(self) -> str:
        return json.dumps(_canonical(self), sort_keys=True, separators=(",", ":"))

    def canonical_hash(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def _canonical(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in value.items()}
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
