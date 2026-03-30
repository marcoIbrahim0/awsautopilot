'use client';

import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'motion/react';

import { cn } from '@/lib/utils';
import {
  REMEDIATION_DIALOG_BODY_CLASS,
  REMEDIATION_DIALOG_CLASS,
  REMEDIATION_DIALOG_HEADER_CLASS,
} from '@/components/ui/remediation-surface';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  headerContent?: React.ReactNode;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  variant?: 'default' | 'dashboard';
}

const sizeStyles = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-4xl',
  xl: 'max-w-[88rem]',
};

const transition = { duration: 0.2, ease: 'easeOut' as const };
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter((element) => {
    if (element.getAttribute('aria-hidden') === 'true') return false;
    if (element.tabIndex < 0) return false;
    if (element.offsetParent === null && getComputedStyle(element).position !== 'fixed') return false;
    return true;
  });
}

export function Modal({
  isOpen,
  onClose,
  title,
  headerContent,
  children,
  size = 'md',
  variant = 'default',
}: ModalProps) {
  const modalRef = useRef<HTMLDivElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!isOpen) return;

    const frame = window.requestAnimationFrame(() => {
      const modalElement = modalRef.current;
      if (!modalElement) return;

      const focusableElements = getFocusableElements(modalElement);
      const firstNonCloseFocusable = focusableElements.find((element) => element !== closeButtonRef.current);
      const initialFocusTarget = firstNonCloseFocusable ?? closeButtonRef.current ?? focusableElements[0] ?? modalElement;
      initialFocusTarget.focus();
    });

    return () => window.cancelAnimationFrame(frame);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    const modalElement = modalRef.current;
    if (!modalElement) return;

    const handleTabKey = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return;

      const focusableElements = getFocusableElements(modalElement);
      if (focusableElements.length === 0) {
        event.preventDefault();
        modalElement.focus();
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const activeElement = document.activeElement as HTMLElement | null;

      if (!activeElement || !modalElement.contains(activeElement)) {
        event.preventDefault();
        firstElement.focus();
        return;
      }

      if (event.shiftKey && activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
        return;
      }

      if (!event.shiftKey && activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    };

    modalElement.addEventListener('keydown', handleTabKey);
    return () => {
      modalElement.removeEventListener('keydown', handleTabKey);
    };
  }, [isOpen]);

  if (typeof window === 'undefined') return null;

  const isDashboard = variant === 'dashboard';

  const modalContent = (
    <AnimatePresence>
      {isOpen && (
        <div className={cn('fixed inset-0 z-50 flex items-center justify-center', isDashboard ? 'p-4 sm:p-6 lg:p-8' : 'p-4')}>
          <motion.div
            className={cn(
              'absolute inset-0 bg-black/60',
              isDashboard ? 'backdrop-blur-md' : 'backdrop-blur-sm',
            )}
            onClick={onClose}
            aria-hidden="true"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={transition}
          />
          <motion.div
            ref={modalRef}
            className={cn(
              'relative flex w-full max-h-[calc(100vh-2rem)] flex-col overflow-hidden',
              sizeStyles[size],
              isDashboard
                ? REMEDIATION_DIALOG_CLASS
                : 'bg-surface border border-border rounded-2xl shadow-premium',
            )}
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
            tabIndex={-1}
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={transition}
          >
            <div
              className={cn(
                'flex items-center justify-between',
                isDashboard
                  ? REMEDIATION_DIALOG_HEADER_CLASS
                  : 'px-6 py-4 border-b border-border',
              )}
            >
              <div className="flex min-w-0 items-center gap-3">
                <h2 id="modal-title" className="text-lg font-semibold text-text">
                  {title}
                </h2>
                {headerContent ? <div className="shrink-0">{headerContent}</div> : null}
              </div>
              <button
                ref={closeButtonRef}
                onClick={onClose}
                className="p-1.5 rounded-xl text-muted hover:text-text hover:bg-dropdown-bg transition-colors"
                aria-label="Close modal"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            <div
              className={cn(
                isDashboard
                  ? REMEDIATION_DIALOG_BODY_CLASS
                  : 'px-6 py-4 min-w-0 overflow-y-auto overflow-x-hidden',
              )}
            >
              {children}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );

  return createPortal(modalContent, document.body);
}
