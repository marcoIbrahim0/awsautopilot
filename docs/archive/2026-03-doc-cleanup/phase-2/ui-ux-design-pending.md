# Findings UX & Display Plan

## 1. Problem Statement & Goals
Currently, findings—specifically out-of-scope ones—create noise, causing confusion and hiding actionable insights. The goal is to redesign the findings experience focusing on relevance, clear information hierarchy, and obvious action paths.

## 2. Scoping & Filtering
To ensure users are focused only on actionable risk, the application strictly enforces scope boundaries at the data layer:

- **Server-Side Filtering (Zero-Noise Policy)**: The SaaS application only receives findings that are currently **in scope**. Out-of-scope findings are filtered out by the API/query engine and are never transmitted to the frontend payload. There is no "Out of Scope" tab, no ghost rows, and no disabled action buttons for out-of-scope items.
- **Audit Context (Out of SaaS)**: Out-of-scope findings remain preserved and queryable at the backend/engine level for compliance and audit requirements, but this is handled via separate administrative reporting or dedicated audit exports, not within the daily user workspace.
- **Removed Concepts**: As a result of this strict data boundary, the UI does not require "Scope Toggles" or visual opacity treatments for out-of-scope items—they simply do not exist in the user's view.

## 3. Information Hierarchy
Findings must be prioritized so the most critical and actionable items demand immediate attention.

### 3.1 Prioritization (Sort Order)
1. **Severity**: Critical -> High -> Medium -> Low.
2. **Actionability**: "Action Required" floats to the top, followed by "Pending/Processing". 
3. **Recency**: Newest first within severity bands.

### 3.2 Finding Group Card / Table Row (Default View)
The primary unit of interaction is the **Finding Group**, not the individual finding. Findings are intelligently grouped by rule + resource type, affected service, or remediation path.
A group should immediately answer: *What is the issue? How widespread is it? How do I fix it?*
- **Primary Information (High Emphasis)**:
  - **Severity Distribution**: Summary of severities within the group (e.g., 2 Critical, 5 High).
  - **Rule/Issue Type**: e.g., "S3 Buckets Publicly Readable".
  - **Finding Count & Resource Category**: e.g., "7 Findings across 3 S3 Buckets".
- **Secondary Information (Medium Emphasis)**:
  - **Grouped Context**: Common account, region, or service.
- **Actions**:
  - **Generate PR**: A single, prominent button to remediate all findings in the group.

### 3.3 Expanded Group Detail (Secondary View)
Users can expand a Finding Group to view the individual findings within it. This is a secondary action for inspection, not the default entry point.
- Displays individual resource ARNs, specific detection times, and granular context.

## 4. Actionability & User Flow
Every finding group needs a clear resolution path. The system handles the grouping, allowing the user to review and act on multiple findings simultaneously.

- **Primary Action (Expected)**: A prominent, high-contrast button (`Generate PR`) on the Finding Group card. The system automatically bundles all findings within the group for remediation—no manual selection required.
- **Secondary Actions (Optional)**: A dropdown or secondary button group for alternatives:
  - `Suppress Group (30 Days)`
  - `Acknowledge Risk for Group` 
  - `Mark Group as False Positive`
- **Confirmation for Shared Context**: If a group applies to a shared resource (see section 5), clicking the primary action triggers a confirmation dialog warning of the wider blast radius.
- **State Feedback**: Immediately after an action is clicked, the UI should transition to an active state (e.g., "Generating PR..."). Once complete, the finding group moves to a "Pending Change" or "Resolved" state to clear it from the active list.

## 5. Visibility & Discovery
Findings should be surfaced intelligently to minimize friction.

- **Global Dashboard**: A high-level summary showing the **"Actionable Risk Score"** and counts grouped by severity. This score is perfectly aligned with the in-scope items loaded into the SaaS.
- **Dedicated Findings Page**: The detailed tabular view described above, with robust granular filtering (Severity, Service, Account, Resource).
- **Inline Context**: If the platform has visual architecture diagrams or inventory lists, attach warning badges (yellow/red dots) to the affected resources. Clicking the resource opens a side-panel showing ONLY findings associated with that resource.
- **Notifications**: Configure alerting (Slack/Email) to fire **only for In-Scope Critical/High** severities. 

