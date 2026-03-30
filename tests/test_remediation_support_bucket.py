"""
Tests for the adjacency safety contract registry and support-bucket baseline.

Covers:
  - ADJACENCY_REGISTRY completeness (all non-exception action_types covered)
  - AdjacencyContract required-fields integrity
  - get_adjacency_contract lookup
  - probe_support_bucket_safety safe and failure paths
  - downgrade_reason helper
  - merge_ssl_only_into_policy correctness
  - ssl_only_policy_statement structure
  - terraform_support_bucket_blocks HCL correctness
"""
from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from backend.services.remediation_strategy import (
    ADJACENCY_REGISTRY,
    STRATEGY_REGISTRY,
    AdjacencyContract,
    get_adjacency_contract,
)
from backend.services.remediation_support_bucket import (
    SUPPORT_BUCKET_APPLY_SNIPPET,
    SUPPORT_BUCKET_KMS_MASTER_KEY_ID,
    SUPPORT_BUCKET_SSE_ALGORITHM,
    SupportBucketProbeResult,
    downgrade_reason,
    merge_ssl_only_into_policy,
    probe_support_bucket_safety,
    ssl_only_policy_statement,
    terraform_support_bucket_blocks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "op")


def _s3_mock(*, pab_ok: bool = True, enc_ok: bool = True, ssl_ok: bool = True, lc_ok: bool = True) -> Any:
    """Build a mock boto3 S3 client with configurable attribute responses."""
    client = MagicMock()
    # head_bucket: always succeeds (ownership confirmed)
    client.head_bucket.return_value = {}

    # public-access block
    if pab_ok:
        client.get_public_access_block.return_value = {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        }
    else:
        client.get_public_access_block.return_value = {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": False,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        }

    # encryption
    if enc_ok:
        client.get_bucket_encryption.return_value = {
            "ServerSideEncryptionConfiguration": {
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "aws:kms",
                            "KMSMasterKeyID": "alias/aws/s3",
                        },
                        "BucketKeyEnabled": True,
                    }
                ]
            }
        }
    else:
        err = _make_client_error("ServerSideEncryptionConfigurationNotFoundError")
        client.get_bucket_encryption.side_effect = err

    # SSL-only policy
    if ssl_ok:
        policy = json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "DenyInsecureTransport",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"],
                    "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                }
            ],
        })
        client.get_bucket_policy.return_value = {"Policy": policy}
    else:
        client.get_bucket_policy.side_effect = _make_client_error("NoSuchBucketPolicy")

    # lifecycle
    if lc_ok:
        client.get_bucket_lifecycle_configuration.return_value = {
            "Rules": [
                {
                    "ID": "abort-incomplete-multipart",
                    "Status": "Enabled",
                    "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
                }
            ]
        }
    else:
        client.get_bucket_lifecycle_configuration.side_effect = _make_client_error(
            "NoSuchLifecycleConfiguration"
        )

    # Wire ClientError exceptions class for isinstance checks in probe
    client.exceptions.ClientError = ClientError
    return client


# ---------------------------------------------------------------------------
# ADJACENCY_REGISTRY completeness
# ---------------------------------------------------------------------------

class TestAdjacencyRegistryCoverage(unittest.TestCase):
    def _non_exception_action_types(self) -> set[str]:
        """Collect all action_types in STRATEGY_REGISTRY that have at least one
        non-exception-only strategy."""
        covered: set[str] = set()
        for action_type, strategies in STRATEGY_REGISTRY.items():
            if any(not s.get("exception_only") for s in strategies):
                covered.add(action_type)
        return covered

    def test_all_non_exception_action_types_covered(self) -> None:
        """Every action_type with an executable strategy must have an adjacency entry."""
        uncovered = self._non_exception_action_types() - set(ADJACENCY_REGISTRY.keys())
        self.assertSetEqual(
            uncovered,
            set(),
            msg=f"Action types missing from ADJACENCY_REGISTRY: {uncovered}",
        )

    def test_all_registry_keys_are_strings(self) -> None:
        for key in ADJACENCY_REGISTRY:
            self.assertIsInstance(key, str)

    def test_no_duplicate_keys(self) -> None:
        # dict() guarantees uniqueness but verify registry size matches unique-key count
        self.assertEqual(len(ADJACENCY_REGISTRY), len(set(ADJACENCY_REGISTRY.keys())))


