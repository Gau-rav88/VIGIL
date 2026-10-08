"use client";

import React from "react";
import { CheckCircle2, XCircle } from "lucide-react";

interface VerifyBadgeProps {
  name: string;
  ok: boolean;
  checked?: number;
  entries?: number;
  keyId?: string;
}

export function VerifyBadge({ name, ok, checked, entries, keyId }: VerifyBadgeProps) {
  let label = "Valid";
  let description = "Integrity check passed";

  if (name === "SCHEMA_VALID") {
    label = "JSON Schema";
    description = "Conforms to canonical Project VIGIL specification";
  } else if (name === "EVIDENCE_HASHES") {
    label = "Evidence SHA-256";
    description = `Verified ${checked ?? 2} manifest artifact hash digests`;
  } else if (name === "MERKLE_ROOT") {
    label = "RFC 6962 Merkle Root";
    description = "Binary tree recomputation matches signed root";
  } else if (name === "LEDGER_CHAIN") {
    label = "Hash-Chain Ledger";
    description = `Verified unbroken ledger chain across ${entries ?? 1} entries`;
  } else if (name === "SIGNATURE") {
    label = "Ed25519 Signature";
    description = `Digital signature verified with key ${keyId || "dev-2026-01"}`;
  } else if (name === "HUMAN_REVIEW_PRESENT") {
    label = "Compliance Audit";
    description = "Authorized human reviewer sign-off present";
  }

  return (
    <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 flex items-start justify-between space-x-3">
      <div className="space-y-1">
        <div className="flex items-center space-x-2">
          <span className="font-mono text-xs font-bold text-white">{name}</span>
          <span className="text-[10px] text-slate-400">({label})</span>
        </div>
        <p className="text-[11px] text-slate-400">{description}</p>
      </div>

      {ok ? (
        <span className="p-1 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 shrink-0">
          <CheckCircle2 className="h-4 w-4" />
        </span>
      ) : (
        <span className="p-1 rounded-md bg-rose-500/10 text-rose-400 border border-rose-500/30 shrink-0">
          <XCircle className="h-4 w-4" />
        </span>
      )}
    </div>
  );
}
export default VerifyBadge;
