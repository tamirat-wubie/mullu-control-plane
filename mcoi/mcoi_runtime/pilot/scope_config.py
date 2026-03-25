"""Phase 124A — Pilot Scope Freeze for Regulated Operations Control Tower."""
PILOT_CAPABILITIES = frozenset({
    "intake", "case_management", "approval", "evidence",
    "reporting", "dashboard", "copilot", "governance",
})
PILOT_CONNECTORS = frozenset({
    "email", "identity_sso", "document_storage", "ticketing", "reporting_export",
})
OPTIONAL_CONNECTORS = frozenset({"chat", "calendar", "voice"})
