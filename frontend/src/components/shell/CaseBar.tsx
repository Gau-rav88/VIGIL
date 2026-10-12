"use client";

import React, { useState, useEffect } from "react";
import { Stepper } from "./Stepper";
import { copy } from "@/lib/copy";
import { Check, AlertTriangle, ChevronDown, ExternalLink, Lock, Send, ShieldCheck, Zap } from "lucide-react";
import { getRole, getRoleCapabilities, Role } from "@/lib/auth";
import { submitCase } from "@/lib/api";

interface CaseBarProps {
  caseId?: string;
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
  onAdjustAnalysis?: (type?: string) => void;
}

export function CaseBar({
  caseId,
  symbol = "—",
  exchange = "—",
  status = "—",
  confidence = 0,
  completeness = 0,
  dossierVersion = 1,
  isVerified = false,
  windowStr = "—",
  flags = [],
  onOpenDossier,
  onAdjustAnalysis,
}: CaseBarProps) {
  const [showAdjust, setShowAdjust] = useState(false);
  const [role, setRoleState] = useState<Role>(getRole());
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    setRoleState(getRole());
    const handler = () => setRoleState(getRole());
    window.addEventListener("vigil-role-changed", handler);
    return () => window.removeEventListener("vigil-role-changed", handler);
  }, []);

  const caps = getRoleCapabilities(role);
  const statusLabel = copy.stage[status as keyof typeof copy.stage] || status;

  const handleSubmitCase = async () => {
    if (!caseId) return;
    setIsSubmitting(true);
    try {
      await submitCase(caseId);
      setToastMessage("Case submitted to Compliance Officer for signoff");
      setTimeout(() => {
        setToastMessage(null);
        window.location.reload();
      }, 1500);
    } catch (err: any) {
      setToastMessage(err.message || "Failed to submit case");
      setTimeout(() => setToastMessage(null), 3500);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDirective = (type: string, label: string) => {
    setShowAdjust(false);
    setToastMessage(`Directive submitted: ${label}`);
    onAdjustAnalysis?.(type);
    setTimeout(() => setToastMessage(null), 3000);
  };


  return (
    <div className="border-b border-line bg-bg-raised text-ink px-6 py-3 space-y-2 sticky top-12 z-40">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-2.5 rounded-panel bg-ink text-bg-raised text-xs font-medium shadow-pop flex items-center space-x-2 animate-in fade-in">
          <ShieldCheck className="h-4 w-4 text-verified" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top row */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center space-x-3 flex-wrap gap-y-1">
          <span className="font-mono font-bold text-lg text-ink tracking-tight">{symbol}</span>
          <span className="text-xs text-ink-muted px-2 py-0.5 rounded-cell bg-bg-sunken border border-line">
            {exchange}
          </span>
          <span className="text-xs px-2.5 py-0.5 rounded-chip font-medium bg-uv-wash text-uv border border-uv/20">
            {statusLabel}
          </span>

          {/* Active Role Persona Badge */}
          <span
            className={`px-2 py-0.5 rounded-chip text-[10px] font-mono font-bold uppercase border ${caps.badgeColor} flex items-center gap-1`}
            title={`Active Persona: ${caps.label} (${caps.description})`}
          >
            {caps.isReadOnly && <Lock className="h-3 w-3" />}
            <span>{caps.badgeLabel}</span>
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

        {/* Action Controls - Strictly Filtered by Role Workflow */}
        <div className="flex items-center space-x-2">
          {/* Investigator & Compliance: Adjust Analysis Menu */}
          {caps.canAdjustAnalysis && (
            <div className="relative">
              <button
                onClick={() => setShowAdjust(!showAdjust)}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-panel text-xs border border-line text-ink hover:bg-bg-sunken transition font-medium"
                title="Adjust forensic observation window or reattribution"
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
          )}

          {/* Investigator Workflow: Submit to Compliance */}
          {caps.canSubmitCase && (
            <button
              onClick={handleSubmitCase}
              disabled={isSubmitting || status === "PENDING_REVIEW" || status === "APPROVED"}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-panel text-xs font-semibold bg-social text-bg-raised hover:opacity-90 transition disabled:opacity-50"
              title="Advance case: Submit findings to Compliance Officer for signoff"
            >
              <Send className="h-3.5 w-3.5" />
              <span>
                {isSubmitting
                  ? "Submitting…"
                  : status === "PENDING_REVIEW"
                  ? "Awaiting Signoff"
                  : "Submit to Compliance"}
              </span>
            </button>
          )}

          {/* Compliance Officer Workflow: Review & Sign Dossier */}
          {caps.canReviewDossier && (
            <button
              onClick={onOpenDossier}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-panel text-xs font-semibold bg-uv text-bg-raised hover:opacity-90 transition"
              title="Review findings and execute regulatory signoff on case dossier"
            >
              <ShieldCheck className="h-3.5 w-3.5" />
              <span>Review & Sign</span>
            </button>
          )}

          {/* Admin Workflow: Simulator Link */}
          {caps.canControlSimulator && (
            <a
              href="/simulator"
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-panel text-xs font-semibold bg-verified text-bg-raised hover:opacity-90 transition"
              title="Open Matching Engine Scenario Control"
            >
              <Zap className="h-3.5 w-3.5" />
              <span>Simulator Ops</span>
            </a>
          )}

          {/* All Roles: View Dossier Record */}
          <button
            onClick={onOpenDossier}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-panel text-xs text-bg-raised bg-ink hover:opacity-90 transition font-medium"
            title="Inspect dossier evidence bundle"
          >
            <span>{caps.isReadOnly ? "View Audit Dossier" : copy.action.openDossier}</span>
            <ExternalLink className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Read-Only Notice Bar if Auditor */}
      {caps.isReadOnly && (
        <div className="bg-seal-wash/40 border border-seal/30 rounded-cell px-3 py-1 text-[11px] text-seal flex items-center space-x-2">
          <Lock className="h-3 w-3 shrink-0" />
          <span>
            <strong>Read-Only Audit Mode:</strong> You are viewing evidentiary records in read-only audit mode. Telemetry adjustment, link confirmation, and dossier signing are restricted.
          </span>
        </div>
      )}

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
