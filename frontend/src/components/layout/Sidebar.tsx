'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { createContext, useContext, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { useAuth } from '@/contexts/AuthContext';
/* -----------------------------------------------------------------------------
 * Types (Aceternity-style API)
 * ----------------------------------------------------------------------------- */

export interface SidebarLinkItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

export interface SidebarContextValue {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  pinned: boolean;
  setPinned: React.Dispatch<React.SetStateAction<boolean>>;
}

const SidebarContext = createContext<SidebarContextValue | null>(null);

function useSidebar() {
  const ctx = useContext(SidebarContext);
  if (!ctx) throw new Error('Sidebar components must be used within SidebarProvider');
  return ctx;
}

/* -----------------------------------------------------------------------------
 * Nav items (same as before)
 * ----------------------------------------------------------------------------- */

const baseNavItems: SidebarLinkItem[] = [
  {
    label: 'Findings',
    href: '/findings',
    icon: (
      <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
      </svg>
    ),
  },
  {
    label: 'Accounts',
    href: '/accounts',
    icon: (
      <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
      </svg>
    ),
  },
  {
    label: 'Settings',
    href: '/settings',
    icon: (
      <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    label: 'Top Risks',
    href: '/top-risks',
    icon: (
      <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6" />
      </svg>
    ),
  },
  {
    label: 'Exports',
    href: '/exports',
    icon: (
      <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M12 3v12m0 0l-4.5-4.5M12 15l4.5-4.5" />
      </svg>
    ),
  },
  {
    label: 'Help',
    href: '/help',
    icon: (
      <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 9.75a3.375 3.375 0 116.75 0c0 1.437-.852 2.674-2.078 3.208-.841.367-1.297 1.194-1.297 2.112v.18m-.75 3.75h1.5" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9 9 0 100-18 9 9 0 000 18z" />
      </svg>
    ),
  },
];

const tenantAdminNavItems: SidebarLinkItem[] = [
  {
    label: 'Audit Log',
    href: '/audit-log',
    icon: (
      <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 4.5h6m-9.75 3h13.5A1.5 1.5 0 0120.25 9v10.5A1.5 1.5 0 0118.75 21h-13.5A1.5 1.5 0 013.75 19.5V9A1.5 1.5 0 015.25 7.5z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 12h9m-9 3h6" />
      </svg>
    ),
  },
];

const saasAdminNavItems: SidebarLinkItem[] = [
  {
    label: 'Control Plane',
    href: '/admin/control-plane',
    icon: (
      <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 5.25h18M3 12h18M3 18.75h18M7.5 3v18m9-18v18" />
      </svg>
    ),
  },
  {
    label: 'Support Inbox',
    href: '/admin/help',
    icon: (
      <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 9.75a3.375 3.375 0 116.75 0c0 1.437-.852 2.674-2.078 3.208-.841.367-1.297 1.194-1.297 2.112v.18m-.75 3.75h1.5" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9 9 0 100-18 9 9 0 000 18z" />
      </svg>
    ),
  },
  {
    label: 'Admin',
    href: '/admin/tenants',
    icon: (
      <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 7.5h18M3 12h18M3 16.5h18M6 4.5v15m12-15v15" />
      </svg>
    ),
  },
];

function getNavItems(isSaasAdmin: boolean, isTenantAdmin: boolean): SidebarLinkItem[] {
  const navItems = isTenantAdmin ? [...baseNavItems, ...tenantAdminNavItems] : baseNavItems;
  if (!isSaasAdmin) return navItems;
  return [...navItems, ...saasAdminNavItems];
}

/* -----------------------------------------------------------------------------
 * SidebarProvider – wraps app and provides open/setOpen
 * ----------------------------------------------------------------------------- */

export interface SidebarProviderProps {
  children: React.ReactNode;
}

const SIDEBAR_PINNED_STORAGE_KEY = 'security-autopilot-sidebar-pinned';

export function SidebarProvider({ children }: SidebarProviderProps) {
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem(SIDEBAR_PINNED_STORAGE_KEY) === '1';
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(SIDEBAR_PINNED_STORAGE_KEY, pinned ? '1' : '0');
  }, [pinned]);

  const value: SidebarContextValue = { open, setOpen, pinned, setPinned };
  return (
    <SidebarContext.Provider value={value}>
      {children}
    </SidebarContext.Provider>
  );
}

/* -----------------------------------------------------------------------------
 * SidebarLink – single nav link with active state
 * ----------------------------------------------------------------------------- */

interface SidebarLinkProps {
  link: SidebarLinkItem;
  className?: string;
}

function SidebarLink({ link, className = '' }: SidebarLinkProps) {
  const pathname = usePathname();
  const isActive = pathname === link.href || pathname.startsWith(`${link.href}/`);

  return (
    <Link
      href={link.href}
      className={`
        flex items-center gap-3 px-3 py-2.5 rounded-xl
        transition-all duration-200 group
        ${isActive
          ? 'border border-transparent bg-[var(--control-hover)] text-text shadow-[0_18px_30px_-24px_rgba(15,23,42,0.28)]'
          : 'border border-transparent text-muted hover:border-[var(--border-strong)] hover:bg-[var(--control-hover)] hover:text-text'
        }
        ${className}
      `}
      title={link.label}
    >
      <span className={`transition-colors duration-200 ${isActive ? 'text-text' : 'text-muted group-hover:text-accent'}`}>{link.icon}</span>
      <span className="text-sm font-semibold whitespace-nowrap overflow-hidden text-ellipsis tracking-tight">
        {link.label}
      </span>
    </Link>
  );
}

/* -----------------------------------------------------------------------------
 * Desktop sidebar – expandable on hover (Aceternity-style)
 * ----------------------------------------------------------------------------- */

