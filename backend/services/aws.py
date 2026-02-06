"""
AWS service utilities for assuming customer roles and interacting with AWS services.

Core function: assume_role() - securely assumes customer IAM roles using STS with ExternalId.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError

from backend.config import settings

if TYPE_CHECKING:
    from mypy_boto3_sts import STSClient

logger = logging.getLogger(__name__)

# Retry configuration for transient errors
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1


def assume_role(
    role_arn: str,
    external_id: str,
    session_name: str | None = None,
) -> boto3.Session:
    """
    Assumes an IAM role using STS and returns a boto3 session.

    Args:
        role_arn: The ARN of the role to assume (e.g., "arn:aws:iam::123456789012:role/ReadRole")
        external_id: The ExternalId value (from tenant) - must match the role's trust policy
        session_name: Identifier for this assume-role session. Defaults to settings.ROLE_SESSION_NAME.

    Returns:
        boto3.Session with temporary credentials from the assumed role.

    Raises:
        ClientError: If assume role fails (invalid ARN, wrong ExternalId, access denied, etc.)
        ValueError: If role_arn or external_id are invalid/empty

    Example:
        >>> session = assume_role(
        ...     role_arn="arn:aws:iam::123456789012:role/SecurityAutopilotReadRole",
        ...     external_id="tenant-123-external-id"
        ... )
        >>> sts = session.client("sts")
        >>> identity = sts.get_caller_identity()
    """
    if not role_arn or not role_arn.strip():
        raise ValueError("role_arn cannot be empty")
    if not external_id or not external_id.strip():
        raise ValueError("external_id cannot be empty")

    session_name = session_name or settings.ROLE_SESSION_NAME

    # Create STS client using default credentials (from env, IAM role, etc.)
    sts_client: STSClient = boto3.client("sts", region_name=settings.AWS_REGION)

    # Retry logic for transient errors (throttling, network issues)
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                logger.info(f"Retrying assume role (attempt {attempt + 1}/{MAX_RETRIES}) for {role_arn}")
                time.sleep(RETRY_DELAY_SECONDS * attempt)  # Exponential backoff

            logger.info(f"Assuming role {role_arn} with session name {session_name}")
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=session_name,
                ExternalId=external_id,
            )

            credentials = response["Credentials"]

            # Create a new boto3 session with the temporary credentials
            session = boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                region_name=settings.AWS_REGION,
            )

            logger.info(f"Successfully assumed role {role_arn}")
            return session

        except ClientError as e:
            last_exception = e
            error_code = e.response.get("Error", {}).get("Code", "Unknown")

            # Don't retry on non-transient errors
            non_retryable_errors = {
                "AccessDenied",
                "InvalidClientTokenId",
                "MalformedPolicyDocument",
                "ValidationError",
                "NoSuchEntity",
            }
            if error_code in non_retryable_errors:
                break

            # Retry on throttling and transient errors
            if error_code in {"Throttling", "ServiceUnavailable", "RequestTimeout"}:
                if attempt < MAX_RETRIES - 1:
                    continue
                # Fall through to raise on last attempt

            # For other errors, don't retry
            break

    # If we exhausted retries or hit a non-retryable error, handle the exception
    if last_exception is None:
        # This shouldn't happen, but handle gracefully
        raise RuntimeError(f"Failed to assume role {role_arn} after {MAX_RETRIES} attempts")

    e = last_exception
    error_code = e.response.get("Error", {}).get("Code", "Unknown")
    error_message = e.response.get("Error", {}).get("Message", str(e))

    # Map common error codes to clearer messages
    if error_code == "AccessDenied":
        logger.warning(f"Access denied when assuming role {role_arn}: {error_message}")
        raise ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied. Check role ARN and trust policy."}},
            "AssumeRole",
        ) from e
    elif error_code == "InvalidClientTokenId":
        logger.warning(f"Invalid credentials when assuming role {role_arn}: {error_message}")
        raise ClientError(
            {"Error": {"Code": "InvalidClientTokenId", "Message": "Invalid AWS credentials."}},
            "AssumeRole",
        ) from e
    elif error_code == "MalformedPolicyDocument":
        logger.warning(f"Malformed policy when assuming role {role_arn}: {error_message}")
        raise ClientError(
            {"Error": {"Code": "MalformedPolicyDocument", "Message": "Role trust policy is malformed."}},
            "AssumeRole",
        ) from e
    elif error_code == "ValidationError":
        # This often means wrong ExternalId or invalid ARN format
        logger.warning(f"Validation error when assuming role {role_arn}: {error_message}")
        # Don't expose ExternalId details for security
        raise ClientError(
            {
                "Error": {
                    "Code": "ValidationError",
                    "Message": "Invalid role ARN or ExternalId mismatch. Verify the role ARN and ExternalId match the CloudFormation deployment.",
                }
            },
            "AssumeRole",
        ) from e
    else:
        logger.error(f"Unexpected error assuming role {role_arn}: {error_code} - {error_message}")
        raise
