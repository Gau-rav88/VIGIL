"use client";

import React from "react";

interface MeterProps {
  value: number; // 0 to 1 or 0 to 100
  max?: number;
  label?: string;
  showPercent?: boolean;
  className?: string;
}

export function Meter({
  value,
  max = 100,
  label,
  showPercent = true,
  className = "",
}: MeterProps) {
  const norm = max === 1 ? value * 100 : value;
  const pct = Math.min(100, Math.max(0, norm));

  let barColor = "bg-verified";
  if (pct >= 80) barColor = "bg-seal";
  else if (pct >= 40) barColor = "bg-uv";

  return (
    <div className={`space-y-1 ${className}`}>
      {(label || showPercent) && (
        <div className="flex justify-between text-[11px]">
          {label && <span className="text-ink-muted">{label}</span>}
          {showPercent && (
            <span className="font-mono font-bold text-ink">{pct.toFixed(0)}%</span>
          )}
        </div>
      )}
      <div className="w-full bg-bg-sunken h-1.5 rounded-full overflow-hidden border border-line/60">
        <div
          className={`h-full rounded-full transition-all duration-300 ${barColor}`}
          style={{ width: `${Math.max(4, pct)}%` }}
        />
      </div>
    </div>
  );
}
export default Meter;
