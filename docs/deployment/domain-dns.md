# Domain & DNS Configuration

This guide covers setting up custom domains, Route 53, and ACM certificates for AWS Security Autopilot.

## Overview

Optional but recommended for production:
- **Route 53** — DNS hosting
- **ACM** — SSL/TLS certificates
- **ALB/API Gateway** — Custom domain configuration

## Route 53 Setup

### Create Hosted Zone

```bash
aws route53 create-hosted-zone \
  --name api.yourcompany.com \
  --caller-reference $(date +%s)
```

### Get Name Servers

```bash
aws route53 get-hosted-zone \
  --id Z1234567890ABC \
  --query "DelegationSet.NameServers"
```

Update your domain registrar with these name servers.

## ACM Certificate

### Request Certificate

```bash
aws acm request-certificate \
  --domain-name api.yourcompany.com \
  --validation-method DNS \
  --region eu-north-1
```

### Validate Certificate

Follow DNS validation instructions (add CNAME record to Route 53).

### Get Certificate ARN

```bash
aws acm list-certificates \
  --region eu-north-1 \
  --query "CertificateSummaryList[?DomainName=='api.yourcompany.com'].CertificateArn" \
  --output text
```

## ALB Configuration

Update ECS stack with certificate ARN (see [Infrastructure: ECS](infrastructure-ecs.md)).

## API Gateway Configuration

For Lambda deployment, configure custom domain in API Gateway:

```bash
aws apigatewayv2 create-domain-name \
  --domain-name api.yourcompany.com \
  --domain-name-configurations CertificateArn=arn:aws:acm:...
```

## See Also

- [Infrastructure: ECS](infrastructure-ecs.md) — ECS deployment with custom domain
- [AWS Route 53 Documentation](https://docs.aws.amazon.com/route53/)
- [AWS ACM Documentation](https://docs.aws.amazon.com/acm/)
