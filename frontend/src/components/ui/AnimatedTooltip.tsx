'use client';

import {
  useState,
  useRef,
  useEffect,
  useLayoutEffect,
  useCallback,
  type ReactNode,
} from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'motion/react';

export interface AnimatedTooltipProps {
  /** Trigger element (e.g. button). */
  children: ReactNode;
  /** Tooltip content. When empty/undefined, tooltip never shows. */
  content: ReactNode;
  /** Optional: force show (e.g. when trigger is disabled and hover is unreliable). */
  forceShow?: boolean;
  /** Placement relative to trigger. */
  placement?: 'top' | 'bottom' | 'left' | 'right';
  /** Max width of tooltip (default 280px). */
  maxWidth?: string;
  /** Delay before hover/focus reveals the tooltip (default 400ms). */
  delayMs?: number;
  /** Optional classes applied to the trigger wrapper. */
  triggerClassName?: string;
  /** Make the wrapper keyboard-focusable for non-button triggers. */
  focusable?: boolean;
  /** Allow touch/pen press to toggle the tooltip. */
  tapToToggle?: boolean;
  /** Flip to the opposite side if the preferred placement would clip. */
  autoFlip?: boolean;
}

const TOOLTIP_GAP = 12;
const VIEWPORT_MARGIN = 12;
const ARROW_HALF = 8;

type TooltipPlacement = NonNullable<AnimatedTooltipProps['placement']>;

type TooltipLayout = {
  arrowLeft: number | null;
  arrowTop: number | null;
  left: number;
  placement: TooltipPlacement;
  top: number;
};

function resolveTooltipMaxWidth(maxWidth: string): number {
  const pxMatch = /^(\d+(?:\.\d+)?)px$/.exec(maxWidth.trim());
  if (pxMatch) {
    return Number.parseFloat(pxMatch[1]);
  }
  return 280;
}

function clamp(value: number, min: number, max: number): number {
  if (max < min) return min;
  return Math.min(Math.max(value, min), max);
}

function normalizeTooltipRect(
  rect: DOMRect,
  node: HTMLDivElement,
  maxWidth: string,
): DOMRect {
  const fallbackWidth = resolveTooltipMaxWidth(maxWidth);
  const width = rect.width || node.offsetWidth || node.scrollWidth || fallbackWidth;
  const height = rect.height || node.offsetHeight || node.scrollHeight || 64;
  return {
    ...rect,
    bottom: rect.top + height,
    height,
    right: rect.left + width,
    width,
    x: rect.left,
    y: rect.top,
  } as DOMRect;
}

function resolvePlacement(
  preferred: TooltipPlacement,
  triggerRect: DOMRect,
  tooltipRect: DOMRect,
  autoFlip: boolean,
): TooltipPlacement {
  if (!autoFlip || typeof window === 'undefined') return preferred;

  if (
    preferred === 'top' &&
    triggerRect.top - tooltipRect.height - TOOLTIP_GAP < VIEWPORT_MARGIN
  ) {
    return 'bottom';
  }
  if (
    preferred === 'bottom' &&
    triggerRect.bottom + tooltipRect.height + TOOLTIP_GAP >
      window.innerHeight - VIEWPORT_MARGIN
  ) {
    return 'top';
  }
  if (
    preferred === 'left' &&
    triggerRect.left - tooltipRect.width - TOOLTIP_GAP < VIEWPORT_MARGIN
  ) {
    return 'right';
  }
  if (
    preferred === 'right' &&
    triggerRect.right + tooltipRect.width + TOOLTIP_GAP >
      window.innerWidth - VIEWPORT_MARGIN
  ) {
    return 'left';
  }

  return preferred;
}

