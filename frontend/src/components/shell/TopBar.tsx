"use client";

import React, { useState, useEffect } from "react";
import { ConnectionStatus } from "./ConnectionStatus";
import { Search, Globe, Moon, Sun, Sliders } from "lucide-react";

interface TopBarProps {
  onSearch?: (query: string) => void;
}

export function TopBar({ onSearch }: TopBarProps) {
  const [tz, setTz] = useState<"IST" | "UTC">("IST");
  const [theme, setTheme] = useState<"standard" | "floor">("standard");
  const [density, setDensity] = useState<"compact" | "comfortable">("compact");

  const toggleTheme = () => {
    const next = theme === "standard" ? "floor" : "standard";
    setTheme(next);
    if (next === "floor") {
      document.documentElement.setAttribute("data-theme", "floor");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  };

  const toggleDensity = () => {
    const next = density === "compact" ? "comfortable" : "compact";
    setDensity(next);
    if (next === "comfortable") {
      document.documentElement.setAttribute("data-density", "comfortable");
    } else {
      document.documentElement.removeAttribute("data-density");
    }
  };

  // Keyboard shortcut '/' to focus search & URL theme param support
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      if (params.get("theme") === "floor") {
        setTheme("floor");
        document.documentElement.setAttribute("data-theme", "floor");
      }
    }

    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
        e.preventDefault();
        document.getElementById("global-search-input")?.focus();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  return (
    <header className="h-12 border-b border-line bg-bg-raised text-ink px-4 flex items-center justify-between sticky top-0 z-50">
      {/* Left Search */}
      <div className="flex items-center space-x-3 w-72">
        <div className="relative w-full">
          <Search className="h-3.5 w-3.5 text-ink-muted absolute left-2.5 top-2.5" />
          <input
            id="global-search-input"
            type="text"
            placeholder="Search cases, tickers, accounts... ( / )"
            onChange={(e) => onSearch?.(e.target.value)}
            className="w-full bg-bg-sunken border border-line rounded-cell pl-8 pr-3 py-1.5 text-xs text-ink placeholder:text-ink-muted focus:outline-none focus:border-uv"
          />
        </div>
      </div>

      {/* Center-Right Status */}
      <div className="flex items-center space-x-4">
        <ConnectionStatus lagMs={120} status="live" />

        <div className="h-4 w-px bg-line" />

        {/* Timezone Switch */}
        <button
          onClick={() => setTz(tz === "IST" ? "UTC" : "IST")}
          className="flex items-center space-x-1.5 text-xs text-ink-muted hover:text-ink px-2 py-1 rounded-cell transition font-mono"
          title="Toggle timezone"
        >
          <Globe className="h-3.5 w-3.5" />
          <span>{tz === "IST" ? "IST (Exchange)" : "UTC"}</span>
        </button>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="text-ink-muted hover:text-ink p-1 rounded-cell transition"
          title={`Switch to ${theme === "standard" ? "Deep bench (dark)" : "Standard (light)"}`}
        >
          {theme === "standard" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
        </button>

        {/* Density Toggle */}
        <button
          onClick={toggleDensity}
          className="text-ink-muted hover:text-ink p-1 rounded-cell transition"
          title={`Switch row density (currently ${density})`}
        >
          <Sliders className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
export default TopBar;
