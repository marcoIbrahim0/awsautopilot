# Account Creation and Login

## Sign Up

1. Open your deployed app signup page.
2. Submit:
- Company name
- Your name
- Email
- Password (8+ chars)
3. After success, you are authenticated and continue into onboarding.

## Login

1. Open the login page.
2. Submit email and password.
3. On success, routing is based on onboarding completion state.

## Invite Flow

- Admins can invite users.
- Invited users accept via tokenized invite link and set password.

## Roles

- `admin`: tenant management and privileged actions
- `member`: limited operational access

## Current limitations

- Password reset/change routes are tracked in live E2E issue workflows and may vary by environment readiness.

## Next

- [Connect your AWS account](/Users/marcomaher/AWS%20Security%20Autopilot/docs/customer-guide/connecting-aws.md)
- [Troubleshooting](/Users/marcomaher/AWS%20Security%20Autopilot/docs/customer-guide/troubleshooting.md)
