import { create } from "zustand";

export interface GraphNode {
  id: string;
  type: "Account" | "Device" | "ASN" | "Cluster";
  label: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

interface GraphStoreState {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNode: GraphNode | null;
  selectedEdge: GraphEdge | null;
  setGraph: (nodes: GraphNode[], edges: GraphEdge[]) => void;
  selectNode: (node: GraphNode | null) => void;
  selectEdge: (edge: GraphEdge | null) => void;
}

export const useGraphStore = create<GraphStoreState>((set) => ({
  nodes: [],
  edges: [],
  selectedNode: null,
  selectedEdge: null,
  setGraph: (nodes, edges) => set({ nodes, edges }),
  selectNode: (node) => set({ selectedNode: node, selectedEdge: null }),
  selectEdge: (edge) => set({ selectedEdge: edge, selectedNode: null }),
}));
