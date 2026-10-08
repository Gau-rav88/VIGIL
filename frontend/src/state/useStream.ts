import { create } from "zustand";
import { TickerData, AlertData, fetchTickers, fetchAlerts } from "@/lib/api";

interface StreamState {
  tickers: TickerData[];
  alerts: AlertData[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export const useStream = create<StreamState>((set) => ({
  tickers: [],
  alerts: [],
  loading: true,
  error: null,
  refresh: async () => {
    try {
      const [tickers, alerts] = await Promise.all([fetchTickers(), fetchAlerts()]);
      set({ tickers, alerts, loading: false, error: null });
    } catch (e: any) {
      set({ error: e.message, loading: false });
    }
  },
}));
