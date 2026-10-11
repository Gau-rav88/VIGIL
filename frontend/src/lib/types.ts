export interface CaseSeries {
  caseId: string;
  symbol: string;
  window: { start: number; end: number };
  hype: Array<{ t: number; hype: number }>;
  bars: Array<{ t: number; organic: number; ring: number; price: number }>;
  bursts: Array<{ id: string; start: number; end: number; score: number }>;
  ctaStems: Array<{ t: number; cls: string; views: number; messageId: string; evidenceId: string }>;
  markers: Array<{ t: number; type: string; severity: string; anomalyId: string }>;
  lag: {
    tSocial: number;
    tMarket: number;
    seconds: number;
    pValue: number;
    xcorrPeak: number;
  };
  evidence: Array<{
    n: number;
    t: number;
    evidenceId: string;
    type: string;
    sha256: string;
  }>;
  a11ySummary: string;
}

export function normalizeCaseSeries(raw: any, fallbackSymbol = "TICKER"): CaseSeries {
  if (!raw) {
    const now = Date.now();
    return {
      caseId: "live",
      symbol: fallbackSymbol,
      window: { start: now - 3600000, end: now },
      hype: [],
      bars: [],
      bursts: [],
      ctaStems: [],
      markers: [],
      lag: { tSocial: 0, tMarket: 0, seconds: 0, pValue: 1, xcorrPeak: 0 },
      evidence: [],
      a11ySummary: `Live surveillance series for ${fallbackSymbol}`,
    };
  }

  // Parse bars
  const rawBars = Array.isArray(raw.bars) ? raw.bars : [];
  const bars = rawBars.map((b: any) => {
    const tMs = typeof b.t === "number" ? b.t : new Date(b.t).getTime();
    const p = Number(b.price ?? b.close ?? b.p ?? 0);
    const vol = Number(b.volume ?? b.q ?? 0);
    const ringVol = Number(b.ring ?? 0);
    const orgVol = Number(b.organic ?? (vol - ringVol > 0 ? vol - ringVol : vol));
    return {
      t: isNaN(tMs) ? Date.now() : tMs,
      price: p,
      organic: orgVol,
      ring: ringVol,
      volume: vol,
    };
  });

  // Parse hype
  const rawHype = Array.isArray(raw.hype) ? raw.hype : [];
  const hype = rawHype.map((h: any) => {
    const tMs = typeof h.t === "number" ? h.t : new Date(h.t).getTime();
    return {
      t: isNaN(tMs) ? Date.now() : tMs,
      hype: Number(h.hype ?? h.score ?? 0),
    };
  });

  // Calculate window start & end
  let startMs = 0;
  let endMs = 0;
  if (raw.window?.start && raw.window?.end) {
    startMs = typeof raw.window.start === "number" ? raw.window.start : new Date(raw.window.start).getTime();
    endMs = typeof raw.window.end === "number" ? raw.window.end : new Date(raw.window.end).getTime();
  } else {
    const allTs = [...bars.map((b: { t: number }) => b.t), ...hype.map((h: { t: number }) => h.t)].filter((t: number) => !isNaN(t) && t > 0);
    if (allTs.length > 0) {
      startMs = Math.min(...allTs);
      endMs = Math.max(...allTs);
      if (startMs === endMs) {
        startMs -= 1800000;
        endMs += 1800000;
      }
    } else {
      endMs = Date.now();
      startMs = endMs - 3600000;
    }
  }

  // Bursts
  const bursts = Array.isArray(raw.bursts)
    ? raw.bursts.map((b: any) => ({
        id: String(b.id || Math.random()),
        start: typeof b.start === "number" ? b.start : new Date(b.start).getTime(),
        end: typeof b.end === "number" ? b.end : new Date(b.end).getTime(),
        score: Number(b.score ?? 0),
      }))
    : [];

  // Lag
  const lag = raw.lag && typeof raw.lag === "object"
    ? {
        tSocial: Number(raw.lag.tSocial ?? 0),
        tMarket: Number(raw.lag.tMarket ?? 0),
        seconds: Number(raw.lag.seconds ?? 0),
        pValue: Number(raw.lag.pValue ?? 1),
        xcorrPeak: Number(raw.lag.xcorrPeak ?? 0),
      }
    : { tSocial: 0, tMarket: 0, seconds: 0, pValue: 1, xcorrPeak: 0 };

  return {
    caseId: String(raw.caseId || raw.case_id || "live"),
    symbol: String(raw.symbol || fallbackSymbol),
    window: { start: startMs, end: endMs },
    hype,
    bars,
    bursts,
    ctaStems: Array.isArray(raw.ctaStems) ? raw.ctaStems : [],
    markers: Array.isArray(raw.markers) ? raw.markers : [],
    lag,
    evidence: Array.isArray(raw.evidence) ? raw.evidence : [],
    a11ySummary: raw.a11ySummary || `Surveillance series for ${raw.symbol || fallbackSymbol}`,
  };
}

export interface CaseAccount {
  accountId: string;
  shortId: string;
  brokerId: string;
  volumeShare: number;
  deviceCount: number;
  entityId: string;
  inCycles: boolean;
}

export interface CaseFlag {
  flag: string;
  since: string;
  explanation: string;
}

export interface EntityDetail {
  entityId: string;
  ringScore: number;
  memberCount: number;
  volumeShare: number;
  accounts: string[];
  brokers: string[];
  sharedDevices: string[];
  sharedNetworks: string[];
  reaction: {
    medianLatencyMs: number;
    nullMedianLatencyMs: number;
    pValue: number;
  };
  cases: string[];
}
