"use client";

import React, { useState, useEffect } from "react";
import { fetchSimStatus } from "@/lib/api";
import { ScenarioControl } from "@/components/ScenarioControl";
import { Button } from "@/components/ui/Button";
import { Zap, RefreshCw, ShieldAlert, ArrowRight } from "lucide-react";

export default function SimulatorPage() {
  const [status, setStatus] = useState<any>(null);

  const loadStatus = async () => {
    try {
      const data = await fetchSimStatus();
      setStatus(data);
    } catch {
      //
    }
  };

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-line pb-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="font-serif text-xl font-bold text-ink flex items-center gap-2">
              <Zap className="h-5 w-5 text-tag-ink" />
              <span>Scenario Control Center</span>
            </h1>
            <span className="px-2 py-0.5 rounded-chip text-[11px] font-bold bg-tag-wash text-tag-ink border border-tag/30">
              Matching Engine
            </span>
          </div>
          <p className="text-xs text-ink-muted mt-0.5">
            Deterministic synthetic manipulation injection across L2/L3 orderbooks and multi-lingual social feeds.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2 px-3 py-1.5 rounded-cell bg-bg-raised border border-line">
            <span
              className={`h-2 w-2 rounded-full ${
                status?.running ? "bg-verified animate-ping" : "bg-ink-muted"
              }`}
            />
            <span className="text-xs font-mono font-medium text-ink">
              {status?.running ? `ACTIVE: ${status.active_scenario}` : "ENGINE IDLE"}
            </span>
          </div>
          <Button size="sm" variant="secondary" onClick={loadStatus}>
            <RefreshCw className="h-3.5 w-3.5 mr-1" />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ScenarioControl status={status} onRefresh={loadStatus} />
        </div>

        {/* Blueprint Side Card */}
        <div className="space-y-4">
          <h2 className="text-xs font-semibold text-ink uppercase tracking-wider flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-ink" />
            <span>Ground Truth Blueprint</span>
          </h2>

          <div className="p-5 rounded-panel bg-bg-raised border border-line space-y-3.5 text-xs shadow-sm">
            <div className="flex justify-between text-ink-muted pb-2 border-b border-line/60">
              <span>Target Symbol:</span>
              <span className="font-mono font-bold text-ink">{status?.target_symbol || "Dynamic Scenario Target"}</span>
            </div>
            <div className="flex justify-between text-ink-muted">
              <span>Topology:</span>
              <span className="font-mono text-ink">20 Accounts / 5 Devices</span>
            </div>
            <div className="flex justify-between text-ink-muted">
              <span>Proxy Infrastructure:</span>
              <span className="font-mono text-ink">ASN 55836</span>
            </div>
            <div className="flex justify-between text-ink-muted">
              <span>Expected Latency:</span>
              <span className="font-mono text-ink">&lt; 60 seconds</span>
            </div>

            <div className="p-3 rounded-cell bg-bg-sunken border border-line text-[11px] text-ink-muted leading-relaxed font-sans">
              <span className="text-ink font-semibold block mb-1">Multi-Agent Pipeline:</span>
              Quant Telemetry ➔ Social Intel ➔ Alignment Engine ➔ Attribution ➔ Orchestrator ➔ Evidence Engine.
            </div>

            <div className="pt-2">
              <a
                href="/cases"
                className="w-full flex items-center justify-center space-x-1.5 py-2 px-3 rounded-panel bg-ink text-bg-raised text-xs font-semibold hover:opacity-90 transition"
              >
                <span>View Case Workbench</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
