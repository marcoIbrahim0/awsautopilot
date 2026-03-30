'use client';

import { forwardRef } from 'react';
import Link from 'next/link';

import { NotificationCenterPanel } from '@/components/layout/NotificationCenterPanel';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/DropdownMenu';
import { useAuth } from '@/contexts/AuthContext';
import { useNotificationCenter } from '@/contexts/NotificationCenterContext';

interface TopBarProps {
  title?: string;
}


const BellButton = forwardRef<
  HTMLButtonElement,
  {
    unreadCount: number;
    active: boolean;
    ariaLabel: string;
    onClick?: () => void;
    expanded?: boolean;
  }
>(function BellButton({ unreadCount, active, ariaLabel, onClick, expanded, ...props }, ref) {
  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      aria-expanded={expanded}
      {...props}
      className="relative flex min-h-11 min-w-11 items-center justify-center rounded-2xl border border-transparent p-2.5 text-muted transition-all hover:border-[var(--border-strong)] hover:bg-[var(--control-hover)] hover:text-accent"
    >
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
      </svg>
      {active ? (
        <span className="absolute right-0.5 top-0.5 inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-accent px-1 text-[11px] font-semibold text-white">
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      ) : null}
    </button>
  );
});

BellButton.displayName = 'BellButton';


export function TopBar({ title }: TopBarProps) {
  const { user, isAuthenticated, logout } = useAuth();
  const {
    items,
    isLoading,
    isOpen,
    unreadCount,
    activeJobCount,
    error,
    setOpen,
    markAllRead,
    archiveNotification,
  } = useNotificationCenter();
  const initial = user?.name?.charAt(0)?.toUpperCase() ?? user?.email?.charAt(0)?.toUpperCase() ?? 'U';
  const hasNotificationDot = unreadCount > 0 || activeJobCount > 0;

  return (
    <header className="sticky top-3 z-30 mx-3 mb-2 mt-3 flex h-16 items-center justify-between overflow-hidden rounded-[2rem] border border-[var(--border-shell)] bg-[var(--shell)] px-4 shadow-[0_24px_42px_-28px_rgba(15,23,42,0.46)] backdrop-blur-2xl md:mx-4 md:mt-4 md:h-20 md:rounded-[2.5rem] md:px-8">
      <div className="flex items-center gap-4">
        {title ? <h1 className="text-base font-semibold tracking-tight text-text md:text-lg">{title}</h1> : null}
      </div>

      <div className="flex items-center gap-2">
        <ThemeToggle />

        <div className="hidden md:block">
          <DropdownMenu open={isOpen} onOpenChange={setOpen}>
            <DropdownMenuTrigger asChild>
              <BellButton unreadCount={unreadCount} active={hasNotificationDot} ariaLabel="Notifications" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-[24rem] overflow-hidden rounded-[1.75rem] p-0">
              <NotificationCenterPanel
                items={items}
                isLoading={isLoading}
                error={error}
                unreadCount={unreadCount}
                onMarkAllRead={markAllRead}
                onArchive={archiveNotification}
              />
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="md:hidden">
          <BellButton
            unreadCount={unreadCount}
            active={hasNotificationDot}
            ariaLabel="Open notifications"
            onClick={() => setOpen(!isOpen)}
            expanded={isOpen}
          />
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className="flex min-h-11 items-center gap-2 rounded-2xl border border-transparent p-1.5 outline-none transition-all hover:border-[var(--border-strong)] hover:bg-[var(--control-hover)] focus:ring-2 focus:ring-offset-2 focus:ring-offset-dropdown-bg focus:ring-ring"
              aria-label="Profile menu"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent/20 text-sm font-medium text-accent">
                {initial}
              </div>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-40">
            <DropdownMenuLabel className="text-muted font-normal">
              {isAuthenticated && user ? (
                <>
                  <p className="font-medium text-text">{user.name || user.email}</p>
                  <p className="mt-0.5 truncate text-xs">{user.email}</p>
                </>
              ) : (
                'Account'
              )}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/settings" className="cursor-pointer">
                Settings
              </Link>
            </DropdownMenuItem>
            {isAuthenticated ? (
              <DropdownMenuItem
                onSelect={() => logout()}
                className="cursor-pointer text-danger focus:bg-danger/10 focus:text-danger"
              >
                Log out
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem asChild>
                <Link href="/login" className="cursor-pointer">
                  Sign in
                </Link>
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {isOpen ? (
        <div className="fixed inset-0 z-40 bg-black/35 backdrop-blur-[1px] md:hidden">
          <div className="absolute inset-x-0 bottom-0 max-h-[85vh] rounded-t-[2rem] border border-[var(--border-shell)] bg-dropdown-bg shadow-2xl">
            <NotificationCenterPanel
              items={items}
              isLoading={isLoading}
              error={error}
              unreadCount={unreadCount}
              onMarkAllRead={markAllRead}
              onArchive={archiveNotification}
              onClose={() => setOpen(false)}
            />
          </div>
        </div>
      ) : null}
    </header>
  );
}
