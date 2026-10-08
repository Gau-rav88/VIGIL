"use client";

import React, { useState } from "react";
import { CaseData } from "@/lib/api";
import { truncateHash, formatTimestamp } from "@/lib/format";

interface CaseTableProps {
  cases: CaseData[];
  selectedCaseId?: string | null;
  onSelectCase: (caseId: string) => void;
}

export function CaseTable({ cases, selectedCaseId, onSelectCase }: CaseTableProps) {
  const [filter, setFilter] = useState<"ALL" | "PENDING" | "PUBLISHED">("ALL");

  const filtered = cases.filter((c) => {
    if (filter === "PENDING") return c.status === "PENDING_REVIEW" || c.status === "OPENED";
    if (filter === "PUBLISHED") return c.status === "PUBLISHED";
    return true;
  });

  return (
    <div className="space-y-3">
      {/* Filter Tabs */}
      <div className="flex items-center space-x-1 p-1 bg-slate-900/80 border border-slate-800 rounded-xl">
        {(["ALL", "PENDING", "PUBLISHED"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition ${
              filter === t ? "bg-slate-800 text-white shadow-sm" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {t === "ALL" ? "All" : t === "PENDING" ? "Pending Review" : "Published"}
          </button>
        ))}
      </div>

      {/* Case Cards List */}
      <div className="space-y-2.5 max-h-[640px] overflow-y-auto pr-1">
        {filtered.map((c) => {
          const isSelected = selectedCaseId === c.case_id;
          const isPublished = c.status === "PUBLISHED";
          const isPending = c.status === "PENDING_REVIEW";

          return (
            <div
              key={c.case_id}
              onClick={() => onSelectCase(c.case_id)}
              className={`p-4 rounded-xl border transition cursor-pointer space-y-2.5 ${
                isSelected
                  ? "bg-slate-900 border-emerald-500/60 shadow-lg shadow-emerald-500/10"
                  : "bg-slate-900/50 border-slate-800/80 hover:border-slate-700 hover:bg-slate-900/80"
              }`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="font-mono font-bold text-white text-base block">{c.symbol}</span>
                  <span className="text-[10px] text-slate-500 font-mono">{truncateHash(c.case_id, 6, 6)}</span>
                </div>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
                    isPublished
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                      : isPending
                      ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                      : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                  }`}
                >
                  {c.status.replace("_", " ")}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400 pt-1 border-t border-slate-800/60">
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase">Confidence</span>
                  <span className="font-mono font-semibold text-emerald-400">96.4%</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase">Created At</span>
                  <span className="font-mono text-slate-300">{formatTimestamp(c.created_at)}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
export default CaseTable;
