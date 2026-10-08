"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useParams } from "next/navigation";
import { fetchCaseTimeline } from "@/lib/api";
import { EvidenceTag } from "@/components/ui/EvidenceTag";
import { formatTime } from "@/lib/time";
import { Clock, Search, Filter, MessageSquare, TrendingUp, AlertTriangle } from "lucide-react";

export default function CaseTimelinePage() {
  const params = useParams();
  const caseId = params.caseId as string;

  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [laneFilter, setLaneFilter] = useState<"ALL" | "SOCIAL" | "MARKET">("ALL");

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchCaseTimeline(caseId);
        setItems(data.items || []);
      } catch (err) {
        console.error("Failed to load timeline", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [caseId]);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (laneFilter !== "ALL" && item.lane !== laneFilter) return false;
      if (searchQuery && !item.sentence.toLowerCase().includes(searchQuery.toLowerCase())) return false;
      return true;
    });
  }, [items, laneFilter, searchQuery]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-line pb-3">
        <div>
          <h1 className="font-serif text-lg font-bold text-ink flex items-center gap-2">
            <Clock className="h-5 w-5 text-ink" />
            <span>Chronological Case Narrative</span>
          </h1>
          <p className="text-xs text-ink-muted">
            Two-lane chronological sequence correlating social coordination triggers with capital market order-flow.
          </p>
        </div>

        {/* Filters */}
        <div className="flex items-center space-x-3 text-xs">
          <div className="relative">
            <Search className="h-3.5 w-3.5 text-ink-muted absolute left-2.5 top-2 pointer-events-none" />
            <input
              type="text"
              placeholder="Filter narrative…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-2.5 py-1 bg-bg-sunken border border-line rounded-cell text-ink text-xs focus:outline-none focus:border-focus"
            />
          </div>

          <div className="flex items-center space-x-1 bg-bg-sunken border border-line rounded-cell p-0.5">
            {(["ALL", "SOCIAL", "MARKET"] as const).map((l) => (
              <button
                key={l}
                onClick={() => setLaneFilter(l)}
                className={`px-2 py-0.5 rounded-cell font-medium transition ${
                  laneFilter === l
                    ? "bg-ink text-bg-raised"
                    : "text-ink-muted hover:text-ink"
                }`}
              >
                {l}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Two-lane Timeline Container */}
      <div className="bg-bg-raised border border-line rounded-panel p-6 shadow-sm">
        <div className="relative">
          {/* Center Vertical Spine */}
          <div className="absolute left-1/2 -ml-px top-0 bottom-0 w-0.5 bg-line" />

          {/* Timeline Items */}
          <div className="space-y-8">
            {filteredItems.map((item, index) => {
              const isSocial = item.lane === "SOCIAL";

              return (
                <div key={item.id || index} className="relative flex items-center">
                  {/* Left Lane: Social */}
                  <div className={`w-1/2 pr-8 text-right ${isSocial ? "opacity-100" : "opacity-0 pointer-events-none"}`}>
                    {isSocial && (
                      <div className="inline-block text-left p-3 rounded-panel bg-bg-sunken border border-line space-y-1 shadow-sm max-w-md">
                        <div className="flex items-center justify-between text-[11px] text-social font-semibold">
                          <span className="flex items-center gap-1">
                            <MessageSquare className="h-3 w-3" />
                            <span>Social Trigger</span>
                          </span>
                          <span className="font-mono text-ink-muted">{formatTime(item.ts, "UTC")} UTC</span>
                        </div>
                        <p className="text-xs text-ink leading-relaxed">{item.sentence}</p>
                        {item.evidenceTags && (
                          <div className="pt-1 flex items-center space-x-1">
                            {item.evidenceTags.map((t: number) => (
                              <EvidenceTag key={t} n={t} />
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Center Node on Spine */}
                  <div className="absolute left-1/2 -ml-2 w-4 h-4 rounded-full bg-bg-raised border-2 border-ink flex items-center justify-center z-10">
                    <span className={`w-1.5 h-1.5 rounded-full ${isSocial ? "bg-social" : "bg-market"}`} />
                  </div>

                  {/* Right Lane: Market */}
                  <div className={`w-1/2 pl-8 text-left ${!isSocial ? "opacity-100" : "opacity-0 pointer-events-none"}`}>
                    {!isSocial && (
                      <div className="inline-block p-3 rounded-panel bg-bg-sunken border border-line space-y-1 shadow-sm max-w-md">
                        <div className="flex items-center justify-between text-[11px] text-ink font-semibold">
                          <span className="flex items-center gap-1">
                            <TrendingUp className="h-3 w-3 text-market" />
                            <span>Market Impact</span>
                          </span>
                          <span className="font-mono text-ink-muted">{formatTime(item.ts, "UTC")} UTC</span>
                        </div>
                        <p className="text-xs text-ink leading-relaxed">{item.sentence}</p>
                        {item.evidenceTags && (
                          <div className="pt-1 flex items-center space-x-1">
                            {item.evidenceTags.map((t: number) => (
                              <EvidenceTag key={t} n={t} />
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
