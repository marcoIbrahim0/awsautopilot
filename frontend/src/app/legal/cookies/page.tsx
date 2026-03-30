import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Cookie Policy | Ocypheris Autopilot',
    description: 'Cookie Policy for Ocypheris Autopilot detailing our use of cookies and local storage.',
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

export default function CookiePolicyPage() {
    return (
        <div style={{ maxWidth: '820px', margin: '0 auto', padding: '3.5rem 1.5rem 5rem' }}>
            {/* Header */}
            <div style={{ marginBottom: '2.5rem' }}>
                <p style={{ fontSize: '0.78rem', fontWeight: 600, color: '#4f46e5', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '0.5rem' }}>Legal</p>
                <h1 style={{ fontSize: '2.25rem', fontWeight: 800, color: '#111827', marginBottom: '0.5rem', lineHeight: 1.2 }}>Cookie Policy</h1>
                <p style={{ fontSize: '0.88rem', color: '#6b7280' }}>Effective Date: December 13, 2025 &nbsp;·&nbsp; Ocypheris</p>
                <div style={{ height: '3px', width: '48px', background: '#4f46e5', borderRadius: '2px', marginTop: '1rem' }} />
            </div>

            <Section number={1} title="Introduction">
                <P>This Cookie Policy explains how Ocypheris (&ldquo;Ocypheris,&rdquo; &ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo;) uses cookies and similar storage technologies when you visit or use our website at <strong>ocypheris.com</strong> and the Autopilot platform (the &ldquo;Services&rdquo;).</P>
                <P>By using our Services, you agree to the use of these technologies as described in this policy. This statement should be read alongside our <a href="/legal/privacy" style={{ color: '#4f46e5' }}>Privacy Policy</a>, which explains how we protect your personal data entirely.</P>
            </Section>

            <Section number={2} title="What Are Cookies and Local Storage?">
                <P><strong>Cookies</strong> are small text files placed on your device by websites you visit. They are widely used to make websites work, improve efficiency, and provide information to the site owners.</P>
                <P><strong>Local Storage (Web Storage)</strong> is an industry-standard technology that allows a website or application to store data locally on your computer or mobile device. Unlike cookies, local storage data is not automatically transmitted to the server with every HTTP request, making it more secure and efficient for storing application state.</P>
            </Section>

            <Section number={3} title="How We Use These Technologies">
                <P>Ocypheris Autopilot is designed as a secure, privacy-first B2B platform. We explicitly use <strong>minimal tracking</strong>. We use cookies and local storage exclusively for essential platform functionality, security, and user preference retention.</P>
                <P>We do <strong>not</strong> use third-party advertising cookies, cross-site trackers, or data-broker pixels.</P>
            </Section>

            <Section number={4} title="Strictly Necessary Technologies">
                <P>These technologies are absolutely essential for the Autopilot platform to function. Because they are strictly necessary, they do not require user consent under GDPR/ePrivacy regulations. You cannot opt out of these while using the authenticated platform.</P>
                <Ul items={[
                    'Authentication Tokens (Local Storage): When you log in, we store a secure JSON Web Token (JWT) in your browser\'s local storage. This verifies your identity to our API and keeps you logged in across page reloads.',
                    'CSRF Tokens (Cookies): Short-lived security cookies used to prevent Cross-Site Request Forgery attacks, ensuring that API requests genuinely originate from your browser.',
                    'Session Routing (Cookies): Infrastructure cookies deployed by our cloud providers (such as Cloudflare or AWS) to ensure your traffic is securely and reliably routed to the correct server instances.'
                ]} />
            </Section>

            <Section number={5} title="Functional Preferences">
                <P>We use local storage to remember your UI choices so you do not have to reconfigure them on every visit. These are strictly functional and do not track your behaviour across the internet.</P>
                <Ul items={[
                    'Theme Preference (Local Storage): Remembers whether you have selected "light" or "dark" mode.',
                    'UI State (Local Storage): Remembers the collapsed/expanded state of your sidebar navigation and data table sorting preferences.'
                ]} />
            </Section>

            <Section number={6} title="Analytics &amp; Performance (Currently Disabled)">
                <P>At this time, Ocypheris does not deploy third-party analytics cookies (e.g., Google Analytics). We rely exclusively on server-side aggregated telemetry (which does not use cookies) to monitor platform health and performance.</P>
                <P>If we introduce first-party or third-party analytics cookies in the future to understand how users interact with the marketing site, we will update this policy and present a consent banner requiring your explicit "opt-in" before such cookies are placed, in accordance with EU/UK law.</P>
            </Section>

            <Section number={7} title="Managing Your Settings">
                <P>You have full control over the data stored in your browser. You can view, manage, and delete cookies and local storage at any time through your browser settings.</P>
                <P>If you choose to block or clear local storage while using the Autopilot platform:</P>
                <Ul items={[
                    'You will be immediately logged out of your active session.',
                    'Your UI preferences (like dark mode) will be reset to defaults.',
                    'You will need to log in again to restore access.'
                ]} />
                <P>To clear your local storage specifically for Autopilot, you can click the "Log Out" button within the platform, which programmatically purges your authentication tokens and session data.</P>
            </Section>

            <Section number={8} title="Changes to This Policy">
                <P>We may update this Cookie Policy periodically to reflect technological changes, new platform features, or regulatory requirements. We will notify you of any material changes by posting the updated policy on our website with a new "Effective Date."</P>
            </Section>

            <Section number={9} title="Contact Us">
                <P>If you have any questions about this Cookie Policy or our data practices, please contact our privacy team:</P>
                <div style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '1.25rem 1.5rem', marginTop: '0.75rem', lineHeight: '2' }}>
                    <strong>Ocypheris — Data Privacy Team</strong><br />
                    Email: <a href="mailto:legal@ocypheris.com" style={{ color: '#4f46e5' }}>legal@ocypheris.com</a><br />
                    Website: <a href="https://ocypheris.com" style={{ color: '#4f46e5' }} target="_blank" rel="noopener noreferrer">ocypheris.com</a>
                </div>
            </Section>
        </div>
    );
}
