"use client";

import React, { useEffect, useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  fetchCase,
  fetchCaseSeries,
  fetchCaseAccounts,
  fetchCaseFlags,
  fetchCaseEvidence,
  postCaseDirective,
  CaseData,
} from "@/lib/api";
import { Tape } from "@/components/Tape/Tape";
import { EvidenceTag } from "@/components/ui/EvidenceTag";
import { Meter } from "@/components/ui/Meter";
import { Button } from "@/components/ui/Button";
import { CopyHash } from "@/components/ui/CopyHash";
import { copy } from "@/lib/copy";
import { CaseSeries, normalizeCaseSeries } from "@/lib/types";
import {
  RefreshCw,
  GitFork,
  FileText,
  AlertTriangle,
  X,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  TrendingUp,
  MessageSquare,
  Network,
  ShieldCheck,
} from "lucide-react";

export default function CaseWorkbenchPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = params.caseId as string;

  const [caseData, setCaseData] = useState<CaseData | null>(null);
  const [series, setSeries] = useState<CaseSeries | null>(null);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [flags, setFlags] = useState<any[]>([]);
  const [evidenceItems, setEvidenceItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Evidence Drawer state
  const [activeEvidenceIndex, setActiveEvidenceIndex] = useState<number | null>(null);
  const [showLeads, setShowLeads] = useState(false);

  useEffect(() => {
    if (!caseId) return;

    async function loadAll() {
      try {
        const [c, s, a, f, e] = await Promise.all([
          fetchCase(caseId),
          fetchCaseSeries(caseId),
          fetchCaseAccounts(caseId),
          fetchCaseFlags(caseId),
          fetchCaseEvidence(caseId),
        ]);
        setCaseData(c);
        setSeries(normalizeCaseSeries(s, c?.symbol));
        setAccounts(a.items || []);
        setFlags(f.flags || []);
        setEvidenceItems(e.items || []);
      } catch (err) {
        console.error("Failed to load case workbench data", err);
      } finally {
        setLoading(false);
      }
    }

    loadAll();
  }, [caseId]);

  const activeEvidence = useMemo(() => {
    if (activeEvidenceIndex === null) return null;
    return evidenceItems.find((e) => e.n === activeEvidenceIndex) || evidenceItems[0];
  }, [activeEvidenceIndex, evidenceItems]);

  const hasNewEvidence = flags.some((f) => f.flag === "NEW_EVIDENCE_AVAILABLE");

  const handleRegenerate = async () => {
    setIsRegenerating(true);
    setToastMessage(copy.toast.regenerating);
    try {
      await postCaseDirective(caseId, "FORCE_REATTRIBUTION", { window_end: "now" });
      setTimeout(() => {
        setIsRegenerating(false);
        setToastMessage(copy.toast.regenerated(2));
        setTimeout(() => setToastMessage(null), 4000);
      }, 1500);
    } catch {
      setIsRegenerating(false);
      setToastMessage("Failed to regenerate dossier");
    }
  };

  if (loading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center space-y-3 text-ink-muted">
        <RefreshCw className="h-6 w-6 animate-spin text-ink" />
        <span className="text-xs">Loading forensic timeline & evidence…</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 relative">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-2.5 rounded-panel bg-ink text-bg-raised text-xs font-medium shadow-pop flex items-center space-x-2 animate-in fade-in slide-in-from-bottom-2">
          <ShieldCheck className="h-4 w-4 text-verified" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* New Activity Notice */}
      {hasNewEvidence && (
        <div className="bg-tag-wash border border-tag/40 rounded-panel px-4 py-2.5 flex items-center justify-between text-xs text-tag-ink">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="h-4 w-4 text-tag-ink shrink-0" />
            <span className="font-medium">
              {copy.flags.NEW_EVIDENCE_AVAILABLE} Fresh telemetry received since version 1.
            </span>
          </div>
          <Button
            size="sm"
            variant="secondary"
            disabled={isRegenerating}
            onClick={handleRegenerate}
          >
            {isRegenerating ? "Regenerating…" : copy.action.regenerate}
          </Button>
        </div>
      )}

      {/* Summary Narrative Box (serif font-serif) */}
      <div className="bg-bg-raised border border-line rounded-panel p-5 shadow-sm">
        <h2 className="text-xs uppercase tracking-wider text-ink-muted font-bold mb-2">
          Forensic Executive Summary
        </h2>
        <p className="font-serif text-md md:text-lg text-ink leading-relaxed max-w-[68ch]">
          Chatter in three public channels led abnormal trading by 42 seconds. Accounts linked to a
          single coordinated ring accounted for 42.8% of buy volume while market price surged 38.4%.{" "}
          <span className="inline-flex space-x-1 ml-1 align-baseline">
            <EvidenceTag n={1} onClick={() => setActiveEvidenceIndex(1)} />
            <EvidenceTag n={2} onClick={() => setActiveEvidenceIndex(2)} />
            <EvidenceTag n={3} onClick={() => setActiveEvidenceIndex(3)} />
          </span>
        </p>
      </div>

      {/* The Signature Tape */}
      {series ? (
        <div className="space-y-2">
          <div className="flex justify-between items-center text-xs text-ink-muted px-1">
            <span className="font-medium">
              Cross-Modal Synchronized Tape (1-Hour Observation Window)
            </span>
            <div className="flex items-center space-x-2 text-[11px]">
              <span className="flex items-center space-x-1">
                <span className="w-2.5 h-2.5 rounded-full bg-social inline-block" />
                <span>Hype</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2.5 h-2.5 rounded-cell bg-market inline-block" />
                <span>Organic Vol</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2.5 h-2.5 rounded-cell bg-uv inline-block" />
                <span>Ring Vol</span>
              </span>
            </div>
          </div>
          <Tape series={series} />
        </div>
      ) : null}

      {/* Three Column Investigation Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Column 1: What the System Found */}
        <div className="bg-bg-raised border border-line rounded-panel p-4 space-y-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-line pb-2">
            <h3 className="font-semibold text-xs text-ink uppercase tracking-wide">
              What the system found
            </h3>
            <span className="text-[11px] text-ink-muted font-mono">3 Modalities</span>
          </div>

          {/* Social finding */}
          <div className="space-y-1.5 text-xs">
            <div className="flex items-center space-x-1.5 text-social font-medium">
              <MessageSquare className="h-3.5 w-3.5" />
              <span>Social Coordination</span>
            </div>
            <div className="pl-5 space-y-1 text-ink-muted">
              <div className="flex justify-between items-center">
                <span className="text-ink font-medium">Hype burst</span>
                <span className="px-1.5 py-0.2 rounded-cell bg-seal-wash text-seal font-bold text-[10px]">
                  HIGH
                </span>
              </div>
              <p className="text-[11px]">
                Coordinated timing: 3 near-duplicate campaigns broadcast across Telegram & WhatsApp.
              </p>
            </div>
          </div>

          {/* Market finding */}
          <div className="space-y-1.5 text-xs pt-2 border-t border-line/60">
            <div className="flex items-center space-x-1.5 text-ink font-medium">
              <TrendingUp className="h-3.5 w-3.5" />
              <span>Market Anomalies</span>
            </div>
            <div className="pl-5 space-y-1 text-ink-muted">
              <div className="flex justify-between items-center">
                <span className="text-ink font-medium">Volume surge (42s lag)</span>
                <span className="px-1.5 py-0.2 rounded-cell bg-seal-wash text-seal font-bold text-[10px]">
                  HIGH
                </span>
              </div>
              <p className="text-[11px]">
                Wash trading: 6 circular transaction cycles matched between 4 member accounts.
              </p>
            </div>
          </div>

          {/* Graph finding */}
          <div className="space-y-1.5 text-xs pt-2 border-t border-line/60">
            <div className="flex items-center space-x-1.5 text-uv font-medium">
              <Network className="h-3.5 w-3.5" />
              <span>Graph Attribution</span>
            </div>
            <div className="pl-5 space-y-1 text-ink-muted">
              <div className="flex justify-between items-center">
                <span className="text-ink font-medium">Syndicate ring confirmed</span>
                <span className="text-uv font-mono font-bold text-[11px]">0.95 SCORE</span>
              </div>
              <p className="text-[11px]">
                20 accounts confirmed active; 5 shared physical device clusters under ASN 55836.
              </p>
            </div>
          </div>
        </div>

        {/* Column 2: Accounts Panel */}
        <div className="bg-bg-raised border border-line rounded-panel p-4 space-y-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-line pb-2">
            <h3 className="font-semibold text-xs text-ink uppercase tracking-wide">
              Attributed Accounts
            </h3>
            <span className="text-[11px] text-ink-muted font-mono">{accounts.length} Accounts</span>
          </div>

          {/* Ring Summary */}
          <div className="bg-bg-sunken/60 p-3 rounded-cell space-y-2 border border-line/60">
            <div className="flex justify-between items-center text-xs">
              <span className="font-bold text-ink">Ring 1 Attribution</span>
              <span className="font-mono font-bold text-uv">0.95</span>
            </div>
            <Meter value={0.95} max={1} />
            <div className="text-[11px] text-ink-muted flex justify-between">
              <span>20 accounts</span>
              <span>4 brokers</span>
              <span>5 devices</span>
            </div>
          </div>

          {/* Top Accounts List */}
          <div className="space-y-1.5 text-xs">
            <span className="text-[11px] text-ink-muted uppercase font-medium">
              Top accounts by volume share
            </span>
            <div className="space-y-1 divide-y divide-line/40 font-mono text-[11px]">
              {accounts.slice(0, 4).map((acc) => (
                <div key={acc.accountId} className="pt-1 flex justify-between items-center">
                  <span className="text-ink font-medium">{acc.shortId}</span>
                  <span className="text-ink-muted">{acc.brokerId}</span>
                  <span className="text-uv font-bold">{(acc.volumeShare * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>

          {/* Collapsible Leads Section */}
          <div className="border-t border-line/60 pt-2 text-xs">
            <button
              onClick={() => setShowLeads(!showLeads)}
              className="flex items-center space-x-1.5 text-ink-muted hover:text-ink w-full justify-between"
            >
              <span className="flex items-center space-x-1">
                {showLeads ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                <span className="font-medium">Leads (not findings)</span>
              </span>
              <span className="text-[10px] text-ink-muted">1 unconfirmed</span>
            </button>
            {showLeads && (
              <p className="mt-1.5 text-[11px] text-ink-muted/80 bg-bg-sunken p-2 rounded-cell">
                {copy.leadsNote} 1 peripheral account (acc_21) observed with single trade overlap.
              </p>
            )}
          </div>

          <Button
            variant="secondary"
            size="sm"
            className="w-full"
            onClick={() => router.push(`/cases/${caseId}/graph`)}
          >
            <GitFork className="h-3.5 w-3.5 mr-1.5" />
            <span>{copy.action.openGraph}</span>
          </Button>
        </div>

        {/* Column 3: Evidence List */}
        <div className="bg-bg-raised border border-line rounded-panel p-4 space-y-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-line pb-2">
            <h3 className="font-semibold text-xs text-ink uppercase tracking-wide">
              Cryptographic Evidence
            </h3>
            <span className="text-[11px] text-ink-muted font-mono">{evidenceItems.length} Artifacts</span>
          </div>

          <div className="space-y-2">
            {evidenceItems.map((ev) => (
              <div
                key={ev.n}
                onClick={() => setActiveEvidenceIndex(ev.n)}
                className={`p-2.5 rounded-cell border cursor-pointer transition ${
                  activeEvidenceIndex === ev.n
                    ? "bg-tag-wash/30 border-tag"
                    : "bg-bg-sunken/40 border-line hover:border-line-strong"
                }`}
              >
                <div className="flex items-center justify-between text-xs mb-1">
                  <div className="flex items-center space-x-1.5">
                    <EvidenceTag n={ev.n} />
                    <span className="font-semibold text-ink">{ev.type}</span>
                  </div>
                  <span className="text-[10px] text-ink-muted font-mono">
                    Entry #{ev.ledgerEntryId}
                  </span>
                </div>
                <div className="text-[11px] font-mono text-ink-muted truncate">
                  {ev.sha256}
                </div>
              </div>
            ))}
          </div>

          <Button
            variant="secondary"
            size="sm"
            className="w-full"
            onClick={() => setActiveEvidenceIndex(1)}
          >
            <FileText className="h-3.5 w-3.5 mr-1.5" />
            <span>View in Drawer</span>
          </Button>
        </div>
      </div>

      {/* 480px Evidence Drawer (slides in from right) */}
      {activeEvidence && (
        <div className="fixed inset-y-0 right-0 z-50 w-full max-w-[480px] bg-bg-raised border-l border-line shadow-pop flex flex-col animate-in slide-in-from-right duration-200">
          {/* Drawer Header */}
          <div className="p-4 border-b border-line flex items-center justify-between bg-bg-sunken/40">
            <div className="flex items-center space-x-2">
              <EvidenceTag n={activeEvidence.n} />
              <div>
                <h4 className="font-bold text-xs text-ink">{activeEvidence.evidenceId}</h4>
                <span className="text-[10px] text-ink-muted uppercase">
                  {activeEvidence.type}
                </span>
              </div>
            </div>
            <button
              onClick={() => setActiveEvidenceIndex(null)}
              className="p-1 rounded-cell hover:bg-bg-sunken text-ink-muted hover:text-ink transition"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
            {/* Hash & Verification Meta */}
            <div className="bg-bg-sunken p-3 rounded-cell space-y-2 border border-line">
              <div className="flex justify-between items-center text-[11px]">
                <span className="font-semibold text-ink">SHA-256 Digest</span>
                <span className="text-verified font-medium flex items-center gap-1">
                  <ShieldCheck className="h-3 w-3" />
                  Verified in Ledger
                </span>
              </div>
              <CopyHash hash={activeEvidence.sha256} />
              <p className="text-[11px] text-ink-muted">
                Hash computed at capture, recorded in the tamper-evident ledger as entry #
                {activeEvidence.ledgerEntryId}.
              </p>
            </div>

            {/* Evidence Summary */}
            <div className="space-y-1">
              <span className="font-semibold text-ink text-[11px] uppercase tracking-wide">
                Summary
              </span>
              <p className="text-ink-muted leading-relaxed">{activeEvidence.summary}</p>
            </div>

            {/* Evidence Payload Display */}
            {activeEvidence.rows && (
              <div className="space-y-1.5">
                <span className="font-semibold text-ink text-[11px] uppercase tracking-wide">
                  Normalized Trade Rows
                </span>
                <div className="border border-line rounded-cell overflow-hidden">
                  <table className="w-full text-left text-[11px] font-mono divide-y divide-line">
                    <thead className="bg-bg-sunken text-ink-muted">
                      <tr>
                        <th className="p-1.5">Time</th>
                        <th className="p-1.5">Acc</th>
                        <th className="p-1.5">Side</th>
                        <th className="p-1.5 text-right">Qty</th>
                        <th className="p-1.5 text-right">Price</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line/60">
                      {activeEvidence.rows.map((row: any, i: number) => (
                        <tr key={i} className="hover:bg-bg-sunken/40">
                          <td className="p-1.5 text-ink-muted">{row.timestamp}</td>
                          <td className="p-1.5 text-ink font-semibold">{row.account}</td>
                          <td className={`p-1.5 font-bold ${row.side === "BUY" ? "text-verified" : "text-seal"}`}>
                            {row.side}
                          </td>
                          <td className="p-1.5 text-right">{row.qty}</td>
                          <td className="p-1.5 text-right">{row.price.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeEvidence.messages && (
              <div className="space-y-1.5">
                <span className="font-semibold text-ink text-[11px] uppercase tracking-wide">
                  Social Capture & Hinglish Transcripts
                </span>
                <div className="space-y-2">
                  {activeEvidence.messages.map((msg: any, i: number) => (
                    <div key={i} className="p-2.5 rounded-cell bg-bg-sunken border border-line space-y-1">
                      <div className="flex justify-between items-center text-[10px] text-ink-muted">
                        <span className="font-semibold text-social">{msg.channel}</span>
                        <span>{msg.time}</span>
                      </div>
                      <p className="font-sans text-ink text-xs font-medium">&ldquo;{msg.text}&rdquo;</p>
                      <span className="text-[10px] text-ink-faint">Author: {msg.author}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Drawer Footer */}
          <div className="p-3 border-t border-line bg-bg-sunken/30 flex justify-end">
            <Button size="sm" variant="ghost" onClick={() => setActiveEvidenceIndex(null)}>
              Close (Esc)
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
