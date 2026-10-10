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
      <div className="flex items-center justify-between text-xs text-ink-muted font-semibold uppercase tracking-wider px-1">
        <span className="flex items-center gap-1.5">
          <AlertTriangle className="h-4 w-4 text-seal" />
          Real-Time Forensic Alerts
        </span>
        <span className="font-mono text-verified text-[11px]">{alerts.length} Active</span>
      </div>

      <div className="space-y-2.5 max-h-[580px] overflow-y-auto pr-1">
        {alerts.map((alt) => (
          <div
            key={alt.id}
            className="p-3.5 rounded-panel bg-bg-raised border border-line space-y-2 hover:border-line-strong transition"
          >
            <div className="flex items-center justify-between">
              <span
                className={`px-2 py-0.5 rounded-cell text-[10px] font-bold uppercase ${
                  alt.severity === "CRITICAL"
                    ? "bg-seal-wash text-seal border border-seal"
                    : "bg-tag-wash text-tag-ink border border-tag"
                }`}
              >
                {alt.severity}
              </span>
              <span className="font-mono text-xs font-bold text-ink">{alt.symbol}</span>
            </div>

            <p className="text-xs text-ink font-medium leading-relaxed">{alt.summary}</p>

            <div className="flex items-center justify-between text-[11px] text-ink-muted pt-1 border-t border-line">
              <span className="text-[10px] text-ink-faint font-mono">{formatTimestamp(alt.ts)}</span>
              <button
                onClick={() => alt.symbol && onInvestigate?.(alt.symbol)}
                className="text-verified hover:underline font-medium flex items-center gap-0.5 transition"
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
