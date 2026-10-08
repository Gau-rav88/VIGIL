"use client";

import React from "react";

interface StepperProps {
  currentStage: string;
}

const STEPS = [
  { n: 1, label: "Detect", stages: ["OPENED"] },
  { n: 2, label: "Align", stages: ["ENRICHING", "ALIGNED"] },
  { n: 3, label: "Attribute", stages: ["ATTRIBUTING"] },
  { n: 4, label: "Assess", stages: ["ASSESSING"] },
  { n: 5, label: "Draft and sign", stages: ["DRAFTING", "VALIDATING", "SIGNING"] },
  { n: 6, label: "Review", stages: ["PENDING_REVIEW", "APPROVED", "PUBLISHED", "REJECTED", "REWORK"] },
];

export function Stepper({ currentStage }: StepperProps) {
  let activeIndex = 0;
  for (let i = 0; i < STEPS.length; i++) {
    if (STEPS[i].stages.includes(currentStage)) {
      activeIndex = i;
      break;
    }
  }

  return (
    <div className="flex items-center space-x-1.5 text-xs text-ink-muted">
      {STEPS.map((step, idx) => {
        const isCurrent = idx === activeIndex;
        const isDone = idx < activeIndex;

        return (
          <React.Fragment key={step.n}>
            <div
              className={`flex items-center space-x-1 font-mono text-[11px] ${
                isCurrent
                  ? "text-ink font-bold"
                  : isDone
                  ? "text-verified font-medium"
                  : "text-ink-faint"
              }`}
            >
              <span
                className={`flex items-center justify-center h-4 w-4 rounded-full text-[9px] ${
                  isCurrent
                    ? "bg-ink text-bg-raised font-bold"
                    : isDone
                    ? "bg-verified text-bg-raised"
                    : "border border-line-strong text-ink-faint"
                }`}
              >
                {step.n}
              </span>
              <span className="font-sans hidden sm:inline">{step.label}</span>
            </div>
            {idx < STEPS.length - 1 && <span className="text-line-strong text-[10px]">─</span>}
          </React.Fragment>
        );
      })}
    </div>
  );
}
export default Stepper;
