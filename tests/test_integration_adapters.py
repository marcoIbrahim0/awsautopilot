from backend.services.integration_adapters import _jira_create_payload, _jira_update_payload


def test_jira_create_payload_uses_adf_description_and_omits_unassigned_assignee() -> None:
    payload = _jira_create_payload(
        config={"project_key": "KAN"},
        payload={
            "title": "EBS default encryption should be enabled",
            "description": "Enable EBS default encryption for the account.",
            "external_assignee_key": "unassigned",
        },
    )

    fields = payload["fields"]
    assert fields["project"] == {"key": "KAN"}
    assert fields["summary"] == "EBS default encryption should be enabled"
    assert fields["description"] == {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "Enable EBS default encryption for the account."}],
            }
        ],
    }
    assert "assignee" not in fields


def test_jira_update_payload_keeps_valid_assignee_account_id() -> None:
    payload = _jira_update_payload(
        payload={
            "title": "EBS default encryption should be enabled",
            "description": "Enable EBS default encryption for the account.",
            "external_assignee_key": "70121:8adc128e-145d-4b13-85cc-a833777436aa",
        }
    )

    fields = payload["fields"]
    assert fields["assignee"] == {"accountId": "70121:8adc128e-145d-4b13-85cc-a833777436aa"}
    assert fields["description"]["type"] == "doc"
