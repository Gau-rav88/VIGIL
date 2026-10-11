const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
const SIM_BASE = process.env.NEXT_PUBLIC_SIM_URL || "http://localhost:8090";

export interface TickerData {
  symbol: string;
  tier: string;
  price: number;
  change_pct: number;
  volume_24h: number;
  mrs: number;
  status: "NORMAL" | "ELEVATED" | "MANIPULATION_DETECTED";
  flags: string[];
}

export interface AlertData {
  id: string;
  ts: string;
  symbol: string;
  type: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM";
  confidence: number;
  summary: string;
  details: Record<string, any>;
}

export interface CaseData {
  case_id: string;
  symbol: string;
  exchange: string;
  status: "OPENED" | "PENDING_REVIEW" | "PUBLISHED" | "REJECTED";
  window_start: string;
  window_end: string;
  created_at: string;
  updated_at: string;
  overall_confidence?: number;
  completeness?: number;
}

export interface DossierData {
  dossier_id: string;
  version: number;
  merkle_root?: string;
  review_status?: string;
  created_at?: string;
}

export interface VerificationData {
  valid: boolean;
  dossier_id?: string;
  version?: number;
  checks: Array<{
    name: string;
    ok: boolean;
    checked?: number;
    entries?: number;
    key_id?: string;
  }>;
  failed: string[];
}

export async function fetchTickers(): Promise<TickerData[]> {
  const res = await fetch(`${API_BASE}/api/v1/live/tickers`);
  if (!res.ok) throw new Error("Failed to fetch tickers");
  const data = await res.json();
  return data.items || [];
}

export async function fetchAlerts(): Promise<AlertData[]> {
  const res = await fetch(`${API_BASE}/api/v1/live/alerts`);
  if (!res.ok) throw new Error("Failed to fetch alerts");
  const data = await res.json();
  return data.items || [];
}

export async function fetchCases(): Promise<CaseData[]> {
  const res = await fetch(`${API_BASE}/api/v1/cases`);
  if (!res.ok) throw new Error("Failed to fetch cases");
  const data = await res.json();
  return data.items || [];
}

export async function fetchCaseGraph(caseId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/cases/${caseId}/graph`);
  if (!res.ok) throw new Error("Failed to fetch case graph");
  return res.json();
}

export async function fetchCaseDossiers(caseId: string): Promise<DossierData[]> {
  const res = await fetch(`${API_BASE}/api/v1/cases/${caseId}/dossiers`);
  if (!res.ok) throw new Error("Failed to fetch dossiers");
  const data = await res.json();
  return data.items || [];
}

export async function reviewCase(caseId: string, status: string, comment: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/cases/${caseId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, comment }),
  });
  if (!res.ok) throw new Error("Failed to review case");
  return res.json();
}

export async function verifyDossier(dossierId: string): Promise<VerificationData> {
  const res = await fetch(`${API_BASE}/api/v1/dossiers/${dossierId}/verify`, { method: "GET" });
  if (!res.ok) throw new Error("Failed to verify dossier");
  return res.json();
}

export async function verifyBundleFile(fileBuffer: ArrayBuffer): Promise<VerificationData> {
  const res = await fetch(`${API_BASE}/api/v1/dossiers/verify-upload`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: fileBuffer,
  });
  if (!res.ok) throw new Error("Failed to verify uploaded bundle");
  return res.json();
}

export async function fetchSimStatus(): Promise<any> {
  const res = await fetch(`${SIM_BASE}/status`);
  if (!res.ok) throw new Error("Failed to fetch simulator status");
  return res.json();
}

export async function startScenario(scenarioId: string, speed = 10, seed = 42): Promise<any> {
  const res = await fetch(`${SIM_BASE}/scenarios/${scenarioId}/start?speed=${speed}&seed=${seed}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to start scenario");
  return res.json();
}

export async function stopScenario(scenarioId: string): Promise<any> {
  const res = await fetch(`${SIM_BASE}/scenarios/${scenarioId}/stop`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to stop scenario");
  return res.json();
}

export async function fetchCase(caseId: string): Promise<CaseData> {
  const res = await fetch(`${API_BASE}/api/v1/cases/${caseId}`);
  if (!res.ok) throw new Error("Failed to fetch case");
  return res.json();
}

export async function fetchCaseSeries(caseId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/cases/${caseId}/series`);
  if (!res.ok) throw new Error("Failed to fetch case series");
  return res.json();
}

export async function fetchCaseAccounts(caseId: string): Promise<{ items: any[] }> {
  const res = await fetch(`${API_BASE}/api/v1/cases/${caseId}/accounts`);
  if (!res.ok) throw new Error("Failed to fetch case accounts");
  return res.json();
}

export async function fetchCaseFlags(caseId: string): Promise<{ flags: any[] }> {
  const res = await fetch(`${API_BASE}/api/v1/cases/${caseId}/flags`);
  if (!res.ok) throw new Error("Failed to fetch case flags");
  return res.json();
}

export async function fetchCaseTimeline(caseId: string): Promise<{ items: any[]; caseId: string }> {
  const res = await fetch(`${API_BASE}/api/v1/cases/${caseId}/timeline`);
  if (!res.ok) throw new Error("Failed to fetch case timeline");
  return res.json();
}

export async function fetchCaseEvidence(caseId: string): Promise<{ items: any[]; caseId: string }> {
  const res = await fetch(`${API_BASE}/api/v1/cases/${caseId}/evidence`);
  if (!res.ok) throw new Error("Failed to fetch case evidence");
  return res.json();
}

export async function postCaseDirective(caseId: string, type: string, params: any = {}): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/cases/${caseId}/directives`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type, params }),
  });
  if (!res.ok) throw new Error("Failed to issue directive");
  return res.json();
}

export async function postLinkFeedback(
  caseId: string,
  source: string,
  target: string,
  action: string,
  comment?: string
): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/cases/${caseId}/links/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, target, action, comment }),
  });
  if (!res.ok) throw new Error("Failed to post link feedback");
  return res.json();
}

export async function fetchEntity(entityId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/entities/${entityId}`);
  if (!res.ok) throw new Error("Failed to fetch entity");
  return res.json();
}

export async function fetchDossier(dossierId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/dossiers/${dossierId}`);
  if (!res.ok) throw new Error("Failed to fetch dossier");
  return res.json();
}

export async function fetchAdminHealth(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/admin/health`);
  if (!res.ok) throw new Error("Failed to fetch admin health");
  return res.json();
}

export async function verifyLedger(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/ledger/verify`);
  if (!res.ok) throw new Error("Failed to verify ledger");
  return res.json();
}

