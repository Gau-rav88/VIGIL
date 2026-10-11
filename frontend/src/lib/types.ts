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
