import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/shell/AppShell";

export const metadata: Metadata = {
  title: "VIGIL | Autonomous Forensic Intelligence Platform",
  description: "Autonomous Multi-Agent Intelligence for Capital-Market Surveillance & Manipulation Detection",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-bg-base text-ink selection:bg-uv-wash selection:text-uv">
        <a href="#main" className="sr-only focus:not-sr-only">Skip to content</a>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}

