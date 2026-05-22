const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

// Centralises header injection so every request automatically carries the API
// key when one is configured. When NEXT_PUBLIC_API_KEY is not set, requests
// are sent without the header and the backend bypasses auth entirely.
function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  return fetch(url, {
    ...init,
    headers: {
      ...(API_KEY ? { "X-Api-Key": API_KEY } : {}),
      ...(init.headers ?? {}),
    },
  });
}

export type EvidenceItem = {
  source: string;
  title: string;
  url?: string;
  point: string;
};

export const TEAM_LABELS = [
  "IAM",
  "SOC",
  "AppSec",
  "Cloud/Infra",
  "Network",
  "Endpoint",
  "GRC",
  "Data/Privacy",
] as const;

export type ProvocationCard = {
  id: string;
  cluster_id: string;
  signal_headline: string;
  evidence_stack: EvidenceItem[];
  compliance_gap: string;
  contextual_question: string;
  board_talking_point: string;
  simple_headline?: string;
  affected_teams: string[];
  risk_domain: string;
  score: number;
  generated_at: string;
  status: string;
  metadata: {
    model: string;
    usage: { input_tokens: number; output_tokens: number };
    cluster_summary: string;
    signal_count?: number;
    source_count?: number;
    severity_max?: string | null;
    all_domains?: string[];
  };
};

export type RiskDomain = {
  id: string;
  label: string;
  description: string;
};

export const DOMAINS: RiskDomain[] = [
  { id: "identity_credential",   label: "Identity & Credential",  description: "Auth bypass, privilege abuse, session attacks" },
  { id: "vulnerability_patch",   label: "Vulnerability & Patch",   description: "Unpatched CVEs, exploit-in-the-wild timing" },
  { id: "supply_chain",          label: "Supply Chain",            description: "Vendor compromise, dependency attacks" },
  { id: "detection_response",    label: "Detection & Response",    description: "Dwell time, alert fatigue, logging gaps" },
  { id: "data_exposure",         label: "Data Exposure",           description: "Misconfigured storage, exfiltration vectors" },
  { id: "ransomware_extortion",  label: "Ransomware & Extortion",  description: "Encryption, extortion, cross-domain worst-case" },
];

export type OrgProfile = {
  id: number;
  technologies: string[];
  blocked_technologies: string[];
  updated_at: string;
};

export type CustomSource = {
  id: string;
  name: string;
  url: string;
  enabled: boolean;
  created_at: string;
};

export type BuiltinSource = {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
};

export async function fetchCards(limit = 50, offset = 0): Promise<ProvocationCard[]> {
  const res = await apiFetch(
    `${API_BASE}/api/cards?limit=${limit}&offset=${offset}`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(`Failed to fetch cards: ${res.status}`);
  const data = await res.json();
  return data.cards ?? [];
}

export async function fetchProfile(): Promise<OrgProfile> {
  const res = await apiFetch(`${API_BASE}/api/profile`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch profile: ${res.status}`);
  return res.json();
}

export async function fetchSources(): Promise<CustomSource[]> {
  const res = await apiFetch(`${API_BASE}/api/profile/sources`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch sources: ${res.status}`);
  const data = await res.json();
  return data.sources ?? [];
}

export async function fetchBuiltinSources(): Promise<BuiltinSource[]> {
  const res = await apiFetch(`${API_BASE}/api/profile/sources/builtin`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch builtin sources: ${res.status}`);
  const data = await res.json();
  return data.sources ?? [];
}

export async function fetchArchivedCards(before?: string): Promise<ProvocationCard[]> {
  const params = new URLSearchParams({ status: "archived", limit: "200" });
  if (before) params.set("before", before);
  const res = await apiFetch(`${API_BASE}/api/cards?${params}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch archived cards: ${res.status}`);
  const data = await res.json();
  return data.cards ?? [];
}

export async function dismissCard(cardId: string): Promise<void> {
  const res = await apiFetch(`${API_BASE}/api/cards/${cardId}/dismiss`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to dismiss card: ${res.status}`);
}

export async function fetchTeamSummary(cardId: string, team: string): Promise<string> {
  const res = await apiFetch(`${API_BASE}/api/cards/${cardId}/team-summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ team }),
  });
  if (!res.ok) throw new Error(`Failed to fetch team summary: ${res.status}`);
  const data = await res.json();
  return data.summary ?? "";
}
