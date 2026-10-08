"use client";

import React from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";

interface AlignedChartProps {
  symbol?: string;
  lagSeconds?: number;
}

export function AlignedChart({ symbol = "ZENITHSME", lagSeconds = 42 }: AlignedChartProps) {
  // Generate aligned timeline data (e.g. 10 time intervals around manipulation burst)
  const data = [
    { time: "10:00:00", volume: 12000, hype: 0.12 },
    { time: "10:00:15", volume: 14500, hype: 0.15 },
    { time: "10:00:30", volume: 15200, hype: 0.28 },
    { time: "10:00:45", volume: 18000, hype: 0.74 }, // CTA burst starts
    { time: "10:01:00", volume: 22000, hype: 0.95 }, // Peak Hype
    { time: "10:01:15", volume: 85000, hype: 0.88 }, // 42s lag -> Volume Surge
    { time: "10:01:30", volume: 142000, hype: 0.76 }, // Peak Volume Spike (8.4x)
    { time: "10:01:45", volume: 98000, hype: 0.45 },
    { time: "10:02:00", volume: 45000, hype: 0.25 },
    { time: "10:02:15", volume: 24000, hype: 0.15 },
  ];

  return (
    <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
        <div>
          <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
            Cross-Modal Alignment: {symbol}
          </h4>
          <span className="text-[11px] text-slate-400">
            Detected Lead-Lag Cross-Correlation: <strong className="text-emerald-400 font-mono">+{lagSeconds}s</strong>
          </span>
        </div>
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
          XCORR: 0.89
        </span>
      </div>

      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 10 }} />
            <YAxis yAxisId="left" stroke="#64748b" tick={{ fontSize: 10 }} />
            <YAxis yAxisId="right" orientation="right" domain={[0, 1]} stroke="#64748b" tick={{ fontSize: 10 }} />
            <Tooltip
              contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", borderRadius: "8px", fontSize: "11px" }}
              labelStyle={{ color: "#94a3b8" }}
            />
            <Legend wrapperStyle={{ fontSize: "11px" }} />
            <Bar yAxisId="left" dataKey="volume" name="Trading Volume" fill="#10b981" opacity={0.6} radius={[4, 4, 0, 0]} />
            <Line yAxisId="right" type="monotone" dataKey="hype" name="Social Hype Score" stroke="#f43f5e" strokeWidth={2.5} dot={{ r: 3 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
export default AlignedChart;
