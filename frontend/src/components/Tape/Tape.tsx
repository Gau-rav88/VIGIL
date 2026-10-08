"use client";

import React, { useMemo, useRef, useState, useLayoutEffect } from "react";
import { scaleTime } from "d3-scale";
import { ComposedChart, Area, Bar, Line, XAxis, YAxis, Tooltip, Brush, ReferenceArea } from "recharts";
import { LagLane } from "./LagLane";
import { EvidenceRow } from "./EvidenceRow";
import { TimeAxis } from "./TimeAxis";
import { TapeTooltip } from "./TapeTooltip";
import { useTapeStore } from "@/state/useTapeStore";
import type { CaseSeries } from "@/lib/types";

export const PLOT_MARGIN = { left: 48, right: 48, top: 8, bottom: 0 };

interface TapeProps {
  series: CaseSeries;
  compact?: boolean;
}

export function Tape({ series, compact = false }: TapeProps) {
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(960);

  useLayoutEffect(() => {
    const ro = new ResizeObserver(([e]) => {
      if (e?.contentRect?.width) {
        setWidth(Math.max(480, Math.floor(e.contentRect.width)));
      }
    });
    if (wrap.current) ro.observe(wrap.current);
    return () => ro.disconnect();
  }, []);

  const { zoom, setScrubber } = useTapeStore();
  const [t0, t1] = zoom ?? [series.window.start, series.window.end];

  const x = useMemo(
    () => scaleTime().domain([new Date(t0), new Date(t1)]).range([PLOT_MARGIN.left, width - PLOT_MARGIN.right]),
    [t0, t1, width]
  );

  const xTicks = useMemo(() => x.ticks(width > 900 ? 10 : 5).map((d) => +d), [x, width]);

  const common = {
    width,
    margin: PLOT_MARGIN,
    syncId: "tape",
    onMouseMove: (s: any) => s?.activeLabel && setScrubber(Number(s.activeLabel)),
  };

  const xAxis = (
    <XAxis
      dataKey="t"
      type="number"
      scale="time"
      domain={[+t0, +t1]}
      ticks={xTicks}
      hide
    />
  );

  return (
    <div
      ref={wrap}
      role="group"
      aria-label={series.a11ySummary}
      className="relative bg-bg-raised border border-line rounded-panel overflow-hidden shadow-sm"
    >
      {/* Social Row Header */}
      <div className="px-4 py-2 border-b border-line/60 flex justify-between items-center bg-bg-sunken/30 text-xs">
        <span className="font-semibold text-social uppercase tracking-wider text-[11px]">
          Social Intelligence & CTA Burst (Hype 0-100)
        </span>
        <span className="font-mono text-ink-muted text-[10px]">
          {series.bursts.length} Active Bursts
        </span>
      </div>

      {/* Social Chart Row */}
      <ComposedChart {...common} height={compact ? 80 : 120} data={series.hype}>
        {xAxis}
        <YAxis width={0} domain={[0, 100]} hide />
        <Area
          dataKey="hype"
          stroke="var(--social)"
          strokeWidth={1.5}
          fill="var(--social)"
          fillOpacity={0.12}
          isAnimationActive={false}
        />
        {series.bursts.map((b) => (
          <ReferenceArea
            key={b.id}
            x1={b.start}
            x2={b.end}
            fill="var(--social)"
            fillOpacity={0.08}
          />
        ))}
      </ComposedChart>

      {/* Lag Lane (SVG bracket sharing x-scale) */}
      <div className="border-t border-b border-line/40 bg-bg-sunken/20">
        <LagLane
          x={x}
          width={width}
          height={compact ? 24 : 36}
          lag={series.lag}
          animateOnce={!compact}
          caseId={series.caseId}
        />
      </div>

      {/* Market Row Header */}
      <div className="px-4 py-1.5 flex justify-between items-center bg-bg-sunken/30 text-xs border-b border-line/40">
        <div className="flex items-center space-x-3 text-[11px]">
          <span className="flex items-center gap-1 font-medium text-ink">
            <span className="h-2 w-2 rounded-sm bg-market" /> Organic Volume
          </span>
          <span className="flex items-center gap-1 font-medium text-uv">
            <span className="h-2 w-2 rounded-sm bg-uv" /> Ring-Attributed Volume
          </span>
          <span className="flex items-center gap-1 font-medium text-price">
            <span className="h-2 w-2 rounded-full bg-price" /> Price (INR)
          </span>
        </div>
      </div>

      {/* Market Chart Row */}
      <ComposedChart {...common} height={compact ? 100 : 150} data={series.bars}>
        {xAxis}
        <YAxis yAxisId="v" width={0} hide />
        <YAxis yAxisId="p" orientation="right" width={0} hide domain={["auto", "auto"]} />
        <Bar yAxisId="v" dataKey="organic" stackId="v" fill="var(--market)" isAnimationActive={false} />
        <Bar yAxisId="v" dataKey="ring" stackId="v" fill="var(--uv)" isAnimationActive={false} />
        <Line yAxisId="p" dataKey="price" stroke="var(--price)" strokeWidth={1.2} dot={false} isAnimationActive={false} />
        <Tooltip content={<TapeTooltip />} cursor={{ stroke: "var(--ink)", strokeWidth: 1 }} />
        {!compact && (
          <Brush
            dataKey="t"
            height={20}
            stroke="var(--line-strong)"
            travellerWidth={6}
            fill="var(--bg-sunken)"
          />
        )}
      </ComposedChart>

      {/* Evidence Row */}
      {!compact && series.evidence.length > 0 && (
        <EvidenceRow x={x} width={width} items={series.evidence} />
      )}

      {/* Shared Time Axis */}
      <TimeAxis x={x} width={width} ticks={xTicks} />
    </div>
  );
}
export default Tape;
