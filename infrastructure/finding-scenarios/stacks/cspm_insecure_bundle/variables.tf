variable "region" {
  description = "AWS region to deploy the insecure finding bundle."
  type        = string
  default     = "eu-north-1"
}

variable "name_prefix" {
  description = "Shared prefix used by all bundle resources."
  type        = string
  default     = "security-autopilot"
}

variable "instance_type" {
  description = "EC2 instance type used in the workload architecture."
  type        = string
  default     = "t3.micro"
}
