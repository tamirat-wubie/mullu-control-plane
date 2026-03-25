from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class ConnectorProfile:
    connector_type: str
    display_name: str
    endpoint_url: str
    auth_method: str  # "oauth2", "api_key", "basic", "saml"
    health_check_path: str
    timeout_ms: int = 5000
    max_retries: int = 3
    backoff_ms: int = 1000

# Default profiles for the 5 required connectors
EMAIL_PROFILE = ConnectorProfile("email", "Email (SMTP/IMAP)", "smtp://localhost:587", "basic", "/health")
IDENTITY_SSO_PROFILE = ConnectorProfile("identity_sso", "Identity/SSO (SAML/OIDC)", "https://idp.example.com", "saml", "/.well-known/openid-configuration")
DOCUMENT_STORAGE_PROFILE = ConnectorProfile("document_storage", "Document Storage (S3/Blob)", "https://storage.example.com", "api_key", "/health")
TICKETING_PROFILE = ConnectorProfile("ticketing", "Ticketing/Helpdesk", "https://helpdesk.example.com/api", "oauth2", "/api/health")
REPORTING_EXPORT_PROFILE = ConnectorProfile("reporting_export", "Reporting Export (SFTP/API)", "sftp://reports.example.com", "api_key", "/status")

ALL_REQUIRED_PROFILES = (EMAIL_PROFILE, IDENTITY_SSO_PROFILE, DOCUMENT_STORAGE_PROFILE, TICKETING_PROFILE, REPORTING_EXPORT_PROFILE)
