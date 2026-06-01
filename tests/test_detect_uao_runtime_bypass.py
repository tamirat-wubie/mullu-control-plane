"""Purpose: verify the Universal Action Orchestration runtime bypass detector.

Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.detect_uao_runtime_bypass.
Invariants: the detector is read-only, deterministic, and fail-closed for new
unbound effect-bearing runtime calls.
"""

from __future__ import annotations

from scripts import detect_uao_runtime_bypass as detector


def test_unbound_runtime_dispatch_is_reported_as_violation() -> None:
    source_text = """
def route_capability(dispatcher, request):
    return dispatcher.dispatch(request)
"""

    findings = detector.scan_source_text(
        source_text, relative_path="gateway/new_capability_surface.py"
    )

    assert len(findings) == 1
    assert findings[0].classification == "violation"
    assert findings[0].call == "dispatcher.dispatch"
    assert findings[0].symbol == "route_capability"
    assert "no UAO/governed binding" in findings[0].reason


def test_uao_bound_runtime_dispatch_is_admitted() -> None:
    source_text = """
def route_capability(dispatcher, action_envelope, admission_receipt_ref):
    closure_state = "closed_allowed"
    execution_receipt_ref = "receipt://execution"
    return dispatcher.dispatch(
        {
            "action_envelope": action_envelope,
            "admission_receipt_ref": admission_receipt_ref,
            "execution_receipt_ref": execution_receipt_ref,
            "closure_state": closure_state,
        }
    )
"""

    findings = detector.scan_source_text(
        source_text, relative_path="gateway/new_capability_surface.py"
    )

    assert len(findings) == 1
    assert findings[0].classification == "uao_bound"
    assert findings[0].call == "dispatcher.dispatch"
    assert "Universal Action Orchestration" in findings[0].reason
    assert findings[0].line > 0


def test_comment_only_binding_terms_do_not_admit_runtime_dispatch() -> None:
    source_text = """
def route_capability(dispatcher, request):
    # universal_action uao_bypass_exempt governed_dispatch
    return dispatcher.dispatch(request)
"""

    findings = detector.scan_source_text(
        source_text, relative_path="gateway/new_capability_surface.py"
    )

    assert len(findings) == 1
    assert findings[0].classification == "violation"
    assert findings[0].call == "dispatcher.dispatch"
    assert findings[0].symbol == "route_capability"
    assert "no UAO/governed binding" in findings[0].reason


def test_governed_dispatch_is_admitted() -> None:
    source_text = """
def route_capability(governed):
    context = GovernedDispatchContext(
        actor_id="actor",
        intent_id="intent",
        request=None,
    )
    return governed.governed_dispatch(context)
"""

    findings = detector.scan_source_text(
        source_text, relative_path="mcoi/mcoi_runtime/core/new_dispatcher.py"
    )

    assert len(findings) == 1
    assert findings[0].classification == "governed_bound"
    assert findings[0].call == "governed.governed_dispatch"
    assert "governed dispatcher" in findings[0].reason


def test_current_workspace_runtime_bypass_report_passes() -> None:
    report = detector.build_detection_report()

    assert report["valid"] is True
    assert report["status"] == "passed"
    assert report["violation_count"] == 0
    assert report["candidate_count"] >= 1
    assert report["uao_bound_count"] >= 1
    assert report["governed_bound_count"] >= 1
    assert report["exempted_count"] >= 1
    assert report["parse_error_count"] == 0
