"""Tests for the Mullu public naming readiness witness.

Purpose: lock the product naming launch gate into the Python test suite.
Governance scope: machine-readable naming witness, blocked public names,
evidence documents, and paid-launch gating.
Dependencies: scripts.validate_public_naming_readiness.
Invariants: public paid launch remains blocked until clearance evidence closes.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_public_naming_readiness import (  # noqa: E402
    BLOCKED_PUBLIC_NAMES,
    CLEARANCE_SCHEMA_PATH,
    CLEARANCE_DRAFT_PATH,
    CONDITIONAL_WEBSITE_ROUTES,
    REQUIRED_DOMAIN_CANDIDATES,
    REQUIRED_CLOSED_GATES,
    REQUIRED_EVIDENCE_DOCS,
    REQUIRED_OFFICIAL_SEARCHES,
    REQUIRED_OPEN_GATES,
    REQUIRED_TSDR_SERIALS,
    REQUIRED_WEBSITE_ROUTES,
    PRODUCT_ROUTE_DEPLOYMENT_HANDOFF_PATH,
    PRODUCT_ROUTE_DRAFT_PATH,
    READINESS_SCHEMA_PATH,
    WEBSITE_DEPLOYMENT_EVIDENCE_LOG_PATH,
    WEBSITE_DEPLOYMENT_EVIDENCE_SUCCESS_PATH,
    WEBSITE_RECHECK_LOG_PATH,
    WITNESS_PATH,
    validate_no_forbidden_terminology,
    validate_clearance_domain_candidates,
    validate_clearance_official_searches,
    validate_domain_acquisition_plan,
    validate_product_route_draft,
    validate_product_route_deployment_handoff,
    validate_public_naming_artifact_manifest,
    validate_public_launch_copy,
    validate_public_naming_readiness,
    validate_public_naming_review_packet,
    validate_tsdr_evidence_template,
    validate_website_deployment_evidence_log,
    validate_website_deployment_success_log,
    validate_website_deployment_evidence_template,
    validate_website_recheck_log,
)
from scripts.report_public_naming_readiness import main as report_public_naming_readiness  # noqa: E402
from scripts.plan_public_naming_transition import main as plan_public_naming_transition  # noqa: E402
from scripts import validate_release_status as release_status  # noqa: E402


def _load_witness() -> dict[str, object]:
    return json.loads(WITNESS_PATH.read_text(encoding="utf-8"))


def _write_witness(tmp_path: Path, witness: dict[str, object]) -> Path:
    path = tmp_path / "public-naming-readiness.json"
    path.write_text(json.dumps(witness, indent=2), encoding="utf-8")
    return path


def test_public_naming_readiness_witness_passes() -> None:
    witness = _load_witness()

    assert witness["product_name"] == "Mullu"
    assert witness["company_brand"] == "Mullusi"
    assert witness["public_paid_launch_allowed"] is False
    validate_public_naming_readiness()


def test_public_naming_readiness_witness_has_required_sets() -> None:
    witness = _load_witness()

    closed_gates = set(witness["closed_gates"])
    open_gates = set(witness["open_gates"])
    blocked_names = set(witness["blocked_public_names"])
    evidence_docs = set(witness["evidence_docs"])

    assert REQUIRED_CLOSED_GATES <= closed_gates
    assert REQUIRED_OPEN_GATES <= open_gates
    assert BLOCKED_PUBLIC_NAMES <= blocked_names
    assert REQUIRED_EVIDENCE_DOCS <= evidence_docs
    assert not (closed_gates & open_gates)


def test_closed_and_open_gate_sets_are_nonempty_and_distinct() -> None:
    assert REQUIRED_CLOSED_GATES
    assert REQUIRED_OPEN_GATES
    assert not (REQUIRED_CLOSED_GATES & REQUIRED_OPEN_GATES)


def test_public_naming_readiness_rejects_launch_before_clearance(tmp_path: Path) -> None:
    witness = _load_witness()
    witness["public_paid_launch_allowed"] = True
    witness_path = _write_witness(tmp_path, witness)

    with pytest.raises(AssertionError, match="public launch must remain blocked"):
        validate_public_naming_readiness(witness_path)


def test_public_naming_readiness_rejects_missing_evidence_doc(tmp_path: Path) -> None:
    witness = _load_witness()
    witness["evidence_docs"] = [
        evidence_doc
        for evidence_doc in witness["evidence_docs"]
        if evidence_doc != "docs/PRODUCT_IDENTITY.md"
    ]
    witness_path = _write_witness(tmp_path, witness)

    with pytest.raises(AssertionError, match="missing evidence docs"):
        validate_public_naming_readiness(witness_path)


def test_clearance_draft_blocks_paid_public_launch() -> None:
    clearance_draft = json.loads(CLEARANCE_DRAFT_PATH.read_text(encoding="utf-8"))

    assert clearance_draft["candidate_name"] == "Mullu"
    assert clearance_draft["company_brand"] == "Mullusi"
    assert clearance_draft["final_decision"] == "pending"
    assert clearance_draft["public_paid_launch_allowed"] is False
    assert clearance_draft["summary"]["trademark_clearance"] == "not_checked"
    assert clearance_draft["summary"]["legal_clearance"] == "not_complete"


def test_naming_witnesses_include_schema_required_fields() -> None:
    witness = _load_witness()
    readiness_schema = json.loads(READINESS_SCHEMA_PATH.read_text(encoding="utf-8"))
    clearance_draft = json.loads(CLEARANCE_DRAFT_PATH.read_text(encoding="utf-8"))
    clearance_schema = json.loads(CLEARANCE_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(readiness_schema["required"]) <= set(witness)
    assert set(clearance_schema["required"]) <= set(clearance_draft)
    assert readiness_schema["properties"]["product_name"]["const"] == "Mullu"
    assert clearance_schema["properties"]["candidate_name"]["const"] == "Mullu"


def test_public_naming_readiness_rejects_wrong_product_name(tmp_path: Path) -> None:
    witness = _load_witness()
    witness["product_name"] = "Mullu Platform"
    witness_path = _write_witness(tmp_path, witness)

    with pytest.raises(AssertionError, match="product_name must be Mullu|schema validation failed"):
        validate_public_naming_readiness(witness_path)


def test_public_naming_readiness_rejects_closed_gate_still_listed_open(tmp_path: Path) -> None:
    witness = _load_witness()
    witness["closed_gates"] = list(witness["closed_gates"]) + ["legal_review"]
    witness_path = _write_witness(tmp_path, witness)

    with pytest.raises(AssertionError, match="gates cannot be both open and closed"):
        validate_public_naming_readiness(witness_path)


def test_public_naming_readiness_rejects_cleared_status_with_open_gates(tmp_path: Path) -> None:
    witness = _load_witness()
    witness["status"] = "cleared_for_public_launch"
    witness_path = _write_witness(tmp_path, witness)

    with pytest.raises(AssertionError, match="cleared status requires no open gates"):
        validate_public_naming_readiness(witness_path)


def test_public_naming_readiness_rejects_unblocked_status_with_pending_decision(tmp_path: Path) -> None:
    witness = _load_witness()
    witness["open_gates"] = []
    witness["closed_gates"] = sorted(set(witness["closed_gates"]) | REQUIRED_OPEN_GATES)
    witness["status"] = "cleared_for_public_launch"
    witness["public_paid_launch_allowed"] = False
    witness_path = _write_witness(tmp_path, witness)

    with pytest.raises(AssertionError, match="cleared status requires final decision"):
        validate_public_naming_readiness(witness_path)


def test_public_naming_readiness_report_outputs_blocked_status(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = report_public_naming_readiness()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Mullu Public Naming Readiness" in output
    assert "Paid public launch allowed: False" in output
    assert "Final clearance decision: pending" in output
    assert "Closed gate count:" in output
    assert "Evidence artifact count:" in output
    assert "STATUS: blocked" in output


def test_public_naming_transition_plan_outputs_remaining_actions(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = plan_public_naming_transition()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Mullu Public Naming Transition Plan" in output
    assert "Closed gate count:" in output
    assert "Evidence artifact count:" in output
    assert "uspto_search" in output
    assert "domain_ownership" in output
    assert "Set public_paid_launch_allowed to true" in output
    assert "STATUS: transition_blocked" in output


def test_public_naming_readiness_rejects_forbidden_terminology() -> None:
    forbidden_text = "artificial" + " " + "intelligence"

    with pytest.raises(AssertionError, match="forbidden terminology"):
        validate_no_forbidden_terminology("draft-public-copy.md", forbidden_text)


def test_public_launch_copy_passes_blocked_name_boundary() -> None:
    validate_public_launch_copy()


def test_product_route_draft_passes_launch_boundary() -> None:
    validate_product_route_draft()


def test_product_route_draft_rejects_blocked_public_name(tmp_path: Path) -> None:
    route_path = tmp_path / "index.html"
    route_text = PRODUCT_ROUTE_DRAFT_PATH.read_text(encoding="utf-8").replace(
        "Mullu Control Plane",
        "Mullusi Operator",
    )
    route_path.write_text(route_text, encoding="utf-8")

    with pytest.raises(AssertionError, match="blocked public names leaked"):
        validate_product_route_draft(route_path)


def test_product_route_deployment_handoff_preserves_live_blocker() -> None:
    validate_product_route_deployment_handoff()


def test_product_route_deployment_handoff_rejects_missing_target(tmp_path: Path) -> None:
    handoff_path = tmp_path / "PRODUCT_ROUTE_DEPLOYMENT_HANDOFF.md"
    handoff_text = PRODUCT_ROUTE_DEPLOYMENT_HANDOFF_PATH.read_text(encoding="utf-8").replace(
        "../mullusi_website/mullu/index.html",
        "../mullusi/index.html",
    )
    handoff_path.write_text(handoff_text, encoding="utf-8")

    with pytest.raises(AssertionError, match="deployment handoff missing literals"):
        validate_product_route_deployment_handoff(handoff_path)


def test_public_launch_copy_rejects_blocked_name_before_boundary(tmp_path: Path) -> None:
    launch_copy = tmp_path / "PUBLIC_LAUNCH_COPY.md"
    launch_copy.write_text(
        "\n".join(
            [
                "# Public Launch Copy",
                "",
                "Mullu, by Mullusi",
                "",
                "Mullusi Work helps teams deploy governed workflows.",
                "",
                "Do not use:",
                "",
                "Mullusi Work",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="blocked public names leaked"):
        validate_public_launch_copy(launch_copy)


def test_tsdr_evidence_template_contains_required_serials() -> None:
    validate_tsdr_evidence_template()


def test_tsdr_evidence_template_rejects_missing_serial(tmp_path: Path) -> None:
    template = tmp_path / "TSDR_EVIDENCE_TEMPLATE.md"
    template.write_text(
        "\n".join(
            [
                "# TSDR Evidence Template",
                "",
                "close_variant_review",
                "https://tsdrapi.uspto.gov/ts/cd/casestatus/sn99518598/content.html",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="missing serials"):
        validate_tsdr_evidence_template(template)


def test_clearance_draft_contains_required_tsdr_serials() -> None:
    clearance_text = CLEARANCE_DRAFT_PATH.read_text(encoding="utf-8")

    assert REQUIRED_TSDR_SERIALS <= {serial for serial in REQUIRED_TSDR_SERIALS if serial in clearance_text}


def test_website_deployment_template_contains_required_routes() -> None:
    validate_website_deployment_evidence_template()


def test_website_deployment_evidence_log_preserves_failed_historical_product_routes() -> None:
    validate_website_deployment_evidence_log()


def test_website_deployment_evidence_log_rejects_cleared_gate(tmp_path: Path) -> None:
    log_path = tmp_path / "WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-07.md"
    log_text = WEBSITE_DEPLOYMENT_EVIDENCE_LOG_PATH.read_text(encoding="utf-8").replace(
        "not cleared",
        "cleared",
    )
    log_path.write_text(log_text, encoding="utf-8")

    with pytest.raises(AssertionError, match="deployment gate blocked"):
        validate_website_deployment_evidence_log(log_path)


def test_website_deployment_success_log_closes_private_beta_route() -> None:
    validate_website_deployment_success_log()


def test_website_deployment_success_log_rejects_missing_paid_launch_blocker(tmp_path: Path) -> None:
    log_path = tmp_path / "WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-15.md"
    log_text = WEBSITE_DEPLOYMENT_EVIDENCE_SUCCESS_PATH.read_text(encoding="utf-8").replace(
        "paid public launch remains blocked",
        "paid public launch is allowed",
    )
    log_path.write_text(log_text, encoding="utf-8")

    with pytest.raises(AssertionError, match="paid-launch blocker"):
        validate_website_deployment_success_log(log_path)


def test_website_recheck_log_preserves_historical_warning_boundary() -> None:
    validate_website_recheck_log()


def test_website_recheck_log_rejects_missing_superseding_evidence(tmp_path: Path) -> None:
    log_path = tmp_path / "WEBSITE_RECHECK_LOG.md"
    log_text = WEBSITE_RECHECK_LOG_PATH.read_text(encoding="utf-8").replace(
        "superseded by direct live-route evidence",
        "still the active route authority",
    )
    log_path.write_text(log_text, encoding="utf-8")

    with pytest.raises(AssertionError, match="website recheck log missing literals"):
        validate_website_recheck_log(log_path)


def test_website_deployment_template_rejects_missing_route(tmp_path: Path) -> None:
    template = tmp_path / "WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE.md"
    template.write_text(
        "\n".join(
            [
                "# Website Deployment Evidence Template",
                "",
                "website_deployment_verification",
                "No GitHub Pages site-not-found page",
                "https://mullusi.com",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="missing routes"):
        validate_website_deployment_evidence_template(template)


def test_website_route_sets_are_nonempty_and_distinct() -> None:
    assert REQUIRED_WEBSITE_ROUTES
    assert CONDITIONAL_WEBSITE_ROUTES
    assert not (REQUIRED_WEBSITE_ROUTES & CONDITIONAL_WEBSITE_ROUTES)


def test_domain_acquisition_plan_contains_required_candidates() -> None:
    validate_domain_acquisition_plan()


def test_clearance_draft_domain_candidates_match_required_priorities() -> None:
    clearance_draft = json.loads(CLEARANCE_DRAFT_PATH.read_text(encoding="utf-8"))

    validate_clearance_domain_candidates(clearance_draft)


def test_clearance_draft_domain_candidates_reject_wrong_priority() -> None:
    clearance_draft = json.loads(CLEARANCE_DRAFT_PATH.read_text(encoding="utf-8"))
    domain_candidates = list(clearance_draft["domain_candidates"])
    domain_candidates[0] = {**domain_candidates[0], "priority": 99}
    clearance_draft["domain_candidates"] = domain_candidates

    with pytest.raises(AssertionError, match="domain priorities changed"):
        validate_clearance_domain_candidates(clearance_draft)


def test_domain_candidate_set_keeps_primary_first() -> None:
    assert REQUIRED_DOMAIN_CANDIDATES["mullu.ai"] == 1
    assert REQUIRED_DOMAIN_CANDIDATES["mullusi.com/mullu"] == 6


def test_clearance_draft_official_searches_match_required_sources() -> None:
    clearance_draft = json.loads(CLEARANCE_DRAFT_PATH.read_text(encoding="utf-8"))

    validate_clearance_official_searches(clearance_draft)


def test_clearance_draft_official_searches_reject_missing_source() -> None:
    clearance_draft = json.loads(CLEARANCE_DRAFT_PATH.read_text(encoding="utf-8"))
    clearance_draft["official_searches"] = [
        search
        for search in clearance_draft["official_searches"]
        if search["source"] != "WIPO Global Brand Database"
    ]

    with pytest.raises(AssertionError, match="missing official search sources"):
        validate_clearance_official_searches(clearance_draft)


def test_clearance_draft_official_searches_reject_missing_uspto_class() -> None:
    clearance_draft = json.loads(CLEARANCE_DRAFT_PATH.read_text(encoding="utf-8"))
    official_searches = list(clearance_draft["official_searches"])
    uspto_search = dict(official_searches[0])
    uspto_search["required_classes"] = [
        required_class
        for required_class in uspto_search["required_classes"]
        if required_class != "42"
    ]
    official_searches[0] = uspto_search
    clearance_draft["official_searches"] = official_searches

    with pytest.raises(AssertionError, match="missing required classes"):
        validate_clearance_official_searches(clearance_draft)


def test_required_official_searches_keep_uspto_serials_and_classes() -> None:
    uspto_search = REQUIRED_OFFICIAL_SEARCHES["USPTO Trademark Search"]

    assert REQUIRED_TSDR_SERIALS
    assert uspto_search["classes"] == {"9", "35", "38", "41", "42", "45"}


def test_public_naming_review_packet_contains_required_review_inputs() -> None:
    validate_public_naming_review_packet()


def test_public_naming_review_packet_rejects_missing_serial(tmp_path: Path) -> None:
    packet = tmp_path / "PUBLIC_NAMING_REVIEW_PACKET.md"
    packet.write_text(
        "\n".join(
            [
                "# Public Naming Review Packet",
                "",
                "Paid public launch allowed | false",
                "Final clearance decision | pending",
                "Do Not Approve If",
                *sorted(REQUIRED_OPEN_GATES),
                *sorted(REQUIRED_DOMAIN_CANDIDATES),
                *sorted(REQUIRED_WEBSITE_ROUTES),
                *sorted(CONDITIONAL_WEBSITE_ROUTES),
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="missing TSDR serials"):
        validate_public_naming_review_packet(packet)


def test_public_naming_artifact_manifest_contains_required_evidence_docs() -> None:
    validate_public_naming_artifact_manifest()


def test_public_naming_artifact_manifest_rejects_missing_artifact(tmp_path: Path) -> None:
    manifest = tmp_path / "PUBLIC_NAMING_ARTIFACT_MANIFEST.md"
    manifest.write_text(
        "\n".join(
            [
                "# Public Naming Artifact Manifest",
                "",
                "python .\\scripts\\validate_public_naming_readiness.py",
                "python .\\scripts\\validate_release_status.py",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="missing evidence docs"):
        validate_public_naming_artifact_manifest(manifest)


def test_public_naming_release_surface_links_pass() -> None:
    errors = release_status.validate_public_naming_release_surface_links()

    assert errors == []


def test_public_naming_release_surface_links_reject_missing_literal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for relative_path, required_literals in (
        release_status.PUBLIC_NAMING_RELEASE_SURFACE_LITERALS.items()
    ):
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        literals = list(required_literals)
        if relative_path == "README.md":
            literals.remove("docs/PUBLIC_NAMING_REVIEW_PACKET.md")
        path.write_text("\n".join(literals), encoding="utf-8")

    monkeypatch.setattr(release_status, "REPO_ROOT", tmp_path)

    errors = release_status.validate_public_naming_release_surface_links()

    assert len(errors) == 1
    assert "README.md" in errors[0]
    assert "docs/PUBLIC_NAMING_REVIEW_PACKET.md" in errors[0]
