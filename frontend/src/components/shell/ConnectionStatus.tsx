"use client";

import React from "react";
import { useStream } from "@/state/useStream";

export function ConnectionStatus() {
  const { connectionStatus, backendHealth } = useStream();

  if (backendHealth?.status === "offline" || connectionStatus === "offline") {
    return (
      <div className="flex items-center space-x-2 text-xs text-rose-500 font-medium px-2 py-0.5 rounded bg-rose-500/10 border border-rose-500/20">
        <span className="h-2 w-2 rounded-full border border-rose-500 bg-rose-500 animate-pulse" />
        <span>Backend Offline</span>
      </div>
    );
  }

  if (backendHealth?.status === "degraded") {
    return (
      <div className="flex items-center space-x-2 text-xs text-amber-500 font-medium px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">
        <span className="h-2 w-2 rounded-full border border-amber-500 bg-amber-500 animate-pulse" />
        <span>Backend Degraded</span>
      </div>
    );
  }

  if (connectionStatus === "polling") {
    return (
      <div className="flex items-center space-x-2 text-xs text-blue-500 font-medium px-2 py-0.5 rounded bg-blue-500/10">
        <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
        <span>Live (Polling)</span>
      </div>
    );
  }

  return (
    <div className="flex items-center space-x-2 text-xs text-emerald-500 font-medium px-2 py-0.5 rounded bg-emerald-500/10">
      <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
      <span className="font-mono">Live (WebSocket)</span>
    </div>
  );
}
export default ConnectionStatus;
