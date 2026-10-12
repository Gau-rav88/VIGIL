"use client";

import React, { useState, useEffect, useMemo } from "react";
import { usePathname } from "next/navigation";
import { Activity, ShieldAlert, ShieldCheck, Zap, HeartPulse, ChevronLeft, ChevronRight, LucideIcon, Shield } from "lucide-react";
import { getRole, getRoleCapabilities } from "@/lib/auth";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export function Rail() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [role, setRoleState] = useState(getRole());

  useEffect(() => {
    setRoleState(getRole());
    const handler = () => setRoleState(getRole());
    window.addEventListener("vigil-role-changed", handler);
    return () => window.removeEventListener("vigil-role-changed", handler);
  }, []);

  const caps = getRoleCapabilities(role);

  const roleNavItems = useMemo<NavItem[]>(() => {
    switch (role) {
      case "investigator":
        return [
          { href: "/live", label: "Live Watch Floor", icon: Activity },
          { href: "/cases", label: "Investigation Queue", icon: ShieldAlert },
        ];
      case "compliance_officer":
        return [
          { href: "/cases", label: "Compliance Queue", icon: ShieldAlert },
          { href: "/verify", label: "Verify Bundle", icon: ShieldCheck },
          { href: "/live", label: "Live Monitor", icon: Activity },
        ];
      case "admin":
        return [
          { href: "/simulator", label: "Simulator Engine", icon: Zap },
          { href: "/admin/health", label: "System Health", icon: HeartPulse },
          { href: "/cases", label: "All Cases", icon: ShieldAlert },
          { href: "/live", label: "Live Monitor", icon: Activity },
        ];
      case "auditor_readonly":
        return [
          { href: "/verify", label: "Verify Ledger", icon: ShieldCheck },
          { href: "/cases", label: "Case Records", icon: ShieldAlert },
          { href: "/live", label: "Live Monitor", icon: Activity },
        ];
      default:
        return [
          { href: "/live", label: "Live Monitor", icon: Activity },
          { href: "/cases", label: "Cases", icon: ShieldAlert },
        ];
    }
  }, [role]);

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

        {/* Navigation Items Filtered by Role */}
        <nav className="p-2 space-y-1">
          {roleNavItems.map((item) => {
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

      {/* Footer Area: Active Role Card + Collapse Toggle */}
      <div className="border-t border-line p-2 space-y-2">
        {!collapsed ? (
          <div className="p-2.5 rounded-cell bg-bg-sunken border border-line text-xs space-y-1">
            <div className="flex items-center justify-between text-[10px] text-ink-muted uppercase tracking-wider font-semibold">
              <span className="flex items-center gap-1">
                <Shield className="h-3 w-3 text-ink-muted" />
                <span>Persona</span>
              </span>
              <span className="w-1.5 h-1.5 rounded-full bg-verified" />
            </div>
            <div className="font-mono font-bold text-[11px] text-ink truncate">
              {caps.label}
            </div>
            <div className="text-[10px] text-ink-muted leading-tight line-clamp-2">
              {caps.description}
            </div>
          </div>
        ) : (
          <div className="flex justify-center py-1" title={`${caps.label}: ${caps.description}`}>
            <span className="w-2.5 h-2.5 rounded-full bg-verified" />
          </div>
        )}

        <div className="flex justify-end">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1.5 rounded-cell hover:bg-bg-sunken text-ink-muted hover:text-ink transition"
            title={collapsed ? "Expand rail" : "Collapse rail"}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </aside>
  );
}
export default Rail;
