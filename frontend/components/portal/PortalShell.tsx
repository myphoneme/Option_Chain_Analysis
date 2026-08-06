"use client";

import { useEffect, useState } from "react";
import {
  BarChart3,
  CandlestickChart,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  FlaskConical,
  Globe,
  Layers,
  LayoutDashboard,
  Link as LinkIcon,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  TrendingUp,
} from "lucide-react";

import { fetchMeta } from "@/lib/api";
import { NAV_ITEMS, PORTAL_BASE, type IconName, type NavItem } from "./nav";

const ICONS: Record<IconName, React.ElementType> = {
  dashboard: LayoutDashboard,
  vault: LinkIcon,
  sop: CheckCircle2,
  analysis: BarChart3,
  volume: CandlestickChart,
  optionchain: Layers,
  api: Globe,
  xtstest: FlaskConical,
};

/**
 * Reproduces the QuantTrade portal chrome (sidebar + header) around this app,
 * ported from myphoneme/quant-trade so /optionchain looks like a portal page.
 */
export function PortalShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    // Remember the user's preference, matching portal behaviour.
    const saved = localStorage.getItem("qt_sidebar_collapsed");
    if (saved) setCollapsed(saved === "1");
    fetchMeta()
      .then((m) => setVersion(m.engine_version ?? null))
      .catch(() => setVersion(null));
  }, []);

  function toggle() {
    setCollapsed((c) => {
      localStorage.setItem("qt_sidebar_collapsed", !c ? "1" : "0");
      return !c;
    });
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar collapsed={collapsed} onToggle={toggle} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header collapsed={collapsed} onToggle={toggle} version={version} />
        <main className="flex-1 space-y-6 p-6">{children}</main>
        <footer className="px-6 pb-6 pt-2 text-xs text-slate-600">
          Educational analysis, not investment advice. Verdicts follow the Module 5 SOP
          and always include an invalidation level.
        </footer>
      </div>
    </div>
  );
}

function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  return (
    <aside
      className={`${collapsed ? "w-16" : "w-72"} sticky top-0 flex h-screen shrink-0 flex-col border-r border-slate-800 bg-slate-900/50 transition-all duration-300`}
    >
      {/* Logo */}
      <div
        className={`flex items-center border-b border-slate-800 p-5 ${collapsed ? "justify-center" : "gap-3"}`}
      >
        <div className="pill-shadow flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-500">
          <TrendingUp size={20} className="text-white" />
        </div>
        {!collapsed && (
          <span className="text-xl font-bold tracking-tight text-white">
            QUANT<span className="text-brand-500">TRADE</span>
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="custom-scrollbar flex-1 space-y-1 overflow-y-auto p-3">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.label} item={item} collapsed={collapsed} />
        ))}
      </nav>

      {/* Sign out + collapse */}
      <div className="space-y-2 border-t border-slate-800 p-3">
        <a
          href={PORTAL_BASE}
          title="Sign out"
          className={`flex w-full items-center rounded-xl px-3 py-2 text-slate-400 transition-all hover:bg-slate-800 hover:text-red-400 ${collapsed ? "justify-center" : "gap-3"}`}
        >
          <LogOut size={18} className="shrink-0" />
          {!collapsed && <span className="text-sm font-medium">Sign Out</span>}
        </a>

        <button
          onClick={onToggle}
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          className="flex w-full items-center justify-center rounded-xl py-2 text-slate-600 transition-all hover:text-slate-400"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  );
}

function NavLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const Icon = ICONS[item.icon];
  const base = `w-full flex items-center ${collapsed ? "justify-center" : "gap-3"} px-3 py-3 rounded-xl transition-all`;
  const tone = item.current
    ? "bg-brand-500 text-white pill-shadow"
    : item.devOnly
    ? "text-slate-600 hover:bg-slate-800 hover:text-slate-400"
    : "text-slate-400 hover:bg-slate-800 hover:text-slate-200";

  return (
    <a
      href={item.href}
      title={collapsed ? item.label : undefined}
      aria-current={item.current ? "page" : undefined}
      {...(item.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      className={`${base} ${tone}`}
    >
      <Icon size={20} className="shrink-0" />
      {!collapsed && (
        <span className="flex items-center gap-2 text-sm font-medium">
          {item.label}
          {item.external && <ExternalLink size={12} className="shrink-0 opacity-50" />}
          {item.devOnly && !item.current && (
            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[9px] font-bold tracking-wide text-slate-500">
              DEV
            </span>
          )}
        </span>
      )}
    </a>
  );
}

function Header({
  collapsed,
  onToggle,
  version,
}: {
  collapsed: boolean;
  onToggle: () => void;
  version: string | null;
}) {
  return (
    <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-800 bg-[#0F172A]/90 px-6 py-3 backdrop-blur-sm">
      <div className="flex min-w-0 items-center gap-3">
        <button
          onClick={onToggle}
          title={collapsed ? "Show navigation" : "Hide navigation"}
          aria-label={collapsed ? "Show navigation" : "Hide navigation"}
          className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-800 hover:text-white"
        >
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </button>
        <div>
          <h1 className="text-xl font-bold text-white">Option Chain</h1>
          <p className="mt-0.5 text-xs text-slate-500">
            Professional Scanning Sequence · NSE / BSE / MCX
          </p>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-xs font-medium text-slate-500">
          Engine v{version ?? "…"}
        </span>
      </div>
    </header>
  );
}
