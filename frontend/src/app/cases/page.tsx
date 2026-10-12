"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { fetchCases, CaseData } from "@/lib/api";
import { copy } from "@/lib/copy";
import { formatTime, formatRelativeTime } from "@/lib/time";
import { Chip } from "@/components/ui/Chip";
import { EmptyState } from "@/components/ui/EmptyState";
import { Search, Filter, ShieldAlert, ArrowRight, Lock, ShieldCheck } from "lucide-react";
import { getRole, getRoleCapabilities, Role } from "@/lib/auth";

type SavedView = "AWAITING_REVIEW" | "NEEDS_REWORK" | "OPEN" | "WATCHLIST" | "ALL";

export default function CasesQueuePage() {
  const router = useRouter();
  const [cases, setCases] = useState<CaseData[]>([]);
  const [loading, setLoading] = useState(true);
  const [role, setRoleState] = useState<Role>(getRole());

  useEffect(() => {
    setRoleState(getRole());
    const handler = () => setRoleState(getRole());
    window.addEventListener("vigil-role-changed", handler);
    return () => window.removeEventListener("vigil-role-changed", handler);
  }, []);

  const caps = getRoleCapabilities(role);

  const [savedView, setSavedView] = useState<SavedView>(
    role === "compliance_officer" ? "AWAITING_REVIEW" : "ALL"
  );
  const [tickerQuery, setTickerQuery] = useState("");
  const [minRisk, setMinRisk] = useState<number>(0);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchCases();
        setCases(data);
      } catch (err) {
        console.error("Failed to load cases", err);
      } finally {
        setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  const filteredCases = useMemo(() => {
    return cases.filter((c) => {
      // Saved view filter
      if (savedView === "AWAITING_REVIEW" && c.status !== "PENDING_REVIEW") return false;
      if (savedView === "NEEDS_REWORK" && c.status !== "REJECTED") return false;
      if (savedView === "OPEN" && c.status !== "OPENED") return false;
      // Ticker filter
      if (tickerQuery && !c.symbol.toLowerCase().includes(tickerQuery.toLowerCase())) return false;
      // Risk filter (prioritize c.mrs, fallback to overall_confidence)
      const riskScore = c.mrs !== undefined && c.mrs !== null ? Math.round(c.mrs) : Math.round((c.overall_confidence ?? 0.86) * 100);
      if (minRisk > 0 && riskScore < minRisk) return false;
      return true;
    });
  }, [cases, savedView, tickerQuery, minRisk]);

  // Keyboard navigation: j/k, Enter, /
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (e.key === "j") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, filteredCases.length - 1));
      } else if (e.key === "k") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter" && filteredCases[selectedIndex]) {
        e.preventDefault();
        router.push(`/cases/${filteredCases[selectedIndex].case_id}`);
      } else if (e.key === "/") {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [filteredCases, selectedIndex, router]);

  return (
    <div className="space-y-6">
      {/* Title & Stats */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-line pb-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="font-serif text-xl font-semibold text-ink flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-ink" />
              <span>Case Queue</span>
            </h1>
            <span
              className={`px-2.5 py-0.5 rounded-chip text-[10px] font-mono font-bold uppercase border ${caps.badgeColor} flex items-center gap-1`}
              title={caps.description}
            >
              {caps.isReadOnly && <Lock className="h-3 w-3" />}
              <span>{caps.badgeLabel}</span>
            </span>
          </div>
          <p className="text-xs text-ink-muted mt-0.5">
            Surveillance desk forensic cases awaiting attribution, verification, or compliance signoff.
          </p>
        </div>
        <div className="flex items-center space-x-2 text-xs text-ink-muted">
          <span>Active filter matches:</span>
          <strong className="text-ink font-mono">{filteredCases.length}</strong>
        </div>
      </div>

      {/* Role Dedicated Workflow Bar */}
      <div className="p-3 rounded-panel bg-bg-raised border border-line flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs shadow-xs">
        <div className="flex items-center space-x-2 flex-wrap gap-y-1">
          <span className="font-bold uppercase tracking-wider text-ink-muted text-[10px] shrink-0">
            {caps.label} Workflow:
          </span>
          {role === "investigator" && (
            <span className="text-ink font-medium">
              1. Triage open case &rarr; 2. Analyze forensic tape &rarr; 3. Confirm graph attribution &rarr; 4. Click &ldquo;Submit to Compliance&rdquo;
            </span>
          )}
          {role === "compliance_officer" && (
            <span className="text-ink font-medium">
              1. Select case pending review &rarr; 2. Inspect cryptographic evidence &rarr; 3. Click &ldquo;Review &amp; Sign&rdquo; for legal signoff
            </span>
          )}
          {role === "admin" && (
            <span className="text-ink font-medium">
              1. Inspect cases &rarr; 2. Use Simulator Engine to inject synthetic manipulation and test detection
            </span>
          )}
          {role === "auditor_readonly" && (
            <span className="text-ink font-medium">
              1. Select case record &rarr; 2. Verify Merkle proofs &amp; SHA-256 evidence digests against ledger
            </span>
          )}
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-bg-raised border border-line rounded-panel p-3 flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Saved Views */}
        <div className="flex items-center space-x-1.5 flex-wrap">
          <span className="text-ink-muted mr-1 font-medium">Saved views:</span>
          {[
            { id: "ALL", label: "All" },
            { id: "AWAITING_REVIEW", label: "Awaiting review" },
            { id: "NEEDS_REWORK", label: "Needs rework" },
            { id: "OPEN", label: "Open" },
            { id: "WATCHLIST", label: "Watching" },
          ].map((view) => (
            <button
              key={view.id}
              onClick={() => setSavedView(view.id as SavedView)}
              className={`px-2.5 py-1 rounded-cell transition font-medium ${
                savedView === view.id
                  ? "bg-ink text-bg-raised"
                  : "bg-bg-sunken text-ink-muted hover:text-ink hover:bg-line/40"
              }`}
            >
              {view.label}
            </button>
          ))}
        </div>

        {/* Inputs */}
        <div className="flex items-center space-x-3">
          <div className="relative">
            <Search className="h-3.5 w-3.5 text-ink-muted absolute left-2.5 top-2 pointer-events-none" />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Search ticker… (/)"
              value={tickerQuery}
              onChange={(e) => setTickerQuery(e.target.value)}
              className="pl-8 pr-2.5 py-1 bg-bg-sunken border border-line rounded-cell text-ink placeholder:text-ink-muted/60 text-xs w-36 md:w-44 focus:outline-none focus:border-focus"
            />
          </div>

          <div className="flex items-center space-x-1.5">
            <span className="text-ink-muted">Min risk:</span>
            <input
              type="number"
              min="0"
              max="100"
              placeholder="0"
              value={minRisk || ""}
              onChange={(e) => setMinRisk(Number(e.target.value) || 0)}
              className="w-14 px-2 py-1 bg-bg-sunken border border-line rounded-cell text-ink text-xs focus:outline-none focus:border-focus font-mono"
            />
          </div>
        </div>
      </div>

      {/* Case Table */}
      {filteredCases.length === 0 ? (
        <EmptyState
          message={copy.empty.cases}
          actionLabel="Clear filters"
          onAction={() => {
            setSavedView("ALL");
            setTickerQuery("");
            setMinRisk(0);
          }}
        />
      ) : (
        <div className="bg-bg-raised border border-line rounded-panel overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-line bg-bg-sunken/60 text-ink-muted font-medium">
                  <th className="py-2.5 px-4">Ticker</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4 text-right">Risk (MRS)</th>
                  <th className="py-2.5 px-4 text-right">Confidence</th>
                  <th className="py-2.5 px-4 text-right">Completeness</th>
                  <th className="py-2.5 px-4">Window</th>
                  <th className="py-2.5 px-4">Opened</th>
                  <th className="py-2.5 px-4">Notices</th>
                  <th className="py-2.5 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60">
                {filteredCases.map((c, index) => {
                  const isSelected = index === selectedIndex;
                  const riskScore = c.mrs !== undefined && c.mrs !== null ? Math.round(c.mrs) : Math.round((c.overall_confidence ?? 0.86) * 100);
                  const isNeedsAttention = c.status === "PENDING_REVIEW";

                  return (
                    <tr
                      key={c.case_id}
                      onClick={() => router.push(`/cases/${c.case_id}`)}
                      className={`cursor-pointer transition group ${
                        isSelected ? "bg-bg-sunken" : "hover:bg-bg-sunken/40"
                      } ${isNeedsAttention ? "font-semibold text-ink" : "text-ink"}`}
                    >
                      {/* Ticker */}
                      <td className="py-3 px-4 font-mono font-bold text-ink flex items-center space-x-2">
                        <span>{c.symbol}</span>
                        <span className="text-[10px] font-sans font-normal text-ink-muted px-1.5 py-0.2 rounded-cell bg-bg-sunken border border-line">
                          {c.exchange || "NSE SME"}
                        </span>
                      </td>

                      {/* Status */}
                      <td className="py-3 px-4">
                        <Chip
                          label={copy.stage[c.status as keyof typeof copy.stage] || c.status}
                          variant="neutral"
                        />
                      </td>

                      {/* Risk */}
                      <td className="py-3 px-4 text-right font-mono">
                        <span
                          className={`px-1.5 py-0.5 rounded-cell ${
                            riskScore >= 70
                              ? "bg-seal-wash text-seal font-bold"
                              : riskScore >= 40
                              ? "bg-tag-wash text-tag-ink font-bold"
                              : "text-ink-muted"
                          }`}
                        >
                          {riskScore}
                        </span>
                      </td>

                      {/* Confidence */}
                      <td className="py-3 px-4 text-right font-mono text-ink">
                        {((c.overall_confidence ?? 0.87) * 100).toFixed(0)}%
                      </td>

                      {/* Completeness */}
                      <td className="py-3 px-4 text-right font-mono text-ink">
                        {((c.completeness ?? 1.0) * 100).toFixed(0)}%
                      </td>

                      {/* Window */}
                      <td className="py-3 px-4 text-ink-muted font-mono text-[11px]">
                        {formatTime(c.window_start, "UTC")}–{formatTime(c.window_end, "UTC")} UTC
                      </td>

                      {/* Opened */}
                      <td className="py-3 px-4 text-ink-muted">
                        {formatRelativeTime(c.created_at)}
                      </td>

                      {/* Notices */}
                      <td className="py-3 px-4">
                        {c.notice && c.notice !== "—" ? (
                          <span className="text-[11px] px-2 py-0.5 rounded-cell bg-uv-wash text-uv border border-uv/20 font-medium">
                            {c.notice}
                          </span>
                        ) : riskScore >= 80 ? (
                          <span className="text-[11px] px-2 py-0.5 rounded-cell bg-uv-wash text-uv border border-uv/20 font-medium">
                            Ring active
                          </span>
                        ) : (
                          <span className="text-ink-faint text-[11px]">—</span>
                        )}
                      </td>

                      {/* Action */}
                      <td className="py-3 px-4 text-right">
                        <span className="inline-flex items-center text-xs text-ink font-medium group-hover:translate-x-0.5 transition-transform">
                          <span>Open</span>
                          <ArrowRight className="h-3.5 w-3.5 ml-1" />
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-2 bg-bg-sunken/40 border-t border-line text-[11px] text-ink-muted flex justify-between items-center">
            <span>Use <kbd className="font-mono bg-bg-raised border border-line px-1 rounded-cell">j</kbd> / <kbd className="font-mono bg-bg-raised border border-line px-1 rounded-cell">k</kbd> to navigate, <kbd className="font-mono bg-bg-raised border border-line px-1 rounded-cell">Enter</kbd> to open.</span>
            <span>Showing {filteredCases.length} of {cases.length} records</span>
          </div>
        </div>
      )}
    </div>
  );
}
