import Link from 'next/link';
import Image from 'next/image';
import {
  FileCheck,
  Linkedin,
  Shield,
  Wrench,
  Zap,
} from 'lucide-react';
import { SiteNav } from '@/components/site-nav';
import { AuroraBackground } from '@/components/ui/aurora-background';
import { CometCard } from '@/components/ui/comet-card';
import { BackgroundImageTexture } from '@/components/ui/bg-image-texture';
import { GlobalScrollTimeline } from '@/components/landing/GlobalScrollTimeline';
import { FlipWords } from '@/components/ui/flip-words';
import { SectionAnimator } from '@/components/landing/SectionAnimator';
import { NoiseBackground } from '@/components/ui/NoiseBackground';
import { ContactPopoverForm } from '@/components/landing/ContactPopoverForm';
import { MaximizeSecurityGrid } from '@/components/landing/MaximizeSecurityGrid';
import { BentoIntroGrid } from '@/components/landing/BentoIntroGrid';
import { PrimaryCTANeumorphic } from '@/components/ui/PrimaryCTANeumorphic';
import { BaselineReportHighlight } from '@/components/landing/BaselineReportHighlight';

const CURRENT_YEAR = new Date().getFullYear();
const PRIMARY_CTA_URL = 'https://calendly.com/maromaher54/30min';
const FOOTER_LINKS = [
  { label: 'Proof', href: '/landing#proof' },
  { label: 'What You Get', href: '/landing#what-you-get' },
  { label: 'From Signal to Action', href: '/landing#how-it-works' },
  { label: 'Outcomes', href: '/landing#autopilot-explained' },
  { label: 'Security', href: '/landing#security-data' },
  { label: 'FAQ', href: '/landing#faq' },
  { label: 'Contact', href: '/landing#contact' },
  { label: 'About', href: '/landing#about' },
];
const FOOTER_SOCIALS = [
  { label: 'LinkedIn', href: 'https://www.linkedin.com/company/111719210/admin/dashboard/', icon: Linkedin },
];
const SECURITY_POINTS = [
  {
    title: 'Access model',
    detail: 'We use STS AssumeRole with External ID and short-lived session credentials.',
  },
  {
    title: 'Credentials handling',
    detail: 'We never store customer AWS access keys or secret keys.',
  },
  {
    title: 'Tenant isolation',
    detail: 'Findings, actions, and exceptions are scoped by tenant_id in the API and data model.',
  },
  {
    title: 'Data residency',
    detail: 'Customer data residency is configurable to match your region and compliance requirements.',
    needsVerification: true,
  },
  {
    title: 'Encryption',
    detail: 'Data is encrypted in transit and at rest across the platform.',
    needsVerification: true,
  },
];
const FAQ_ITEMS = [
  {
    q: 'How fast can we get value?',
    a: 'Most teams connect an account and see prioritized actions in minutes.',
  },
  {
    q: 'Do you change infrastructure automatically?',
    a: 'No. Changes are either explicitly approved direct fixes or reviewed PR bundles.',
  },
  {
    q: 'Does this replace Security Hub or GuardDuty?',
    a: 'No. It operationalizes them by turning findings into a clear, manageable workflow.',
  },
  {
    q: 'What does it cost?',
    a: "Pricing starts at $399/month for a single AWS account. Multi-account and enterprise plans are available — book a walkthrough and we'll scope it together.",
  },
  {
    q: 'Is my data safe?',
    a: 'AWS Security Autopilot uses a read-only IAM role — it never writes to your AWS account without explicit approval. We do not store your AWS credentials. All data is encrypted in transit and at rest. A full data handling overview is available in our Security section.',
  },
  {
    q: 'What happens if AWS Security Autopilot goes offline?',
    a: 'Nothing changes in your AWS account. The product is read-only by default. Remediation actions only execute when you explicitly approve them. Your infrastructure is never touched without your direct action.',
  },
  {
    q: 'How is this different from Wiz, Prowler, or AWS Security Hub?',
    a: 'Security Hub and Prowler find problems. Wiz maps them. AWS Security Autopilot operationalizes them — it takes you from a list of findings to merged pull requests and a signed evidence pack, without your team spending weeks on manual remediation.',
  },
];

