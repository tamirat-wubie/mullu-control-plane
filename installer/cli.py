"""mullusi init - interactive setup for the governed agent platform.

Usage: python -m installer.cli init
       python -m installer.cli status
       python -m installer.cli start

Flow:
  1. Choose LLM provider -> enter API key
  2. Choose channels -> enter credentials
  3. Configure first tenant
  4. Generate .env + mullusi.yml
  5. Validate connectivity
  6. Start gateway + API server
"""

from __future__ import annotations

import argparse
import base64
import json
import secrets
from pathlib import Path
from typing import Any


class MulluConfig:
    """Configuration state built during interactive setup."""

    def __init__(self) -> None:
        self.llm_provider: str = "stub"
        self.llm_api_key: str = ""
        self.llm_model: str = ""
        self.db_backend: str = "memory"
        self.db_url: str = ""
        self.postgres_password: str = ""
        self.channels: dict[str, dict[str, str]] = {}
        self.tenant_id: str = "default"
        self.tenant_name: str = "Default Tenant"
        self.jwt_secret: str = ""
        self.encryption_key: str = ""
        self.env: str = "pilot"
        self.cors_origins: str = "https://dashboard.mullusi.com,http://localhost:3000"
        self.state_dir: str = "/var/lib/mullu/state"
        self.command_anchor_key_id: str = "pilot-command-anchor-v1"
        self.command_anchor_secret: str = ""
        self.gateway_approval_secret: str = ""
        self.runtime_witness_secret: str = ""
        self.runtime_conformance_secret: str = ""
        self.capability_worker_secret: str = ""
        self.capability_worker_url: str = "http://capability-worker:8010/capability/execute"

    def ensure_deployment_bindings(self) -> None:
        """Generate missing governed deployment bindings without exposing values."""
        if not self.encryption_key:
            self.encryption_key = base64.b64encode(secrets.token_bytes(32)).decode()
        if not self.command_anchor_secret:
            self.command_anchor_secret = secrets.token_hex(32)
        if not self.gateway_approval_secret:
            self.gateway_approval_secret = secrets.token_hex(32)
        if not self.runtime_witness_secret:
            self.runtime_witness_secret = secrets.token_hex(32)
        if not self.runtime_conformance_secret:
            self.runtime_conformance_secret = secrets.token_hex(32)
        if not self.capability_worker_secret:
            self.capability_worker_secret = secrets.token_hex(32)

    def to_env_dict(self) -> dict[str, str]:
        """Convert to environment variable dict for .env file."""
        strict_env = self.env in ("pilot", "production")
        durable_backend = "postgresql" if self.db_backend == "postgresql" else "memory"
        env: dict[str, str] = {
            "MULLU_ENV": self.env,
            "MULLU_API_AUTH_REQUIRED": "true" if strict_env else "false",
            "MULLU_DB_BACKEND": self.db_backend,
            "MULLU_CORS_ORIGINS": self.cors_origins,
            "MULLU_LLM_BACKEND": self.llm_provider,
            "MULLU_PII_SCAN": "true",
            "MULLU_CERT_ENABLED": "true",
            "MULLU_CERT_INTERVAL": "300",
            "MULLU_STATE_DIR": self.state_dir,
            "MULLU_LLM_BUDGET_MAX_COST": "100.0",
            "MULLU_LLM_BUDGET_MAX_CALLS": "10000",
            "MULLU_COMMAND_LEDGER_BACKEND": durable_backend,
            "MULLU_TENANT_IDENTITY_BACKEND": durable_backend,
            "MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY": "true" if strict_env else "false",
            "MULLU_GATEWAY_DEFER_APPROVED_EXECUTION": "true" if strict_env else "false",
            "MULLU_COMMAND_ANCHOR_KEY_ID": self.command_anchor_key_id,
            "MULLU_REQUIRE_COMMAND_ANCHOR": "true" if strict_env else "false",
            "MULLU_CAPABILITY_WORKER_URL": self.capability_worker_url,
        }
        if self.llm_api_key:
            if self.llm_provider == "anthropic":
                env["ANTHROPIC_API_KEY"] = self.llm_api_key
            elif self.llm_provider == "openai":
                env["OPENAI_API_KEY"] = self.llm_api_key
        if self.llm_model:
            env["MULLU_LLM_MODEL"] = self.llm_model
        if self.db_url:
            env["MULLU_DB_URL"] = self.db_url
            env["MULLU_COMMAND_LEDGER_DB_URL"] = self.db_url
        if self.postgres_password:
            env["POSTGRES_PASSWORD"] = self.postgres_password
        if self.jwt_secret:
            env["MULLU_JWT_SECRET"] = self.jwt_secret
            env["MULLU_JWT_ISSUER"] = "mullu"
            env["MULLU_JWT_AUDIENCE"] = "mullu-api"
        if self.encryption_key:
            env["MULLU_ENCRYPTION_KEY"] = self.encryption_key
        if self.command_anchor_secret:
            env["MULLU_COMMAND_ANCHOR_SECRET"] = self.command_anchor_secret
        if self.gateway_approval_secret:
            env["MULLU_GATEWAY_APPROVAL_SECRET"] = self.gateway_approval_secret
        if self.runtime_witness_secret:
            env["MULLU_RUNTIME_WITNESS_SECRET"] = self.runtime_witness_secret
        if self.runtime_conformance_secret:
            env["MULLU_RUNTIME_CONFORMANCE_SECRET"] = self.runtime_conformance_secret
        if self.capability_worker_secret:
            env["MULLU_CAPABILITY_WORKER_SECRET"] = self.capability_worker_secret

        for creds in self.channels.values():
            for key, value in creds.items():
                env[key] = value

        return env

    def to_yaml_dict(self) -> dict[str, Any]:
        """Convert to mullusi.yml configuration."""
        return {
            "version": "1.0",
            "environment": self.env,
            "llm": {
                "provider": self.llm_provider,
                "model": self.llm_model or "default",
            },
            "database": {
                "backend": self.db_backend,
            },
            "channels": list(self.channels.keys()),
            "tenant": {
                "id": self.tenant_id,
                "name": self.tenant_name,
            },
            "governance": {
                "pii_scan": True,
                "content_safety": True,
                "jwt_auth": bool(self.jwt_secret),
                "field_encryption": bool(self.encryption_key),
            },
        }


