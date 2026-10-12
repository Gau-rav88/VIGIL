"use client";

import React, { useEffect, useState } from "react";
import { useParams, usePathname, useRouter } from "next/navigation";
import { CaseBar } from "@/components/shell/CaseBar";
import { fetchCase, fetchCaseFlags, fetchCaseDossiers, CaseData } from "@/lib/api";
import { formatTime } from "@/lib/time";
import { BarChart2, GitFork, Clock } from "lucide-react";

export default function CaseLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const pathname = usePathname();
  const router = useRouter();
  const caseId = params.caseId as string;

  const [caseData, setCaseData] = useState<CaseData | null>(null);
  const [flags, setFlags] = useState<Array<{ flag: string; explanation: string }>>([]);
  const [latestDossierId, setLatestDossierId] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;

    async function load() {
      try {
        const c = await fetchCase(caseId);
        setCaseData(c);
      } catch (err) {
        console.error("Failed to load case", err);
      }

      try {
        const f = await fetchCaseFlags(caseId);
        setFlags(f.flags || []);
      } catch (err) {
        console.error("Failed to load flags", err);
      }

      try {
        const d = await fetchCaseDossiers(caseId);
        if (d && d.length > 0) {
          setLatestDossierId(d[0].dossier_id);
        }
      } catch (err) {
        console.error("Failed to load dossiers", err);
      }
    }

    load();
  }, [caseId]);

  const windowStr = caseData
    ? `Window ${formatTime(caseData.window_start, "UTC")} to ${formatTime(
        caseData.window_end,
        "UTC"
      )} UTC (IST ${formatTime(caseData.window_start, "IST")} to ${formatTime(
        caseData.window_end,
        "IST"
      )})`
    : "Window 04:20 to 04:37 UTC (IST 09:50 to 10:07)";

  const isGraph = pathname.endsWith("/graph");
  const isTimeline = pathname.endsWith("/timeline");
  const isOverview = !isGraph && !isTimeline;

  return (
    <div className="flex flex-col flex-1 -m-6 min-h-screen bg-bg-base">
      {/* Pinned CaseBar */}
      <CaseBar
        caseId={caseId}
        symbol={caseData?.symbol || "—"}
        exchange={caseData?.exchange || "—"}
        status={caseData?.status || "—"}
        confidence={caseData?.overall_confidence ?? 0}
        completeness={caseData?.completeness ?? 0}
        dossierVersion={1}
        isVerified={false}
        windowStr={windowStr}
        flags={flags}
        onOpenDossier={() => {
          router.push(`/dossiers/${latestDossierId || caseId}`);
        }}
      />

      {/* Case Sub-Navigation Navigation Bar */}
      <div className="bg-bg-raised border-b border-line px-6 py-2 flex items-center justify-between text-xs">
        <div className="flex items-center space-x-1">
          <button
            onClick={() => router.push(`/cases/${caseId}`)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-cell font-medium transition ${
              isOverview
                ? "bg-bg-sunken text-ink font-bold border border-line"
                : "text-ink-muted hover:text-ink hover:bg-bg-sunken/60"
            }`}
          >
            <BarChart2 className="h-3.5 w-3.5" />
            <span>Forensic Tape & Overview</span>
          </button>

          <button
            onClick={() => router.push(`/cases/${caseId}/graph`)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-cell font-medium transition ${
              isGraph
                ? "bg-bg-sunken text-ink font-bold border border-line"
                : "text-ink-muted hover:text-ink hover:bg-bg-sunken/60"
            }`}
          >
            <GitFork className="h-3.5 w-3.5" />
            <span>Syndicate Graph Explorer</span>
          </button>

          <button
            onClick={() => router.push(`/cases/${caseId}/timeline`)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-cell font-medium transition ${
              isTimeline
                ? "bg-bg-sunken text-ink font-bold border border-line"
                : "text-ink-muted hover:text-ink hover:bg-bg-sunken/60"
            }`}
          >
            <Clock className="h-3.5 w-3.5" />
            <span>Chronology Timeline</span>
          </button>
        </div>

        <div className="text-ink-muted text-[11px] font-mono">
          Case ID: {caseId}
        </div>
      </div>

      {/* Page Content */}
      <div className="flex-1 p-6 max-w-7xl w-full mx-auto">{children}</div>
    </div>
  );
}
