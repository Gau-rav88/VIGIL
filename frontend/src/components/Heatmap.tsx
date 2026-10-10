"use client";

import React, { useState } from "react";
import { TickerData } from "@/lib/api";
import { formatCurrency, formatPct, formatCompactNumber } from "@/lib/format";

interface HeatmapProps {
  tickers: TickerData[];
  onSelectTicker?: (ticker: TickerData) => void;
}

export function Heatmap({ tickers, onSelectTicker }: HeatmapProps) {
  const [tierFilter, setTierFilter] = useState<"ALL" | "MICRO_SME" | "LARGE_MID">("ALL");
  const [search, setSearch] = useState("");

  const filtered = tickers.filter((t) => {
    const matchesTier = tierFilter === "ALL" || t.tier === tierFilter;
    const matchesSearch = t.symbol.toLowerCase().includes(search.toLowerCase());
    return matchesTier && matchesSearch;
  });

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 rounded-panel bg-bg-raised border border-line">
        <div className="flex items-center space-x-1.5 w-full sm:w-auto">
          {(["ALL", "MICRO_SME", "LARGE_MID"] as const).map((tier) => (
            <button
              key={tier}
              onClick={() => setTierFilter(tier)}
              className={`px-3 py-1.5 rounded-cell text-xs font-semibold transition ${
                tierFilter === tier
                  ? "bg-bg-sunken text-verified border border-verified"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              {tier === "ALL" ? "All (40)" : tier === "MICRO_SME" ? "SME / Micro (10)" : "Large / Mid (30)"}
            </button>
          ))}
        </div>

        <input
          type="text"
          placeholder="Filter ticker..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:w-56 bg-bg-base border border-line rounded-cell px-3 py-1.5 text-xs text-ink placeholder:text-ink-faint focus:outline-none focus:border-focus"
        />
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
        {filtered.map((t) => {
          const isCritical = t.status === "MANIPULATION_DETECTED";
          const isElevated = t.status === "ELEVATED";

          let borderClass = "border-line hover:border-line-strong bg-bg-raised";
          if (isCritical) {
            borderClass = "border-seal bg-seal-wash shadow-pop animate-pulse";
          } else if (isElevated) {
            borderClass = "border-tag bg-tag-wash";
          }

          return (
            <div
              key={t.symbol}
              onClick={() => onSelectTicker?.(t)}
              className={`p-3 rounded-panel border transition cursor-pointer flex flex-col justify-between h-28 relative overflow-hidden ${borderClass}`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="font-mono font-bold text-ink text-xs block">{t.symbol}</span>
                  <span className="text-[10px] text-ink-muted">{formatCurrency(t.price)}</span>
                </div>
                <span
                  className={`text-[10px] font-mono font-semibold ${
                    (t.change_pct ?? 0) >= 0 ? "text-verified" : "text-seal"
                  }`}
                >
                  {formatPct(t.change_pct ?? 0)}
                </span>
              </div>

              {/* MRS Meter */}
              <div className="space-y-1">
                <div className="flex justify-between text-[9px]">
                  <span className="text-ink-muted">MRS</span>
                  <span
                    className={`font-mono font-bold ${
                      isCritical ? "text-seal" : isElevated ? "text-tag-ink" : "text-ink-muted"
                    }`}
                  >
                    {((t.mrs ?? 0) * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="w-full bg-bg-sunken h-1.5 rounded-chip overflow-hidden">
                  <div
                    className={`h-full rounded-chip transition-all duration-500 ${
                      isCritical
                        ? "bg-seal"
                        : isElevated
                        ? "bg-tag"
                        : "bg-verified"
                    }`}
                    style={{ width: `${Math.max(5, (t.mrs ?? 0) * 100)}%` }}
                  />
                </div>
              </div>

              <div className="flex justify-between items-center text-[9px] text-ink-muted">
                <span>{(t.tier ?? "ALL").replace("_", " ")}</span>
                <span>{formatCompactNumber(t.volume_24h ?? 0)} vol</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
export default Heatmap;
