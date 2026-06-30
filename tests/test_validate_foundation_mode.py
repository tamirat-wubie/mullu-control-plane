"""Tests for the Foundation Mode posture validator.

Purpose: lock current solo-founder Foundation Mode guidance into the test suite.
Governance scope: Foundation Mode, access-language blocking, and current public
copy boundaries.
Dependencies: scripts.validate_foundation_mode.
Invariants: Foundation Mode remains local-proof-first and does not authorize
customer access, pilot access, beta invitation, waitlist, or deployment claims.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_mode import (  # noqa: E402
    FOUNDATION_CORE_GUIDANCE_SURFACES,
    QUIET_PUBLIC_README_REQUIRED_PHRASES,
    REQUIRED_PHRASES_BY_FILE,
    is_quiet_public_readme,
    validate_central_foundation_dependency_headers,
    validate_core_guidance_surface_registration,
    validate_foundation_boundary_status_blocks,
    validate_foundation_boundary_routing_surfaces,
    validate_central_table_label_uniqueness,
    validate_forward_text_boundary,
    validate_foundation_mode,
    validate_foundation_navigation_links,
    validate_foundation_ordered_paths,
    validate_prerequisite_go_deeper_boundary_links,
    validate_required_phrases,
)


def test_foundation_mode_posture_passes() -> None:
    assert validate_foundation_mode() == []


def test_required_phrase_map_covers_current_guidance_surfaces() -> None:
    findings = validate_core_guidance_surface_registration()

    assert findings == []
    for relative_path in FOUNDATION_CORE_GUIDANCE_SURFACES:
        assert relative_path in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_MODE.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PREREQUISITES.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_OPERATOR_READINESS_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_SOLO_DAILY_LOOP_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_LEARNING_PATH_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_MODULE_INVENTORY_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_COMPONENT_CONTRACT_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_INTERFACE_MAP_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_INVARIANT_MAP_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_HAZARD_MAP_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PROOF_REFERENCE_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_GAP_REGISTER_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DIFF_REVIEW_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DOCUMENTATION_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_ACCESSIBILITY_LANGUAGE_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_CAPABILITY_ROADMAP_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_AGENTIC_MANAGEMENT_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_OPERATIONS_RUNBOOK_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_CLAIM_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_MARKET_RESEARCH_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DECISION_JOURNAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_NEXT_ACTION_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_TEST_EVIDENCE_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_LOCAL_PROOF_THREAD.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_SECURITY_BASELINE_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_COST_BUDGET_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_BACKUP_EXPORT_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_RUNTIME_SECRET_HANDOFF_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PRODUCTION_DEPENDENCY_EVIDENCE_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_EXTERNAL_EVIDENCE_ACCEPTANCE_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DEPLOYMENT_UPSTREAM_API_GATE_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DEPLOYMENT_WITNESS_DISPATCH_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DEPLOYMENT_WITNESS_ARTIFACT_VALIDATION_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_GATEWAY_DNS_PUBLICATION_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_GATEWAY_ENDPOINT_REACHABILITY_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_GATEWAY_ENDPOINT_EVIDENCE_RECEIPT_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PUBLIC_HEALTH_DECLARATION_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_GITHUB_APP_TOKEN_FORMAT_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_LEARNING_LOOP_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_CONCEPT_GLOSSARY_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_LIFE_MEANING_DOCTRINE_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_LOCAL_RELEASE_PACKET_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PYTHON_DEPENDENCY_VISIBILITY_REHEARSAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_COMPANY_FORMATION_DEFERRAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PATENT_DISCLOSURE_DEFERRAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_FUNDING_TEAM_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/explain/PLAIN_ENGLISH.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/START_HERE.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/WEBSITE_UPDATE_CHECKLIST.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/PUBLIC_NAMING_REVIEW_PACKET.md" in REQUIRED_PHRASES_BY_FILE
    assert "site/mullu/index.html" in REQUIRED_PHRASES_BY_FILE


def test_core_guidance_surface_registration_missing_entry_is_reported(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("Foundation Mode\n", encoding="utf-8")
    findings = validate_core_guidance_surface_registration(
        tmp_path,
        required_surfaces=("README.md", "docs/START_HERE.md"),
        phrase_map={"README.md": ("Foundation Mode",)},
    )

    assert findings
    assert any(finding.rule_id == "foundation_core_guidance_surface_unregistered" for finding in findings)
    assert any(finding.rule_id == "foundation_core_guidance_surface_missing" for finding in findings)
    assert any("docs/START_HERE.md" in finding.message for finding in findings)


def test_all_foundation_boundary_docs_are_registered_and_routed() -> None:
    findings = validate_foundation_boundary_routing_surfaces()
    boundary_docs = sorted((REPO_ROOT / "docs").glob("FOUNDATION_*BOUNDARY.md"))
    routing_surfaces = (
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "START_HERE.md",
        REPO_ROOT / "docs" / "FOUNDATION_MODE.md",
        REPO_ROOT / "docs" / "CURRENT_READINESS_SNAPSHOT.md",
    )

    assert findings == []
    assert boundary_docs
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8-sig")
    assert is_quiet_public_readme("README.md", readme_text)
    for phrase in QUIET_PUBLIC_README_REQUIRED_PHRASES:
        assert phrase in readme_text
    for boundary_doc in boundary_docs:
        required_key = f"docs/{boundary_doc.name}"
        assert required_key in REQUIRED_PHRASES_BY_FILE
        for routing_surface in routing_surfaces:
            if routing_surface.name == "README.md":
                continue
            assert boundary_doc.name in routing_surface.read_text(encoding="utf-8-sig")


def test_foundation_boundary_routing_surface_missing_link_is_reported(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "FOUNDATION_OPERATOR_BOUNDARY.md").write_text("STATUS:\n", encoding="utf-8")
    for relative_path in (
        "README.md",
        "docs/START_HERE.md",
        "docs/FOUNDATION_MODE.md",
        "docs/CURRENT_READINESS_SNAPSHOT.md",
    ):
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("FOUNDATION_OPERATOR_BOUNDARY.md\n", encoding="utf-8")
    (tmp_path / "docs" / "CURRENT_READINESS_SNAPSHOT.md").write_text("missing route\n", encoding="utf-8")

    findings = validate_foundation_boundary_routing_surfaces(tmp_path)

    assert findings
    assert any(finding.rule_id == "foundation_boundary_route_missing" for finding in findings)
    assert any("docs/CURRENT_READINESS_SNAPSHOT.md" in finding.message for finding in findings)


def test_central_foundation_docs_list_all_boundary_dependencies() -> None:
    findings = validate_central_foundation_dependency_headers()
    boundary_docs = sorted((REPO_ROOT / "docs").glob("FOUNDATION_*BOUNDARY.md"))
    central_docs = (
        REPO_ROOT / "docs" / "FOUNDATION_MODE.md",
        REPO_ROOT / "docs" / "FOUNDATION_PREREQUISITES.md",
    )

    assert findings == []
    assert boundary_docs
    for central_doc in central_docs:
        header = central_doc.read_text(encoding="utf-8-sig").split("-->", 1)[0]
        for boundary_doc in boundary_docs:
            assert boundary_doc.name in header


def test_central_foundation_dependency_header_missing_boundary_is_reported(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "FOUNDATION_ALPHA_BOUNDARY.md").write_text("STATUS:\nAwaitingEvidence\n", encoding="utf-8")
    (docs_dir / "FOUNDATION_BETA_BOUNDARY.md").write_text("STATUS:\nAwaitingEvidence\n", encoding="utf-8")
    header_text = "<!--\nDependencies: docs/FOUNDATION_ALPHA_BOUNDARY.md.\n-->\n"
    (docs_dir / "FOUNDATION_MODE.md").write_text(header_text, encoding="utf-8")
    (docs_dir / "FOUNDATION_PREREQUISITES.md").write_text(header_text, encoding="utf-8")

    findings = validate_central_foundation_dependency_headers(tmp_path)

    assert findings
    assert all(finding.rule_id == "foundation_central_dependency_missing" for finding in findings)
    assert all("FOUNDATION_BETA_BOUNDARY.md" in finding.message for finding in findings)


def test_all_foundation_boundary_docs_have_status_blocks() -> None:
    findings = validate_foundation_boundary_status_blocks()
    boundary_docs = sorted((REPO_ROOT / "docs").glob("FOUNDATION_*BOUNDARY.md"))
    required_status_fields = (
        "STATUS:",
        "Completeness:",
        "Invariants verified:",
        "Open issues:",
        "Next action:",
    )

    assert findings == []
    assert boundary_docs
    for boundary_doc in boundary_docs:
        text = boundary_doc.read_text(encoding="utf-8-sig")

        for required_status_field in required_status_fields:
            assert required_status_field in text, f"{boundary_doc.name} missing {required_status_field}"
        assert "AwaitingEvidence" in text, f"{boundary_doc.name} missing AwaitingEvidence posture"


def test_foundation_boundary_status_block_missing_posture_is_reported(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "FOUNDATION_OPERATOR_BOUNDARY.md").write_text(
        "\n".join(
            (
                "STATUS:",
                "  Completeness: 100%",
                "  Invariants verified: local only",
                "  Open issues: none",
            )
        ),
        encoding="utf-8",
    )

    findings = validate_foundation_boundary_status_blocks(tmp_path)

    assert findings
    assert any(finding.rule_id == "foundation_boundary_status_field_missing" for finding in findings)
    assert any(finding.rule_id == "foundation_boundary_awaiting_evidence_missing" for finding in findings)
    assert any("Next action:" in finding.message for finding in findings)


def test_foundation_navigation_links_stay_repo_local_and_resolve() -> None:
    findings = validate_foundation_navigation_links()
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    navigation_files = (
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "START_HERE.md",
        REPO_ROOT / "docs" / "FOUNDATION_MODE.md",
        REPO_ROOT / "docs" / "FOUNDATION_PREREQUISITES.md",
        REPO_ROOT / "docs" / "CURRENT_READINESS_SNAPSHOT.md",
        *sorted((REPO_ROOT / "docs").glob("FOUNDATION_*BOUNDARY.md")),
    )

    assert findings == []
    for navigation_file in navigation_files:
        text = navigation_file.read_text(encoding="utf-8-sig")
        for match in link_pattern.finditer(text):
            target = match.group(1).strip()
            if (
                not target
                or target.startswith("#")
                or "://" in target
                or target.startswith("mailto:")
            ):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            resolved_path = (navigation_file.parent / target_path).resolve()

            assert resolved_path.is_relative_to(REPO_ROOT)
            assert resolved_path.exists()


def test_foundation_navigation_link_violation_is_reported(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (tmp_path / "README.md").write_text(
        "[outside](../outside.md)\n[missing](docs/MISSING_BOUNDARY.md)\n",
        encoding="utf-8",
    )
    for doc_name in (
        "START_HERE.md",
        "FOUNDATION_MODE.md",
        "FOUNDATION_PREREQUISITES.md",
        "CURRENT_READINESS_SNAPSHOT.md",
        "FOUNDATION_OPERATOR_BOUNDARY.md",
    ):
        (docs_dir / doc_name).write_text("STATUS:\n", encoding="utf-8")

    findings = validate_foundation_navigation_links(tmp_path)

    assert findings
    assert any(finding.rule_id == "foundation_navigation_link_outside_repo" for finding in findings)
    assert any(finding.rule_id == "foundation_navigation_link_missing" for finding in findings)
    assert any("../outside.md" in finding.message for finding in findings)
    assert any("docs/MISSING_BOUNDARY.md" in finding.message for finding in findings)


def test_central_foundation_tables_do_not_repeat_first_column_labels() -> None:
    findings = validate_central_table_label_uniqueness()

    assert findings == []
    assert (REPO_ROOT / "docs" / "FOUNDATION_MODE.md").exists()
    assert (REPO_ROOT / "docs" / "FOUNDATION_PREREQUISITES.md").exists()


def test_central_table_duplicate_label_is_reported(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    for doc_name in (
        "START_HERE.md",
        "FOUNDATION_MODE.md",
        "FOUNDATION_PREREQUISITES.md",
        "CURRENT_READINESS_SNAPSHOT.md",
    ):
        (docs_dir / doc_name).write_text(
            "\n".join(
                (
                    "| Label | Route |",
                    "| --- | --- |",
                    "| Duplicate | first |",
                    "| Duplicate | second |",
                )
            ),
            encoding="utf-8",
        )

    findings = validate_central_table_label_uniqueness(tmp_path)

    assert findings
    assert all(finding.rule_id == "foundation_table_duplicate_label" for finding in findings)
    assert any("repeats first-column label: Duplicate" in finding.message for finding in findings)


def test_start_here_brand_new_path_is_consecutive_and_complete() -> None:
    findings = validate_foundation_ordered_paths()
    text = (REPO_ROOT / "docs" / "START_HERE.md").read_text(encoding="utf-8-sig")
    section = text.split('## 3. The "I\'m brand new" path (do these in order)', 1)[1]
    section = section.split("Now you can wander into", 1)[0]
    entry_pattern = re.compile(
        r"^(?P<number>\d+)\. \*\*\[[^\]]+\]\((?P<target>[^)]+)\)",
        re.MULTILINE,
    )
    entries = [
        (int(match.group("number")), match.group("target"))
        for match in entry_pattern.finditer(section)
    ]
    entry_targets = [target for _, target in entries]
    foundation_targets = {
        target
        for _, target in entries
        if target.startswith("FOUNDATION_")
    }
    expected_foundation_targets = {
        boundary_doc.name
        for boundary_doc in (REPO_ROOT / "docs").glob("FOUNDATION_*BOUNDARY.md")
    }
    expected_foundation_targets.update(
        {
            "FOUNDATION_MODE.md",
            "FOUNDATION_PREREQUISITES.md",
            "FOUNDATION_LOCAL_PROOF_THREAD.md",
        }
    )

    assert findings == []
    assert entries
    assert [number for number, _ in entries] == list(range(1, len(entries) + 1))
    assert len(entry_targets) == len(set(entry_targets))
    assert foundation_targets == expected_foundation_targets
    assert len(foundation_targets) == len(expected_foundation_targets)


def test_foundation_prerequisites_recommended_order_is_consecutive_and_complete() -> None:
    findings = validate_foundation_ordered_paths()
    text = (REPO_ROOT / "docs" / "FOUNDATION_PREREQUISITES.md").read_text(encoding="utf-8-sig")
    section = text.split("## Recommended Order", 1)[1]
    section = section.split("## Narrow Local Proof Thread Definition", 1)[0]
    numbered_line_pattern = re.compile(r"^(?P<number>\d+)\. .+$", re.MULTILINE)
    linked_entry_pattern = re.compile(
        r"^(?P<number>\d+)\. .*?\[[^\]]+\]\((?P<target>FOUNDATION_[^)]+\.md)\)",
        re.MULTILINE,
    )
    numbers = [int(match.group("number")) for match in numbered_line_pattern.finditer(section)]
    entries = [
        (int(match.group("number")), match.group("target"))
        for match in linked_entry_pattern.finditer(section)
    ]
    entry_targets = [target for _, target in entries]
    foundation_targets = {target for _, target in entries if target.startswith("FOUNDATION_")}
    expected_foundation_targets = {
        boundary_doc.name
        for boundary_doc in (REPO_ROOT / "docs").glob("FOUNDATION_*BOUNDARY.md")
    }
    expected_foundation_targets.update(
        {
            "FOUNDATION_MODE.md",
            "FOUNDATION_LOCAL_PROOF_THREAD.md",
        }
    )

    assert findings == []
    assert numbers
    assert numbers == list(range(1, len(numbers) + 1))
    assert len(entry_targets) == len(set(entry_targets))
    assert foundation_targets == expected_foundation_targets
    assert len(foundation_targets) == len(expected_foundation_targets)


def test_foundation_ordered_path_missing_entry_is_reported(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    for doc_name in (
        "FOUNDATION_ALPHA_BOUNDARY.md",
        "FOUNDATION_BETA_BOUNDARY.md",
        "FOUNDATION_MODE.md",
        "FOUNDATION_PREREQUISITES.md",
        "FOUNDATION_LOCAL_PROOF_THREAD.md",
    ):
        (docs_dir / doc_name).write_text("STATUS:\nAwaitingEvidence\n", encoding="utf-8")
    (docs_dir / "START_HERE.md").write_text(
        "\n".join(
            (
                '## 3. The "I\'m brand new" path (do these in order)',
                "1. **[Foundation Mode](FOUNDATION_MODE.md)**",
                "3. **[Foundation Alpha Boundary](FOUNDATION_ALPHA_BOUNDARY.md)**",
                "Now you can wander into other docs.",
            )
        ),
        encoding="utf-8",
    )
    (docs_dir / "FOUNDATION_PREREQUISITES.md").write_text(
        "\n".join(
            (
                "## Recommended Order",
                "1. Keep the current [Foundation Mode](FOUNDATION_MODE.md) boundary intact.",
                "2. Close one local proof thread using [Foundation Local Proof Thread](FOUNDATION_LOCAL_PROOF_THREAD.md).",
                "## Narrow Local Proof Thread Definition",
            )
        ),
        encoding="utf-8",
    )

    findings = validate_foundation_ordered_paths(tmp_path)

    assert findings
    assert any(finding.rule_id == "foundation_start_here_order_numbers_not_consecutive" for finding in findings)
    assert any(finding.rule_id == "foundation_start_here_order_foundation_targets_invalid" for finding in findings)
    assert any(finding.rule_id == "foundation_prerequisite_order_foundation_targets_invalid" for finding in findings)
    assert any("FOUNDATION_BETA_BOUNDARY.md" in finding.message for finding in findings)


def test_foundation_prerequisites_go_deeper_links_all_boundaries() -> None:
    findings = validate_prerequisite_go_deeper_boundary_links()

    assert findings == []
    assert (REPO_ROOT / "docs" / "FOUNDATION_GITHUB_APP_TOKEN_FORMAT_BOUNDARY.md").exists()
    assert "FOUNDATION_GITHUB_APP_TOKEN_FORMAT_BOUNDARY.md" in (
        REPO_ROOT / "docs" / "FOUNDATION_PREREQUISITES.md"
    ).read_text(encoding="utf-8-sig").split("## Go deeper / where to go next", 1)[1]


def test_foundation_prerequisites_go_deeper_missing_boundary_is_reported(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "FOUNDATION_ALPHA_BOUNDARY.md").write_text("STATUS:\n", encoding="utf-8")
    (docs_dir / "FOUNDATION_BETA_BOUNDARY.md").write_text("STATUS:\n", encoding="utf-8")
    (docs_dir / "FOUNDATION_PREREQUISITES.md").write_text(
        "\n".join(
            (
                "## Go deeper / where to go next",
                "",
                "| You now want to... | Go to |",
                "| --- | --- |",
                "| Prepare alpha | [Alpha](FOUNDATION_ALPHA_BOUNDARY.md) |",
            )
        ),
        encoding="utf-8",
    )

    findings = validate_prerequisite_go_deeper_boundary_links(tmp_path)

    assert findings
    assert findings[0].rule_id == "foundation_prerequisite_navigation_boundary_missing"
    assert "FOUNDATION_BETA_BOUNDARY.md" in findings[0].message


def test_required_phrase_validator_rejects_missing_foundation_doc(tmp_path: Path) -> None:
    findings = validate_required_phrases(tmp_path)

    assert findings
    assert any(finding.rule_id == "foundation_file_missing" for finding in findings)


def test_forward_text_boundary_rejects_access_invitation() -> None:
    findings = validate_forward_text_boundary(
        "docs/example.md",
        "Primary action: Request access when ready.",
    )

    assert findings
    assert findings[0].rule_id == "foundation_forbidden_forward_phrase"


def test_forward_text_boundary_allows_blocking_waitlist_language() -> None:
    findings = validate_forward_text_boundary(
        "docs/example.md",
        "Current copy must be foundation-stage with no access, waitlist, or beta invitation.",
    )

    assert findings == []
