"use client";

import React, { useState } from "react";
import { usePathname } from "next/navigation";
import { Activity, ShieldAlert, ShieldCheck, Zap, HeartPulse, ChevronLeft, ChevronRight, LucideIcon } from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  devOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/live", label: "Live Monitor", icon: Activity },
  { href: "/cases", label: "Cases", icon: ShieldAlert },
  { href: "/verify", label: "Verify Bundle", icon: ShieldCheck },
  { href: "/simulator", label: "Simulator", icon: Zap, devOnly: true },
  { href: "/admin/health", label: "Admin Health", icon: HeartPulse },
];

export function Rail() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`border-r border-line bg-bg-raised text-ink transition-all duration-200 flex flex-col justify-between select-none ${
        collapsed ? "w-14" : "w-52"
      }`}
    >
      <div>
        {/* Brand Header */}
        <div className="h-12 border-b border-line px-4 flex items-center justify-between">
          <a href="/live" className="flex items-center space-x-2.5">
            <div className="h-6 w-6 rounded-cell bg-ink text-bg-raised flex items-center justify-center font-bold text-xs">
              V
            </div>
            {!collapsed && (
              <span className="font-bold tracking-wider text-xs uppercase text-ink">
                Project VIGIL
              </span>
            )}
          </a>
        </div>

        {/* Navigation Items */}
        <nav className="p-2 space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = pathname.startsWith(item.href);

            return (
              <a
                key={item.href}
                href={item.href}
                className={`flex items-center space-x-3 px-3 py-2 rounded-cell text-xs transition relative ${
                  isActive
                    ? "font-bold text-ink bg-bg-sunken"
                    : "text-ink-muted hover:text-ink hover:bg-bg-sunken/60"
                }`}
                title={collapsed ? item.label : undefined}
              >
                {isActive && (
                  <span className="absolute left-0 top-1 bottom-1 w-0.5 bg-ink rounded-r" />
                )}
                <Icon className="h-4 w-4 shrink-0" strokeWidth={1.75} />
                {!collapsed && <span>{item.label}</span>}
              </a>
            );
          })}
        </nav>
      </div>

      {/* Collapse Toggle Footer */}
      <div className="p-2 border-t border-line flex justify-end">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-cell hover:bg-bg-sunken text-ink-muted hover:text-ink transition"
          title={collapsed ? "Expand rail" : "Collapse rail"}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>
    </aside>
  );
}
export default Rail;
