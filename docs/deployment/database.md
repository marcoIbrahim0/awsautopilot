# Database Setup

This guide covers PostgreSQL database configuration for AWS Security Autopilot, including RDS setup, migrations, and backups.

## Overview

AWS Security Autopilot uses **PostgreSQL** as its primary database. You can use:
- **AWS RDS PostgreSQL** (recommended for production)
- **External PostgreSQL** (e.g., Neon, Supabase)
- **Local PostgreSQL** (development only)

## Option 1: AWS RDS PostgreSQL

### Create RDS Instance

```bash
# Create RDS PostgreSQL instance
aws rds create-db-instance \
  --db-instance-identifier security-autopilot-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.4 \
  --master-username postgres \
  --master-user-password "YourSecurePassword123!" \
  --allocated-storage 20 \
  --storage-type gp3 \
  --vpc-security-group-ids sg-xxx \
  --db-subnet-group-name default \
  --backup-retention-period 7 \
  --multi-az \
  --region eu-north-1
```

### Key Parameters

- **Instance class**: `db.t3.micro` (dev) or `db.t3.small` (prod)
- **Engine version**: PostgreSQL 15.4+ (recommended)
- **Storage**: 20 GB (gp3) minimum
- **Multi-AZ**: Enable for production (high availability)
- **Backup retention**: 7 days (production)

### Connection String Format

```
postgresql+asyncpg://postgres:password@security-autopilot-db.xxx.eu-north-1.rds.amazonaws.com:5432/postgres
```

**Note**: Replace `password` with your master password and `xxx` with your RDS endpoint.

### Security Group Configuration

Allow inbound traffic from ECS tasks or Lambda:

```bash
# Get ECS task security group
ECS_SG="sg-xxx"

# Allow PostgreSQL (port 5432) from ECS tasks
aws ec2 authorize-security-group-ingress \
  --group-id sg-rds-xxx \
  --protocol tcp \
  --port 5432 \
  --source-group "$ECS_SG"
```

---

## Option 2: External PostgreSQL (Neon)

### Create Neon Project

1. Sign up at https://neon.tech
2. Create project
3. Copy connection string

### Connection String Format

```
postgresql+asyncpg://user:password@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require
```

**Note**: Neon requires SSL (`sslmode=require`). The application automatically configures SSL for Neon connections.

---

## Database Migrations

### Apply Migrations

```bash
# Check current revision
alembic current

# Show repo heads
alembic heads

# Apply all migrations
alembic upgrade heads

# View migration history
alembic history
```

Use `heads`, not `head`: the current migration tree has two heads, `0042_bidirectional_integrations` and `0042_action_remediation_system_of_record`.

### Migration Guard

The application checks database revision on startup:
- **API**: Fails fast if DB revision != Alembic head
- **Worker**: Fails fast if DB revision != Alembic head

To disable (not recommended):
```bash
DB_REVISION_GUARD_ENABLED=false
```

When the guard fails, the recovery command for the current repo is:

```bash
alembic upgrade heads
```

### Create New Migration

After modifying models:

```bash
# Generate migration
alembic revision --autogenerate -m "description of changes"

# Review generated migration file
# Edit if needed

# Apply migration
alembic upgrade heads
```

---

## Backups

### RDS Automated Backups

RDS automatically creates backups:
- **Retention**: 7 days (configurable)
- **Backup window**: Configurable (e.g., 03:00-04:00 UTC)
- **Point-in-time recovery**: Available within retention period

### Manual Backup

```bash
# Create manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier security-autopilot-db \
  --db-snapshot-identifier security-autopilot-backup-$(date +%Y%m%d)
```

### Restore from Snapshot

```bash
# Restore from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier security-autopilot-db-restored \
  --db-snapshot-identifier security-autopilot-backup-20240101
```

---

## Performance Tuning

### Connection Pooling

SQLAlchemy uses connection pooling. Configure in connection string:

```
postgresql+asyncpg://user:pass@host/db?pool_size=10&max_overflow=20
```

### Indexes

Key indexes are created via migrations:
- `findings.finding_key` (unique per tenant)
- `actions.tenant_id`, `actions.status`
- `aws_accounts.tenant_id`, `aws_accounts.account_id`

### Query Optimization

- Use async queries (async SQLAlchemy)
- Avoid N+1 queries (use `joinedload` or `selectinload`)
- Monitor slow queries via CloudWatch (RDS) or database logs

---

## Monitoring

### RDS Metrics

Monitor via CloudWatch:
- **CPUUtilization** — Target: < 70%
- **DatabaseConnections** — Monitor connection pool usage
- **FreeableMemory** — Ensure sufficient memory
- **FreeStorageSpace** — Alert when < 20% free

### Database Logs

Enable PostgreSQL logs in RDS:

```bash
aws rds modify-db-instance \
  --db-instance-identifier security-autopilot-db \
  --enable-cloudwatch-logs-exports postgresql
```

---

## Security

### Encryption

- **Encryption at rest**: Enable for RDS (default in some regions)
- **Encryption in transit**: Use SSL (`sslmode=require`)

### Access Control

- **Use IAM database authentication** (optional, for RDS)
- **Restrict security groups** to ECS tasks/Lambda only
- **Rotate passwords** regularly

### Secrets Management

Store database credentials in AWS Secrets Manager (see [Secrets & Configuration](secrets-config.md)).

---

## Troubleshooting

### Connection Errors

**Error**: `Connection refused` or `timeout`

**Solutions**:
- Verify security group allows traffic from ECS/Lambda
- Check RDS instance is running
- Verify endpoint and port are correct

### SSL Errors

**Error**: `SSL connection required`

**Solutions**:
- Add `sslmode=require` to connection string
- For Neon: SSL is required (automatically configured)

### Migration Errors

**Error**: `Migration not found` or `Can't locate revision`

**Solutions**:
- Verify all migrations are applied: `alembic upgrade heads`
- Check migration files exist in `alembic/versions/`
- Verify `DATABASE_URL_SYNC` is set (for Alembic)


**Error**: `value too long for type character varying(32)` while inserting into `alembic_version`

**Solutions**:
- Existing databases created before the March 12, 2026 Alembic env fix may still have `alembic_version.version_num varchar(32)`.
- Widen the metadata column once, then rerun the upgrade:

```sql
ALTER TABLE alembic_version
ALTER COLUMN version_num TYPE varchar(64);
```

- Re-run `alembic upgrade heads`.

---

## Next Steps

- **[Secrets & Configuration](secrets-config.md)** — Store database credentials in Secrets Manager
- **[Infrastructure: ECS](infrastructure-ecs.md)** — Deploy ECS infrastructure
- **[Monitoring & Alerting](monitoring-alerting.md)** — Set up database monitoring

---

## See Also

- [AWS RDS Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
