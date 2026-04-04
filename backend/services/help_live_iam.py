from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote

from botocore.exceptions import ClientError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.action import Action
from backend.models.aws_account import AwsAccount
from backend.models.finding import Finding
from backend.models.user import User
from backend.services.account_trust import canonical_tenant_external_id_async
from backend.services.aws import API_ASSUME_ROLE_SOURCE_IDENTITY, assume_role, build_assume_role_tags

logger = logging.getLogger(__name__)

_MAX_ROLE_SUMMARIES = 8
_MAX_USER_SUMMARIES = 12
_MAX_RISKY_USERS = 8
_LIVE_IAM_SCOPE = "iam_readonly_v1"
_IAM_RESOURCE_TYPES = ("AwsAccount", "AwsIamAccessKey", "AwsIamPolicy", "AwsIamRole", "AwsIamUser")


@dataclass(slots=True)
class HelpLiveLookupCandidateAccount:
    account_id: str
    label: str


@dataclass(slots=True)
class HelpLiveLookupObservation:
    title: str
    summary: str
    details: list[str]


@dataclass(slots=True)
class HelpLiveLookupState:
    status: str
    account_id: str | None = None
    scope: str | None = None
    message: str | None = None
    confirmation_required: bool = False
    candidate_accounts: list[HelpLiveLookupCandidateAccount] | None = None
    observations: list[HelpLiveLookupObservation] | None = None
    observed_at: str | None = None

    def serialize(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidate_accounts"] = [asdict(item) for item in self.candidate_accounts or []]
        payload["observations"] = [asdict(item) for item in self.observations or []]
        return payload


def classify_help_intent(question: str) -> str:
    text = (question or "").strip().lower()
    iam_tokens = ("iam", "role", "trust policy", "access key", "policy", "privilege", "user permissions", "access analyzer")
    if any(token in text for token in iam_tokens):
        return "live_iam_candidate"
    tenant_tokens = ("my account", "my data", "my findings", "my actions", "my security")
    if any(token in text for token in tenant_tokens):
        return "tenant_security"
    return "general_help"


def _entity_account_id(context: dict[str, object]) -> str | None:
    if isinstance(context.get("resolved_account_id"), str):
        return str(context["resolved_account_id"])
    for key in ("account", "action", "finding"):
        value = context.get(key)
        if isinstance(value, dict) and isinstance(value.get("account_id"), str):
            return str(value["account_id"])
    return None


async def _enabled_accounts(db: AsyncSession, *, tenant_id: Any) -> list[AwsAccount]:
    result = await db.execute(
        select(AwsAccount)
        .where(AwsAccount.tenant_id == tenant_id, AwsAccount.ai_live_lookup_enabled.is_(True))
        .order_by(AwsAccount.account_id.asc())
    )
    return list(result.scalars().all())


async def resolve_live_lookup_state(
    db: AsyncSession,
    *,
    current_user: User,
    question: str,
    context: dict[str, object],
    confirm_live_lookup: bool,
) -> tuple[HelpLiveLookupState, AwsAccount | None]:
    if classify_help_intent(question) != "live_iam_candidate":
        return HelpLiveLookupState(status="not_applicable"), None
    enabled_accounts = await _enabled_accounts(db, tenant_id=current_user.tenant_id)
    if not enabled_accounts:
        return HelpLiveLookupState(status="disabled", message="Live IAM account inspection is not enabled for this tenant."), None
    resolved_account_id = _entity_account_id(context)
    if resolved_account_id:
        account = next((item for item in enabled_accounts if item.account_id == resolved_account_id), None)
        if account is None:
            return HelpLiveLookupState(status="disabled", account_id=resolved_account_id, message="Live IAM inspection is not enabled for this account."), None
        if not confirm_live_lookup:
            return HelpLiveLookupState(
                status="pending_confirmation",
                account_id=account.account_id,
                scope=_LIVE_IAM_SCOPE,
                message=f"I can run a live read-only IAM security check for account {account.account_id}. Confirm to continue.",
                confirmation_required=True,
            ), account
        return HelpLiveLookupState(status="ready", account_id=account.account_id, scope=_LIVE_IAM_SCOPE), account
    if len(enabled_accounts) == 1:
        account = enabled_accounts[0]
        if not confirm_live_lookup:
            return HelpLiveLookupState(
                status="pending_confirmation",
                account_id=account.account_id,
                scope=_LIVE_IAM_SCOPE,
                message=f"I can run a live read-only IAM security check for account {account.account_id}. Confirm to continue.",
                confirmation_required=True,
            ), account
        return HelpLiveLookupState(status="ready", account_id=account.account_id, scope=_LIVE_IAM_SCOPE), account
    candidates = [
        HelpLiveLookupCandidateAccount(account_id=item.account_id, label=f"AWS account {item.account_id}")
        for item in enabled_accounts
    ]
    return HelpLiveLookupState(
        status="account_selection_required",
        scope=_LIVE_IAM_SCOPE,
        message="I need a specific enabled AWS account before I can run a live IAM security check.",
        candidate_accounts=candidates,
    ), None


def _safe_trust_document(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        return json.loads(unquote(raw))
    except json.JSONDecodeError:
        return {}


def _principal_values(principal: object) -> list[str]:
    if isinstance(principal, str):
        return [principal]
    if isinstance(principal, list):
        return [str(item) for item in principal if item]
    if isinstance(principal, dict):
        values: list[str] = []
        for item in principal.values():
            values.extend(_principal_values(item))
        return values
    return []


def _role_risk_flags(role: dict[str, Any], *, account_id: str) -> list[str]:
    trust = _safe_trust_document(role.get("AssumeRolePolicyDocument"))
    statements = trust.get("Statement")
    if not isinstance(statements, list):
        statements = [statements] if statements else []
    principals: list[str] = []
    for statement in statements:
        if isinstance(statement, dict):
            principals.extend(_principal_values(statement.get("Principal")))
    flags: list[str] = []
    if "*" in principals:
        flags.append("wildcard trust principal")
    if any(":root" in item and f"::{account_id}:" not in item for item in principals):
        flags.append("cross-account root trust")
    if any("saml-provider" in item or "oidc-provider" in item for item in principals):
        flags.append("federated trust present")
    return flags


def _admin_policy_names(names: list[str]) -> list[str]:
    risky_tokens = ("admin", "administrator", "poweruser", "fullaccess")
    return [name for name in names if any(token in name.lower() for token in risky_tokens)]


def _role_observations(iam: Any, *, account_id: str) -> list[HelpLiveLookupObservation]:
    roles = iam.list_roles(MaxItems=_MAX_ROLE_SUMMARIES).get("Roles", [])
    details: list[str] = []
    risky_names: list[str] = []
    external_trust = 0
    for role in roles[:_MAX_ROLE_SUMMARIES]:
        flags = _role_risk_flags(role, account_id=account_id)
        if any(flag in flags for flag in ("wildcard trust principal", "cross-account root trust")):
            risky_names.append(str(role.get("RoleName") or "unknown"))
            external_trust += 1
        attached = iam.list_attached_role_policies(RoleName=role["RoleName"]).get("AttachedPolicies", [])
        admins = _admin_policy_names([str(item.get("PolicyName") or "") for item in attached])
        if admins:
            details.append(f"{role['RoleName']}: admin-like policies {', '.join(admins[:2])}")
    summary = f"Reviewed {min(len(roles), _MAX_ROLE_SUMMARIES)} IAM roles; {external_trust} showed high-signal trust risks."
    if risky_names:
        details.insert(0, f"Roles with elevated trust risk: {', '.join(risky_names[:4])}")
    return [HelpLiveLookupObservation(title="IAM roles", summary=summary, details=details[:4])]


def _user_observations(iam: Any) -> list[HelpLiveLookupObservation]:
    users = iam.list_users(MaxItems=_MAX_USER_SUMMARIES).get("Users", [])
    key_users: list[str] = []
    for user in users[:_MAX_USER_SUMMARIES]:
        keys = iam.list_access_keys(UserName=user["UserName"]).get("AccessKeyMetadata", [])
        if any(str(item.get("Status") or "").lower() == "active" for item in keys):
            key_users.append(user["UserName"])
    summary = f"Reviewed {min(len(users), _MAX_USER_SUMMARIES)} IAM users; {len(key_users)} currently have active access keys."
    details = [f"Users with active keys: {', '.join(key_users[:_MAX_RISKY_USERS])}"] if key_users else []
    return [HelpLiveLookupObservation(title="IAM users and access keys", summary=summary, details=details)]


def _root_observation(iam: Any) -> HelpLiveLookupObservation:
    summary_map = iam.get_account_summary().get("SummaryMap", {})
    access_keys_present = int(summary_map.get("AccountAccessKeysPresent", 0) or 0)
    mfa_enabled = int(summary_map.get("AccountMFAEnabled", 0) or 0)
    details = [
        f"Root access keys present: {'yes' if access_keys_present else 'no'}",
        f"Root MFA enabled: {'yes' if mfa_enabled else 'no'}",
    ]
    return HelpLiveLookupObservation(
        title="Root account posture",
        summary="Used IAM account summary to check root access-key and MFA posture.",
        details=details,
    )


async def run_live_iam_lookup(
    *,
    account: AwsAccount,
    current_user: User,
    db: AsyncSession,
) -> HelpLiveLookupState:
    try:
        tenant_external_id = await canonical_tenant_external_id_async(db, current_user.tenant_id)
        session = assume_role(
            role_arn=account.role_read_arn,
            external_id=tenant_external_id or "",
            source_identity=f"{API_ASSUME_ROLE_SOURCE_IDENTITY}-help",
            tags=build_assume_role_tags(service_component="help-ai", tenant_id=current_user.tenant_id),
        )
        iam = session.client("iam")
        observations = _role_observations(iam, account_id=account.account_id)
        observations.extend(_user_observations(iam))
        observations.append(_root_observation(iam))
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "AssumeRoleFailed")
        logger.warning("help live iam lookup failed account=%s code=%s", account.account_id, code)
        return HelpLiveLookupState(
            status="failed",
            account_id=account.account_id,
            scope=_LIVE_IAM_SCOPE,
            message="The live IAM check could not be completed with the current ReadRole permissions.",
        )
    return HelpLiveLookupState(
        status="executed",
        account_id=account.account_id,
        scope=_LIVE_IAM_SCOPE,
        message=f"Live read-only IAM inspection completed for account {account.account_id}.",
        observations=observations,
        observed_at=datetime.now(timezone.utc).isoformat(),
    )


async def build_ingested_security_references(
    db: AsyncSession,
    *,
    tenant_id: Any,
    account_id: str | None,
) -> list[dict[str, str]]:
    action_query = select(Action).where(Action.tenant_id == tenant_id)
    finding_query = select(Finding).where(Finding.tenant_id == tenant_id)
    if account_id:
        action_query = action_query.where(Action.account_id == account_id)
        finding_query = finding_query.where(Finding.account_id == account_id)
    action_query = action_query.where(
        or_(
            Action.control_id.ilike("IAM.%"),
            Action.action_type.ilike("iam%"),
            Action.resource_type.in_(_IAM_RESOURCE_TYPES),
        )
    )
    finding_query = finding_query.where(
        or_(
            Finding.control_id.ilike("IAM.%"),
            Finding.canonical_control_id.ilike("IAM.%"),
            Finding.resource_type.in_(_IAM_RESOURCE_TYPES),
        )
    )
    action_result = await db.execute(action_query.order_by(Action.priority.desc()).limit(3))
    finding_result = await db.execute(finding_query.order_by(Finding.severity_normalized.desc()).limit(3))
    return [
        {"type": "action", "id": str(item.id), "label": item.title}
        for item in action_result.scalars().all()
    ] + [
        {"type": "finding", "id": str(item.id), "label": item.title}
        for item in finding_result.scalars().all()
    ]
