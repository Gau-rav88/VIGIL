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
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 rounded-xl bg-slate-900/60 border border-slate-800">
        <div className="flex items-center space-x-1.5 w-full sm:w-auto">
          {(["ALL", "MICRO_SME", "LARGE_MID"] as const).map((tier) => (
            <button
              key={tier}
              onClick={() => setTierFilter(tier)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                tierFilter === tier
                  ? "bg-slate-800 text-emerald-400 border border-emerald-500/30"
                  : "text-slate-400 hover:text-slate-200"
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
          className="w-full sm:w-56 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500/50"
        />
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
        {filtered.map((t) => {
          const isCritical = t.status === "MANIPULATION_DETECTED";
          const isElevated = t.status === "ELEVATED";

          let borderClass = "border-slate-800/80 hover:border-slate-700 bg-slate-900/50";
          if (isCritical) {
            borderClass = "border-rose-500/60 bg-rose-950/20 shadow-lg shadow-rose-950/30 animate-pulse";
          } else if (isElevated) {
            borderClass = "border-amber-500/40 bg-amber-950/10";
          }

          return (
            <div
              key={t.symbol}
              onClick={() => onSelectTicker?.(t)}
              className={`p-3 rounded-xl border transition cursor-pointer flex flex-col justify-between h-28 relative overflow-hidden ${borderClass}`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="font-mono font-bold text-white text-xs block">{t.symbol}</span>
                  <span className="text-[10px] text-slate-400">{formatCurrency(t.price)}</span>
                </div>
                <span
                  className={`text-[10px] font-mono font-semibold ${
                    (t.change_pct ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {formatPct(t.change_pct ?? 0)}
                </span>
              </div>

              {/* MRS Meter */}
              <div className="space-y-1">
                <div className="flex justify-between text-[9px]">
                  <span className="text-slate-500">MRS</span>
                  <span
                    className={`font-mono font-bold ${
                      isCritical ? "text-rose-400" : isElevated ? "text-amber-400" : "text-slate-400"
                    }`}
                  >
                    {((t.mrs ?? t.mrs_score ?? 0) * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="w-full bg-slate-800/80 h-1.5 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      isCritical
                        ? "bg-rose-500"
                        : isElevated
                        ? "bg-amber-400"
                        : "bg-emerald-500/40"
                    }`}
                    style={{ width: `${Math.max(5, (t.mrs ?? t.mrs_score ?? 0) * 100)}%` }}
                  />
                </div>
              </div>

              <div className="flex justify-between items-center text-[9px] text-slate-500">
                <span>{(t.tier ?? "ALL").replace("_", " ")}</span>
                <span>{formatCompactNumber(t.volume_24h ?? t.volume ?? 0)} vol</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
export default Heatmap;