export default function LandingPage() {
  return (
    <>
      <SiteNav />
      <main className="min-h-screen bg-[var(--bg)]">
        <div className="dark bg-[var(--bg)]">
          <AuroraBackground className="min-h-[90.75vh]" showRadialGradient dark>
            <div
              className="relative z-10 mx-auto flex min-h-[90.75vh] max-w-5xl flex-col items-center justify-center px-6 py-24 text-center"
            >
              <Image
                src="/logo/ocypheris-logo.svg"
                alt="Ocypheris"
                width={346}
                height={95}
                className="mb-8 h-[7rem] w-auto text-white"
                priority
              />
              <h1 className="mb-2 text-[2.925rem] font-bold tracking-tight text-white sm:text-[4.875rem]">
                <FlipWords
                  words={['Secure Your AWS Environment on Autopilot.']}
                  duration={4500}
                  startDelay={500}
                  className="px-0 text-white"
                />
              </h1>
              <div className="mx-auto mt-6 max-w-2xl text-[1.65rem] leading-snug text-white/90">
                <p>Stop drowning in security alerts.</p>
                <p className="mt-3">
                  Resolve hundreds of cloud security findings instantly. Reduce manual overhead by 90% and achieve compliance faster.
                </p>
              </div>
              <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
                <PrimaryCTANeumorphic href={PRIMARY_CTA_URL} text="Book a 20-minute walkthrough" className="nm-raised-lg" />
                <Link
                  href="#autopilot-explained"
                  className="inline-flex items-center justify-center rounded-lg border border-[var(--border)] bg-transparent px-8 py-3.5 text-[0.95rem] font-semibold text-white transition-all duration-300 hover:border-[var(--accent)] hover:bg-[rgba(10,113,255,0.05)] focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--accent)] nm-raised"
                >
                  See how it works
                </Link>
              </div>
            </div>
          </AuroraBackground>
        </div>

        {/* Professional Glowing Edge SVG Wave Transition */}
        <div className="relative w-full h-32 sm:h-48 overflow-hidden bg-[#dde6f0] pointer-events-none" aria-hidden="true">
          <svg
            className="absolute top-[-1px] left-0 w-full h-full"
            preserveAspectRatio="none"
            viewBox="0 0 1440 320"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="glowGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#040817" stopOpacity="1" />
                <stop offset="100%" stopColor="#dde6f0" stopOpacity="0" />
              </linearGradient>
            </defs>
            {/* Base Dark Wave */}
            <path
              fill="#040817"
              fillOpacity="1"
              d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"
            ></path>
            {/* Layer 1: Soft edge blur */}
            <path
              fill="url(#glowGradient)"
              opacity="0.6"
              transform="translate(0, 15) scale(1, 1.1)"
              d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"
            ></path>
            {/* Layer 2: Softer, wider edge blur */}
            <path
              fill="url(#glowGradient)"
              opacity="0.3"
              transform="translate(0, 30) scale(1, 1.25)"
              d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"
            ></path>
            {/* Layer 3: Widest diffusion glow */}
            <path
              fill="url(#glowGradient)"
              opacity="0.1"
              transform="translate(0, 50) scale(1, 1.4)"
              d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"
            ></path>
          </svg>
        </div>

        {/* Start Light Neumorphic Section */}
        <div className="landing-neumorphic">

          <GlobalScrollTimeline>
            {/* B. Autopilot, Explained (MOVED UP) */}
            <section
              id="autopilot-explained"
              className="relative z-10 border-0 bg-transparent px-6 pt-8 pb-12 sm:pt-12 sm:pb-16"
              aria-labelledby="autopilot-explained-title"
              data-landing-animate
            >
              <div className="mx-auto max-w-[85rem]">
                <div className="inline-block max-w-fit mb-4">
                  <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)]" aria-hidden />
                  <p className="font-mono text-sm uppercase tracking-[0.2em] text-[var(--accent)] mb-3">
                    Introducing AWS Security Autopilot
                  </p>
                  <h2 id="autopilot-explained-title" className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl max-w-3xl" style={{ color: 'var(--nm-text)' }}>
                    The cloud security posture manager that actually <span className="nm-text-accent">fixes things.</span>
                  </h2>
                  <p className="mt-4 text-lg max-w-2xl leading-relaxed" style={{ color: 'var(--nm-text-muted)' }}>
                    Traditional tools drown you in alerts. Autopilot ingests your raw AWS findings, determines the blast radius, and generates the exact infrastructure code needed to secure your environment.
                  </p>
                </div>

                <BentoIntroGrid />
              </div>
            </section>

            {/* Integrations Marquee removed */}

            {/* Maximize Security Sticky Scroll */}
            <section
              id="proof"
              className="relative z-10 border-0 bg-transparent px-6 pt-16 pb-0 sm:pt-24 sm:pb-0"
              aria-labelledby="proof-title"
              data-landing-animate
            >
              <div className="mx-auto max-w-[85rem]">
                <div className="flex flex-col items-start justify-between gap-6 md:flex-row md:items-end md:gap-4">
                  <div className="inline-block max-w-fit">
                    <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)]" aria-hidden />
                    <h2 id="proof-title" className="text-3xl font-bold tracking-tight sm:text-4xl" style={{ color: 'var(--nm-text)' }}>
                      Maximize Security. Minimize <span className="nm-text-accent">Effort.</span>
                    </h2>
                    <p className="mt-3 max-w-3xl text-lg sm:text-xl" style={{ color: 'var(--nm-text-muted)' }}>
                      Transparent permissions, fast time-to-value.
                    </p>
                  </div>
                  <div className="shrink-0 mb-[2px]">
                    <Link
                      href="#how-it-works"
                      className="nm-btn-secondary"
                      style={{ fontSize: '0.875rem', padding: '0.625rem 1.5rem' }}
                    >
                      See how it works
                    </Link>
                  </div>
                </div>

                <MaximizeSecurityGrid />
              </div>
            </section>

            {/* C. Comprehensive Security Services */}
            <section
              id="services"
              className="relative z-10 border-0 bg-transparent px-6 py-16 sm:py-24"
              aria-labelledby="services-title"
              data-landing-animate
            >
              <div className="mx-auto max-w-6xl">
                {/* Section Header */}
                <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)]" aria-hidden />
                <h2 id="services-title" className="text-3xl font-bold tracking-tight sm:text-4xl" style={{ color: 'var(--nm-text)' }}>
                  Comprehensive Security Services
                </h2>
                <p className="mt-3 text-lg sm:text-xl" style={{ color: 'var(--nm-text-muted)' }}>
                  The elite expertise behind the automation. Tailored to your architecture.
                </p>

                {/* Clean Neumorphic Services Cards */}
                <div className="relative mt-12 grid grid-cols-1 gap-8 sm:grid-cols-2">
                  <div className="nm-raised-lg p-10 flex flex-col justify-between">
                    <div>
                      <div className="mb-6 nm-icon-well h-12 w-12 text-[var(--accent)]">
                        <Shield className="h-6 w-6" aria-hidden />
                      </div>
                      <h3 className="mb-3 text-2xl font-bold tracking-tight" style={{ color: 'var(--nm-text)' }}>Manual Security Management</h3>
                      <p className="font-semibold text-sm mb-3" style={{ color: 'var(--nm-accent)' }}>Take Full Control of Your AWS Environment.</p>
                      <p className="text-base leading-relaxed" style={{ color: 'var(--nm-text-muted)' }}>
                        Our elite cloud security architects provide hands-on audits, continuous monitoring, and tailored hardening to ensure every layer of your environment is bulletproof.
                      </p>
                    </div>
                  </div>

                  <div className="nm-raised-lg p-10 flex flex-col justify-between">
                    <div>
                      <div className="mb-6 nm-icon-well h-12 w-12 text-[var(--accent)]">
                        <Wrench className="h-6 w-6" aria-hidden />
                      </div>
                      <h3 className="mb-3 text-2xl font-bold tracking-tight" style={{ color: 'var(--nm-text)' }}>Secure SaaS Deployment</h3>
                      <p className="font-semibold text-sm mb-3" style={{ color: 'var(--nm-accent)' }}>Built Secure from Day One.</p>
                      <p className="text-base leading-relaxed" style={{ color: 'var(--nm-text-muted)' }}>
                        From architecture design to production release, we deploy secure, highly available SaaS products end-to-end—with security baked natively into the CI/CD pipeline.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="mt-12 flex justify-center w-full">
                  <PrimaryCTANeumorphic href={PRIMARY_CTA_URL} text="Book a 20-minute walkthrough" />
                </div>
              </div>
            </section>

            <section
              id="security-data"
              className="relative z-10 px-6 py-16 sm:py-24"
              aria-labelledby="security-data-title"
              data-landing-animate
            >
              <div className="mx-auto max-w-4xl text-center">
                <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)] mx-auto" aria-hidden />
                <h2 id="security-data-title" className="text-3xl font-bold tracking-tight sm:text-4xl" style={{ color: 'var(--nm-text)' }}>
                  Security & Data Handling
                </h2>
                <p className="mt-4 text-lg sm:text-xl" style={{ color: 'var(--nm-text-muted)' }}>
                  Trust is our foundation. Here is exactly how we ensure your environments and data stay completely locked down.
                </p>
              </div>
              <div className="mx-auto mt-12 grid max-w-5xl gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {SECURITY_POINTS.map((point) => (
                  <div key={point.title} className="nm-raised-lg flex h-full w-full flex-col overflow-hidden p-8">
                    <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--nm-text)' }}>{point.title}</h3>
                    {point.needsVerification && (
                      <>
                        {/* VERIFY: this claim needs confirmation before launch */}
                      </>
                    )}
                    <p className="mt-3 text-sm sm:text-base leading-relaxed" style={{ color: 'var(--nm-text-muted)' }}>{point.detail}</p>
                  </div>
                ))}
              </div>
            </section>

            <BaselineReportHighlight />

            <section
              id="faq"
              className="relative z-10 border-0 bg-transparent px-6 py-16 sm:py-24"
              aria-labelledby="faq-title"
              data-landing-animate
            >
              <div className="mx-auto max-w-6xl">
                <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)]" aria-hidden />
                <div className="grid gap-10 lg:grid-cols-[1.1fr_1.4fr] lg:items-start">
                  <div>
                    <h2 id="faq-title" className="text-3xl font-bold tracking-tight sm:text-4xl" style={{ color: 'var(--nm-text)' }}>
                      FAQ
                    </h2>
                  </div>
                  <div className="space-y-4">
                    {FAQ_ITEMS.map((item) => (
                      <details
                        key={item.q}
                        className="group nm-raised-sm p-6 sm:p-7"
                      >
                        <summary className="flex cursor-pointer list-none items-center gap-4 text-left outline-none marker:content-none [&::-webkit-details-marker]:hidden">
                          <span className="nm-icon-well relative flex h-9 w-9 shrink-0 items-center justify-center text-[var(--accent)] transition duration-300 group-open:scale-[1.06]">
                            <span className="absolute h-[2px] w-4 rounded-full bg-[var(--accent)] transition-all duration-300 ease-out group-open:w-[18px]" />
                            <span className="absolute h-4 w-[2px] rounded-full bg-[var(--accent)] transition-all duration-300 ease-out group-open:scale-y-0 group-open:rotate-90" />
                          </span>
                          <span className="text-xl font-semibold transition-colors duration-300 sm:text-2xl" style={{ color: 'var(--nm-text)' }}>
                            {item.q}
                          </span>
                        </summary>
                        <div className="faq-panel">
                          <div className="overflow-hidden">
                            <p className="faq-answer mt-3 text-base sm:text-lg pl-13" style={{ color: 'var(--nm-text-muted)' }}>
                              {item.a}
                            </p>
                          </div>
                        </div>
                      </details>
                    ))}
                  </div>
                </div>
              </div>
            </section>

            <section
              id="team"
              className="relative z-10 border-0 bg-transparent px-6 py-16 sm:py-24"
              aria-labelledby="team-title"
              data-landing-animate
            >
              <div className="mx-auto max-w-6xl">
                <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)]" aria-hidden />
                <h2 id="team-title" className="text-2xl font-semibold tracking-tight sm:text-3xl" style={{ color: 'var(--nm-text)' }}>
                  Built by engineers, for engineers
                </h2>
                <div className="mt-6 flex items-start gap-4">
                  {/* TODO MKT-027: replace with real headshot before launch */}
                  {/* @ts-expect-error MKT-027 requires an alt attribute on this placeholder div */}
                  <div className="h-16 w-16 rounded-full nm-icon-well shrink-0 bg-gray-300" alt="Founder headshot" />
                  <p className="max-w-4xl text-base sm:text-lg" style={{ color: 'var(--nm-text-muted)' }}>
                    AWS Security Autopilot is built by engineers who have helped AWS-first teams prepare for SOC 2
                    audits and wanted a faster path from finding to fix without long consulting cycles.
                  </p>
                </div>
              </div>
            </section>

            {/* Final CTA / Contact */}
            <section
              id="contact"
              className="relative z-10 border-0 bg-transparent px-6 py-16 sm:py-24"
              aria-labelledby="contact-title"
              data-landing-animate
            >
              <div className="mx-auto max-w-6xl">
                <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-start">
                  <div>
                    <div className="mb-4 h-[3px] w-24 rounded-full bg-[var(--accent)]" aria-hidden />
                    <h2 id="contact-title" className="text-3xl font-bold tracking-tight sm:text-4xl" style={{ color: 'var(--nm-text)' }}>
                      See your risk. No commitment.
                    </h2>
                    <p className="mt-2 text-lg" style={{ color: 'var(--nm-text-muted)' }}>
                      Book a 20-minute walkthrough and we&apos;ll show you what AWS Security Autopilot finds in your account.
                    </p>
                    <p className="mt-6" style={{ color: 'var(--nm-text-muted)' }}>
                      Or get started with a 48-hour baseline report — no credit card required.
                      <br />
                      Contact us for custom pricing and immediate beta access.
                    </p>
                    <div className="mt-8 flex flex-wrap items-center gap-4">
                      <PrimaryCTANeumorphic href={PRIMARY_CTA_URL} text="Get Started" />
                      <Link
                        href={PRIMARY_CTA_URL}
                        target="_blank"
                        rel="noreferrer"
                        className="nm-btn-secondary"
                        style={{ padding: '0.625rem 1.5rem', fontSize: '0.875rem' }}
                      >
                        Contact Sales
                      </Link>
                    </div>
                  </div>

                  <div className="space-y-6">
                    <div>
                      <h3 className="text-xl font-semibold" style={{ color: 'var(--nm-text)' }}>Book a call or send a note</h3>
                      <p className="mt-2 text-base" style={{ color: 'var(--nm-text-muted)' }}>
                        Prefer email? Reach us directly at{' '}
                        <Link
                          href="mailto:sales@ocypheris.com"
                          className="font-semibold text-[var(--accent)] transition hover:text-[var(--nm-text)]"
                        >
                          sales@ocypheris.com
                        </Link>
                        .
                      </p>
                      <p className="mt-4 text-sm" style={{ color: 'var(--nm-text-muted)' }}>
                        Share your AWS footprint, compliance needs, and the timelines you&apos;re targeting.
                      </p>
                    </div>

                    <ContactPopoverForm />
                  </div>
                </div>
              </div>
            </section>
          </GlobalScrollTimeline>
        </div>

        {/* Professional Glowing Edge SVG Wave Transition to Footer */}
        <div className="relative w-full h-32 sm:h-48 overflow-hidden bg-[#02040a] pointer-events-none" aria-hidden="true" style={{ marginTop: '-2px' }}>
          <svg
            className="absolute top-0 left-0 w-full h-full"
            preserveAspectRatio="none"
            viewBox="0 0 1440 320"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="footerGlowGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#dde6f0" stopOpacity="1" />
                <stop offset="100%" stopColor="#02040a" stopOpacity="0" />
              </linearGradient>
            </defs>
            {/* Base Light Wave */}
            <path
              fill="#dde6f0"
              fillOpacity="1"
              d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"
            ></path>
            {/* Layer 1: Soft edge blur */}
            <path
              fill="url(#footerGlowGradient)"
              opacity="0.6"
              transform="translate(0, 15) scale(1, 1.1)"
              d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"
            ></path>
            {/* Layer 2: Softer, wider edge blur */}
            <path
              fill="url(#footerGlowGradient)"
              opacity="0.3"
              transform="translate(0, 30) scale(1, 1.25)"
              d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"
            ></path>
            {/* Layer 3: Widest diffusion glow */}
            <path
              fill="url(#footerGlowGradient)"
              opacity="0.1"
              transform="translate(0, 50) scale(1, 1.4)"
              d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,149.3C960,160,1056,160,1152,138.7C1248,117,1344,75,1392,53.3L1440,32L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"
            ></path>
          </svg>
        </div>

        <footer
          className="relative z-10 border-0 bg-transparent"
          style={{
            backgroundImage:
              "linear-gradient(180deg, rgba(2, 4, 10, 0.98) 0%, rgba(2, 4, 10, 0.0) 18%), linear-gradient(180deg, rgba(4, 9, 35, 0.0) 20%, rgba(10, 29, 76, 0.6) 58%, rgba(20, 41, 120, 0.95) 80%, rgba(31, 63, 188, 0.98) 100%), url('/images/footer-gradient.png')",
            backgroundSize: 'cover',
            backgroundPosition: 'center top',
            backgroundBlendMode: 'screen',
          }}
        >
          <div className="mx-auto max-w-6xl px-6 pt-20 pb-14 sm:pt-24 sm:pb-20">
            <div className="flex flex-col items-center text-center">
              <Image
                src="/logo/ocypheris-logo.svg"
                alt="Ocypheris"
                width={220}
                height={60}
                className="h-12 w-auto"
              />

              <div id="about" className="mt-6 max-w-3xl text-center">
                <h3 className="text-lg font-semibold text-white">About Ocypheris</h3>
                <p className="mt-2 text-sm text-white/70 sm:text-base">
                  Ocypheris builds AWS-native security and compliance tooling. Autopilot turns Security Hub and GuardDuty findings into prioritized action, controlled remediation, and audit-ready evidence for teams that need clarity without extra overhead.
                </p>
              </div>
              <nav
                aria-label="Footer"
                className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-3 text-sm font-medium text-white/80"
              >
                {FOOTER_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className="transition hover:text-white"
                  >
                    {link.label}
                  </Link>
                ))}
              </nav>
              <div className="mt-8 flex items-center gap-4">
                {FOOTER_SOCIALS.map(({ label, href, icon: Icon }) => (
                  <Link
                    key={label}
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/15 text-white/70 transition hover:border-white/40 hover:text-white"
                    aria-label={label}
                  >
                    <Icon className="h-5 w-5" aria-hidden />
                  </Link>
                ))}
              </div>
              <p className="mt-8 text-xs text-white/80">
                © {CURRENT_YEAR} Ocypheris. All rights reserved.
              </p>
            </div>
          </div>
        </footer>
        <SectionAnimator />
      </main>
    </>
  );
}
