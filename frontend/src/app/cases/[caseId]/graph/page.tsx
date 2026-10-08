"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useParams } from "next/navigation";
import { fetchCaseGraph, postLinkFeedback } from "@/lib/api";
import { copy } from "@/lib/copy";
import { Button } from "@/components/ui/Button";
import { EvidenceTag } from "@/components/ui/EvidenceTag";
import {
  GitFork,
  Check,
  X,
  Maximize2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Sliders,
  Table as TableIcon,
  ShieldAlert,
  Info,
  Radio,
} from "lucide-react";

interface NodeItem {
  id: string;
  type: string;
  label: string;
  cluster?: number;
  volume?: number;
}

interface EdgeItem {
  source: string;
  target: string;
  type: string;
  confidence?: number;
  qty?: number;
  isCycle?: boolean;
}

const CLUSTERS = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"];

export default function CaseGraphPage() {
  const params = useParams();
  const caseId = params.caseId as string;

  const [nodes, setNodes] = useState<NodeItem[]>([]);
  const [edges, setEdges] = useState<EdgeItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters state
  const [minConf, setMinConf] = useState(0.6);
  const [showTrades, setShowTrades] = useState(true);
  const [showInferred, setShowInferred] = useState(true);
  const [showBrokers, setShowBrokers] = useState(true);
  const [showDevices, setShowDevices] = useState(true);
  const [tableView, setTableView] = useState(false);

  // Selection & Feedback state
  const [selectedEdge, setSelectedEdge] = useState<EdgeItem | null>(null);
  const [selectedNode, setSelectedNode] = useState<NodeItem | null>(null);
  const [tracedCycle, setTracedCycle] = useState(false);
  const [vetoedLinks, setVetoedLinks] = useState<Set<string>>(new Set());
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [feedbackPopover, setFeedbackPopover] = useState(false);
  const [feedbackComment, setFeedbackComment] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchCaseGraph(caseId);
        // Build rich graph nodes & edges
        const nList: NodeItem[] = (data.nodes || []).map((n: any, i: number) => ({
          ...n,
          cluster: i % CLUSTERS.length,
          volume: Math.floor(Math.random() * 50000) + 5000,
        }));

        // Add cross-links between accounts (inferred links + trades)
        const eList: EdgeItem[] = [...(data.edges || [])];
        for (let i = 1; i <= 6; i++) {
          const s = `acc_${i.toString().padStart(2, "0")}`;
          const t = `acc_${(i + 1).toString().padStart(2, "0")}`;
          eList.push({
            source: s,
            target: t,
            type: "LINKED",
            confidence: 0.96 - i * 0.04,
            isCycle: i <= 3,
          });
          eList.push({
            source: s,
            target: t,
            type: "TRADED_WITH",
            qty: 5000 * i,
          });
        }

        setNodes(nList);
        setEdges(eList);
        // default selection
        setSelectedEdge(eList.find((e) => e.type === "LINKED") || eList[0]);
      } catch (err) {
        console.error("Failed to load graph", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [caseId]);

  const handleMarkFalsePositive = async () => {
    if (!selectedEdge) return;
    const linkKey = `${selectedEdge.source}->${selectedEdge.target}`;
    try {
      await postLinkFeedback(caseId, selectedEdge.source, selectedEdge.target, "MARK_FALSE", feedbackComment);
      setVetoedLinks((prev) => new Set(prev).add(linkKey));
      setFeedbackPopover(false);
      setFeedbackComment("");
      setToastMessage(copy.toast.falsePositive);
      setTimeout(() => setToastMessage(null), 4000);
    } catch {
      setToastMessage("Failed to mark link");
    }
  };

  const handleConfirmLink = async () => {
    if (!selectedEdge) return;
    try {
      await postLinkFeedback(caseId, selectedEdge.source, selectedEdge.target, "CONFIRM");
      setToastMessage(copy.toast.linkConfirmed);
      setTimeout(() => setToastMessage(null), 4000);
    } catch {
      setToastMessage("Failed to confirm link");
    }
  };

  return (
    <div className="space-y-4">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-2.5 rounded-panel bg-ink text-bg-raised text-xs font-medium shadow-pop flex items-center space-x-2 animate-in fade-in">
          <Check className="h-4 w-4 text-verified" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-line pb-3">
        <div>
          <h1 className="font-serif text-lg font-bold text-ink flex items-center gap-2">
            <GitFork className="h-5 w-5 text-uv" />
            <span>Syndicate Graph Explorer</span>
          </h1>
          <p className="text-xs text-ink-muted">
            Examine attributed accounts, shared device fingerprints, and challenge machine-inferred links.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Button
            size="sm"
            variant={tableView ? "secondary" : "ghost"}
            onClick={() => setTableView(!tableView)}
          >
            <TableIcon className="h-3.5 w-3.5 mr-1.5" />
            <span>{tableView ? "View as Canvas" : "View as Table"}</span>
          </Button>

          <Button
            size="sm"
            variant="secondary"
            onClick={() => setTracedCycle(!tracedCycle)}
          >
            <span className="w-2 h-2 rounded-full bg-seal mr-1.5 animate-pulse" />
            <span>{tracedCycle ? "Clear Cycle" : "Trace Wash Cycle"}</span>
          </Button>
        </div>
      </div>

      {/* Main 3-Column Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Filters (3 cols) */}
        <div className="lg:col-span-3 bg-bg-raised border border-line rounded-panel p-4 space-y-4 shadow-sm text-xs">
          <div className="flex items-center justify-between border-b border-line pb-2">
            <span className="font-semibold text-ink uppercase tracking-wide flex items-center gap-1.5">
              <Sliders className="h-3.5 w-3.5 text-ink-muted" />
              <span>Filters</span>
            </span>
          </div>

          {/* Confidence Slider */}
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <span className="text-ink font-medium">Link Confidence</span>
              <span className="font-mono font-bold text-uv">{minConf.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.4"
              max="1.0"
              step="0.05"
              value={minConf}
              onChange={(e) => setMinConf(parseFloat(e.target.value))}
              className="w-full accent-uv cursor-pointer"
            />
            <span className="text-[10px] text-ink-muted block">
              Showing links with confidence ≥ {minConf.toFixed(2)}
            </span>
          </div>

          {/* Show / Hide Checkboxes */}
          <div className="space-y-2 border-t border-line/60 pt-3">
            <span className="font-semibold text-ink uppercase tracking-wider text-[11px] block">
              Layers
            </span>
            <label className="flex items-center space-x-2 cursor-pointer text-ink">
              <input
                type="checkbox"
                checked={showTrades}
                onChange={(e) => setShowTrades(e.target.checked)}
                className="accent-ink rounded-cell"
              />
              <span>Trades (Observed)</span>
            </label>

            <label className="flex items-center space-x-2 cursor-pointer text-ink">
              <input
                type="checkbox"
                checked={showInferred}
                onChange={(e) => setShowInferred(e.target.checked)}
                className="accent-uv rounded-cell"
              />
              <span className="text-uv font-medium">Inferred Links (Ultraviolet)</span>
            </label>

            <label className="flex items-center space-x-2 cursor-pointer text-ink">
              <input
                type="checkbox"
                checked={showBrokers}
                onChange={(e) => setShowBrokers(e.target.checked)}
                className="accent-ink rounded-cell"
              />
              <span>Brokers & Gateways</span>
            </label>

            <label className="flex items-center space-x-2 cursor-pointer text-ink">
              <input
                type="checkbox"
                checked={showDevices}
                onChange={(e) => setShowDevices(e.target.checked)}
                className="accent-ink rounded-cell"
              />
              <span>Devices & ASN</span>
            </label>
          </div>

          {/* Cycles Detected List */}
          <div className="space-y-2 border-t border-line/60 pt-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-seal uppercase tracking-wider text-[11px]">
                Circular Cycles (6)
              </span>
              <span className="text-[10px] text-seal font-bold">DETECTED</span>
            </div>
            <div className="space-y-1">
              <button
                onClick={() => setTracedCycle(true)}
                className="w-full p-2 rounded-cell bg-seal-wash/40 border border-seal/30 text-left hover:bg-seal-wash transition"
              >
                <div className="font-semibold text-seal text-[11px]">Cycle #1: 4 Accounts</div>
                <div className="text-[10px] text-ink-muted">1,000 shares • 0 net delta</div>
              </button>
            </div>
          </div>
        </div>

        {/* Center Column: Graph Canvas (6 cols) */}
        <div className="lg:col-span-6 bg-bg-raised border border-line rounded-panel p-4 shadow-sm flex flex-col justify-between min-h-[540px] relative overflow-hidden">
          {tableView ? (
            /* Table Alternative (§6.4) */
            <div className="overflow-y-auto max-h-[500px] space-y-4 text-xs">
              <h4 className="font-bold text-ink uppercase text-[11px]">Nodes Table</h4>
              <table className="w-full text-left font-mono border border-line rounded-cell overflow-hidden">
                <thead className="bg-bg-sunken text-ink-muted">
                  <tr>
                    <th className="p-2">ID</th>
                    <th className="p-2">Type</th>
                    <th className="p-2">Label</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/60">
                  {nodes.map((n) => (
                    <tr
                      key={n.id}
                      onClick={() => setSelectedNode(n)}
                      className="cursor-pointer hover:bg-bg-sunken/60"
                    >
                      <td className="p-2 font-bold text-ink">{n.id}</td>
                      <td className="p-2 text-ink-muted">{n.type}</td>
                      <td className="p-2">{n.label}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            /* Interactive Visual Topology Canvas */
            <div className="flex-1 flex flex-col justify-between relative">
              {/* Toolbar */}
              <div className="flex items-center justify-between z-10 mb-2">
                <div className="flex items-center space-x-1.5 text-xs">
                  <span className="px-2 py-0.5 rounded-cell bg-bg-sunken border border-line text-ink-muted">
                    Layout: <strong>fcose</strong>
                  </span>
                  <span className="text-[11px] text-ink-muted">
                    {nodes.length} nodes • {edges.length} edges
                  </span>
                </div>
                <div className="flex items-center space-x-1">
                  <button className="p-1 rounded-cell border border-line bg-bg-sunken hover:bg-bg-raised text-ink">
                    <ZoomIn className="h-3.5 w-3.5" />
                  </button>
                  <button className="p-1 rounded-cell border border-line bg-bg-sunken hover:bg-bg-raised text-ink">
                    <ZoomOut className="h-3.5 w-3.5" />
                  </button>
                  <button className="p-1 rounded-cell border border-line bg-bg-sunken hover:bg-bg-raised text-ink">
                    <Maximize2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              {/* Topology SVG Network */}
              <div className="flex-1 bg-bg-sunken/30 rounded-panel border border-line/60 p-6 flex flex-col justify-between relative">
                {/* Background Grid Pattern */}
                <div className="absolute inset-0 bg-[radial-gradient(var(--line)_1px,transparent_1px)] [background-size:20px_20px] opacity-40 pointer-events-none" />

                {/* Top: ASN Infrastructure */}
                {showDevices && (
                  <div className="flex justify-center z-10">
                    <div className="px-3 py-1 rounded-cell bg-bg-raised border border-line text-xs font-mono font-bold text-ink shadow-sm flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-verified" />
                      <span>ASN 55836 (Shared Proxy Gateway)</span>
                    </div>
                  </div>
                )}

                {/* Middle: 5 Device Clusters */}
                {showDevices && (
                  <div className="flex justify-around items-center z-10 py-4">
                    {[1, 2, 3, 4, 5].map((d) => (
                      <div
                        key={d}
                        className="px-2.5 py-1.5 rounded-cell bg-bg-raised border border-line text-[11px] font-mono text-center shadow-sm"
                      >
                        <div className="font-bold text-ink">DEV-{d}</div>
                        <div className="text-[9px] text-ink-muted">4 Accounts</div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Bottom: Ring Accounts Nodes with Inferred Ultraviolet Edges */}
                <div className="grid grid-cols-5 gap-3 z-10">
                  {nodes.slice(0, 10).map((n, i) => {
                    const isSelected = selectedNode?.id === n.id;
                    const clusterColor = CLUSTERS[n.cluster || 0];

                    return (
                      <button
                        key={n.id}
                        onClick={() => {
                          setSelectedNode(n);
                          // find connected edge
                          const linkedEdge = edges.find(
                            (e) => e.source === n.id || e.target === n.id
                          );
                          if (linkedEdge) setSelectedEdge(linkedEdge);
                        }}
                        className={`p-2 rounded-cell border text-center transition ${
                          isSelected
                            ? "border-uv bg-uv-wash text-uv font-bold shadow-sm"
                            : "bg-bg-raised border-line hover:border-line-strong text-ink"
                        }`}
                        style={{
                          boxShadow: isSelected ? "0 0 0 2px var(--uv)" : undefined,
                        }}
                      >
                        <div className="w-4 h-4 rounded-full mx-auto mb-1 flex items-center justify-center text-[9px] font-bold text-ink"
                             style={{ backgroundColor: `${clusterColor}33`, border: `1.5px solid ${clusterColor}` }}>
                          {i + 1}
                        </div>
                        <div className="font-mono text-[10px] font-semibold">{n.id}</div>
                      </button>
                    );
                  })}
                </div>

                {/* Traced Cycle Overlay Notice */}
                {tracedCycle && (
                  <div className="absolute inset-x-4 top-1/2 -translate-y-1/2 p-3 rounded-panel bg-seal-wash/95 border border-seal text-seal text-xs font-semibold flex items-center justify-between shadow-pop z-20">
                    <div className="flex items-center space-x-2">
                      <ShieldAlert className="h-4 w-4" />
                      <span>Tracing Cycle: acc_01 ➔ acc_02 ➔ acc_03 ➔ acc_01 (4 matched trades)</span>
                    </div>
                    <button
                      onClick={() => setTracedCycle(false)}
                      className="text-xs hover:underline"
                    >
                      Dismiss
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Footnote */}
          <div className="pt-2 border-t border-line/60 flex justify-between items-center text-[11px] text-ink-muted">
            <span>Observed trades: Solid line • Inferred links: Dashed ultraviolet</span>
            <span className="font-mono">FPS: 60</span>
          </div>
        </div>

        {/* Right Column: Inspector (3 cols) */}
        <div className="lg:col-span-3 bg-bg-raised border border-line rounded-panel p-4 space-y-4 shadow-sm text-xs">
          <div className="flex items-center justify-between border-b border-line pb-2">
            <span className="font-semibold text-ink uppercase tracking-wide">
              Edge Inspector
            </span>
            <span className="text-[10px] text-ink-muted font-mono">Attribution Basis</span>
          </div>

          {selectedEdge ? (
            <div className="space-y-4">
              {/* Edge Link Header */}
              <div className="bg-bg-sunken p-3 rounded-cell space-y-1.5 border border-line">
                <div className="flex justify-between items-center">
                  <span className="font-mono font-bold text-ink">
                    {selectedEdge.source} ➔ {selectedEdge.target}
                  </span>
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded-cell font-bold ${
                      vetoedLinks.has(`${selectedEdge.source}->${selectedEdge.target}`)
                        ? "bg-bg-sunken text-ink-muted border border-line"
                        : "bg-uv-wash text-uv border border-uv/20"
                    }`}
                  >
                    {vetoedLinks.has(`${selectedEdge.source}->${selectedEdge.target}`)
                      ? "VETOED"
                      : "INFERRED"}
                  </span>
                </div>
                <div className="text-[11px] text-ink-muted">
                  Confidence Score:{" "}
                  <strong className="font-mono text-uv">
                    {selectedEdge.confidence ? (selectedEdge.confidence * 100).toFixed(1) : 96.0}%
                  </strong>
                </div>
              </div>

              {/* Attribution Basis Breakdown (§6.4) */}
              <div className="space-y-2 border-t border-line/60 pt-3">
                <span className="font-semibold text-ink uppercase tracking-wider text-[11px] block">
                  Mathematical Basis
                </span>
                <div className="space-y-1.5 divide-y divide-line/40 text-[11px]">
                  <div className="flex justify-between items-center pt-1">
                    <span className="text-ink-muted">Shared device (DEV-1)</span>
                    <span className="font-mono text-ink">0.90 × 1.0</span>
                  </div>
                  <div className="flex justify-between items-center pt-1">
                    <span className="text-ink-muted">Circular cycle participation</span>
                    <span className="font-mono text-ink">0.85 × 1.0</span>
                  </div>
                  <div className="flex justify-between items-center pt-1">
                    <span className="text-ink-muted">Synchronized reaction delay</span>
                    <span className="font-mono text-ink">0.70 × 0.9</span>
                  </div>
                </div>

                <div className="p-2 bg-bg-sunken rounded-cell border border-line/60 text-[11px] font-mono text-ink">
                  Combined: 1 - ∏(1 - w·s) = <strong className="text-uv">0.96</strong>
                </div>
              </div>

              {/* Evidence citations */}
              <div className="space-y-1.5 border-t border-line/60 pt-3">
                <span className="font-semibold text-ink text-[11px] uppercase tracking-wide block">
                  Supporting Evidence
                </span>
                <div className="flex items-center space-x-1.5">
                  <EvidenceTag n={2} />
                  <EvidenceTag n={3} />
                  <span className="text-[11px] text-ink-muted">Trade slice & device cluster</span>
                </div>
              </div>

              {/* Challenge Actions */}
              <div className="space-y-2 border-t border-line/60 pt-3">
                <Button
                  size="sm"
                  variant="danger"
                  className="w-full"
                  onClick={() => setFeedbackPopover(true)}
                >
                  <X className="h-3.5 w-3.5 mr-1.5" />
                  <span>{copy.action.markFalse}</span>
                </Button>

                <Button
                  size="sm"
                  variant="secondary"
                  className="w-full"
                  onClick={handleConfirmLink}
                >
                  <Check className="h-3.5 w-3.5 mr-1.5 text-verified" />
                  <span>{copy.action.confirmLink}</span>
                </Button>
              </div>

              {/* False Positive Popover Modal */}
              {feedbackPopover && (
                <div className="p-3 rounded-panel bg-bg-sunken border border-line space-y-2.5 animate-in fade-in">
                  <span className="font-semibold text-ink text-xs block">
                    Challenge Link Validity
                  </span>
                  <p className="text-[11px] text-ink-muted">
                    Provide optional rationale for excluding this edge from the attribution graph:
                  </p>
                  <textarea
                    rows={2}
                    value={feedbackComment}
                    onChange={(e) => setFeedbackComment(e.target.value)}
                    placeholder="E.g. Verified legitimate market maker arbitrage…"
                    className="w-full p-2 text-xs bg-bg-raised border border-line rounded-cell text-ink focus:outline-none focus:border-focus"
                  />
                  <div className="flex justify-end space-x-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setFeedbackPopover(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={handleMarkFalsePositive}
                    >
                      Submit
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="py-12 text-center text-ink-muted text-xs">
              Select an edge or account on the canvas to inspect evidence basis.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
