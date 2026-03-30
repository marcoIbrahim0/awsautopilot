'use client';

import { ThemeProvider as NextThemesProvider } from 'next-themes';

import { usePathname } from 'next/navigation';

interface ThemeProviderProps {
  children: React.ReactNode;
}

/**
 * Wraps the app with next-themes ThemeProvider.
 * Uses class strategy so Tailwind dark: variant and our .dark CSS variables apply.
 */
export function ThemeProvider({ children }: ThemeProviderProps) {
  const pathname = usePathname();
  const isLandingPage = pathname === '/landing' || pathname === '/';

  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      storageKey="security-autopilot-theme"
      enableColorScheme
      forcedTheme={isLandingPage ? 'light' : undefined}
    >
      {children}
    </NextThemesProvider>
  );
}
