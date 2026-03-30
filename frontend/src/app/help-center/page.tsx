'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

import { MarketingFooter } from '@/components/landing/MarketingFooter';
import { SiteNav } from '@/components/site-nav';
import { ButtonLink } from '@/components/ui/ButtonLink';
import { Input } from '@/components/ui/Input';
import { getErrorMessage, HelpArticle, HelpSearchResult, listHelpArticles, searchHelpArticles } from '@/lib/api';

function articleExcerpt(article: HelpArticle | HelpSearchResult): string {
  return typeof (article as HelpSearchResult).snippet === 'string'
    ? (article as HelpSearchResult).snippet
    : article.summary;
}

export default function HelpCenterPage() {
  const [articles, setArticles] = useState<HelpArticle[]>([]);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<HelpSearchResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listHelpArticles()
      .then((response) => setArticles(response.items))
      .catch((value) => setError(getErrorMessage(value)));
  }, []);

  async function handleSearch() {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    try {
      const response = await searchHelpArticles({ q: query.trim() });
      setResults(response.items);
    } catch (value) {
      setError(getErrorMessage(value));
    }
  }

  const items = query.trim() ? results : articles;

  return (
    <>
      <SiteNav />
      <main className="landing-neumorphic min-h-screen px-6 pb-20 pt-32">
        <section className="mx-auto max-w-6xl">
          <div className="flex flex-col gap-6 rounded-[2rem] border border-[rgba(17,24,39,0.08)] bg-white/75 p-8 shadow-[0_24px_80px_rgba(15,23,42,0.10)] backdrop-blur md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[#0B71FF]">Help Center</p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900">Published support articles</h1>
              <p className="mt-4 max-w-3xl text-base leading-8 text-slate-600">
                Browse the same published help articles used by the in-product Help Hub. Sign in if you need grounded
                assistant answers or private support cases.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <ButtonLink href="/help" variant="secondary">Open In-App Help</ButtonLink>
              <ButtonLink href="/login">Sign In</ButtonLink>
            </div>
          </div>

          <div className="mt-8 flex gap-2">
            <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search onboarding, actions, integrations..." />
            <button
              type="button"
              onClick={() => handleSearch()}
              className="rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
            >
              Search
            </button>
          </div>
          {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}

          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {items.map((article) => (
              <Link
                key={article.slug}
                href={`/help-center/${article.slug}`}
                className="rounded-[1.6rem] border border-slate-200 bg-white/80 p-6 shadow-[0_18px_50px_rgba(15,23,42,0.07)] transition hover:-translate-y-0.5 hover:border-[#0B71FF]/30"
              >
                <div className="flex flex-wrap gap-2">
                  {article.tags.slice(0, 3).map((tag) => (
                    <span key={tag} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{tag}</span>
                  ))}
                </div>
                <h2 className="mt-4 text-xl font-semibold text-slate-900">{article.title}</h2>
                <p className="mt-3 text-sm leading-7 text-slate-600">{articleExcerpt(article)}</p>
              </Link>
            ))}
          </div>
        </section>
      </main>
      <MarketingFooter compactWave />
    </>
  );
}
