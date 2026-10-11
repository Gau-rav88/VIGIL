import { create } from "zustand";
import { TickerData, AlertData, fetchTickers, fetchAlerts, fetchBackendHealth, BackendHealthData } from "@/lib/api";
import { getAuthToken } from "@/lib/auth";

export type ConnectionStatus = "connected" | "connecting" | "polling" | "offline";

interface StreamState {
  tickers: TickerData[];
  alerts: AlertData[];
  loading: boolean;
  error: string | null;
  connectionStatus: ConnectionStatus;
  backendHealth: BackendHealthData | null;
  refresh: () => Promise<void>;
  startStreaming: () => () => void;
  checkHealth: () => Promise<void>;
}

export const useStream = create<StreamState>((set, get) => ({
  tickers: [],
  alerts: [],
  loading: true,
  error: null,
  connectionStatus: "connecting",
  backendHealth: null,

  checkHealth: async () => {
    try {
      const health = await fetchBackendHealth();
      set({ backendHealth: health });
    } catch {
      set({ backendHealth: { status: "offline" } });
    }
  },

  refresh: async () => {
    try {
      const [tickers, alerts] = await Promise.all([fetchTickers(), fetchAlerts()]);
      set({ tickers, alerts, loading: false, error: null });
    } catch (e: any) {
      set({ error: e.message, loading: false });
    }
  },

  startStreaming: () => {
    let ws: WebSocket | null = null;
    let pollInterval: any = null;
    let healthInterval: any = null;
    let reconnectTimeout: any = null;
    let backoffMs = 1000;
    let isCleanedUp = false;

    const startPollingFallback = () => {
      set({ connectionStatus: "polling" });
      if (!pollInterval) {
        pollInterval = setInterval(async () => {
          if (!isCleanedUp) {
            await get().refresh();
          }
        }, 3000);
      }
    };

    const stopPollingFallback = () => {
      if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
      }
    };

    const connectWs = async () => {
      if (isCleanedUp) return;
      set({ connectionStatus: "connecting" });

      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
      const wsBase = process.env.NEXT_PUBLIC_WS_URL || apiBase.replace(/^http/, "ws");
      const token = await getAuthToken();

      try {
        const url = `${wsBase}/ws/v1/stream?topics=heatmap,anomalies,cases&token=${encodeURIComponent(token)}`;
        ws = new WebSocket(url);

        ws.onopen = () => {
          if (isCleanedUp) return;
          set({ connectionStatus: "connected", error: null });
          stopPollingFallback();
          backoffMs = 1000;
        };

        ws.onmessage = (event) => {
          if (isCleanedUp) return;
          try {
            const frame = JSON.parse(event.data);
            if (frame.topic === "heatmap" && Array.isArray(frame.data)) {
              set((state) => {
                const updatedTickers = [...state.tickers];
                for (const item of frame.data) {
                  const idx = updatedTickers.findIndex((t) => t.symbol === item.symbol);
                  if (idx >= 0) {
                    updatedTickers[idx] = { ...updatedTickers[idx], ...item };
                  }
                }
                return { tickers: updatedTickers };
              });
            } else if (frame.topic === "anomalies" && frame.data) {
              const anom = frame.data;
              set((state) => {
                const newAlert: AlertData = {
                  id: anom.anomaly_id || `anom-${Date.now()}`,
                  ts: frame.ts || new Date().toISOString(),
                  symbol: anom.symbol || "UNKNOWN",
                  type: anom.type || "ANOMALY",
                  severity: (anom.severity as any) || "HIGH",
                  confidence: anom.score || 0.9,
                  summary: `${anom.type} on ${anom.symbol}`,
                  details: anom.metrics || {},
                };
                return { alerts: [newAlert, ...state.alerts.slice(0, 49)] };
              });
            }
          } catch (err) {
            console.debug("Failed parsing WS frame", err);
          }
        };

        ws.onerror = () => {
          if (isCleanedUp) return;
          startPollingFallback();
        };

        ws.onclose = () => {
          if (isCleanedUp) return;
          startPollingFallback();
          reconnectTimeout = setTimeout(() => {
            backoffMs = Math.min(backoffMs * 2, 10000);
            connectWs();
          }, backoffMs);
        };
      } catch (err) {
        startPollingFallback();
      }
    };

    // Initial load
    get().checkHealth();
    get().refresh();
    connectWs();

    healthInterval = setInterval(() => {
      if (!isCleanedUp) get().checkHealth();
    }, 5000);

    return () => {
      isCleanedUp = true;
      if (ws) ws.close();
      stopPollingFallback();
      if (healthInterval) clearInterval(healthInterval);
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  },
}));
