/**
 * Root layout — clinical monitor typography.
 * IBM Plex Sans Condensed for labels, JetBrains Mono for numerics.
 * Fonts are loaded from Google Fonts via <link> so the build never depends on
 * network access at compile time.
 */
import type { Metadata } from "next";
import "./globals.scss";
import { AuthProvider } from "@/contexts/AuthContext";
import { AppShell } from "@/components/AppShell";

export const metadata: Metadata = {
  title: "SepNova — ICU Sepsis Monitor",
  description: "Bedside sepsis risk monitor — decision support, not diagnosis",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Condensed:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
