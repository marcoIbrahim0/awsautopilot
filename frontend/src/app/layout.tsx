import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { AuthProvider } from "@/contexts/AuthContext";
import { BackgroundJobsProvider } from "@/contexts/BackgroundJobsContext";
import { NotificationCenterProvider } from "@/contexts/NotificationCenterContext";
import { ThemeProvider } from "@/components/ThemeProvider";
import { PageTransition } from "@/components/PageTransition";
import { NavigationFeedback } from "@/components/NavigationFeedback";
import { LanguageProvider } from "@/lib/i18n";
import { FloatingChat } from "@/components/help/FloatingChat";

export const metadata: Metadata = {
  title: "AWS Security Autopilot",
  description: "Secure AWS quickly, stay secure with minimal weekly effort.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@400;600&family=Space+Grotesk:wght@600&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet" />
        <script
          dangerouslySetInnerHTML={{
            __html: "window.__name = window.__name || ((fn) => fn);",
          }}
        />
      </head>
      <body
        className="m-0 antialiased min-h-screen bg-bg text-text"
        suppressHydrationWarning
      >
        <LanguageProvider>
          <ThemeProvider>
            <AuthProvider>
              <BackgroundJobsProvider>
                <NotificationCenterProvider>
                  <Suspense fallback={null}>
                    <NavigationFeedback />
                  </Suspense>
                  <PageTransition>{children}</PageTransition>
                  <FloatingChat />
                </NotificationCenterProvider>
              </BackgroundJobsProvider>
            </AuthProvider>
          </ThemeProvider>
        </LanguageProvider>
      </body>
    </html>
  );
}
