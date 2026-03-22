# Deployment Prerequisites

This guide covers all prerequisites needed before deploying AWS Security Autopilot infrastructure.

## AWS Account Setup

### Create AWS Account

If you don't have an AWS account:

1. Go to https://aws.amazon.com/
2. Click "Create an AWS Account"
3. Follow the signup process
4. Complete payment information (credit card required, but free tier available)

### AWS Account ID

Your AWS Account ID is a 12-digit number. Find it:

- **AWS Console**: Top-right corner (click your account name)
- **AWS CLI**: `aws sts get-caller-identity --query Account --output text`

You'll need this for:
- CloudFormation stack parameters (`SAAS_AWS_ACCOUNT_ID`)
- CloudFormation stack parameters (`SAAS_EXECUTION_ROLE_ARNS`) when narrowing customer trust to the exact SaaS runtime role set
- IAM trust policies (customer ReadRole)
- SQS queue URLs

---

## IAM Permissions

### Deployment User/Role

Create an IAM user or role with permissions to deploy infrastructure:

**Required Permissions**:
- `cloudformation:*` — Create/update/delete stacks
- `ec2:*` — VPC, subnets, security groups (for ECS)
- `ecs:*` — ECS cluster, services, task definitions
- `ecr:*` — Container registry (for ECS)
- `lambda:*` — Lambda functions (for serverless)
- `apigateway:*` — API Gateway (for serverless)
- `sqs:*` — SQS queues
- `s3:*` — S3 buckets (exports, support, templates)
- `rds:*` — RDS databases (if using RDS)
- `secretsmanager:*` — Secrets Manager
- `logs:*` — CloudWatch Logs
- `iam:*` — IAM roles and policies
- `route53:*` — DNS (if using Route 53)
- `acm:*` — SSL certificates (if using ACM)
- `cloudwatch:*` — Metrics and alarms
- `events:*` — EventBridge (for scheduled jobs)

**Recommended**: Use an IAM role (not user) for deployments, especially in CI/CD pipelines.

### Example IAM Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "ec2:*",
        "ecs:*",
        "ecr:*",
        "lambda:*",
        "apigateway:*",
        "sqs:*",
        "s3:*",
        "rds:*",
        "secretsmanager:*",
        "logs:*",
        "iam:*",
        "route53:*",
        "acm:*",
        "cloudwatch:*",
        "events:*"
      ],
      "Resource": "*"
    }
  ]
}
```

**Note**: For production, restrict resources to specific ARNs and use least-privilege principles.

---

## Tools Installation

### AWS CLI

Install AWS CLI v2:

```bash
# macOS (Homebrew)
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Windows
# Download installer from https://aws.amazon.com/cli/
```

**Configure AWS CLI**:

```bash
aws configure
# AWS Access Key ID: <your-access-key>
# AWS Secret Access Key: <your-secret-key>
# Default region name: eu-north-1
# Default output format: json
```

**Verify configuration**:

```bash
aws sts get-caller-identity
```

### Docker

Required for building container images (ECS deployment):

```bash
# macOS (Homebrew)
brew install docker

# Linux (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install docker.io

# Windows
# Download Docker Desktop from https://www.docker.com/products/docker-desktop
```

**Verify installation**:

```bash
docker --version
docker run hello-world
```

### Terraform (Optional)

If using Terraform instead of CloudFormation:

```bash
# macOS (Homebrew)
brew install terraform

# Linux
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Windows
# Download from https://www.terraform.io/downloads
```

**Verify installation**:

```bash
terraform version
```

### Git

For cloning the repository:

```bash
# macOS (Homebrew)
brew install git

# Linux (Ubuntu/Debian)
sudo apt-get install git

# Windows
# Download from https://git-scm.com/download/win
```

**Verify installation**:

```bash
git --version
```

### Python 3.10+

Required for running deployment scripts:

```bash
# macOS (Homebrew)
brew install python@3.12

# Linux (Ubuntu/Debian)
sudo apt-get install python3.12 python3.12-venv

# Windows
# Download from https://www.python.org/downloads/
```

**Verify installation**:

```bash
python3 --version  # Should be 3.10+
```

---

## Database Setup

### Option 1: AWS RDS PostgreSQL

**Pros**: Managed service, automated backups, high availability

**Steps**:
1. Create RDS PostgreSQL instance (see [Database Setup](database.md))
2. Note connection string (format: `postgresql+asyncpg://user:pass@host:5432/dbname`)
3. Configure security groups to allow access from ECS/Lambda

**Cost**: ~$15-50/month (db.t3.micro)

### Option 2: External PostgreSQL (e.g., Neon)

**Pros**: Free tier available, easy setup, no AWS management

**Steps**:
1. Sign up at https://neon.tech (or another provider)
2. Create project and database
3. Copy connection string
4. Note: Requires SSL (`sslmode=require`)

**Cost**: Free tier available, then ~$10-20/month

### Option 3: Local PostgreSQL (Development Only)

**Not recommended for production**. Use for local development only.

---

## Domain Name (Optional)

If you want a custom API domain (e.g., `api.yourcompany.com`):

1. **Register domain** (if not already owned):
   - Use Route 53, Namecheap, GoDaddy, etc.
   - Cost: ~$10-15/year

2. **Create Route 53 hosted zone** (if using Route 53):
   - See [Domain & DNS](domain-dns.md)

3. **Request ACM certificate**:
   - See [Domain & DNS](domain-dns.md)

