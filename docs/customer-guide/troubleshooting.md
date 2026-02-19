# Troubleshooting & FAQs

Common issues and solutions for AWS Security Autopilot customers.

## Account & Authentication

### Can't Log In

**Symptoms**: Login fails with "Invalid email or password"

**Solutions**:
- Verify email address is correct (case-sensitive)
- Check password is correct
- Try password reset (if available) or contact support

### Invitation Link Expired

**Symptoms**: "Invitation token expired" error

**Solution**: Ask your admin to send a new invitation

---

## AWS Account Connection

### AssumeRole Fails

**Symptoms**: "Cannot assume role" or "AccessDenied" when connecting account

**Solutions**:
- Verify **External ID** matches exactly (case-sensitive, no extra spaces)
- Verify **SaaS Account ID** is correct (`029037611564`)
- Check **IAM trust policy** allows the SaaS account
- Verify **role ARN** is correct and role exists
- Check CloudFormation stack status (should be `CREATE_COMPLETE`)

### Validation Fails

**Symptoms**: Account connection validation fails

**Solutions**:
- Verify role ARN format: `arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME`
- Check role exists in the correct AWS account
- Verify External ID matches your tenant's External ID
- Ensure role trust policy includes ExternalId condition

### CloudFormation Stack Fails

**Symptoms**: Stack creation fails with errors

**Solutions**:
- **"Resource already exists"**: Delete existing roles or use different stack name
- **"Invalid parameter"**: Verify External ID format (`ext-` + 16 hex chars)
- **"Access denied"**: Check IAM permissions for CloudFormation

---

## Findings & Actions

### No Findings Appear

**Symptoms**: Findings page is empty after connecting account

**Solutions**:
- **Wait for ingestion** — First ingestion takes 5-10 minutes
- **Check account status** — Go to Settings → AWS Accounts, verify account is "active"
- **Trigger manual ingestion** — Click "Ingest" button on account
- **Verify Security Hub** — Ensure Security Hub is enabled in your AWS account
- **Check regions** — Verify regions are configured correctly

### Findings Not Updating

**Symptoms**: Findings are stale or not refreshing

**Solutions**:
- **Trigger manual ingestion** — Click "Ingest" on the account
- **Check account status** — Verify account is not "disabled"
- **Verify Security Hub** — Ensure Security Hub is still enabled
- **Check worker logs** — Contact support if ingestion jobs are failing

### Actions Not Computing

**Symptoms**: Actions page shows "No actions" or actions are stale

**Solutions**:
- **Trigger action computation** — Click "Compute Actions" button
- **Wait for processing** — Action computation takes 1-2 minutes
- **Check findings** — Ensure findings exist (actions are derived from findings)
- **Check exceptions** — Verify findings aren't suppressed by exceptions

---

## Remediation

### Direct Fix Fails

**Symptoms**: Remediation run fails with error

**Solutions**:
- **Check WriteRole** — Verify WriteRole is deployed and connected
- **Verify permissions** — Ensure WriteRole has required permissions
- **Check pre-checks** — Review pre-remediation checks in run details
- **Review logs** — Check remediation run logs for specific error

### PR Bundle Not Generated

**Symptoms**: PR bundle download fails or is empty

**Solutions**:
- **Wait for generation** — PR bundle generation takes 30-60 seconds
- **Check run status** — Ensure remediation run is in "completed" status
- **Retry** — Click "Generate PR Bundle" again
- **Contact support** — If issue persists

---

## Exports & Reports

### Export Fails

**Symptoms**: Evidence pack export fails or times out

**Solutions**:
- **Reduce scope** — Export smaller date ranges or specific accounts
- **Wait and retry** — Large exports can take 5-10 minutes
- **Check S3 permissions** — Verify export bucket is accessible
- **Contact support** — For persistent issues

### Baseline Report Not Generated

**Symptoms**: 48h baseline report fails or is empty

**Solutions**:
- **Wait for completion** — Report generation takes 2-5 minutes
- **Check account status** — Ensure at least one account is connected and active
- **Verify findings** — Ensure findings exist (report needs data)
- **Retry** — Click "Generate Report" again

---

## Notifications

### Weekly Digest Not Received

**Symptoms**: Email/Slack digest not arriving

**Solutions**:
- **Check settings** — Go to Settings → Notifications, verify digest is enabled
- **Verify recipients** — Ensure email addresses are correct
- **Check spam folder** — Email may be filtered
- **Verify Slack webhook** — For Slack, ensure webhook URL is correct and active

### Slack Integration Not Working

**Symptoms**: Slack messages not appearing

**Solutions**:
- **Verify webhook URL** — Test webhook URL manually
- **Check webhook permissions** — Ensure webhook has permission to post
- **Verify Slack settings** — Go to Settings → Notifications, ensure Slack digest is enabled
- **Test webhook** — Use Slack's webhook tester to verify URL

---

## Performance

### Slow Page Loads

**Symptoms**: Pages take long to load

**Solutions**:
- **Check internet connection** — Verify stable connection
- **Reduce filters** — Use fewer filters on findings/actions pages
- **Clear browser cache** — Clear cache and cookies
- **Contact support** — If issue persists

### Timeouts

**Symptoms**: Requests timeout or fail

**Solutions**:
- **Retry** — Many operations are idempotent, safe to retry
- **Reduce scope** — Export smaller datasets, filter findings
- **Check status page** — Verify service is operational
- **Contact support** — For persistent timeouts

---

## General

### Feature Not Working

**Symptoms**: A feature doesn't work as expected

**Solutions**:
1. **Check documentation** — Review relevant guide
2. **Clear browser cache** — Refresh page or clear cache
3. **Try different browser** — Rule out browser-specific issues
4. **Check browser console** — Look for JavaScript errors
5. **Contact support** — Provide:
   - What you were trying to do
   - What happened vs. what you expected
   - Screenshots or error messages
   - Browser and OS version

### Data Not Syncing

**Symptoms**: Data appears stale or out of sync

**Solutions**:
- **Refresh page** — Hard refresh (Ctrl+F5 or Cmd+Shift+R)
- **Trigger sync** — Manually trigger ingestion or action computation
- **Check account status** — Verify accounts are active
- **Wait for background jobs** — Some sync happens asynchronously

---

## Getting Help

### Contact Support

- **Email**: support@yourcompany.com
- **Response time**: Within 24 hours (business days)
- **What to include**:
  - Your tenant name or email
  - Description of the issue
  - Steps to reproduce
  - Screenshots or error messages
  - Browser/OS version

### Self-Service Resources

- **[Documentation Index](../README.md)** — Complete documentation
- **[API Reference](../api/README.md)** — For technical integrations
- **[Architecture Docs](../architecture/owner/README.md)** — Technical details

---

## See Also

- [Account Creation](account-creation.md) — Signup and login
- [Connecting AWS Account](connecting-aws.md) — AWS account connection
- [Features Walkthrough](features-walkthrough.md) — Complete feature guide
