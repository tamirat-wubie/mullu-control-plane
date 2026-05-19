"""Tests for the declarative protected-variable monitor (gap #3).

The monitor must be observe-only (pure), catch every weakening pattern
the codebase currently hardcodes ad hoc, and emit a frozen,
serializable verdict.
"""

from __future__ import annotations

import json

import pytest

from mcoi_runtime.governance.protected_variables import (
    ProtectedVariable,
    ProtectedVariableMonitor,
    ProtectionReport,
    ProtectionRule,
)


def _monitor(*vars_: ProtectedVariable) -> ProtectedVariableMonitor:
    m = ProtectedVariableMonitor()
    m.register_many(vars_)
    return m


# ── MUST_REMAIN_TRUE (mirrors profiles.py effect_assurance_required) ─────


def test_must_remain_true_blocks_weakening():
    m = _monitor(
        ProtectedVariable(
            name="effect_assurance_required",
            rule=ProtectionRule.MUST_REMAIN_TRUE,
        )
    )
    ok = m.check({"effect_assurance_required": True}, {"effect_assurance_required": True})
    assert ok.ok

    bad = m.check(
        {"effect_assurance_required": True},
        {"effect_assurance_required": False},
    )
    assert not bad.ok
    assert bad.violated_names == ("effect_assurance_required",)
    assert bad.violations[0].reason == "must remain True"


def test_unset_protected_var_is_not_a_violation():
    m = _monitor(
        ProtectedVariable(name="x", rule=ProtectionRule.MUST_REMAIN_TRUE)
    )
    # Proposed state simply doesn't touch x.
    assert m.check({"x": True}, {"unrelated": 1}).ok


# ── IMMUTABLE (incl. silent-removal bypass) ─────────────────────────────


def test_immutable_blocks_change_and_removal():
    m = _monitor(ProtectedVariable(name="owner", rule=ProtectionRule.IMMUTABLE))
    assert m.check({"owner": "alice"}, {"owner": "alice"}).ok

    changed = m.check({"owner": "alice"}, {"owner": "mallory"})
    assert not changed.ok
    assert "immutable" in changed.violations[0].reason

    removed = m.check({"owner": "alice"}, {})
    assert not removed.ok
    assert "removed" in removed.violations[0].reason

    # Not yet set → nothing protected.
    assert m.check({}, {"owner": "alice"}).ok


# ── monotonic floors ────────────────────────────────────────────────────


def test_monotonic_nondecreasing():
    m = _monitor(
        ProtectedVariable(name="min_approvals", rule=ProtectionRule.MONOTONIC_NONDECREASING)
    )
    assert m.check({"min_approvals": 2}, {"min_approvals": 3}).ok
    assert m.check({"min_approvals": 2}, {"min_approvals": 2}).ok
    assert not m.check({"min_approvals": 2}, {"min_approvals": 1}).ok


def test_monotonic_ignores_non_numeric():
    m = _monitor(
        ProtectedVariable(name="v", rule=ProtectionRule.MONOTONIC_NONINCREASING)
    )
    # Non-numeric values can't be ordered → not a violation, no crash.
    assert m.check({"v": "a"}, {"v": "z"}).ok


# ── value-set rules ─────────────────────────────────────────────────────


def test_forbidden_values():
    m = _monitor(
        ProtectedVariable(
            name="external_effect_policy",
            rule=ProtectionRule.FORBIDDEN_VALUES,
            forbidden_values=("allow_all", "disabled"),
        )
    )
    assert m.check({}, {"external_effect_policy": "approval_required"}).ok
    assert not m.check({}, {"external_effect_policy": "allow_all"}).ok


def test_allowed_values():
    m = _monitor(
        ProtectedVariable(
            name="tenant_scope",
            rule=ProtectionRule.ALLOWED_VALUES,
            allowed_values=("team_tenant", "org_tenant"),
        )
    )
    assert m.check({}, {"tenant_scope": "org_tenant"}).ok
    assert not m.check({}, {"tenant_scope": "global"}).ok


# ── REQUIRED_SUPERSET (mirrors identity PROTECTED_FORBIDDEN_CAPABILITIES) ─


def test_required_superset_floor_must_be_preserved():
    m = _monitor(
        ProtectedVariable(
            name="forbidden_capabilities",
            rule=ProtectionRule.REQUIRED_SUPERSET,
            required_members=("approval.self_grant", "policy.disable"),
        )
    )
    ok = m.check(
        {},
        {"forbidden_capabilities": ["approval.self_grant", "policy.disable", "x"]},
    )
    assert ok.ok

    bad = m.check({}, {"forbidden_capabilities": ["x"]})
    assert not bad.ok
    assert "approval.self_grant" in bad.violations[0].reason

    not_collection = m.check({}, {"forbidden_capabilities": 5})
    assert not not_collection.ok
    assert "not a collection" in not_collection.violations[0].reason


# ── report aggregation + purity + serialization ─────────────────────────


def test_multiple_violations_aggregate():
    m = _monitor(
        ProtectedVariable(name="a", rule=ProtectionRule.MUST_REMAIN_TRUE),
        ProtectedVariable(name="b", rule=ProtectionRule.IMMUTABLE),
    )
    report = m.check({"a": True, "b": 1}, {"a": False, "b": 2})
    assert not report.ok
    assert set(report.violated_names) == {"a", "b"}


def test_check_does_not_mutate_inputs():
    m = _monitor(ProtectedVariable(name="a", rule=ProtectionRule.MUST_REMAIN_TRUE))
    before = {"a": True}
    after = {"a": False}
    m.check(before, after)
    assert before == {"a": True}
    assert after == {"a": False}


def test_report_is_json_serializable():
    m = _monitor(ProtectedVariable(name="a", rule=ProtectionRule.MUST_REMAIN_TRUE))
    report = m.check({"a": True}, {"a": False})
    blob = report.to_json()
    parsed = json.loads(blob)
    assert parsed["violations"][0]["name"] == "a"
    assert parsed["violations"][0]["rule"] == "must_remain_true"


def test_empty_report_ok_and_serializable():
    assert ProtectionReport().ok
    assert json.loads(ProtectionReport().to_json()) == {"violations": []}


# ── declaration-time validation ─────────────────────────────────────────


def test_duplicate_registration_rejected():
    m = ProtectedVariableMonitor()
    m.register(ProtectedVariable(name="a", rule=ProtectionRule.IMMUTABLE))
    with pytest.raises(ValueError, match="already registered"):
        m.register(ProtectedVariable(name="a", rule=ProtectionRule.IMMUTABLE))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rule": ProtectionRule.ALLOWED_VALUES},
        {"rule": ProtectionRule.FORBIDDEN_VALUES},
        {"rule": ProtectionRule.REQUIRED_SUPERSET},
    ],
)
def test_set_rules_require_their_params(kwargs):
    with pytest.raises(ValueError):
        ProtectedVariable(name="a", **kwargs)


def test_blank_name_rejected():
    with pytest.raises(ValueError):
        ProtectedVariable(name="  ", rule=ProtectionRule.IMMUTABLE)
