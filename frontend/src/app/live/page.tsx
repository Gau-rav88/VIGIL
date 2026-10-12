"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { fetchTickers, fetchAlerts, fetchCases, fetchCaseSeries, fetchSymbolSeries, TickerData, AlertData, CaseData } from "@/lib/api";
import { copy } from "@/lib/copy";
import { Tape } from "@/components/Tape/Tape";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { CaseSeries, normalizeCaseSeries } from "@/lib/types";
import {
  Activity,
  ShieldAlert,
  ArrowRight,
  TrendingUp,
  MessageSquare,
  AlertTriangle,
  Radio,
  Lock,
} from "lucide-react";
import { getRole, getRoleCapabilities, Role } from "@/lib/auth";

export default function LiveWatchFloorPage() {
  const router = useRouter();
  const [tickers, setTickers] = useState<TickerData[]>([]);
  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const [cases, setCases] = useState<CaseData[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [miniSeries, setMiniSeries] = useState<CaseSeries | null>(null);
  const [loading, setLoading] = useState(true);
  const [newAlertIds, setNewAlertIds] = useState<Set<string>>(new Set());
  const [role, setRoleState] = useState<Role>(getRole());

  useEffect(() => {
    setRoleState(getRole());
    const handler = () => setRoleState(getRole());
    window.addEventListener("vigil-role-changed", handler);
    return () => window.removeEventListener("vigil-role-changed", handler);
  }, []);

  const caps = getRoleCapabilities(role);

  const loadData = async () => {
    try {
      const [tList, aList, cList] = await Promise.all([
        fetchTickers(),
        fetchAlerts(),
        fetchCases(),
      ]);
      setTickers(tList);
      setCases(cList);
      if (tList.length > 0) {
        setSelectedSymbol((prev) => prev || tList[0].symbol);
      }

      // Detect new alerts to trigger 600ms tag-wash flash
      if (alerts.length > 0) {
        const existingIds = new Set(alerts.map((a) => a.id));
        const freshlyArrived = aList.filter((a) => !existingIds.has(a.id)).map((a) => a.id);
        if (freshlyArrived.length > 0) {
          setNewAlertIds(new Set(freshlyArrived));
          setTimeout(() => setNewAlertIds(new Set()), 600);
        }
      }
      setAlerts(aList);
    } catch (err) {
      console.error("Live feed fetch error", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 4000);
    return () => clearInterval(interval);
  }, []);

  // Fetch mini-tape series for selected symbol (matching case or symbol series)
  useEffect(() => {
    async function loadMiniTape() {
      if (!selectedSymbol) return;
      const matchingCase = cases.find((c) => c.symbol === selectedSymbol);
      if (matchingCase) {
        try {
          const s = await fetchCaseSeries(matchingCase.case_id);
          if (s && s.bars && s.bars.length > 0) {
            setMiniSeries(normalizeCaseSeries(s, selectedSymbol));
            return;
          }
        } catch {
          // fallback to symbol series
        }
      }
      try {
        const s = await fetchSymbolSeries(selectedSymbol);
        setMiniSeries(normalizeCaseSeries(s, selectedSymbol));
      } catch {
        // fallback
      }
    }
    loadMiniTape();
  }, [selectedSymbol, cases]);

  // Sort tickers by risk (MRS) descending
  const sortedTickers = useMemo(() => {
    return [...tickers].sort((a, b) => b.mrs - a.mrs);
  }, [tickers]);

  const selectedCase = cases.find((c) => c.symbol === selectedSymbol);
  const selectedTickerData = tickers.find((t) => t.symbol === selectedSymbol);

  if (loading && tickers.length === 0) {
    return (
      <div className="py-20 flex flex-col items-center justify-center space-y-3 text-ink-muted">
        <Activity className="h-6 w-6 animate-pulse text-verified" />
        <span className="text-xs">Connecting to market surveillance floor…</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-line pb-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="font-serif text-xl font-bold text-ink flex items-center gap-2">
              <Activity className="h-5 w-5 text-ink" />
              <span>Watch Floor</span>
            </h1>
            <span className="flex items-center space-x-1.5 px-2 py-0.5 rounded-chip text-[11px] bg-verified-wash text-verified font-medium border border-verified/30">
              <span className="w-1.5 h-1.5 rounded-full bg-verified animate-ping" />
              <span>Surveillance active</span>
            </span>
            <span
              className={`px-2.5 py-0.5 rounded-chip text-[10px] font-mono font-bold uppercase border ${caps.badgeColor} flex items-center gap-1`}
              title={caps.description}
            >
              {caps.isReadOnly && <Lock className="h-3 w-3" />}
              <span>{caps.badgeLabel}</span>
            </span>
          </div>
          <p className="text-xs text-ink-muted mt-0.5">
            Ranked risk watch ladder, synchronized dual-track mini tape, and prioritized anomaly stream.
          </p>
        </div>

        <div className="flex items-center space-x-3 text-xs text-ink-muted font-mono">
          <span>{tickers.length} EQUITIES</span>
          <span>•</span>
          <span>REDPANDA 16P</span>
        </div>
      </div>

      {/* Main 3-Column Surveillance Layout (§6.1) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Watch ladder (ranked by risk) - 5 cols */}
        <div className="lg:col-span-5 bg-bg-raised border border-line rounded-panel p-4 space-y-3 shadow-sm">
          <div className="flex items-center justify-between border-b border-line pb-2">
            <div className="flex items-center space-x-2">
              <h2 className="font-semibold text-xs text-ink uppercase tracking-wide">
                Watch ladder
              </h2>
              <span className="text-[11px] text-ink-muted">(Ranked by Risk)</span>
            </div>
            <span className="text-[10px] text-ink-muted font-mono">MRS 0-100</span>
          </div>

          {sortedTickers.length === 0 ? (
            <EmptyState message={copy.empty.live} />
          ) : (
            <div className="space-y-1 overflow-y-auto max-h-[680px] pr-1">
              {sortedTickers.map((t) => {
                const isSelected = t.symbol === selectedSymbol;
                const riskVal = Math.round(t.mrs * 100);
                const hasCase = cases.some((c) => c.symbol === t.symbol);
                const matchingCase = cases.find((c) => c.symbol === t.symbol);

                return (
                  <div
                    key={t.symbol}
                    onClick={() => setSelectedSymbol(t.symbol)}
                    className={`p-2.5 rounded-cell border cursor-pointer transition text-xs ${
                      isSelected
                        ? "bg-bg-sunken border-ink font-semibold"
                        : "bg-bg-raised border-line/60 hover:bg-bg-sunken/40"
                    }`}
                    role="button"
                    aria-label={`Ticker ${t.symbol}, Risk ${riskVal}`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono font-bold text-ink">{t.symbol}</span>
                        <span className="text-[10px] text-ink-muted font-sans px-1.5 py-0.2 rounded-cell bg-bg-sunken border border-line">
                          {t.tier === "MICRO_SME" ? "SME" : "MAIN"}
                        </span>
                      </div>

                      <div className="flex items-center space-x-3 font-mono text-[11px]">
                        <span className="text-ink-muted">
                          Hype: {Math.round(t.hype ?? (riskVal * 0.8))}
                        </span>
                        <span className="text-ink-muted">
                          Vol z: {(t.volume_z ?? (t.mrs * 3)).toFixed(1)}σ
                        </span>
                        <strong
                          className={`px-1.5 py-0.5 rounded-cell font-mono text-xs ${
                            riskVal >= 70
                              ? "bg-seal-wash text-seal font-bold"
                              : riskVal >= 40
                              ? "bg-tag-wash text-tag-ink font-bold"
                              : "text-ink"
                          }`}
                        >
                          {riskVal}
                        </strong>
                      </div>
                    </div>

                    {/* Proportional Risk Bar (Length = MRS) */}
                    <div className="mt-2 w-full h-1.5 bg-bg-sunken rounded-cell overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 ${
                          riskVal >= 70
                            ? "bg-seal"
                            : riskVal >= 40
                            ? "bg-tag"
                            : "bg-market"
                        }`}
                        style={{ width: `${Math.min(100, Math.max(5, riskVal))}%` }}
                      />
                    </div>

                    {/* Second line: Case open notification */}
                    {hasCase && matchingCase && (
                      <div className="mt-2 pt-1 border-t border-line/40 flex items-center justify-between text-[11px]">
                        <a
                          href={`/cases/${matchingCase.case_id}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            router.push(`/cases/${matchingCase.case_id}`);
                          }}
                          className="text-uv hover:underline font-medium flex items-center gap-1"
                        >
                          <span>Case open ▸ {copy.stage[matchingCase.status as keyof typeof copy.stage] || matchingCase.status}</span>
                        </a>
                        <span className="text-[10px] text-ink-muted">Inspect ↗</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Center Column: Mini Tape for selected ticker - 4 cols */}
        <div className="lg:col-span-4 bg-bg-raised border border-line rounded-panel p-4 space-y-4 shadow-sm flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-line pb-2">
              <div className="flex items-center space-x-2">
                <h2 className="font-semibold text-xs text-ink uppercase tracking-wide">
                  {selectedSymbol}
                </h2>
                <span className="text-[11px] text-ink-muted font-mono">Last 60m</span>
              </div>
              {selectedCase && (
                <span className="text-[10px] px-2 py-0.5 rounded-chip bg-uv-wash text-uv font-medium border border-uv/20">
                  Case Active
                </span>
              )}
            </div>

            {/* Key stats row */}
            <div className="grid grid-cols-3 gap-2 text-xs font-mono">
              <div className="bg-bg-sunken p-2 rounded-cell border border-line">
                <span className="text-[10px] text-ink-muted font-sans block">Hype</span>
                <span className="font-bold text-social">
                  {Math.round(selectedTickerData?.hype ?? ((selectedTickerData?.mrs ?? 0) * 80))} / 100
                </span>
              </div>
              <div className="bg-bg-sunken p-2 rounded-cell border border-line">
                <span className="text-[10px] text-ink-muted font-sans block">Volume z</span>
                <span className="font-bold text-ink">
                  {selectedTickerData?.volume_z != null
                    ? `${selectedTickerData.volume_z}σ`
                    : `${((selectedTickerData?.mrs ?? 0) * 3).toFixed(1)}σ`}
                </span>
              </div>
              <div className="bg-bg-sunken p-2 rounded-cell border border-line">
                <span className="text-[10px] text-ink-muted font-sans block">Price / Chg</span>
                <span className={`font-bold ${(selectedTickerData?.change_pct ?? 0) >= 0 ? "text-verified" : "text-seal"}`}>
                  ₹{(selectedTickerData?.price ?? 0).toFixed(2)} ({(selectedTickerData?.change_pct ?? 0) >= 0 ? "+" : ""}{(selectedTickerData?.change_pct ?? 0)}%)
                </span>
              </div>
            </div>

            {/* Mini Tape display */}
            {miniSeries ? (
              <div className="space-y-2">
                <Tape series={miniSeries} compact={true} />
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-ink-muted border border-dashed border-line rounded-cell">
                Loading mini tape for {selectedSymbol}…
              </div>
            )}
          </div>

          {/* Action button */}
          {selectedCase && (
            <div className="pt-3 border-t border-line">
              <Button
                variant="primary"
                size="sm"
                className="w-full"
                onClick={() => router.push(`/cases/${selectedCase.case_id}`)}
              >
                <span>Open case workbench</span>
                <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
              </Button>
            </div>
          )}
        </div>

        {/* Right Column: Alert Feed - 3 cols */}
        <div className="lg:col-span-3 bg-bg-raised border border-line rounded-panel p-4 space-y-3 shadow-sm">
          <div className="flex items-center justify-between border-b border-line pb-2">
            <h2 className="font-semibold text-xs text-ink uppercase tracking-wide flex items-center gap-1.5">
              <Radio className="h-3.5 w-3.5 text-verified" />
              <span>Alert feed</span>
            </h2>
            <span className="text-[10px] text-ink-muted font-mono">{alerts.length} Newest</span>
          </div>

          <div
            className="space-y-2 overflow-y-auto max-h-[680px] pr-1"
            role="region"
            aria-live="polite"
          >
            {alerts.map((alert) => {
              const isFlashing = newAlertIds.has(alert.id);
              const matchingCase = cases.find((c) => c.symbol === alert.symbol);

              return (
                <div
                  key={alert.id}
                  onClick={() => {
                    if (matchingCase) {
                      router.push(`/cases/${matchingCase.case_id}`);
                    }
                  }}
                  className={`p-2.5 rounded-cell border text-xs cursor-pointer transition ${
                    isFlashing
                      ? "bg-tag-wash border-tag"
                      : "bg-bg-sunken/40 border-line hover:border-line-strong hover:bg-bg-sunken"
                  }`}
                >
                  <div className="flex items-center justify-between text-[11px] mb-1">
                    <span className="font-mono font-bold text-ink">{alert.symbol}</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.2 rounded-cell font-bold ${
                        alert.severity === "CRITICAL"
                          ? "bg-seal-wash text-seal"
                          : "bg-tag-wash text-tag-ink"
                      }`}
                    >
                      {alert.severity}
                    </span>
                  </div>
                  <p className="text-[11px] text-ink leading-snug font-medium mb-1.5">
                    {alert.summary}
                  </p>
                  <div className="flex justify-between items-center text-[10px] text-ink-muted">
                    <span className="font-mono">{alert.type}</span>
                    <span>{matchingCase ? "Case open ↗" : "Monitor"}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
