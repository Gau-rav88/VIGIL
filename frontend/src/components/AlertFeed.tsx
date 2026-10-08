"use client";

import React from "react";
import { AlertData } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { AlertTriangle, ArrowUpRight } from "lucide-react";

interface AlertFeedProps {
  alerts: AlertData[];
  onInvestigate?: (symbol: string) => void;
}

export function AlertFeed({ alerts, onInvestigate }: AlertFeedProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs text-slate-300 font-semibold uppercase tracking-wider px-1">
        <span className="flex items-center gap-1.5">
          <AlertTriangle className="h-4 w-4 text-rose-400" />
          Real-Time Forensic Alerts
        </span>
        <span className="font-mono text-emerald-400 text-[11px]">{alerts.length} Active</span>
      </div>

      <div className="space-y-2.5 max-h-[580px] overflow-y-auto pr-1">
        {alerts.map((alt) => (
          <div
            key={alt.id}
            className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2 hover:border-slate-700 transition"
          >
            <div className="flex items-center justify-between">
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                  alt.severity === "CRITICAL"
                    ? "bg-rose-500/10 text-rose-400 border border-rose-500/30"
                    : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                }`}
              >
                {alt.severity}
              </span>
              <span className="font-mono text-xs font-bold text-white">{alt.symbol}</span>
            </div>

            <p className="text-xs text-slate-300 font-medium leading-relaxed">{alt.summary}</p>

            <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-800/80">
              <span className="text-[10px] text-slate-500 font-mono">{formatTimestamp(alt.ts)}</span>
              <button
                onClick={() => onInvestigate?.(alt.symbol)}
                className="text-emerald-400 hover:text-emerald-300 font-medium flex items-center gap-0.5 transition"
              >
                <span>Investigate Case</span>
                <ArrowUpRight className="h-3 w-3" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
export default AlertFeed;
