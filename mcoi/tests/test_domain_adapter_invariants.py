"""
Cross-adapter shape invariants.

Every domain adapter must satisfy the same governance contract:

  translate_to_universal(domain_request) -> UniversalRequest
  translate_from_universal(UniversalResult, domain_request) -> domain_result
  run_with_ucja(domain_request) -> domain_result

This file parametrizes one set of invariant tests over every registered
adapter so shape drift in any single adapter is caught. New adapters
get four lines added to ``ADAPTERS`` and inherit the full test set.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from uuid import UUID

import pytest

from mcoi_runtime.domain_adapters import UniversalRequest, UniversalResult
from mcoi_runtime.domain_adapters._registry import ADAPTERS, AdapterEntry




_VALID_VIOLATION_RESPONSES = frozenset({"block", "escalate", "warn"})
_VALID_PERMEABILITIES = frozenset({"closed", "selective", "open"})


# ---- Per-adapter parametrized invariants ----


@pytest.fixture(params=ADAPTERS, ids=lambda a: a.name)
def adapter(request) -> AdapterEntry:
    return request.param


def test_request_is_dataclass(adapter: AdapterEntry):
    assert is_dataclass(adapter.request_cls), (
        f"{adapter.name} request must be a dataclass"
    )


def test_action_kind_has_at_least_two_values(adapter: AdapterEntry):
    values = list(adapter.action_kind_cls)
    assert len(values) >= 2, (
        f"{adapter.name}.{adapter.action_kind_cls.__name__} should "
        f"distinguish at least two kinds"
    )


def test_request_has_summary_field(adapter: AdapterEntry):
    field_names = {f.name for f in fields(adapter.request_cls)}
    assert "summary" in field_names, (
        f"{adapter.name} request must carry a `summary` field"
    )


def test_request_has_blast_radius_field(adapter: AdapterEntry):
    field_names = {f.name for f in fields(adapter.request_cls)}
    # software_dev predates the convention but matches via blast_radius
    assert "blast_radius" in field_names, (
        f"{adapter.name} request should expose `blast_radius`"
    )


def test_translate_returns_universal_request(adapter: AdapterEntry):
    uni = adapter.translate_to_universal(adapter.build())
    assert isinstance(uni, UniversalRequest)


def test_purpose_statement_is_namespaced(adapter: AdapterEntry):
    uni = adapter.translate_to_universal(adapter.build())
    assert uni.purpose_statement, f"{adapter.name} produced empty purpose"
    assert ":" in uni.purpose_statement, (
        f"{adapter.name} purpose should be 'verb_phrase: summary' shape, "
        f"got {uni.purpose_statement!r}"
    )


def test_authority_is_tuple_of_strings(adapter: AdapterEntry):
    uni = adapter.translate_to_universal(adapter.build())
    assert isinstance(uni.authority_required, tuple)
    assert len(uni.authority_required) >= 1, (
        f"{adapter.name} should require at least one authority"
    )
    for a in uni.authority_required:
        assert isinstance(a, str) and a, (
            f"{adapter.name} authority entry must be non-empty str: {a!r}"
        )


def test_observer_is_tuple_of_strings(adapter: AdapterEntry):
    uni = adapter.translate_to_universal(adapter.build())
    assert isinstance(uni.observer_required, tuple)
    assert len(uni.observer_required) >= 1, (
        f"{adapter.name} should require at least one observer"
    )
    for o in uni.observer_required:
        assert isinstance(o, str) and o, (
            f"{adapter.name} observer entry must be non-empty str: {o!r}"
        )


def test_constraint_set_violation_responses_are_valid(adapter: AdapterEntry):
    uni = adapter.translate_to_universal(adapter.build())
    for c in uni.constraint_set:
        assert "domain" in c, f"{adapter.name} constraint missing 'domain'"
        assert "restriction" in c, (
            f"{adapter.name} constraint missing 'restriction'"
        )
        assert isinstance(c["domain"], str) and c["domain"]
        assert isinstance(c["restriction"], str) and c["restriction"]
        vr = c.get("violation_response", "block")
        assert vr in _VALID_VIOLATION_RESPONSES, (
            f"{adapter.name} constraint has invalid violation_response "
            f"{vr!r} (allowed: {_VALID_VIOLATION_RESPONSES})"
        )


def test_boundary_specification_shape(adapter: AdapterEntry):
    uni = adapter.translate_to_universal(adapter.build())
    spec = uni.boundary_specification
    assert "inside_predicate" in spec, (
        f"{adapter.name} boundary missing inside_predicate"
    )
    assert isinstance(spec.get("interface_points", []), list), (
        f"{adapter.name} boundary.interface_points must be a list "
        f"(consistency across adapters), got "
        f"{type(spec.get('interface_points')).__name__}"
    )
    permeability = spec.get("permeability", "selective")
    assert permeability in _VALID_PERMEABILITIES, (
        f"{adapter.name} permeability {permeability!r} not in "
        f"{_VALID_PERMEABILITIES}"
    )


def test_run_with_ucja_returns_object_with_governance_status(adapter: AdapterEntry):
    out = adapter.run_with_ucja(adapter.build())
    assert hasattr(out, "governance_status"), (
        f"{adapter.name} result lacks governance_status"
    )
    assert isinstance(out.governance_status, str)
    assert out.governance_status, (
        f"{adapter.name} governance_status is empty"
    )


def test_run_with_ucja_attaches_audit_trail_uuid(adapter: AdapterEntry):
    out = adapter.run_with_ucja(adapter.build())
    assert hasattr(out, "audit_trail_id"), (
        f"{adapter.name} result lacks audit_trail_id"
    )
    assert isinstance(out.audit_trail_id, UUID)


def test_run_with_ucja_returns_risk_flags_tuple(adapter: AdapterEntry):
    out = adapter.run_with_ucja(adapter.build())
    assert hasattr(out, "risk_flags"), (
        f"{adapter.name} result lacks risk_flags"
    )
    assert isinstance(out.risk_flags, tuple)
    for f in out.risk_flags:
        assert isinstance(f, str) and f


def test_translate_round_trip_preserves_audit_id(adapter: AdapterEntry):
    """translate_from_universal must propagate the UniversalResult's
    job_definition_id into the domain result's audit_trail_id."""
    req = adapter.build()
    fake_uuid = UUID("12345678-1234-5678-1234-567812345678")
    fake_universal_result = UniversalResult(
        job_definition_id=fake_uuid,
        construct_graph_summary={
            "observation": 1, "inference": 1, "decision": 1,
            "transformation": 1, "validation": 1, "execution": 1,
        },
        cognitive_cycles_run=1,
        converged=True,
        proof_state="Pass",
    )
    domain_result = adapter.translate_from_universal(
        fake_universal_result, req,
    )
    assert domain_result.audit_trail_id == fake_uuid, (
        f"{adapter.name} translate_from_universal did not propagate "
        f"job_definition_id into audit_trail_id"
    )