# ---------------------------------------------------------------------------
# AdjacencyContract field integrity
# ---------------------------------------------------------------------------

class TestAdjacencyContractFields(unittest.TestCase):
    REQUIRED_FIELDS = {
        "target_scope_proof",
        "adjacent_controls_at_risk",
        "creates_helper_resources",
        "merge_safe_preservation_required",
        "downgrade_rule",
    }

    def test_all_entries_have_required_fields(self) -> None:
        for action_type, contract in ADJACENCY_REGISTRY.items():
            for field in self.REQUIRED_FIELDS:
                self.assertIn(
                    field,
                    contract,
                    msg=f"ADJACENCY_REGISTRY['{action_type}'] is missing field '{field}'",
                )

    def test_target_scope_proof_non_empty(self) -> None:
        for action_type, contract in ADJACENCY_REGISTRY.items():
            self.assertTrue(
                contract["target_scope_proof"].strip(),
                msg=f"ADJACENCY_REGISTRY['{action_type}'].target_scope_proof is empty",
            )

    def test_downgrade_rule_non_empty(self) -> None:
        for action_type, contract in ADJACENCY_REGISTRY.items():
            self.assertTrue(
                contract["downgrade_rule"].strip(),
                msg=f"ADJACENCY_REGISTRY['{action_type}'].downgrade_rule is empty",
            )

    def test_adjacent_controls_at_risk_is_list(self) -> None:
        for action_type, contract in ADJACENCY_REGISTRY.items():
            self.assertIsInstance(
                contract["adjacent_controls_at_risk"],
                list,
                msg=f"ADJACENCY_REGISTRY['{action_type}'].adjacent_controls_at_risk must be list",
            )

    def test_boolean_fields_are_bool(self) -> None:
        for action_type, contract in ADJACENCY_REGISTRY.items():
            for bool_field in ("creates_helper_resources", "merge_safe_preservation_required"):
                self.assertIsInstance(
                    contract[bool_field],
                    bool,
                    msg=f"ADJACENCY_REGISTRY['{action_type}'].{bool_field} must be bool",
                )

    def test_p0_families_create_helper_resources(self) -> None:
        """P0 families must flag creates_helper_resources=True."""
        for action_type in ("s3_bucket_access_logging", "cloudtrail_enabled", "aws_config_enabled"):
            self.assertTrue(
                ADJACENCY_REGISTRY[action_type]["creates_helper_resources"],
                msg=f"{action_type} should have creates_helper_resources=True",
            )

    def test_p0_families_have_adjacent_s3_controls(self) -> None:
        """All P0 families must list S3 adjacent-control risks."""
        for action_type in ("s3_bucket_access_logging", "cloudtrail_enabled", "aws_config_enabled"):
            risks = ADJACENCY_REGISTRY[action_type]["adjacent_controls_at_risk"]
            self.assertIn("S3.9", risks, msg=f"{action_type} should include S3.9 in adjacent_controls_at_risk")


# ---------------------------------------------------------------------------
# get_adjacency_contract lookup
# ---------------------------------------------------------------------------

class TestGetAdjacencyContract(unittest.TestCase):
    def test_known_action_type_returns_contract(self) -> None:
        contract = get_adjacency_contract("cloudtrail_enabled")
        self.assertIsNotNone(contract)
        assert contract is not None
        self.assertIn("downgrade_rule", contract)

    def test_unknown_action_type_returns_none(self) -> None:
        result = get_adjacency_contract("non_existent_action_xyz")
        self.assertIsNone(result)

    def test_empty_string_returns_none(self) -> None:
        self.assertIsNone(get_adjacency_contract(""))

    def test_all_registry_entries_retrievable(self) -> None:
        for action_type in ADJACENCY_REGISTRY:
            result = get_adjacency_contract(action_type)
            self.assertIsNotNone(result, msg=f"get_adjacency_contract('{action_type}') returned None")


