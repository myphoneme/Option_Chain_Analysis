import type { Metadata } from "next";
import "./globals.css";
import { PortalShell } from "@/components/portal/PortalShell";

export const metadata: Metadata = {
  title: "Option Chain · QuantTrade",
  description: "Professional option-chain analysis following the Module 5 SOP.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <PortalShell>{children}</PortalShell>
      </body>
    </html>
  );
}
