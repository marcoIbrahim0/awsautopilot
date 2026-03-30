'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';
import { NAVIGATION_FEEDBACK_EVENT } from '@/lib/navigation-feedback';

const MAX_NAVIGATION_FEEDBACK_MS = 12000;

function isInternalNavigationClick(event: MouseEvent): boolean {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
    return false;
  }

  const target = event.target as HTMLElement | null;
  const anchor = target?.closest('a');
  if (!anchor) return false;
  if (anchor.hasAttribute('download')) return false;

  const targetAttr = anchor.getAttribute('target');
  if (targetAttr && targetAttr !== '_self') return false;

  const href = anchor.getAttribute('href');
  if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) {
    return false;
  }

  let targetUrl: URL;
  try {
    targetUrl = new URL(anchor.href, window.location.href);
  } catch {
    return false;
  }

  const currentUrl = new URL(window.location.href);
  if (targetUrl.origin !== currentUrl.origin) return false;
  if (
    targetUrl.pathname === currentUrl.pathname &&
    targetUrl.search === currentUrl.search &&
    targetUrl.hash === currentUrl.hash
  ) {
    return false;
  }

  return true;
}

export function NavigationFeedback() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isNavigating, setIsNavigating] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  const stopFeedback = useCallback(() => {
    setIsNavigating(false);
    if (timeoutRef.current) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const startFeedback = useCallback(() => {
    setIsNavigating(true);
    if (timeoutRef.current) {
      window.clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = window.setTimeout(() => {
      setIsNavigating(false);
      timeoutRef.current = null;
    }, MAX_NAVIGATION_FEEDBACK_MS);
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      stopFeedback();
    }, 0);
    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [pathname, searchParams, stopFeedback]);

  useEffect(() => {
    const onDocumentClick = (event: MouseEvent) => {
      if (isInternalNavigationClick(event)) {
        startFeedback();
      }
    };

    const onCustomNavigationStart = () => {
      startFeedback();
    };

    document.addEventListener('click', onDocumentClick, true);
    window.addEventListener(NAVIGATION_FEEDBACK_EVENT, onCustomNavigationStart);

    return () => {
      document.removeEventListener('click', onDocumentClick, true);
      window.removeEventListener(NAVIGATION_FEEDBACK_EVENT, onCustomNavigationStart);
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [startFeedback]);

  useEffect(() => {
    document.body.classList.toggle('route-loading', isNavigating);
    return () => {
      document.body.classList.remove('route-loading');
    };
  }, [isNavigating]);

  return (
    <>
      <div
        aria-hidden
        className={`pointer-events-none fixed inset-x-0 top-0 z-[120] h-0.5 overflow-hidden transition-opacity duration-150 ${isNavigating ? 'opacity-100' : 'opacity-0'}`}
      >
        <div className="nav-loading-bar h-full w-1/3 bg-accent" />
      </div>
      <span className="sr-only" role="status" aria-live="polite">
        {isNavigating ? 'Loading content' : ''}
      </span>
    </>
  );
}
