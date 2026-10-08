import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VIGIL | Capital-Market Forensic Intelligence",
  description: "Autonomous Multi-Agent Forensic Intelligence Platform for Market Manipulation",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-[#090d16] text-slate-100">
        <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-xl font-bold tracking-wider text-emerald-400">VIGIL</span>
            <span className="text-xs text-slate-400 border border-slate-700 rounded px-2 py-0.5">FORENSIC SUITE</span>
          </div>
          <nav className="flex space-x-6 text-sm text-slate-300">
            <a href="/live" className="hover:text-emerald-400 transition">Live Monitor</a>
            <a href="/cases" className="hover:text-emerald-400 transition">Case Workbench</a>
            <a href="/verify" className="hover:text-emerald-400 transition">Bundle Verifier</a>
          </nav>
        </header>
        <main className="p-6">{children}</main>
      </body>
    </html>
  );
}
