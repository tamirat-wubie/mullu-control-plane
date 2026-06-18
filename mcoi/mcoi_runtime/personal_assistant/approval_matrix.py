"""Purpose: typed Personal Assistant approval-matrix runtime policy.
Governance scope: P0-P5 approval classification, allowed execution modes,
blocked-without-approval coverage, overclaim denial, and no-effect approval
admission checks.
Dependencies: checked-in approval matrix JSON-compatible YAML and Personal
Assistant contracts.
Invariants:
  - Loading the approval matrix never executes connector, mailbox, calendar,
    deployment, memory, or external actions.
  - P3/P4/P5 remain explicit-approval tiers.
  - P5 remains blocked in Foundation Mode.
  - Approval decisions are evidence records, not execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError, SkillRiskLevel


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_APPROVAL_MATRIX_PATH = REPO_ROOT / "governance" / "personal_assistant_approval_matrix.yaml"
EXPECTED_RISK_LEVELS = tuple(level.value for level in SkillRiskLevel)
APPROVAL_REQUIRED_LEVELS = frozenset({"P3", "P4", "P5"})
FOUNDATION_ALLOWED_EXECUTION_MODES = frozenset(
    {"dry_run", "preview", "draft", "read_and_draft_only", "execute_with_approval", "blocked"}
)
LOCAL_APPROVAL_BLOCKERS = frozenset(
    {
        "recipient_unapproved",
        "recipient_not_confirmed",
        "send_without_approval",
        "connector_mutation_without_receipt",
    }
)


@dataclass(frozen=True, slots=True)
class ApprovalRiskPolicy:
    """Runtime policy for one Personal Assistant risk tier."""

    level: SkillRiskLevel
    description: str
    private_connector_allowed: bool
    effect_bearing: bool
    explicit_approval_required: bool
    allowed_modes: tuple[str, ...]

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "ApprovalRiskPolicy":
        """Build and validate one risk policy entry."""
        if not isinstance(payload, Mapping):
            raise PersonalAssistantInvariantError("approval risk policy must be an object")
        policy = ApprovalRiskPolicy(
            level=SkillRiskLevel.coerce(_require_text(payload, "level")),
            description=_require_text(payload, "description"),
            private_connector_allowed=_require_bool(payload, "private_connector_allowed"),
            effect_bearing=_require_bool(payload, "effect_bearing"),
            explicit_approval_required=_require_bool(payload, "explicit_approval_required"),
            allowed_modes=_text_tuple(payload, "allowed_modes"),
        )
        policy.assert_consistent()
        return policy

    def assert_consistent(self) -> None:
        """Fail closed on approval-tier contradictions."""
        if self.level.value in APPROVAL_REQUIRED_LEVELS:
            if not self.explicit_approval_required:
                raise PersonalAssistantInvariantError(
                    f"{self.level.value}: explicit_approval_required must be true"
                )
            if not self.effect_bearing:
                raise PersonalAssistantInvariantError(f"{self.level.value}: effect_bearing must be true")
        else:
            if self.explicit_approval_required:
                raise PersonalAssistantInvariantError(
                    f"{self.level.value}: explicit approval must not be required by default"
                )
            if self.effect_bearing:
                raise PersonalAssistantInvariantError(f"{self.level.value}: effect_bearing must be false")
        unknown_modes = sorted(set(self.allowed_modes).difference(FOUNDATION_ALLOWED_EXECUTION_MODES))
        if unknown_modes:
            raise PersonalAssistantInvariantError(
                f"{self.level.value}: allowed_modes contain unknown entries {unknown_modes}"
            )
        if self.level is SkillRiskLevel.P5 and self.allowed_modes != ("blocked",):
            raise PersonalAssistantInvariantError("P5: allowed_modes must be exactly blocked")

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready risk policy projection."""
        return {
            "level": self.level.value,
            "description": self.description,
            "private_connector_allowed": self.private_connector_allowed,
            "effect_bearing": self.effect_bearing,
            "explicit_approval_required": self.explicit_approval_required,
            "allowed_modes": list(self.allowed_modes),
        }