## 6. Shared Context & Scope Dynamics

- **Shared Context Findings (Always Show)**: 
  - *Scenario*: A resource (e.g., a global IAM role) is used by both the current in-scope project and an external/legacy application.
  - *Data Layer*: These findings *are* sent to the frontend payload because they represent a valid risk to an in-scope resource.
  - *UX Pattern*: Surface the finding normally, but append a prominent `Shared Resource` warning badge to the row/card.
  - *Actioning*: Actions remain fully enabled, but attempting remediation prompts a mandatory confirmation dialog: *"Warning: Modifying this resource will affect out-of-scope applications. Proceed?"*
- **Scope Changes Mid-Project**:
  - *Resource leaves scope*: Any open findings associated with that resource drop out of the API payload and dynamically disappear from the UI. Active PRs/Remediations should show a state warning (e.g., "Note: This resource is no longer in scope") if they are tracked separately.
  - *Resource enters scope*: Findings appear in the API payload, triggering a one-time "New Resources in Scope" notification summary rather than individual alerts for each pre-existing finding.

## 7. Finding Type Matrix Mental Model
| Finding Type | Load in SaaS? | Show to User? | Action Enabled? |
| :--- | :--- | :--- | :--- |
| **In-Scope** | Yes | Yes | Yes |
| **Shared Context** | Yes | Yes (Badged) | With confirmation |
| **Out-of-Scope** | No | No | N/A |

## 8. Grouping Configuration
To manage large volumes of findings effectively, the system employs a flexible, multi-dimensional grouping architecture. Users can dynamically organize their findings to match their workflow.

### 8.1 Grouping Dimensions
Users can slice and dice findings using the following core dimensions:
- **Rules**: Group findings that violate the same security rule (e.g., all "Public S3 Buckets").
- **Resources**: Group findings affecting a specific resource or resource classification.
- **Severity**: Group findings by risk tier (Critical, High, Medium, Low).
- **Region**: Group findings by the AWS cloud region where they reside.
- **Status**: Group findings by their current remediation state (e.g., Active, Pending Processing).

### 8.2 Multi-Dimensional Stacking Hierarchy
The grouping engine allows users to apply multiple dimensions simultaneously. When stacked, these dimensions create a nested visual hierarchy in the UI.

- **Stacking Logic**: The order in which dimensions are selected defines the parent-child nesting. 
  - *Example Setup*: `1. Severity` → `2. Region` → `3. Rule`
  - *Resulting UI*: A top-level section for **Critical** vulnerabilities. Inside that section, sub-groups for **us-east-1** and **eu-west-1**. Inside `us-east-1`, the specific finding groups by **Rule** (e.g., "S3 Public Read").
- **Limit**: To prevent UX degradation, stacking should generally be capped at 3 active dimensions.

### 8.3 UX Patterns for the Grouping Selector
The interface for manipulating these groups must feel lightweight but powerful:

- **The Control Bar**: A horizontal bar placed directly above the findings table/list, featuring a visual "Group By" builder.
- **Adding a Group Level**: A `+ Add Grouping` button opens a dropdown of available dimensions. Selecting one adds a token/pill to the control bar.
- **Reordering Levels**: The grouping tokens in the control bar act as drag-and-drop elements. Dragging a token changes its position in the hierarchy, instantly re-rendering the table beneath it.
- **Removing Levels**: Each grouping token features a clear `x` icon to quickly remove that dimension from the stack.
- **Visual Nesting**: The data table utilizes collapsible rows (accordions) or indented sub-tables to represent the nested hierarchy clearly.

### 8.4 Default Configuration
Out of the box, the system provides a highly actionable default grouping state that guides the user toward the most urgent tasks:
1.  **Severity** (Parent Level) – Focuses attention on Criticals and Highs first.
2.  **Rules** (Child/Group Level) – Bundles identical issues together so a single "Generate PR" action can resolve multiple findings at once.
