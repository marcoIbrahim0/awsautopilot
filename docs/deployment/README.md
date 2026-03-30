# Owner Deployment Guide

This guide provides step-by-step instructions for deploying AWS Security Autopilot infrastructure on AWS. It covers both **ECS Fargate** (recommended for dev/prod) and **Lambda serverless** deployment options.

## Overview

AWS Security Autopilot can be deployed in two ways:

1. **ECS Fargate** (recommended) — Container-based deployment with ALB, persistent connections, easier debugging
2. **Lambda Serverless** — Function-based deployment with HTTP API, cost-efficient scaling

Both options use the same codebase and support the same features.

## Canonical Repo Contract

- Root `master` is the only authoritative branch for deployable code.
- `frontend/` is tracked directly inside the root repo; do not restore a separate frontend repo, gitlink, or submodule flow.
- Production frontend deploys must be run from `frontend/` inside the root repo checkout on `master`.

## Deployment Prerequisites

Before starting, ensure you have:

- **AWS Account** with appropriate permissions
- **AWS CLI** installed and configured
- **Docker** (for building container images)
- **PostgreSQL database** (RDS or external like Neon)
- **Domain name** (optional, for custom API domain)

See [Prerequisites](prerequisites.md) for detailed requirements.

## Quick Start

### Option A: ECS Fargate Deployment

