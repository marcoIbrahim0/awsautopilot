from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_cookie_auth_and_csrf_controls_are_present() -> None:
    auth_text = _read("backend/auth.py")

    required_tokens = (
        "AUTH_COOKIE_NAME = \"access_token\"",
        "CSRF_COOKIE_NAME = \"csrf_token\"",
        "CSRF_HEADER_NAME = \"X-CSRF-Token\"",
        "def set_auth_cookies",
        "def clear_auth_cookies",
        "def _enforce_csrf_for_cookie_auth",
        "request.cookies.get(AUTH_COOKIE_NAME)",
        "status.HTTP_403_FORBIDDEN",
    )

    for token in required_tokens:
        assert token in auth_text


def test_auth_routes_issue_and_clear_cookie_session() -> None:
    auth_router = _read("backend/routers/auth.py")
    users_router = _read("backend/routers/users.py")

    assert "set_auth_cookies(response, access_token)" in auth_router
    assert "@router.post(\"/logout\"" in auth_router
    assert "clear_auth_cookies(response)" in auth_router
    assert "set_auth_cookies(response, access_token)" in users_router


def test_frontend_auth_removes_localstorage_bearer_usage() -> None:
    auth_context = _read("frontend/src/contexts/AuthContext.tsx")
    api_client = _read("frontend/src/lib/api.ts")
    combined = auth_context + "\n" + api_client

    forbidden_tokens = (
        "localStorage.setItem",
        "localStorage.getItem",
        "localStorage[",
        "Authorization': `Bearer",
        "Authorization: `Bearer",
    )

    for token in forbidden_tokens:
        assert token not in combined

    required_tokens = (
        "credentials: 'include'",
        "CSRF_HEADER_NAME",
        "applyCsrfHeader",
        "buildCsrfHeader",
    )

    for token in required_tokens:
        assert token in combined


def test_frontend_csp_and_security_headers_are_configured() -> None:
    text = _read("frontend/next.config.ts")

    required_tokens = (
        "Content-Security-Policy",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Strict-Transport-Security",
        "default-src 'self'",
    )

    for token in required_tokens:
        assert token in text


def test_edge_protection_template_has_waf_rate_limit_and_alarms() -> None:
    text = _read("infrastructure/cloudformation/edge-protection.yaml")

    required_tokens = (
        "Type: AWS::WAFv2::WebACL",
        "AWSManagedRulesCommonRuleSet",
        "AWSManagedRulesKnownBadInputsRuleSet",
        "RateBasedStatement",
        "EnableIpv4AllowList",
        "AllowedIpv4Cidrs",
        "Type: AWS::WAFv2::WebACLAssociation",
        "Type: AWS::CloudWatch::Alarm",
        "MetricName: BlockedRequests",
    )

    for token in required_tokens:
        assert token in text


def test_edge_docs_and_phase3_security_checklist_exist_with_expected_content() -> None:
    architecture_text = _read("docs/edge-protection-architecture.md")
    runbook_text = _read("docs/edge-traffic-incident-runbook.md")
    checklist_text = _read("docs/audit-remediation/phase3-security-closure-checklist.md")
    evidence_script = _read("scripts/collect_phase3_security_evidence.py")

    architecture_tokens = (
        "edge-protection.yaml",
        "AWSManagedRulesCommonRuleSet",
        "IPAddressRateLimit",
        "cookie",
        "CSRF",
    )

    for token in architecture_tokens:
        assert token in architecture_text

    runbook_tokens = (
        "get-sampled-requests",
        "RateLimitRequestsPer5Min",
        "blocked-requests",
        "rate-limit-triggered",
    )

    for token in runbook_tokens:
        assert token in runbook_text

    checklist_tokens = (
        "SEC-008",
        "SEC-010",
        "test_security_phase3_hardening.py",
        "security-phase3.yml",
        "collect_phase3_security_evidence.py",
    )

    for token in checklist_tokens:
        assert token in checklist_text

    assert "Phase 3 security evidence" in evidence_script
