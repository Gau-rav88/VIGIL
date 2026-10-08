"use client";

import React from "react";

interface ChipProps {
  label: string;
  variant?: "tag" | "uv" | "verified" | "seal" | "default" | "neutral";
  className?: string;
}

export function Chip({ label, variant = "default", className = "" }: ChipProps) {
  const variantStyles = {
    tag: "bg-tag-wash text-tag-ink border-tag/40",
    uv: "bg-uv-wash text-uv border-uv/30 font-semibold",
    verified: "bg-verified-wash text-verified border-verified/30 font-semibold",
    seal: "bg-seal-wash text-seal border-seal/30 font-semibold",
    default: "bg-bg-sunken text-ink border-line",
    neutral: "bg-bg-sunken text-ink border-line",
  }[variant];

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-chip text-[11px] border font-mono ${variantStyles} ${className}`}
    >
      {label}
    </span>
  );
}
export default Chip;
