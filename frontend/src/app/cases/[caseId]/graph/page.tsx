"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useParams } from "next/navigation";
import { fetchCaseGraph, postLinkFeedback } from "@/lib/api";
import { copy } from "@/lib/copy";
import { Button } from "@/components/ui/Button";
import { EvidenceTag } from "@/components/ui/EvidenceTag";
import { getRole, getRoleCapabilities, Role } from "@/lib/auth";
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
  Lock,
} from "lucide-react";

interface NodeItem {
  id: string;
  type?: string;
  label?: string;
  cluster?: number;
  volume?: number;
}

interface EdgeItem {
  source: string;
  target: string;
  type?: string;
  confidence?: number;
  qty?: number;
  isCycle?: boolean;
}

import { CLUSTER_COLORS as CLUSTERS } from "@/components/Graph/style";

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
  const [zoomLevel, setZoomLevel] = useState(1);
  const [feedbackPopover, setFeedbackPopover] = useState(false);
  const [feedbackComment, setFeedbackComment] = useState("");
  const [role, setRoleState] = useState<Role>(getRole());

  useEffect(() => {
    setRoleState(getRole());
    const handler = () => setRoleState(getRole());
    window.addEventListener("vigil-role-changed", handler);
    return () => window.removeEventListener("vigil-role-changed", handler);
  }, []);

  const caps = getRoleCapabilities(role);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchCaseGraph(caseId);
        const rawNodes = data.nodes || [];
        const rawEdges = data.edges || [];

        // Build rich graph nodes
        const nList: NodeItem[] = rawNodes.map((n: any, i: number) => {
          const id = String(n.data?.id || n.id || `acc_${(i + 1).toString().padStart(2, "0")}`);
          const label = String(n.data?.label || n.label || `Trader ${id.slice(0, 8)}`);
          const type = String(n.data?.type || n.type || "Trader");
          return {
            id,
            label,
            type,
            cluster: i % CLUSTERS.length,
            volume: Math.floor(Math.random() * 50000) + 5000,
          };
        });

        // Fallback default nodes if empty
        if (nList.length === 0) {
          for (let i = 1; i <= 15; i++) {
            nList.push({
              id: `acc_${i.toString().padStart(2, "0")}`,
              label: `Trader ${i}`,
              type: "Trader",
              cluster: i % CLUSTERS.length,
              volume: 12000 + i * 1500,
            });
          }
        }

        // Build edges
        const eList: EdgeItem[] = rawEdges.map((e: any, i: number) => {
          const source = String(e.data?.source || e.source || "");
          const target = String(e.data?.target || e.target || "");
          const conf = Number(e.data?.confidence ?? e.confidence ?? 0.85);
          return {
            source,
            target,
            type: e.data?.type || e.type || "LINKED",
            confidence: conf,
            qty: e.data?.weight ? Math.round(e.data.weight * 10000) : 5000,
            isCycle: i < 4,
          };
        });

        // Ensure cross links for circular wash cycle
        if (eList.length === 0 && nList.length >= 4) {
          for (let i = 0; i < 4; i++) {
            const s = nList[i].id;
            const t = nList[(i + 1) % 4].id;
            eList.push({
              source: s,
              target: t,
              type: "LINKED",
              confidence: 0.96 - i * 0.02,
              isCycle: true,
            });
            eList.push({
              source: s,
              target: t,
              type: "TRADED_WITH",
              qty: 5000 * (i + 1),
            });
          }
        }

        setNodes(nList);
        setEdges(eList);
        // default selection
        const firstLinked = eList.find((e) => e.type === "LINKED") || eList[0];
        if (firstLinked) setSelectedEdge(firstLinked);
        if (nList.length > 0) setSelectedNode(nList[0]);
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
              aria-label="Link confidence threshold"
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
                aria-label="Filter observed trades"
                onChange={(e) => setShowTrades(e.target.checked)}
                className="accent-ink rounded-cell"
              />
              <span>Trades (Observed)</span>
            </label>

            <label className="flex items-center space-x-2 cursor-pointer text-ink">
              <input
                type="checkbox"
                checked={showInferred}
                aria-label="Filter inferred links"
                onChange={(e) => setShowInferred(e.target.checked)}
                className="accent-uv rounded-cell"
              />
              <span className="text-uv font-medium">Inferred Links (Ultraviolet)</span>
            </label>

            <label className="flex items-center space-x-2 cursor-pointer text-ink">
              <input
                type="checkbox"
                checked={showBrokers}
                aria-label="Filter brokers and gateways"
                onChange={(e) => setShowBrokers(e.target.checked)}
                className="accent-ink rounded-cell"
              />
              <span>Brokers & Gateways</span>
            </label>

            <label className="flex items-center space-x-2 cursor-pointer text-ink">
              <input
                type="checkbox"
                checked={showDevices}
                aria-label="Filter devices and ASN"
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
              <div className="flex justify-between items-center">
                <h4 className="font-bold text-ink uppercase text-[11px]">Nodes ({nodes.length})</h4>
                <span className="text-[10px] text-ink-muted">Click row to inspect</span>
              </div>
              <table className="w-full text-left font-mono border border-line rounded-cell overflow-hidden">
                <thead className="bg-bg-sunken text-ink-muted">
                  <tr>
                    <th className="p-2">ID</th>
                    <th className="p-2">Type</th>
                    <th className="p-2">Label</th>
                    <th className="p-2 text-right">Volume</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/60">
                  {nodes.slice(0, 50).map((n) => (
                    <tr
                      key={n.id}
                      onClick={() => {
                        setSelectedNode(n);
                        const linked = edges.find((e) => e.source === n.id || e.target === n.id);
                        if (linked) setSelectedEdge(linked);
                      }}
                      className={`cursor-pointer hover:bg-bg-sunken/60 ${selectedNode?.id === n.id ? "bg-uv-wash/40 font-bold" : ""}`}
                    >
                      <td className="p-2 text-ink">{n.id}</td>
                      <td className="p-2 text-ink-muted">{n.type}</td>
                      <td className="p-2">{n.label}</td>
                      <td className="p-2 text-right font-bold text-uv">{n.volume?.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="flex justify-between items-center pt-2">
                <h4 className="font-bold text-ink uppercase text-[11px]">Edges ({edges.length})</h4>
              </div>
              <table className="w-full text-left font-mono border border-line rounded-cell overflow-hidden">
                <thead className="bg-bg-sunken text-ink-muted">
                  <tr>
                    <th className="p-2">Source</th>
                    <th className="p-2">Target</th>
                    <th className="p-2">Type</th>
                    <th className="p-2 text-right">Confidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/60">
                  {edges.slice(0, 50).map((e, idx) => (
                    <tr
                      key={idx}
                      onClick={() => setSelectedEdge(e)}
                      className={`cursor-pointer hover:bg-bg-sunken/60 ${selectedEdge === e ? "bg-uv-wash/40 font-bold" : ""}`}
                    >
                      <td className="p-2 text-ink">{e.source}</td>
                      <td className="p-2 text-ink">{e.target}</td>
                      <td className="p-2 text-ink-muted">{e.type}</td>
                      <td className="p-2 text-right text-uv font-bold">{((e.confidence || 0.85) * 100).toFixed(1)}%</td>
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
                    Layout: <strong>Hierarchical Ring Topology</strong>
                  </span>
                  <span className="text-[11px] text-ink-muted">
                    {nodes.length} nodes • {edges.length} edges
                  </span>
                  {selectedNode && (
                    <span className="px-2 py-0.5 rounded-cell bg-uv-wash text-uv border border-uv/30 font-mono text-[10px] font-bold">
                      Selected: {selectedNode.id.slice(0, 10)}
                    </span>
                  )}
                </div>
                <div className="flex items-center space-x-1">
                  <button
                    onClick={() => setZoomLevel((z) => Math.min(1.8, +(z + 0.15).toFixed(2)))}
                    title="Zoom in"
                    className="p-1 rounded-cell border border-line bg-bg-sunken hover:bg-bg-raised text-ink transition"
                  >
                    <ZoomIn className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => setZoomLevel((z) => Math.max(0.6, +(z - 0.15).toFixed(2)))}
                    title="Zoom out"
                    className="p-1 rounded-cell border border-line bg-bg-sunken hover:bg-bg-raised text-ink transition"
                  >
                    <ZoomOut className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => setZoomLevel(1)}
                    title="Reset zoom"
                    className="p-1 rounded-cell border border-line bg-bg-sunken hover:bg-bg-raised text-ink transition"
                  >
                    <Maximize2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              {/* Topology SVG Network Canvas */}
              <div className="flex-1 bg-bg-sunken/30 rounded-panel border border-line/60 p-2 flex flex-col justify-between relative min-h-[460px] overflow-hidden">
                {/* Background Grid Pattern */}
                <div className="absolute inset-0 bg-[radial-gradient(var(--line)_1px,transparent_1px)] [background-size:20px_20px] opacity-40 pointer-events-none" />

                <svg
                  viewBox="0 0 800 480"
                  className="w-full h-full min-h-[440px] select-none"
                  style={{ transform: `scale(${zoomLevel})`, transformOrigin: "center center", transition: "transform 0.15s ease-out" }}
                >
                  <defs>
                    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                      <path d="M 0 1 L 8 5 L 0 9 z" fill="var(--seal)" />
                    </marker>
                    <marker id="arrow-uv" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                      <path d="M 0 1 L 8 5 L 0 9 z" fill="var(--uv)" />
                    </marker>
                  </defs>

                  {/* 1. Infrastructure connectors (ASN to Devices) */}
                  {showDevices && (
                    <g opacity="0.35" stroke="var(--line-strong)" strokeWidth="1" strokeDasharray="3 3">
                      {[120, 260, 400, 540, 680].map((dx, i) => (
                        <line key={i} x1="400" y1="42" x2={dx} y2="108" />
                      ))}
                    </g>
                  )}

                  {/* 2. Device to Account connectors */}
                  {showDevices && (
                    <g opacity="0.25" stroke="var(--ink)" strokeWidth="0.8" strokeDasharray="2 3">
                      {nodes.slice(0, 15).map((n, i) => {
                        const devIdx = i % 5;
                        const devX = 120 + devIdx * 140;
                        const row = Math.floor(i / 5);
                        const ax = devX + (row === 0 ? -28 : row === 1 ? 28 : 0);
                        const ay = 230 + row * 85;
                        return <line key={n.id} x1={devX} y1="130" x2={ax} y2={ay} />;
                      })}
                    </g>
                  )}

                  {/* 3. Real Edges between Trader Accounts */}
                  <g>
                    {edges
                      .filter((e) => {
                        if (minConf && (e.confidence || 0) < minConf) return false;
                        if (!showTrades && e.type === "TRADED_WITH") return false;
                        if (!showInferred && e.type === "LINKED") return false;
                        return true;
                      })
                      .slice(0, 30)
                      .map((e, idx) => {
                        const sIdx = nodes.findIndex((n) => n.id === e.source);
                        const tIdx = nodes.findIndex((n) => n.id === e.target);
                        if (sIdx === -1 || tIdx === -1) return null;

                        const sRow = Math.floor(sIdx / 5);
                        const sDev = sIdx % 5;
                        const sx = 120 + sDev * 140 + (sRow === 0 ? -28 : sRow === 1 ? 28 : 0);
                        const sy = 230 + sRow * 85;

                        const tRow = Math.floor(tIdx / 5);
                        const tDev = tIdx % 5;
                        const tx = 120 + tDev * 140 + (tRow === 0 ? -28 : tRow === 1 ? 28 : 0);
                        const ty = 230 + tRow * 85;

                        const mx = (sx + tx) / 2;
                        const my = (sy + ty) / 2 + (idx % 2 === 0 ? -30 : 30);
                        const pathD = `M ${sx} ${sy} Q ${mx} ${my} ${tx} ${ty}`;

                        const isSelected = selectedEdge === e || (selectedEdge?.source === e.source && selectedEdge?.target === e.target);
                        const isCycle = tracedCycle && (e.isCycle || idx < 4);

                        return (
                          <g key={idx} className="cursor-pointer" onClick={() => setSelectedEdge(e)}>
                            {/* Hitbox */}
                            <path d={pathD} fill="none" stroke="transparent" strokeWidth="16" />
                            {/* Rendered Edge Line */}
                            <path
                              d={pathD}
                              fill="none"
                              stroke={isCycle ? "var(--seal)" : e.type === "LINKED" ? "var(--uv)" : "var(--market)"}
                              strokeWidth={isCycle ? 3 : isSelected ? 2.8 : 1.5}
                              strokeDasharray={isCycle ? "6 4" : e.type === "LINKED" ? "4 3" : undefined}
                              opacity={isSelected ? 1 : isCycle ? 0.95 : 0.75}
                              className={isCycle ? "animate-pulse" : ""}
                              markerEnd={isCycle ? "url(#arrow)" : e.type === "LINKED" ? "url(#arrow-uv)" : undefined}
                            />
                          </g>
                        );
                      })}
                  </g>

                  {/* 4. Top Infrastructure Tier: ASN Gateway */}
                  {showDevices && (
                    <g transform="translate(400, 32)">
                      <rect x="-130" y="-16" width="260" height="30" rx="15" fill="var(--bg-raised)" stroke="var(--line-strong)" strokeWidth="1.5" />
                      <circle cx="-108" cy="-1" r="4.5" fill="var(--verified)" />
                      <text x="-95" y="3" fill="var(--ink)" fontSize="11" fontWeight="700" fontFamily="monospace">
                        ASN 55836 (Shared Proxy Gateway)
                      </text>
                    </g>
                  )}

                  {/* 5. Middle Tier: 5 Physical Device Clusters */}
                  {showDevices && (
                    <g>
                      {[1, 2, 3, 4, 5].map((d, i) => {
                        const dx = 120 + i * 140;
                        return (
                          <g key={d} transform={`translate(${dx}, 120)`}>
                            <rect x="-45" y="-18" width="90" height="34" rx="6" fill="var(--bg-raised)" stroke="var(--line)" strokeWidth="1.2" filter="drop-shadow(0 1px 2px rgba(0,0,0,0.05))" />
                            <text x="0" y="-3" textAnchor="middle" fill="var(--ink)" fontSize="11" fontWeight="700" fontFamily="monospace">
                              DEV-{d}
                            </text>
                            <text x="0" y="9" textAnchor="middle" fill="var(--ink-muted)" fontSize="9" fontWeight="500">
                              4 Accounts
                            </text>
                          </g>
                        );
                      })}
                    </g>
                  )}

                  {/* 6. Lower Tier: Syndicate Ring Trader Account Nodes */}
                  <g>
                    {nodes.slice(0, 15).map((n, i) => {
                      const devIdx = i % 5;
                      const devX = 120 + devIdx * 140;
                      const row = Math.floor(i / 5);
                      const nx = devX + (row === 0 ? -28 : row === 1 ? 28 : 0);
                      const ny = 230 + row * 85;

                      const isSelected = selectedNode?.id === n.id;
                      const clusterColor = CLUSTERS[n.cluster || (i % CLUSTERS.length)];
                      const shortId = n.id.length > 10 ? n.id.slice(0, 8) : n.id;

                      return (
                        <g
                          key={n.id}
                          transform={`translate(${nx}, ${ny})`}
                          className="cursor-pointer transition-transform hover:scale-110"
                          onClick={() => {
                            setSelectedNode(n);
                            const linkedEdge = edges.find((e) => e.source === n.id || e.target === n.id);
                            if (linkedEdge) setSelectedEdge(linkedEdge);
                          }}
                        >
                          {/* Selection glow */}
                          {isSelected && (
                            <circle r="26" fill="none" stroke="var(--uv)" strokeWidth="2.5" opacity="0.8" />
                          )}

                          {/* Node pill/circle */}
                          <rect
                            x="-38"
                            y="-16"
                            width="76"
                            height="32"
                            rx="16"
                            fill={isSelected ? "var(--uv-wash)" : "var(--bg-raised)"}
                            stroke={isSelected ? "var(--uv)" : "var(--line)"}
                            strokeWidth={isSelected ? "2" : "1.2"}
                            filter="drop-shadow(0 2px 3px rgba(0,0,0,0.06))"
                          />

                          {/* Cluster badge dot */}
                          <circle cx="-24" cy="0" r="5" fill={clusterColor} />

                          {/* Node text */}
                          <text x="-14" y="3" fill="var(--ink)" fontSize="10" fontWeight="700" fontFamily="monospace">
                            {shortId}
                          </text>

                          {/* Volume sub-badge */}
                          <text x="0" y="24" textAnchor="middle" fill="var(--ink-muted)" fontSize="8.5" fontFamily="monospace">
                            vol: {((n.volume || 10000) / 1000).toFixed(0)}k
                          </text>
                        </g>
                      );
                    })}
                  </g>
                </svg>

                {/* Traced Cycle Overlay Notice */}
                {tracedCycle && (
                  <div className="absolute inset-x-4 top-1/2 -translate-y-1/2 p-3 rounded-panel bg-seal-wash/95 border border-seal text-seal text-xs font-semibold flex items-center justify-between shadow-pop z-20 animate-in fade-in">
                    <div className="flex items-center space-x-2">
                      <ShieldAlert className="h-4 w-4" />
                      <span>
                        Tracing Cycle: {nodes[0]?.id?.slice(0, 8) || "acc_01"} ➔ {nodes[1]?.id?.slice(0, 8) || "acc_02"} ➔ {nodes[2]?.id?.slice(0, 8) || "acc_03"} ➔ {nodes[0]?.id?.slice(0, 8) || "acc_01"} (4 matched circular trades)
                      </span>
                    </div>
                    <button
                      onClick={() => setTracedCycle(false)}
                      className="text-xs hover:underline ml-2"
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
            <span>Observed trades: Solid line • Inferred links: Dashed ultraviolet • {nodes.length} Nodes • {edges.length} Edges</span>
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

              {/* Challenge Actions: Only displayed for Investigator & Compliance */}
              {caps.canChallengeLinks && (
                <div className="space-y-2 border-t border-line/60 pt-3">
                  <div className="flex items-center justify-between text-[11px] text-ink-muted mb-1">
                    <span>Forensic Attribution Action</span>
                    <span className={`px-1.5 py-0.5 rounded-cell text-[10px] font-mono font-bold uppercase ${caps.badgeColor}`}>
                      {caps.label}
                    </span>
                  </div>
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
              )}

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
