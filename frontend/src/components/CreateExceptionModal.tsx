'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import {
  REMEDIATION_EYEBROW_CLASS,
  RemediationCallout,
  RemediationPanel,
  RemediationSection,
  SectionTitleExplainer,
  dashboardFieldClass,
  remediationInsetClass,
} from '@/components/ui/remediation-surface';
import {
  createException,
  type CreateExceptionRequest,
  getErrorMessage,
} from '@/lib/api';
import { cn } from '@/lib/utils';

interface CreateExceptionModalProps {
  isOpen: boolean;
  onClose: () => void;
  entityType: 'finding' | 'action';
  entityId: string;
  onSuccess?: (payload: CreateExceptionRequest) => void;
  tenantId?: string;
  initialReason?: string;
  introText?: string;
  initialExpiryDate?: string;
}

interface CreateExceptionWorkflowContentProps
  extends Omit<CreateExceptionModalProps, 'isOpen'> {
  onBusyChange?: (busy: boolean) => void;
}

function defaultExceptionExpiryDate() {
  const date = new Date();
  date.setDate(date.getDate() + 30);
  return date.toISOString().split('T')[0];
}

function exceptionFieldClass(className?: string): string {
  return cn(dashboardFieldClass(), className);
}

export function CreateExceptionWorkflowContent({
  onClose,
  entityType,
  entityId,
  onSuccess,
  tenantId,
  initialReason,
  introText,
  initialExpiryDate,
  onBusyChange,
}: CreateExceptionWorkflowContentProps) {
  const [reason, setReason] = useState(initialReason ?? '');
  const [expiresAt, setExpiresAt] = useState(initialExpiryDate || defaultExceptionExpiryDate());
  const [ticketLink, setTicketLink] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const title = useMemo(
    () => `Suppress ${entityType === 'finding' ? 'Finding' : 'Action'}`,
    [entityType],
  );

  const resetForm = useCallback(() => {
    setReason('');
    setExpiresAt('');
    setTicketLink('');
    setError(null);
    setIsSubmitting(false);
  }, []);

  useEffect(() => {
    onBusyChange?.(isSubmitting);
  }, [isSubmitting, onBusyChange]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    if (reason.length < 10) {
      setError('Reason must be at least 10 characters');
      return;
    }

    if (!expiresAt) {
      setError('Expiry date is required');
      return;
    }

    const expiryDate = new Date(expiresAt);
    if (expiryDate <= new Date()) {
      setError('Expiry date must be in the future');
      return;
    }

    setIsSubmitting(true);

    try {
      const payload: CreateExceptionRequest = {
        entity_type: entityType,
        entity_id: entityId,
        reason: reason.trim(),
        expires_at: new Date(expiresAt).toISOString(),
        ticket_link: ticketLink.trim() || undefined,
      };

      await createException(payload, tenantId);
      resetForm();
      onClose();
      onSuccess?.(payload);
    } catch (err) {
      setError(getErrorMessage(err));
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (isSubmitting) return;
    resetForm();
    onClose();
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <RemediationPanel className="p-6" tone="warning">
        <div className="space-y-3">
          <p className={REMEDIATION_EYEBROW_CLASS}>Exception workflow</p>
          <h3 className="text-2xl font-semibold leading-tight text-text">{title}</h3>
          <p className="text-sm leading-7 text-text/74">
            {introText ?? (
              <>
                Create an exception to suppress this {entityType} from the active list. You must provide a reason and
                expiry date.
              </>
            )}
          </p>
        </div>
      </RemediationPanel>

      <RemediationSection
        description={`Capture why this ${entityType} should be suppressed and when it should return to the active queue.`}
        eyebrow="Suppression"
        title="Exception details"
        titleExplainer={<SectionTitleExplainer conceptId="suppression" context="suppression" label="Exception details" />}
        tone="warning"
      >
        <div className="space-y-4">
          <div className={remediationInsetClass('warning')}>
            <div className="flex flex-wrap items-center gap-2">
              <label
                htmlFor={`${entityType}-exception-reason`}
                className="block text-sm font-medium text-text"
              >
                Reason <span className="text-accent">*</span>
              </label>
              <SectionTitleExplainer conceptId="exception_reason" context="suppression" label="Reason" />
            </div>
            <textarea
              id={`${entityType}-exception-reason`}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              rows={4}
              className={exceptionFieldClass('mt-3 resize-none')}
              placeholder="e.g., False positive - scanner misconfiguration. Accepted risk per security policy review."
              required
              minLength={10}
              disabled={isSubmitting}
            />
            <p className="mt-2 text-xs text-muted">
              Minimum 10 characters. Explain why this {entityType} should be suppressed.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className={remediationInsetClass('default')}>
              <div className="flex flex-wrap items-center gap-2">
                <label
                  htmlFor={`${entityType}-exception-expiry`}
                  className="block text-sm font-medium text-text"
                >
                  Expires On <span className="text-accent">*</span>
                </label>
                <SectionTitleExplainer conceptId="exception_duration" context="suppression" label="Expires On" />
              </div>
              <Input
                id={`${entityType}-exception-expiry`}
                type="date"
                value={expiresAt}
                onChange={(event) => setExpiresAt(event.target.value)}
                required
                disabled={isSubmitting}
                min={new Date().toISOString().split('T')[0]}
                className="mt-3 bg-bg/80 shadow-none"
              />
              <p className="mt-2 text-xs text-muted">
                After this date, the exception will expire and the {entityType} will reappear.
              </p>
            </div>

            <div className={remediationInsetClass('default')}>
              <div className="flex flex-wrap items-center gap-2">
                <label
                  htmlFor={`${entityType}-exception-ticket-link`}
                  className="block text-sm font-medium text-text"
                >
                  Ticket Link <span className="text-xs text-muted">(optional)</span>
                </label>
                <SectionTitleExplainer conceptId="ticket_link" context="suppression" label="Ticket Link" />
              </div>
              <Input
                id={`${entityType}-exception-ticket-link`}
                type="url"
                value={ticketLink}
                onChange={(event) => setTicketLink(event.target.value)}
                placeholder="https://jira.example.com/TICKET-123"
                disabled={isSubmitting}
                className="mt-3 bg-bg/80 shadow-none"
              />
              <p className="mt-2 text-xs text-muted">
                Link to Jira, ServiceNow, or other ticketing system.
              </p>
            </div>
          </div>
        </div>
      </RemediationSection>

      {error && (
        <RemediationCallout description={error} title="Unable to create exception" tone="danger" />
      )}

      <div className={remediationInsetClass('default', 'flex flex-col gap-3 sm:flex-row')}>
        <Button
          type="button"
          variant="secondary"
          onClick={handleClose}
          disabled={isSubmitting}
          className="flex-1"
        >
          Cancel
        </Button>
        <Button
          type="submit"
          variant="primary"
          isLoading={isSubmitting}
          className="flex-1"
        >
          {isSubmitting ? 'Creating...' : 'Create Exception'}
        </Button>
      </div>

      <span className="sr-only">{title}</span>
    </form>
  );
}

export function CreateExceptionModal({
  isOpen,
  onClose,
  entityType,
  entityId,
  onSuccess,
  tenantId,
  initialReason,
  introText,
  initialExpiryDate,
}: CreateExceptionModalProps) {
  const [preventClose, setPreventClose] = useState(false);
  const title = `Suppress ${entityType === 'finding' ? 'Finding' : 'Action'}`;

  const handleClose = useCallback(() => {
    if (preventClose) return;
    setPreventClose(false);
    onClose();
  }, [onClose, preventClose]);

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={title} size="lg" variant="dashboard">
      <CreateExceptionWorkflowContent
        key={`${entityType}-${entityId}-${initialReason ?? ''}-${initialExpiryDate ?? ''}`}
        onClose={handleClose}
        entityType={entityType}
        entityId={entityId}
        onSuccess={onSuccess}
        tenantId={tenantId}
        initialReason={initialReason}
        introText={introText}
        initialExpiryDate={initialExpiryDate}
        onBusyChange={setPreventClose}
      />
    </Modal>
  );
}
