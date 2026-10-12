"use client";

import React, { useState, useEffect } from "react";
import { startScenario, stopScenario } from "@/lib/api";
import { Play, Square, Lock } from "lucide-react";
import { getRole, getRoleCapabilities, Role } from "@/lib/auth";

interface ScenarioControlProps {
  status: any;
  onRefresh?: () => void;
}

const SCENARIOS = [
  {
    id: "pump_dump_ring_01",
    name: "Syndicate Pump & Dump Ring",
    badge: "CRITICAL",
    badgeColor: "bg-seal-wash text-seal border-seal",
    desc: "20 accounts + Telegram CTA bursts + circular wash trading on target SME equity.",
  },
  {
    id: "wash_ring_01",
    name: "Circular Wash Trading",
    badge: "HIGH VOLUME",
    badgeColor: "bg-tag-wash text-tag-ink border-tag",
    desc: "Multi-hop order loops A -> B -> C -> A inflating volume without price change.",
  },
  {
    id: "spoofing_01",
    name: "L3 Orderbook Spoofing",
    badge: "MICROSTRUCTURE",
    badgeColor: "bg-uv-wash text-uv border-uv",
    desc: "High-frequency non-bona fide buy orders placed and immediately cancelled.",
  },
  {
    id: "baseline_01",
    name: "Clean Market Baseline",
    badge: "BENCHMARK",
    badgeColor: "bg-verified-wash text-verified border-verified",
    desc: "Organic GBM trading across all 40 assets with zero manipulation.",
  },
];

export function ScenarioControl({ status, onRefresh }: ScenarioControlProps) {
  const [selectedScenario, setSelectedScenario] = useState("pump_dump_ring_01");
  const [speed, setSpeed] = useState(10);
  const [loading, setLoading] = useState(false);
  const [role, setRoleState] = useState<Role>(getRole());

  useEffect(() => {
    setRoleState(getRole());
    const handler = () => setRoleState(getRole());
    window.addEventListener("vigil-role-changed", handler);
    return () => window.removeEventListener("vigil-role-changed", handler);
  }, []);

  const caps = getRoleCapabilities(role);

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
        <div className="p-4 rounded-panel bg-bg-raised border border-line">
          <span className="text-xs text-ink-muted block mb-1">Engine TPS</span>
          <span className="text-2xl font-mono font-bold text-ink">
            {status?.running ? `${(speed * 42.5).toFixed(0)}` : "0"}
          </span>
          <span className="text-[11px] text-ink-faint block mt-1">events/s</span>
        </div>

        <div className="p-4 rounded-panel bg-bg-raised border border-line">
          <span className="text-xs text-ink-muted block mb-1">Trades Emitted</span>
          <span className="text-2xl font-mono font-bold text-ink">
            {status?.events_emitted?.trades?.toLocaleString() || "0"}
          </span>
          <span className="text-[11px] text-ink-faint block mt-1">Normalized</span>
        </div>

        <div className="p-4 rounded-panel bg-bg-raised border border-line">
          <span className="text-xs text-ink-muted block mb-1">L2/L3 Snapshots</span>
          <span className="text-2xl font-mono font-bold text-ink">
            {((status?.events_emitted?.l2 || 0) + (status?.events_emitted?.l3 || 0)).toLocaleString()}
          </span>
          <span className="text-[11px] text-ink-faint block mt-1">Sequenced</span>
        </div>

        <div className="p-4 rounded-panel bg-bg-raised border border-line">
          <span className="text-xs text-ink-muted block mb-1">Social CTAs</span>
          <span className="text-2xl font-mono font-bold text-ink">
            {status?.events_emitted?.social?.toLocaleString() || "0"}
          </span>
          <span className="text-[11px] text-ink-faint block mt-1">Broadcasts</span>
        </div>
      </div>

      {/* Scenario Selector */}
      <div className="p-5 rounded-panel bg-bg-raised border border-line space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {SCENARIOS.map((sc) => (
            <div
              key={sc.id}
              onClick={() => setSelectedScenario(sc.id)}
              className={`p-3.5 rounded-panel border transition cursor-pointer ${
                selectedScenario === sc.id
                  ? "bg-bg-sunken border-verified shadow-pop"
                  : "bg-bg-raised border-line hover:border-line-strong"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className={`px-2 py-0.5 rounded-cell text-[10px] font-bold uppercase border ${sc.badgeColor}`}>
                  {sc.badge}
                </span>
                {status?.active_scenario === sc.id && (
                  <span className="text-[10px] font-mono text-verified font-bold">RUNNING</span>
                )}
              </div>
              <h4 className="font-bold text-sm text-ink">{sc.name}</h4>
              <p className="text-xs text-ink-muted mt-1 line-clamp-2">{sc.desc}</p>
            </div>
          ))}
        </div>

        {/* Speed and Action Buttons */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-line">
          <div className="flex items-center space-x-2">
            <span className="text-xs text-ink-muted font-medium">Speed:</span>
            {[1, 5, 10, 20].map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={`px-2.5 py-1 rounded-cell text-xs font-mono font-bold transition ${
                  speed === s ? "bg-verified text-bg-raised" : "bg-bg-sunken text-ink-muted"
                }`}
              >
                {s}x
              </button>
            ))}
          </div>

          <div className="flex items-center space-x-2">
            {!caps.canControlSimulator ? (
              <div className="flex items-center space-x-2">
                <span className="flex items-center space-x-1.5 px-3.5 py-2 rounded-panel bg-bg-sunken border border-line text-xs font-mono font-medium text-ink-muted">
                  <Lock className="h-3.5 w-3.5 text-ink-muted" />
                  <span>Admin Persona Required</span>
                </span>
              </div>
            ) : (
              <>
                <button
                  onClick={handleStart}
                  disabled={loading}
                  className="flex items-center space-x-2 px-5 py-2.5 rounded-panel bg-verified text-bg-raised font-bold text-xs shadow-md transition disabled:opacity-50"
                >
                  <Play className="h-4 w-4 fill-current" />
                  <span>Start Scenario</span>
                </button>
                <button
                  onClick={handleStop}
                  disabled={loading || !status?.running}
                  className="flex items-center space-x-2 px-4 py-2.5 rounded-panel bg-bg-sunken text-ink-muted hover:text-seal border border-line-strong font-semibold text-xs transition disabled:opacity-50"
                >
                  <Square className="h-4 w-4" />
                  <span>Halt</span>
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
export default ScenarioControl;
