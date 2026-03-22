from __future__ import annotations

from pathlib import Path

from backend.services.cloudformation_templates import (
    build_cloudformation_parameter_list,
    build_role_template_parameter_values,
)


def test_build_role_template_parameter_values_includes_execution_role_arns_when_set() -> None:
    values = build_role_template_parameter_values(
        external_id="ext-123",
        saas_account_id="029037611564",
        saas_execution_role_arns=(
            "arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-api,"
            "arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-worker"
        ),
    )

    assert values == {
        "SaaSAccountId": "029037611564",
        "ExternalId": "ext-123",
        "SaaSExecutionRoleArns": (
            "arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-api,"
            "arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-worker"
        ),
    }


def test_build_cloudformation_parameter_list_omits_execution_role_arns_when_empty() -> None:
    values = build_role_template_parameter_values(
        external_id="ext-123",
        saas_account_id="029037611564",
        saas_execution_role_arns="",
    )

    parameters = build_cloudformation_parameter_list(values)

    assert parameters == [
        {"ParameterKey": "SaaSAccountId", "ParameterValue": "029037611564"},
        {"ParameterKey": "ExternalId", "ParameterValue": "ext-123"},
    ]


def test_role_templates_constrain_execution_roles_via_aws_principal_arn() -> None:
    project_root = Path(__file__).resolve().parents[1]

    for rel_path in (
        "infrastructure/cloudformation/read-role-template.yaml",
        "infrastructure/cloudformation/write-role-template.yaml",
    ):
        template_text = (project_root / rel_path).read_text()

        assert '"Principal": {"AWS": f"arn:{partition}:iam::{saas_account_id}:root"}' in template_text
        assert '"ArnEquals"' in template_text
        assert '"aws:PrincipalArn"' in template_text
        assert 'TemplateVersion:' in template_text