@dataclass(slots=True)
class PersonalAssistantApprovalMatrix:
    """Runtime approval matrix for no-effect Personal Assistant policy checks."""

    matrix_id: str
    schema_version: str
    foundation_mode_required: bool
    risk_policies: dict[SkillRiskLevel, ApprovalRiskPolicy] = field(default_factory=dict)
    action_classification: Mapping[str, SkillRiskLevel] = field(default_factory=dict)
    blocked_without_approval: tuple[str, ...] = ()
    overclaim_blocks: Mapping[str, bool] = field(default_factory=dict)
    required_evidence_for_p5: tuple[str, ...] = ()

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "PersonalAssistantApprovalMatrix":
        """Build and validate a runtime approval matrix from parsed policy."""
        if not isinstance(payload, Mapping):
            raise PersonalAssistantInvariantError("approval matrix root must be an object")
        risk_entries = payload.get("risk_levels")
        if not isinstance(risk_entries, list):
            raise PersonalAssistantInvariantError("risk_levels must be a list")
        risk_policies: dict[SkillRiskLevel, ApprovalRiskPolicy] = {}
        for offset, entry in enumerate(risk_entries):
            try:
                policy = ApprovalRiskPolicy.from_mapping(entry)
            except PersonalAssistantInvariantError as exc:
                raise PersonalAssistantInvariantError(f"risk_levels[{offset}]: {exc}") from exc
            if policy.level in risk_policies:
                raise PersonalAssistantInvariantError(f"duplicate risk level: {policy.level.value}")
            risk_policies[policy.level] = policy

        action_classification = _risk_classification_mapping(
            _require_mapping(payload, "action_classification")
        )
        matrix = PersonalAssistantApprovalMatrix(
            matrix_id=_require_text(payload, "matrix_id"),
            schema_version=_require_text(payload, "schema_version"),
            foundation_mode_required=_require_bool(payload, "foundation_mode_required"),
            risk_policies=risk_policies,
            action_classification=action_classification,
            blocked_without_approval=_text_tuple(payload, "blocked_without_approval"),
            overclaim_blocks=_bool_mapping(_require_mapping(payload, "overclaim_blocks")),
            required_evidence_for_p5=_text_tuple(payload, "required_evidence_for_p5"),
        )
        matrix.assert_consistent()
        return matrix

    def assert_consistent(self) -> None:
        """Fail closed on matrix-level contradictions."""
        if self.schema_version != "personal_assistant.approval_matrix.v1":
            raise PersonalAssistantInvariantError("approval matrix schema_version is unsupported")
        if not self.matrix_id:
            raise PersonalAssistantInvariantError("approval matrix_id must be set")
        if self.foundation_mode_required is not True:
            raise PersonalAssistantInvariantError("foundation_mode_required must be true")
        levels = tuple(policy.level.value for policy in self.risk_policies.values())
        if levels != EXPECTED_RISK_LEVELS:
            raise PersonalAssistantInvariantError(f"risk_levels must be ordered {EXPECTED_RISK_LEVELS}")
        for flag_name, flag_value in self.overclaim_blocks.items():
            if flag_value is not False:
                raise PersonalAssistantInvariantError(f"overclaim_blocks.{flag_name} must be false")
        for action_name, risk_level in self.action_classification.items():
            if risk_level.value in APPROVAL_REQUIRED_LEVELS:
                blocked_action = _canonical_blocked_action(action_name)
                if blocked_action not in self.blocked_without_approval:
                    raise PersonalAssistantInvariantError(
                        f"{action_name}: {risk_level.value} action must be blocked without approval"
                    )
        required_p5 = {
            "operator_approval_ref",
            "uao_admission_ref",
            "receipt_ref",
            "rollback_or_compensation_ref",
            "named_witness_ref",
        }
        missing_p5 = sorted(required_p5.difference(self.required_evidence_for_p5))
        if missing_p5:
            raise PersonalAssistantInvariantError(f"required_evidence_for_p5 missing {missing_p5}")

    def policy_for(self, risk_level: SkillRiskLevel | str) -> ApprovalRiskPolicy:
        """Return the policy entry for a risk tier."""
        level = risk_level if isinstance(risk_level, SkillRiskLevel) else SkillRiskLevel.coerce(str(risk_level))
        try:
            return self.risk_policies[level]
        except KeyError as exc:
            raise PersonalAssistantInvariantError(f"missing approval policy for {level.value}") from exc

    def assert_action_admitted(
        self,
        *,
        risk_level: SkillRiskLevel | str,
        execution_mode: str,
        forbidden_without_approval: Sequence[str],
    ) -> None:
        """Validate one proposed approval action against the matrix."""
        policy = self.policy_for(risk_level)
        if execution_mode not in policy.allowed_modes:
            raise PersonalAssistantInvariantError(
                f"{policy.level.value}: execution_mode {execution_mode} is not allowed by approval matrix"
            )
        if not policy.explicit_approval_required:
            raise PersonalAssistantInvariantError(
                f"{policy.level.value}: proposed action does not require explicit approval"
            )
        missing_forbidden = sorted(
            set(_normalize_text_sequence(forbidden_without_approval, "forbidden_without_approval")).difference(
                set(self.blocked_without_approval).union(LOCAL_APPROVAL_BLOCKERS)
            )
        )
        if missing_forbidden:
            raise PersonalAssistantInvariantError(
                f"forbidden_without_approval contains actions outside matrix {missing_forbidden}"
            )
        if policy.level is SkillRiskLevel.P5 and execution_mode != "blocked":
            raise PersonalAssistantInvariantError("P5: foundation execution_mode must be blocked")

    def read_model(self) -> dict[str, Any]:
        """Return a deterministic no-effect approval matrix read model."""
        policies = [self.risk_policies[level].as_dict() for level in SkillRiskLevel]
        return {
            "schema_version": self.schema_version,
            "matrix_id": self.matrix_id,
            "foundation_mode_required": self.foundation_mode_required,
            "risk_levels": policies,
            "action_classification": {
                action: level.value for action, level in sorted(self.action_classification.items())
            },
            "blocked_without_approval": list(self.blocked_without_approval),
            "overclaim_blocks": dict(self.overclaim_blocks),
            "required_evidence_for_p5": list(self.required_evidence_for_p5),
            "execution_allowed_by_matrix": False,
            "approval_is_execution": False,
        }