export function computeTooltipLayout(
  preferredPlacement: TooltipPlacement,
  triggerRect: DOMRect,
  tooltipRect: DOMRect,
  autoFlip: boolean,
): TooltipLayout {
  const placement = resolvePlacement(
    preferredPlacement,
    triggerRect,
    tooltipRect,
    autoFlip,
  );
  const viewportWidth =
    typeof window === 'undefined' ? tooltipRect.width : window.innerWidth;
  const viewportHeight =
    typeof window === 'undefined' ? tooltipRect.height : window.innerHeight;
  const triggerCenterX = triggerRect.left + triggerRect.width / 2;
  const triggerCenterY = triggerRect.top + triggerRect.height / 2;

  if (placement === 'top' || placement === 'bottom') {
    const top =
      placement === 'top'
        ? triggerRect.top - tooltipRect.height - TOOLTIP_GAP
        : triggerRect.bottom + TOOLTIP_GAP;
    const left = clamp(
      triggerCenterX - tooltipRect.width / 2,
      VIEWPORT_MARGIN,
      viewportWidth - tooltipRect.width - VIEWPORT_MARGIN,
    );
    const arrowLeft = clamp(
      triggerCenterX - left - ARROW_HALF,
      12,
      tooltipRect.width - 12 - ARROW_HALF * 2,
    );
    return {
      arrowLeft,
      arrowTop: null,
      left,
      placement,
      top: clamp(
        top,
        VIEWPORT_MARGIN,
        viewportHeight - tooltipRect.height - VIEWPORT_MARGIN,
      ),
    };
  }

  const left =
    placement === 'left'
      ? triggerRect.left - tooltipRect.width - TOOLTIP_GAP
      : triggerRect.right + TOOLTIP_GAP;
  const top = clamp(
    triggerCenterY - tooltipRect.height / 2,
    VIEWPORT_MARGIN,
    viewportHeight - tooltipRect.height - VIEWPORT_MARGIN,
  );
  const arrowTop = clamp(
    triggerCenterY - top - ARROW_HALF,
    12,
    tooltipRect.height - 12 - ARROW_HALF * 2,
  );
  return {
    arrowLeft: null,
    arrowTop,
    left: clamp(
      left,
      VIEWPORT_MARGIN,
      viewportWidth - tooltipRect.width - VIEWPORT_MARGIN,
    ),
    placement,
    top,
  };
}

function arrowClassName(placement: TooltipPlacement): string {
  if (placement === 'top') {
    return 'top-full border-l-transparent border-r-transparent border-b-transparent border-t-surface';
  }
  if (placement === 'bottom') {
    return 'bottom-full border-l-transparent border-r-transparent border-t-transparent border-b-surface';
  }
  if (placement === 'left') {
    return 'right-0 translate-x-full border-t-transparent border-b-transparent border-r-transparent border-l-surface';
  }
  return 'left-0 -translate-x-full border-t-transparent border-b-transparent border-l-transparent border-r-surface';
}

