"use client";

import React from "react";
import type { ScaleTime } from "d3-scale";
import { formatTime } from "@/lib/time";

interface TimeAxisProps {
  x: ScaleTime<number, number>;
  width: number;
  ticks: number[];
}

export function TimeAxis({ x, width, ticks }: TimeAxisProps) {
  return (
    <div className="h-6 border-t border-line bg-bg-raised text-[11px] text-ink-muted relative overflow-hidden font-mono select-none">
      {ticks.map((t) => {
        const posX = x(new Date(t));
        return (
          <div
            key={t}
            className="absolute top-1 -translate-x-1/2 whitespace-nowrap"
            style={{ left: `${posX}px` }}
          >
            {formatTime(t, "IST")}
          </div>
        );
      })}
    </div>
  );
}
export default TimeAxis;