def _print_step(title: str) -> None:
    print(f"\n=== {title} ===")


def _prompt(message: str, default: str = "") -> str:
    """Prompt user for input with optional default."""
    if default:
        result = input(f"  {message} [{default}]: ").strip()
        return result or default
    return input(f"  {message}: ").strip()


def _prompt_choice(message: str, choices: list[str], default: str = "") -> str:
    """Prompt user to choose from a list."""
    print(f"\n  {message}")
    for i, choice in enumerate(choices, 1):
        marker = " (default)" if choice == default else ""
        print(f"    {i}. {choice}{marker}")
    while True:
        raw = input(f"  Choose [1-{len(choices)}]: ").strip()
        if not raw and default:
            return default
        try:
            idx = int(raw)
            if 1 <= idx <= len(choices):
                return choices[idx - 1]
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(choices)}")


def _prompt_yn(message: str, default: bool = True) -> bool:
    """Prompt yes/no."""
    hint = "Y/n" if default else "y/N"
    raw = input(f"  {message} [{hint}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def setup_llm(config: MulluConfig) -> None:
    """Step 1: Choose LLM provider and enter API key."""
    _print_step("Step 1: LLM Provider")
    provider = _prompt_choice(
        "Which LLM provider?",
        ["anthropic", "openai", "stub (testing only)"],
        default="anthropic",
    )
    if provider.startswith("stub"):
        config.llm_provider = "stub"
        print("  Using stub provider (no API key needed)")
        return

    config.llm_provider = provider
    config.llm_api_key = _prompt(f"Enter {provider} API key")

    if provider == "anthropic":
        config.llm_model = _prompt("Model name", default="claude-sonnet-4-20250514")
    elif provider == "openai":
        config.llm_model = _prompt("Model name", default="gpt-4o")


def setup_database(config: MulluConfig) -> None:
    """Step 2: Choose database backend."""
    _print_step("Step 2: Database")
    backend = _prompt_choice(
        "Database backend?",
        ["postgresql", "memory (development only)"],
        default="postgresql",
    )
    if backend.startswith("memory"):
        config.db_backend = "memory"
        return

    config.db_backend = "postgresql"
    config.postgres_password = _prompt(
        "PostgreSQL password",
        default=secrets.token_urlsafe(16),
    )
    config.db_url = f"postgresql://mullu:{config.postgres_password}@postgres:5432/mullu"


def setup_channels(config: MulluConfig) -> None:
    """Step 3: Choose and configure channels."""
    _print_step("Step 3: Channels")

    if _prompt_yn("Enable WhatsApp?", default=False):
        config.channels["whatsapp"] = {
            "WHATSAPP_PHONE_NUMBER_ID": _prompt("WhatsApp Phone Number ID"),
            "WHATSAPP_ACCESS_TOKEN": _prompt("WhatsApp Access Token"),
            "WHATSAPP_VERIFY_TOKEN": _prompt(
                "WhatsApp Verify Token",
                default=secrets.token_urlsafe(16),
            ),
        }

    if _prompt_yn("Enable Telegram?", default=False):
        config.channels["telegram"] = {
            "TELEGRAM_BOT_TOKEN": _prompt("Telegram Bot Token"),
        }

    if _prompt_yn("Enable Slack?", default=False):
        config.channels["slack"] = {
            "SLACK_BOT_TOKEN": _prompt("Slack Bot Token"),
            "SLACK_SIGNING_SECRET": _prompt("Slack Signing Secret"),
        }

    if _prompt_yn("Enable Discord?", default=False):
        config.channels["discord"] = {
            "DISCORD_BOT_TOKEN": _prompt("Discord Bot Token"),
            "DISCORD_PUBLIC_KEY": _prompt("Discord Public Key"),
        }

    print("  Web chat: always enabled (no credentials needed)")


def setup_tenant(config: MulluConfig) -> None:
    """Step 4: Configure first tenant."""
    _print_step("Step 4: First Tenant")
    config.tenant_id = _prompt("Tenant ID", default="default")
    config.tenant_name = _prompt("Tenant name", default="Default Tenant")


def setup_security(config: MulluConfig) -> None:
    """Step 5: Generate security keys."""
    _print_step("Step 5: Security")
    if _prompt_yn("Enable JWT authentication?", default=True):
        key = secrets.token_bytes(32)
        config.jwt_secret = base64.b64encode(key).decode()
        print("  JWT secret generated (32 bytes)")

    if _prompt_yn("Enable field encryption?", default=True):
        key = secrets.token_bytes(32)
        config.encryption_key = base64.b64encode(key).decode()
        print("  Encryption key generated (AES-256)")


def write_env_file(config: MulluConfig, path: Path) -> None:
    """Write .env file."""
    config.ensure_deployment_bindings()
    env = config.to_env_dict()
    lines = [f"{k}={v}" for k, v in sorted(env.items())]
    path.write_text("\n".join(lines) + "\n")
    print(f"  Written: {path}")


def write_yaml_file(config: MulluConfig, path: Path) -> None:
    """Write mullusi.yml configuration file."""
    data = config.to_yaml_dict()
    lines = ["# Mullu Platform Configuration", "# Generated by mullusi init", ""]
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for nested_key, nested_value in value.items():
                lines.append(f"  {nested_key}: {json.dumps(nested_value)}")
        elif isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {json.dumps(value)}")
    path.write_text("\n".join(lines) + "\n")
    print(f"  Written: {path}")


def validate_config(config: MulluConfig) -> list[str]:
    """Validate configuration. Returns list of warnings."""
    warnings: list[str] = []
    if config.llm_provider != "stub" and not config.llm_api_key:
        warnings.append("No LLM API key - LLM calls will fail")
    if config.db_backend == "memory":
        warnings.append("Using in-memory database - data lost on restart")
    if not config.channels:
        warnings.append("No channels configured - only web chat available")
    if not config.jwt_secret:
        if config.env in ("pilot", "production"):
            warnings.append(
                "JWT auth disabled - bearer API-key auth remains required in pilot/production"
            )
        else:
            warnings.append(
                "JWT auth disabled - API-key auth is permissive in local_dev/test unless "
                "MULLU_API_AUTH_REQUIRED=true"
            )
    if not config.encryption_key:
        warnings.append("Field encryption disabled - audit data stored in plaintext")
    return warnings


def cmd_init(args: argparse.Namespace) -> int:
    """Interactive setup: configure and generate deployment files."""
    _print_step("MULLU PLATFORM SETUP WIZARD")

    config = MulluConfig()

    if args.non_interactive:
        config.llm_provider = "stub"
        config.db_backend = "memory"
        config.env = "local_dev"
    else:
        setup_llm(config)
        setup_database(config)
        setup_channels(config)
        setup_tenant(config)
        setup_security(config)

    config.ensure_deployment_bindings()
    warnings = validate_config(config)
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  - {warning}")

    root = Path(args.directory)
    root.mkdir(parents=True, exist_ok=True)
    _print_step("Generating Configuration")
    write_env_file(config, root / ".env")
    write_yaml_file(config, root / "mullusi.yml")

    _print_step("Setup Complete")
    print(f"  Configuration written to: {root}")
    print("  Start with: docker compose up")
    print("  Gateway: http://localhost:8001/health")
    print("  API:     http://localhost:8000/health")
    if config.channels:
        print(f"  Channels: {', '.join(config.channels.keys())} + web")
    else:
        print("  Channels: web (configure more with mullusi init)")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show current configuration status."""
    env_path = Path(args.directory) / ".env"
    yml_path = Path(args.directory) / "mullusi.yml"

    _print_step("Mullu Platform Status")
    print(f"  .env exists:         {env_path.exists()}")
    print(f"  mullusi.yml exists:  {yml_path.exists()}")

    if env_path.exists():
        env_vars = dict(
            line.split("=", 1)
            for line in env_path.read_text().strip().split("\n")
            if "=" in line and not line.startswith("#")
        )
        print(f"  LLM provider:       {env_vars.get('MULLU_LLM_BACKEND', 'not set')}")
        print(f"  Database:           {env_vars.get('MULLU_DB_BACKEND', 'not set')}")
        print(
            "  API auth required:  "
            f"{env_vars.get('MULLU_API_AUTH_REQUIRED', 'not set')}"
        )
        print(
            "  JWT auth:           "
            f"{'enabled' if env_vars.get('MULLU_JWT_SECRET') else 'disabled'}"
        )
        print(
            "  Encryption:         "
            f"{'enabled' if env_vars.get('MULLU_ENCRYPTION_KEY') else 'disabled'}"
        )
        channels = []
        if env_vars.get("WHATSAPP_PHONE_NUMBER_ID"):
            channels.append("whatsapp")
        if env_vars.get("TELEGRAM_BOT_TOKEN"):
            channels.append("telegram")
        if env_vars.get("SLACK_BOT_TOKEN"):
            channels.append("slack")
        if env_vars.get("DISCORD_BOT_TOKEN"):
            channels.append("discord")
        channels.append("web")
        print(f"  Channels:           {', '.join(channels)}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mullusi",
        description="Mullu Platform - Governed Autonomous Agent Setup",
    )
    parser.add_argument(
        "--directory",
        "-d",
        default=".",
        help="Project directory (default: current directory)",
    )
    sub = parser.add_subparsers(dest="command")

    init_parser = sub.add_parser("init", help="Interactive setup wizard")
    init_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Use defaults without prompting (for CI/testing)",
    )

    sub.add_parser("status", help="Show configuration status")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        return cmd_init(args)
    if args.command == "status":
        return cmd_status(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
