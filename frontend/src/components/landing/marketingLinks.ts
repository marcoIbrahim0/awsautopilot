'use client';

type Translate = (key: string) => string;

export type MarketingLink = {
  href: string;
  label: string;
};

export const MARKETING_SOCIALS = [
  { label: 'LinkedIn', href: 'https://www.linkedin.com/company/ocypheris' },
  { label: '@ocypheris', href: 'https://x.com/ocypheris' },
] as const;

export function getMarketingPrimaryLinks(t: Translate): MarketingLink[] {
  return [
    { label: t('nav.autopilot'), href: '/landing#autopilot-explained' },
    { label: t('nav.security'), href: '/security' },
    { label: t('nav.faq'), href: '/faq' },
    { label: t('nav.contact'), href: '/landing#contact' },
  ];
}

export function getMarketingFooterLinks(t: Translate): MarketingLink[] {
  return [
    ...getMarketingPrimaryLinks(t),
    { label: 'Privacy Policy', href: '/legal/privacy' },
    { label: 'Terms of Service', href: '/legal/terms' },
    { label: 'Cookie Policy', href: '/legal/cookies' },
  ];
}
