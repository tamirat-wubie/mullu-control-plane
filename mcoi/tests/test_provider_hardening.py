"""Tests for provider policy enforcement and review workflows."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.provider_policy import (
    HttpProviderPolicy,
    PolicyViolationSeverity,
    ProcessProviderPolicy,
    ProviderPolicyType,
    SmtpProviderPolicy,
)
from mcoi_runtime.contracts.review import (
    ReviewDecision,
    ReviewRequest,
    ReviewScope,
    ReviewScopeType,
    ReviewStatus,
)
from mcoi_runtime.governance.policy.provider import ProviderPolicyEnforcer
from mcoi_runtime.core.review import ReviewEngine


T0 = "2025-01-15T10:00:00+00:00"
T1 = "2025-01-15T11:00:00+00:00"


# --- HTTP policy ---


class TestHttpPolicyEnforcement:
    def _policy(self, **kw):
        defaults = dict(policy_id="http-pol-1", allowed_methods=("GET", "POST"))
        defaults.update(kw)
        return HttpProviderPolicy(**defaults)

    def test_allowed_method(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_http(self._policy(), provider_id="p1", method="GET", url="https://api.example.com")
        assert result.allowed

    def test_blocked_method(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_http(self._policy(), provider_id="p1", method="DELETE", url="https://api.example.com")
        assert not result.allowed
        assert any(v.field_name == "method" for v in result.violations)

    def test_https_required(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_http(
            self._policy(require_https=True),
            provider_id="p1", method="GET", url="http://insecure.example.com",
        )
        assert not result.allowed

    def test_https_not_required(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_http(
            self._policy(require_https=False),
            provider_id="p1", method="GET", url="http://ok.example.com",
        )
        assert result.allowed

    def test_content_type_blocked(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_http(
            self._policy(),
            provider_id="p1", method="GET", url="https://x.com",
            content_type="application/xml",
        )
        assert not result.allowed

    def test_response_size_exceeded(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_http(
            self._policy(max_response_bytes=1000),
            provider_id="p1", method="GET", url="https://x.com",
            response_size=5000,
        )
        assert not result.allowed

    def test_multiple_violations(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_http(
            self._policy(require_https=True),
            provider_id="p1", method="DELETE", url="http://x.com",
            content_type="text/xml",
        )
        assert not result.allowed
        assert len(result.violations) >= 2


# --- SMTP policy ---


class TestSmtpPolicyEnforcement:
    def _policy(self, **kw):
        defaults = dict(policy_id="smtp-pol-1")
        defaults.update(kw)
        return SmtpProviderPolicy(**defaults)

    def test_allowed_domain(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_smtp(
            self._policy(allowed_recipient_domains=("company.com",)),
            provider_id="p1", recipient="user@company.com",
        )
        assert result.allowed

    def test_blocked_domain(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_smtp(
            self._policy(allowed_recipient_domains=("company.com",)),
            provider_id="p1", recipient="user@evil.com",
        )
        assert not result.allowed

    def test_no_domain_restriction(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_smtp(self._policy(), provider_id="p1", recipient="anyone@anywhere.com")
        assert result.allowed

    def test_subject_prefix_required(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_smtp(
            self._policy(subject_prefix="[MULLU]"),
            provider_id="p1", recipient="user@co.com", subject="Wrong prefix",
        )
        assert not result.allowed

    def test_subject_prefix_correct(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_smtp(
            self._policy(subject_prefix="[MULLU]"),
            provider_id="p1", recipient="user@co.com", subject="[MULLU] Alert",
        )
        assert result.allowed

    def test_message_size_exceeded(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_smtp(
            self._policy(max_message_bytes=100),
            provider_id="p1", recipient="user@co.com", message_size=500,
        )
        assert not result.allowed

    def test_attachments_denied(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_smtp(
            self._policy(attachments_enabled=False),
            provider_id="p1", recipient="user@co.com", has_attachment=True,
        )
        assert not result.allowed

    def test_attachments_allowed(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_smtp(
            self._policy(attachments_enabled=True),
            provider_id="p1", recipient="user@co.com", has_attachment=True,
        )
        assert result.allowed


# --- Process policy ---


class TestProcessPolicyEnforcement:
    def _policy(self, **kw):
        defaults = dict(policy_id="proc-pol-1")
        defaults.update(kw)
        return ProcessProviderPolicy(**defaults)

    def test_command_allowed(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_process(
            self._policy(command_allowlist=("ls", "cat")),
            provider_id="p1", command="ls -la",
        )
        assert result.allowed

    def test_command_blocked(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_process(
            self._policy(command_allowlist=("ls",)),
            provider_id="p1", command="rm -rf /",
        )
        assert not result.allowed

    def test_no_command_allowlist(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_process(self._policy(), provider_id="p1", command="anything")
        assert result.allowed

    def test_shell_expansion_denied(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_process(
            self._policy(shell_expansion_denied=True),
            provider_id="p1", command="echo test", uses_shell_expansion=True,
        )
        assert not result.allowed

    def test_cwd_not_allowed(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_process(
            self._policy(cwd_allowed=("/home/user",)),
            provider_id="p1", command="ls", cwd="/etc",
        )
        assert not result.allowed

    def test_env_var_not_allowed(self):
        enforcer = ProviderPolicyEnforcer()
        result = enforcer.check_process(
            self._policy(env_allowlist=("PATH",)),
            provider_id="p1", command="echo", env_vars=("SECRET_KEY",),
        )
        assert not result.allowed


# --- Review engine ---


class TestReviewEngine:
    def test_submit_and_get(self):
        engine = ReviewEngine(clock=lambda: T0)
        scope = ReviewScope(scope_type=ReviewScopeType.RUNBOOK_ADMISSION, target_id="rb-1", description="new runbook")
        req = ReviewRequest(request_id="rev-1", requester_id="sys", scope=scope, reason="new admission", requested_at=T0)
        engine.submit(req)
        assert engine.get_request("rev-1") is req

    def test_list_pending(self):
        engine = ReviewEngine(clock=lambda: T0)
        scope = ReviewScope(scope_type=ReviewScopeType.RUNBOOK_ADMISSION, target_id="rb-1", description="x")
        engine.submit(ReviewRequest(request_id="rev-1", requester_id="sys", scope=scope, reason="x", requested_at=T0))
        engine.submit(ReviewRequest(request_id="rev-2", requester_id="sys", scope=scope, reason="x", requested_at=T0))
        assert len(engine.list_pending()) == 2

    def test_approve(self):
        engine = ReviewEngine(clock=lambda: T0)
        scope = ReviewScope(scope_type=ReviewScopeType.INCIDENT_CLOSURE, target_id="inc-1", description="close incident")
        engine.submit(ReviewRequest(request_id="rev-1", requester_id="sys", scope=scope, reason="resolved", requested_at=T0))
        d = engine.decide(request_id="rev-1", reviewer_id="op-1", approved=True, comment="looks good")
        assert d.is_approved
        assert engine.is_review_approved("rev-1")

    def test_reject(self):
        engine = ReviewEngine(clock=lambda: T0)
        scope = ReviewScope(scope_type=ReviewScopeType.DEPLOYMENT_CHANGE, target_id="dep-1", description="profile change")
        engine.submit(ReviewRequest(request_id="rev-1", requester_id="sys", scope=scope, reason="change", requested_at=T0))
        d = engine.decide(request_id="rev-1", reviewer_id="op-1", approved=False)
        assert not d.is_approved
        assert d.is_resolved

    def test_gate_blocks_pending(self):
        engine = ReviewEngine(clock=lambda: T0)
        scope = ReviewScope(scope_type=ReviewScopeType.RUNBOOK_DRIFT, target_id="rb-1", description="drift")
        engine.submit(ReviewRequest(request_id="rev-1", requester_id="sys", scope=scope, reason="drift detected", requested_at=T0))
        allowed, reason = engine.check_gate("rev-1")
        assert not allowed
        assert "pending" in reason

    def test_gate_allows_approved(self):
        engine = ReviewEngine(clock=lambda: T0)
        scope = ReviewScope(scope_type=ReviewScopeType.SKILL_PROMOTION, target_id="sk-1", description="promote skill")
        engine.submit(ReviewRequest(request_id="rev-1", requester_id="sys", scope=scope, reason="verified", requested_at=T0))
        engine.decide(request_id="rev-1", reviewer_id="op-1", approved=True)
        allowed, reason = engine.check_gate("rev-1")
        assert allowed

    def test_expired_review(self):
        engine = ReviewEngine(clock=lambda: T1)
        scope = ReviewScope(scope_type=ReviewScopeType.RUNBOOK_ADMISSION, target_id="rb-1", description="x")
        engine.submit(ReviewRequest(
            request_id="rev-1", requester_id="sys", scope=scope,
            reason="x", requested_at=T0, expires_at=T0,  # Expired
        ))
        d = engine.decide(request_id="rev-1", reviewer_id="op-1", approved=True)
        assert d.status is ReviewStatus.EXPIRED

    def test_gate_blocks_rejected(self):
        engine = ReviewEngine(clock=lambda: T0)
        scope = ReviewScope(scope_type=ReviewScopeType.PROVIDER_POLICY_CHANGE, target_id="pol-1", description="x")
        engine.submit(ReviewRequest(request_id="rev-1", requester_id="sys", scope=scope, reason="x", requested_at=T0))
        engine.decide(request_id="rev-1", reviewer_id="op-1", approved=False)
        allowed, reason = engine.check_gate("rev-1")
        assert not allowed
        assert "not approved" in reason
