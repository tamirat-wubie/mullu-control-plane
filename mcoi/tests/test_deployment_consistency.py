"""Deployment consistency checks for Docker, compose, and installer surfaces."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_installer_cli():
    installer_path = REPO_ROOT / "installer" / "cli.py"
    spec = importlib.util.spec_from_file_location("installer_cli_test", installer_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDockerfileConsistency:
    def test_dockerfile_provisions_state_dir(self):
        dockerfile = (REPO_ROOT / "Dockerfile").read_text()
        assert "ENV MULLU_STATE_DIR=/data/state" in dockerfile
        assert "mkdir -p /data/state" in dockerfile
        assert "chown -R mullu:mullu /data" in dockerfile


class TestComposeConsistency:
    def test_compose_persists_state_volume(self):
        compose = (REPO_ROOT / "docker-compose.yml").read_text()
        assert "state-data:/data/state" in compose
        assert "state-data:" in compose

    def test_compose_sets_explicit_api_auth(self):
        compose = (REPO_ROOT / "docker-compose.yml").read_text()
        assert 'MULLU_API_AUTH_REQUIRED: "true"' in compose


class TestInstallerConsistency:
    def test_installer_emits_explicit_api_auth_by_environment(self):
        installer_cli = _load_installer_cli()

        pilot = installer_cli.MulluConfig()
        pilot.env = "pilot"
        assert pilot.to_env_dict()["MULLU_API_AUTH_REQUIRED"] == "true"

        local_dev = installer_cli.MulluConfig()
        local_dev.env = "local_dev"
        assert local_dev.to_env_dict()["MULLU_API_AUTH_REQUIRED"] == "false"

    def test_installer_warning_matches_current_auth_model(self):
        installer_cli = _load_installer_cli()
        config = installer_cli.MulluConfig()
        config.env = "pilot"

        warnings = installer_cli.validate_config(config)

        assert any("bearer API-key auth remains required" in warning for warning in warnings)
        assert all("API endpoints are unauthenticated" not in warning for warning in warnings)
