"use client";

import React from "react";

interface EvidenceTagProps {
  n: number;
  evidenceId?: string;
  onClick?: () => void;
  className?: string;
}

export function EvidenceTag({ n, evidenceId, onClick, className = "" }: EvidenceTagProps) {
  return (
    <button
      onClick={onClick}
      title={evidenceId ? `Evidence #${n}: ${evidenceId}` : `Evidence item #${n}`}
      className={`inline-flex items-center justify-center px-1.5 py-0.5 rounded-cell font-mono font-bold text-[10px] bg-tag text-tag-ink border border-tag-ink/20 hover:scale-105 active:scale-95 transition shadow-sm ${className}`}
    >
      [{n}]
    </button>
  );
}
export default EvidenceTag;
