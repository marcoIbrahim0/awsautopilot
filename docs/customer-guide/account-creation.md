# Account Creation & Login

This guide covers creating an account, logging in, and accepting team invitations.

## Creating an Account

### Sign Up

1. **Visit the signup page** (e.g., https://app.yourcompany.com/signup)

2. **Fill in the form**:
   - **Company Name** — Your organization name
   - **Your Name** — Your full name
   - **Email** — Your email address (used for login)
   - **Password** — Minimum 8 characters

3. **Click "Sign Up"**

4. **You're automatically logged in** and redirected to the onboarding wizard

### What Happens During Signup

- A new **tenant** (organization) is created
- You become the **admin** user for that tenant
- A unique **External ID** is generated (used for AWS account connection)
- A **control-plane token** is generated for onboarding (one-time reveal only); only a non-recoverable hash + fingerprint are stored server-side

---

## Logging In

### Login Process

1. **Visit the login page** (e.g., https://app.yourcompany.com/login)

2. **Enter credentials**:
   - **Email** — Your registered email
   - **Password** — Your password

3. **Click "Log In"**

4. **You're redirected**:
   - If onboarding is incomplete → Onboarding wizard
   - If onboarding is complete → Findings page (or dashboard)

### Password Requirements

- Minimum 8 characters
- Maximum 128 characters
- No other requirements (but use a strong password!)

### Forgot Password

> ⚠️ **Status**: Planned — Password reset functionality is not yet implemented.

Contact support@yourcompany.com for password reset assistance.

---

## Accepting Team Invitations

### Receiving an Invite

When a team member invites you:

1. **Check your email** for an invitation from AWS Security Autopilot
2. **Click the invitation link** (or copy the token from the email)

### Accepting the Invite

1. **Visit the accept-invite page** (e.g., https://app.yourcompany.com/accept-invite?token=xxx)

2. **Review invitation details**:
   - **Tenant name** — Organization you're joining
   - **Invited by** — Who invited you
   - **Your email** — Email address you'll use

3. **Set your password**:
   - **Password** — Minimum 8 characters
   - **Confirm Password** — Re-enter password

4. **Click "Accept Invitation"**

5. **You're automatically logged in** and redirected to the dashboard

### Invited User Onboarding

- If the tenant has **no AWS accounts** → You'll see onboarding wizard (to connect first account)
- If the tenant **has AWS accounts** → You'll go directly to the dashboard

---

## User Roles

### Admin

- **Full access** to all features
- Can **invite users**
- Can **delete users**
- Can **manage AWS accounts**
- Can **approve remediations**

### Member

- **Read-only** access to findings and actions
- Can **create exceptions** (with admin approval)
- Cannot **invite users**
- Cannot **approve remediations**

---

## Account Management

### Viewing Your Profile

1. Click your **name/avatar** in the top-right corner
2. Select **"Settings"** or **"Profile"**
3. View your:
   - Email address
   - Name
   - Role (admin/member)
   - Tenant name

### Updating Your Profile

1. Go to **Settings** → **Profile**
2. Update your **name** (email cannot be changed)
3. Click **"Save"**

### Changing Password

> ⚠️ **Status**: Planned — Password change functionality is not yet implemented.

Contact support@yourcompany.com for password change assistance.

---

## Troubleshooting

### Can't Log In

**Check**:
- Email address is correct (case-sensitive)
- Password is correct
- Account exists (try signing up if new)

**Solution**: Contact support@yourcompany.com

### Invitation Link Expired

**Solution**: Ask the admin to send a new invitation

### Email Not Received

**Check**:
- Spam/junk folder
- Email address is correct
- Invitation was actually sent

**Solution**: Ask the admin to resend the invitation

---

## Next Steps

After creating an account:

1. **[Connect AWS Account](connecting-aws.md)** — Deploy IAM roles in your AWS account
2. **[Complete Onboarding](features-walkthrough.md#onboarding-wizard)** — Follow the onboarding wizard
3. **[Invite Team Members](team-management.md)** — Add your team

---

## See Also

- [Connecting AWS Account](connecting-aws.md) — AWS account connection
- [Team Management](team-management.md) — User invites and roles
- [Features Walkthrough](features-walkthrough.md) — Complete feature guide
