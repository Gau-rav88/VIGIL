"use client";

import React, { useState } from "react";
import { startScenario, stopScenario } from "@/lib/api";
import { Play, Square, Activity, Database, Radio, Layers, Zap } from "lucide-react";

interface ScenarioControlProps {
  status: any;
  onRefresh?: () => void;
}

const SCENARIOS = [
  {
    id: "pump_dump_ring_01",
    name: "Syndicate Pump & Dump Ring",
    badge: "CRITICAL",
    badgeColor: "bg-rose-500/10 text-rose-400 border-rose-500/30",
    desc: "20 accounts + Telegram CTA bursts + circular wash trading on ZENITHSME.",
  },
  {
    id: "wash_ring_01",
    name: "Circular Wash Trading",
    badge: "HIGH VOLUME",
    badgeColor: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    desc: "Multi-hop order loops A -> B -> C -> A inflating volume without price change.",
  },
  {
    id: "spoofing_01",
    name: "L3 Orderbook Spoofing",
    badge: "MICROSTRUCTURE",
    badgeColor: "bg-indigo-500/10 text-indigo-400 border-indigo-500/30",
    desc: "High-frequency non-bona fide buy orders placed and immediately cancelled.",
  },
  {
    id: "baseline_01",
    name: "Clean Market Baseline",
    badge: "BENCHMARK",
    badgeColor: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    desc: "Organic GBM trading across all 40 assets with zero manipulation.",
  },
];

export function ScenarioControl({ status, onRefresh }: ScenarioControlProps) {
  const [selectedScenario, setSelectedScenario] = useState("pump_dump_ring_01");
  const [speed, setSpeed] = useState(10);
  const [loading, setLoading] = useState(false);

  const handleStart = async () => {
    setLoading(true);
    try {
      await startScenario(selectedScenario, speed);
      onRefresh?.();
    } catch {
      //
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await stopScenario(status?.active_scenario || selectedScenario);
      onRefresh?.();
    } catch {
      //
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Telemetry Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
          <span className="text-xs text-slate-400 block mb-1">Engine TPS</span>
          <span className="text-2xl font-mono font-bold text-white">
            {status?.running ? `${(speed * 42.5).toFixed(0)}` : "0"}
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">events/s</span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
          <span className="text-xs text-slate-400 block mb-1">Trades Emitted</span>
          <span className="text-2xl font-mono font-bold text-white">
            {status?.events_emitted?.trades?.toLocaleString() || "0"}
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">Normalized</span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
          <span className="text-xs text-slate-400 block mb-1">L2/L3 Snapshots</span>
          <span className="text-2xl font-mono font-bold text-white">
            {((status?.events_emitted?.l2 || 0) + (status?.events_emitted?.l3 || 0)).toLocaleString()}
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">Sequenced</span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
          <span className="text-xs text-slate-400 block mb-1">Social CTAs</span>
          <span className="text-2xl font-mono font-bold text-white">
            {status?.events_emitted?.social?.toLocaleString() || "0"}
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">Broadcasts</span>
        </div>
      </div>

      {/* Scenario Selector */}
      <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {SCENARIOS.map((sc) => (
            <div
              key={sc.id}
              onClick={() => setSelectedScenario(sc.id)}
              className={`p-3.5 rounded-xl border transition cursor-pointer ${
                selectedScenario === sc.id
                  ? "bg-slate-900 border-emerald-500/60 shadow-lg shadow-emerald-500/10"
                  : "bg-slate-900/40 border-slate-800 hover:border-slate-700"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${sc.badgeColor}`}>
                  {sc.badge}
                </span>
                {status?.active_scenario === sc.id && (
                  <span className="text-[10px] font-mono text-emerald-400 font-bold">RUNNING</span>
                )}
              </div>
              <h4 className="font-bold text-sm text-slate-200">{sc.name}</h4>
              <p className="text-xs text-slate-400 mt-1 line-clamp-2">{sc.desc}</p>
            </div>
          ))}
        </div>

        {/* Speed and Action Buttons */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-slate-800">
          <div className="flex items-center space-x-2">
            <span className="text-xs text-slate-400 font-medium">Speed:</span>
            {[1, 5, 10, 20].map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={`px-2.5 py-1 rounded text-xs font-mono font-bold transition ${
                  speed === s ? "bg-emerald-500 text-slate-950" : "bg-slate-800 text-slate-300"
                }`}
              >
                {s}x
              </button>
            ))}
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleStart}
              disabled={loading}
              className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 text-slate-950 font-bold text-xs shadow-md transition disabled:opacity-50"
            >
              <Play className="h-4 w-4 fill-current" />
              <span>Start Scenario</span>
            </button>
            <button
              onClick={handleStop}
              disabled={loading || !status?.running}
              className="flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-slate-800 text-slate-300 hover:text-rose-400 border border-slate-700 font-semibold text-xs transition disabled:opacity-50"
            >
              <Square className="h-4 w-4" />
              <span>Halt</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
export default ScenarioControl;
