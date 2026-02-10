output "bundle_name" {
  value = "cspm_insecure_bundle"
}

output "foundational_controls" {
  value = {
    architecture_name            = module.foundational_controls_gaps.architecture_name
    audit_bucket_name            = module.foundational_controls_gaps.audit_bucket_name
    regional_cloudtrail_arn      = module.foundational_controls_gaps.regional_cloudtrail_arn
    config_recorder_name         = module.foundational_controls_gaps.config_recorder_name
    config_delivery_channel_name = module.foundational_controls_gaps.config_delivery_channel_name
  }
}

output "workload_stack" {
  value = {
    architecture_name         = module.insecure_workload_stack.architecture_name
    ec2_instance_id           = module.insecure_workload_stack.ec2_instance_id
    workload_iam_role_name    = module.insecure_workload_stack.workload_iam_role_name
    open_admin_security_group = module.insecure_workload_stack.open_admin_security_group_id
    workload_snapshot_id      = module.insecure_workload_stack.workload_snapshot_id
    bucket_names              = module.insecure_workload_stack.bucket_names
  }
}
