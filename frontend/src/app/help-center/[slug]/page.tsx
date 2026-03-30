'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';

import { MarketingFooter } from '@/components/landing/MarketingFooter';
import { SiteNav } from '@/components/site-nav';
import { ButtonLink } from '@/components/ui/ButtonLink';
import { getErrorMessage, getHelpArticle, HelpArticle } from '@/lib/api';

interface HelpCenterArticlePageProps {
  params: Promise<{ slug: string }>;
}

export default function HelpCenterArticlePage({ params }: HelpCenterArticlePageProps) {
  const { slug } = use(params);
  const [article, setArticle] = useState<HelpArticle | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHelpArticle(slug)
      .then(setArticle)
      .catch((value) => setError(getErrorMessage(value)));
  }, [slug]);

  return (
    <>
      <SiteNav />
      <main className="landing-neumorphic min-h-screen px-6 pb-20 pt-32">
        <section className="mx-auto max-w-4xl rounded-[2rem] border border-[rgba(17,24,39,0.08)] bg-white/80 p-8 shadow-[0_24px_80px_rgba(15,23,42,0.10)] backdrop-blur">
          <Link href="/help-center" className="text-sm font-medium text-[#0B71FF] hover:underline">← Back to Help Center</Link>
          {error ? <p className="mt-6 text-sm text-red-600">{error}</p> : null}
          {article ? (
            <>
              <div className="mt-6 flex flex-wrap gap-2">
                {article.tags.map((tag) => (
                  <span key={tag} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{tag}</span>
                ))}
              </div>
              <h1 className="mt-6 text-4xl font-semibold tracking-tight text-slate-900">{article.title}</h1>
              <p className="mt-4 whitespace-pre-line text-base leading-8 text-slate-700">{article.body}</p>
              <div className="mt-8 flex flex-wrap gap-3">
                <ButtonLink href="/help" variant="secondary">Open In-App Help</ButtonLink>
                <ButtonLink href="/login">Sign In To Open A Case</ButtonLink>
              </div>
            </>
          ) : null}
        </section>
      </main>
      <MarketingFooter compactWave />
    </>
  );
}
