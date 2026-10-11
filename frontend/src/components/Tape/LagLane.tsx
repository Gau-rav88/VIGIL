"use client";

import React, { useState, useEffect } from "react";
import type { ScaleTime } from "d3-scale";

interface LagLaneProps {
  x: ScaleTime<number, number>;
  width: number;
  height: number;
  lag: {
    tSocial: number;
    tMarket: number;
    seconds: number;
    pValue: number;
    xcorrPeak: number;
  };
  animateOnce?: boolean;
  caseId?: string;
}

export function LagLane({
  x,
  width,
  height,
  lag,
  animateOnce = true,
  caseId = "default",
}: LagLaneProps) {
  const [drawn, setDrawn] = useState(() => !animateOnce);

  useEffect(() => {
    if (!drawn) {
      const id = requestAnimationFrame(() => setDrawn(true));
      return () => cancelAnimationFrame(id);
    }
  }, [drawn]);

  if (!lag || !lag.seconds || lag.seconds <= 0 || !lag.tSocial || !lag.tMarket) {
    return <div style={{ height }} className="w-full" />;
  }

  const xs = x(new Date(lag.tSocial));
  const xm = x(new Date(lag.tMarket));
  const midX = (xs + xm) / 2;
  const bracketY = height / 2;

  const tooltipText = `Trading rose ${lag.seconds} seconds after the first coordinated message. A shuffle test says a gap this consistent would occur by chance about ${(lag.pValue * 100).toFixed(2)}% of the time.`;

  return (
    <svg
      width={width}
      height={height}
      role="img"
      aria-label={`Trading rose ${lag.seconds} seconds after the first coordinated message`}
      className="overflow-visible select-none"
    >
      <title>{tooltipText}</title>

      {/* Vertical hairlines extending through rows */}
      <line x1={xs} x2={xs} y1={0} y2={height} stroke="var(--ink)" strokeDasharray="2 3" strokeWidth={1} />
      <line x1={xm} x2={xm} y1={0} y2={height} stroke="var(--ink)" strokeDasharray="2 3" strokeWidth={1} />

      {/* Connecting Bracket Line */}
      <line
        x1={xs}
        x2={xm}
        y1={bracketY}
        y2={bracketY}
        stroke="var(--uv)"
        strokeWidth={1.5}
        className={drawn ? "transition-all duration-500" : ""}
      />

      {/* Downward tick marks on bracket ends */}
      <line x1={xs} x2={xs} y1={bracketY - 4} y2={bracketY + 4} stroke="var(--uv)" strokeWidth={1.5} />
      <line x1={xm} x2={xm} y1={bracketY - 4} y2={bracketY + 4} stroke="var(--uv)" strokeWidth={1.5} />

      {/* Center Label */}
      <g transform={`translate(${midX}, ${bracketY - 6})`}>
        <rect
          x={-34}
          y={-10}
          width={68}
          height={16}
          rx={3}
          fill="var(--bg-raised)"
          stroke="var(--line)"
          strokeWidth={1}
        />
        <text
          x={0}
          y={2}
          textAnchor="middle"
          fontSize={10}
          fontWeight={600}
          fill="var(--ink)"
          fontFamily="monospace"
        >
          +{lag.seconds}s later
        </text>
      </g>
    </svg>
  );
}
export default LagLane;
