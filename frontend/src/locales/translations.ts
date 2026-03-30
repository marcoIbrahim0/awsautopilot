export const translations = {
  en: {
    nav: {
      logoAlt: 'Ocypheris – Complexity Simplified',
      product: 'Product',
      autopilot: 'Autopilot',
      security: 'Security',
      faq: 'FAQ',
      contact: 'Contact us',
      company: 'Company',
      bookCall: 'Book a call',
      signIn: 'Sign in',
    },
    hero: {
      title: 'Secure Your AWS Environment on Autopilot.',
      subtitle1: 'Stop drowning in security alerts.',
      subtitle2: 'Resolve hundreds of cloud security findings instantly. Reduce manual overhead by 90% and achieve compliance faster.',
      cta: 'Book a 20-minute walkthrough',
    },
    autopilot: {
      label: 'Introducing AWS Security Autopilot',
      title: 'The cloud security posture manager that actually ',
      titleHighlight: 'fixes things.',
      desc: 'Traditional tools drown you in alerts. Autopilot ingests your raw AWS findings, determines the blast radius, and generates the exact infrastructure code needed to secure your environment.',
      cards: {
        signal: {
          title: 'Intelligent Signal Extraction',
          desc: 'Connect to EventBridge and distill thousands of raw, duplicate Security Hub findings into a single, prioritized queue of root-cause vulnerabilities.',
        },
        cures: {
          title: 'Automated Cures',
          desc: 'Stop writing manual patches. AWS Autopilot delivers safe, 1-click direct fixes or ready-to-merge Terraform bundles for critical alerts.',
        },
        compliance: {
          title: 'Provable Compliance',
          desc: 'Every automated remediation creates immutable, board-ready evidence packets seamlessly mapped to your SOC 2 and ISO frameworks.',
        },
      },
    },
    proof: {
      title: 'Maximize Security. Minimize ',
      titleHighlight: 'Effort.',
      desc: 'Transparent permissions, fast time-to-value.',
      features: {
        connect: {
          title: 'Connect Securely in 5 Minutes',
          desc: 'No agents to install. No broad administrative permissions. Just a simple, transparent read-only IAM role that takes exactly 5 minutes for AWS Autopilot to deploy via CloudFormation.',
        },
        visibility: {
          title: 'Instant Visibility',
          desc: 'Why wait up to 24 hours for Security Hub to refresh? AWS Autopilot connects directly into your account\'s state machine via EventBridge routing, identifying new risks the absolute second they are born.',
        },
        control: {
          title: 'Absolute Control',
          desc: 'You maintain total authority over your infrastructure. AWS Autopilot discovery runs strictly in read-only mode, and remediation actions are delivered as verifiable PR bundles so you can approve every single line of code before it ships.',
        },
      },
    },
    services: {
      title: 'Comprehensive Security Services',
      desc: 'The elite expertise behind the automation. Tailored to your architecture.',
      cards: {
        manual: {
          title: 'Manual Security Management',
          subtitle: 'Take Full Control of Your AWS Environment.',
          desc: 'Our elite cloud security architects provide hands-on audits, continuous monitoring, and tailored hardening to ensure every layer of your environment is bulletproof.',
        },
        saas: {
          title: 'Secure SaaS Deployment',
          subtitle: 'Built Secure from Day One.',
          desc: 'From architecture design to production release, we deploy secure, highly available SaaS products end-to-end—with security baked natively into the CI/CD pipeline.',
        },
      },
    },
    security: {
      label: 'Trust is our Foundation',
      title: 'Security & Data Handling',
      desc: 'Every layer of Ocypheris is designed with a "security-first" mindset, ensuring your AWS environment remains locked down and your data stays private.',
      cards: {
        access: {
          title: 'Access Model',
          desc: 'AWS Autopilot utilizes STS:AssumeRole with External ID and short-lived session credentials. This ensures no permanent keys exist and every action is strictly scoped.',
        },
        credentials: {
          title: 'Credentials Handling',
          desc: 'AWS Autopilot never stores customer AWS access keys or secret keys. Our architecture is designed to function entirely on identity-based roles, eliminating the risk of credential leakage.',
        },
        isolation: {
          title: 'Tenant Isolation',
          desc: 'Findings, actions, and exceptions within AWS Autopilot are strictly scoped by tenant_id at the API and data model levels, preventing any cross-account data exposure.',
        },
        residency: {
          title: 'Data Residency',
          desc: 'AWS Autopilot customer data residency is configurable to match your specific regional and compliance requirements.',
        },
        encryption: {
          title: 'Encryption',
          desc: 'AWS Autopilot data is encrypted at rest using AES-256 and in transit via TLS 1.3 across the entire platform architecture.',
        },
      },
      cta: 'Explore our Security whitepaper',
    },
    baseline: {
      title: 'Continuous Compliance Reporting',
      desc: 'Stop scrambling before an audit. Autopilot continuously generates board-ready baselines and immutable evidence packs proving your security posture.',
      card: {
        title: '48-Hour Baseline Analysis',
        features: {
          clock: { title: 'Real-time Snapshots', desc: 'AWS Autopilot enables continuous tracking of infrastructure state across all connected accounts.' },
          check: { title: 'Framework Mapping', desc: 'AWS Autopilot findings are mapped automatically against SOC 2, ISO 27001, and CIS benchmarks.' },
          file: { title: 'Machine-Readable Artifacts', desc: 'AWS Autopilot allows you to export raw JSON payloads or formatted CSVs for your GRC tooling.' },
        },
      },
    },
    faq: {
      title: 'Questions about Ocypheris?',
      desc: 'We\'ve compiled answers to the most common questions on security, pricing, auto-remediation, and integration.',
      cta: 'Read the FAQs',
    },
    team: {
      title: 'Built by engineers, for engineers',
      desc: 'AWS Security Autopilot is built by engineers who have helped AWS-first teams prepare for SOC 2 audits and wanted a faster path from finding to fix without long consulting cycles.',
    },
    contact: {
      title: 'See your risk. No commitment.',
      desc1: 'Book a 20-minute walkthrough and we\'ll show you what AWS Security Autopilot finds in your account.',
      desc2: 'Or get started with a 48-hour baseline report — no credit card required.',
      desc3: 'Contact us for custom pricing and immediate beta access.',
      cta1: 'Get Started',
      cta2: 'Contact Sales',
      side: {
        title: 'Book a call or send a note',
        desc1: 'Prefer email? Reach us directly at ',
        desc2: 'Share your AWS footprint, compliance needs, and the timelines you\'re targeting.',
      },
    },
    footer: {
      about: {
        title: 'About Ocypheris',
        desc: 'Ocypheris builds AWS-native security and compliance tooling. Autopilot turns Security Hub and GuardDuty findings into prioritized action, controlled remediation, and audit-ready evidence for teams that need clarity without extra overhead.',
      },
      copyright: 'Ocypheris. All rights reserved.',
    },
    about: {
      hero: {
        label: 'The Ocypheris Story',
        title: 'Complexity Simplified',
        desc: "We're engineers who spent too many nights triaging thousands of duplicate AWS alerts. We built AWS Security Autopilot to fix the root cause instead of just drawing graphs of the blast radius.",
      },
      mission: {
        title: 'Our Mission',
        desc1: 'Security teams are drowning in noise. Traditional Cloud Security Posture Management (CSPM) tools like Security Hub or GuardDuty are fantastic at finding problems, but they dump the burden of fixing those problems back onto understaffed engineering teams.',
        desc2: 'Ocypheris bridges the gap between identifying a vulnerability and actually remediating it. By turning raw, duplicate findings into a single, prioritized queue of deterministic, 1-click fixes—complete with verifiable SOC 2 and ISO evidence packs—we give security teams their time back.',
      },
      cards: {
        safety: {
          title: 'Uncompromising Safety',
          desc: 'We operate exclusively via identity-based roles. We never store long-lived credentials. Every automated action is rigorously gated, actively checks for blast radius preconditions, and requires manual, explicit human approval before deploying.',
        },
        action: {
          title: 'Action Over Alerts',
          desc: "We don't sell dashboards of red dots. Autopilot isn't just an aggregator—it's an execution engine. We prioritize concrete fixes, like mutating an open S3 bucket policy or generating a secure ready-to-merge Terraform pull request over generating more noise.",
        },
      },
      cta: 'Contact the Team',
    },
    faqPage: {
      hero: {
        label: 'Ocypheris Support',
        title: 'Frequently Asked Questions',
        desc: 'Everything you need to know about AWS Security Autopilot.',
      },
      items: {
        q1: 'How fast can we get value?',
        a1: 'Most teams connect an account and see prioritized actions in minutes.',
        q2: 'Do you change infrastructure automatically?',
        a2: 'No. Changes are either explicitly approved direct fixes or reviewed PR bundles.',
        q3: 'Does this replace Security Hub or GuardDuty?',
        a3: 'No. It operationalizes them by turning findings into a clear, manageable workflow.',
        q4: 'What does it cost?',
        a4: "Pricing starts at $399/month for a single AWS account. Multi-account and enterprise plans are available — book a walkthrough and we'll scope it together.",
        q5: 'Is my data safe?',
        a5: 'AWS Security Autopilot uses a read-only IAM role — it never writes to your AWS account without explicit approval. We do not store your AWS credentials. All data is encrypted in transit and at rest. A full data handling overview is available in our Security section.',
        q6: 'What happens if AWS Security Autopilot goes offline?',
        a6: 'Nothing changes in your AWS account. The product is read-only by default. Remediation actions only execute when you explicitly approve them. Your infrastructure is never touched without your direct action.',
        q7: 'How is this different from Wiz, Prowler, or AWS Security Hub?',
        a7: 'Security Hub and Prowler find problems. Wiz maps them. AWS Security Autopilot operationalizes them — it takes you from a list of findings to merged pull requests and a signed evidence pack, without your team spending weeks on manual remediation.',
      },
      contact: {
        desc: 'Still have questions? Reach out to us at ',
        cta: 'Get In Touch',
      },
    },
    securityPage: {
      hero: {
        label: 'Ocypheris Trust Center',
        title: 'Security Whitepaper',
        desc: 'How we secure your AWS environment with Autopilot — without compromising your data or credentials.',
      },
      exec: {
        title: 'Executive Summary',
        desc: 'Ocypheris (AWS Security Autopilot) operates on a security-first, least-privilege paradigm. We operationalize native AWS security tooling by translating findings into prioritized queues and actionable remediations entirely via identity-based access. Our architecture ensures customer environments remain siloed, credentials are never stored, and every remediation requires explicit customer approval.',
      },
      cards: {
        access: {
          title: 'Access Model',
          desc: 'We utilize STS:AssumeRole with an External ID and short-lived session credentials. We enforce strict separation of duties, requiring a ReadRole for data ingestion and a separate WriteRole scoped exclusively to safe remediation actions.',
        },
        zero: {
          title: 'Zero Credential Storage Policy',
          desc: 'Ocypheris never stores AWS Access Key IDs or Secret Access Keys. All operations function entirely on identity-based roles, eliminating the risk of long-lived credential leakage.',
        },
        isolation: {
          title: 'Tenant Isolation',
          desc: 'Findings, actions, and exceptions are strictly scoped by tenant_id. This isolation is enforced at both the API routing layer and the database layer, preventing any cross-account data exposure.',
        },
        encryption: {
          title: 'Encryption & Residency',
          desc: 'Data is encrypted at rest using AES-256 (RDS and S3) and in transit via TLS 1.3 across the entire platform. Customer data residency is configurable to match regional and compliance frameworks.',
        },
        controls: {
          title: 'Remediation Safety Controls',
          desc: 'No infrastructure changes occur without explicit customer approval. Ocypheris executes pre-flight checks, gates remediation behind human review, and provides rollback capabilities for all supported direct fixes.',
        },
        iam: {
          title: 'Least Privilege IAM',
          desc: 'Our IAM policies are strictly maintained without wildcards. The WriteRole is scoped exclusively to safe, idempotent automated remediation actions, ensuring unauthorized modifications are impossible.',
        },
      },
      audit: {
        title: 'Audit Trail & Compliance Posture',
        desc1: 'Every action, exception, and remediation payload is immutably logged. Customers can generate SOC 2 and ISO 27001 readiness evidence packs on demand, mapping specific active configurations to framework requirements. Ocypheris itself operates with a continuous compliance posture ensuring security of our own internal systems.',
        desc2: 'Vulnerability scanning is integrated into our CI/CD pipelines, and we maintain a 24/7 incident response protocol to address emerging threats rapidly.',
      },
      cta: 'Back to Product Security',
    },
    contactPopover: {
      trigger: {
        title: 'Tell us what you have got in mind.',
        label: 'Direct Email',
      },
      desc: 'Or email us directly at ',
      form: {
        message: 'How can we help?',
        name: 'Full name',
        email: 'Work email',
        company: 'Company',
        phone: 'Phone (optional)',
      },
    },
    deepSurface: {
      background: 'SECURE BY DESIGN',
      screen1: {
        title: 'Secure by ',
        highlight: 'Design',
        desc: 'Beyond our automated tooling, we design, implement, and deploy inherently secure SaaS products and cloud architectures tailored exactly to your business needs.',
        cta: 'Book a Consultation',
      },
      screen2: {
        title: 'The Build Sequence',
        subtitle: 'Secure SaaS Deployment Pipeline',
        step1: { title: 'Design', desc: 'Secure Architecture' },
        step2: { title: 'Build', desc: 'Hardened CI/CD' },
        step3: { title: 'Release', desc: 'Verified Deployment' },
      },
      screen3: {
        title: 'Ready to build your {br}Secure Foundation?',
        desc: 'Experience the peace of mind of architectural security. Our engineers are ready to scope, design, and deliver your next secure release.',
        cta: 'Book a 20-min walkthrough',
        badges: {
          soc2: 'SOC2 COMPLIANT',
          iso: 'ISO 27001',
          saas: 'SaaS FIRST',
        },
      },
    },
  },
  de: {
    nav: {
      logoAlt: 'Ocypheris – Komplexität vereinfacht',
      product: 'Produkt',
      autopilot: 'Autopilot',
      security: 'Sicherheit',
      faq: 'FAQ',
      contact: 'Kontakt',
      company: 'Unternehmen',
      bookCall: 'Termin buchen',
      signIn: 'Anmelden',
    },
    hero: {
      title: 'Sichern Sie Ihre AWS-Umgebung im Autopilot-Modus.',
      subtitle1: 'Hören Sie auf, in Sicherheitswarnungen zu ertrinken.',
      subtitle2: 'Beheben Sie hunderte Cloud-Sicherheitsbefunde sofort. Reduzieren Sie manuellen Aufwand um 90 % und erreichen Sie Compliance deutlich schneller.',
      cta: '20-minütige Produktdemo buchen',
    },
    autopilot: {
      label: 'Introducing AWS Security Autopilot',
      title: 'Der Cloud Security Posture Manager, der tatsächlich ',
      titleHighlight: 'Probleme behebt.',
      desc: 'Traditionelle Tools überfluten Sie mit Warnmeldungen. Autopilot verarbeitet Ihre rohen AWS-Befunde, bestimmt den potenziellen Impact („Blast Radius“) und generiert den exakten Infrastruktur-Code, der benötigt wird, um Ihre Umgebung zu sichern.',
      cards: {
        signal: {
          title: 'Intelligente Signalextraktion',
          desc: 'Verbinden Sie sich mit EventBridge und verdichten Sie tausende rohe und doppelte Security Hub Findings zu einer einzigen priorisierten Warteschlange von Root-Cause-Schwachstellen.',
        },
        cures: {
          title: 'Automatisierte Behebung',
          desc: 'Schreiben Sie keine manuellen Patches mehr. AWS Autopilot liefert sichere 1-Klick-Fixes oder merge-bereite Terraform-Bundles für kritische Warnungen.',
        },
        compliance: {
          title: 'Nachweisbare Compliance',
          desc: 'Jede automatisierte Behebung erzeugt unveränderliche, auditfähige Nachweispakete, die automatisch Ihren SOC 2- und ISO-Frameworks zugeordnet werden.',
        },
      },
    },
    proof: {
      title: 'Maximale Sicherheit. Minimaler ',
      titleHighlight: 'Aufwand.',
      desc: 'Transparente Berechtigungen. Schneller Mehrwert.',
      features: {
        connect: {
          title: 'Sichere Verbindung in 5 Minuten',
          desc: 'Keine Agenten zu installieren. Keine weitreichenden Administratorrechte. Nur eine einfache, transparente Read-Only IAM-Rolle, die in exakt 5 Minuten für AWS Autopilot per CloudFormation bereitgestellt werden kann.',
        },
        visibility: {
          title: 'Sofortige Transparenz',
          desc: 'Warum bis zu 24 Stunden warten, bis Security Hub aktualisiert wird? AWS Autopilot verbindet sich direkt mit der State Machine Ihres Accounts über EventBridge routing, um neue Risiken im Moment ihres Entstehens zu erkennen.',
        },
        control: {
          title: 'Volle Kontrolle',
          desc: 'Sie behalten jederzeit die vollständige Kontrolle über Ihre Infrastruktur. Die AWS Autopilot-Analyse läuft strikt im Read-Only-Modus, und Behebungsmaßnahmen werden als verifizierbare Pull-Request-Bundles bereitgestellt, sodass Sie jede einzelne Codezeile freigeben können.',
        },
      },
    },
    services: {
      title: 'Umfassende Sicherheitsservices',
      desc: 'Die Elite-Expertise hinter der Automatisierung – zugeschnitten auf Ihre Architektur.',
      cards: {
        manual: {
          title: 'Manuelles Sicherheitsmanagement',
          subtitle: 'Volle Kontrolle über Ihre AWS-Umgebung',
          desc: 'Unsere Cloud-Security-Architekten bieten praktische Audits, kontinuierliches Monitoring und maßgeschneiderte Härtung, um jede Ebene Ihrer Umgebung abzusichern.',
        },
        saas: {
          title: 'Sicheres SaaS-Deployment',
          subtitle: 'Von Tag eins an sicher.',
          desc: 'Vom Architekturdesign bis zum Produktions-Release implementieren wir sichere, hochverfügbare SaaS-Produkte End-to-End – mit nativer Sicherheit in der CI/CD-Pipeline.',
        },
      },
    },
    security: {
      label: 'Vertrauen ist unser Fundament',
      title: 'Sicherheit & Datenverarbeitung',
      desc: 'Jede Schicht von Ocypheris basiert auf einem „Security-First“-Ansatz, der sicherstellt, dass Ihre AWS-Umgebung geschützt und Ihre Daten absolut privat bleiben.',
      cards: {
        access: {
          title: 'Zugriffsmodell',
          desc: 'AWS Autopilot verwendet STS:AssumeRole mit External ID und kurzlebigen Sitzungsdaten. So existieren keine permanenten Schlüssel und jede Aktion ist strikt begrenzt.',
        },
        credentials: {
          title: 'Umgang mit Zugangsdaten',
          desc: 'AWS Autopilot speichert niemals AWS Access Keys oder Secret Keys unserer Kunden. Unsere Architektur basiert vollständig auf identitätsbasierten Rollen.',
        },
        isolation: {
          title: 'Mandantentrennung (Tenant Isolation)',
          desc: 'Findings, Aktionen und Ausnahmen in AWS Autopilot sind auf API- und Datenebene streng nach tenant_id getrennt, was kontoübergreifende Datenexposition verhindert.',
        },
        residency: {
          title: 'Datenresidenz',
          desc: 'Die Datenresidenz für AWS Autopilot-Kunden ist anpassbar, um Ihren spezifischen regionalen und Compliance-Anforderungen gerecht zu werden.',
        },
        encryption: {
          title: 'Verschlüsselung',
          desc: 'AWS Autopilot-Daten werden im Ruhezustand (AES-256) und bei der Übertragung (TLS 1.3) über die gesamte Plattformarchitektur hinweg verschlüsselt.',
        },
      },
      cta: 'Unser Security-Whitepaper ansehen',
    },
    baseline: {
      title: 'Kontinuierliche Compliance-Berichterstattung',
      desc: 'Keine Panik mehr vor Audits. Autopilot erstellt kontinuierlich auditfähige Baselines und unveränderliche Nachweispakete, die Ihre Sicherheitslage belegen.',
      card: {
        title: '48-Stunden-Baseline-Analyse',
        features: {
          clock: { title: 'Echtzeit-Snapshots', desc: 'AWS Autopilot ermöglicht kontinuierliches Tracking des Infrastrukturzustands über alle verbundenen Accounts hinweg.' },
          check: { title: 'Framework-Mapping', desc: 'AWS Autopilot-Findings werden automatisch SOC 2, ISO 27001 und CIS-Benchmarks zugeordnet.' },
          file: { title: 'Maschinenlesbare Artefakte', desc: 'AWS Autopilot erlaubt es Ihnen, rohe JSON-Payloads oder formatierte CSV-Dateien für Ihre GRC-Tools zu exportieren.' },
        },
      },
    },
    faq: {
      title: 'Fragen zu Ocypheris?',
      desc: 'Wir haben Antworten auf die häufigsten Fragen zu Sicherheit, Preisen, automatischer Behebung und Integrationen zusammengestellt.',
      cta: 'FAQs lesen',
    },
    team: {
      title: 'Entwickelt von Engineers für Engineers',
      desc: 'AWS Security Autopilot wurde von Ingenieuren entwickelt, die AWS-orientierten Teams bei SOC 2-Audits geholfen haben und einen schnelleren Weg vom Finding zur Behebung schaffen wollten – ohne langwierige Beratungsprojekte.',
    },
    contact: {
      title: 'Sehen Sie Ihr Risiko. Ohne Verpflichtung.',
      desc1: 'Buchen Sie eine 20-minütige Demo, und wir zeigen Ihnen, welche Risiken AWS Security Autopilot in Ihrem Account findet.',
      desc2: 'Oder starten Sie mit einem 48-Stunden-Baseline-Report – ohne Kreditkarte.',
      desc3: 'Kontaktieren Sie uns für individuelle Preise und sofortigen Beta-Zugang.',
      cta1: 'Loslegen',
      cta2: 'Sales kontaktieren',
      side: {
        title: 'Termin buchen oder Nachricht senden',
        desc1: 'Bevorzugen Sie E-Mail? Kontaktieren Sie uns direkt unter ',
        desc2: 'Teilen Sie uns Ihren AWS-Footprint, Ihre Compliance-Anforderungen und Ihre Zeitplanung mit.',
      },
    },
    footer: {
      about: {
        title: 'Über Ocypheris',
        desc: 'Ocypheris entwickelt AWS-native Sicherheits- und Compliance-Tools. Autopilot verwandelt Security Hub- und GuardDuty-Findings in priorisierte Maßnahmen, kontrollierte Behebungen und auditfähige Nachweise – für Teams, die Klarheit ohne zusätzlichen Aufwand benötigen.',
      },
      copyright: 'Ocypheris. Alle Rechte vorbehalten.',
    },
    about: {
      hero: {
        label: 'Die Ocypheris Story',
        title: 'Komplexität vereinfacht',
        desc: "Wir sind Ingenieure, die zu viele Nächte damit verbracht haben, tausende von doppelten AWS-Warnungen zu sichten. Wir haben den AWS Security Autopilot entwickelt, um die eigentliche Ursache zu beheben, anstatt nur Diagramme des 'Blast Radius' zu zeichnen.",
      },
      mission: {
        title: 'Unsere Mission',
        desc1: 'Sicherheitsteams ertrinken im Lärm. Klassische Cloud Security Posture Management (CSPM) Tools wie Security Hub oder GuardDuty eignen sich hervorragend zum Finden von Problemen, aber sie übertragen die Last der Behebung wieder auf unterbesetzte Entwicklungsteams.',
        desc2: 'Ocypheris schließt die Lücke zwischen der Erkennung einer Schwachstelle und deren tatsächlicher Behebung. Indem wir rohe, doppelte Findings in eine einzige priorisierte Warteschlange deterministischer 1-Click-Fixes umwandeln – inklusive nachweisbarer SOC 2 und ISO Evidence-Packs –, geben wir Sicherheitsteams ihre Zeit zurück.',
      },
      cards: {
        safety: {
          title: 'Kompromisslose Sicherheit',
          desc: 'Wir operieren ausschließlich über identitätsbasierte Rollen. Wir speichern niemals langlebige Anmeldedaten. Jede automatisierte Aktion ist strengstens abgesichert, prüft aktiv auf „Blast Radius“-Vorbedingungen und erfordert vor der Ausführung eine manuelle, ausdrückliche menschliche Freigabe.',
        },
        action: {
          title: 'Aktion statt Warnungen',
          desc: "Wir verkaufen keine Dashboards mit roten Punkten. Autopilot ist nicht nur ein Aggregator – es ist eine Ausführungs-Engine. Wir priorisieren konkrete Fixes, wie das Ändern einer offenen S3-Bucket-Richtlinie oder das Generieren eines sicheren, merge-bereiten Terraform Pull Requests, anstatt weiteren Lärm zu erzeugen.",
        },
      },
      cta: 'Team kontaktieren',
    },
    faqPage: {
      hero: {
        label: 'Ocypheris Support',
        title: 'Häufig gestellte Fragen (FAQ)',
        desc: 'Alles, was Sie über AWS Security Autopilot wissen müssen.',
      },
      items: {
        q1: 'Wie schnell sehen wir Ergebnisse?',
        a1: 'Die meisten Teams binden einen Account an und sehen priorisierte Maßnahmen in wenigen Minuten.',
        q2: 'Ändern Sie die Infrastruktur automatisch?',
        a2: 'Nein. Änderungen erfolgen entweder über explizit genehmigte Direct Fixes oder überprüfte PR-Bundles.',
        q3: 'Ersetzt dies Security Hub oder GuardDuty?',
        a3: 'Nein. Es operationalisiert diese Tools, indem es Findings in einen klaren, handhabbaren Workflow übersetzt.',
        q4: 'Was kostet das?',
        a4: 'Die Preise beginnen bei 399 $/Monat für einen einzelnen AWS-Account. Multi-Account- und Enterprise-Pläne sind verfügbar — buchen Sie eine Demo und wir ermitteln den Umfang gemeinsam.',
        q5: 'Sind meine Daten sicher?',
        a5: 'AWS Security Autopilot nutzt eine Read-Only IAM-Rolle — es schreibt niemals ohne ausdrückliche Genehmigung in Ihren AWS-Account. Wir speichern Ihre AWS-Zugangsdaten nicht. Alle Daten sind bei der Übertragung und im Ruhezustand verschlüsselt. Eine vollständige Übersicht zur Datenverarbeitung finden Sie im Bereich Security.',
        q6: 'Was passiert, wenn AWS Security Autopilot offline geht?',
        a6: 'In Ihrem AWS-Account ändert sich nichts. Das Produkt ist standardmäßig im Read-Only-Modus. Behebungsmaßnahmen werden nur ausgeführt, wenn Sie diese ausdrücklich genehmigen. Ihre Infrastruktur wird nie ohne Ihre direkte Aktion berührt.',
        q7: 'Wie unterscheidet sich das von Wiz, Prowler oder AWS Security Hub?',
        a7: 'Security Hub und Prowler finden Probleme. Wiz stellt sie dar. AWS Security Autopilot operationalisiert sie — es führt Sie von einer Liste von Findings zu gemergten Pull-Requests und einem signierten Evidence-Pack, ohne dass Ihr Team Wochen für manuelle Fehlerbehebungen aufwenden muss.',
      },
      contact: {
        desc: 'Noch Fragen? Kontaktieren Sie uns unter ',
        cta: 'Kontakt aufnehmen',
      },
    },
    securityPage: {
      hero: {
        label: 'Ocypheris Trust Center',
        title: 'Security Whitepaper',
        desc: 'So sichern wir Ihre AWS-Umgebung mit Autopilot – ohne Ihre Daten oder Zugangsdaten zu gefährden.',
      },
      exec: {
        title: 'Executive Summary',
        desc: 'Ocypheris (AWS Security Autopilot) folgt einem "Security-First, Least-Privilege"-Ansatz. Wir operationalisieren native AWS-Sicherheitstools, indem wir Findings in priorisierte Maßnahmen und umsetzbare Fehlerbehebungen verwandeln – vollständig über identitätsbasierten Zugriff. Unsere Architektur stellt sicher, dass Kundenumgebungen abgeschottet bleiben, Zugangsdaten niemals gespeichert werden und jede Fehlerbehebung die ausdrückliche Genehmigung des Kunden erfordert.',
      },
      cards: {
        access: {
          title: 'Zugriffsmodell',
          desc: 'Wir verwenden STS:AssumeRole mit einer External ID und kurzlebigen Sitzungsdaten. Wir erzwingen eine strikte Aufgabentrennung, indem wir eine ReadRole für die Datenerfassung und eine separate WriteRole verlangen, die ausschließlich auf sichere Behebungsmaßnahmen beschränkt ist.',
        },
        zero: {
          title: 'Zero Credential Storage Policy',
          desc: 'Ocypheris speichert niemals AWS Access Key IDs oder Secret Access Keys. Alle Operationen basieren vollständig auf identitätsbasierten Rollen, was das Risiko des Verlusts langlebiger Zugangsdaten eliminiert.',
        },
        isolation: {
          title: 'Mandantentrennung (Tenant Isolation)',
          desc: 'Findings, Aktionen und Ausnahmen sind strikt nach tenant_id getrennt. Diese Isolation wird sowohl auf der API-Routing- als auch auf der Datenbank-Ebene durchgesetzt und verhindert jegliche kontoübergreifende Datenexposition.',
        },
        encryption: {
          title: 'Verschlüsselung & Residenz',
          desc: 'Daten werden im Ruhezustand mit AES-256 (RDS und S3) und bei der Übertragung via TLS 1.3 über die gesamte Plattform hinweg verschlüsselt. Die Datenresidenz der Kunden ist anpassbar, um regionalen und Compliance-bezogenen Rahmenbedingungen zu entsprechen.',
        },
        controls: {
          title: 'Sicherheitskontrollen bei der Behebung',
          desc: 'Keine Infrastrukturänderungen erfolgen ohne ausdrückliche Freigabe des Kunden. Ocypheris führt Pre-Flight-Checks durch, sichert Behebungen durch menschliche Überprüfung (Human Review) ab und bietet Rollback-Funktionen für alle unterstützten Direct Fixes.',
        },
        iam: {
          title: 'Least Privilege IAM',
          desc: 'Unsere IAM-Richtlinien werden strikt ohne Wildcards (Platzhalter) verwaltet. Die WriteRole ist ausschließlich auf sichere, idempotente automatisierte Behebungsmaßnahmen beschränkt, wodurch unbefugte Änderungen unmöglich gemacht werden.',
        },
      },
      audit: {
        title: 'Audit-Trail & Compliance-Status',
        desc1: 'Jede Aktion, Ausnahme und Behebungs-Payload wird unveränderlich protokolliert. Kunden können auf Abruf Nachweispakete (Evidence Packs) für SOC 2 und ISO 27001 generieren, die spezifische aktive Konfigurationen den Anforderungen der Frameworks zuordnen. Ocypheris selbst arbeitet mit einem kontinuierlichen Compliance-Status, der die Sicherheit unserer eigenen internen Systeme gewährleistet.',
        desc2: 'Schwachstellen-Scans sind in unsere CI/CD-Pipelines integriert, und wir unterhalten ein 24/7 Incident-Response-Protokoll, um aufkommende Bedrohungen schnell zu adressieren.',
      },
      cta: 'Zurück zur Produktsicherheit',
    },
    contactPopover: {
      trigger: {
        title: 'Teilen Sie uns mit, an was Sie denken.',
        label: 'Direkte E-Mail',
      },
      desc: 'Oder senden Sie uns direkt eine E-Mail an ',
      form: {
        message: 'Wie können wir helfen?',
        name: 'Vollständiger Name',
        email: 'Geschäftliche E-Mail',
        company: 'Unternehmen',
        phone: 'Telefon (optional)',
      },
    },
    deepSurface: {
      background: 'SICHERHEIT DURCH DESIGN',
      screen1: {
        title: 'Sicher durch ',
        highlight: 'Design',
        desc: 'Über unsere automatisierten Tools hinaus entwerfen, implementieren und implementieren wir von Grund auf sichere SaaS-Produkte und Cloud-Architekturen, die exakt auf Ihre Geschäftsanforderungen zugeschnitten sind.',
        cta: 'Beratung anfordern',
      },
      screen2: {
        title: 'Die Build-Sequenz',
        subtitle: 'Sichere SaaS-Deployment-Pipeline',
        step1: { title: 'Design', desc: 'Sichere Architektur' },
        step2: { title: 'Build', desc: 'Gehärtete CI/CD' },
        step3: { title: 'Release', desc: 'Verifizierte Bereitstellung' },
      },
      screen3: {
        title: 'Bereit für Ihr {br}sicheres Fundament?',
        desc: 'Erleben Sie die Sicherheit einer durchdachten Architektur. Unsere Ingenieure sind bereit, Ihr nächstes sicheres Release zu planen, zu entwerfen und auszuliefern.',
        cta: '20-minütige Produktdemo buchen',
        badges: {
          soc2: 'SOC2 KONFORM',
          iso: 'ISO 27001',
          saas: 'SaaS FIRST',
        },
      },
    },
  },
  fr: {
    nav: {
      logoAlt: 'Ocypheris – La complexité simplifiée',
      product: 'Produit',
      autopilot: 'Autopilot',
      security: 'Sécurité',
      faq: 'FAQ',
      company: 'Entreprise',
      contact: 'Contactez-nous',
      bookCall: 'Réserver un appel',
    },
    hero: {
      title: 'Sécurisez votre environnement AWS en mode Autopilot.',
      subtitle1: 'Arrêtez de vous noyer dans les alertes de sécurité.',
      subtitle2: 'Résolvez instantanément des centaines de vulnérabilités cloud. Réduisez le travail manuel de 90 % et atteignez la conformité plus rapidement.',
      cta: 'Réserver une démonstration de 20 minutes',
    },
    autopilot: {
      label: 'Présentation d’AWS Security Autopilot',
      title: 'Le gestionnaire de posture de sécurité cloud ',
      titleHighlight: 'qui corrige réellement les problèmes.',
      desc: 'Les outils traditionnels vous submergent d’alertes. Autopilot ingère vos alertes AWS brutes, détermine le périmètre d’impact (« blast radius ») et génère le code d’infrastructure exact nécessaire pour sécuriser votre environnement.',
      cards: {
        signal: {
          title: 'Extraction intelligente des signaux',
          desc: 'Connectez-vous à EventBridge et transformez des milliers de résultats bruts et dupliqués provenant de Security Hub en une file priorisée unique de vulnérabilités à la racine.',
        },
        cures: {
          title: 'Corrections automatisées',
          desc: 'Arrêtez d’écrire des correctifs manuels. AWS Autopilot fournit des corrections directes en un clic ou des bundles Terraform prêts à fusionner pour les alertes critiques.',
        },
        compliance: {
          title: 'Conformité vérifiable',
          desc: 'Chaque correction automatisée génère des preuves immuables prêtes pour les audits, automatiquement associées à vos frameworks SOC 2 et ISO.',
        },
      },
    },
    proof: {
      title: 'Maximisez la sécurité. ',
      titleHighlight: 'Minimisez l’effort.',
      desc: 'Permissions transparentes. Mise en valeur rapide.',
      features: {
        connect: {
          title: 'ZÉRO AGENTS',
          desc: 'Aucun agent à installer. Aucune permission administrative étendue. Seulement un rôle IAM en lecture seule, simple et transparent, déployé en 5 minutes pour AWS Autopilot via CloudFormation.',
        },
        visibility: {
          title: 'TRAÇAGE EN TEMPS RÉEL',
          desc: 'Pourquoi attendre jusqu’à 24 heures que Security Hub se mette à jour ? AWS Autopilot se connecte directement à la machine d’état de votre compte via EventBridge, identifiant les nouveaux risques dès leur apparition.',
        },
        control: {
          title: 'CONFIANCE VÉRIFIÉE',
          desc: 'Vous gardez une autorité complète sur votre infrastructure. L\'analyse d\'AWS Autopilot s\'effectue strictement en mode lecture seule, et les corrections sont livrées sous forme de bundles de pull request vérifiables, vous permettant d’approuver chaque ligne de code avant son déploiement.',
        },
      },
    },

    services: {
      title: 'Services de sécurité complets',
      desc: 'L’expertise d’élite derrière l’automatisation, adaptée à votre architecture.',
      cards: {
        manual: {
          title: 'Gestion manuelle de la sécurité',
          subtitle: 'Prenez le contrôle total de votre environnement AWS',
          desc: 'Nos architectes en sécurité cloud réalisent des audits approfondis, assurent une surveillance continue et appliquent des renforcements personnalisés afin de rendre chaque couche de votre infrastructure totalement sécurisée.',
        },
        saas: {
          title: 'Déploiement SaaS sécurisé',
          subtitle: 'Conçu pour être sécurisé dès le premier jour',
          desc: 'De la conception de l’architecture au déploiement en production, nous déployons des produits SaaS sécurisés et hautement disponibles, avec la sécurité intégrée nativement dans votre pipeline CI/CD.',
        },
      },
    },
    security: {
      label: 'La confiance est notre fondation',
      title: 'Sécurité et gestion des données',
      desc: 'Chaque couche d’Ocypheris est conçue avec une approche « security-first », afin de garantir que votre environnement AWS reste protégé et que vos données restent privées.',
      cta: 'Explorer notre livre blanc sur la sécurité',
      cards: {
        access: {
          title: 'Modèle d’accès vérifié',
          desc: 'AWS Autopilot utilise STS:AssumeRole avec External ID et des identifiants de session à durée limitée. Cela garantit qu’aucune clé permanente n’existe et que chaque action est strictement limitée.',
        },
        credentials: {
          title: 'Gestion des identifiants',
          desc: 'AWS Autopilot ne stocke jamais les clés d’accès AWS ou les clés secrètes de nos clients. Notre architecture fonctionne exclusivement avec des rôles basés sur l’identité, éliminant les risques de fuite d’identifiants.',
        },
        isolation: {
          title: 'Isolation des locataires encapsulée',
          desc: 'Les résultats, actions et exceptions dans AWS Autopilot sont strictement isolés par tenant_id au niveau de l’API et du modèle de données, empêchant toute exposition de données entre comptes.',
        },
        residency: {
          title: 'Résidence des données',
          desc: 'La résidence des données clients pour AWS Autopilot est configurable pour répondre à vos exigences régionales et réglementaires.',
        },
        encryption: {
          title: 'Chiffrement',
          desc: 'Les données d\'AWS Autopilot sont chiffrées au repos avec AES-256 et en transit via TLS 1.3 sur toute l’architecture de la plateforme.',
        },
      },
    },
    baseline: {
      title: 'Reporting de conformité continue',
      desc: 'Arrêtez de courir avant un audit. AWS Autopilot génère en continu des baselines prêtes pour les conseils d’administration et des preuves immuables démontrant votre posture de sécurité.',
      card: {
        title: 'Analyse de baseline en 48 heures',
        features: {
          clock: { title: 'Instantanés en temps réel', desc: 'AWS Autopilot assure le suivi continu de l’état de l’infrastructure sur tous les comptes connectés.' },
          check: { title: 'Mapping des frameworks', desc: 'Les résultats d\'AWS Autopilot sont automatiquement associés aux référentiels SOC 2, ISO 27001 et CIS Benchmarks.' },
          file: { title: 'Artefacts lisibles par machine', desc: 'AWS Autopilot vous permet d\'exporter des payloads JSON bruts ou des fichiers CSV formatés pour vos outils GRC.' },
        },
      },
    },
    faq: {
      title: 'Des questions sur Ocypheris ?',
      desc: 'Nous avons compilé les réponses aux questions les plus fréquentes concernant la sécurité, les tarifs, la remédiation automatique et les intégrations.',
      cta: 'Lire la FAQ',
    },
    team: {
      title: 'Conçu par des ingénieurs, pour des ingénieurs',
      desc: 'AWS Security Autopilot a été conçu par des ingénieurs ayant aidé des équipes AWS-first à préparer des audits SOC 2, et qui souhaitaient une méthode plus rapide pour passer d’une vulnérabilité détectée à sa correction, sans cycles de conseil interminables.',
    },
    contact: {
      title: 'Visualisez vos risques. Sans engagement.',
      desc1: 'Réservez une démonstration de 20 minutes et nous vous montrerons ce que AWS Security Autopilot détecte dans votre compte.',
      desc2: 'Ou commencez avec un rapport de baseline en 48 heures — sans carte bancaire requise.',
      desc3: 'Contactez-nous pour un tarif personnalisé et un accès bêta immédiat.',
      cta1: 'Commencer',
      cta2: 'Contacter l’équipe commerciale',
      side: {
        title: 'Réservez un appel ou envoyez-nous un message',
        desc1: 'Vous préférez l’e-mail ? Contactez-nous directement à ',
        desc2: 'Partagez votre empreinte AWS, vos besoins de conformité et vos délais.',
      },
    },
    footer: {
      about: {
        title: 'À propos d’Ocypheris',
        desc: 'Ocypheris développe des outils de sécurité et de conformité natifs AWS. Autopilot transforme les résultats de Security Hub et GuardDuty en actions priorisées, corrections contrôlées et preuves prêtes pour audit — pour les équipes qui recherchent de la clarté sans surcharge opérationnelle.',
      },
      copyright: 'Ocypheris. Tous droits réservés.',
    },
    about: {
      hero: {
        label: 'L\'histoire d\'Ocypheris',
        title: 'La complexité simplifiée',
        desc: "Nous sommes des ingénieurs qui ont passé trop de nuits blanches à trier des milliers de fausses alertes AWS en double. Nous avons construit AWS Security Autopilot pour corriger la véritable cause racine, et pas seulement pour tracer des diagrammes de « blast radius ».",
      },
      mission: {
        title: 'Notre Mission',
        desc1: 'Les équipes de sécurité croulent sous le bruit. Les outils CSPM classiques comme Security Hub ou GuardDuty sont excellents pour détecter des problèmes, mais ils repassent la charge de la correction à des équipes d\'ingénierie en sous-effectif.',
        desc2: 'Ocypheris comble le fossé entre la découverte d\'une vulnérabilité et sa correction définitive. En regroupant les alertes brutes et dupliquées en une seule file prioritaire de correctifs déterministes en 1 clic – avec des preuves SOC 2 et ISO vérifiables – nous redonnons du temps aux équipes de sécurité.',
      },
      cards: {
        safety: {
          title: 'Une Sécurité Intransigeante',
          desc: 'Nous fonctionnons uniquement avec des rôles basés sur l\'identité. Nous ne stockons jamais de clés ou mots de passe à long terme. Chaque action automatisée est strictement protégée, vérifie les conditions de « blast radius » et nécessite une approbation humaine explicite avant son exécution.',
        },
        action: {
          title: 'De l\'Action plutôt que des Alertes',
          desc: "Nous ne vendons pas de tableaux de bord remplis de points rouges. Autopilot n'est pas qu'un simple agrégateur – c'est un moteur d'exécution. Nous privilégions les correctifs réels, qu'il s'agisse de modifier une politique de bucket S3 ou de générer une Pull Request Terraform prête à être validée, plutôt que de générer encore plus de bruit.",
        },
      },
      cta: 'Contacter l’équipe',
    },
    faqPage: {
      hero: {
        label: 'Support Ocypheris',
        title: 'Questions Fréquentes (FAQ)',
        desc: 'Tout ce que vous devez savoir sur AWS Security Autopilot.',
      },
      items: {
        q1: 'À quelle vitesse obtient-on des résultats ?',
        a1: 'La plupart des équipes connectent un compte et voient des actions prioritaires en quelques minutes.',
        q2: 'Modifiez-vous l\'infrastructure automatiquement ?',
        a2: 'Non. Les modifications se font soit via des correctifs directs explicitement approuvés, soit par des bundles de Pull Request révisés.',
        q3: 'Cela remplace-t-il Security Hub ou GuardDuty ?',
        a3: 'Non. Cela les rend opérationnels en transformant les résultats en un workflow clair et gérable.',
        q4: 'Combien cela coûte-t-il ?',
        a4: 'Les tarifs commencent à 399 $/mois pour un seul compte AWS. Des forfaits multi-comptes et Enterprise sont disponibles — réservez une démonstration pour évaluer vos besoins.',
        q5: 'Mes données sont-elles en sécurité ?',
        a5: 'AWS Security Autopilot utilise un rôle IAM en lecture seule — il ne modifie jamais votre compte sans approbation explicite. Nous ne stockons pas vos identifiants AWS. Toutes les données sont chiffrées en transit et au repos. Retrouvez plus de détails dans notre section Sécurité.',
        q6: 'Que se passe-t-il si AWS Security Autopilot est hors ligne ?',
        a6: 'Rien ne change dans votre compte AWS. Le produit fonctionne en lecture seule par défaut. Les actions de correction s\'exécutent uniquement après votre validation. Votre infrastructure n\'est jamais touchée sans votre intervention directe.',
        q7: 'En quoi est-ce différent de Wiz, Prowler ou AWS Security Hub ?',
        a7: 'Security Hub et Prowler trouvent des problèmes. Wiz les cartographie. AWS Security Autopilot les résout — il vous permet de passer d\'une liste d\'alertes à des correctifs fusionnés et des preuves prêtes pour l\'audit, sans perdre des semaines en travail manuel.',
      },
      contact: {
        desc: 'Vous avez d\'autres questions ? Contactez-nous sur ',
        cta: 'Contactez-nous',
      },
    },
    securityPage: {
      hero: {
        label: 'Trust Center Ocypheris',
        title: 'Livre Blanc sur la Sécurité',
        desc: 'Comment nous sécurisons votre environnement AWS avec Autopilot — sans compromettre vos données ni vos identifiants.',
      },
      exec: {
        title: 'Résumé Executif',
        desc: 'Ocypheris (AWS Security Autopilot) est conçu sur un modèle « security-first, least-privilege ». Nous transformons les alertes de sécurité natives d\'AWS en actions prioritaires et recommandations exploitables, via un accès strictement identitaire. Notre architecture garantit que l\'environnement des clients reste verrouillé, qu\'aucun identifiant n\'est stocké et que chaque correction nécessite une approbation explicite.',
      },
      cards: {
        access: {
          title: 'Modèle d’accès',
          desc: 'Nous utilisons STS:AssumeRole avec un External ID et des identifiants de session à durée de vie limitée. Nous appliquons une stricte séparation des privilèges avec un rôle en lecture (ReadRole) pour l\'analyse et un rôle d\'écriture (WriteRole) restreint aux seules actions formellement autorisées.',
        },
        zero: {
          title: 'Politique de zéro stockage d\'identifiants',
          desc: 'Ocypheris ne stocke jamais d\'AWS Access Key IDs ni de Secret Access Keys. Toutes les opérations reposent sur des rôles basés sur l\'identité, éliminant ainsi les risques de fuite de clés à long terme.',
        },
        isolation: {
          title: 'Isolation des Locataires',
          desc: 'Les résultats, actions et exceptions sont strictement séparés par tenant_id. Cette isolation s\'applique à la fois sur le routage de l\'API et dans la base de données afin de prévenir tout accès non autorisé inter-comptes.',
        },
        encryption: {
          title: 'Chiffrement & Stockage',
          desc: 'Toutes les données sont chiffrées au repos via AES-256 (sur RDS et S3) et en transit via TLS 1.3. La zone géographique de résidence des données clients est configurable pour garantir le respect des normes en vigueur.',
        },
        controls: {
          title: 'Contrôles de Sécurité de Remédiation',
          desc: 'Aucune modification de l\'infrastructure n\'a lieu sans approbation client explicite. L\'Autopilot exécute des validations préliminaires (pre-flight checks), soumet la correction à une validation humaine et propose un mécanisme de rollback automatique si nécessaire.',
        },
        iam: {
          title: 'Moindre Privilège IAM',
          desc: 'Nos politiques IAM sont strictement définies sans joker (wildcard). Le rôle WriteRole est exclusivement restreint aux corrections sûres, idempotentes et automatisées de l\'infrastructure, bloquant par design toute modification non autorisée.',
        },
      },
      audit: {
        title: 'Pistes d\'Audit & Conformité Continue',
        desc1: 'Chaque action, demande d\'exception et tentative de correction est enregistrée de manière immuable. Les clients peuvent générer des preuves d\'audit au format SOC 2 et ISO 27001, justifiant instantanément de l\'application de configurations spécifiques face aux exigences réglementaires. De notre côté, Ocypheris maintient en interne sa propre posture de sécurité auditable à tout moment.',
        desc2: 'Des analyses de vulnérabilités sont intégrées à nos pipelines CI/CD et nous opérons un protocole de réponse aux incidents actif 24h/24 & 7j/7 contre les menaces émergentes.',
      },
      cta: 'Retour à la Sécurité Produit',
    },
    contactPopover: {
      trigger: {
        title: 'Dites-nous ce que vous avez en tête.',
        label: 'E-mail direct',
      },
      desc: 'Ou écrivez-nous directement à ',
      form: {
        message: 'Comment pouvons-nous vous aider ?',
        name: 'Nom complet',
        email: 'E-mail professionnel',
        company: 'Entreprise',
        phone: 'Téléphone (optionnel)',
      },
    },
    deepSurface: {
      background: 'SÉCURISÉ PAR CONCEPTION',
      screen1: {
        title: 'Sécurisé par ',
        highlight: 'Conception',
        desc: 'Au-delà de nos outils automatisés, nous concevons, implémentons et déployons des produits SaaS intrinsèquement sécurisés et des architectures cloud adaptées exactement à vos besoins métier.',
        cta: 'Prendre rendez-vous',
      },
      screen2: {
        title: 'La séquence de build',
        subtitle: 'Pipeline de déploiement SaaS sécurisé',
        step1: { title: 'Conception', desc: 'Architecture sécurisée' },
        step2: { title: 'Build', desc: 'CI/CD durcie' },
        step3: { title: 'Déploiement', desc: 'Mise en production vérifiée' },
      },
      screen3: {
        title: 'Prêt à bâtir votre {br}fondation sécurisée ?',
        desc: 'Vivez la tranquillité d\'esprit d\'une sécurité architecturale. Nos ingénieurs sont prêts à cadrer, concevoir et livrer votre prochaine version sécurisée.',
        cta: 'Réserver une démo de 20 min',
        badges: {
          soc2: 'CONFORME SOC2',
          iso: 'ISO 27001',
          saas: 'SaaS FIRST',
        },
      },
    },
  },
} as const;

export type Language = keyof typeof translations;
