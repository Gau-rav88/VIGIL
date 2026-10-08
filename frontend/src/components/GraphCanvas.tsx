"use client";

import React from "react";
import { useGraphStore, GraphNode, GraphEdge } from "@/state/useGraphStore";
import { Network } from "lucide-react";

interface GraphCanvasProps {
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  onSelectNode?: (node: GraphNode) => void;
  onSelectEdge?: (edge: GraphEdge) => void;
}

export function GraphCanvas({ onSelectNode, onSelectEdge }: GraphCanvasProps) {
  const { selectNode, selectEdge, selectedNode } = useGraphStore();

  const handleNodeClick = (node: GraphNode) => {
    selectNode(node);
    onSelectNode?.(node);
  };

  return (
    <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Network className="h-5 w-5 text-emerald-400" />
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">
            Syndicate Ring Attribution Topology
          </h3>
        </div>
        <div className="flex items-center space-x-3 text-[11px] text-slate-400">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-cyan-400" /> 20 Accounts
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-purple-400" /> 5 Shared Devices
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-amber-400" /> ASN 55836
          </span>
        </div>
      </div>

      {/* Visual Topology Canvas */}
      <div className="h-72 rounded-xl bg-slate-950/90 border border-slate-800/80 p-4 flex flex-col justify-between relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:16px_16px] opacity-40 pointer-events-none" />

        {/* Central ASN Node */}
        <div className="flex justify-center z-10">
          <button
            onClick={() => handleNodeClick({ id: "asn_55836", type: "ASN", label: "ASN 55836 (Proxy Infrastructure)" })}
            className={`px-4 py-1.5 rounded-lg border font-mono text-xs font-bold flex items-center gap-2 shadow-md transition ${
              selectedNode?.id === "asn_55836"
                ? "bg-amber-500 text-slate-950 border-amber-400"
                : "bg-amber-500/10 border-amber-500/40 text-amber-300 hover:bg-amber-500/20"
            }`}
          >
            <span className="h-2 w-2 rounded-full bg-amber-400 animate-ping" />
            <span>Autonomous System: ASN 55836</span>
          </button>
        </div>

        {/* Middle: 5 Device Clusters */}
        <div className="flex justify-around items-center z-10 py-2">
          {[1, 2, 3, 4, 5].map((d) => {
            const devId = `dev_0${d}`;
            const isSelected = selectedNode?.id === devId;
            return (
              <button
                key={d}
                onClick={() => handleNodeClick({ id: devId, type: "Device", label: `Device Hardware FP #${d} (Shared by 4 Accounts)` })}
                className={`flex flex-col items-center p-2 rounded-lg border transition ${
                  isSelected
                    ? "bg-purple-600 text-white border-purple-400"
                    : "bg-purple-500/10 border-purple-500/40 text-purple-300 hover:bg-purple-500/20"
                }`}
              >
                <span className="text-[10px] font-mono font-bold">DEV-0{d}</span>
                <span className="text-[9px] opacity-80">4 Accounts</span>
              </button>
            );
          })}
        </div>

        {/* Bottom: 20 Accounts Grid */}
        <div className="grid grid-cols-10 gap-1.5 z-10">
          {Array.from({ length: 20 }).map((_, i) => {
            const accId = `acc_${(i + 1).toString().padStart(2, "0")}`;
            const isSelected = selectedNode?.id === accId;
            return (
              <button
                key={i}
                onClick={() => handleNodeClick({ id: accId, type: "Account", label: `Account #${i + 1} (Syndicate Ring Member)` })}
                className={`py-1 px-0.5 rounded border font-mono text-[9px] text-center truncate transition ${
                  isSelected
                    ? "bg-cyan-400 text-slate-950 font-bold border-cyan-300"
                    : "bg-cyan-950/40 border-cyan-500/30 text-cyan-300 hover:border-cyan-400 hover:bg-cyan-900/60"
                }`}
                title={`Account ${(i + 1).toString().padStart(2, "0")}`}
              >
                A{i + 1}
              </button>
            );
          })}
        </div>
      </div>

      <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
        <span>Attribution Algorithm: <strong>Louvain Modularity + Cycle DFS</strong></span>
        <span className="text-emerald-400 font-mono font-semibold">Ring Score: 0.95 (Threshold ≥0.80)</span>
      </div>
    </div>
  );
}
export default GraphCanvas;