# ---------------------------------------------------------------------------
# probe_support_bucket_safety
# ---------------------------------------------------------------------------

class TestProbeSupportBucketSafetyFullyHealthy(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _s3_mock()
        self.result: SupportBucketProbeResult = probe_support_bucket_safety(
            self.client, "test-bucket"
        )

    def test_safe_is_true(self) -> None:
        self.assertTrue(self.result["safe"])

    def test_no_failed_attributes(self) -> None:
        failed = [a for a in self.result["attributes"] if not a["passed"]]
        self.assertEqual(failed, [])

    def test_downgrade_reason_empty_when_safe(self) -> None:
        self.assertEqual(downgrade_reason(self.result), "")


class TestProbeSupportBucketMissingPAB(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _s3_mock(pab_ok=False)
        self.result = probe_support_bucket_safety(self.client, "test-bucket")

    def test_safe_is_false(self) -> None:
        self.assertFalse(self.result["safe"])

    def test_block_public_access_failed(self) -> None:
        names = {a["name"] for a in self.result["attributes"] if not a["passed"]}
        self.assertIn("public_access_block", names)

    def test_downgrade_reason_mentions_bucket(self) -> None:
        reason = downgrade_reason(self.result)
        self.assertIn("test-bucket", reason)
        self.assertIn("public_access_block", reason)


class TestProbeSupportBucketMissingEncryption(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _s3_mock(enc_ok=False)
        self.result = probe_support_bucket_safety(self.client, "test-bucket")

    def test_safe_is_false(self) -> None:
        self.assertFalse(self.result["safe"])

    def test_encryption_attribute_failed(self) -> None:
        names = {a["name"] for a in self.result["attributes"] if not a["passed"]}
        self.assertIn("default_encryption", names)


class TestProbeSupportBucketMissingSSLPolicy(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _s3_mock(ssl_ok=False)
        self.result = probe_support_bucket_safety(self.client, "test-bucket")

    def test_safe_is_false(self) -> None:
        self.assertFalse(self.result["safe"])

    def test_ssl_only_policy_attribute_failed(self) -> None:
        names = {a["name"] for a in self.result["attributes"] if not a["passed"]}
        self.assertIn("ssl_only_policy", names)


class TestProbeSupportBucketMissingLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _s3_mock(lc_ok=False)
        self.result = probe_support_bucket_safety(self.client, "test-bucket")

    def test_safe_is_false(self) -> None:
        self.assertFalse(self.result["safe"])

    def test_lifecycle_attribute_failed(self) -> None:
        names = {a["name"] for a in self.result["attributes"] if not a["passed"]}
        self.assertIn("lifecycle_abort_incomplete", names)


class TestProbeSupportBucketUnowendBucket(unittest.TestCase):
    def test_unowned_bucket_returns_unsafe_immediately(self) -> None:
        client = MagicMock()
        client.head_bucket.side_effect = _make_client_error("NoSuchBucket")
        client.exceptions.ClientError = ClientError
        result = probe_support_bucket_safety(client, "ghost-bucket")
        self.assertFalse(result["safe"])
        self.assertEqual(len(result["attributes"]), 1)
        self.assertEqual(result["attributes"][0]["name"], "bucket_owned")


class TestProbeSupportBucketVersioningOptIn(unittest.TestCase):
    def test_versioning_not_checked_by_default(self) -> None:
        client = _s3_mock()
        result = probe_support_bucket_safety(client, "test-bucket")
        names = {a["name"] for a in result["attributes"]}
        self.assertNotIn("versioning_enabled", names)

    def test_versioning_checked_when_requested(self) -> None:
        client = _s3_mock()
        client.get_bucket_versioning.return_value = {"Status": "Enabled"}
        result = probe_support_bucket_safety(client, "test-bucket", check_versioning=True)
        names = {a["name"] for a in result["attributes"]}
        self.assertIn("versioning_enabled", names)
        versioning_attr = next(a for a in result["attributes"] if a["name"] == "versioning_enabled")
        self.assertTrue(versioning_attr["passed"])


# ---------------------------------------------------------------------------
# merge_ssl_only_into_policy
# ---------------------------------------------------------------------------

class TestMergeSslOnlyIntoPolicy(unittest.TestCase):
    def test_empty_policy_gets_ssl_statement(self) -> None:
        merged = merge_ssl_only_into_policy(None, "my-bucket")
        doc = json.loads(merged)
        sids = [s["Sid"] for s in doc["Statement"]]
        self.assertIn("DenyInsecureTransport", sids)

    def test_existing_policy_preserved(self) -> None:
        existing = json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {"Sid": "MyCustomStatement", "Effect": "Allow", "Principal": "*", "Action": "s3:GetObject", "Resource": "*"}
            ],
        })
        merged = merge_ssl_only_into_policy(existing, "my-bucket")
        doc = json.loads(merged)
        sids = [s["Sid"] for s in doc["Statement"]]
        self.assertIn("MyCustomStatement", sids)
        self.assertIn("DenyInsecureTransport", sids)

    def test_existing_ssl_statement_replaced_not_duplicated(self) -> None:
        existing = json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "DenyInsecureTransport",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::old-bucket", "arn:aws:s3:::old-bucket/*"],
                    "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                }
            ],
        })
        merged = merge_ssl_only_into_policy(existing, "new-bucket")
        doc = json.loads(merged)
        ssl_stmts = [s for s in doc["Statement"] if s.get("Sid") == "DenyInsecureTransport"]
        self.assertEqual(len(ssl_stmts), 1, "Should not duplicate the SSL statement")
        # Must contain new-bucket, not old-bucket
        resources = ssl_stmts[0]["Resource"]
        self.assertTrue(any("new-bucket" in r for r in resources))

    def test_version_preserved(self) -> None:
        existing = json.dumps({"Version": "2012-10-17", "Statement": []})
        merged = json.loads(merge_ssl_only_into_policy(existing, "b"))
        self.assertEqual(merged["Version"], "2012-10-17")


# ---------------------------------------------------------------------------
# ssl_only_policy_statement
# ---------------------------------------------------------------------------

class TestSslOnlyPolicyStatement(unittest.TestCase):
    def setUp(self) -> None:
        self.stmt = ssl_only_policy_statement("my-bucket")

    def test_effect_is_deny(self) -> None:
        self.assertEqual(self.stmt["Effect"], "Deny")

    def test_action_covers_all(self) -> None:
        self.assertIn("s3:*", self.stmt["Action"])

    def test_condition_on_secure_transport(self) -> None:
        cond = self.stmt["Condition"]["Bool"]["aws:SecureTransport"]
        self.assertEqual(str(cond).lower(), "false")

    def test_resources_include_bucket_and_objects(self) -> None:
        resources = self.stmt["Resource"]
        self.assertTrue(any("my-bucket" in r and r.endswith("/*") for r in resources))
        self.assertTrue(any(r == "arn:aws:s3:::my-bucket" for r in resources))


# ---------------------------------------------------------------------------
# terraform_support_bucket_blocks
# ---------------------------------------------------------------------------

class TestTerraformSupportBucketBlocks(unittest.TestCase):
    def _generate(self, **kwargs: Any) -> str:
        return terraform_support_bucket_blocks(
            resource_suffix=kwargs.get("resource_suffix", "log_dest"),
            bucket_id_ref=kwargs.get("bucket_id_ref", "aws_s3_bucket.log_dest[0].id"),
            bucket_name_ref=kwargs.get("bucket_name_ref", "var.log_bucket_name"),
            **{k: v for k, v in kwargs.items() if k not in ("resource_suffix", "bucket_id_ref", "bucket_name_ref")},
        )

    def test_contains_public_access_block_resource(self) -> None:
        hcl = self._generate()
        self.assertIn("aws_s3_bucket_public_access_block", hcl)
        self.assertIn("block_public_acls       = true", hcl)

    def test_contains_sse_kms_encryption(self) -> None:
        hcl = self._generate()
        self.assertIn(f'sse_algorithm     = "{SUPPORT_BUCKET_SSE_ALGORITHM}"', hcl)
        self.assertIn(f'kms_master_key_id = "{SUPPORT_BUCKET_KMS_MASTER_KEY_ID}"', hcl)

    def test_contains_abort_incomplete_lifecycle(self) -> None:
        hcl = self._generate()
        self.assertIn("abort-incomplete-multipart", hcl)
        self.assertIn("days_after_initiation = 7", hcl)

    def test_contains_deny_insecure_transport(self) -> None:
        hcl = self._generate()
        self.assertIn("DenyInsecureTransport", hcl)
        self.assertIn("aws:SecureTransport", hcl)

    def test_contains_bucket_policy_resource(self) -> None:
        hcl = self._generate()
        self.assertIn("aws_s3_bucket_policy", hcl)

    def test_versioning_block_added_when_requested(self) -> None:
        hcl = self._generate(enable_versioning=True)
        self.assertIn("aws_s3_bucket_versioning", hcl)
        self.assertIn('status = "Enabled"', hcl)

    def test_versioning_absent_by_default(self) -> None:
        hcl = self._generate()
        self.assertNotIn("aws_s3_bucket_versioning", hcl)

    def test_log_retention_rule_added_when_specified(self) -> None:
        hcl = self._generate(log_retention_days=180)
        self.assertIn("expire-support-logs", hcl)
        self.assertIn("days = 180", hcl)

    def test_log_retention_absent_by_default(self) -> None:
        hcl = self._generate()
        self.assertNotIn("expire-support-logs", hcl)

    def test_service_write_data_source_merged(self) -> None:
        hcl = self._generate(
            service_write_data_source="data.aws_iam_policy_document.cloudtrail_delivery"
        )
        self.assertIn("source_policy_documents", hcl)
        self.assertIn("cloudtrail_delivery", hcl)

    def test_count_expr_included(self) -> None:
        hcl = self._generate(count_expr="var.create_log_bucket ? 1 : 0")
        self.assertIn("var.create_log_bucket ? 1 : 0", hcl)

    def test_kms_key_is_aws_managed_not_aes256(self) -> None:
        """Verify SSE-KMS (not AES256) is used — prevents S3.15 drift."""
        hcl = self._generate()
        self.assertNotIn("AES256", hcl)
        self.assertIn("aws:kms", hcl)


# ---------------------------------------------------------------------------
# SUPPORT_BUCKET_APPLY_SNIPPET sanity
# ---------------------------------------------------------------------------

class TestSupportBucketApplySnippet(unittest.TestCase):
    def test_snippet_is_non_empty_string(self) -> None:
        self.assertIsInstance(SUPPORT_BUCKET_APPLY_SNIPPET, str)
        self.assertGreater(len(SUPPORT_BUCKET_APPLY_SNIPPET.strip()), 0)

    def test_snippet_references_alias_aws_s3(self) -> None:
        self.assertIn("alias/aws/s3", SUPPORT_BUCKET_APPLY_SNIPPET)

    def test_snippet_references_deny_insecure_transport(self) -> None:
        self.assertIn("DenyInsecureTransport", SUPPORT_BUCKET_APPLY_SNIPPET)

    def test_snippet_references_abort_incomplete(self) -> None:
        self.assertIn("abort-incomplete-multipart", SUPPORT_BUCKET_APPLY_SNIPPET)


if __name__ == "__main__":
    unittest.main()
