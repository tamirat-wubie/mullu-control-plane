"""Validate the Mullu public naming readiness witness.

Purpose: enforce the machine-readable launch gate for Mullu public naming.
Governance scope: product naming, blocked public names, evidence docs, and
public paid launch gating.
Dependencies: docs/public-naming-readiness.json and referenced evidence docs.
Invariants: public paid launch remains blocked until clearance gates close.
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    import jsonschema
except ImportError:  # pragma: no cover - exercised only in minimal environments.
    jsonschema = None


REPO_ROOT = Path(__file__).resolve().parents[1]
WITNESS_PATH = REPO_ROOT / "docs" / "public-naming-readiness.json"
CLEARANCE_DRAFT_PATH = REPO_ROOT / "docs" / "mullu-name-clearance-draft.json"
PUBLIC_LAUNCH_COPY_PATH = REPO_ROOT / "docs" / "PUBLIC_LAUNCH_COPY.md"
PRODUCT_ROUTE_DRAFT_PATH = REPO_ROOT / "site" / "mullu" / "index.html"
PRODUCT_ROUTE_DEPLOYMENT_HANDOFF_PATH = REPO_ROOT / "docs" / "PRODUCT_ROUTE_DEPLOYMENT_HANDOFF.md"
TSDR_EVIDENCE_TEMPLATE_PATH = REPO_ROOT / "docs" / "TSDR_EVIDENCE_TEMPLATE.md"
WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE_PATH = REPO_ROOT / "docs" / "WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE.md"
WEBSITE_DEPLOYMENT_EVIDENCE_LOG_PATH = REPO_ROOT / "docs" / "WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-07.md"
WEBSITE_DEPLOYMENT_EVIDENCE_SUCCESS_PATH = REPO_ROOT / "docs" / "WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-15.md"
WEBSITE_RECHECK_LOG_PATH = REPO_ROOT / "docs" / "WEBSITE_RECHECK_LOG.md"
DOMAIN_ACQUISITION_PLAN_PATH = REPO_ROOT / "docs" / "DOMAIN_ACQUISITION_PLAN.md"
PUBLIC_NAMING_REVIEW_PACKET_PATH = REPO_ROOT / "docs" / "PUBLIC_NAMING_REVIEW_PACKET.md"
PUBLIC_NAMING_ARTIFACT_MANIFEST_PATH = REPO_ROOT / "docs" / "PUBLIC_NAMING_ARTIFACT_MANIFEST.md"
READINESS_SCHEMA_PATH = REPO_ROOT / "schemas" / "public_naming_readiness.schema.json"
CLEARANCE_SCHEMA_PATH = REPO_ROOT / "schemas" / "mullu_name_clearance_draft.schema.json"


REQUIRED_CLOSED_GATES = {
    "product_identity",
    "company_boundary",
    "platform_boundary",
    "admin_boundary",
    "blocked_generic_names",
    "public_copy",
    "product_route_draft",
    "product_route_deployment_handoff",
    "trademark_runbook",
    "tsdr_evidence_template",
    "domain_plan",
    "website_checklist",
    "website_deployment_evidence_template",
    "website_deployment_probe",
    "website_deployment_verification",
    "website_recheck_log",
    "homepage_update",
    "state_transition_rules",
    "handoff_summary",
    "pr_summary",
    "review_packet",
    "artifact_manifest",
    "clearance_packet_template",
    "domain_ownership_template",
    "draft_clearance_packet",
    "preliminary_web_search",
    "machine_readable_witness",
    "readiness_validator",
    "readiness_tests",
    "readiness_report",
    "transition_planner",
    "naming_schemas",
}

REQUIRED_OPEN_GATES = {
    "uspto_search",
    "wipo_search",
    "euipo_tmview_search",
    "close_variant_review",
    "domain_ownership",
    "legal_review",
    "app_title_update",
    "sdk_api_stability_review",
}

BLOCKED_PUBLIC_NAMES = {
    "Mullusi Handler",
    "Mullusi Work",
    "Mullusi Operator",
    "Mullu AI",
}

REQUIRED_EVIDENCE_DOCS = {
    "docs/PRODUCT_IDENTITY.md",
    "docs/PUBLIC_LAUNCH_COPY.md",
    "site/mullu/index.html",
    "docs/PRODUCT_ROUTE_DEPLOYMENT_HANDOFF.md",
    "docs/PUBLIC_NAMING_READINESS.md",
    "docs/NAMING_MIGRATION_PLAN.md",
    "docs/NAME_CLEARANCE_PRELIMINARY.md",
    "docs/TRADEMARK_SEARCH_RUNBOOK.md",
    "docs/TSDR_EVIDENCE_TEMPLATE.md",
    "docs/DOMAIN_ACQUISITION_PLAN.md",
    "docs/WEBSITE_UPDATE_CHECKLIST.md",
    "docs/WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE.md",
    "docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-07.md",
    "docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-15.md",
    "docs/WEBSITE_RECHECK_LOG.md",
    "docs/PUBLIC_NAMING_STATE_TRANSITION.md",
    "docs/PUBLIC_NAMING_HANDOFF.md",
    "docs/PUBLIC_NAMING_PR_SUMMARY.md",
    "docs/PUBLIC_NAMING_REVIEW_PACKET.md",
    "docs/PUBLIC_NAMING_ARTIFACT_MANIFEST.md",
    "docs/CLEARANCE_PACKET_TEMPLATE.md",
    "docs/DOMAIN_OWNERSHIP_RECORD_TEMPLATE.md",
    "docs/mullu-name-clearance-draft.json",
    "schemas/public_naming_readiness.schema.json",
    "schemas/mullu_name_clearance_draft.schema.json",
    "scripts/validate_public_naming_readiness.py",
    "scripts/report_public_naming_readiness.py",
    "scripts/plan_public_naming_transition.py",
    "tests/test_public_naming_readiness.py",
}

FORBIDDEN_TERMS = {
    "artificial" + " " + "intelligence",
}

REQUIRED_TSDR_SERIALS = {
    "99518598",
    "99264214",
    "85772539",
    "85494313",
    "85222451",
}

REQUIRED_WEBSITE_ROUTES = {
    "https://mullusi.com",
    "https://mullusi.com/mullu",
    "https://mullu.mullusi.com",
}

CONDITIONAL_WEBSITE_ROUTES = {
    "https://docs.mullusi.com",
    "https://dashboard.mullusi.com",
    "https://api.mullusi.com",
}

REQUIRED_DOMAIN_CANDIDATES = {
    "mullu.ai": 1,
    "mullu.app": 2,
    "mullu.dev": 3,
    "getmullu.com": 4,
    "mullu.mullusi.com": 5,
    "mullusi.com/mullu": 6,
}

REQUIRED_OFFICIAL_SEARCHES = {
    "USPTO Trademark Search": {
        "url": "https://tmsearch.uspto.gov",
        "queries": {
            "MULLU",
            "MULLUSI",
            "Mullu by Mullusi",
            "Mullu Inspect",
            "Mullu CLI",
            "Mullu Code",
            "Mullu Control Plane",
            "MULU",
        },
        "classes": {"9", "35", "38", "41", "42", "45"},
    },
    "WIPO Global Brand Database": {
        "url": "https://branddb.wipo.int",
        "queries": {"MULLU", "MULLUSI", "Mullu by Mullusi"},
    },
    "EUIPO eSearch plus and TMview": {
        "url": "https://www.euipo.europa.eu/en/search-ip",
        "queries": {"MULLU", "MULLUSI", "Mullu by Mullusi"},
    },
}


def _load_witness(witness_path: Path = WITNESS_PATH) -> dict[str, object]:
    if not witness_path.exists():
        raise AssertionError(f"Missing witness: {witness_path}")
    return json.loads(witness_path.read_text(encoding="utf-8"))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_no_forbidden_terminology(source_name: str, text: str) -> None:
    lowered_text = text.casefold()
    violations = sorted(term for term in FORBIDDEN_TERMS if term in lowered_text)
    _require(not violations, f"forbidden terminology in {source_name}: {violations}")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def validate_public_launch_copy(copy_path: Path = PUBLIC_LAUNCH_COPY_PATH) -> None:
    copy_text = copy_path.read_text(encoding="utf-8")
    validate_no_forbidden_terminology(_display_path(copy_path), copy_text)
    _require("Mullu, by Mullusi" in copy_text, "public launch copy must include first-reference form")
    _require("Do not use:" in copy_text, "public launch copy must identify blocked names")

    public_copy_before_blocked_section = copy_text.split("Do not use:", maxsplit=1)[0]
    leaked_names = sorted(name for name in BLOCKED_PUBLIC_NAMES if name in public_copy_before_blocked_section)
    _require(not leaked_names, f"blocked public names leaked into launch copy: {leaked_names}")


def validate_product_route_draft(route_path: Path = PRODUCT_ROUTE_DRAFT_PATH) -> None:
    route_text = route_path.read_text(encoding="utf-8")
    validate_no_forbidden_terminology(_display_path(route_path), route_text)
    conflict_markers = ("<<<<<<<", "=======", ">>>>>>>")
    leaked_markers = sorted(marker for marker in conflict_markers if marker in route_text)
    _require(not leaked_markers, f"product route draft contains conflict markers: {leaked_markers}")

    leaked_names = sorted(name for name in BLOCKED_PUBLIC_NAMES if name in route_text)
    _require(not leaked_names, f"blocked public names leaked into product route draft: {leaked_names}")

    required_literals = (
        "<title>Mullu, by Mullusi",
        "Mullu, by Mullusi",
        "Symbols are atomic. Meaning is relational. Traversal is governed. Judgment is earned.",
        "private beta",
        "Request access",
        "Mullu Inspect",
        "Mullu CLI",
        "Mullu Code",
        "Mullu Desk",
        "Mullu Control Plane",
        "Mullusi",
    )
    missing_literals = sorted(literal for literal in required_literals if literal not in route_text)
    _require(not missing_literals, f"product route draft missing literals: {missing_literals}")
    _require(
        "paid public launch" not in route_text.casefold(),
        "product route draft must not advertise paid public launch",
    )


def validate_product_route_deployment_handoff(
    handoff_path: Path = PRODUCT_ROUTE_DEPLOYMENT_HANDOFF_PATH,
) -> None:
    handoff_text = handoff_path.read_text(encoding="utf-8")
    validate_no_forbidden_terminology(_display_path(handoff_path), handoff_text)

    required_literals = (
        "site/mullu/index.html",
        "../mullusi_website/mullu/index.html",
        "https://mullusi.com/mullu",
        "origin/main",
        "https://github.com/mullusi/mullusi-site.git",
        "ea4159d",
        "25919014515",
        "25919013720",
        "mullusi.github.io",
        "Mullu, by Mullusi",
        "private beta",
        "HTTP 200",
        "website_deployment_verification",
    )
    missing_literals = sorted(literal for literal in required_literals if literal not in handoff_text)
    _require(not missing_literals, f"product route deployment handoff missing literals: {missing_literals}")


def validate_tsdr_evidence_template(template_path: Path = TSDR_EVIDENCE_TEMPLATE_PATH) -> None:
    template_text = template_path.read_text(encoding="utf-8")
    validate_no_forbidden_terminology(_display_path(template_path), template_text)
    missing_serials = sorted(serial for serial in REQUIRED_TSDR_SERIALS if serial not in template_text)
    _require(not missing_serials, f"TSDR evidence template missing serials: {missing_serials}")

    missing_urls = sorted(
        serial
        for serial in REQUIRED_TSDR_SERIALS
        if f"https://tsdrapi.uspto.gov/ts/cd/casestatus/sn{serial}/content.html" not in template_text
    )
    _require(not missing_urls, f"TSDR evidence template missing status URLs: {missing_urls}")
    _require("close_variant_review" in template_text, "TSDR template must name close_variant_review gate")


def validate_website_deployment_evidence_template(
    template_path: Path = WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE_PATH,
) -> None:
    template_text = template_path.read_text(encoding="utf-8")
    validate_no_forbidden_terminology(_display_path(template_path), template_text)

    missing_required_routes = sorted(route for route in REQUIRED_WEBSITE_ROUTES if route not in template_text)
    _require(not missing_required_routes, f"website deployment template missing routes: {missing_required_routes}")

    missing_conditional_routes = sorted(route for route in CONDITIONAL_WEBSITE_ROUTES if route not in template_text)
    _require(
        not missing_conditional_routes,
        f"website deployment template missing conditional routes: {missing_conditional_routes}",
    )
    _require(
        "website_deployment_verification" in template_text,
        "website template must name website_deployment_verification gate",
    )
    _require("No GitHub Pages site-not-found page" in template_text, "website template must reject site-not-found pages")


def validate_website_deployment_evidence_log(
    log_path: Path = WEBSITE_DEPLOYMENT_EVIDENCE_LOG_PATH,
) -> None:
    log_text = log_path.read_text(encoding="utf-8")
    validate_no_forbidden_terminology(_display_path(log_path), log_text)

    required_literals = (
        "2026-05-07",
        "https://mullusi.com",
        "https://www.mullusi.com/",
        "HTTP 200",
        "https://mullusi.com/mullu",
        "HTTP 404",
        "https://mullu.mullusi.com",
        "DNS name does not exist",
        "MULLUSI — Symbolic Intelligence",
        "Mullu, by Mullusi",
        "website_deployment_verification",
        "homepage_update",
    )
    missing_literals = sorted(literal for literal in required_literals if literal not in log_text)
    _require(not missing_literals, f"website deployment evidence log missing literals: {missing_literals}")
    _require(
        "not cleared" in log_text,
        "website deployment evidence log must keep the deployment gate blocked",
    )


def validate_website_deployment_success_log(
    log_path: Path = WEBSITE_DEPLOYMENT_EVIDENCE_SUCCESS_PATH,
) -> None:
    log_text = log_path.read_text(encoding="utf-8")
    validate_no_forbidden_terminology(_display_path(log_path), log_text)

    required_literals = (
        "2026-05-15",
        "https://mullusi.com/mullu/",
        "HTTP 200",
        "Mullu, by Mullusi",
        "private beta",
        "Request access",
        "Symbols are atomic. Meaning is relational. Traversal is governed. Judgment is earned.",
        "mullusi/mullusi-site",
        "ea4159d",
        "Validate Site",
        "25919014515",
        "pages-build-deployment",
        "25919013720",
        "https://mullusi.com/sitemap.xml",
        "website_deployment_verification",
        "homepage_update",
    )
    missing_literals = sorted(literal for literal in required_literals if literal not in log_text)
    _require(not missing_literals, f"website deployment success log missing literals: {missing_literals}")
    _require(
        "paid public launch remains blocked" in log_text,
        "website deployment success log must preserve paid-launch blocker",
    )


def validate_website_recheck_log(log_path: Path = WEBSITE_RECHECK_LOG_PATH) -> None:
    log_text = log_path.read_text(encoding="utf-8")
    validate_no_forbidden_terminology(_display_path(log_path), log_text)

    required_literals = (
        "2026-05-07",
        "mullusi.com",
        "GitHub Pages site-not-found",
        "non-authoritative",
        "website_deployment_verification",
        "superseded by direct live-route evidence",
    )
    missing_literals = sorted(literal for literal in required_literals if literal not in log_text)
    _require(not missing_literals, f"website recheck log missing literals: {missing_literals}")
    _require("2026-05-15" in log_text, "website recheck log must reference the superseding live evidence")


def validate_domain_acquisition_plan(plan_path: Path = DOMAIN_ACQUISITION_PLAN_PATH) -> None:
    plan_text = plan_path.read_text(encoding="utf-8")
    validate_no_forbidden_terminology(_display_path(plan_path), plan_text)

    missing_domains = sorted(domain for domain in REQUIRED_DOMAIN_CANDIDATES if domain not in plan_text)
    _require(not missing_domains, f"domain acquisition plan missing candidates: {missing_domains}")
    _require("Either mullu.ai is acquired" in plan_text, "domain plan must preserve minimum launch requirement")
    _require("mullu.mullusi.com is live under controlled Mullusi DNS" in plan_text, "domain plan must preserve DNS fallback")


def validate_clearance_domain_candidates(clearance_draft: dict[str, object]) -> None:
    domain_candidates = clearance_draft.get("domain_candidates", [])
    _require(isinstance(domain_candidates, list), "domain candidates must be a list")

    observed_priorities = {
        candidate.get("domain"): candidate.get("priority")
        for candidate in domain_candidates
        if isinstance(candidate, dict)
    }
    missing_domains = sorted(domain for domain in REQUIRED_DOMAIN_CANDIDATES if domain not in observed_priorities)
    _require(not missing_domains, f"clearance draft missing domain candidates: {missing_domains}")

    wrong_priorities = {
        domain: observed_priorities[domain]
        for domain, expected_priority in REQUIRED_DOMAIN_CANDIDATES.items()
        if observed_priorities.get(domain) != expected_priority
    }
    _require(not wrong_priorities, f"clearance draft domain priorities changed: {wrong_priorities}")


def validate_clearance_official_searches(clearance_draft: dict[str, object]) -> None:
    official_searches = clearance_draft.get("official_searches", [])
    _require(isinstance(official_searches, list), "official searches must be a list")

    searches_by_source = {
        search.get("source"): search
        for search in official_searches
        if isinstance(search, dict)
    }
    missing_sources = sorted(source for source in REQUIRED_OFFICIAL_SEARCHES if source not in searches_by_source)
    _require(not missing_sources, f"clearance draft missing official search sources: {missing_sources}")
    _require(len(official_searches) >= 3, "official search list must include USPTO, WIPO, and EUIPO/TMview")

    for source, expected in REQUIRED_OFFICIAL_SEARCHES.items():
        search = searches_by_source[source]
        _require(search.get("url") == expected["url"], f"{source} URL mismatch")
        _require(search.get("status") == "open", f"{source} must remain open until evidence is recorded")

        required_queries = set(search.get("required_queries", []))
        missing_queries = sorted(expected["queries"] - required_queries)
        _require(not missing_queries, f"{source} missing required queries: {missing_queries}")

        if source == "USPTO Trademark Search":
            missing_serial_queries = sorted(REQUIRED_TSDR_SERIALS - required_queries)
            _require(not missing_serial_queries, f"USPTO search missing TSDR serial queries: {missing_serial_queries}")
            required_classes = set(search.get("required_classes", []))
            missing_classes = sorted(expected["classes"] - required_classes)
            _require(not missing_classes, f"USPTO search missing required classes: {missing_classes}")


def validate_public_naming_review_packet(packet_path: Path = PUBLIC_NAMING_REVIEW_PACKET_PATH) -> None:
    packet_text = packet_path.read_text(encoding="utf-8")
    validate_no_forbidden_terminology(_display_path(packet_path), packet_text)
    _require("Paid public launch allowed | false" in packet_text, "review packet must show launch remains blocked")
    _require("Final clearance decision | pending" in packet_text, "review packet must show final decision is pending")
    _require("Do Not Approve If" in packet_text, "review packet must include rejection criteria")

    missing_open_gates = sorted(gate for gate in REQUIRED_OPEN_GATES if gate not in packet_text)
    _require(not missing_open_gates, f"review packet missing open gates: {missing_open_gates}")

    missing_serials = sorted(serial for serial in REQUIRED_TSDR_SERIALS if serial not in packet_text)
    _require(not missing_serials, f"review packet missing TSDR serials: {missing_serials}")

    missing_domains = sorted(domain for domain in REQUIRED_DOMAIN_CANDIDATES if domain not in packet_text)
    _require(not missing_domains, f"review packet missing domain candidates: {missing_domains}")

    missing_required_routes = sorted(route for route in REQUIRED_WEBSITE_ROUTES if route not in packet_text)
    _require(not missing_required_routes, f"review packet missing required website routes: {missing_required_routes}")

    missing_conditional_routes = sorted(route for route in CONDITIONAL_WEBSITE_ROUTES if route not in packet_text)
    _require(not missing_conditional_routes, f"review packet missing conditional website routes: {missing_conditional_routes}")


def validate_public_naming_artifact_manifest(
    manifest_path: Path = PUBLIC_NAMING_ARTIFACT_MANIFEST_PATH,
) -> None:
    manifest_text = manifest_path.read_text(encoding="utf-8")
    validate_no_forbidden_terminology(_display_path(manifest_path), manifest_text)

    missing_artifacts = sorted(artifact for artifact in REQUIRED_EVIDENCE_DOCS if artifact not in manifest_text)
    _require(not missing_artifacts, f"artifact manifest missing evidence docs: {missing_artifacts}")
    _require("python .\\scripts\\validate_public_naming_readiness.py" in manifest_text, "manifest missing readiness validator command")
    _require("python .\\scripts\\validate_release_status.py" in manifest_text, "manifest missing release validator command")


def _validate_top_level_required(payload: dict[str, object], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if jsonschema is not None:
        try:
            jsonschema.Draft202012Validator(schema).validate(payload)
        except jsonschema.ValidationError as exc:
            path = ".".join(str(part) for part in exc.absolute_path)
            location = f" at {path}" if path else ""
            raise AssertionError(f"{schema_path.name}: schema validation failed{location}: {exc.message}") from exc

    required_fields = set(schema.get("required", []))
    missing_fields = sorted(required_fields - set(payload))
    _require(not missing_fields, f"{schema_path.name}: missing required fields: {missing_fields}")


def validate_public_naming_readiness(witness_path: Path = WITNESS_PATH) -> None:
    witness = _load_witness(witness_path)
    _validate_top_level_required(witness, READINESS_SCHEMA_PATH)
    validate_public_launch_copy()
    validate_product_route_draft()
    validate_product_route_deployment_handoff()
    validate_tsdr_evidence_template()
    validate_website_deployment_evidence_template()
    validate_website_deployment_evidence_log()
    validate_website_deployment_success_log()
    validate_website_recheck_log()
    validate_domain_acquisition_plan()
    validate_public_naming_review_packet()
    validate_public_naming_artifact_manifest()

    _require(witness.get("product_name") == "Mullu", "product_name must be Mullu")
    _require(witness.get("company_brand") == "Mullusi", "company_brand must be Mullusi")
    _require(witness.get("first_reference") == "Mullu, by Mullusi", "first reference mismatch")
    _require(witness.get("platform_term") == "Mullu Platform", "platform term mismatch")
    _require(witness.get("admin_surface") == "Mullu Control Plane", "admin surface mismatch")
    _require(witness.get("public_paid_launch_allowed") is False, "public launch must remain blocked")

    closed_gates = set(witness.get("closed_gates", []))
    open_gates = set(witness.get("open_gates", []))
    blocked_names = set(witness.get("blocked_public_names", []))
    evidence_docs = set(witness.get("evidence_docs", []))

    _require(REQUIRED_CLOSED_GATES <= closed_gates, f"missing closed gates: {sorted(REQUIRED_CLOSED_GATES - closed_gates)}")
    status = witness.get("status")
    if status == "cleared_for_public_launch":
        _require(not open_gates, "cleared status requires no open gates")
        _require(REQUIRED_OPEN_GATES <= closed_gates, f"cleared status requires closed gates: {sorted(REQUIRED_OPEN_GATES - closed_gates)}")
    else:
        _require(REQUIRED_OPEN_GATES <= open_gates, f"missing open gates: {sorted(REQUIRED_OPEN_GATES - open_gates)}")
    _require(not (closed_gates & open_gates), f"gates cannot be both open and closed: {sorted(closed_gates & open_gates)}")
    _require(BLOCKED_PUBLIC_NAMES <= blocked_names, f"missing blocked names: {sorted(BLOCKED_PUBLIC_NAMES - blocked_names)}")
    _require(REQUIRED_EVIDENCE_DOCS <= evidence_docs, f"missing evidence docs: {sorted(REQUIRED_EVIDENCE_DOCS - evidence_docs)}")

    for evidence_doc in evidence_docs:
        evidence_path = REPO_ROOT / evidence_doc
        _require(evidence_path.exists(), f"evidence doc does not exist: {evidence_doc}")
        if evidence_path.suffix in {".md", ".py", ".json"}:
            validate_no_forbidden_terminology(evidence_doc, evidence_path.read_text(encoding="utf-8"))

    clearance_draft = json.loads(CLEARANCE_DRAFT_PATH.read_text(encoding="utf-8"))
    _validate_top_level_required(clearance_draft, CLEARANCE_SCHEMA_PATH)
    validate_clearance_domain_candidates(clearance_draft)
    validate_clearance_official_searches(clearance_draft)
    _require(clearance_draft.get("candidate_name") == "Mullu", "clearance draft candidate mismatch")
    _require(clearance_draft.get("company_brand") == "Mullusi", "clearance draft company mismatch")
    _require(clearance_draft.get("public_paid_launch_allowed") is False, "clearance draft must block public launch")
    _require(clearance_draft.get("final_decision") == "pending", "clearance draft decision must remain pending")

    if status == "cleared_for_public_launch":
        _require(
            clearance_draft.get("final_decision") in {"proceed", "proceed_with_risk_controls"},
            "cleared status requires final decision to proceed or proceed_with_risk_controls",
        )

    summary = clearance_draft.get("summary", {})
    _require(isinstance(summary, dict), "clearance draft summary must be an object")
    _require(summary.get("trademark_clearance") == "not_checked", "trademark clearance must remain open")
    _require(summary.get("legal_clearance") == "not_complete", "legal clearance must remain open")

    clearance_text = CLEARANCE_DRAFT_PATH.read_text(encoding="utf-8")
    missing_clearance_serials = sorted(serial for serial in REQUIRED_TSDR_SERIALS if serial not in clearance_text)
    _require(not missing_clearance_serials, f"clearance draft missing TSDR serials: {missing_clearance_serials}")


def main() -> int:
    try:
        validate_public_naming_readiness()
    except AssertionError as exc:
        print(f"FAILED: {exc}")
        return 1
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
