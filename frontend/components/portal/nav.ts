/**
 * QuantTrade portal navigation, ported from
 * myphoneme/quant-trade → client/src/components/layout/Sidebar.tsx
 *
 * This app runs as its own service behind nginx at `${PORTAL_BASE}/optionchain`
 * (see deploy.sh), so the portal chrome is reproduced here and the Option Chain
 * route renders as a native portal page instead of a detached one.
 *
 * Keep this list in step with the portal's `navItems`.
 */

export const PORTAL_BASE =
  process.env.NEXT_PUBLIC_PORTAL_BASE || "https://quanttrade.phoneme.in";

export type IconName =
  | "dashboard" | "vault" | "sop" | "analysis"
  | "volume" | "optionchain" | "api" | "xtstest";

export interface NavItem {
  label: string;
  href: string;
  icon: IconName;
  /** Route this application owns — rendered as the active pill. */
  current?: boolean;
  /** Opens outside the portal shell. */
  external?: boolean;
  devOnly?: boolean;
}

/** The portal drives these by SPA state; from here they are plain links. */
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: `${PORTAL_BASE}/`, icon: "dashboard" },
  { label: "Accounts Vault", href: `${PORTAL_BASE}/`, icon: "vault" },
  { label: "Morning SOP", href: `${PORTAL_BASE}/`, icon: "sop" },
  { label: "Analysis", href: `${PORTAL_BASE}/`, icon: "analysis" },
  { label: "Volume Analysis", href: `${PORTAL_BASE}/`, icon: "volume" },
  { label: "Option Chain", href: `${PORTAL_BASE}/optionchain`, icon: "optionchain", current: true },
  {
    label: "Option Chain API",
    href: "https://quantapi.phoneme.in/optionchain/docs",
    icon: "api",
    external: true,
  },
  { label: "XTS API Test", href: `${PORTAL_BASE}/`, icon: "xtstest", devOnly: true },
];
