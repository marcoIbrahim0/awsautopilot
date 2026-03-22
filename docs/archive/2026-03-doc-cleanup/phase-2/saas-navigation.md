# SaaS Navigation Restructure Plan

## 1. Problem Statement
The current application requires excessive context switching. A security operator has to navigate between four distinct pages—**Findings**, **Actions**, **Exceptions**, and **Top Risks**—to complete what is fundamentally a single workflow: responding to and triaging security alerts. 

Additionally, administrative features and global configuration items are mixed into the same navigation hierarchy as daily operator tasks.

## 2. Core Objective
Reduce cognitive overload by restructuring the Information Architecture (IA) into a single, cohesive operations-first flow. We will consolidate overlapping intents and move contextual drill-downs into modals/drawers rather than standalone navigation routes.

---

## 3. Proposed Navigation Hierarchy changes

### A. The "Operations Hub" (Consolidated)
Instead of forcing users to jump between Findings, Actions, and Exceptions, these should be unified into a single primary operations hub.

- **Primary Route:** `/findings` (or `/operations`)
- **UX Update:** This page becomes the central command center.
  - Generative Actions, Suppressions (Exceptions), and Acknowledged Risks are all handled inline or via side-panels directly from the Findings view.
  - Users no longer need to leave the page to "see" their Actions or Exceptions—these become filterable states (e.g., Status: "Pending Action", "Suppressed") within the same grouped findings list.

### B. The "Reporting Hub"
High-level dashboards and summaries are intended for a different mindset (reporting/review vs. triage).

- **Primary Route:** `/top-risks`
- **UX Update:** Kept separate from the daily operations flow. This serves as the entry point for management and high-level prioritization before diving into the Operations Hub.

### C. The "Administration Hub"
Configuration, scoping, and account management are infrequent tasks that should not clutter the primary navigation.

- **Primary Route:** `/settings`
- **UX Update:** Group all utility, account, notification config, and integration setup under this single Settings hub. Use sensible sub-tabs (e.g., Settings > AWS Accounts, Settings > Notifications) to keep the global navigation clean.

---

## 4. Implementation Steps (Frontend)

1. **Delete/Deprecate Standalone Routes:** 
   - Remove or deprecate the standalone `/actions` and `/exceptions` pages from the main sidebar.
2. **Update Sidebar Navigation:**
   - Simplify the AppShell navigation links to point only to the core hubs (Top Risks, Findings, Settings).
3. **Migrate Functionality to Modals/Drawers:**
   - The detailed views currently on the Action page (e.g., viewing PR bundle details) should open in a slide-out drawer or modal directly over the Findings page when a "Generate PR" button is clicked or a grouped finding is selected.
   - The same applies to managing suppressions/exceptions.
4. **State Management:**
   - Ensure the Unified Findings page can query and visibly distinguish findings that are currently "Actionable", "In Remediation", or "Suppressed" using the new Grouping control bar.

---

## 5. Next Steps
Once approved, we will update the `frontend/src/components/site-nav.tsx` (and related AppShell components) to reflect the simplified layout, and begin moving the `Action` and `Exception` details into contextual drawers.
