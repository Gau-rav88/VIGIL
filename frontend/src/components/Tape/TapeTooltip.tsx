"use client";

import React from "react";
import { formatTime } from "@/lib/time";
import { formatCurrency, formatCompactNumber } from "@/lib/format";

export function TapeTooltip({ active, payload, label }: any) {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0]?.payload || {};
  const t = label || data.t;

  return (
    <div className="bg-bg-raised border border-line rounded-panel shadow-pop p-3 text-xs space-y-1.5 z-50 pointer-events-none min-w-44">
      <div className="border-b border-line pb-1 flex justify-between font-mono text-[11px] text-ink-muted">
        <span>IST {formatTime(t, "IST")}</span>
        <span>UTC {formatTime(t, "UTC")}</span>
      </div>

      {data.hype !== undefined && (
        <div className="flex justify-between">
          <span className="text-social font-medium">Hype Score:</span>
          <span className="font-mono font-bold text-ink">{data.hype}</span>
        </div>
      )}

      {data.organic !== undefined && (
        <div className="flex justify-between">
          <span className="text-ink font-medium">Organic Vol:</span>
          <span className="font-mono font-bold text-ink">{formatCompactNumber(data.organic)}</span>
        </div>
      )}

      {data.ring !== undefined && (
        <div className="flex justify-between">
          <span className="text-uv font-medium">Ring Vol:</span>
          <span className="font-mono font-bold text-uv">{formatCompactNumber(data.ring)}</span>
        </div>
      )}

      {data.price !== undefined && (
        <div className="flex justify-between pt-1 border-t border-line/60">
          <span className="text-price font-medium">Price:</span>
          <span className="font-mono font-bold text-ink">{formatCurrency(data.price)}</span>
        </div>
      )}
    </div>
  );
}
export default TapeTooltip;
