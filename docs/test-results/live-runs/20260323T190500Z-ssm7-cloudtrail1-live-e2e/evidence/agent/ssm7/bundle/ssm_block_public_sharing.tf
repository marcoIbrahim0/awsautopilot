# SSM block public document sharing - Action: e6b1eac2-041c-4fb3-9a47-2525a3afa908
resource "aws_ssm_service_setting" "security_autopilot" {
  setting_id    = "arn:aws:ssm:us-east-1:696505809372:servicesetting/ssm/documents/console/public-sharing-permission"
  setting_value = "Disable"
}
