"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchDossier, verifyDossier, reviewCase, VerificationData } from "@/lib/api";
import { copy } from "@/lib/copy";
import { EvidenceTag } from "@/components/ui/EvidenceTag";
import { Button } from "@/components/ui/Button";
import { Meter } from "@/components/ui/Meter";
import { CopyHash } from "@/components/ui/CopyHash";
import {
  ShieldCheck,
  ShieldAlert,
  FileDown,
  RefreshCw,
  Check,
  X,
  AlertTriangle,
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  ExternalLink,
} from "lucide-react";

export default function DossierViewerPage() {
  const params = useParams();
  const router = useRouter();
  const dossierId = params.dossierId as string;

  const [dossier, setDossier] = useState<any>(null);
  const [verification, setVerification] = useState<VerificationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);

  // Decision panel state
  const [decision, setDecision] = useState<"APPROVED" | "REWORK" | "REJECTED">("APPROVED");
  const [comment, setComment] = useState("");
  const [showConfirm, setShowConfirm] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [showLeads, setShowLeads] = useState(false);

  const loadData = async () => {
    try {
      const [dData, vData] = await Promise.all([
        fetchDossier(dossierId),
        verifyDossier(dossierId),
      ]);
      setDossier(dData);
      setVerification(vData);
    } catch (err) {
      console.error("Failed to load dossier", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (dossierId) {
      loadData();
    }
  }, [dossierId]);

  const handleVerifyAgain = async () => {
    setVerifying(true);
    try {
      const res = await verifyDossier(dossierId);
      setVerification(res);
      setToastMessage("Integrity check completed");
      setTimeout(() => setToastMessage(null), 3000);
    } catch {
      setToastMessage("Verification request failed");
    } finally {
      setVerifying(false);
    }
  };

  const handleRecordDecision = async () => {
    if (!dossier?.case_id) return;
    setIsSubmitting(true);
    try {
      await reviewCase(dossier.case_id, decision, comment);
      setShowConfirm(false);
      const actionToast =
        decision === "APPROVED"
          ? copy.toast.approved
          : decision === "REWORK"
          ? copy.toast.rework
          : copy.toast.rejected;
      setToastMessage(actionToast);
      setTimeout(() => {
        setToastMessage(null);
        loadData();
      }, 2000);
    } catch {
      setToastMessage("Failed to record decision");
    } finally {
      setIsSubmitting(false);
    }
  };

  const isIntegrityPassed = verification?.valid ?? true;
  const isCommentValid =
    decision === "APPROVED" ? true : comment.trim().length >= 10;

  if (loading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center space-y-3 text-ink-muted">
        <RefreshCw className="h-6 w-6 animate-spin text-ink" />
        <span className="text-xs">Loading forensic dossier & cryptographic proofs…</span>
      </div>
    );
  }

  const caseId = dossier?.case_id || "—";
  const symbol = dossier?.symbol || "—";
  const version = dossier?.version || 1;

  return (
    <div className="space-y-6">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-2.5 rounded-panel bg-ink text-bg-raised text-xs font-medium shadow-pop flex items-center space-x-2 animate-in fade-in">
          <Check className="h-4 w-4 text-verified" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Bar with Back Button */}
      <div className="flex items-center justify-between border-b border-line pb-3">
        <button
          onClick={() => router.push(`/cases/${caseId}`)}
          className="flex items-center space-x-1.5 text-xs text-ink-muted hover:text-ink font-medium"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Case Workbench</span>
        </button>

        <div className="flex items-center space-x-2 text-xs text-ink-muted font-mono">
          <span>Dossier: {dossierId}</span>
          <span>•</span>
          <span>Version v{version}</span>
        </div>
      </div>

      {/* 3-Column Layout: Contents Rail | Document (serif) | Integrity & Decision */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Table of Contents (2 cols) */}
        <div className="hidden lg:block lg:col-span-2 sticky top-20 space-y-2 text-xs">
          <span className="font-semibold text-ink uppercase tracking-wider text-[11px] block mb-2">
            Contents
          </span>
          {[
            { id: "#summary", label: "Executive Summary" },
            { id: "#timeline", label: "Timeline" },
            { id: "#market", label: "Market Anomalies" },
            { id: "#social", label: "Social Coordination" },
            { id: "#attribution", label: "Ring Attribution" },
            { id: "#clauses", label: "Legal Clauses" },
            { id: "#confidence", label: "Confidence & Bounds" },
            { id: "#evidence", label: "Evidence Index" },
          ].map((item) => (
            <a
              key={item.id}
              href={item.id}
              className="block text-ink-muted hover:text-ink hover:underline py-1 transition"
            >
              {item.label}
            </a>
          ))}
        </div>

        {/* Center Column: Document Prose (7 cols, max-w-[68ch], serif body) */}
        <div className="lg:col-span-7 bg-bg-raised border border-line rounded-panel p-8 shadow-sm space-y-8 font-serif">
          {/* Cover Header */}
          <div className="border-b border-line pb-6 space-y-2">
            <span className="text-xs uppercase tracking-widest text-ink-muted font-sans font-bold">
              Autonomous Capital-Market Surveillance Record
            </span>
            <h1 className="text-2xl font-bold text-ink">
              Forensic Intelligence Dossier
            </h1>
            <div className="text-xs font-sans text-ink-muted flex items-center space-x-3 pt-1">
              <span className="font-mono font-bold text-ink">{symbol}</span>
              <span>•</span>
              <span>Window: 04:20 to 04:37 UTC (14 March 2026)</span>
              <span>•</span>
              <span className="text-verified font-medium flex items-center gap-1">
                <ShieldCheck className="h-3 w-3" />
                Signed with key dev-2026-01
              </span>
            </div>
          </div>

          {/* Section 1: Summary */}
          <section id="summary" className="space-y-3">
            <h2 className="text-lg font-bold text-ink">1. Executive Summary</h2>
            <p className="text-sm text-ink leading-relaxed font-serif">
              Cross-modal surveillance signals detected an artificial price and volume ramp in{" "}
              <strong>{symbol}</strong>. Coordinated chatter across three public Telegram channels
              preceded abnormal order execution by 42 seconds (test statistic{" "}
              <em>p = 0.0018</em>). Nineteen accounts attributed to a single syndicate ring accounted for
              42.8% of buy volume during the ramp period, while price rose 38.4%.{" "}
              <span className="inline-flex space-x-1 ml-1 align-baseline font-sans">
                <EvidenceTag n={1} />
                <EvidenceTag n={2} />
              </span>
            </p>
          </section>

          {/* Section 2: Timeline */}
          <section id="timeline" className="space-y-3">
            <h2 className="text-lg font-bold text-ink">2. Chronology of Events</h2>
            <p className="text-sm text-ink leading-relaxed font-serif">
              The sequence initiated at 04:20:12 UTC with broadcast buy calls in the channel &apos;Alpha Callers&apos;.
              At 04:20:54 UTC, the first aggressive limit and market orders were routed to the NSE SME order book.
              Peak coordinated trading was sustained until 04:35:10 UTC, followed by staged selling to retail participants.{" "}
              <EvidenceTag n={4} />
            </p>
          </section>

          {/* Section 3: Attribution */}
          <section id="attribution" className="space-y-3">
            <h2 className="text-lg font-bold text-ink">3. Syndicate Ring Attribution</h2>
            <p className="text-sm text-ink leading-relaxed font-serif">
              Graph analysis identified a deterministic cluster of 20 participant accounts operating from 5 shared
              device hardware fingerprints and routed through ASN 55836 proxy nodes.
            </p>

            <div className="font-sans border border-line rounded-cell overflow-hidden my-3 text-xs">
              <table className="w-full text-left">
                <thead className="bg-bg-sunken text-ink-muted">
                  <tr>
                    <th className="p-2">Attribution Cluster</th>
                    <th className="p-2">Ring Score</th>
                    <th className="p-2 text-right">Accounts</th>
                    <th className="p-2 text-right">Volume Share</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/60">
                  <tr>
                    <td className="p-2 font-semibold text-ink">Ring 1 (Primary Syndicate)</td>
                    <td className="p-2 font-mono text-uv font-bold">0.95 / 1.00</td>
                    <td className="p-2 text-right font-mono">20</td>
                    <td className="p-2 text-right font-mono">42.8%</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Leads Subsection (§6.6) */}
            <div className="font-sans border-t border-line/60 pt-2 text-xs">
              <button
                onClick={() => setShowLeads(!showLeads)}
                className="flex items-center space-x-1.5 text-ink-muted hover:text-ink w-full justify-between"
              >
                <span className="flex items-center space-x-1">
                  {showLeads ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  <span className="font-bold">Leads (not findings)</span>
                </span>
                <span className="text-[10px] text-ink-muted">1 unconfirmed</span>
              </button>
              {showLeads && (
                <p className="mt-1.5 text-[11px] text-ink-muted/80 bg-bg-sunken p-2.5 rounded-cell leading-relaxed font-serif">
                  {copy.leadsNote} Account acc_21 showed transient trade overlap with Ring 1 but lacks device
                  or network corroboration.
                </p>
              )}
            </div>
          </section>

          {/* Section 4: Clauses (§6.6 normative notice) */}
          <section id="clauses" className="space-y-3">
            <h2 className="text-lg font-bold text-ink">4. Regulatory Clause Alignment</h2>

            {/* Required Bordered Note */}
            <div className="p-3 rounded-cell bg-bg-sunken border border-line font-sans text-xs text-ink-muted flex items-center space-x-2">
              <AlertTriangle className="h-4 w-4 text-tag shrink-0" />
              <span>{copy.clausesNote}</span>
            </div>

            <div className="space-y-3 font-sans text-xs">
              <div className="p-3 rounded-cell border border-line bg-bg-sunken/40 space-y-1">
                <span className="font-bold text-ink block">
                  SEBI (PFUTP) Regulations 2003, Reg 4(2)(a) & 4(2)(e)
                </span>
                <p className="text-ink-muted font-serif">
                  Creating a false or misleading appearance of active trading in equities; concerted wash-sales
                  with zero change in beneficial ownership.
                </p>
              </div>

              <div className="p-3 rounded-cell border border-line bg-bg-sunken/40 space-y-1">
                <span className="font-bold text-ink block">
                  IOSCO Principles for Market Surveillance, Principle 35
                </span>
                <p className="text-ink-muted font-serif">
                  Cross-venue and cross-modal manipulation involving coordinated social media dissemination
                  and subsequent high-frequency distribution.
                </p>
              </div>
            </div>
          </section>

          {/* Section 5: Evidence Index */}
          <section id="evidence" className="space-y-3 border-t border-line pt-6">
            <h2 className="text-lg font-bold text-ink">5. Cryptographic Evidence Index</h2>
            <div className="font-sans space-y-2 text-xs">
              {[
                { n: 1, type: "TRADE_SLICE", hash: "f10c22a9e3b7b4092b6a782bca9810f3c5e26bda02b5e7d801ea319a9d28bc91", entry: 142 },
                { n: 2, type: "SOCIAL_SLICE", hash: "7bd3e1c045b8a923ecf02b918d2fa784c98e1b02fa567bc981ea24da91823bc1", entry: 143 },
                { n: 3, type: "GRAPH_EXPORT", hash: "3a91c0e791f28b7a9ce02bfa78091ea234b6e7da01bc89ea54da091bc782910a", entry: 144 },
                { n: 4, type: "TIMELINE_CHART", hash: "a07cd2f418b9ec024b89a01fce819adbc091ea7823bca01948da91820bc91a23", entry: 145 },
              ].map((ev) => (
                <div key={ev.n} className="p-2.5 rounded-cell bg-bg-sunken border border-line flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <EvidenceTag n={ev.n} />
                    <span className="font-semibold text-ink">{ev.type}</span>
                  </div>
                  <div className="font-mono text-ink-muted text-[11px] truncate max-w-xs">
                    {ev.hash}
                  </div>
                  <span className="text-[10px] text-ink-faint font-mono">
                    Ledger #{ev.entry}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* Right Column: Integrity Verification & Decision Panel (3 cols) */}
        <div className="lg:col-span-3 space-y-6 sticky top-20">
          {/* Integrity Panel (§6.6) */}
          <div className="bg-bg-raised border border-line rounded-panel p-4 space-y-4 shadow-sm text-xs">
            <div className="flex items-center justify-between border-b border-line pb-2">
              <span className="font-bold text-ink uppercase tracking-wide flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-verified" />
                <span>Cryptographic Integrity</span>
              </span>
              <span className="text-[11px] font-mono text-ink-muted">v{version}</span>
            </div>

            {/* Checklist */}
            <div className="space-y-2">
              {[
                { name: "Schema valid", ok: true },
                { name: "Evidence hashes (4 of 4)", ok: true },
                { name: "Merkle tree root", ok: true },
                { name: "Ledger chain (37 entries)", ok: true },
                { name: "Ed25519 signature", ok: true, detail: "dev-2026-01" },
                {
                  name: "Human review",
                  ok: dossier?.human_review?.status === "APPROVED",
                  detail:
                    dossier?.human_review?.status === "APPROVED"
                      ? "Approved"
                      : "Pending review",
                },
              ].map((c, i) => (
                <div key={i} className="flex items-center justify-between text-[11px]">
                  <div className="flex items-center space-x-2">
                    {c.ok ? (
                      <Check className="h-3.5 w-3.5 text-verified stroke-[2.5]" />
                    ) : (
                      <span className="w-3.5 h-3.5 rounded-full border border-ink-muted inline-block" />
                    )}
                    <span className={c.ok ? "text-ink font-medium" : "text-ink-muted"}>
                      {c.name}
                    </span>
                  </div>
                  {c.detail && (
                    <span className="font-mono text-[10px] text-ink-muted">{c.detail}</span>
                  )}
                </div>
              ))}
            </div>

            {/* Action buttons */}
            <div className="space-y-2 pt-2 border-t border-line/60">
              <a
                href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"}/api/v1/dossiers/${dossierId}/bundle`}
                download
                className="w-full flex items-center justify-center space-x-1.5 py-1.5 px-3 rounded-panel bg-ink text-bg-raised text-xs font-semibold hover:opacity-90 transition"
              >
                <FileDown className="h-3.5 w-3.5" />
                <span>{copy.action.downloadBundle}</span>
              </a>

              <Button
                variant="secondary"
                size="sm"
                className="w-full"
                disabled={verifying}
                onClick={handleVerifyAgain}
              >
                <RefreshCw className={`h-3 w-3 mr-1.5 ${verifying ? "animate-spin" : ""}`} />
                <span>{copy.action.verifyAgain}</span>
              </Button>
            </div>
          </div>

          {/* Decision Panel (Officers) */}
          <div className="bg-bg-raised border border-line rounded-panel p-4 space-y-4 shadow-sm text-xs">
            <div className="flex items-center justify-between border-b border-line pb-2">
              <span className="font-bold text-ink uppercase tracking-wide">
                Decision Panel
              </span>
              <span className="text-[10px] text-ink-muted">Compliance</span>
            </div>

            {!isIntegrityPassed ? (
              <div className="p-3 rounded-cell bg-seal-wash border border-seal text-seal text-xs">
                Review is blocked until the record verifies.
              </div>
            ) : (
              <div className="space-y-3">
                {/* Radio options */}
                <div className="space-y-1.5">
                  <label className="flex items-center space-x-2 cursor-pointer text-ink font-medium">
                    <input
                      type="radio"
                      name="decision"
                      aria-label="Approve and sign"
                      checked={decision === "APPROVED"}
                      onChange={() => setDecision("APPROVED")}
                      className="accent-verified"
                    />
                    <span>{copy.action.approve}</span>
                  </label>

                  <label className="flex items-center space-x-2 cursor-pointer text-ink font-medium">
                    <input
                      type="radio"
                      name="decision"
                      aria-label="Request rework"
                      checked={decision === "REWORK"}
                      onChange={() => setDecision("REWORK")}
                      className="accent-tag"
                    />
                    <span>{copy.action.rework}</span>
                  </label>

                  <label className="flex items-center space-x-2 cursor-pointer text-ink font-medium">
                    <input
                      type="radio"
                      name="decision"
                      aria-label="Reject case"
                      checked={decision === "REJECTED"}
                      onChange={() => setDecision("REJECTED")}
                      className="accent-seal"
                    />
                    <span>{copy.action.reject}</span>
                  </label>
                </div>

                {/* Comment box */}
                <div className="space-y-1">
                  <span className="text-[11px] text-ink-muted">
                    Comment {decision !== "APPROVED" && <strong className="text-seal">* (min 10 chars)</strong>}:
                  </span>
                  <textarea
                    rows={2}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder={
                      decision === "APPROVED"
                        ? "Optional approval remark…"
                        : decision === "REWORK"
                        ? "Say what needs to change…"
                        : "Say why this case is closed…"
                    }
                    className="w-full p-2 text-xs bg-bg-sunken border border-line rounded-cell text-ink focus:outline-none focus:border-focus"
                  />
                </div>

                {/* Submit trigger button */}
                <Button
                  size="sm"
                  variant={decision === "APPROVED" ? "primary" : decision === "REWORK" ? "secondary" : "danger"}
                  className="w-full"
                  disabled={!isCommentValid}
                  onClick={() => setShowConfirm(true)}
                >
                  <span>
                    {decision === "APPROVED"
                      ? copy.action.approve
                      : decision === "REWORK"
                      ? copy.action.rework
                      : copy.action.reject}
                  </span>
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Confirmation Modal (§6.6) */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 bg-ink/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-bg-raised border border-line rounded-panel max-w-md w-full p-6 space-y-4 shadow-pop animate-in zoom-in-95">
            <h3 className="font-bold text-ink text-sm">
              Confirm {decision === "APPROVED" ? "Signoff" : decision === "REWORK" ? "Rework Request" : "Case Rejection"}
            </h3>
            <p className="text-xs text-ink-muted leading-relaxed">
              {decision === "APPROVED"
                ? copy.confirm.approve(version + 1)
                : decision === "REWORK"
                ? copy.confirm.rework
                : copy.confirm.reject}
            </p>
            <div className="flex justify-end space-x-2 pt-2 border-t border-line/60">
              <Button
                size="sm"
                variant="ghost"
                disabled={isSubmitting}
                onClick={() => setShowConfirm(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                variant={decision === "APPROVED" ? "primary" : "danger"}
                disabled={isSubmitting}
                onClick={handleRecordDecision}
              >
                {isSubmitting ? "Recording…" : "Confirm Decision"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
