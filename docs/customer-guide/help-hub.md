# Help Hub and Support Cases

The Help Hub is the customer-facing support surface for AWS Security Autopilot.

Authenticated route:

- `/help`

Public article route:

- `/help-center`

## What is in the Help Hub

The Help Hub has four tabs:

- `Help Center` for published support articles
- `Ask AI` for grounded, citation-backed answers
- `My Cases` for your private support threads
- `Shared Files` for files shared to your tenant by support

Support links are also available directly from:

- `/onboarding`
- `/accounts`
- `/actions/[id]`
- `/findings/[id]`
- `/settings`

Those entry points prefill the current route and any available account, action, or finding context so support can see where the issue happened.

## When to use each tab

Use `Help Center` when you want product guidance first:

- onboarding steps
- AWS account validation
- findings vs. actions
- exceptions and governance
- PR bundle workflows
- notifications, integrations, and shared files

Use `Ask AI` when you want a quick answer tied to the page you are on:

- the assistant cites Help Center articles
- the assistant can include the current route and visible account, action, or finding context
- AI follow-up turns stay grouped in one Help Hub thread until you start a new thread
- if the evidence is weak, the citations are missing, or you ask for a human, the request escalates into a support case

Current AI limitations:

- the assistant is read-only and cannot trigger remediation or AWS changes
- the assistant answers only from published Help Center articles plus the visible SaaS context attached to your current route
- if the AI service is unavailable, Help Hub falls back to a support escalation path instead of returning an ungrounded answer

Use `My Cases` when the issue needs a human reply:

- each case is private to the requester
- other users in your tenant cannot view your private case thread in the current MVP
- SaaS support admins can review and reply

Use `Shared Files` when support has posted tenant-visible artifacts such as:

- guidance documents
- exported diagnostics
- shared evidence files

Case attachments are different from Shared Files. Case attachments belong to a specific private support thread.

## What happens when you open a case

Every case stores the current route plus any referenced account, action, or finding context that was available when you opened it.

Current customer-visible case statuses:

- `new`
- `triaging`
- `waiting_on_customer`
- `resolved`
- `closed`

You receive in-app notification-center updates when:

- your case is created
- support replies
- support changes the case status

## Public Help Center

The public Help Center at `/help-center` exposes the same published article corpus used in the in-product Help Hub.

Use it when you need:

- documentation without signing in
- a direct article link to share internally
- a quick search across published support content

To open a private support case, sign in and use `/help`.

## Related

- [Feature implementation details](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/help-desk-platform.md)
- [Customer guide index](/Users/marcomaher/AWS%20Security%20Autopilot/docs/customer-guide/README.md)
- [Connect your AWS account](/Users/marcomaher/AWS%20Security%20Autopilot/docs/customer-guide/connecting-aws.md)
- [Troubleshooting](/Users/marcomaher/AWS%20Security%20Autopilot/docs/customer-guide/troubleshooting.md)