def load_default_personal_assistant_approval_matrix() -> PersonalAssistantApprovalMatrix:
    """Load the checked-in Personal Assistant approval matrix."""
    return load_personal_assistant_approval_matrix(DEFAULT_APPROVAL_MATRIX_PATH)


def load_personal_assistant_approval_matrix(path: Path) -> PersonalAssistantApprovalMatrix:
    """Load and validate the Personal Assistant approval matrix."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PersonalAssistantInvariantError(f"approval matrix could not be read: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PersonalAssistantInvariantError(f"approval matrix must be JSON-compatible YAML: {path}") from exc
    return PersonalAssistantApprovalMatrix.from_mapping(payload)


def _require_mapping(payload: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError(f"{field_name} must be an object")
    return value


def _require_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    return value


def _require_bool(payload: Mapping[str, Any], field_name: str) -> bool:
    value = payload.get(field_name)
    if not isinstance(value, bool):
        raise PersonalAssistantInvariantError(f"{field_name} must be a boolean")
    return value


def _text_tuple(payload: Mapping[str, Any], field_name: str) -> tuple[str, ...]:
    values = payload.get(field_name)
    return _normalize_text_sequence(values, field_name)


def _normalize_text_sequence(values: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    normalized: list[str] = []
    for offset, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise PersonalAssistantInvariantError(f"{field_name}[{offset}] must be a non-empty string")
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise PersonalAssistantInvariantError(f"{field_name} must contain at least one item")
    return tuple(normalized)


def _bool_mapping(payload: Mapping[str, Any]) -> Mapping[str, bool]:
    result: dict[str, bool] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not key.strip():
            raise PersonalAssistantInvariantError("overclaim block keys must be non-empty strings")
        if not isinstance(value, bool):
            raise PersonalAssistantInvariantError(f"overclaim_blocks.{key} must be a boolean")
        result[key] = value
    return result


def _risk_classification_mapping(payload: Mapping[str, Any]) -> Mapping[str, SkillRiskLevel]:
    result: dict[str, SkillRiskLevel] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not key.strip():
            raise PersonalAssistantInvariantError("action classification keys must be non-empty strings")
        result[key] = SkillRiskLevel.coerce(str(value))
    return result


def _canonical_blocked_action(action_name: str) -> str:
    mapping = {
        "send_email": "send",
        "create_calendar_event": "create_event",
        "invite_people": "invite_people",
        "write_task": "system_of_record_write",
        "publish_public_page": "publish",
        "deploy_service": "deploy_service",
        "pay_invoice": "pay_invoice",
        "activate_nested_mind_live": "live_nested_mind_activation",
    }
    return mapping.get(action_name, action_name)
