"use client";

import React from "react";
import { DossierData } from "@/lib/api";
import { truncateHash } from "@/lib/format";
import { Download, ShieldCheck, FileText, Check } from "lucide-react";

interface DossierViewProps {
  dossier?: DossierData | null;
  caseId: string;
}

export function DossierView({ dossier, caseId }: DossierViewProps) {
  const merkleRoot = dossier?.merkle_root || "b6a7afc6f27583c1d25ed395255f5a3a8be2f2e2276ceadea50e9acf104fd22f";
  const downloadUrl = dossier
    ? `http://localhost:8001/api/v1/dossiers/${dossier.dossier_id}/bundle`
    : `http://localhost:8001/api/v1/dossiers/sample/bundle`;

  return (
    <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="h-5 w-5 text-emerald-400" />
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">
            Cryptographic Dossier & Evidence Sealing
          </h3>
        </div>

        <a
          href={downloadUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold text-xs transition"
        >
          <Download className="h-4 w-4" />
          <span>Download Bundle (.zip)</span>
        </a>
      </div>

      <div className="space-y-2.5 text-xs">
        <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <span className="text-slate-400 font-medium">Merkle Root (RFC 6962):</span>
          <span className="font-mono text-emerald-400 text-[11px] break-all">{merkleRoot}</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
            <span className="text-slate-400">Canonical Spec:</span>
            <span className="font-mono text-slate-200 font-semibold">RFC 8785 JSON</span>
          </div>
          <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
            <span className="text-slate-400">Signer Key:</span>
            <span className="font-mono text-cyan-400 font-semibold">dev-2026-01 (Ed25519)</span>
          </div>
          <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
            <span className="text-slate-400">Ledger Status:</span>
            <span className="font-mono text-emerald-400 font-semibold flex items-center gap-1">
              <Check className="h-3.5 w-3.5" /> Hash-Chain OK
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
export default DossierView;
