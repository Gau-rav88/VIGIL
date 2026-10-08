"use client";

import React from "react";

interface ConnectionStatusProps {
  lagMs?: number;
  status?: "live" | "degraded" | "offline";
}

export function ConnectionStatus({ lagMs = 120, status = "live" }: ConnectionStatusProps) {
  if (status === "offline") {
    return (
      <div className="flex items-center space-x-2 text-xs text-seal font-medium">
        <span className="h-2 w-2 rounded-full border border-seal bg-transparent animate-pulse" />
        <span>Reconnecting... Live data paused</span>
      </div>
    );
  }

  if (status === "degraded") {
    return (
      <div className="flex items-center space-x-2 text-xs text-tag font-medium">
        <span className="h-2 w-2 rounded-full border border-tag bg-transparent" />
        <span>Behind by {(lagMs / 1000).toFixed(1)} s</span>
      </div>
    );
  }

  return (
    <div className="flex items-center space-x-2 text-xs text-ink-muted">
      <span className="h-2 w-2 rounded-full bg-verified animate-pulse" />
      <span className="font-mono text-ink">Live, {lagMs} ms behind</span>
    </div>
  );
}
export default ConnectionStatus;