1. **Set up prerequisites** — [Prerequisites](prerequisites.md)
2. **Deploy SQS queues** — [Infrastructure: ECS](infrastructure-ecs.md#step-1-deploy-sqs-queues)
3. **Deploy ECS infrastructure** — [Infrastructure: ECS](infrastructure-ecs.md#step-2-deploy-ecs-infrastructure)
4. **Configure secrets** — [Secrets & Configuration](secrets-config.md)
5. **Deploy database** — [Database Setup](database.md)
6. **Deploy domain & DNS** — [Domain & DNS](domain-dns.md) (optional)
7. **Set up monitoring** — [Monitoring & Alerting](monitoring-alerting.md)

### Option B: Lambda Serverless Deployment

1. **Set up prerequisites** — [Prerequisites](prerequisites.md)
2. **Deploy SQS queues** — [Infrastructure: Serverless](infrastructure-serverless.md#step-1-deploy-sqs-queues)
3. **Deploy Lambda infrastructure** — [Infrastructure: Serverless](infrastructure-serverless.md)
4. **Configure secrets** — [Secrets & Configuration](secrets-config.md)
5. **Deploy database** — [Database Setup](database.md)
6. **Set up monitoring** — [Monitoring & Alerting](monitoring-alerting.md)

## Deployment Order

The recommended deployment order is:

1. **SQS Queues** — Required for API and worker communication
2. **Database** — PostgreSQL (RDS or external)
3. **Compute Infrastructure** — ECS Fargate or Lambda
4. **Secrets** — AWS Secrets Manager
5. **Domain & DNS** — Route 53, ACM certificates (optional)
6. **Monitoring** — CloudWatch logs, metrics, alarms

## Documentation Structure

- **[Prerequisites](prerequisites.md)** — AWS accounts, IAM permissions, tools, architecture overview
- **[Infrastructure: ECS](infrastructure-ecs.md)** — ECS Fargate deployment (CloudFormation/Terraform)
- **[Infrastructure: Serverless](infrastructure-serverless.md)** — Lambda serverless deployment
- **[Database Setup](database.md)** — RDS Postgres configuration, migrations, backups
- **[Domain & DNS](domain-dns.md)** — Route 53, ACM certificates, ALB/CloudFront
- **[Secrets & Configuration](secrets-config.md)** — Environment variables and Secrets Manager
- **[CI/CD](ci-cd.md)** — Deployment pipelines, rollback procedures
- **[CI Dependency Governance Policy](ci-dependency-governance.md)** — Required CI checks, lock/version policy, and vulnerability scan gates
- **[Monitoring & Alerting](monitoring-alerting.md)** — CloudWatch setup, alarms, readiness checks

## Cost Considerations

### ECS Fargate

- **ECS Tasks**: ~$0.04/vCPU-hour, ~$0.004/GB-hour (varies by region)
- **ALB**: ~$0.0225/hour + $0.008/GB data processed
- **ECR**: $0.10/GB-month storage
- **Estimated monthly cost** (dev): ~$50-100 (1 API task + 1 worker task, minimal traffic)

### Lambda Serverless

- **Lambda**: $0.20 per 1M requests + $0.0000166667/GB-second
- **API Gateway**: $1.00 per 1M requests + $0.09/GB data transfer
- **Estimated monthly cost** (dev): ~$10-30 (low traffic)

### Common Costs (Both Options)

- **RDS Postgres**: ~$15-50/month (db.t3.micro)
- **SQS**: $0.40 per 1M requests (first 1B requests/month free)
- **S3**: $0.023/GB-month storage + $0.005/1K PUT requests
- **CloudWatch**: $0.50/GB log ingestion + $0.10/metric/month
- **Secrets Manager**: $0.40/secret/month

**Total estimated monthly cost** (dev environment): **$100-200** (ECS) or **$50-100** (Lambda)

## First Deployment Checklist

- [ ] AWS account created and configured
- [ ] IAM user/role with deployment permissions
- [ ] AWS CLI installed and configured
- [ ] PostgreSQL database provisioned (RDS or external)
- [ ] Domain name registered (optional)
- [ ] SQS queues deployed
- [ ] Compute infrastructure deployed (ECS or Lambda)
- [ ] Secrets configured in Secrets Manager
- [ ] Database migrations applied
- [ ] Health checks passing (`/health`, `/ready`)
- [ ] Monitoring and alarms configured

## Future Deployments

For subsequent deployments:

1. **Build and push container image** (ECS) or **package Lambda** (serverless)
2. **Update CloudFormation stack** with new image/package
3. **Verify health checks** pass
4. **Monitor logs** for errors

See [CI/CD](ci-cd.md) for automated deployment workflows.

## Rollback Procedures

If a deployment fails:

1. **ECS**: Rollback to previous task definition revision
2. **Lambda**: Deploy previous function version
3. **CloudFormation**: Use stack rollback (automatic on failure)

See [CI/CD](ci-cd.md#rollback-procedures) for detailed rollback steps.

## Support

- **Deployment Issues**: Check [Troubleshooting](#troubleshooting) section
- **Infrastructure Questions**: See [Runbooks index](../runbooks/README.md)
- **API Questions**: See [Local backend API guide](../local-dev/backend.md)

---

## Troubleshooting

### CloudFormation Stack Fails

- **Check IAM permissions** — Ensure deployment user/role has required permissions
- **Check resource limits** — Verify VPC, ECS, Lambda quotas
- **Check parameter values** — Verify all required parameters are provided
- **Review CloudFormation events** — Check stack events for specific error

### Health Checks Failing

- **Check database connectivity** — Verify `DATABASE_URL` is correct
- **Check SQS queue URLs** — Verify queue URLs match deployed stacks
- **Check secrets** — Verify Secrets Manager secrets are accessible
- **Check logs** — Review CloudWatch logs for errors

### High Costs

- **Review resource sizing** — Reduce ECS task CPU/memory or Lambda memory
- **Review S3 usage** — Enable lifecycle policies for old exports
- **Review CloudWatch logs** — Set log retention policies
- **Use Lambda** — Consider Lambda for cost savings at low traffic

---

## Next Steps

After deployment:

1. **[Customer Onboarding Guide](../customer-guide/README.md)** — Help customers get started
2. **[Runbooks index](../runbooks/README.md)** — Use operator runbooks for incidents and debugging
3. **[Monitoring & Alerting](monitoring-alerting.md)** — Set up comprehensive monitoring
