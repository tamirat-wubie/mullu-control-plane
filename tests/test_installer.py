"""Installer CLI Tests.

Tests: Configuration model, file generation, validation,
    non-interactive mode, status command.
"""

import sys
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest
from installer.cli import (
    MulluConfig,
    build_parser,
    cmd_init,
    cmd_status,
    validate_config,
    write_env_file,
    write_yaml_file,
)


# ═══ MulluConfig ═══


class TestMulluConfig:
    def test_default_config(self):
        cfg = MulluConfig()
        assert cfg.llm_provider == "stub"
        assert cfg.db_backend == "memory"
        assert cfg.tenant_id == "default"

    def test_to_env_dict_minimal(self):
        cfg = MulluConfig()
        env = cfg.to_env_dict()
        assert env["MULLU_ENV"] == "pilot"
        assert env["MULLU_DB_BACKEND"] == "memory"
        assert env["MULLU_LLM_BACKEND"] == "stub"

    def test_to_env_dict_with_anthropic(self):
        cfg = MulluConfig()
        cfg.llm_provider = "anthropic"
        cfg.llm_api_key = "sk-test-key"
        cfg.llm_model = "claude-sonnet-4-20250514"
        env = cfg.to_env_dict()
        assert env["ANTHROPIC_API_KEY"] == "sk-test-key"
        assert env["MULLU_LLM_MODEL"] == "claude-sonnet-4-20250514"

    def test_to_env_dict_with_openai(self):
        cfg = MulluConfig()
        cfg.llm_provider = "openai"
        cfg.llm_api_key = "sk-openai-key"
        env = cfg.to_env_dict()
        assert env["OPENAI_API_KEY"] == "sk-openai-key"

    def test_to_env_dict_with_channels(self):
        cfg = MulluConfig()
        cfg.channels["whatsapp"] = {"WHATSAPP_PHONE_NUMBER_ID": "123"}
        cfg.channels["telegram"] = {"TELEGRAM_BOT_TOKEN": "tok"}
        env = cfg.to_env_dict()
        assert env["WHATSAPP_PHONE_NUMBER_ID"] == "123"
        assert env["TELEGRAM_BOT_TOKEN"] == "tok"

    def test_to_env_dict_with_security(self):
        cfg = MulluConfig()
        cfg.jwt_secret = "jwt-secret-base64"
        cfg.encryption_key = "enc-key-base64"
        env = cfg.to_env_dict()
        assert env["MULLU_JWT_SECRET"] == "jwt-secret-base64"
        assert env["MULLU_ENCRYPTION_KEY"] == "enc-key-base64"

    def test_to_yaml_dict(self):
        cfg = MulluConfig()
        cfg.llm_provider = "anthropic"
        cfg.channels["telegram"] = {"TELEGRAM_BOT_TOKEN": "tok"}
        data = cfg.to_yaml_dict()
        assert data["version"] == "1.0"
        assert data["llm"]["provider"] == "anthropic"
        assert "telegram" in data["channels"]


# ═══ Validation ═══


class TestValidation:
    def test_stub_provider_no_warning(self):
        cfg = MulluConfig()
        cfg.llm_provider = "stub"
        warnings = validate_config(cfg)
        assert not any("LLM API key" in w for w in warnings)

    def test_real_provider_without_key_warns(self):
        cfg = MulluConfig()
        cfg.llm_provider = "anthropic"
        cfg.llm_api_key = ""
        warnings = validate_config(cfg)
        assert any("LLM API key" in w for w in warnings)

    def test_memory_backend_warns(self):
        cfg = MulluConfig()
        warnings = validate_config(cfg)
        assert any("in-memory" in w for w in warnings)

    def test_no_channels_warns(self):
        cfg = MulluConfig()
        warnings = validate_config(cfg)
        assert any("No channels" in w for w in warnings)

    def test_no_jwt_warns(self):
        cfg = MulluConfig()
        warnings = validate_config(cfg)
        assert any("JWT" in w for w in warnings)

    def test_fully_configured_minimal_warnings(self):
        cfg = MulluConfig()
        cfg.llm_provider = "anthropic"
        cfg.llm_api_key = "key"
        cfg.db_backend = "postgresql"
        cfg.channels["telegram"] = {"TELEGRAM_BOT_TOKEN": "tok"}
        cfg.jwt_secret = "secret"
        cfg.encryption_key = "key"
        warnings = validate_config(cfg)
        assert len(warnings) == 0


# ═══ File Generation ═══


class TestFileGeneration:
    def test_write_env_file(self, tmp_path):
        cfg = MulluConfig()
        cfg.llm_provider = "anthropic"
        cfg.llm_api_key = "test-key"
        env_path = tmp_path / ".env"
        write_env_file(cfg, env_path)
        content = env_path.read_text()
        assert "ANTHROPIC_API_KEY=test-key" in content
        assert "MULLU_LLM_BACKEND=anthropic" in content

    def test_write_yaml_file(self, tmp_path):
        cfg = MulluConfig()
        yml_path = tmp_path / "mullusi.yml"
        write_yaml_file(cfg, yml_path)
        content = yml_path.read_text()
        assert "Mullu Platform Configuration" in content
        assert "version" in content

    def test_env_file_one_var_per_line(self, tmp_path):
        cfg = MulluConfig()
        cfg.jwt_secret = "secret"
        env_path = tmp_path / ".env"
        write_env_file(cfg, env_path)
        lines = env_path.read_text().strip().split("\n")
        for line in lines:
            assert "=" in line
            parts = line.split("=", 1)
            assert len(parts) == 2


# ═══ Non-Interactive Init ═══


class TestNonInteractiveInit:
    def test_non_interactive_creates_files(self, tmp_path):
        args = build_parser().parse_args(["--directory", str(tmp_path), "init", "--non-interactive"])
        result = cmd_init(args)
        assert result == 0
        assert (tmp_path / ".env").exists()
        assert (tmp_path / "mullusi.yml").exists()

    def test_non_interactive_uses_defaults(self, tmp_path):
        args = build_parser().parse_args(["--directory", str(tmp_path), "init", "--non-interactive"])
        cmd_init(args)
        content = (tmp_path / ".env").read_text()
        assert "MULLU_LLM_BACKEND=stub" in content
        assert "MULLU_DB_BACKEND=memory" in content


# ═══ Status Command ═══


class TestStatusCommand:
    def test_status_no_config(self, tmp_path, capsys):
        args = build_parser().parse_args(["--directory", str(tmp_path), "status"])
        result = cmd_status(args)
        assert result == 0
        output = capsys.readouterr().out
        assert "False" in output  # .env doesn't exist

    def test_status_with_config(self, tmp_path, capsys):
        # Create .env first
        cfg = MulluConfig()
        cfg.llm_provider = "anthropic"
        cfg.llm_api_key = "key"
        write_env_file(cfg, tmp_path / ".env")
        write_yaml_file(cfg, tmp_path / "mullusi.yml")

        args = build_parser().parse_args(["--directory", str(tmp_path), "status"])
        cmd_status(args)
        output = capsys.readouterr().out
        assert "anthropic" in output


# ═══ Parser ═══


class TestParser:
    def test_init_command(self):
        args = build_parser().parse_args(["init"])
        assert args.command == "init"

    def test_status_command(self):
        args = build_parser().parse_args(["status"])
        assert args.command == "status"

    def test_non_interactive_flag(self):
        args = build_parser().parse_args(["init", "--non-interactive"])
        assert args.non_interactive is True

    def test_directory_option(self):
        args = build_parser().parse_args(["--directory", "/tmp/test", "init"])
        assert args.directory == "/tmp/test"
