"use client";

import React, { useState } from "react";
import { truncateHash } from "@/lib/format";
import { Copy, Check } from "lucide-react";

interface CopyHashProps {
  hash: string;
  lead?: number;
  trail?: number;
  className?: string;
}

export function CopyHash({ hash, lead = 8, trail = 8, className = "" }: CopyHashProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(hash);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      //
    }
  };

  return (
    <button
      onClick={handleCopy}
      title="Click to copy full hash"
      className={`inline-flex items-center space-x-1 font-mono text-xs text-ink hover:text-uv bg-bg-sunken px-2 py-0.5 rounded-cell border border-line transition ${className}`}
    >
      <span>{truncateHash(hash, lead, trail)}</span>
      {copied ? <Check className="h-3 w-3 text-verified" /> : <Copy className="h-3 w-3 text-ink-muted" />}
    </button>
  );
}
export default CopyHash;
