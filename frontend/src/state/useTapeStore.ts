import { create } from "zustand";

interface TapeStoreState {
  zoom: [number, number] | null;
  scrubberTs: number | null;
  focusedEvidenceId: string | null;
  viewMode: "chart" | "table";
  setZoom: (zoom: [number, number] | null) => void;
  setScrubber: (ts: number | null) => void;
  setFocusedEvidenceId: (id: string | null) => void;
  toggleViewMode: () => void;
}

export const useTapeStore = create<TapeStoreState>((set) => ({
  zoom: null,
  scrubberTs: null,
  focusedEvidenceId: null,
  viewMode: "chart",
  setZoom: (zoom) => set({ zoom }),
  setScrubber: (scrubberTs) => set({ scrubberTs }),
  setFocusedEvidenceId: (focusedEvidenceId) => set({ focusedEvidenceId }),
  toggleViewMode: () => set((state) => ({ viewMode: state.viewMode === "chart" ? "table" : "chart" })),
}));
