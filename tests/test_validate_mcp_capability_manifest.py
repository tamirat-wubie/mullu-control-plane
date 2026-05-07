"""MCP capability manifest validation tests.

Tests: operator-facing MCP manifest validation and CLI evidence output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_mcp_capability_manifest import (  # noqa: E402
    main,
    validate_mcp_capability_manifest,
)


def test_validate_mcp_capability_manifest_accepts_example() -> None:
    manifest_path = Path("examples") / "mcp_capability_manifest.json"

    result = validate_mcp_capability_manifest(manifest_path)

    assert result.ok is True
    assert result.capability_ids == ("mcp.docs_search_docs",)
    assert result.certified_by_refs == ("operator-1",)
    assert result.certification_evidence_refs == ("evidence:mcp-docs-search",)
    assert result.owner_teams == ("knowledge-ops",)
    assert result.ownership_resource_refs == ("mcp.docs_search_docs",)
    assert len(result.approval_policy_ids) == 1
    assert result.approval_policy_capabilities == ("mcp.docs_search_docs",)
    assert result.escalation_policy_ids == ("mcp-escalation-tenant-1",)
    assert result.errors == ()


def test_validate_mcp_capability_manifest_rejects_missing_certification(tmp_path: Path) -> None:
    manifest_path = tmp_path / "mcp_manifest_missing_certification.json"
    manifest_path.write_text(
        json.dumps({
            "tenant_id": "tenant-1",
            "primary_owner_id": "owner-1",
            "fallback_owner_id": "owner-2",
            "escalation_team": "platform-ops",
            "certification_evidence_ref": "evidence:mcp-docs-search",
            "tools": [{
                "server_id": "Docs",
                "name": "Search Docs",
                "description": "Search internal documents.",
                "input_schema": {"type": "object"},
            }],
        }),
        encoding="utf-8",
    )

    result = validate_mcp_capability_manifest(manifest_path)

    assert result.ok is False
    assert result.capability_ids == ()
    assert result.certified_by_refs == ()
    assert result.certification_evidence_refs == ()
    assert result.owner_teams == ()
    assert result.ownership_resource_refs == ()
    assert result.approval_policy_ids == ()
    assert result.approval_policy_capabilities == ()
    assert result.escalation_policy_ids == ()
    assert result.errors == ("MCP manifest requires a configured string field",)


def test_validate_mcp_capability_manifest_rejects_incomplete_runtime_bindings(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manifest_path = tmp_path / "mcp_manifest.json"
    manifest_path.write_text(json.dumps({"tools": []}), encoding="utf-8")

    def _malformed_import(manifest_path: Path, *, clock):  # noqa: ARG001
        capability_id = "mcp.mail_send_email"
        return SimpleNamespace(
            manifest_ref=manifest_path.resolve().as_uri(),
            entries=(
                SimpleNamespace(
                    capability_id=capability_id,
                    domain="mcp",
                    certification_status=SimpleNamespace(value="certified"),
                    metadata={
                        "certified_by": "operator-1",
                        "certification_evidence_ref": "evidence:mcp-mail-send",
                    },
                    obligation_model=SimpleNamespace(owner_team="mail-ops"),
                ),
            ),
            authority_records=SimpleNamespace(
                ownership=(
                    SimpleNamespace(
                        resource_ref=capability_id,
                        owner_team="mail-ops",
                        primary_owner_id="owner-1",
                        fallback_owner_id="owner-2",
                        escalation_team="platform-ops",
                    ),
                ),
                approval_policies=(
                    SimpleNamespace(
                        policy_id="mcp-approval-mail-high",
                        capability=capability_id,
                        risk_tier="high",
                        required_roles=(),
                        required_approver_count=1,
                        separation_of_duty=False,
                        timeout_seconds=600,
                        escalation_policy_id="missing-escalation-policy",
                    ),
                ),
                escalation_policies=(
                    SimpleNamespace(
                        policy_id="mcp-escalation-tenant-1",
                        notify_after_seconds=600,
                        escalate_after_seconds=1200,
                        incident_after_seconds=4800,
                        fallback_owner_id="owner-2",
                        escalation_team="platform-ops",
                    ),
                ),
            ),
        )

    monkeypatch.setattr(
        "scripts.validate_mcp_capability_manifest.build_mcp_gateway_import_from_manifest",
        _malformed_import,
    )

    result = validate_mcp_capability_manifest(manifest_path)

    assert result.ok is False
    assert result.capability_ids == ("mcp.mail_send_email",)
    assert "MCP manifest approval policy missing required roles: mcp-approval-mail-high" in result.errors
    assert "MCP manifest high-risk approval policy requires dual approval: mcp-approval-mail-high" in result.errors
    assert "MCP manifest high-risk approval policy requires separation of duty: mcp-approval-mail-high" in result.errors
    assert (
        "MCP manifest approval policy references missing escalation policy: mcp-approval-mail-high"
        in result.errors
    )


def test_validate_mcp_capability_manifest_cli_outputs_json(capsys) -> None:
    exit_code = main([
        "--manifest",
        str(Path("examples") / "mcp_capability_manifest.json"),
        "--json",
    ])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["capability_count"] == 1
    assert payload["certified_by_refs"] == ["operator-1"]
    assert payload["certification_evidence_refs"] == ["evidence:mcp-docs-search"]
    assert payload["owner_teams"] == ["knowledge-ops"]
    assert payload["ownership_count"] == 1
    assert payload["approval_policy_count"] == 1
    assert payload["capability_ids"] == ["mcp.docs_search_docs"]
    assert payload["approval_policy_capabilities"] == ["mcp.docs_search_docs"]


def test_validate_mcp_capability_manifest_cli_fails_invalid(tmp_path: Path, capsys) -> None:
    manifest_path = tmp_path / "invalid_mcp_manifest.json"
    manifest_path.write_text(json.dumps({"tools": []}), encoding="utf-8")

    exit_code = main(["--manifest", str(manifest_path)])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "error:" in captured.out
    assert "MCP manifest requires at least one tool" in captured.out
    assert captured.err == ""
