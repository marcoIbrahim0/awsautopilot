import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Terms of Service | Ocypheris Autopilot',
    description: 'Terms of Service governing access to and use of the Ocypheris Autopilot platform.',
};

function Section({ number, title, children }: { number: number; title: string; children: React.ReactNode }) {
    return (
        <section style={{ marginBottom: '2.5rem' }}>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#1f2937', marginBottom: '0.75rem', paddingBottom: '0.4rem', borderBottom: '2px solid #e5e7eb' }}>
                {number}. {title}
            </h2>
            <div style={{ color: '#374151', lineHeight: '1.8', fontSize: '0.97rem' }}>{children}</div>
        </section>
    );
}

function Sub({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div style={{ marginTop: '1rem', marginBottom: '0.5rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#374151', marginBottom: '0.4rem' }}>{title}</h3>
            <div>{children}</div>
        </div>
    );
}

function P({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
    return <p style={{ marginBottom: '0.75rem', ...style }}>{children}</p>;
}

function Ul({ items }: { items: string[] }) {
    return (
        <ul style={{ listStyleType: 'disc', paddingLeft: '1.5rem', marginBottom: '0.75rem' }}>
            {items.map((item, i) => (
                <li key={i} style={{ marginBottom: '0.3rem' }}>{item}</li>
            ))}
        </ul>
    );
}

function Callout({ children }: { children: React.ReactNode }) {
    return (
        <div style={{ background: '#fffbeb', border: '1px solid #f59e0b', borderRadius: '8px', padding: '1rem 1.25rem', marginBottom: '1rem', fontSize: '0.93rem', color: '#92400e' }}>
            <strong style={{ display: 'block', marginBottom: '0.25rem' }}>⚠ Important Notice</strong>
            {children}
        </div>
    );
}

export default function TermsPage() {
    return (
        <div style={{ maxWidth: '820px', margin: '0 auto', padding: '3.5rem 1.5rem 5rem' }}>
            {/* Header */}
            <div style={{ marginBottom: '2.5rem' }}>
                <p style={{ fontSize: '0.78rem', fontWeight: 600, color: '#4f46e5', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '0.5rem' }}>Legal</p>
                <h1 style={{ fontSize: '2.25rem', fontWeight: 800, color: '#111827', marginBottom: '0.5rem', lineHeight: 1.2 }}>Terms of Service</h1>
                <p style={{ fontSize: '0.88rem', color: '#6b7280' }}>Effective Date: December 13, 2025 &nbsp;·&nbsp; Ocypheris</p>
                <div style={{ height: '3px', width: '48px', background: '#4f46e5', borderRadius: '2px', marginTop: '1rem' }} />
            </div>

            <Section number={1} title="Introduction &amp; Acceptance">
                <P>These Terms of Service (&ldquo;Terms&rdquo;) constitute a legally binding agreement between you (the subscriber, &ldquo;Customer,&rdquo; &ldquo;you,&rdquo; or &ldquo;your&rdquo;) and <strong>Ocypheris</strong> (&ldquo;Ocypheris,&rdquo; &ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo;) governing your access to and use of the <strong>Autopilot</strong> platform available at <strong>ocypheris.com</strong> and any related APIs, services, workers, or exported artefacts (collectively, the &ldquo;Services&rdquo;).</P>
                <P>By creating an account, clicking &ldquo;Sign Up,&rdquo; connecting an AWS account, or otherwise accessing the Services, you acknowledge that you have read, understood, and agree to be bound by these Terms and our <a href="/legal/privacy" style={{ color: '#4f46e5' }}>Privacy Policy</a>, which is incorporated herein by reference. If you are entering into these Terms on behalf of an organisation, you represent that you have authority to bind that organisation. If you do not agree to these Terms, do not access or use the Services.</P>
            </Section>

            <Section number={2} title="Definitions">
                <Ul items={[
                    '"Autopilot" means the Ocypheris cloud security SaaS platform that ingests AWS security findings, surfaces prioritised remediation actions, and executes approved remediations.',
                    '"AWS Environment" means the Amazon Web Services account(s), infrastructure, configurations, and resources owned or operated by the Customer that are connected to Autopilot.',
                    '"Read Role" means an AWS IAM role with read-only permissions, deployed by the Customer in their AWS account, which Autopilot uses to ingest security findings.',
                    '"Write Role" means an AWS IAM role with limited write permissions, deployed by the Customer in their AWS account, which Autopilot uses solely to execute direct-fix remediations approved by the Customer.',
                    '"Finding" means a security vulnerability, misconfiguration, or risk signal ingested from AWS Security Hub, Amazon GuardDuty, or IAM Access Analyzer.',
                    '"Action" means a prioritised, deduplicated task derived from one or more Findings and presented to the Customer for review, exception, or remediation.',
                    '"Remediation Run" means an execution event — initiated by an explicit Customer approval — in which Autopilot applies a fix to the Customer\'s AWS Environment via the Write Role, or generates an IaC patch bundle for Customer-managed deployment.',
                    '"IaC Patch Bundle" means a Terraform or CloudFormation template or patch generated by Autopilot and delivered to the Customer for independent review and deployment.',
                    '"Evidence Pack" means a compliance export artefact (findings, exceptions, control mappings, attestations) generated by Autopilot and stored in Amazon S3.',
                    '"Subscription" means the paid plan tier governing the Customer\'s access to the Services as agreed in the applicable order form or subscription agreement.',
                ]} />
            </Section>

            <Section number={3} title="The Services">
                <P>Ocypheris provides the Autopilot platform as a subscription-based SaaS service. The Services include:</P>
                <Ul items={[
                    'AWS account onboarding and IAM role-based integration (Read Role + Write Role)',
                    'Continuous ingestion of security findings from AWS Security Hub, GuardDuty, and IAM Access Analyzer',
                    'Automated action grouping, deduplication, and context-driven prioritisation',
                    'Exception management with configurable expiry and approval workflows',
                    'Hybrid remediation: direct-fix execution (via Write Role, with Customer approval) and IaC patch bundle generation',
                    'Compliance and evidence pack export (CSV, JSON, ZIP)',
                    'Weekly security digest notifications via email and/or Slack',
                    'Baseline security reports',
                ]} />
                <P>Ocypheris reserves the right to modify, enhance, or discontinue features of the Services with reasonable notice to active Customers. We will not materially reduce the core functionality of your subscribed plan without offering a refund for the affected period.</P>
            </Section>

            <Section number={4} title="AWS Access &amp; Customer Authorisation">
                <Sub title="4.1  Granting Access">
                    <P>To use Autopilot, you must deploy a Read Role and a Write Role in your AWS account(s), configured with an ExternalId provided by Ocypheris. By deploying these roles and connecting your account through the Autopilot platform, you explicitly authorise Ocypheris to:</P>
                    <Ul items={[
                        'Assume the Read Role to ingest and analyse security findings from your AWS Environment on an ongoing, automated basis',
                        'Assume the Write Role solely to execute Remediation Runs you have individually approved within the platform',
                    ]} />
                </Sub>
                <Sub title="4.2  No Unauthorised Actions">
                    <P>Ocypheris will not use your Write Role to execute any action that has not been explicitly approved by an authorised user in your Autopilot account. We will not modify, delete, or reconfigure any AWS resource beyond the specific action scope of an approved Remediation Run. Each Remediation Run is logged with full before-and-after state, execution output, and the identity of the approving user.</P>
                </Sub>
                <Sub title="4.3  Credential Security">
                    <P>Ocypheris accesses your AWS Environment exclusively via STS AssumeRole with ExternalId. No long-lived AWS access keys or secret keys are stored by Ocypheris. All temporary credentials are discarded after each job execution. You may revoke access at any time by modifying or deleting the IAM roles in your AWS account.</P>
                </Sub>
                <Sub title="4.4  Customer Representation">
                    <P>By connecting an AWS account you represent and warrant that:</P>
                    <Ul items={[
                        'You are the account owner or have been authorised by the account owner to grant this access',
                        'You have the legal and organisational authority to permit automated security operations on those AWS resources',
                        'The AWS environment you connect is not owned by or shared with any party whose consent you have not obtained',
                    ]} />
                </Sub>
            </Section>

            <Section number={5} title="Automated Remediation — Customer Responsibility">
                <Callout>Autopilot has the ability to make changes to your live AWS environment when you approve a Remediation Run. Please read this section carefully before approving any remediation.</Callout>
                <Sub title="5.1  Approval-Gated Execution">
                    <P>Every Remediation Run requires explicit approval by an authorised user within your Autopilot account. No remediation is executed automatically or without your consent. By approving a Remediation Run, you instruct Ocypheris to execute the described action against your AWS Environment and you assume responsibility for the consequences of that instruction.</P>
                </Sub>
                <Sub title="5.2  Pre-Checks and Logging">
                    <P>Prior to executing a direct-fix remediation, Autopilot performs configurable safety pre-checks and logs the original state of the affected resource. Post-execution verification checks are run where applicable, and a full execution log is retained.</P>
                </Sub>
                <Sub title="5.3  Customer Backup Responsibility">
                    <P><strong>You are solely responsible for maintaining independent backups, snapshots, and disaster recovery plans for your AWS Environment, independent of any Autopilot engagement.</strong> Ocypheris does not create backups of your AWS resources before executing remediations. You should verify that your environment has appropriate recovery mechanisms before approving any Remediation Run.</P>
                </Sub>
                <Sub title="5.4  No Guarantee of Remediation Outcome">
                    <P>While Autopilot implements safety checks and follows AWS best practices, no automated system can guarantee that a remediation action will produce the exact desired outcome in every possible AWS configuration. AWS service behaviour, race conditions, regional dependencies, or custom configurations may produce unexpected results. You should review rollback guidance provided with each action type before approving execution.</P>
                </Sub>
                <Sub title="5.5  IaC Patch Bundles">
                    <P>IaC Patch Bundles are generated templates for Customer-managed deployment. Ocypheris provides these outputs as reference artefacts. The Customer bears sole responsibility for reviewing, testing, and deploying IaC Patch Bundles in their environment.</P>
                </Sub>
            </Section>

            <Section number={6} title="Customer Responsibilities">
                <P>You agree to:</P>
                <Ul items={[
                    'Provide accurate, current, and complete information when registering and throughout the term of your Subscription',
                    'Maintain the security of your Autopilot account credentials and promptly notify us of any suspected unauthorised access',
                    'Ensure that all users accessing your Autopilot account have agreed to these Terms',
                    'Use the Services only for lawful purposes in compliance with all applicable laws and regulations',
                    'Connect only AWS accounts that you own or have explicit authority to manage',
                    'Review and make independent decisions regarding all Findings, Actions, and Remediation Runs presented by Autopilot',
                    'Maintain current contact information so we can notify you of material changes, security events, or service notices',
                ]} />
            </Section>

            <Section number={7} title="Acceptable Use">
                <P>You must not use the Services to:</P>
                <Ul items={[
                    'Connect or scan AWS accounts you do not own or have written, explicit authorisation to manage',
                    'Reverse engineer, decompile, or attempt to extract the source code of any part of the platform',
                    'Attempt to circumvent tenant isolation, access other customers\' data, or exploit platform vulnerabilities',
                    'Use the platform for any purpose that violates applicable law, including data protection, export control, or sanctions law',
                    'Resell, sublicense, or provide access to the Services to any third party without Ocypheris\' prior written consent',
                    'Use automated mechanisms (bots, scrapers) to access the platform in a manner that degrades service for other users',
                ]} />
                <P>Ocypheris reserves the right to suspend or terminate access immediately and without notice if we reasonably believe you are in violation of this section.</P>
            </Section>

            <Section number={8} title="Intellectual Property">
                <Sub title="8.1  Ocypheris IP">
                    <P>The Autopilot platform, including its software, algorithms, action scoring methodology, user interface, documentation, and all underlying technology, is the exclusive intellectual property of Ocypheris and is protected by applicable copyright, trade secret, and intellectual property laws. Nothing in these Terms transfers any ownership of Ocypheris IP to you. You receive a limited, non-exclusive, non-transferable, revocable licence to access and use the Services during your active Subscription solely for your internal business security operations.</P>
                </Sub>
                <Sub title="8.2  Customer Data">
                    <P>You retain all ownership of your AWS Environment data, security findings, and any proprietary business information you bring to the platform. You grant Ocypheris a limited licence to process, store, and use this data solely to provide and improve the Services as described in our Privacy Policy.</P>
                </Sub>
                <Sub title="8.3  Feedback">
                    <P>If you provide suggestions, feedback, or ideas regarding the Services, you grant Ocypheris a perpetual, irrevocable, royalty-free licence to use such feedback for any purpose without restriction or compensation.</P>
                </Sub>
            </Section>

            <Section number={9} title="Subscription, Fees &amp; Payment">
                <Sub title="9.1  Subscription Plans">
                    <P>Access to Autopilot is offered on a subscription basis. Plan tiers, features, and pricing are specified in your applicable order form or subscription agreement entered into with Ocypheris.</P>
                </Sub>
                <Sub title="9.2  Payment">
                    <P>Fees are payable via bank transfer as specified on your invoice. Unless otherwise agreed in writing, invoices are due within <strong>30 days</strong> of the invoice date. All fees are stated exclusive of applicable taxes. You are responsible for all taxes, duties, or levies imposed on the Services by applicable authority.</P>
                </Sub>
                <Sub title="9.3  Late Payment">
                    <P>Unpaid invoices after the due date may accrue interest at 1.5% per month (or the maximum permitted by applicable law, whichever is lower). Ocypheris reserves the right to suspend access to the Services for accounts with overdue balances after 15 days&apos; written notice.</P>
                </Sub>
                <Sub title="9.4  Cancellation &amp; Refunds">
                    <P>You may cancel your Subscription at any time by contacting <a href="mailto:legal@ocypheris.com" style={{ color: '#4f46e5' }}>legal@ocypheris.com</a>. Cancellation takes effect at the end of your current billing period. Fees paid for the current period are non-refundable except where Ocypheris has materially failed to deliver the subscribed Services. Pre-paid fees for future periods will be refunded on a pro-rata basis upon written request.</P>
                </Sub>
            </Section>

            <Section number={10} title="Confidentiality">
                <P>Each party agrees to hold in strict confidence all non-public information disclosed by the other party in connection with the Services (&ldquo;Confidential Information&rdquo;), including security Findings, technical architecture details, pricing, and business information. Neither party shall disclose Confidential Information to any third party without the other&apos;s prior written consent, except as required by law.</P>
                <P>This obligation does not apply to information that: (a) was publicly known at the time of disclosure; (b) becomes publicly known through no breach of these Terms; (c) was independently developed without use of Confidential Information; or (d) is required to be disclosed by law, provided the disclosing party gives prompt written notice where practicable.</P>
                <P>This confidentiality obligation survives termination of the Subscription for a period of <strong>three (3) years</strong>.</P>
            </Section>

            <Section number={11} title="Disclaimer of Warranties">
                <P>TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, THE SERVICES ARE PROVIDED &ldquo;AS IS&rdquo; AND &ldquo;AS AVAILABLE.&rdquo; OCYPHERIS EXPRESSLY DISCLAIMS ALL WARRANTIES, EXPRESS OR IMPLIED, INCLUDING WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT.</P>
                <P>IN PARTICULAR, OCYPHERIS DOES NOT WARRANT THAT: (A) THE SERVICES WILL IDENTIFY ALL SECURITY VULNERABILITIES OR MISCONFIGURATIONS IN YOUR AWS ENVIRONMENT; (B) IMPLEMENTING ANY REMEDIATION ACTION WILL PREVENT ALL SECURITY INCIDENTS; (C) FINDINGS OR RECOMMENDATIONS ARE FREE FROM ERROR; OR (D) THE SERVICES WILL MEET YOUR SPECIFIC REGULATORY OR COMPLIANCE REQUIREMENTS WITHOUT INDEPENDENT ASSESSMENT.</P>
                <P>The Services are a decision-support and execution tool. The Customer retains sole responsibility for final security and compliance decisions.</P>
            </Section>

            <Section number={12} title="Limitation of Liability">
                <P>TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, OCYPHERIS SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS, REVENUE, DATA, BUSINESS, OR GOODWILL, ARISING OUT OF OR IN CONNECTION WITH THE SERVICES OR THESE TERMS, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.</P>
                <P>OCYPHERIS&apos;S TOTAL AGGREGATE LIABILITY TO YOU FOR ALL CLAIMS ARISING OUT OF OR RELATED TO THE SERVICES SHALL NOT EXCEED THE TOTAL FEES ACTUALLY PAID BY YOU TO OCYPHERIS DURING THE <strong>THREE (3) MONTHS</strong> PRECEDING THE EVENT GIVING RISE TO THE CLAIM.</P>
                <P>THIS LIMITATION APPLIES TO ALL CLAIMS, WHETHER BASED IN CONTRACT, TORT (INCLUDING NEGLIGENCE), STRICT LIABILITY, OR ANY OTHER LEGAL THEORY.</P>
            </Section>

            <Section number={13} title="Indemnification">
                <P><strong>By Customer:</strong> You agree to indemnify, defend, and hold harmless Ocypheris and its officers, employees, directors, and contractors from and against any claims, damages, losses, costs, and expenses (including reasonable legal fees) arising out of or related to: (a) your use of the Services in violation of these Terms; (b) your approval and initiation of any Remediation Run; (c) your breach of any representation, warranty, or obligation under these Terms; or (d) your violation of applicable law or third-party rights.</P>
                <P><strong>By Ocypheris:</strong> Ocypheris agrees to indemnify, defend, and hold you harmless from any third-party claims alleging that the Autopilot platform, as provided by Ocypheris, infringes that third party&apos;s intellectual property rights, provided that you promptly notify Ocypheris of such claim, grant Ocypheris sole control of the defence, and cooperate reasonably. This does not apply to claims arising from modifications you make to the platform or your combination of the Services with other products.</P>
            </Section>

            <Section number={14} title="Term &amp; Termination">
                <Sub title="14.1  Term">
                    <P>These Terms are effective from the date you first access the Services and remain in force for the duration of your active Subscription and any renewal periods.</P>
                </Sub>
                <Sub title="14.2  Termination for Cause">
                    <P>Either party may terminate these Terms upon material breach by the other party, if such breach is not cured within <strong>14 days</strong> of written notice specifying the breach. Either party may terminate immediately if the other becomes insolvent or subject to bankruptcy proceedings.</P>
                </Sub>
                <Sub title="14.3  Termination by Ocypheris">
                    <P>Ocypheris may suspend or terminate your access without prior notice if we reasonably determine you are in material violation of Section 7 (Acceptable Use), or if required to do so by applicable law.</P>
                </Sub>
                <Sub title="14.4  Effect of Termination">
                    <P>Upon termination or expiry of your Subscription:</P>
                    <Ul items={[
                        'Your access to the platform will be disabled',
                        'You must immediately revoke all IAM roles granted to Ocypheris in your AWS account',
                        'You will have 30 days to request an export of your data; thereafter, we will delete your data per our Privacy Policy',
                        'All outstanding fees become immediately due and payable',
                        'Sections 6, 8, 10, 11, 12, 13, 14.4, and 15 survive termination',
                    ]} />
                </Sub>
            </Section>

            <Section number={15} title="Governing Law &amp; Disputes">
                <P>These Terms are governed by and construed in accordance with the laws of the <strong>Arab Republic of Egypt</strong>, without regard to its conflict of law principles. Any dispute, controversy, or claim arising out of or relating to these Terms or the Services that cannot be resolved by good-faith negotiation within 30 days shall be finally settled by binding arbitration conducted in Cairo, Egypt, in the English language, under the rules of the Cairo Regional Centre for International Commercial Arbitration (CRCICA). Judgment on the arbitration award may be entered in any court of competent jurisdiction.</P>
                <P>Nothing in this section prevents either party from seeking emergency injunctive or other equitable relief from a court of competent jurisdiction to protect intellectual property rights or prevent imminent irreparable harm pending arbitration.</P>
            </Section>

            <Section number={16} title="Changes to These Terms">
                <P>Ocypheris reserves the right to update these Terms at any time. We will notify you of material changes by email to your registered address and by posting a notice on <strong>ocypheris.com</strong> at least <strong>14 days</strong> before the updated Terms take effect. Your continued use of the Services after the effective date constitutes your acceptance of the updated Terms. If you do not agree, you must stop using the Services and notify us to close your account.</P>
            </Section>

            <Section number={17} title="Miscellaneous">
                <Ul items={[
                    'Entire Agreement: These Terms, together with the Privacy Policy and any applicable order form, constitute the entire agreement between the parties and supersede all prior negotiations, representations, or agreements.',
                    'Severability: If any provision is held invalid or unenforceable, it will be modified to the minimum extent necessary; remaining provisions remain in full force.',
                    'Waiver: Failure to enforce any right or provision does not constitute a waiver of that right or provision.',
                    'Assignment: You may not assign these Terms without our prior written consent. Ocypheris may assign these Terms in connection with a merger, acquisition, or asset sale with notice to you.',
                    'Force Majeure: Neither party shall be liable for failure to perform due to causes beyond their reasonable control, including AWS regional outages, natural disasters, acts of government, or cyber-attacks.',
                    'Notices: All legal notices must be sent to legal@ocypheris.com (for Ocypheris) or to the account email registered in your Autopilot profile (for you).',
                ]} />
            </Section>

            <Section number={18} title="Contact">
                <P>For questions regarding these Terms or your account, contact us at:</P>
                <div style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '1.25rem 1.5rem', marginTop: '0.75rem', lineHeight: '2' }}>
                    <strong>Ocypheris — Legal &amp; Compliance</strong><br />
                    Email: <a href="mailto:legal@ocypheris.com" style={{ color: '#4f46e5' }}>legal@ocypheris.com</a><br />
                    Website: <a href="https://ocypheris.com" style={{ color: '#4f46e5' }} target="_blank" rel="noopener noreferrer">ocypheris.com</a>
                </div>
            </Section>
        </div>
    );
}
