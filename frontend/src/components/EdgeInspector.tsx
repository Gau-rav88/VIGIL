"use client";

import React from "react";
import { useGraphStore } from "@/state/useGraphStore";
import { Info, X } from "lucide-react";

export function EdgeInspector() {
  const { selectedNode, selectedEdge, selectNode, selectEdge } = useGraphStore();

  if (!selectedNode && !selectedEdge) {
    return (
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-500 text-center">
        Click any node or device cluster above to inspect attribution metadata.
      </div>
    );
  }

  const handleClose = () => {
    selectNode(null);
    selectEdge(null);
  };

  return (
    <div className="p-4 rounded-xl bg-slate-900 border border-slate-700/80 space-y-3 relative shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center space-x-2">
          <Info className="h-4 w-4 text-emerald-400" />
          <h4 className="text-xs font-bold text-white uppercase tracking-wider">
            Entity Inspector
          </h4>
        </div>
        <button onClick={handleClose} className="text-slate-400 hover:text-white text-xs px-1">
          <X className="h-4 w-4" />
        </button>
      </div>

      {selectedNode && (
        <div className="space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-slate-400">Node Identifier:</span>
            <span className="font-mono font-bold text-emerald-400">{selectedNode.id}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Entity Type:</span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-200">
              {selectedNode.type}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Classification:</span>
            <span className="text-slate-300 font-medium">{selectedNode.label}</span>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-400 leading-relaxed mt-2">
            Evidence: Node shares colocated IP subnet hash and hardware canvas signature across all 14 coordinated wash transactions.
          </div>
        </div>
      )}
    </div>
  );
}
export default EdgeInspector;
