"use client";

import React from "react";
import { FolderOpen } from "lucide-react";

interface EmptyStateProps {
  message: string;
  actionText?: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export function EmptyState({ message, actionText, actionLabel, onAction, className = "" }: EmptyStateProps) {
  const label = actionLabel || actionText;
  return (
    <div className={`p-12 text-center rounded-panel border border-line bg-bg-raised space-y-3 ${className}`}>
      <div className="h-10 w-10 rounded-cell bg-bg-sunken border border-line flex items-center justify-center mx-auto text-ink-muted">
        <FolderOpen className="h-5 w-5" />
      </div>
      <p className="text-xs text-ink-muted max-w-sm mx-auto leading-relaxed">{message}</p>
      {label && (
        <button
          onClick={onAction}
          className="px-3.5 py-1.5 rounded-panel bg-ink text-bg-raised font-medium text-xs hover:opacity-90 transition"
        >
          {label}
        </button>
      )}
    </div>
  );
}
export default EmptyState;
