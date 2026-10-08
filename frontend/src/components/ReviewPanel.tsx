"use client";

import React, { useState } from "react";
import { reviewCase } from "@/lib/api";
import { Check, XCircle, AlertCircle, RefreshCw } from "lucide-react";

interface ReviewPanelProps {
  caseId: string;
  status: string;
  onReviewed?: () => void;
}

export function ReviewPanel({ caseId, status, onReviewed }: ReviewPanelProps) {
  const [loading, setLoading] = useState(false);
  const [comment, setComment] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleReview = async (reviewStatus: "APPROVED" | "REJECTED" | "REWORK") => {
    setLoading(true);
    setFeedback(null);
    try {
      await reviewCase(
        caseId,
        reviewStatus,
        comment || `Action ${reviewStatus} executed by Compliance Officer.`
      );
      setFeedback(`Case successfully marked as ${reviewStatus}!`);
      onReviewed?.();
    } catch (e: any) {
      setFeedback(`Failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const isPublished = status === "PUBLISHED";

  return (
    <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">
            Compliance Review & Governance Sign-Off
          </h3>
          <span className="text-xs text-slate-400">Current Lifecycle: <strong className="text-emerald-400 font-mono">{status}</strong></span>
        </div>
      </div>

      {feedback && (
        <div className="p-3 rounded-lg bg-slate-950 border border-emerald-500/30 text-xs text-emerald-300">
          {feedback}
        </div>
      )}

      {!isPublished ? (
        <div className="space-y-3">
          <textarea
            placeholder="Compliance notes / audit comment..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={2}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500/50"
          />

          <div className="flex items-center space-x-2">
            <button
              onClick={() => handleReview("APPROVED")}
              disabled={loading}
              className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs shadow-lg shadow-emerald-500/20 transition disabled:opacity-50"
            >
              <Check className="h-4 w-4 stroke-[3]" />
              <span>Approve & Publish Case</span>
            </button>

            <button
              onClick={() => handleReview("REWORK")}
              disabled={loading}
              className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 font-semibold text-xs transition disabled:opacity-50"
            >
              <AlertCircle className="h-4 w-4" />
              <span>Request Rework</span>
            </button>

            <button
              onClick={() => handleReview("REJECTED")}
              disabled={loading}
              className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-rose-950/40 text-rose-400 border border-slate-700 font-semibold text-xs transition disabled:opacity-50"
            >
              <XCircle className="h-4 w-4" />
              <span>Reject Case</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="p-3 rounded-xl bg-emerald-950/20 border border-emerald-500/40 text-xs text-emerald-300 flex items-center space-x-2">
          <Check className="h-4 w-4 text-emerald-400 shrink-0 stroke-[3]" />
          <span>Case is APPROVED and officially PUBLISHED in the public evidence ledger.</span>
        </div>
      )}
    </div>
  );
}
export default ReviewPanel;
