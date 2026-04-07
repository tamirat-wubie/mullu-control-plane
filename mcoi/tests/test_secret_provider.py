"""Secret Provider Tests — Pluggable secret backend abstraction."""

import json
import os

import pytest
from mcoi_runtime.core.secret_provider import (
    ChainedSecretProvider,
    EnvSecretProvider,
    FileSecretProvider,
    SecretProvider,
    SecretValue,
)


class TestSecretValueSafety:
    def test_repr_hides_value(self):
        s = SecretValue(key="db_password", value="super_secret_123", source="env")
        assert "super_secret_123" not in repr(s)
        assert "db_password" in repr(s)

    def test_str_hides_value(self):
        s = SecretValue(key="api_key", value="sk-12345", source="file")
        assert "sk-12345" not in str(s)


class TestEnvSecretProvider:
    def test_get_existing(self, monkeypatch):
        monkeypatch.setenv("MULLU_DB_PASSWORD", "secret123")
        p = EnvSecretProvider(prefix="MULLU_")
        result = p.get("db_password", accessor="test")
        assert result is not None
        assert result.value == "secret123"
        assert result.source == "env"

    def test_get_missing(self):
        p = EnvSecretProvider(prefix="MULLU_TEST_MISSING_")
        result = p.get("nonexistent")
        assert result is None

    def test_exists(self, monkeypatch):
        monkeypatch.setenv("MULLU_API_KEY", "test")
        p = EnvSecretProvider(prefix="MULLU_")
        assert p.exists("api_key") is True
        assert p.exists("nonexistent") is False

    def test_list_keys(self, monkeypatch):
        monkeypatch.setenv("MULLU_SECRET_A", "1")
        monkeypatch.setenv("MULLU_SECRET_B", "2")
        p = EnvSecretProvider(prefix="MULLU_SECRET_")
        keys = p.list_keys()
        assert "a" in keys
        assert "b" in keys

    def test_list_keys_no_prefix(self):
        p = EnvSecretProvider()
        assert p.list_keys() == []

    def test_access_log(self, monkeypatch):
        monkeypatch.setenv("MULLU_KEY", "val")
        p = EnvSecretProvider(prefix="MULLU_", clock=lambda: "2026-04-07T12:00:00Z")
        p.get("key", accessor="admin")
        log = p.access_log
        assert len(log) == 1
        assert log[0].key == "key"
        assert log[0].accessor == "admin"
        assert log[0].found is True


class TestFileSecretProvider:
    def test_get_from_file(self, tmp_path):
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({"db_password": "file_secret", "api_key": "sk-123"}))
        p = FileSecretProvider(path=str(secrets_file))
        result = p.get("db_password")
        assert result is not None
        assert result.value == "file_secret"
        assert result.source == "file"

    def test_get_missing_key(self, tmp_path):
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({"a": "1"}))
        p = FileSecretProvider(path=str(secrets_file))
        assert p.get("nonexistent") is None

    def test_missing_file(self, tmp_path):
        p = FileSecretProvider(path=str(tmp_path / "nonexistent.json"))
        assert p.get("key") is None

    def test_corrupted_file(self, tmp_path):
        secrets_file = tmp_path / "bad.json"
        secrets_file.write_text("not json{{{")
        p = FileSecretProvider(path=str(secrets_file))
        assert p.get("key") is None

    def test_exists(self, tmp_path):
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({"a": "1"}))
        p = FileSecretProvider(path=str(secrets_file))
        assert p.exists("a") is True
        assert p.exists("b") is False

    def test_list_keys(self, tmp_path):
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({"x": "1", "y": "2"}))
        p = FileSecretProvider(path=str(secrets_file))
        assert sorted(p.list_keys()) == ["x", "y"]

    def test_reload(self, tmp_path):
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({"v": "1"}))
        p = FileSecretProvider(path=str(secrets_file))
        assert p.get("v").value == "1"
        secrets_file.write_text(json.dumps({"v": "2"}))
        p.reload()
        assert p.get("v").value == "2"

    def test_access_log(self, tmp_path):
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({"k": "v"}))
        p = FileSecretProvider(path=str(secrets_file), clock=lambda: "now")
        p.get("k", accessor="user1")
        assert len(p.access_log) == 1


class TestChainedSecretProvider:
    def test_first_match_wins(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CHAIN_KEY", "from_env")
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({"key": "from_file"}))

        chain = ChainedSecretProvider([
            EnvSecretProvider(prefix="CHAIN_"),
            FileSecretProvider(path=str(secrets_file)),
        ])
        result = chain.get("key")
        assert result is not None
        assert result.value == "from_env"

    def test_fallback_to_second(self, tmp_path):
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({"fallback_key": "from_file"}))

        chain = ChainedSecretProvider([
            EnvSecretProvider(prefix="MISSING_PREFIX_"),
            FileSecretProvider(path=str(secrets_file)),
        ])
        result = chain.get("fallback_key")
        assert result is not None
        assert result.value == "from_file"

    def test_all_miss(self):
        chain = ChainedSecretProvider([
            EnvSecretProvider(prefix="NOTHING_HERE_"),
        ])
        assert chain.get("nonexistent") is None

    def test_exists(self, monkeypatch):
        monkeypatch.setenv("CHAIN_X", "1")
        chain = ChainedSecretProvider([EnvSecretProvider(prefix="CHAIN_")])
        assert chain.exists("x") is True
        assert chain.exists("y") is False

    def test_list_keys_merged(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PFX_A", "1")
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({"b": "2"}))
        chain = ChainedSecretProvider([
            EnvSecretProvider(prefix="PFX_"),
            FileSecretProvider(path=str(secrets_file)),
        ])
        keys = chain.list_keys()
        assert "a" in keys
        assert "b" in keys

    def test_provider_count(self):
        chain = ChainedSecretProvider([SecretProvider(), SecretProvider()])
        assert chain.provider_count == 2


class TestBaseProvider:
    def test_defaults(self):
        p = SecretProvider()
        assert p.get("key") is None
        assert p.exists("key") is False
        assert p.list_keys() == []
