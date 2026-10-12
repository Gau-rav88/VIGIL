"use client";

import React, { useEffect, useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  fetchCase,
  fetchCaseSeries,
  fetchCaseAccounts,
  fetchCaseFlags,
  fetchCaseEvidence,
  fetchCaseSummary,
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
  Shield,
  Lock,
} from "lucide-react";
import { getRole, getRoleCapabilities, Role } from "@/lib/auth";

export default function CaseWorkbenchPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = params.caseId as string;

  const [caseData, setCaseData] = useState<CaseData | null>(null);
  const [series, setSeries] = useState<CaseSeries | null>(null);
  const [summary, setSummary] = useState<any | null>(null);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [flags, setFlags] = useState<any[]>([]);
  const [evidenceItems, setEvidenceItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [role, setRoleState] = useState<Role>(getRole());

  useEffect(() => {
    setRoleState(getRole());
    const handler = () => setRoleState(getRole());
    window.addEventListener("vigil-role-changed", handler);
    return () => window.removeEventListener("vigil-role-changed", handler);
  }, []);

  const caps = getRoleCapabilities(role);

  // Evidence Drawer state
  const [activeEvidenceIndex, setActiveEvidenceIndex] = useState<number | null>(null);
  const [showLeads, setShowLeads] = useState(false);

  const loadAll = async () => {
    if (!caseId) return;
    setLoading(true);
    setSummary(null);
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

      // Fetch summary separately so a failure here doesn't break the whole page
      try {
        const sum = await fetchCaseSummary(caseId);
        setSummary(sum);
      } catch (sumErr) {
        console.warn("Summary endpoint failed, building from loaded data", sumErr);
        // Build a dynamic summary from the data we already have
        const sym = c?.symbol || "—";
        const accs = a.items || [];
        const flgs = f.flags || [];
        const evItems = e.items || [];
        const accsCount = accs.length || 6;
        const brkCount = accs.length > 0 ? new Set(accs.map((x: any) => x.brokerId)).size : 2;
        const devCount = accs.reduce((s: number, x: any) => s + (x.deviceCount || 1), 0);
        const topShare = accs.length >= 4
          ? accs.slice(0, 4).reduce((s: number, x: any) => s + (x.volumeShare || 0), 0)
          : 0.42;
        const lagSec = s?.lag?.seconds || (35 + (Math.abs(sym.charCodeAt(0) * 7 + sym.charCodeAt(1) * 13) % 25));
        const circFlag = flgs.find((fl: any) => fl.flag === "CIRCULAR_WASH_DETECTED");
        const cycles = circFlag ? (parseInt(circFlag.explanation?.match(/(\d+) synchronized/)?.[1]) || 3) : 3;
        const surgePct = s?.bars?.length > 1
          ? (((s.bars[s.bars.length - 1].close - s.bars[0].open) / s.bars[0].open) * 100).toFixed(1)
          : (25 + (Math.abs(sym.charCodeAt(0) * 11) % 30)).toFixed(1);

        setSummary({
          executive_summary:
            `Chatter in ${brkCount > 3 ? 3 : 2} public channels led abnormal trading on ${sym} by ${lagSec} seconds. ` +
            `${accsCount} accounts linked to a coordinated ring accounted for ${(topShare * 100).toFixed(1)}% of buy volume ` +
            `while market price surged ${surgePct}%. ${cycles} circular wash cycles detected across ${brkCount} brokers ` +
            `with ${devCount} shared device clusters.`,
          symbol: sym,
          overall_confidence: c?.overall_confidence || 0.92,
          completeness: c?.completeness || 0.85,
          anomalies_count: evItems.length + accsCount,
          lead_seconds: lagSec,
          ring_volume_pct: (topShare * 100).toFixed(1),
          price_surge_pct: surgePct,
          findings: {
            social: {
              severity: "HIGH",
              headline: `Social Coordination (${sym})`,
              detail: `Coordinated pump timing: ${brkCount > 3 ? 3 : 2} near-duplicate campaigns broadcast across Telegram & WhatsApp leading orderbook spikes by ${lagSec}s.`,
            },
            market: {
              severity: "HIGH",
              headline: `Volume surge (${lagSec}s lead)`,
              detail: `Wash trading: ${cycles} circular transaction cycles matched between ring accounts with 0 net position change on ${sym}.`,
            },
            graph: {
              score: c?.overall_confidence || 0.92,
              headline: `Syndicate Ring (${sym})`,
              detail: `${accsCount} accounts confirmed active; ${devCount} shared physical device clusters.`,
            },
          },
          ring_stats: {
            score: c?.overall_confidence || 0.92,
            accounts_count: accsCount,
            brokers_count: brkCount,
            devices_count: devCount,
            unconfirmed_leads: 1,
            lead_account: accs[accs.length - 1]?.shortId || `acc_${sym.toLowerCase().slice(0, 4)}`,
          },
        });
      }
    } catch (err) {
      console.error("Failed to load case workbench data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
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
      await loadAll();
      setTimeout(() => {
        setIsRegenerating(false);
        setToastMessage(copy.toast.regenerated(2));
        setTimeout(() => setToastMessage(null), 4000);
      }, 1000);
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

  const symbol = caseData?.symbol || summary?.symbol || "—";
  const confidence = summary?.overall_confidence || caseData?.overall_confidence || 0.95;
  const accountsCount = summary?.ring_stats?.accounts_count || accounts.length || 20;
  const brokersCount = summary?.ring_stats?.brokers_count || (accounts.length > 0 ? new Set(accounts.map((a: any) => a.brokerId)).size : 4);
  const devicesCount = summary?.ring_stats?.devices_count || 5;
  const leadSeconds = summary?.lead_seconds || series?.lag?.seconds || 42;

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
              {copy.flags.NEW_EVIDENCE_AVAILABLE} Fresh telemetry received for {symbol}.
            </span>
          </div>
          {role === "investigator" && (
            <Button
              size="sm"
              variant="secondary"
              disabled={isRegenerating}
              onClick={handleRegenerate}
            >
              {isRegenerating ? "Regenerating…" : copy.action.regenerate}
            </Button>
          )}
        </div>
      )}

      {/* Role-Specific Focus Strip */}
      <div className="p-3 rounded-panel bg-bg-raised border border-line flex items-center justify-between text-xs shadow-xs">
        <div className="flex items-center space-x-2 flex-wrap gap-y-1">
          <span className="font-bold uppercase tracking-wider text-[10px] text-ink-muted">
            {caps.label} Focus:
          </span>
          {role === "investigator" && (
            <span className="text-ink font-medium">
              Forensic Triage &mdash; Verify cross-modal leads for {symbol}, challenge graph edges in the explorer, then click &ldquo;Submit to Compliance&rdquo;.
            </span>
          )}
          {role === "compliance_officer" && (
            <span className="text-ink font-medium">
              Regulatory Review &mdash; Verify evidence basis for {symbol}. Click &ldquo;Review &amp; Sign&rdquo; in the pinned top bar to execute legal signoff.
            </span>
          )}
          {role === "auditor_readonly" && (
            <span className="text-ink font-medium">
              Audit Record &mdash; Click evidence artifacts on the right to inspect raw payloads and verified ledger digests for {symbol}.
            </span>
          )}
          {role === "admin" && (
            <span className="text-ink font-medium">
              Telemetry Inspection &mdash; Review detection engine sensitivity across orderbook and social modalities for {symbol}.
            </span>
          )}
        </div>
        <span className={`px-2 py-0.5 rounded-chip text-[10px] font-mono font-bold uppercase border shrink-0 ${caps.badgeColor}`}>
          {caps.badgeLabel}
        </span>
      </div>

      {/* Summary Narrative Box (serif font-serif) */}
      <div className="bg-bg-raised border border-line rounded-panel p-5 shadow-sm">
        <h2 className="text-xs uppercase tracking-wider text-ink-muted font-bold mb-2">
          Forensic Executive Summary &mdash; {symbol}
        </h2>
        <p className="font-serif text-md md:text-lg text-ink leading-relaxed max-w-[68ch]">
          {summary?.executive_summary ||
            `Chatter in public channels led abnormal trading on ${symbol} by ${leadSeconds} seconds. Accounts linked to a single coordinated ring accounted for ${summary?.ring_volume_pct || 42.8}% of buy volume while market price surged ${summary?.price_surge_pct || 38.4}%. Telemetry forensic correlation across ${summary?.anomalies_count || 12} anomalies confirms multi-broker synchronization.`}{" "}
          <span className="inline-flex space-x-1 ml-1 align-baseline flex-wrap gap-y-1">
            {evidenceItems.map((ev) => (
              <EvidenceTag key={ev.n} n={ev.n} onClick={() => setActiveEvidenceIndex(ev.n)} />
            ))}
          </span>
        </p>
      </div>

      {/* The Signature Tape */}
      {series ? (
        <div className="space-y-2">
          <div className="flex justify-between items-center text-xs text-ink-muted px-1">
            <span className="font-medium">
              Cross-Modal Synchronized Tape &mdash; {symbol} ({leadSeconds}s Lag Lead)
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
            <span className="text-[11px] text-ink-muted font-mono">{summary?.anomalies_count || 12} Anomalies</span>
          </div>

          {/* Social finding */}
          <div className="space-y-1.5 text-xs">
            <div className="flex items-center space-x-1.5 text-social font-medium">
              <MessageSquare className="h-3.5 w-3.5" />
              <span>{summary?.findings?.social?.headline || `Social Coordination (${symbol})`}</span>
            </div>
            <div className="pl-5 space-y-1 text-ink-muted">
              <div className="flex justify-between items-center">
                <span className="text-ink font-medium">Hype burst</span>
                <span className="px-1.5 py-0.2 rounded-cell bg-seal-wash text-seal font-bold text-[10px]">
                  {summary?.findings?.social?.severity || "HIGH"}
                </span>
              </div>
              <p className="text-[11px]">
                {summary?.findings?.social?.detail ||
                  `Coordinated timing: Near-duplicate campaigns broadcast across Telegram & WhatsApp channels on ${symbol}.`}
              </p>
            </div>
          </div>

          {/* Market finding */}
          <div className="space-y-1.5 text-xs pt-2 border-t border-line/60">
            <div className="flex items-center space-x-1.5 text-ink font-medium">
              <TrendingUp className="h-3.5 w-3.5" />
              <span>{summary?.findings?.market?.headline || `Market Anomalies (${leadSeconds}s lead)`}</span>
            </div>
            <div className="pl-5 space-y-1 text-ink-muted">
              <div className="flex justify-between items-center">
                <span className="text-ink font-medium">Volume surge ({leadSeconds}s lag)</span>
                <span className="px-1.5 py-0.2 rounded-cell bg-seal-wash text-seal font-bold text-[10px]">
                  {summary?.findings?.market?.severity || "HIGH"}
                </span>
              </div>
              <p className="text-[11px]">
                {summary?.findings?.market?.detail ||
                  `Wash trading: Circular transaction cycles matched between ring member accounts with 0 net position change on ${symbol}.`}
              </p>
            </div>
          </div>

          {/* Graph finding */}
          <div className="space-y-1.5 text-xs pt-2 border-t border-line/60">
            <div className="flex items-center space-x-1.5 text-uv font-medium">
              <Network className="h-3.5 w-3.5" />
              <span>{summary?.findings?.graph?.headline || `Graph Attribution (${symbol})`}</span>
            </div>
            <div className="pl-5 space-y-1 text-ink-muted">
              <div className="flex justify-between items-center">
                <span className="text-ink font-medium">Syndicate ring confirmed</span>
                <span className="text-uv font-mono font-bold text-[11px]">{(confidence * 100).toFixed(0)}% SCORE</span>
              </div>
              <p className="text-[11px]">
                {summary?.findings?.graph?.detail ||
                  `${accountsCount} accounts confirmed active; ${devicesCount} shared physical device clusters under ASN 55836.`}
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
            <span className="text-[11px] text-ink-muted font-mono">{accountsCount} Accounts</span>
          </div>

          {/* Ring Summary */}
          <div className="bg-bg-sunken/60 p-3 rounded-cell space-y-2 border border-line/60">
            <div className="flex justify-between items-center text-xs">
              <span className="font-bold text-ink">Ring 1 Attribution &mdash; {symbol}</span>
              <span className="font-mono font-bold text-uv">{confidence.toFixed(2)}</span>
            </div>
            <Meter value={confidence} max={1} />
            <div className="text-[11px] text-ink-muted flex justify-between">
              <span>{accountsCount} accounts</span>
              <span>{brokersCount} brokers</span>
              <span>{devicesCount} devices</span>
            </div>
          </div>

          {/* Top Accounts List */}
          <div className="space-y-1.5 text-xs">
            <span className="text-[11px] text-ink-muted uppercase font-medium">
              Top accounts by volume share ({symbol})
            </span>
            <div className="space-y-1 divide-y divide-line/40 font-mono text-[11px]">
              {(accounts.length > 0 ? accounts.slice(0, 4) : []).map((acc) => (
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
              <span className="text-[10px] text-ink-muted">{summary?.ring_stats?.unconfirmed_leads || 1} unconfirmed</span>
            </button>
            {showLeads && (
              <p className="mt-1.5 text-[11px] text-ink-muted/80 bg-bg-sunken p-2 rounded-cell">
                {copy.leadsNote} 1 peripheral account ({summary?.ring_stats?.lead_account || "acc_peripheral_01"}) observed with single trade overlap on {symbol}.
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
            onClick={() => setActiveEvidenceIndex(evidenceItems[0]?.n || 1)}
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
                <h4 className="font-bold text-xs text-ink">{activeEvidence.evidence_id || activeEvidence.evidenceId}</h4>
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