**Note**: You can deploy without a custom domain (use ALB DNS name or API Gateway URL).

---

## Architecture Overview

Before deploying, understand the architecture:

### Control Plane Components

1. **API** — FastAPI application (ECS Fargate task or Lambda function)
2. **Worker** — SQS consumer (ECS Fargate task or Lambda function)
3. **Database** — PostgreSQL (RDS or external)
4. **Queues** — SQS (4 main queues + 4 DLQs + 1 quarantine queue)
5. **Storage** — S3 (exports, support files, templates)
6. **Secrets** — Secrets Manager (`DATABASE_URL`, `JWT_SECRET`, `BUNDLE_REPORTING_TOKEN_SECRET`, `CONTROL_PLANE_EVENTS_SECRET`, etc.)
7. **Monitoring** — CloudWatch (logs, metrics, alarms)

### Customer AWS Resources

Customers deploy in their AWS accounts:
- **ReadRole** — IAM role for read-only access
- **WriteRole** — out of scope for the current product contract; retained only as a deprecated template/reference artifact
- **Control-Plane Forwarder** — EventBridge rule + API Destination (optional)

See [Connecting Your AWS Account](../customer-guide/connecting-aws.md) and [WriteRole status](../connect-write-role.md) for the current customer-side role contract.

---

## Resource Limits & Quotas

Check AWS service quotas before deploying:

### VPC Limits
- **VPCs per region**: 5 (default)
- **Subnets per VPC**: 200 (default)
- **Security groups per VPC**: 2,500 (default)

### ECS Limits
- **Clusters per account**: 1,000 (default)
- **Services per cluster**: 1,000 (default)
- **Tasks per service**: 1,000 (default)

### Lambda Limits
- **Functions per region**: 1,000 (default)
- **Concurrent executions**: 1,000 (default, can request increase)

### SQS Limits
- **Queues per account**: 1,000 (default)
- **Messages per queue**: Unlimited

**Request quota increases** if needed: AWS Console → Service Quotas → Request increase

---

## Cost Estimation

Before deploying, estimate costs:

### ECS Fargate (Dev Environment)
- **ECS Tasks**: ~$30/month (1 API + 1 worker, 0.5 vCPU, 1GB each)
- **ALB**: ~$16/month
- **ECR**: ~$1/month (storage)
- **RDS**: ~$15-50/month (db.t3.micro)
- **SQS**: ~$1/month (low traffic)
- **S3**: ~$1/month (minimal storage)
- **CloudWatch**: ~$5/month
- **Secrets Manager**: ~$2/month (4 secrets)

**Total**: ~$70-120/month

### Lambda Serverless (Dev Environment)
- **Lambda**: ~$5/month (low traffic)
- **API Gateway**: ~$5/month
- **RDS**: ~$15-50/month
- **SQS**: ~$1/month
- **S3**: ~$1/month
- **CloudWatch**: ~$5/month
- **Secrets Manager**: ~$1/month

**Total**: ~$35-70/month

**Note**: Costs vary by region, traffic, and resource sizing. Use AWS Pricing Calculator for accurate estimates.

---

## Security Considerations

### Secrets Management

- **Never commit secrets** to Git
- **Use Secrets Manager** for production secrets
- **Rotate secrets** regularly (`JWT_SECRET`, `BUNDLE_REPORTING_TOKEN_SECRET`, database passwords)

### Network Security

- **Use VPC** for ECS tasks (not required for Lambda)
- **Restrict security groups** to minimum required access
- **Use private subnets** for database (if using RDS)

### IAM Best Practices

- **Least privilege** — Grant minimum required permissions
- **Use roles** — Prefer IAM roles over users for applications
- **Rotate credentials** — Regularly rotate access keys

---

## Verification Checklist

Before proceeding to deployment:

- [ ] AWS account created and configured
- [ ] AWS CLI installed and configured (`aws sts get-caller-identity` works)
- [ ] IAM user/role with deployment permissions created
- [ ] Docker installed (for ECS deployment)
- [ ] Python 3.10+ installed
- [ ] Git installed (for cloning repository)
- [ ] Database provisioned (RDS or external)
- [ ] Domain name registered (optional)
- [ ] AWS service quotas checked (VPC, ECS, Lambda, SQS)
- [ ] Cost estimation reviewed

---

## Next Steps

After completing prerequisites:

1. **[Infrastructure: ECS](infrastructure-ecs.md)** — Deploy ECS Fargate infrastructure
2. **[Infrastructure: Serverless](infrastructure-serverless.md)** — Deploy Lambda serverless infrastructure
3. **[Database Setup](database.md)** — Configure PostgreSQL database
4. **[Secrets & Configuration](secrets-config.md)** — Set up Secrets Manager

---

## Troubleshooting

### AWS CLI Not Configured

**Error**: `Unable to locate credentials`

**Solution**:
```bash
aws configure
# Enter access key, secret key, region
```

### Docker Not Running

**Error**: `Cannot connect to the Docker daemon`

**Solution**:
```bash
# Start Docker service
sudo systemctl start docker  # Linux
# Or start Docker Desktop (macOS/Windows)
```

### Database Connection Issues

**Error**: `Connection refused` or `SSL required`

**Solution**:
- Verify database is running and accessible
- Check security groups (RDS) or firewall rules
- Ensure SSL is enabled for cloud-hosted databases (`sslmode=require`)
