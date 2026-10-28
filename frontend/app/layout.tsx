import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { AppShell } from "@/components/AppShell";
import { AuthProvider } from "@/lib/auth";
import { I18nProvider } from "@/lib/i18n";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "JUSTICE AI", template: "%s · JUSTICE AI" },
  description: "Understand your legal rights in India, organise your situation and prepare for a lawyer.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#14213d" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <I18nProvider>
          <AuthProvider>
            <AppShell>{children}</AppShell>
          </AuthProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
