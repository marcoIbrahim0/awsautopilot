'use client';

import { useEffect } from 'react';

export function SectionAnimator() {
  useEffect(() => {
    const isMobile = typeof window !== 'undefined' && window.innerWidth <= 767;
    const root = document.documentElement;
    const targets = Array.from(
      document.querySelectorAll<HTMLElement>('[data-landing-animate]')
    ).filter((target) => target.tagName !== 'FOOTER' && !target.closest('footer'));
    if (!targets.length) {
      return;
    }

    targets.forEach((target, index) => {
      const delayStep = isMobile ? 42 : 70;
      const delay = Math.min(index * delayStep, isMobile ? 280 : 420);
      target.style.setProperty('--landing-delay', `${delay}ms`);
      target.style.setProperty(
        '--landing-delay-fast',
        `${Math.min(index * (isMobile ? 28 : 45), isMobile ? 180 : 270)}ms`
      );
    });

    const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
    const initialTopRatio = isMobile ? 0.68 : 0.76;
    const initialBottomRatio = isMobile ? 0.32 : 0.24;
    targets.forEach((target) => {
      const rect = target.getBoundingClientRect();
      const overlapsViewport =
        rect.top < viewportHeight * initialTopRatio &&
        rect.bottom > viewportHeight * initialBottomRatio;
      if (overlapsViewport) {
        target.classList.add('landing-animate-visible');
      }
    });

    root.classList.add('landing-animations-ready');

    const showRatio = isMobile ? 0.2 : 0.18;
    const hideRatio = isMobile ? 0.02 : 0.03;
    const rootMargin = isMobile ? '-2% 0px -2% 0px' : '-10% 0px -10% 0px';
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const target = entry.target as HTMLElement;
          const isVisible = target.classList.contains('landing-animate-visible');
          const ratio = entry.intersectionRatio;
          const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
          const offscreenBuffer = viewportHeight * (isMobile ? 0.16 : 0.12);
          const isFarOutsideViewport =
            entry.boundingClientRect.bottom < -offscreenBuffer ||
            entry.boundingClientRect.top > viewportHeight + offscreenBuffer;

          if (!isVisible && ratio >= showRatio) {
            target.classList.add('landing-animate-visible');
            return;
          }

          if (isVisible && ratio <= hideRatio && isFarOutsideViewport) {
            target.classList.remove('landing-animate-visible');
          }
        });
      },
      {
        threshold: [0, hideRatio, showRatio, 0.25],
        rootMargin,
      }
    );

    targets.forEach((target) => observer.observe(target));

    return () => {
      observer.disconnect();
      root.classList.remove('landing-animations-ready');
      targets.forEach((target) => {
        target.classList.remove('landing-animate-visible');
      });
    };
  }, []);

  return null;
}
