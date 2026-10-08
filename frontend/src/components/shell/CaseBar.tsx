"use client";

import React, { useState } from "react";
import { Stepper } from "./Stepper";
import { copy } from "@/lib/copy";
import { Check, AlertTriangle, ChevronDown, ExternalLink } from "lucide-react";

interface CaseBarProps {
  symbol?: string;
  exchange?: string;
  status?: string;
  confidence?: number;
  completeness?: number;
  dossierVersion?: number;
  isVerified?: boolean;
  windowStr?: string;
  flags?: Array<{ flag: string; explanation: string }>;
  onOpenDossier?: () => void;
  onAdjustAnalysis?: () => void;
}

export function CaseBar({
  symbol = "ZENITHSME",
  exchange = "NSE SME",
  status = "PENDING_REVIEW",
  confidence = 0.964,
  completeness = 1.0,
  dossierVersion = 1,
  isVerified = true,
  windowStr = "Window 04:20 to 04:37 UTC (IST 09:50 to 10:07)",
  flags = [],
  onOpenDossier,
  onAdjustAnalysis,
}: CaseBarProps) {
  const [showAdjust, setShowAdjust] = useState(false);
  const statusLabel = copy.stage[status as keyof typeof copy.stage] || status;

  return (
    <div className="border-b border-line bg-bg-raised text-ink px-6 py-3 space-y-2 sticky top-12 z-40">
      {/* Top row */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <span className="font-mono font-bold text-lg text-ink tracking-tight">{symbol}</span>
          <span className="text-xs text-ink-muted px-2 py-0.5 rounded-cell bg-bg-sunken border border-line">
            {exchange}
          </span>
          <span className="text-xs px-2.5 py-0.5 rounded-chip font-medium bg-uv-wash text-uv border border-uv/20">
            {statusLabel}
          </span>
          <span className="text-xs text-ink-muted">
            Confidence: <strong className="font-mono text-ink">{(confidence * 100).toFixed(0)}%</strong>
          </span>
          <span className="text-xs text-ink-muted">
            Completeness: <strong className="font-mono text-ink">{(completeness * 100).toFixed(0)}%</strong>
          </span>
          <span className="text-xs text-ink-muted font-mono">
            Dossier v{dossierVersion}
          </span>
          {isVerified && (
            <span className="flex items-center space-x-1 text-xs text-verified font-medium">
              <Check className="h-3.5 w-3.5 stroke-[3]" />
              <span>Verified</span>
            </span>
          )}
        </div>

        <div className="flex items-center space-x-2">
          <div className="relative">
            <button
              onClick={() => setShowAdjust(!showAdjust)}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-panel text-xs text-ink border border-line hover:bg-bg-sunken transition font-medium"
            >
              <span>{copy.action.adjust}</span>
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
            {showAdjust && (
              <div className="absolute right-0 mt-1 w-56 rounded-panel bg-bg-raised border border-line shadow-pop p-1.5 z-50 text-xs space-y-1">
                <button
                  onClick={() => { setShowAdjust(false); onAdjustAnalysis?.(); }}
                  className="w-full text-left px-2.5 py-1.5 rounded-cell hover:bg-bg-sunken text-ink"
                >
                  {copy.action.widen}
                </button>
                <button
                  onClick={() => { setShowAdjust(false); onAdjustAnalysis?.(); }}
                  className="w-full text-left px-2.5 py-1.5 rounded-cell hover:bg-bg-sunken text-ink"
                >
                  {copy.action.rerun}
                </button>
                <button
                  onClick={() => { setShowAdjust(false); onAdjustAnalysis?.(); }}
                  className="w-full text-left px-2.5 py-1.5 rounded-cell hover:bg-bg-sunken text-ink"
                >
                  {copy.action.exclude}
                </button>
              </div>
            )}
          </div>

          <button
            onClick={onOpenDossier}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-panel text-xs text-bg-raised bg-ink hover:opacity-90 transition font-medium"
          >
            <span>{copy.action.openDossier}</span>
            <ExternalLink className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Second row: Window and Stepper */}
      <div className="flex flex-col md:flex-row md:items-center justify-between text-xs gap-2 pt-1 border-t border-line/60">
        <span className="text-ink-muted font-mono">{windowStr}</span>
        <Stepper currentStage={status} />
      </div>

      {/* Flags row if present */}
      {flags.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-1">
          {flags.map((f, i) => (
            <div
              key={i}
              className="flex items-center space-x-1.5 px-2.5 py-1 rounded-cell text-[11px] bg-tag-wash text-tag-ink border border-tag/30"
            >
              <AlertTriangle className="h-3.5 w-3.5 text-tag-ink shrink-0" />
              <span>{f.explanation}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
export default CaseBar;
