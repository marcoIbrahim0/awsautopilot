"""
Runtime risk probes for remediation strategy gating.

These checks are intentionally incremental and non-mutating. They collect
high-signal evidence before run creation to reduce avoidable runtime failures.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

from backend.models.action import Action
from backend.models.aws_account import AwsAccount
from backend.services.aws import assume_role
from backend.services.remediation_strategy import RemediationStrategy

logger = logging.getLogger(__name__)

_ACCESS_DENIED_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "UnauthorizedOperation",
    "UnauthorizedException",
}
_S3_POLICY_MAX_BYTES = 20 * 1024
_STRICT_ACCESS_PATH_STRATEGIES = frozenset(
    {
        "s3_bucket_block_public_access_standard",
        "s3_migrate_cloudfront_oac_private",
        "s3_enforce_ssl_strict_deny",
        "ssm_disable_public_document_sharing",
        "snapshot_block_all_sharing",
        "snapshot_block_new_sharing_only",
    }
)
_KMS_ARN_PATTERN = re.compile(
    r"^arn:(aws|aws-us-gov|aws-cn):kms:[a-z0-9-]+:\d{12}:(key|alias)/[A-Za-z0-9/_+=,.@-]+$"
)
_S3_BUCKET_ARN_PATTERN = re.compile(r"arn:aws:s3:::(?P<bucket>[A-Za-z0-9.\-_]{3,63})")
_SECURITY_GROUP_ID_PATTERN = re.compile(r"\bsg-[0-9a-fA-F]{8,17}\b")


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", "")).strip()


def _error_message(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Message", "")).strip()


def _is_access_denied(exc: ClientError) -> bool:
    code = _error_code(exc)
    if code in _ACCESS_DENIED_CODES:
        return True
    message = _error_message(exc).lower()
    return "access denied" in message or "not authorized" in message


def _to_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _bucket_name_from_target_id(target_id: str | None) -> str | None:
    if target_id is None:
        return None
    if not isinstance(target_id, str):
        return None
    tid = target_id.strip()
    if not tid:
        return None

    match = _S3_BUCKET_ARN_PATTERN.search(tid)
    if match:
        return match.group("bucket")

    if "|" in tid:
        for part in tid.split("|"):
            part = part.strip()
            match = _S3_BUCKET_ARN_PATTERN.search(part)
            if match:
                return match.group("bucket")
        return None

    if tid.startswith("arn:aws:s3:::"):
        candidate = tid.split("arn:aws:s3:::")[-1].split("/")[0].strip()
        return candidate or None

    return tid


def _security_group_id_from_target_id(target_id: str | None) -> str | None:
    """Extract a security-group ID from an action target identifier."""
    if not isinstance(target_id, str):
        return None
    tid = target_id.strip()
    if not tid:
        return None
    match = _SECURITY_GROUP_ID_PATTERN.search(tid)
    if match:
        return match.group(0)
    return None


def _extract_public_admin_ports(permission: dict[str, Any], *, ipv6: bool) -> set[int]:
    """
    Return public admin ports (22/3389) exposed by one SG permission block.

    We only consider tcp and all-protocol rules and treat 0.0.0.0/0 or ::/0 as public.
    """
    public_marker = "::/0" if ipv6 else "0.0.0.0/0"
    ranges_key = "Ipv6Ranges" if ipv6 else "IpRanges"
    ranges = permission.get(ranges_key)
    if not isinstance(ranges, list):
        return set()

    has_public = False
    cidr_key = "CidrIpv6" if ipv6 else "CidrIp"
    for item in ranges:
        if not isinstance(item, dict):
            continue
        if str(item.get(cidr_key, "")).strip() == public_marker:
            has_public = True
            break
    if not has_public:
        return set()

    protocol = str(permission.get("IpProtocol", "")).strip().lower()
    if protocol not in {"tcp", "-1", "all"}:
        return set()

    # All protocols includes both admin ports by definition.
    if protocol in {"-1", "all"}:
        return {22, 3389}

    from_port = _to_int(permission.get("FromPort"))
    to_port = _to_int(permission.get("ToPort"))
    if from_port is None or to_port is None:
        return set()
    start = min(from_port, to_port)
    end = max(from_port, to_port)
    ports: set[int] = set()
    if start <= 22 <= end:
        ports.add(22)
    if start <= 3389 <= end:
        ports.add(3389)
    return ports


def _policy_enforces_ssl_only(policy_json: str | None) -> bool:
    """Best-effort check for a deny statement on insecure transport."""
    normalized = _normalize_bucket_policy_document(policy_json)
    if not normalized:
        return False
    try:
        parsed = json.loads(normalized)
    except (TypeError, ValueError):
        return False
    statements = parsed.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list):
        return False

    for statement in statements:
        if not isinstance(statement, dict):
            continue
        if str(statement.get("Effect", "")).lower() != "deny":
            continue
        condition = statement.get("Condition")
        if not isinstance(condition, dict):
            continue
        bool_block = condition.get("Bool")
        if not isinstance(bool_block, dict):
            continue
        secure_transport = bool_block.get("aws:SecureTransport")
        if str(secure_transport).strip().lower() == "false":
            return True
    return False


def _context_payload(signals: dict[str, Any]) -> dict[str, Any]:
    """Return mutable context payload for API option rendering metadata."""
    payload = signals.setdefault("context", {})
    if isinstance(payload, dict):
        return payload
    payload = {}
    signals["context"] = payload
    return payload


def _estimate_ssl_policy_size_bytes(bucket: str, exempt_principals: list[str]) -> int:
    statements: list[dict[str, Any]] = [
        {
            "Sid": "DenyInsecureTransport",
            "Effect": "Deny",
            "Principal": "*",
            "Action": "s3:*",
            "Resource": [
                f"arn:aws:s3:::{bucket}",
                f"arn:aws:s3:::{bucket}/*",
            ],
            "Condition": {"Bool": {"aws:SecureTransport": "false"}},
        }
    ]
    if exempt_principals:
        statements.append(
            {
                "Sid": "AllowExemptPrincipals",
                "Effect": "Allow",
                "Principal": {"AWS": exempt_principals},
                "Action": "s3:*",
                "Resource": [
                    f"arn:aws:s3:::{bucket}",
                    f"arn:aws:s3:::{bucket}/*",
                ],
            }
        )
    doc = {"Version": "2012-10-17", "Statement": statements}
    return len(json.dumps(doc, separators=(",", ":")))


def _normalize_bucket_policy_document(policy_json: str | None) -> str | None:
    """Return canonical bucket-policy JSON string or None when invalid."""
    if not isinstance(policy_json, str):
        return None
    raw = policy_json.strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None

    statements = parsed.get("Statement")
    if statements is None:
        parsed["Statement"] = []
    elif isinstance(statements, dict):
        parsed["Statement"] = [statements]
    elif not isinstance(statements, list):
        return None

    return json.dumps(parsed, separators=(",", ":"), sort_keys=True)


def _policy_statement_count(policy_json: str | None) -> int:
    """Count policy statements from normalized/raw policy JSON."""
    normalized = _normalize_bucket_policy_document(policy_json)
    if not normalized:
        return 0
    parsed = json.loads(normalized)
    statements = parsed.get("Statement")
    if isinstance(statements, list):
        return len(statements)
    if isinstance(statements, dict):
        return 1
    return 0


def probe_direct_fix_permissions(action: Action, account: AwsAccount) -> tuple[bool | None, str | None]:
    """
    Non-mutating direct-fix permission probe.

    Returns:
      - (False, msg): deterministic permission failure (should block run creation)
      - (True, None): probe succeeded / known non-permission state
      - (None, msg): probe unavailable (do not block solely on this signal)
    """
    role_arn = (account.role_write_arn or "").strip()
    external_id = (account.external_id or "").strip()
    if not role_arn or not external_id:
        return None, "WriteRole probe skipped: missing role or external_id."

    try:
        session = assume_role(role_arn=role_arn, external_id=external_id)
    except ClientError as exc:
        if _is_access_denied(exc):
            code = _error_code(exc) or "AccessDenied"
            return False, f"WriteRole assume-role denied ({code})."
        return None, f"WriteRole probe unavailable: {_error_code(exc) or 'ClientError'}."
    except Exception as exc:  # pragma: no cover - defensive
        return None, f"WriteRole probe unavailable: {exc}"

    action_type = (action.action_type or "").strip().lower()
    account_id = (action.account_id or "").strip()
    region = (action.region or "").strip()
    try:
        if action_type == "s3_block_public_access":
            # S3 account-level Public Access Block is global-to-account but S3Control is a regional endpoint.
            # Default to the session/config region (eu-north-1 in this repo) unless an explicit action region is provided.
            s3c_region = region or session.region_name or "eu-north-1"
            s3c = session.client("s3control", region_name=s3c_region)
            try:
                s3c.get_public_access_block(AccountId=account_id)
            except ClientError as exc:
                if _error_code(exc) == "NoSuchPublicAccessBlockConfiguration":
                    return True, None
                raise
            return True, None

        if action_type == "enable_security_hub":
            if not region:
                return False, "Region is required for Security Hub remediation."
            sh = session.client("securityhub", region_name=region)
            try:
                sh.get_enabled_standards(MaxResults=1)
            except ClientError as exc:
                code = _error_code(exc)
                # Not enabled yet is expected for remediation targets.
                if code in {"InvalidAccessException", "ResourceNotFoundException"}:
                    return True, None
                raise
            return True, None

        if action_type == "enable_guardduty":
            if not region:
                return False, "Region is required for GuardDuty remediation."
            gd = session.client("guardduty", region_name=region)
            gd.list_detectors()
            return True, None

        if action_type == "ebs_default_encryption":
            if not region:
                return False, "Region is required for EBS default encryption remediation."
            ec2 = session.client("ec2", region_name=region)
            ec2.get_ebs_encryption_by_default()
            return True, None

        return None, f"Direct-fix probe not implemented for action_type '{action_type}'."
    except ClientError as exc:
        code = _error_code(exc) or "ClientError"
        if _is_access_denied(exc):
            return False, f"WriteRole probe denied by AWS API ({code})."
        return None, f"WriteRole probe unavailable: {code}."
    except Exception as exc:  # pragma: no cover - defensive
        return None, f"WriteRole probe unavailable: {exc}"


def collect_runtime_risk_signals(
    action: Action,
    strategy: RemediationStrategy,
    strategy_inputs: dict[str, Any] | None,
    account: AwsAccount | None,
) -> dict[str, Any]:
    """
    Collect optional runtime signals for strategy risk evaluation.

    Signals are best-effort and non-mutating. Missing signals should not be
    interpreted as success.
    """
    strategy_inputs = strategy_inputs or {}
    strategy_id = strategy["strategy_id"]
    signals: dict[str, Any] = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "strategy_id": strategy_id,
        "evidence": {},
    }

    read_session = None
    read_probe_error: str | None = None

    def _get_read_session():
        nonlocal read_session, read_probe_error
        if read_session is not None:
            return read_session
        if read_probe_error is not None:
            return None
        if account is None:
            read_probe_error = "AWS account metadata missing for runtime probes."
            return None
        role_arn = (account.role_read_arn or "").strip()
        external_id = (account.external_id or "").strip()
        if not role_arn or not external_id:
            read_probe_error = "ReadRole is not configured for runtime probes."
            return None
        try:
            read_session = assume_role(role_arn=role_arn, external_id=external_id)
            return read_session
        except Exception as exc:  # pragma: no cover - network-dependent
            read_probe_error = str(exc)
            return None

    def _mark_access_path_unavailable(reason: str) -> None:
        signals["access_path_evidence_available"] = False
        if "access_path_evidence_reason" not in signals:
            signals["access_path_evidence_reason"] = reason

    is_access_path_strategy = strategy_id in _STRICT_ACCESS_PATH_STRATEGIES
    if is_access_path_strategy:
        if account is not None:
            session = _get_read_session()
            if session is None:
                _mark_access_path_unavailable(read_probe_error or "ReadRole runtime probe unavailable.")
            else:
                signals["access_path_evidence_available"] = True

    if strategy_id == "sg_restrict_public_ports_guided":
        sg_id = _security_group_id_from_target_id(action.target_id)
        evidence_payload = signals.setdefault("evidence", {})
        if isinstance(evidence_payload, dict):
            if sg_id:
                evidence_payload["security_group_id"] = sg_id
            else:
                evidence_payload["security_group_probe_error"] = "Could not derive security group ID from target."
        if sg_id:
            session = _get_read_session()
            if session is not None:
                ec2 = session.client("ec2", region_name=action.region or None)
                try:
                    response = ec2.describe_security_groups(GroupIds=[sg_id])
                    groups = response.get("SecurityGroups", [])
                    if isinstance(groups, list) and groups:
                        permissions = groups[0].get("IpPermissions", [])
                        if isinstance(permissions, list):
                            public_ipv4_ports: set[int] = set()
                            public_ipv6_ports: set[int] = set()
                            for permission in permissions:
                                if not isinstance(permission, dict):
                                    continue
                                public_ipv4_ports.update(
                                    _extract_public_admin_ports(permission, ipv6=False)
                                )
                                public_ipv6_ports.update(
                                    _extract_public_admin_ports(permission, ipv6=True)
                                )
                            if isinstance(evidence_payload, dict):
                                evidence_payload["public_admin_ipv4_ports"] = sorted(public_ipv4_ports)
                                evidence_payload["public_admin_ipv6_ports"] = sorted(public_ipv6_ports)
                except ClientError as exc:
                    if isinstance(evidence_payload, dict):
                        evidence_payload["security_group_probe_error"] = _error_code(exc) or "DescribeSecurityGroupsFailed"
                except Exception as exc:  # pragma: no cover - defensive
                    if isinstance(evidence_payload, dict):
                        evidence_payload["security_group_probe_error"] = f"{type(exc).__name__}"

    if strategy_id == "s3_bucket_encryption_kms":
        session = _get_read_session()
        context_payload = _context_payload(signals)
        if session is None:
            context_payload["kms_key_options_error"] = read_probe_error or "ReadRole runtime probe unavailable."
        else:
            kms = session.client("kms", region_name=action.region or None)
            options: list[dict[str, str]] = []
            marker: str | None = None
            try:
                while True:
                    kwargs: dict[str, Any] = {"Limit": 100}
                    if marker:
                        kwargs["Marker"] = marker
                    resp = kms.list_aliases(**kwargs)
                    aliases = resp.get("Aliases", [])
                    if isinstance(aliases, list):
                        for alias in aliases:
                            if not isinstance(alias, dict):
                                continue
                            alias_name = str(alias.get("AliasName", "")).strip()
                            alias_arn = str(alias.get("AliasArn", "")).strip()
                            if not alias_name or not alias_arn:
                                continue
                            target_key_id = str(alias.get("TargetKeyId", "")).strip()
                            label = alias_name
                            if target_key_id:
                                label = f"{alias_name} ({target_key_id})"
                            options.append({"value": alias_arn, "label": label})
                    if not resp.get("Truncated"):
                        break
                    marker = str(resp.get("NextMarker", "")).strip() or None
                    if marker is None:
                        break
                # Keep AWS-managed alias first if present, then stable alphabetical order.
                options.sort(
                    key=lambda item: (
                        0 if item["label"].startswith("alias/aws/s3") else 1,
                        item["label"],
                    )
                )
                if options:
                    context_payload["kms_key_options"] = options
            except ClientError as exc:
                context_payload["kms_key_options_error"] = _error_code(exc) or "ListAliasesFailed"

    if strategy_id == "cloudtrail_enable_guided":
        context_payload = _context_payload(signals)
        default_inputs: dict[str, Any] = {}
        evidence_payload = signals.setdefault("evidence", {})
        if not isinstance(evidence_payload, dict):
            evidence_payload = {}
            signals["evidence"] = evidence_payload
        session = _get_read_session()
        if session is None:
            context_payload["default_inputs_error"] = read_probe_error or "ReadRole runtime probe unavailable."
        else:
            cloudtrail = session.client("cloudtrail", region_name=action.region or None)
            try:
                response = cloudtrail.describe_trails(includeShadowTrails=False)
                trails = response.get("trailList", [])
                if isinstance(trails, list) and trails:
                    trail = trails[0] if isinstance(trails[0], dict) else {}
                    signals["cloudtrail_existing_trail_present"] = True
                    trail_name = str(trail.get("Name", "")).strip()
                    if trail_name:
                        signals["cloudtrail_existing_trail_name"] = trail_name
                        evidence_payload["cloudtrail_existing_trail_name"] = trail_name
                        default_inputs["trail_name"] = trail_name
                    if isinstance(trail.get("IsMultiRegionTrail"), bool):
                        multi_region = bool(trail.get("IsMultiRegionTrail"))
                        signals["cloudtrail_existing_trail_multi_region"] = multi_region
                        evidence_payload["cloudtrail_existing_trail_multi_region"] = multi_region
                        default_inputs["multi_region"] = multi_region
                else:
                    signals["cloudtrail_existing_trail_present"] = False
            except ClientError as exc:
                context_payload["default_inputs_error"] = _error_code(exc) or "DescribeTrailsFailed"
                signals["cloudtrail_describe_trails_error"] = _error_code(exc) or "DescribeTrailsFailed"

        if "trail_name" not in default_inputs:
            default_inputs["trail_name"] = "security-autopilot-trail"
        default_inputs.setdefault("create_bucket_policy", True)
        default_inputs.setdefault("multi_region", True)
        context_payload["default_inputs"] = default_inputs

    if strategy_id in ("config_enable_centralized_delivery", "config_enable_account_local_delivery"):
        session = _get_read_session()
        context_payload = _context_payload(signals)
        default_inputs: dict[str, Any] = {}
        if session is not None:
            config_client = session.client("config", region_name=action.region or None)
            evidence_payload = signals.setdefault("evidence", {})
            if isinstance(evidence_payload, dict):
                try:
                    recorder_resp = config_client.describe_configuration_recorders()
                    recorders = recorder_resp.get("ConfigurationRecorders", [])
                    if isinstance(recorders, list) and recorders:
                        recorder = recorders[0] if isinstance(recorders[0], dict) else {}
                        evidence_payload["config_recorder_exists"] = True
                        recorder_name = str(recorder.get("name", "")).strip()
                        if recorder_name:
                            evidence_payload["config_recorder_name"] = recorder_name
                        recording_group = recorder.get("recordingGroup", {})
                        if isinstance(recording_group, dict):
                            if recording_group.get("allSupported") is True:
                                evidence_payload["config_recording_scope"] = "all_resources"
                            elif recording_group:
                                evidence_payload["config_recording_scope"] = "custom"
                    else:
                        evidence_payload["config_recorder_exists"] = False
                except ClientError as exc:
                    signals["config_recorder_probe_error"] = _error_code(exc) or "DescribeConfigurationRecordersFailed"

                try:
                    channel_resp = config_client.describe_delivery_channels()
                    channels = channel_resp.get("DeliveryChannels", [])
                    if isinstance(channels, list) and channels:
                        channel = channels[0] if isinstance(channels[0], dict) else {}
                        evidence_payload["config_delivery_channel_exists"] = True
                        bucket_name = str(channel.get("s3BucketName", "")).strip()
                        if bucket_name:
                            evidence_payload["config_delivery_bucket_name"] = bucket_name
                        kms_key_arn = str(channel.get("s3KmsKeyArn", "")).strip()
                        if kms_key_arn:
                            evidence_payload["config_delivery_kms_key_arn"] = kms_key_arn
                    else:
                        evidence_payload["config_delivery_channel_exists"] = False
                except ClientError as exc:
                    signals["config_delivery_channel_probe_error"] = _error_code(exc) or "DescribeDeliveryChannelsFailed"
        elif account is not None:
            context_payload["default_inputs_error"] = read_probe_error or "ReadRole runtime probe unavailable."

        evidence_payload = signals.get("evidence")
        if isinstance(evidence_payload, dict):
            if evidence_payload.get("config_recorder_exists") is True:
                default_inputs["recording_scope"] = "keep_existing"
            elif evidence_payload.get("config_recorder_exists") is False:
                default_inputs["recording_scope"] = "all_resources"

            existing_bucket = str(evidence_payload.get("config_delivery_bucket_name", "")).strip()
            fallback_bucket = f"security-autopilot-config-{(action.account_id or '').strip()}"
            suggested_bucket = existing_bucket or fallback_bucket
            if suggested_bucket:
                default_inputs["delivery_bucket"] = suggested_bucket
                default_inputs["existing_bucket_name"] = suggested_bucket
                default_inputs["delivery_bucket_mode"] = "use_existing" if existing_bucket else "create_new"
        if default_inputs:
            context_payload["default_inputs"] = default_inputs

        bucket = str(strategy_inputs.get("delivery_bucket", "")).strip()
        if bucket:
            signals["evidence"]["delivery_bucket"] = bucket
            if session is None:
                _mark_access_path_unavailable(read_probe_error or "Unable to validate Config delivery bucket.")
            else:
                s3 = session.client("s3")
                try:
                    s3.head_bucket(Bucket=bucket)
                    signals["config_delivery_bucket_reachable"] = True
                    signals["config_central_bucket_policy_valid"] = True
                except ClientError as exc:
                    code = _error_code(exc) or "HeadBucketFailed"
                    signals["config_delivery_bucket_reachable"] = False
                    signals["config_delivery_bucket_error"] = code
                    if _is_access_denied(exc):
                        signals["config_central_bucket_policy_valid"] = False
                        signals["config_central_bucket_policy_error"] = (
                            "Centralized delivery bucket access is denied for this account context."
                        )
        kms_key_arn = str(strategy_inputs.get("kms_key_arn", "")).strip()
        if kms_key_arn:
            session = _get_read_session()
            if not _KMS_ARN_PATTERN.match(kms_key_arn):
                signals["config_kms_policy_valid"] = False
                signals["config_kms_policy_error"] = "kms_key_arn is not a valid KMS ARN."
            elif session is not None:
                arn_parts = kms_key_arn.split(":", 5)
                kms_region = arn_parts[3] if len(arn_parts) > 4 else ""
                kms = session.client("kms", region_name=action.region or kms_region or None)
                try:
                    key_metadata = kms.describe_key(KeyId=kms_key_arn).get("KeyMetadata", {})
                    if key_metadata.get("KeyState") != "Enabled":
                        signals["config_kms_policy_valid"] = False
                        signals["config_kms_policy_error"] = "Configured KMS key is not enabled."
                    else:
                        signals["config_kms_policy_valid"] = True
                except ClientError as exc:
                    signals["config_kms_policy_valid"] = False
                    signals["config_kms_policy_error"] = _error_code(exc) or "DescribeKeyFailed"

    if strategy_id in (
        "ebs_enable_default_encryption_customer_kms",
        "ebs_enable_default_encryption_customer_kms_pr_bundle",
    ):
        kms_key_arn = str(strategy_inputs.get("kms_key_arn", "")).strip()
        if kms_key_arn:
            signals["evidence"]["kms_key_arn"] = kms_key_arn
            if not _KMS_ARN_PATTERN.match(kms_key_arn):
                signals["ebs_customer_kms_key_valid"] = False
                signals["ebs_customer_kms_key_error"] = "kms_key_arn is not a valid KMS ARN."
            else:
                arn_parts = kms_key_arn.split(":", 5)
                kms_region = arn_parts[3] if len(arn_parts) > 4 else ""
                kms_account_id = arn_parts[4] if len(arn_parts) > 5 else ""
                if action.region and kms_region and kms_region != action.region:
                    signals["ebs_customer_kms_key_valid"] = False
                    signals["ebs_customer_kms_key_error"] = (
                        f"KMS key region {kms_region} does not match action region {action.region}."
                    )
                elif account is not None and kms_account_id and kms_account_id != account.account_id:
                    signals["ebs_customer_kms_key_valid"] = False
                    signals["ebs_customer_kms_key_error"] = (
                        f"KMS key account {kms_account_id} does not match action account {account.account_id}."
                    )
                else:
                    session = _get_read_session()
                    if session is not None:
                        kms = session.client("kms", region_name=action.region or kms_region or None)
                        try:
                            key_metadata = kms.describe_key(KeyId=kms_key_arn).get("KeyMetadata", {})
                            if key_metadata.get("KeyState") != "Enabled":
                                signals["ebs_customer_kms_key_valid"] = False
                                signals["ebs_customer_kms_key_error"] = "KMS key is not enabled."
                            else:
                                signals["ebs_customer_kms_key_valid"] = True
                        except ClientError as exc:
                            signals["ebs_customer_kms_key_valid"] = False
                            signals["ebs_customer_kms_key_error"] = _error_code(exc) or "DescribeKeyFailed"

    if strategy_id == "iam_root_key_delete":
        session = _get_read_session()
        if session is None:
            signals["iam_root_account_mfa_probe_error"] = (
                read_probe_error or "ReadRole runtime probe unavailable for root MFA enrollment check."
            )
        else:
            iam = session.client("iam", region_name=action.region or None)
            try:
                summary = iam.get_account_summary()
                summary_map = summary.get("SummaryMap") if isinstance(summary, dict) else {}
                mfa_raw = summary_map.get("AccountMFAEnabled") if isinstance(summary_map, dict) else None
                mfa_enabled = _to_int(mfa_raw)
                if mfa_enabled is None:
                    signals["iam_root_account_mfa_probe_error"] = "AccountMFAEnabled is unavailable in account summary."
                else:
                    signals["iam_root_account_mfa_enrolled"] = mfa_enabled == 1
                    evidence_payload = signals.setdefault("evidence", {})
                    if isinstance(evidence_payload, dict):
                        evidence_payload["account_mfa_enabled"] = mfa_enabled
            except ClientError as exc:
                signals["iam_root_account_mfa_probe_error"] = _error_code(exc) or "GetAccountSummaryFailed"
            except Exception as exc:  # pragma: no cover - defensive
                signals["iam_root_account_mfa_probe_error"] = f"{type(exc).__name__}"

    if strategy_id in ("s3_enforce_ssl_strict_deny", "s3_enforce_ssl_with_principal_exemptions"):
        bucket = _bucket_name_from_target_id(action.target_id)
        exempt_principals = strategy_inputs.get("exempt_principals")
        if not isinstance(exempt_principals, list):
            exempt_principals = []
        exempt_principals = [str(v).strip() for v in exempt_principals if str(v).strip()]
        if not bucket:
            signals["s3_ssl_policy_generation_ok"] = False
            signals["s3_ssl_policy_generation_error"] = "Could not derive bucket name from action target."
            if is_access_path_strategy and account is not None:
                _mark_access_path_unavailable("Missing bucket identifier for SSL policy analysis.")
        else:
            signals["evidence"]["target_bucket"] = bucket
            signals["s3_ssl_policy_generation_ok"] = True
            signals["s3_ssl_policy_estimated_bytes"] = _estimate_ssl_policy_size_bytes(
                bucket=bucket,
                exempt_principals=exempt_principals,
            )
            session = _get_read_session()
            if session is None:
                if is_access_path_strategy and account is not None:
                    _mark_access_path_unavailable(read_probe_error or "Unable to read current bucket policy.")
            else:
                s3 = session.client("s3")
                try:
                    raw_policy = s3.get_bucket_policy(Bucket=bucket).get("Policy")
                    normalized_policy = _normalize_bucket_policy_document(raw_policy)
                    evidence_payload = signals.setdefault("evidence", {})
                    if isinstance(evidence_payload, dict):
                        if normalized_policy is not None:
                            statement_count = _policy_statement_count(normalized_policy)
                            evidence_payload["existing_bucket_policy_statement_count"] = statement_count
                            if statement_count > 0:
                                evidence_payload["existing_bucket_policy_json"] = normalized_policy
                            evidence_payload["s3_ssl_deny_present"] = _policy_enforces_ssl_only(normalized_policy)
                        else:
                            evidence_payload["s3_ssl_deny_present"] = False
                            evidence_payload["existing_bucket_policy_parse_error"] = (
                                "GetBucketPolicy returned invalid JSON."
                            )
                    signals["s3_policy_analysis_possible"] = True
                except ClientError as exc:
                    code = _error_code(exc)
                    if code == "NoSuchBucketPolicy":
                        signals["s3_policy_analysis_possible"] = True
                        evidence_payload = signals.setdefault("evidence", {})
                        if isinstance(evidence_payload, dict):
                            evidence_payload["existing_bucket_policy_statement_count"] = 0
                            evidence_payload["s3_ssl_deny_present"] = False
                    else:
                        signals["s3_policy_analysis_possible"] = False
                        signals["s3_policy_analysis_error"] = code or "GetBucketPolicyFailed"
                        evidence_payload = signals.setdefault("evidence", {})
                        if isinstance(evidence_payload, dict):
                            evidence_payload["existing_bucket_policy_capture_error"] = code or "GetBucketPolicyFailed"
                        if is_access_path_strategy and account is not None:
                            _mark_access_path_unavailable(
                                f"Unable to inspect current bucket policy ({code or 'GetBucketPolicyFailed'})."
                            )

    if strategy_id in ("s3_bucket_block_public_access_standard", "s3_migrate_cloudfront_oac_private"):
        bucket = _bucket_name_from_target_id(action.target_id)
        if bucket:
            signals["evidence"]["target_bucket"] = bucket
            session = _get_read_session()
            if session is None:
                if account is not None:
                    _mark_access_path_unavailable(read_probe_error or "Unable to inspect bucket access posture.")
            else:
                s3 = session.client("s3")
                try:
                    policy_status = s3.get_bucket_policy_status(Bucket=bucket).get("PolicyStatus", {})
                    signals["s3_bucket_policy_public"] = bool(policy_status.get("IsPublic"))
                except ClientError as exc:
                    code = _error_code(exc)
                    if code == "NoSuchBucketPolicy":
                        signals["s3_bucket_policy_public"] = False
                    elif code not in {"NoSuchBucket"}:
                        if account is not None:
                            _mark_access_path_unavailable(
                                f"Unable to inspect bucket policy status ({code or 'GetBucketPolicyStatusFailed'})."
                            )
                if strategy_id == "s3_migrate_cloudfront_oac_private":
                    try:
                        raw_policy = s3.get_bucket_policy(Bucket=bucket).get("Policy")
                        normalized_policy = _normalize_bucket_policy_document(raw_policy)
                        if normalized_policy is not None:
                            statement_count = _policy_statement_count(normalized_policy)
                            evidence_payload = signals.setdefault("evidence", {})
                            if isinstance(evidence_payload, dict):
                                evidence_payload["existing_bucket_policy_statement_count"] = statement_count
                                if statement_count > 0:
                                    evidence_payload["existing_bucket_policy_json"] = normalized_policy
                        else:
                            evidence_payload = signals.setdefault("evidence", {})
                            if isinstance(evidence_payload, dict):
                                evidence_payload["existing_bucket_policy_parse_error"] = (
                                    "GetBucketPolicy returned invalid JSON."
                                )
                    except ClientError as exc:
                        code = _error_code(exc)
                        evidence_payload = signals.setdefault("evidence", {})
                        if isinstance(evidence_payload, dict):
                            if code == "NoSuchBucketPolicy":
                                evidence_payload["existing_bucket_policy_statement_count"] = 0
                            else:
                                evidence_payload["existing_bucket_policy_capture_error"] = code or "GetBucketPolicyFailed"
                        if code not in {"NoSuchBucketPolicy", "NoSuchBucket"} and account is not None:
                            _mark_access_path_unavailable(
                                f"Unable to capture existing bucket policy ({code or 'GetBucketPolicyFailed'})."
                            )
                try:
                    s3.get_bucket_website(Bucket=bucket)
                    signals["s3_bucket_website_configured"] = True
                except ClientError as exc:
                    code = _error_code(exc)
                    if code == "NoSuchWebsiteConfiguration":
                        signals["s3_bucket_website_configured"] = False
                    elif code not in {"NoSuchBucket"}:
                        if account is not None:
                            _mark_access_path_unavailable(
                                f"Unable to inspect bucket website configuration ({code or 'GetBucketWebsiteFailed'})."
                            )
        else:
            if account is not None:
                _mark_access_path_unavailable("Missing bucket identifier for access-path validation.")

    if strategy_id in ("snapshot_block_all_sharing", "snapshot_block_new_sharing_only"):
        session = _get_read_session()
        if session is not None:
            ec2 = session.client("ec2", region_name=action.region or None)
            try:
                resp = ec2.describe_snapshots(
                    OwnerIds=["self"],
                    Filters=[{"Name": "create-volume-permission.group", "Values": ["all"]}],
                    MaxResults=200,
                )
                snapshots = resp.get("Snapshots", [])
                signals["snapshot_public_shares_count"] = len(snapshots) if isinstance(snapshots, list) else 0
            except ClientError as exc:
                signals["snapshot_public_shares_error"] = _error_code(exc) or "DescribeSnapshotsFailed"

    evidence = signals.get("evidence")
    if isinstance(evidence, dict) and not evidence:
        signals.pop("evidence", None)
    context = signals.get("context")
    if isinstance(context, dict) and not context:
        signals.pop("context", None)

    # If no meaningful signal beyond metadata was produced, return empty.
    meaningful_keys = set(signals.keys()) - {"collected_at", "strategy_id", "evidence", "context"}
    if not meaningful_keys and "evidence" not in signals and "context" not in signals:
        return {}

    # Include policy size threshold for evaluator diagnostics.
    signals["s3_policy_size_limit_bytes"] = _S3_POLICY_MAX_BYTES
    return signals


__all__ = [
    "collect_runtime_risk_signals",
    "probe_direct_fix_permissions",
]
