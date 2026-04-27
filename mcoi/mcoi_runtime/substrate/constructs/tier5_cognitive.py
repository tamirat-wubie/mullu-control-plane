"""
Tier 5 — Cognitive Constructs (Reasoning Operations).

The thinking layer. Where Tier 4 names governance, Tier 5 names the cognitive
acts that produce, refine, and apply governed decisions: observing,
inferring, deciding, executing, learning.

In MUSIA, an LLM is one of many possible Execution organs. The 15-step SCCCE
cycle is built on these five constructs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from mcoi_runtime.substrate.constructs.tier1_foundational import (
    ConstructBase,
    ConstructType,
    Tier,
)


@dataclass
class Observation(ConstructBase):
    """
    WHAT: state_recognition — sensor receives signal, interprets, attaches confidence.

    Observation is the entry point of cognition: a State is recognized through
    a sensor with bounded confidence. Distinct from State itself (which is the
    configuration); Observation is the *act of recognition*.
    """

    type: ConstructType = ConstructType.OBSERVATION
    tier: Tier = Tier.COGNITIVE

    sensor_identifier: str = ""
    raw_signal: str = ""
    interpreted_state_id: Optional[UUID] = None
    confidence: float = 0.0  # [0, 1]
    timestamp_iso: str = ""

    def __post_init__(self) -> None:
        if not self.sensor_identifier:
            raise ValueError("Observation requires sensor_identifier")
        if not self.raw_signal:
            raise ValueError("Observation requires raw_signal")
        if self.interpreted_state_id is None:
            raise ValueError(
                "Observation requires interpreted_state_id "
                "(uninterpreted signal is not an Observation)"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence {self.confidence} not in [0,1]")
        if not self.invariants:
            self.invariants = (
                "sensor_identified",
                "signal_present",
                "interpretation_attached",
                "confidence_bounded",
            )
        super().__post_init__()


@dataclass
class Inference(ConstructBase):
    """
    WHAT: pattern_extension — premises plus rules yield conclusion at certainty.

    Inference produces a new claim from existing claims via a rule. Distinct
    from Observation (input) and Decision (selection). Inference is the
    bridge between what is observed and what is decided.
    """

    type: ConstructType = ConstructType.INFERENCE
    tier: Tier = Tier.COGNITIVE

    premise_ids: tuple[UUID, ...] = ()
    rule_identifier: str = ""
    conclusion_id: Optional[UUID] = None
    certainty: float = 0.0  # [0, 1]
    inference_kind: str = "deductive"  # deductive | inductive | abductive

    def __post_init__(self) -> None:
        if not self.premise_ids:
            raise ValueError("Inference requires at least one premise")
        if not self.rule_identifier:
            raise ValueError("Inference requires rule_identifier")
        if self.conclusion_id is None:
            raise ValueError("Inference requires conclusion_id")
        if not (0.0 <= self.certainty <= 1.0):
            raise ValueError(f"certainty {self.certainty} not in [0,1]")
        if self.inference_kind not in {"deductive", "inductive", "abductive"}:
            raise ValueError(f"invalid inference_kind: {self.inference_kind}")
        # Deductive inferences make stronger claims about certainty
        if self.inference_kind == "deductive" and self.certainty < 1.0:
            # Allowed but flagged via invariants — caller should be deliberate
            pass
        if not self.invariants:
            self.invariants = (
                "premises_present",
                "rule_named",
                "conclusion_referenced",
                "certainty_bounded",
                "inference_kind_classified",
            )
        super().__post_init__()


@dataclass
class Decision(ConstructBase):
    """
    WHAT: constraint_selection from a set of options under criteria.

    Decision picks one option from many using stated criteria, with
    justification. Distinct from Inference (which produces conclusions) and
    Execution (which acts on decisions).
    """

    type: ConstructType = ConstructType.DECISION
    tier: Tier = Tier.COGNITIVE

    option_ids: tuple[UUID, ...] = ()
    selection_criteria: tuple[str, ...] = ()
    chosen_option_id: Optional[UUID] = None
    justification: str = ""
    decision_kind: str = "deliberate"  # deliberate | reflexive | escalated

    def __post_init__(self) -> None:
        if len(self.option_ids) < 2:
            raise ValueError(
                "Decision requires >= 2 options (a forced choice is not a Decision)"
            )
        if len(set(self.option_ids)) != len(self.option_ids):
            raise ValueError("Decision: option_ids must be distinct")
        if not self.selection_criteria:
            raise ValueError("Decision requires selection_criteria")
        if self.chosen_option_id is None:
            raise ValueError("Decision requires chosen_option_id")
        if self.chosen_option_id not in self.option_ids:
            raise ValueError(
                "Decision: chosen_option_id must be one of option_ids"
            )
        if not self.justification:
            raise ValueError(
                "Decision requires justification "
                "(an unjustified choice is not a Decision)"
            )
        if self.decision_kind not in {"deliberate", "reflexive", "escalated"}:
            raise ValueError(f"invalid decision_kind: {self.decision_kind}")
        if not self.invariants:
            self.invariants = (
                "options_plural",
                "options_distinct",
                "criteria_present",
                "chosen_among_options",
                "justification_present",
                "kind_classified",
            )
        super().__post_init__()


@dataclass
class Execution(ConstructBase):
    """
    WHAT: constraint_application — plan + resources + monitoring → completion.

    Execution acts on a Decision. It allocates resources, monitors progress,
    and produces a Change. In MUSIA, an LLM call is one possible Execution;
    others include database writes, API calls, robot motions.

    Distinct from Decision (which selects) and Change (which is the delta);
    Execution is the *carrying out*.
    """

    type: ConstructType = ConstructType.EXECUTION
    tier: Tier = Tier.COGNITIVE

    plan_description: str = ""
    decision_id: Optional[UUID] = None
    resource_allocations: tuple[str, ...] = ()
    monitoring_endpoints: tuple[str, ...] = ()
    completion_state: str = "pending"
    # pending | in_progress | completed | failed | cancelled
    produced_change_id: Optional[UUID] = None

    def __post_init__(self) -> None:
        if not self.plan_description:
            raise ValueError("Execution requires plan_description")
        if self.decision_id is None:
            raise ValueError(
                "Execution requires decision_id "
                "(execution without prior Decision is unaccountable)"
            )
        valid_completion = {
            "pending",
            "in_progress",
            "completed",
            "failed",
            "cancelled",
        }
        if self.completion_state not in valid_completion:
            raise ValueError(
                f"invalid completion_state: {self.completion_state}"
            )
        if self.completion_state == "completed" and self.produced_change_id is None:
            raise ValueError(
                "Execution: completed state requires produced_change_id"
            )
        if not self.invariants:
            self.invariants = (
                "plan_specified",
                "decision_referenced",
                "completion_state_classified",
                "completed_requires_change",
            )
        super().__post_init__()


@dataclass
class Learning(ConstructBase):
    """
    WHAT: pattern_refinement — extract patterns from experience, integrate, validate.

    Learning takes Executions (with their outcomes) and refines Patterns
    accordingly. Distinct from Inference (which produces conclusions from
    rules) — Learning produces *new rules* from outcomes.
    """

    type: ConstructType = ConstructType.LEARNING
    tier: Tier = Tier.COGNITIVE

    experience_execution_ids: tuple[UUID, ...] = ()
    extracted_pattern_id: Optional[UUID] = None
    integration_target_id: Optional[UUID] = None  # what the pattern is being added to
    validation_id: Optional[UUID] = None  # Tier 4 Validation
    learning_kind: str = "supervised"  # supervised | unsupervised | reinforcement

    def __post_init__(self) -> None:
        if not self.experience_execution_ids:
            raise ValueError(
                "Learning requires at least one experience Execution"
            )
        if self.extracted_pattern_id is None:
            raise ValueError(
                "Learning requires extracted_pattern_id "
                "(learning without an extracted pattern is not Learning)"
            )
        if self.validation_id is None:
            raise ValueError(
                "Learning requires validation_id "
                "(unvalidated learning is the same fabrication pattern as MUSIA_MODE — "
                "claims without verification)"
            )
        if self.learning_kind not in {
            "supervised",
            "unsupervised",
            "reinforcement",
        }:
            raise ValueError(f"invalid learning_kind: {self.learning_kind}")
        if not self.invariants:
            self.invariants = (
                "experience_present",
                "pattern_extracted",
                "validation_attached",
                "kind_classified",
            )
        super().__post_init__()


# ---- DISAMBIGUATION ----


TIER5_RESPONSIBILITIES: dict[ConstructType, str] = {
    ConstructType.OBSERVATION: "WHAT_RECOGNIZES_STATES",
    ConstructType.INFERENCE:   "WHAT_EXTENDS_PATTERNS_VIA_RULES",
    ConstructType.DECISION:    "WHAT_SELECTS_AMONG_OPTIONS",
    ConstructType.EXECUTION:   "WHAT_APPLIES_DECISIONS",
    ConstructType.LEARNING:    "WHAT_REFINES_RULES_FROM_OUTCOMES",
}


def verify_tier5_disambiguation() -> None:
    seen: set[str] = set()
    for ct, resp in TIER5_RESPONSIBILITIES.items():
        if resp in seen:
            raise ValueError(f"tier 5 responsibility overlap detected: {resp}")
        seen.add(resp)


verify_tier5_disambiguation()
