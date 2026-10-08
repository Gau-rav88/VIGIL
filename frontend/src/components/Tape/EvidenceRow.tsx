"use client";

import React from "react";
import type { ScaleTime } from "d3-scale";
import { EvidenceTag } from "@/components/ui/EvidenceTag";
import { useTapeStore } from "@/state/useTapeStore";

interface EvidenceRowProps {
  x: ScaleTime<number, number>;
  width: number;
  items: Array<{
    n: number;
    t: number;
    evidenceId: string;
    type: string;
    sha256: string;
  }>;
}

export function EvidenceRow({ x, width, items }: EvidenceRowProps) {
  const { setFocusedEvidenceId } = useTapeStore();

  return (
    <div className="h-7 border-t border-line/60 relative overflow-hidden bg-bg-sunken/40">
      {items.map((item) => {
        const posX = x(new Date(item.t));
        return (
          <div
            key={item.evidenceId}
            className="absolute top-1 -translate-x-1/2 z-20"
            style={{ left: `${posX}px` }}
          >
            <EvidenceTag
              n={item.n}
              evidenceId={item.evidenceId}
              onClick={() => setFocusedEvidenceId(item.evidenceId)}
            />
          </div>
        );
      })}
    </div>
  );
}
export default EvidenceRow;