def test_pass_proof_state_yields_approved(adapter: AdapterEntry):
    req = adapter.build()
    fake_universal_result = UniversalResult(
        job_definition_id=UUID("12345678-1234-5678-1234-567812345678"),
        construct_graph_summary={
            "observation": 1, "inference": 1, "decision": 1,
            "transformation": 1, "validation": 1, "execution": 1,
        },
        cognitive_cycles_run=1,
        converged=True,
        proof_state="Pass",
    )
    domain_result = adapter.translate_from_universal(
        fake_universal_result, req,
    )
    assert domain_result.governance_status == "approved", (
        f"{adapter.name}: Pass proof_state must yield 'approved' status, "
        f"got {domain_result.governance_status!r}"
    )


def test_non_pass_proof_state_yields_blocked_status(adapter: AdapterEntry):
    req = adapter.build()
    for state in ("Fail", "Unknown", "BudgetUnknown"):
        fake_universal_result = UniversalResult(
            job_definition_id=UUID("12345678-1234-5678-1234-567812345678"),
            construct_graph_summary={},
            cognitive_cycles_run=0,
            converged=False,
            proof_state=state,
        )
        domain_result = adapter.translate_from_universal(
            fake_universal_result, req,
        )
        assert domain_result.governance_status.startswith("blocked"), (
            f"{adapter.name}: non-Pass proof_state {state!r} must yield "
            f"'blocked: ...' status, got {domain_result.governance_status!r}"
        )


# ---- Whole-suite invariants ----


def test_all_adapters_produce_distinct_purposes():
    """No two adapters should generate identical purpose strings for
    their minimal requests — purpose is the domain fingerprint."""
    purposes = {
        a.name: a.translate_to_universal(a.build()).purpose_statement
        for a in ADAPTERS
    }
    seen: dict[str, str] = {}
    for name, purpose in purposes.items():
        if purpose in seen:
            pytest.fail(
                f"adapters {seen[purpose]!r} and {name!r} produce "
                f"identical purpose_statement {purpose!r}"
            )
        seen[purpose] = name


def test_all_adapters_count_matches_init_docstring():
    """Sanity check: catch the case where we add an adapter import to
    __init__ but forget to add it to ADAPTERS in this file."""
    import mcoi_runtime.domain_adapters as mod
    docstring = mod.__doc__ or ""
    # Count "(v" occurrences in the bullet list as a proxy for adapter count
    declared = docstring.count("(v")
    assert declared == len(ADAPTERS), (
        f"__init__ docstring declares {declared} adapters but "
        f"ADAPTERS list has {len(ADAPTERS)} — keep them in sync"
    )