const SIDEBAR_WIDTH_COLLAPSED = 64;
const SIDEBAR_WIDTH_EXPANDED = 224;

function DesktopSidebarContent() {
  const { pinned, setPinned } = useSidebar();
  const { user } = useAuth();
  const [hovered, setHovered] = useState(false);
  const navItems = getNavItems(Boolean(user?.is_saas_admin), user?.role === 'admin');
  const expanded = hovered || pinned;

  return (
    <motion.aside
      className="fixed left-2 top-2 bottom-2 z-40 hidden overflow-hidden rounded-[2.5rem] border border-[var(--border-shell)] bg-[var(--shell)] shadow-[0_30px_60px_-28px_rgba(15,23,42,0.45)] backdrop-blur-2xl md:flex md:flex-col"
      initial={false}
      animate={{ width: expanded ? SIDEBAR_WIDTH_EXPANDED : SIDEBAR_WIDTH_COLLAPSED }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Brand mark only in both collapsed and expanded states. */}
      <div className="min-h-20 flex items-center justify-center shrink-0 px-2">
        <div className="h-16 w-16 shrink-0 flex items-center justify-center overflow-hidden relative">
          <AnimatePresence mode="wait">
            {expanded ? (
              <motion.div
                key="logo"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.2 }}
                className="absolute inset-0 flex items-center justify-center"
              >
                <img
                  src="/logo/ocypheris-icon.png"
                  alt=""
                  className="max-h-full max-w-full w-auto h-auto object-contain"
                />
              </motion.div>
            ) : (
              <motion.div
                key="favicon"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.2 }}
                className="absolute inset-0 flex items-center justify-center"
              >
                <img
                  src="/logo/ocypheris-icon.png"
                  alt=""
                  className="max-h-full max-w-full w-10 h-10 object-contain"
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-2 overflow-y-auto">
        {navItems.map((item) => (
          <SidebarLink key={item.href} link={item} />
        ))}
      </nav>

      {/* Bottom – pin sidebar only */}
      <div className="shrink-0 border-t border-border/35 p-3">
        <div className="flex items-center justify-end gap-1">
          <button
            type="button"
            onClick={() => setPinned((p) => !p)}
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-dropdown-bg ${pinned ? 'border-transparent bg-[var(--control-hover)] text-text shadow-[0_18px_28px_-24px_rgba(15,23,42,0.28)]' : 'border-transparent text-muted hover:border-border/70 hover:bg-[var(--control-hover)] hover:text-text'
              }`}
            title={pinned ? 'Unpin sidebar' : 'Pin sidebar open'}
            aria-label={pinned ? 'Unpin sidebar' : 'Pin sidebar open'}
          >
            <svg className="w-5 h-5 transition-transform duration-300" style={{ transform: pinned ? 'rotate(0deg)' : 'rotate(-90deg)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
            </svg>
          </button>
        </div>
      </div>
    </motion.aside>
  );
}

/* -----------------------------------------------------------------------------
 * Mobile sidebar – drawer opened by hamburger
 * ----------------------------------------------------------------------------- */

function MobileSidebarContent() {
  const { open, setOpen } = useSidebar();
  const { user } = useAuth();
  const navItems = getNavItems(Boolean(user?.is_saas_admin), user?.role === 'admin');

  return (
    <>
      {/* Hamburger – only on mobile */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed left-4 top-4 z-30 rounded-2xl border border-border/60 bg-[var(--shell)] p-2.5 text-text shadow-[0_20px_34px_-24px_rgba(15,23,42,0.48)] backdrop-blur-xl md:hidden"
        aria-label="Open menu"
      >
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
        </svg>
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              role="button"
              tabIndex={-1}
              aria-label="Close menu"
              className="fixed inset-0 z-40 bg-black/60 md:hidden backdrop-blur-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setOpen(false)}
              onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}
            />
            <motion.aside
              className="fixed left-2 top-2 bottom-2 z-50 flex w-64 flex-col overflow-hidden rounded-[2.5rem] border border-border/60 bg-[var(--shell)] shadow-[0_30px_60px_-28px_rgba(15,23,42,0.5)] backdrop-blur-2xl md:hidden"
              initial={{ x: -250 }}
              animate={{ x: 0 }}
              exit={{ x: -250 }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            >
              <div className="min-h-16 flex items-center justify-between px-6 border-b border-white/5 gap-2">
                <div className="h-10 w-10 shrink-0 flex items-center overflow-hidden">
                  <img src="/logo/ocypheris-icon.png" alt="" className="h-10 w-10 object-contain" />
                </div>
                <span className="flex-1 min-w-0" aria-hidden />
                <ThemeToggle />
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="p-2 rounded-xl text-muted hover:text-text hover:nm-raised-sm transition-all"
                  aria-label="Close menu"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <nav className="flex-1 p-3 space-y-2 overflow-y-auto">
                {navItems.map((item) => (
                  <SidebarLink key={item.href} link={item} />
                ))}
              </nav>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

/* -----------------------------------------------------------------------------
 * Sidebar – desktop + mobile (Aceternity-style)
 * ----------------------------------------------------------------------------- */

export function Sidebar() {
  return (
    <>
      <DesktopSidebarContent />
      <MobileSidebarContent />
    </>
  );
}

/* -----------------------------------------------------------------------------
 * Hook for main content – sidebar expanded width for layout offset
 * ----------------------------------------------------------------------------- */

export function useSidebarWidth(): number {
  return SIDEBAR_WIDTH_EXPANDED;
}

export const SIDEBAR_DESKTOP_WIDTH = SIDEBAR_WIDTH_EXPANDED;
export const SIDEBAR_COLLAPSED_WIDTH = SIDEBAR_WIDTH_COLLAPSED;
