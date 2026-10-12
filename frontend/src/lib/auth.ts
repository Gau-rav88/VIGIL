const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NEXT_PUBLIC_API_BASE ? process.env.NEXT_PUBLIC_API_BASE.replace(/\/api\/v1\/?$/, "") : "http://localhost:8001");

export type Role = "compliance_officer" | "investigator" | "admin" | "auditor_readonly";

export interface RoleCapabilities {
  role: Role;
  label: string;
  badgeLabel: string;
  badgeColor: string;
  description: string;
  canReviewDossier: boolean;
  canSubmitCase: boolean;
  canAdjustAnalysis: boolean;
  canChallengeLinks: boolean;
  canRevealIdentity: boolean;
  canControlSimulator: boolean;
  isReadOnly: boolean;
}

export const ROLE_DEFINITIONS: Record<Role, RoleCapabilities> = {
  compliance_officer: {
    role: "compliance_officer",
    label: "Compliance Officer",
    badgeLabel: "COMPLIANCE OFFICER",
    badgeColor: "bg-uv-wash text-uv border-uv/40",
    description: "Regulatory signing authority, identity unmasking, and enforcement oversight.",
    canReviewDossier: true,
    canSubmitCase: false,
    canAdjustAnalysis: true,
    canChallengeLinks: true,
    canRevealIdentity: true,
    canControlSimulator: false,
    isReadOnly: false,
  },
  investigator: {
    role: "investigator",
    label: "Investigator",
    badgeLabel: "INVESTIGATOR",
    badgeColor: "bg-social-wash text-social border-social/40",
    description: "Forensic analysis, edge confirmation, observation window adjustment, and case submission.",
    canReviewDossier: false,
    canSubmitCase: true,
    canAdjustAnalysis: true,
    canChallengeLinks: true,
    canRevealIdentity: false,
    canControlSimulator: false,
    isReadOnly: false,
  },
  admin: {
    role: "admin",
    label: "System Admin",
    badgeLabel: "SYSTEM ADMIN",
    badgeColor: "bg-verified-wash text-verified border-verified/40",
    description: "Scenario matching engine execution, system health diagnostics, and platform operations.",
    canReviewDossier: false,
    canSubmitCase: false,
    canAdjustAnalysis: true,
    canChallengeLinks: true,
    canRevealIdentity: false,
    canControlSimulator: true,
    isReadOnly: false,
  },
  auditor_readonly: {
    role: "auditor_readonly",
    label: "Auditor (Read-Only)",
    badgeLabel: "AUDITOR (READ-ONLY)",
    badgeColor: "bg-seal-wash text-seal border-seal/40",
    description: "Independent evidentiary inspection & cryptographic Merkle ledger verification only.",
    canReviewDossier: false,
    canSubmitCase: false,
    canAdjustAnalysis: false,
    canChallengeLinks: false,
    canRevealIdentity: false,
    canControlSimulator: false,
    isReadOnly: true,
  },
};

let currentRole: Role = "compliance_officer";
let cachedToken: string | null = null;

export function getRole(): Role {
  if (typeof window !== "undefined") {
    const saved = (sessionStorage.getItem("vigil_role") || localStorage.getItem("vigil_role")) as Role;
    if (saved && ROLE_DEFINITIONS[saved]) {
      currentRole = saved;
    }
  }
  return currentRole;
}

export function getRoleCapabilities(role?: Role): RoleCapabilities {
  const r = role || getRole();
  return ROLE_DEFINITIONS[r] || ROLE_DEFINITIONS.compliance_officer;
}

export async function setRole(role: Role): Promise<string> {
  currentRole = role;
  if (typeof window !== "undefined") {
    sessionStorage.setItem("vigil_role", role);
    localStorage.setItem("vigil_role", role);
    sessionStorage.removeItem("vigil_token");
    localStorage.removeItem("vigil_token");
  }
  cachedToken = null;
  const token = await getAuthToken();
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("vigil-role-changed", { detail: { role } }));
  }
  return token;
}

export async function getAuthToken(): Promise<string> {
  if (typeof window !== "undefined") {
    const saved = sessionStorage.getItem("vigil_token") || localStorage.getItem("vigil_token");
    if (saved) {
      cachedToken = saved;
      return saved;
    }
  }

  if (cachedToken) return cachedToken;

  try {
    const r = getRole();
    const res = await fetch(`${API_BASE}/api/v1/auth/dev-token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sub: `dev_${r}`, role: r }),
    });

    if (res.ok) {
      const data = await res.json();
      cachedToken = data.token;
      if (typeof window !== "undefined" && cachedToken) {
        sessionStorage.setItem("vigil_token", cachedToken);
        localStorage.setItem("vigil_token", cachedToken);
      }
      return cachedToken || "";
    }
  } catch (err) {
    console.warn("Could not obtain dev token from backend", err);
  }

  return "";
}

export async function getAuthHeaders(): Promise<Record<string, string>> {
  const token = await getAuthToken();
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

