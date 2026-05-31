"""Tests for the gateway method registry."""

from __future__ import annotations

import pytest

from gateway.candidate_composer import CandidateComposer, MethodCapsule
from gateway.candidate_ledger import CandidateLedger
from gateway.method_registry import (
    STARTER_CAPSULES,
    MethodRegistry,
    default_registry,
)
from gateway.problem_signature import ProblemMetric, ProblemSignature


def _capsule(capsule_id: str, family: str, *, risk_ceiling: str = "medium", domains=()):
    return MethodCapsule(
        capsule_id=capsule_id,
        method_family=family,
        declared_inputs=("x",),
        declared_outputs=("y",),
        declared_assumptions=(),
        declared_failure_modes=(),
        risk_ceiling=risk_ceiling,
        metadata={"domains": tuple(domains)},
    )


def _signature(
    *,
    risk: str = "medium",
    allowed: tuple[str, ...] = (),
    forbidden: tuple[str, ...] = (),
) -> ProblemSignature:
    return ProblemSignature(
        problem_id="reg.test.v1",
        domain="document_verification",
        goal="exercise registry admissibility",
        inputs=("records",),
        constraints=(),
        risk=risk,
        metrics=(ProblemMetric(metric_id="f1", metric_kind="success", direction="maximize"),),
        required_evidence=(),
        budget_units=10.0,
        timeout_seconds=1.0,
        allowed_method_families=allowed,
        forbidden_method_families=forbidden,
    )


def test_register_and_get():
    reg = MethodRegistry()
    cap = _capsule("c:1", "rule_based")
    reg.register(cap)
    assert reg.has("c:1")
    assert reg.get("c:1") is cap
    assert reg.all_capsules() == (cap,)


def test_duplicate_registration_rejected():
    reg = MethodRegistry((_capsule("c:1", "rule_based"),))
    with pytest.raises(ValueError, match="duplicate_capsule_id"):
        reg.register(_capsule("c:1", "graph_match"))


def test_get_unknown_raises():
    reg = MethodRegistry()
    with pytest.raises(ValueError, match="unknown_capsule_id"):
        reg.get("missing")


def test_families_sorted_and_unique():
    reg = MethodRegistry(
        (
            _capsule("c:1", "graph_match"),
            _capsule("c:2", "rule_based"),
            _capsule("c:3", "rule_based"),
        )
    )
    assert reg.families() == ("graph_match", "rule_based")
    assert len(reg.by_family("rule_based")) == 2


def test_for_domain_includes_tagged_and_untagged():
    reg = MethodRegistry(
        (
            _capsule("c:doc", "rule_based", domains=("document_verification",)),
            _capsule("c:wf", "search_planner", domains=("workflow_automation",)),
            _capsule("c:gen", "human_review_gate", domains=()),  # untagged = general
        )
    )
    ids = {c.capsule_id for c in reg.for_domain("document_verification")}
    assert ids == {"c:doc", "c:gen"}


def test_admissible_for_respects_allowed_list():
    reg = MethodRegistry(
        (_capsule("c:rb", "rule_based"), _capsule("c:gm", "graph_match"))
    )
    sig = _signature(allowed=("rule_based",))
    ids = {c.capsule_id for c in reg.admissible_for(sig)}
    assert ids == {"c:rb"}


def test_admissible_for_respects_forbidden_list():
    reg = MethodRegistry(
        (_capsule("c:rb", "rule_based"), _capsule("c:gm", "graph_match"))
    )
    sig = _signature(forbidden=("graph_match",))
    ids = {c.capsule_id for c in reg.admissible_for(sig)}
    assert ids == {"c:rb"}


def test_admissible_for_respects_risk_ceiling():
    reg = MethodRegistry(
        (
            _capsule("c:hi", "rule_based", risk_ceiling="high"),
            _capsule("c:med", "graph_match", risk_ceiling="medium"),
        )
    )
    sig = _signature(risk="high")  # medium-ceiling capsule must be excluded
    ids = {c.capsule_id for c in reg.admissible_for(sig)}
    assert ids == {"c:hi"}


def test_composer_for_excludes_forbidden_family():
    reg = MethodRegistry(
        (_capsule("c:rb", "rule_based"), _capsule("c:gm", "graph_match"))
    )
    sig = _signature(forbidden=("graph_match",))
    composer = reg.composer_for(sig, CandidateLedger())
    assert isinstance(composer, CandidateComposer)
    families = {c.method_family for c in composer.capsules()}
    assert families == {"rule_based"}


def test_composer_for_has_no_promotion_surface():
    # The registry must not smuggle in a promote/install path via the composer.
    reg = default_registry()
    composer = reg.composer_for(_signature(allowed=("rule_based",)), CandidateLedger())
    for forbidden_attr in ("promote", "install", "certify", "deploy", "register_capability"):
        assert not hasattr(composer, forbidden_attr)
    for forbidden_attr in ("promote", "install", "certify", "deploy", "register_capability"):
        assert not hasattr(reg, forbidden_attr)


def test_starter_catalog_integrity():
    reg = default_registry()
    assert reg.all_capsules() == STARTER_CAPSULES
    seen: set[str] = set()
    valid_cost = {"low", "medium", "high", "unknown"}
    valid_expl = {"low", "medium", "high", "unknown"}
    valid_risk = {"low", "medium", "high", "physical"}
    for cap in STARTER_CAPSULES:
        assert cap.capsule_id not in seen, f"duplicate starter id {cap.capsule_id}"
        seen.add(cap.capsule_id)
        assert cap.cost_class in valid_cost
        assert cap.explainability in valid_expl
        assert cap.risk_ceiling in valid_risk
        assert cap.declared_inputs and cap.declared_outputs
        # Honest provenance label so owners know these are starter defaults.
        assert cap.metadata.get("provenance") == "starter_default"


def test_default_registry_is_fresh_each_call():
    a = default_registry()
    b = default_registry()
    assert a is not b
    assert a.families() == b.families()
