import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Option Chain SOP Analyzer",
  description: "Professional option-chain analysis following the Module 5 SOP.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto max-w-6xl px-4 py-6">
          <header className="mb-6 flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h1 className="text-xl font-semibold">
                Option Chain <span className="text-accent">SOP</span> Analyzer
              </h1>
              <p className="text-sm text-slate-400">
                Professional Scanning Sequence · NSE / BSE / MCX
              </p>
            </div>
            <span className="pill bg-slate-800 text-slate-300">Phase 1 · Engine v0.1</span>
          </header>
          {children}
          <footer className="mt-10 border-t border-slate-800 pt-4 text-xs text-slate-500">
            Educational analysis, not investment advice. Verdicts follow the
            Module 5 SOP and always include an invalidation level.
          </footer>
        </div>
      </body>
    </html>
  );
}
