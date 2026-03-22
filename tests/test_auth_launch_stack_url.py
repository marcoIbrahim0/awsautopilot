from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from backend.auth import build_read_role_launch_stack_url


def _fragment_params(url: str) -> dict[str, list[str]]:
    fragment = urlsplit(url).fragment
    query = fragment.split("?", 1)[1]
    return parse_qs(query)


def test_build_read_role_launch_stack_url_includes_execution_role_params_when_set() -> None:
    url = build_read_role_launch_stack_url(
        template_url="https://bucket.s3.eu-north-1.amazonaws.com/cloudformation/read-role/v1.5.8.yaml",
        region="eu-north-1",
        external_id="ext-123",
        saas_account_id="029037611564",
        saas_execution_role_arns=(
            "arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-api,"
            "arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-worker"
        ),
    )

    params = _fragment_params(url)

    assert params["param_SaaSExecutionRoleArns"] == [
        "arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-api,"
        "arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-worker"
    ]


def test_build_read_role_launch_stack_url_omits_execution_role_param_when_empty() -> None:
    url = build_read_role_launch_stack_url(
        template_url="https://bucket.s3.eu-north-1.amazonaws.com/cloudformation/read-role/v1.5.8.yaml",
        region="eu-north-1",
        external_id="ext-123",
        saas_account_id="029037611564",
    )

    params = _fragment_params(url)

    assert "param_SaaSExecutionRoleArns" not in params
