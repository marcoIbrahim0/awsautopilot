ARCHITECTURE 1 SCENARIO

Name: RapidClaims Telehealth Evidence Pipeline

Business narrative:
RapidClaims is a mid-market workers’ compensation insurer that runs a telehealth evidence platform where partner clinics upload injury photos, PDFs, and nurse notes within minutes of each visit. The platform was built by a six-person Claims Platform team (4 backend engineers, 1 DevOps engineer, 1 product engineer) that owns both feature delivery and AWS operations. The system exists to meet a contractual 24-hour adjudication SLA demanded by employer groups and third-party administrators. After signing several large clinic networks in one quarter, the team prioritized onboarding speed and workflow reliability, and deferred security hardening tasks that did not block launch.

AWS service categories used:
- Compute: runs the intake API, background processing workers, and internal case services that transform uploaded evidence into claim-ready packages.
- Storage: stores raw uploads, processed claim artifacts, and retention-managed archive data for legal and audit needs.
- Networking and Content Delivery: exposes a secure external intake path for clinics and isolates internal processing paths from public traffic.
- Messaging and Integration: decouples upload intake from downstream document processing so claim traffic spikes do not interrupt clinic workflows.
- Database: stores case metadata, processing states, and partner-tenant mappings needed for adjudication timelines.
- Identity and Access Management: enforces service-to-service permissions and tenant-scoped access patterns across ingestion and processing components.
- Management and Observability: centralizes logs, operational telemetry, and deployment visibility for a small on-call team.

Tier structure:
- Tier 1 (External Intake): clinic-facing upload and submission entry components that accept files and claim metadata and hand off work asynchronously.
- Tier 2 (Workflow and Processing): internal application components that validate submissions, enrich case context, and orchestrate evidence processing jobs.
- Tier 3 (Data and Retention): durable data services for object storage, metadata persistence, and policy-driven retention handling.
- Tier 4 (Operations and Access): operational control components for deployment access, runtime telemetry, and environment-level guardrails.
This architecture is intentionally compact at roughly 10-12 interconnected AWS resources across the four tiers.

Why misconfigurations would naturally occur here:
The team reused a pilot-environment infrastructure template to accelerate onboarding and kept broad network and storage defaults in place while they focused on SLA-critical claim throughput. Ownership is split between feature engineers and one shared DevOps engineer, so security settings are often applied inconsistently across new clinic onboarding waves. Several controls are handled by inherited modules and copy-pasted policies, which makes drift and partial configuration states likely during fast releases.

Control coverage plan:
- Architecture 1 covers these 14 controls: S3.1, S3.2, S3.3, S3.4, S3.5, S3.8, S3.9, S3.11, S3.15, S3.17, EC2.53, EC2.13, EC2.18, EC2.19.
- Architecture 2 will cover the remaining 11 controls so no inventory control is unassigned: SecurityHub.1, GuardDuty.1, CloudTrail.1, Config.1, SSM.7, EC2.7, EC2.182, IAM.4, RDS.PUBLIC_ACCESS, RDS.ENCRYPTION, EKS.PUBLIC_ENDPOINT.
