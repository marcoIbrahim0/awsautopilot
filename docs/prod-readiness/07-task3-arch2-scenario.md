ARCHITECTURE 2 SCENARIO

Name: RapidRad Teleradiology Exchange Platform

Business narrative:
RapidRad is a regional teleradiology provider that receives imaging studies from urgent-care clinics and returns AI-prioritized radiologist reports within minutes. The platform was built by an 8-person Clinical Platform team (2 platform engineers, 3 integration engineers, and 3 ML engineers) under a 90-day rollout deadline tied to hospital network contracts. They moved from pilot to production quickly to support overnight coverage across multiple states, prioritizing uptime and partner onboarding over security hardening. Ownership sits with the Clinical Platform team, while a small shared SRE function only provides part-time support. The system exists to reduce report turnaround time and avoid lost referral revenue for partner clinics.

AWS service categories used:
- Container orchestration/compute: Runs bursty image-processing and inference workloads with separate long-running and batch execution paths.
- Relational database services: Stores study metadata, routing status, clinician audit references, and operational state that require transactional consistency.
- Object storage services: Holds inbound imaging payloads, derived artifacts, and long-retention archives needed for clinical traceability.
- Networking and edge access services: Provides partner-facing ingestion endpoints and clinician-access paths with controlled ingress between tiers.
- Identity and access management services: Separates automation roles, operator roles, and emergency access patterns across a small team.
- Systems management services: Supports remote operational runbooks and document-based maintenance automation for mixed compute footprints.
- Security/audit governance services: Captures account activity and configuration history needed for healthcare partner audits.

Tier structure:
Tier 1 (Access and ingestion): Partner and clinician entry points receive uploads and requests, then hand off validated jobs to internal processing paths.
Tier 2 (Processing and orchestration): Containerized processing services and automation workers normalize studies, run inference, and coordinate downstream writes.
Tier 3 (Data and retention): Durable storage and relational state back the operational workflow, long-term retention, and lifecycle transitions.
Tier 4 (Governance and administration): Account-level identity, audit, and service-configuration controls govern how the first three tiers are operated and reviewed.
Overall shape is a 4-tier, tightly connected production stack with roughly 11-13 managed resources/components.

Why misconfigurations would naturally occur here:
The team is clinically deadline-driven and spends most cycles on integration reliability and report latency, not infrastructure hardening. Temporary partner access exceptions and emergency operational shortcuts are likely to persist because only a few engineers cover both daytime delivery and overnight incidents. With part-time SRE support, backlog items around encryption defaults, endpoint exposure boundaries, and logging hygiene can remain unresolved across releases.

Control coverage plan:
- Architecture 2 covers these remaining 11 controls: SecurityHub.1, GuardDuty.1, CloudTrail.1, Config.1, SSM.7, EC2.7, EC2.182, IAM.4, RDS.PUBLIC_ACCESS, RDS.ENCRYPTION, EKS.PUBLIC_ENDPOINT.
- Architecture 1 covers the complementary 14 controls so no inventory control is unassigned: S3.1, S3.2, S3.3, S3.4, S3.5, S3.8, S3.9, S3.11, S3.15, S3.17, EC2.53, EC2.13, EC2.18, EC2.19.
