# ECS Dev Deploy (ALB + Fargate)

This folder deploys:
- VPC (public subnets), ALB, ECS cluster
- One ECR repo (single image used for both API + worker)
- ECS services:
  - `api` behind ALB (port 8000)
  - `worker` (no load balancer)

It does **not** manage:
- WAF association (use `/Users/marcomaher/AWS Security Autopilot/scripts/deploy_phase3_security.sh --alb-arn ...`)
- Reconcile scheduler base URL/secret (update the CloudFormation stack after the API is live)
- DNS records (because your domain is not in Route53 in this account)

## Prereqs
- AWS creds configured for this account/region
- `terraform` installed
- `podman` (or Docker) installed

## 1) Build and push image

1. Create the ECR repo via Terraform first (step 2).
2. Login and push:

```bash
AWS_REGION=eu-north-1
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

aws ecr get-login-password --region "${AWS_REGION}" | podman login --username AWS --password-stdin "${ECR}"

podman build -f /Users/marcomaher/AWS Security Autopilot/Containerfile -t security-autopilot-app:dev /Users/marcomaher/AWS Security Autopilot
podman tag security-autopilot-app:dev "${ECR}/security-autopilot-app:dev"
podman push "${ECR}/security-autopilot-app:dev"
```

## 2) Terraform apply

Copy the example tfvars and fill secrets locally:

```bash
cd /Users/marcomaher/AWS Security Autopilot/infrastructure/terraform/saas-ecs-dev
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

After apply, Terraform prints the ALB DNS name and ALB ARN.

## 3) DNS + TLS (recommended)

Recommended hostname: `api.valensjewelry.com`.

1. Request an ACM cert in `eu-north-1` for `api.valensjewelry.com` (DNS validation).
2. Add the ACM validation CNAME in your DNS provider.
3. Add a CNAME:
   - `api.valensjewelry.com` -> `<alb_dns_name>`
4. Set `certificate_arn` in `terraform.tfvars` and re-apply to enable the 443 listener + HTTP->HTTPS redirect.

## 4) Attach WAF (SEC-010)

```bash
bash /Users/marcomaher/AWS Security Autopilot/scripts/deploy_phase3_security.sh \
  --region eu-north-1 \
  --scope REGIONAL \
  --alb-arn "<alb_arn_from_terraform_output>"
```

## 5) Update reconcile scheduler to stop calling ngrok

Update `security-autopilot-reconcile-scheduler` so `SaaSBaseUrl=https://api.valensjewelry.com` and
`ControlPlaneSecret` matches your API env `CONTROL_PLANE_EVENTS_SECRET`.

