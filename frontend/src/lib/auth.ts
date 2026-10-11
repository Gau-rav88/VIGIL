const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export type Role = "compliance_officer" | "investigator" | "admin" | "auditor_readonly";

let currentRole: Role = "compliance_officer";
let cachedToken: string | null = null;

export function getRole(): Role {
  if (typeof window !== "undefined") {
    const saved = sessionStorage.getItem("vigil_role") as Role;
    if (saved) currentRole = saved;
  }
  return currentRole;
}

export async function setRole(role: Role): Promise<string> {
  currentRole = role;
  if (typeof window !== "undefined") {
    sessionStorage.setItem("vigil_role", role);
    sessionStorage.removeItem("vigil_token");
  }
  cachedToken = null;
  return getAuthToken();
}

export async function getAuthToken(): Promise<string> {
  if (typeof window !== "undefined") {
    const saved = sessionStorage.getItem("vigil_token");
    if (saved) {
      cachedToken = saved;
      return saved;
    }
  }

  if (cachedToken) return cachedToken;

  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/dev-token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sub: `dev_${getRole()}`, role: getRole() }),
    });

    if (res.ok) {
      const data = await res.json();
      cachedToken = data.token;
      if (typeof window !== "undefined" && cachedToken) {
        sessionStorage.setItem("vigil_token", cachedToken);
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