export function AnimatedTooltip({
  children,
  content,
  forceShow = false,
  placement = 'top',
  maxWidth = '280px',
  delayMs = 400,
  triggerClassName = '',
  focusable = false,
  tapToToggle = false,
  autoFlip = false,
}: AnimatedTooltipProps) {
  const [mounted, setMounted] = useState(false);
  const [visible, setVisible] = useState(false);
  const [touchVisible, setTouchVisible] = useState(false);
  const [tooltipLayout, setTooltipLayout] = useState<TooltipLayout | null>(null);
  const [triggerNode, setTriggerNode] = useState<HTMLDivElement | null>(null);
  const [tooltipNode, setTooltipNode] = useState<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = (forceShow && content) || visible || touchVisible;

  const scheduleShow = () => {
    if (!content) return;
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setVisible(true), delayMs);
  };

  const scheduleHide = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setVisible(false);
  };

  const closeAll = () => {
    scheduleHide();
    setTouchVisible(false);
  };

  const handleBlur = () => {
    closeAll();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') closeAll();
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!tapToToggle || !content) return;
    if (event.pointerType !== 'touch' && event.pointerType !== 'pen') return;
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setTouchVisible((current) => !current);
  };

  const handleTriggerRef = useCallback((node: HTMLDivElement | null) => {
    triggerRef.current = node;
    setTriggerNode(node);
  }, []);

  const handleTooltipRef = useCallback((node: HTMLDivElement | null) => {
    tooltipRef.current = node;
    setTooltipNode(node);
  }, []);

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  useEffect(() => {
    if (!touchVisible) return;
    const handleDocumentPointerDown = (event: PointerEvent) => {
      if (triggerRef.current?.contains(event.target as Node)) return;
      setTouchVisible(false);
    };
    document.addEventListener('pointerdown', handleDocumentPointerDown);
    return () => {
      document.removeEventListener('pointerdown', handleDocumentPointerDown);
    };
  }, [touchVisible]);

  useEffect(() => {
    if (show) return;
    setTooltipLayout(null);
  }, [show]);

  useLayoutEffect(() => {
    if (!show || !triggerNode || !tooltipNode) return;

    let frameId: number | null = null;

    const updateLayout = () => {
      const triggerRect = triggerRef.current?.getBoundingClientRect();
      const tooltipRect = tooltipRef.current?.getBoundingClientRect();
      if (!triggerRect || !tooltipRect || !tooltipRef.current) return;
      setTooltipLayout(
        computeTooltipLayout(
          placement,
          triggerRect,
          normalizeTooltipRect(tooltipRect, tooltipRef.current, maxWidth),
          autoFlip,
        ),
      );
    };

    updateLayout();
    frameId = window.requestAnimationFrame(updateLayout);
    window.addEventListener('resize', updateLayout);
    window.addEventListener('scroll', updateLayout, true);
    return () => {
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId);
      }
      window.removeEventListener('resize', updateLayout);
      window.removeEventListener('scroll', updateLayout, true);
    };
  }, [autoFlip, content, placement, show, tooltipNode, triggerNode]);

  if (!content) {
    return <>{children}</>;
  }

  const tooltipPortal =
    mounted && typeof document !== 'undefined'
      ? createPortal(
          <AnimatePresence>
            {show && (
              <motion.div
                ref={handleTooltipRef}
                role="tooltip"
                data-placement={tooltipLayout?.placement ?? placement}
                className="fixed z-[220] w-max max-w-[calc(100vw-2rem)] whitespace-normal break-words rounded-xl border border-border bg-surface px-3 py-2 text-sm text-text shadow-premium pointer-events-none"
                style={{
                  left: tooltipLayout?.left ?? -9999,
                  maxWidth,
                  minWidth: 'min(14rem, calc(100vw - 2rem))',
                  top: tooltipLayout?.top ?? -9999,
                  visibility: tooltipLayout ? 'visible' : 'hidden',
                  width: 'max-content',
                }}
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.96 }}
                transition={{ duration: 0.15, ease: [0.25, 0.1, 0.25, 1] }}
              >
                {content}
                <span
                  aria-hidden
                  className={`absolute h-0 w-0 border-4 ${arrowClassName(
                    tooltipLayout?.placement ?? placement,
                  )}`}
                  style={{
                    left:
                      tooltipLayout?.arrowLeft !== null &&
                      tooltipLayout?.arrowLeft !== undefined
                        ? tooltipLayout.arrowLeft
                        : undefined,
                    top:
                      tooltipLayout?.arrowTop !== null &&
                      tooltipLayout?.arrowTop !== undefined
                        ? tooltipLayout.arrowTop
                        : undefined,
                  }}
                />
              </motion.div>
            )}
          </AnimatePresence>,
          document.body,
        )
      : null;

  return (
    <>
      <div
        ref={handleTriggerRef}
        className={`relative inline-flex ${triggerClassName}`}
        onMouseEnter={scheduleShow}
        onMouseLeave={scheduleHide}
        onFocus={scheduleShow}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        onPointerDown={handlePointerDown}
        tabIndex={focusable ? 0 : undefined}
      >
        {children}
      </div>
      {tooltipPortal}
    </>
  );
}
