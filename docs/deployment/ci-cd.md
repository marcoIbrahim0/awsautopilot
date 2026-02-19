# CI/CD Pipeline Setup

This guide covers setting up continuous integration and deployment pipelines for AWS Security Autopilot.

## Overview

CI/CD pipelines automate:
- **Testing** — Run tests on pull requests
- **Building** — Build Docker images
- **Deploying** — Deploy to AWS (ECS/Lambda)
- **Rollback** — Automatic rollback on failure

## Current Required Quality Gates

The repository uses the following required CI status checks for merge readiness:

1. `Backend CI Matrix / Backend Required Gate`
2. `Worker CI Matrix / Worker Required Gate`
3. `Frontend CI Matrix / Frontend Required Gate`
4. `Security Phase 3 Cookie Auth and Edge Controls / Phase 3 Security Tests`
5. `Architecture Phase 2 Reliability / Architecture Phase 2 Required Gate`
6. `Architecture Phase 3 Readiness and DR / Phase 3 Architecture Tests`
7. `Frontend Accessibility CI / Accessibility Gate`
8. `Dependency Governance / Dependency Governance Required Gate`
9. `Migration Gate / Migration Gate`

Canonical governance for required checks and branch protection is maintained in:
- [Phase 4 Required Check Governance](../audit-remediation/phase4-required-check-governance.md)

Dependency version and vulnerability policy details are maintained in:
- [CI Dependency Governance Policy](ci-dependency-governance.md)

## GitHub Actions

### Example Workflow

```yaml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: eu-north-1
      - name: Build and push
        run: |
          docker build -t security-autopilot-app:${{ github.sha }} .
          docker tag security-autopilot-app:${{ github.sha }} 123456789012.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-app:${{ github.sha }}
          aws ecr get-login-password | docker login --username AWS --password-stdin 123456789012.dkr.ecr.eu-north-1.amazonaws.com
          docker push 123456789012.dkr.ecr.eu-north-1.amazonaws.com/security-autopilot-app:${{ github.sha }}
      - name: Deploy
        run: |
          ./scripts/deploy_saas_ecs_dev.sh --tag ${{ github.sha }} --api-count 1
```

## Rollback Procedures

### ECS Rollback

```bash
# Rollback to previous task definition
aws ecs update-service \
  --cluster security-autopilot-dev-cluster \
  --service security-autopilot-dev-api \
  --task-definition security-autopilot-dev-api:PREVIOUS_REVISION \
  --force-new-deployment
```

### CloudFormation Rollback

Automatic on stack update failure. Manual rollback:

```bash
aws cloudformation cancel-update-stack \
  --stack-name security-autopilot-saas-ecs-dev
```

## See Also

- [Infrastructure: ECS](infrastructure-ecs.md) — Deployment details
- [CI Dependency Governance Policy](ci-dependency-governance.md) — Version bounds, lockfile rules, vulnerability gates
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
