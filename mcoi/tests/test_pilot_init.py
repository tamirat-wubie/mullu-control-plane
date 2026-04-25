"""Purpose: verify one-command pilot bring-up scaffolding.

Governance scope: local pilot artifact generation and CLI routing only.
Dependencies: pilot_init module and CLI parser.
Invariants: generated files are deterministic; existing files fail closed unless
forced; tenant, policy, budget, dashboard, audit, and lineage artifacts exist.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.app.cli import main
from fastapi.testclient import TestClient

from mcoi_runtime.app.pilot_init import (
    PILOT_FILE_NAMES,
    PilotInitRequest,
    PilotProvisionRegistry,
    build_pilot_scaffold,
    initialize_pilot,
)


def _request(output_dir: Path, *, force: bool = False) -> PilotInitRequest:
    return PilotInitRequest(
        tenant_id="tenant-pilot",
        pilot_name="Acme Pilot",
        output_dir=output_dir,
        policy_pack_id="default-safe",
        policy_version="v0.1",
        max_cost=250.0,
        max_calls=500,
        force=force,
    )


def test_initialize_pilot_writes_complete_artifact_set(tmp_path: Path) -> None:
    result = initialize_pilot(_request(tmp_path / "pilot"))
    written_names = {path.name for path in result.files_written}

    assert result.pilot_id.startswith("pilot-")
    assert written_names == set(PILOT_FILE_NAMES)
    assert result.manifest_path.exists()
    assert json.loads((tmp_path / "pilot" / "tenant.json").read_text(encoding="utf-8"))["tenant_id"] == "tenant-pilot"
    assert json.loads((tmp_path / "pilot" / "budget.json").read_text(encoding="utf-8"))["max_cost"] == 250.0


def test_initialize_pilot_is_deterministic_for_same_inputs(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    first = initialize_pilot(_request(first_dir))
    second = initialize_pilot(_request(second_dir))

    assert first.pilot_id == second.pilot_id
    assert (first_dir / "pilot.manifest.json").read_text(encoding="utf-8") == (
        second_dir / "pilot.manifest.json"
    ).read_text(encoding="utf-8")
    assert (first_dir / "policy.json").read_text(encoding="utf-8") == (second_dir / "policy.json").read_text(
        encoding="utf-8"
    )


def test_build_pilot_scaffold_has_no_filesystem_side_effects(tmp_path: Path) -> None:
    output_dir = tmp_path / "not-written"
    bundle = build_pilot_scaffold(_request(output_dir))

    assert bundle.pilot_id.startswith("pilot-")
    assert set(bundle.artifacts) == set(PILOT_FILE_NAMES)
    assert bundle.artifacts["tenant.json"]["tenant_id"] == "tenant-pilot"
    assert not output_dir.exists()


def test_pilot_provision_registry_persists_bounded_records(tmp_path: Path) -> None:
    registry = PilotProvisionRegistry(max_records=1)
    first_request = _request(tmp_path / "first")
    first_bundle = build_pilot_scaffold(first_request)
    second_request = PilotInitRequest(
        tenant_id="tenant-pilot-2",
        pilot_name="Second Pilot",
        output_dir=tmp_path / "second",
    )
    second_bundle = build_pilot_scaffold(second_request)

    first = registry.accept(request=first_request, bundle=first_bundle, accepted_at="2026-04-25T00:00:00Z")
    second = registry.accept(request=second_request, bundle=second_bundle, accepted_at="2026-04-25T00:00:01Z")
    records = registry.list_records()

    assert first.pilot_id != second.pilot_id
    assert registry.get(first.pilot_id) is None
    assert registry.get(second.pilot_id) == second
    assert records == (second,)


def test_initialize_pilot_fails_closed_on_existing_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "pilot"
    initialize_pilot(_request(output_dir))
    tenant_path = output_dir / "tenant.json"
    original_tenant = tenant_path.read_text(encoding="utf-8")

    with pytest.raises(FileExistsError, match="existing files"):
        initialize_pilot(_request(output_dir))

    assert tenant_path.read_text(encoding="utf-8") == original_tenant
    assert len(list(output_dir.iterdir())) == len(PILOT_FILE_NAMES)


def test_initialize_pilot_force_overwrites_existing_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "pilot"
    initialize_pilot(_request(output_dir))
    (output_dir / "tenant.json").write_text("{}", encoding="utf-8")

    result = initialize_pilot(_request(output_dir, force=True))
    tenant = json.loads((output_dir / "tenant.json").read_text(encoding="utf-8"))

    assert result.manifest_path.exists()
    assert tenant["tenant_id"] == "tenant-pilot"
    assert tenant["status"] == "scaffolded"


def test_cli_pilot_init_routes_to_scaffold(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output_dir = tmp_path / "pilot"

    exit_code = main(
        [
            "pilot",
            "init",
            "--tenant-id",
            "tenant-pilot",
            "--name",
            "Acme Pilot",
            "--output",
            str(output_dir),
        ]
    )
    captured = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["governed"] is True
    assert captured["pilot_id"].startswith("pilot-")
    assert (output_dir / "lineage_examples.json").exists()


def test_cli_pilot_without_subcommand_fails_closed(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["pilot"])
    captured = capsys.readouterr()

    assert exc_info.value.code == 1
    assert "pilot subcommand is required" in captured.err
    assert captured.out == ""


def test_pilot_provision_endpoint_returns_audited_scaffold() -> None:
    from mcoi_runtime.app.server import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/pilots/provision",
        json={
            "tenant_id": "tenant-pilot-http",
            "name": "HTTP Pilot",
            "policy_pack": "default-safe",
            "policy_version": "v0.1",
            "max_cost": 125.0,
            "max_calls": 250,
        },
    )
    audit = client.get("/api/v1/audit?action=pilot.provision.scaffold&limit=5")
    data = response.json()

    assert response.status_code == 200
    assert data["governed"] is True
    assert data["pilot"]["pilot_id"].startswith("pilot-")
    assert data["record"]["pilot_id"] == data["pilot"]["pilot_id"]
    assert data["record"]["tenant_id"] == "tenant-pilot-http"
    assert set(data["pilot"]["artifact_names"]) == set(PILOT_FILE_NAMES)
    assert data["pilot"]["artifacts"]["budget.json"]["max_cost"] == 125.0
    assert audit.status_code == 200
    assert audit.json()["count"] >= 1


def test_pilot_provision_history_routes_return_accepted_records() -> None:
    from mcoi_runtime.app.server import app

    client = TestClient(app)
    provision = client.post(
        "/api/v1/pilots/provision",
        json={
            "tenant_id": "tenant-pilot-history",
            "name": "History Pilot",
        },
    ).json()
    pilot_id = provision["pilot"]["pilot_id"]
    history = client.get("/api/v1/pilots/provisions?tenant_id=tenant-pilot-history&limit=5")
    detail = client.get(f"/api/v1/pilots/provisions/{pilot_id}")

    assert history.status_code == 200
    assert history.json()["governed"] is True
    assert history.json()["records"][0]["pilot_id"] == pilot_id
    assert detail.status_code == 200
    assert detail.json()["record"]["tenant_id"] == "tenant-pilot-history"


def test_pilot_provision_detail_fails_closed_for_missing_record() -> None:
    from mcoi_runtime.app.server import app

    client = TestClient(app)
    response = client.get("/api/v1/pilots/provisions/missing-pilot")

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "pilot_provision_not_found"
    assert response.json()["detail"]["governed"] is True


def test_pilot_provision_endpoint_fails_closed_on_invalid_request() -> None:
    from mcoi_runtime.app.server import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/pilots/provision",
        json={
            "tenant_id": "",
            "name": "HTTP Pilot",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "pilot_provisioning_request_failed"
    assert response.json()["detail"]["governed"] is True
