const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  { id: "cloud_security",        label: "Cloud Security",          description: "Cloud misconfigs, container risks, IAM in AWS/Azure/GCP" },
];

export type OrgProfile = {
  id: number;
  technologies: string[];
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

export async function fetchCards(): Promise<ProvocationCard[]> {
  const res = await fetch(`${API_BASE}/api/cards?limit=100`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to fetch cards: ${res.status}`);
  const data = await res.json();
  return data.cards ?? [];
}

export async function fetchProfile(): Promise<OrgProfile> {
  const res = await fetch(`${API_BASE}/api/profile`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch profile: ${res.status}`);
  return res.json();
}

export async function fetchSources(): Promise<CustomSource[]> {
  const res = await fetch(`${API_BASE}/api/profile/sources`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch sources: ${res.status}`);
  const data = await res.json();
  return data.sources ?? [];
}

export async function fetchBuiltinSources(): Promise<BuiltinSource[]> {
  const res = await fetch(`${API_BASE}/api/profile/sources/builtin`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch builtin sources: ${res.status}`);
  const data = await res.json();
  return data.sources ?? [];
}

export async function fetchTeamSummary(cardId: string, team: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/cards/${cardId}/team-summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ team }),
  });
  if (!res.ok) throw new Error(`Failed to fetch team summary: ${res.status}`);
  const data = await res.json();
  return data.summary ?? "";
}
