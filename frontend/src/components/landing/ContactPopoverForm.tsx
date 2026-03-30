'use client';

import { useState } from 'react';
import Link from 'next/link';
import { submitContactForm } from '@/app/actions/contact';
import {
  FloatingPanelBody,
  FloatingPanelCloseButton,
  FloatingPanelContent,
  FloatingPanelFooter,
  FloatingPanelForm,
  FloatingPanelLabel,
  FloatingPanelRoot,
  FloatingPanelSubmitButton,
  FloatingPanelTextarea,
  FloatingPanelTrigger,
} from '@/components/ui/floating-panel';
import { useLanguage } from '@/lib/i18n';

export function ContactPopoverForm() {
  const { t } = useLanguage();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleSubmit = async (note: string, form: HTMLFormElement) => {
    setIsSubmitting(true);
    const formData = new FormData(form);
    formData.set('message', note);
    const res = await submitContactForm(formData);
    setIsSubmitting(false);

    if (res.success) {
      setIsSuccess(true);
      setTimeout(() => setIsSuccess(false), 3000);
    } else {
      throw new Error(res.error || 'Failed to submit form');
    }
  };

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg)] p-6 nm-raised-lg">
      <FloatingPanelRoot className="flex flex-col gap-3">
        <FloatingPanelTrigger
          title={t('contactPopover.trigger.title')}
          className="w-full justify-center rounded-lg border border-[var(--border)] bg-transparent px-4 py-2 text-sm font-semibold !text-[#1d305a] transition-all duration-300 hover:border-[var(--accent)] hover:bg-[rgba(10,113,255,0.05)] focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--accent)] nm-raised"
        >
          {t('contactPopover.trigger.label')}
        </FloatingPanelTrigger>
        <p className="text-sm" style={{ color: 'var(--nm-text-muted)' }}>
          {t('contactPopover.desc')}{' '}
          <Link href="mailto:sales@ocypheris.com" className="font-semibold transition-colors duration-200" style={{ color: 'var(--accent)' }}>
            sales@ocypheris.com
          </Link>
          .
        </p>

        <FloatingPanelContent className="w-[calc(100vw-24px)] max-w-[360px] rounded-2xl border border-white/10 bg-[#0b1024] text-white shadow-2xl">
          <FloatingPanelForm className="text-white" onSubmit={handleSubmit}>
            <FloatingPanelBody className="space-y-3">
              <FloatingPanelLabel htmlFor="contact-message" className="text-white/80">
                {t('contactPopover.form.message')}
              </FloatingPanelLabel>
              <FloatingPanelTextarea
                id="contact-message"
                className="min-h-[120px] rounded-xl border border-white/10 bg-white/5 text-white placeholder:text-white/40"
              />
              <div className="space-y-1.5">
                <label htmlFor="contact-name" className="block text-sm font-medium text-white/80">
                  {t('contactPopover.form.name')}
                </label>
                <input
                  id="contact-name"
                  name="name"
                  type="text"
                  placeholder="Alex Johnson"
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/40 transition focus:border-[var(--accent)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/60"
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="contact-email" className="block text-sm font-medium text-white/80">
                  {t('contactPopover.form.email')}
                </label>
                <input
                  id="contact-email"
                  name="email"
                  type="email"
                  placeholder="you@company.com"
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/40 transition focus:border-[var(--accent)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/60"
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="contact-company" className="block text-sm font-medium text-white/80">
                  {t('contactPopover.form.company')}
                </label>
                <input
                  id="contact-company"
                  name="company"
                  type="text"
                  placeholder="Company name"
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/40 transition focus:border-[var(--accent)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/60"
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="contact-phone" className="block text-sm font-medium text-white/80">
                  {t('contactPopover.form.phone')}
                </label>
                <input
                  id="contact-phone"
                  name="phone"
                  type="tel"
                  placeholder="+1 (555) 000-0000"
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/40 transition focus:border-[var(--accent)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/60"
                />
              </div>
            </FloatingPanelBody>
            <FloatingPanelFooter className="items-center">
              <FloatingPanelCloseButton className="text-white/70" />
              <FloatingPanelSubmitButton
                className="border-white/15 text-white/80 hover:bg-white/10 hover:text-white"
                disabled={isSubmitting || isSuccess}
              >
                {isSubmitting ? 'Sending...' : (isSuccess ? 'Message Sent!' : 'Send Message')}
              </FloatingPanelSubmitButton>
            </FloatingPanelFooter>
          </FloatingPanelForm>
        </FloatingPanelContent>
      </FloatingPanelRoot>
    </div>
  );
}
