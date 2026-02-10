"""
AWS account resource teardown utilities for account disconnect flow.

Best-effort cleanup targets resources created by onboarding templates:
- IAM roles: SecurityAutopilotReadRole / SecurityAutopilotWriteRole
- IAM managed policies: SecurityAutopilotReadRolePolicy / SecurityAutopilotWriteRolePolicy
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from botocore.exceptions import ClientError

from backend.models.aws_account import AwsAccount
from backend.services.aws import assume_role

logger = logging.getLogger(__name__)

DEFAULT_ROLE_NAMES = {
    "SecurityAutopilotReadRole",
    "SecurityAutopilotWriteRole",
}

DEFAULT_POLICY_NAMES = {
    "SecurityAutopilotReadRolePolicy",
    "SecurityAutopilotWriteRolePolicy",
}


class AwsCleanupError(Exception):
    """Raised when required cleanup cannot be completed."""


@dataclass
class CleanupSummary:
    """Summary of detached/deleted resources."""

    roles_deleted: set[str]
    policies_deleted: set[str]
    roles_missing: set[str]
    policies_missing: set[str]


def _role_name_from_arn(role_arn: str | None) -> str | None:
    if not role_arn or ":role/" not in role_arn:
        return None
    return role_arn.split(":role/", 1)[1].split("/")[-1] or None


def _candidate_role_names(account: AwsAccount) -> set[str]:
    names = set(DEFAULT_ROLE_NAMES)
    read_name = _role_name_from_arn(account.role_read_arn)
    write_name = _role_name_from_arn(account.role_write_arn)
    if read_name:
        names.add(read_name)
    if write_name:
        names.add(write_name)
    return names


def _candidate_policy_names() -> set[str]:
    return set(DEFAULT_POLICY_NAMES)


def _is_no_such_entity(err: ClientError) -> bool:
    return err.response.get("Error", {}).get("Code") == "NoSuchEntity"


def _delete_policy_versions(iam, policy_arn: str) -> None:
    versions = iam.list_policy_versions(PolicyArn=policy_arn).get("Versions", [])
    for version in versions:
        if not version.get("IsDefaultVersion"):
            iam.delete_policy_version(PolicyArn=policy_arn, VersionId=version["VersionId"])


def _delete_managed_policy(iam, policy_arn: str) -> bool:
    try:
        _delete_policy_versions(iam, policy_arn)
        iam.delete_policy(PolicyArn=policy_arn)
        return True
    except ClientError as err:
        if _is_no_such_entity(err):
            return False
        raise


def _find_customer_policy_arn(iam, policy_name: str) -> str | None:
    paginator = iam.get_paginator("list_policies")
    for page in paginator.paginate(Scope="Local"):
        for policy in page.get("Policies", []):
            if policy.get("PolicyName") == policy_name:
                return policy.get("Arn")
    return None


def _delete_role_and_attachments(iam, role_name: str) -> tuple[bool, set[str], set[str]]:
    detached_policy_arns: set[str] = set()
    deleted_inline_policy_names: set[str] = set()
    try:
        attached = iam.list_attached_role_policies(RoleName=role_name).get("AttachedPolicies", [])
    except ClientError as err:
        if _is_no_such_entity(err):
            return False, detached_policy_arns, deleted_inline_policy_names
        raise

    for policy in attached:
        policy_arn = policy.get("PolicyArn")
        if policy_arn:
            iam.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            detached_policy_arns.add(policy_arn)

    inline_names = iam.list_role_policies(RoleName=role_name).get("PolicyNames", [])
    for inline_name in inline_names:
        iam.delete_role_policy(RoleName=role_name, PolicyName=inline_name)
        deleted_inline_policy_names.add(inline_name)

    iam.delete_role(RoleName=role_name)
    return True, detached_policy_arns, deleted_inline_policy_names


def _assume_first_available_role(role_arns: Iterable[str | None], external_id: str):
    assume_errors: list[str] = []
    for role_arn in role_arns:
        if not role_arn:
            continue
        try:
            return assume_role(role_arn=role_arn, external_id=external_id)
        except ClientError as err:
            code = err.response.get("Error", {}).get("Code", "Unknown")
            message = err.response.get("Error", {}).get("Message", str(err))
            assume_errors.append(f"{role_arn} -> {code}: {message}")
    if not assume_errors:
        raise AwsCleanupError("No role ARN available for AWS cleanup.")
    raise AwsCleanupError("Unable to assume cleanup role. " + " | ".join(assume_errors))


def cleanup_account_resources(account: AwsAccount, external_id: str) -> CleanupSummary:
    """
    Delete Autopilot IAM resources in the customer account before disconnect.

    This function intentionally fails hard on AWS permission errors so callers can
    block account removal when cleanup cannot complete.
    """
    session = _assume_first_available_role(
        role_arns=[account.role_write_arn, account.role_read_arn],
        external_id=external_id,
    )
    iam = session.client("iam")

    candidate_policy_names = _candidate_policy_names()
    roles_deleted: set[str] = set()
    roles_missing: set[str] = set()
    policies_deleted: set[str] = set()
    policies_missing: set[str] = set()

    detached_policy_arns: set[str] = set()
    for role_name in _candidate_role_names(account):
        deleted, detached, _inline_deleted = _delete_role_and_attachments(iam, role_name)
        detached_policy_arns.update(detached)
        if deleted:
            roles_deleted.add(role_name)
        else:
            roles_missing.add(role_name)

    for policy_arn in detached_policy_arns:
        policy_name = policy_arn.rsplit("/", 1)[-1]
        if policy_name in candidate_policy_names and _delete_managed_policy(iam, policy_arn):
            policies_deleted.add(policy_name)

    for policy_name in candidate_policy_names:
        if policy_name in policies_deleted:
            continue
        policy_arn = _find_customer_policy_arn(iam, policy_name)
        if not policy_arn:
            policies_missing.add(policy_name)
            continue
        if _delete_managed_policy(iam, policy_arn):
            policies_deleted.add(policy_name)

    summary = CleanupSummary(
        roles_deleted=roles_deleted,
        policies_deleted=policies_deleted,
        roles_missing=roles_missing,
        policies_missing=policies_missing,
    )
    logger.info(
        "AWS account cleanup summary account_id=%s roles_deleted=%s policies_deleted=%s roles_missing=%s policies_missing=%s",
        account.account_id,
        sorted(summary.roles_deleted),
        sorted(summary.policies_deleted),
        sorted(summary.roles_missing),
        sorted(summary.policies_missing),
    )
    return summary
