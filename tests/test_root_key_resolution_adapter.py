from backend.services.root_key_resolution_adapter import (
    ROOT_KEY_EXECUTION_AUTHORITY_PATH,
    ROOT_KEY_EXECUTION_AUTHORITY_REASON,
    ROOT_KEY_GENERIC_ROUTE_REASON,
    build_root_key_execution_authority_error,
    build_root_key_guidance_metadata,
    is_root_key_action_type,
    is_root_key_strategy_id,
    root_key_default_support_tier,
    root_key_family_resolver_kind,
)


def test_root_key_guidance_metadata_is_guidance_only() -> None:
    metadata = build_root_key_guidance_metadata(
        strategy_id="iam_root_key_delete",
        blocked_reasons=["Root MFA must be enabled."],
    )

    assert metadata["support_tier"] == "manual_guidance_only"
    assert metadata["blocked_reasons"] == [
        "Root MFA must be enabled.",
        ROOT_KEY_EXECUTION_AUTHORITY_REASON,
    ]
    assert metadata["preservation_summary"] == {
        "guidance_only": True,
        "generic_execution_allowed": False,
        "execution_authority": ROOT_KEY_EXECUTION_AUTHORITY_PATH,
        "runbook_url": "docs/prod-readiness/root-credentials-required-iam-root-access-key-absent.md",
    }
    assert ROOT_KEY_EXECUTION_AUTHORITY_PATH in metadata["decision_rationale"]


def test_root_key_route_error_includes_authority_path() -> None:
    detail = build_root_key_execution_authority_error(strategy_id="iam_root_key_disable")

    assert detail["reason"] == ROOT_KEY_GENERIC_ROUTE_REASON
    assert detail["strategy_id"] == "iam_root_key_disable"
    assert detail["execution_authority"] == ROOT_KEY_EXECUTION_AUTHORITY_PATH


def test_root_key_catalog_helpers_only_match_iam_4() -> None:
    assert is_root_key_action_type("iam_root_access_key_absent") is True
    assert is_root_key_action_type("sg_restrict_public_ports") is False
    assert is_root_key_strategy_id("iam_root_key_delete") is True
    assert is_root_key_strategy_id("config_enable_account_local_delivery") is False
    assert root_key_default_support_tier("iam_root_access_key_absent") == "manual_guidance_only"
    assert root_key_default_support_tier("sg_restrict_public_ports") is None
    assert root_key_family_resolver_kind("iam_root_access_key_absent") == "iam_4_root_key_authority"
    assert root_key_family_resolver_kind("sg_restrict_public_ports") == "compatibility"
