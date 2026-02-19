# Infrastructure Deployment: ECS Fargate

This guide covers deploying AWS Security Autopilot on **ECS Fargate** with Application Load Balancer (ALB). This is the recommended deployment option for dev/prod environments.

## Overview

ECS Fargate deployment includes:
- **VPC** — Public subnets in 2 availability zones
- **ALB** — Application Load Balancer for API traffic
- **ECS Cluster** — Fargate cluster for API and worker tasks
- **ECR** — Container registry for Docker images
- **Security Groups** — Network security for ALB and tasks
- **IAM Roles** — Task execution and task roles
- **CloudWatch Logs** — Centralized logging

## Prerequisites

Before starting:
- ✅ [Prerequisites](prerequisites.md) completed
- ✅ [SQS Queues](infrastructure-ecs.md#step-1-deploy-sqs-queues) deployed
- ✅ [Database](database.md) provisioned
- ✅ [Secrets](secrets-config.md) created in Secrets Manager

---

## Step 1: Deploy SQS Queues

SQS queues must be deployed first (they're referenced by the ECS stack).

### Deploy SQS Stack

```bash
# Set variables
STACK_NAME="security-autopilot-sqs-queues"
REGION="eu-north-1"

# Deploy stack
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --template-file infrastructure/cloudformation/sqs-queues.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```

### Verify Deployment

```bash
# Check stack status
aws cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].StackStatus"

# Get queue URLs (save for later)
aws cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs" \
  --output table
```

**Outputs to note**:
- `IngestQueueURL`
- `EventsFastLaneQueueURL`
- `InventoryReconcileQueueURL`
- `ExportReportQueueURL`
- `ContractQuarantineQueueURL`
- `ApiSendPolicyArn`
- `WorkerConsumePolicyArn`

---

## Step 2: Build and Push Container Image

### Build Docker Image

```bash
# From project root
docker build -t security-autopilot-app:latest -f Containerfile .

# Tag for ECR
ECR_REPO="123456789012.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-app"
docker tag security-autopilot-app:latest "${ECR_REPO}:dev"
```

**Note**: Replace `123456789012` with your AWS account ID and `eu-north-1` with your region.

### Push to ECR

```bash
# Login to ECR
aws ecr get-login-password --region eu-north-1 | \
  docker login --username AWS --password-stdin "${ECR_REPO%%/*}"

# Push image
docker push "${ECR_REPO}:dev"
```

**Note**: ECR repository is created automatically by CloudFormation stack (see Step 3).

---

## Step 3: Deploy ECS Infrastructure

### Using Deployment Script

The easiest way is to use the provided deployment script:

```bash
# Set required variables
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db"
export JWT_SECRET="your-jwt-secret-here"
export CONTROL_PLANE_EVENTS_SECRET="your-secret-here"

# Run deployment script
./scripts/deploy_saas_ecs_dev.sh \
  --region eu-north-1 \
  --stack security-autopilot-saas-ecs-dev \
  --name-prefix security-autopilot-dev \
  --sqs-stack security-autopilot-sqs-queues \
  --repo security-autopilot-app \
  --tag dev \
  --cpu-arch ARM64 \
  --api-domain api.yourcompany.com \
  --certificate-arn arn:aws:acm:eu-north-1:123456789012:certificate/xxx \
  --api-count 1 \
  --worker-count 1
```

### Manual CloudFormation Deployment

If you prefer manual deployment:

```bash
# Prepare parameters
STACK_NAME="security-autopilot-saas-ecs-dev"
REGION="eu-north-1"

aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --template-file infrastructure/cloudformation/saas-ecs-dev.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    NamePrefix=security-autopilot-dev \
    AppName="AWS Security Autopilot" \
    AppEnv=dev \
    LogLevel=INFO \
    FrontendUrl=https://app.yourcompany.com \
    CorsOrigins=https://app.yourcompany.com \
    WorkerPool=all \
    EcrRepoName=security-autopilot-app \
    ImageTag=dev \
    CpuArchitecture=ARM64 \
    ApiDomain=api.yourcompany.com \
    CertificateArn=arn:aws:acm:eu-north-1:123456789012:certificate/xxx \
    SqsStackName=security-autopilot-sqs-queues \
    DatabaseUrl="postgresql+asyncpg://user:pass@host:5432/db" \
    JwtSecret="your-jwt-secret" \
    ControlPlaneEventsSecret="your-secret" \
    ApiDesiredCount=1 \
    WorkerDesiredCount=1 \
  --no-fail-on-empty-changeset
```

### Key Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `NamePrefix` | Resource name prefix | `security-autopilot-dev` |
| `AppEnv` | Environment (local/dev/prod) | `dev` |
| `EcrRepoName` | ECR repository name | `security-autopilot-app` |
| `ImageTag` | Container image tag | `dev` |
| `CpuArchitecture` | CPU architecture (ARM64/X86_64) | `ARM64` |
| `ApiDomain` | API domain (optional) | `api.yourcompany.com` |
| `CertificateArn` | ACM certificate ARN (optional) | `arn:aws:acm:...` |
| `SqsStackName` | SQS stack name | `security-autopilot-sqs-queues` |
| `ApiDesiredCount` | API service task count | `1` |
| `WorkerDesiredCount` | Worker service task count | `1` |

---

## Step 4: Apply Database Migrations

After ECS tasks start, apply database migrations:

```bash
# Get ECS task ID
CLUSTER="security-autopilot-dev-cluster"
SERVICE="security-autopilot-dev-api"
TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER" \
  --service-name "$SERVICE" \
  --query "taskArns[0]" \
  --output text)

# Execute migration command
aws ecs execute-command \
  --cluster "$CLUSTER" \
  --task "$TASK_ARN" \
  --container api \
  --command "alembic upgrade head" \
  --interactive
```

**Note**: Migrations run automatically on API task startup (see task definition command), but you can verify manually.

---

## Step 5: Verify Deployment

### Check Stack Outputs

```bash
aws cloudformation describe-stacks \
  --region eu-north-1 \
  --stack-name security-autopilot-saas-ecs-dev \
  --query "Stacks[0].Outputs" \
  --output table
```

**Key outputs**:
- `EcrRepositoryUri` — ECR repository URI
- `LoadBalancerDnsName` — ALB DNS name
- `ApiBaseUrlEffective` — Effective API base URL

### Check ECS Services

```bash
# Check API service
aws ecs describe-services \
  --cluster security-autopilot-dev-cluster \
  --services security-autopilot-dev-api \
  --query "services[0].{Status:status,RunningCount:runningCount,DesiredCount:desiredCount}"

# Check worker service
aws ecs describe-services \
  --cluster security-autopilot-dev-cluster \
  --services security-autopilot-dev-worker \
  --query "services[0].{Status:status,RunningCount:runningCount,DesiredCount:desiredCount}"
```

### Test Health Endpoints

```bash
# Get ALB DNS name
ALB_DNS=$(aws cloudformation describe-stacks \
  --region eu-north-1 \
  --stack-name security-autopilot-saas-ecs-dev \
  --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerDnsName'].OutputValue" \
  --output text)

# Test health endpoint
curl "http://${ALB_DNS}/health"

# Test readiness endpoint
curl "http://${ALB_DNS}/ready"
```

**Expected responses**:
- `/health` → `{"status":"ok","app":"AWS Security Autopilot"}`
- `/ready` → `{"ready":true,"status":"ok",...}`

---

## Step 6: Configure Domain & DNS (Optional)

If using a custom domain:

1. **Create Route 53 hosted zone** (if not exists):
   ```bash
   aws route53 create-hosted-zone \
     --name api.yourcompany.com \
     --caller-reference $(date +%s)
   ```

2. **Request ACM certificate**:
   ```bash
   aws acm request-certificate \
     --domain-name api.yourcompany.com \
     --validation-method DNS \
     --region eu-north-1
   ```

3. **Validate certificate** (follow DNS validation instructions)

4. **Create Route 53 record** pointing to ALB:
   ```bash
   # Get ALB DNS name
   ALB_DNS="security-autopilot-dev-api-xxx.eu-north-1.elb.amazonaws.com"
   
   # Create A record (alias to ALB)
   aws route53 change-resource-record-sets \
     --hosted-zone-id Z1234567890ABC \
     --change-batch '{
       "Changes": [{
         "Action": "CREATE",
         "ResourceRecordSet": {
           "Name": "api.yourcompany.com",
           "Type": "A",
           "AliasTarget": {
             "DNSName": "'"$ALB_DNS"'",
             "HostedZoneId": "Z1D633PJN98FT9",
             "EvaluateTargetHealth": true
           }
         }
       }]
     }'
   ```

5. **Update CloudFormation stack** with certificate ARN:
   ```bash
   aws cloudformation update-stack \
     --stack-name security-autopilot-saas-ecs-dev \
     --use-previous-template \
     --parameters ParameterKey=CertificateArn,ParameterValue=arn:aws:acm:...
   ```

See [Domain & DNS](domain-dns.md) for detailed instructions.

---

## Resource Sizing

### Default Sizing

- **API Task**: 512 CPU units (0.5 vCPU), 1024 MB memory
- **Worker Task**: 512 CPU units (0.5 vCPU), 1024 MB memory

### Scaling Recommendations

**Development**:
- API: 1 task (512 CPU, 1024 MB)
- Worker: 1 task (512 CPU, 1024 MB)

**Production**:
- API: 2+ tasks (1024 CPU, 2048 MB each)
- Worker: 2+ tasks (1024 CPU, 2048 MB each)

**Auto-scaling**: Configure ECS service auto-scaling based on:
- CPU utilization (target: 70%)
- Memory utilization (target: 80%)
- ALB request count

---

## Cost Considerations

### Monthly Cost Estimate (Dev Environment)

- **ECS Tasks**: ~$30/month (1 API + 1 worker, 0.5 vCPU, 1GB each)
- **ALB**: ~$16/month
- **ECR**: ~$1/month (storage)
- **VPC**: Free (within limits)
- **CloudWatch Logs**: ~$5/month

**Total**: ~$52/month (excluding RDS, SQS, S3)

### Cost Optimization

- **Use ARM64** — 20% cheaper than x86_64
- **Right-size tasks** — Start small, scale up as needed
- **Use Spot instances** — Not available for Fargate (use EC2 launch type if needed)
- **Set log retention** — Reduce CloudWatch Logs costs

---

## Troubleshooting

### Stack Deployment Fails

**Check CloudFormation events**:
```bash
aws cloudformation describe-stack-events \
  --stack-name security-autopilot-saas-ecs-dev \
  --max-items 10 \
  --query "StackEvents[*].{Time:Timestamp,Status:ResourceStatus,Reason:ResourceStatusReason}"
```

**Common issues**:
- **IAM permissions** — Verify deployment user/role has required permissions
- **Resource limits** — Check VPC, ECS quotas
- **Parameter validation** — Verify all required parameters are provided

### Tasks Not Starting

**Check task status**:
```bash
aws ecs describe-tasks \
  --cluster security-autopilot-dev-cluster \
  --tasks <task-arn> \
  --query "tasks[0].{LastStatus:lastStatus,StoppedReason:stoppedReason}"
```

**Check CloudWatch Logs**:
```bash
aws logs tail /ecs/security-autopilot-dev/api --follow
```

**Common issues**:
- **Secrets not found** — Verify Secrets Manager secrets exist
- **Database connection** — Verify `DATABASE_URL` is correct
- **Image pull errors** — Verify ECR image exists and task role has ECR permissions

### Health Checks Failing

**Check target group health**:
```bash
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn>
```

**Common issues**:
- **Security group** — Verify ALB security group allows traffic to task security group
- **Health check path** — Verify `/health` endpoint returns 200
- **Task not running** — Verify task is running and healthy

---

## Next Steps

- **[Database Setup](database.md)** — Configure RDS PostgreSQL (if using RDS)
- **[Domain & DNS](domain-dns.md)** — Set up custom domain
- **[Monitoring & Alerting](monitoring-alerting.md)** — Set up CloudWatch alarms
- **[CI/CD](ci-cd.md)** — Automate deployments

---

## See Also

- [Infrastructure: Serverless](infrastructure-serverless.md) — Lambda deployment option
- [Architecture Documentation](../architecture/owner/README.md) — System architecture
- [ECS Fargate Documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)
