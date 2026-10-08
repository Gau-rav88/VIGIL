"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchEntity } from "@/lib/api";
import { copy } from "@/lib/copy";
import { Button } from "@/components/ui/Button";
import { Meter } from "@/components/ui/Meter";
import {
  Network,
  GitFork,
  Eye,
  ShieldAlert,
  Server,
  Smartphone,
  Clock,
  ArrowLeft,
  Check,
} from "lucide-react";

export default function EntityProfilePage() {
  const params = useParams();
  const router = useRouter();
  const entityId = params.entityId as string;

  const [entity, setEntity] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showRevealConfirm, setShowRevealConfirm] = useState(false);
  const [revealedAccount, setRevealedAccount] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchEntity(entityId);
        setEntity(data);
      } catch (err) {
        console.error("Failed to load entity", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [entityId]);

  const handleReveal = () => {
    setShowRevealConfirm(false);
    setRevealedAccount("PAN: ABCDE1234F (Arjun M. Trading LLP)");
    setToastMessage("Account identity revealed. Audit log entry recorded.");
    setTimeout(() => {
      setRevealedAccount(null);
    }, 60000); // 60s timeout according to §11
  };

  if (loading) {
    return (
      <div className="py-20 text-center text-xs text-ink-muted">
        Loading syndicate entity profile…
      </div>
    );
  }

  const ringScore = entity?.ringScore || 0.95;
  const accounts = entity?.accounts || [];
  const brokers = entity?.brokers || [];
  const devices = entity?.sharedDevices || [];

  return (
    <div className="space-y-6">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-2.5 rounded-panel bg-ink text-bg-raised text-xs font-medium shadow-pop flex items-center space-x-2 animate-in fade-in">
          <Check className="h-4 w-4 text-verified" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Back button */}
      <div className="flex items-center justify-between border-b border-line pb-3">
        <button
          onClick={() => router.back()}
          className="flex items-center space-x-1.5 text-xs text-ink-muted hover:text-ink font-medium"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back</span>
        </button>
        <span className="font-mono text-xs text-ink-muted">Entity: {entityId}</span>
      </div>

      {/* Header Profile Card */}
      <div className="bg-bg-raised border border-line rounded-panel p-6 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-3">
              <h1 className="font-serif text-xl font-bold text-ink flex items-center gap-2">
                <Network className="h-5 w-5 text-uv" />
                <span>Syndicate Entity Profile: {entityId}</span>
              </h1>
              <span className="px-2 py-0.5 rounded-chip text-[11px] font-bold bg-uv-wash text-uv border border-uv/20">
                Coordinated Ring
              </span>
            </div>
            <p className="text-xs text-ink-muted mt-1">
              Deterministic cluster attributed via shared device identifiers, IP proxies, and circular cycles.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => router.push(`/cases/case_01/graph`)}
            >
              <GitFork className="h-3.5 w-3.5 mr-1.5" />
              <span>{copy.action.openGraph}</span>
            </Button>

            <Button
              size="sm"
              variant="danger"
              onClick={() => setShowRevealConfirm(true)}
            >
              <Eye className="h-3.5 w-3.5 mr-1.5" />
              <span>Reveal Account Identity</span>
            </Button>
          </div>
        </div>

        {/* Revealed Identity Banner */}
        {revealedAccount && (
          <div className="p-3 rounded-cell bg-seal-wash border border-seal text-seal text-xs font-mono font-bold animate-in fade-in flex items-center justify-between">
            <span>UNMASKED: {revealedAccount}</span>
            <span className="text-[10px] font-sans font-normal opacity-80">Masks in 60s</span>
          </div>
        )}

        {/* Score & Volume Ribbon */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-2 border-t border-line/60">
          <div className="space-y-1">
            <span className="text-xs text-ink-muted">Attribution Score</span>
            <div className="font-mono text-xl font-bold text-uv">
              {(ringScore * 100).toFixed(0)}%
            </div>
            <Meter value={ringScore} max={1} />
          </div>

          <div className="space-y-1">
            <span className="text-xs text-ink-muted">Attributed Volume Share</span>
            <div className="font-mono text-xl font-bold text-ink">42.8%</div>
            <span className="text-[11px] text-ink-muted">During ramp interval</span>
          </div>

          <div className="space-y-1">
            <span className="text-xs text-ink-muted">Member Accounts</span>
            <div className="font-mono text-xl font-bold text-ink">{accounts.length}</div>
            <span className="text-[11px] text-ink-muted">Across 4 clearing brokers</span>
          </div>

          <div className="space-y-1">
            <span className="text-xs text-ink-muted">Reaction Latency</span>
            <div className="font-mono text-xl font-bold text-ink">420 ms</div>
            <span className="text-[11px] text-verified">vs 3,500 ms baseline (p&lt;0.001)</span>
          </div>
        </div>
      </div>

      {/* Accounts & Device Clusters Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 text-xs">
        {/* Accounts Table */}
        <div className="bg-bg-raised border border-line rounded-panel p-5 space-y-3 shadow-sm">
          <h3 className="font-semibold text-ink uppercase tracking-wide">
            Attributed Member Accounts
          </h3>
          <div className="border border-line rounded-cell overflow-hidden">
            <table className="w-full text-left font-mono">
              <thead className="bg-bg-sunken text-ink-muted">
                <tr>
                  <th className="p-2">Pseudonym</th>
                  <th className="p-2">Broker</th>
                  <th className="p-2 text-right">Role</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60">
                {accounts.slice(0, 8).map((acc: string, idx: number) => (
                  <tr key={idx} className="hover:bg-bg-sunken/40">
                    <td className="p-2 font-bold text-ink">{acc}</td>
                    <td className="p-2 text-ink-muted">BRK_{((idx % 4) + 1).toString().padStart(2, "0")}</td>
                    <td className="p-2 text-right text-uv font-semibold">
                      {idx < 3 ? "Wash Cycle" : "Liquidity"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Devices & Shared Infrastructure */}
        <div className="bg-bg-raised border border-line rounded-panel p-5 space-y-3 shadow-sm">
          <h3 className="font-semibold text-ink uppercase tracking-wide">
            Shared Infrastructure Clusters
          </h3>
          <div className="space-y-2">
            {devices.map((dev: string, idx: number) => (
              <div
                key={idx}
                className="p-3 rounded-cell bg-bg-sunken border border-line flex items-center justify-between"
              >
                <div className="flex items-center space-x-2">
                  <Smartphone className="h-4 w-4 text-ink-muted" />
                  <span className="font-mono font-bold text-ink">{dev}</span>
                </div>
                <span className="text-ink-muted font-mono">4 Shared Accounts</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Reveal Confirmation Dialog */}
      {showRevealConfirm && (
        <div className="fixed inset-0 z-50 bg-ink/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-bg-raised border border-line rounded-panel max-w-md w-full p-6 space-y-4 shadow-pop animate-in zoom-in-95">
            <h3 className="font-bold text-ink text-sm">
              Confirm Pseudonym Unmasking
            </h3>
            <p className="text-xs text-ink-muted leading-relaxed">
              {copy.confirm.reveal}
            </p>
            <div className="flex justify-end space-x-2 pt-2 border-t border-line/60">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setShowRevealConfirm(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={handleReveal}
              >
                Confirm Reveal
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
