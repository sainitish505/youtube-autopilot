const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token
    ? { "Content-Type": "application/json", Authorization: `Bearer ${token}` }
    : { "Content-Type": "application/json" };
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) },
  });

  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      msg = err.detail || err.message || JSON.stringify(err);
    } catch {}
    throw new Error(msg);
  }

  return res.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
}

export const auth = {
  signUp: (email: string, password: string, display_name: string) =>
    request<AuthResponse>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name }),
    }),

  signIn: (email: string, password: string) =>
    request<AuthResponse>("/api/auth/signin", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<{ user_id: string; email: string }>("/api/auth/me"),
};

// ── Jobs ──────────────────────────────────────────────────────────────────────
export interface AgentStatus {
  agent_name: string;
  status: "pending" | "running" | "done" | "failed";
  updated_at?: string;
}

export interface Job {
  id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  niche: string;
  title?: string;
  scenes_count?: number;
  video_url?: string;
  total_cost_usd: number;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  agents?: AgentStatus[];
  assets?: { type: string; url?: string; path?: string }[];
}

export interface JobListOut {
  jobs: Job[];
  total: number;
}

export const jobs = {
  list: () => request<JobListOut>("/api/jobs"),
  get: (id: string) => request<Job>(`/api/jobs/${id}`),
  create: (niche: string) =>
    request<{ job_id: string; status: string }>("/api/jobs", {
      method: "POST",
      body: JSON.stringify({ niche }),
    }),
  cancel: (id: string) =>
    request<{ message: string }>(`/api/jobs/${id}`, { method: "DELETE" }),
};

// ── Keys ─────────────────────────────────────────────────────────────────────
export interface KeyStatus {
  has_openai_key: boolean;
  openai_added_at?: string;
  has_youtube_token: boolean;
  youtube_channel_name?: string;
  youtube_channel_id?: string;
  youtube_connected_at?: string;
}

export const keys = {
  status: () => request<KeyStatus>("/api/keys"),
  saveOpenAI: (key: string) =>
    request("/api/keys/openai", {
      method: "POST",
      body: JSON.stringify({ openai_api_key: key }),
    }),
  deleteOpenAI: () => request("/api/keys/openai", { method: "DELETE" }),
};

// ── Settings ─────────────────────────────────────────────────────────────────
export interface UserSettings {
  default_niche: string;
  max_video_minutes: number;
  upload_privacy: string;
  tts_voice: string;
  video_model: string;
  auto_approve_under_dollars: number;
  autonomous_mode: boolean;
}

export const settings = {
  get: () => request<UserSettings>("/api/settings"),
  update: (data: Partial<UserSettings>) =>
    request("/api/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
};

// ── YouTube OAuth ─────────────────────────────────────────────────────────────
export const youtube = {
  connectUrl: () =>
    request<{ auth_url: string }>("/api/youtube/connect"),
  disconnect: () =>
    request("/api/youtube/disconnect", { method: "DELETE" }),
};

// ── Analytics ─────────────────────────────────────────────────────────────────
export interface AnalyticsSummary {
  // Fields returned by the actual API
  total_videos: number;
  total_cost_usd: number;
  success_rate: number;
  avg_cost_per_video: number;
  videos_this_month: number;
  cost_this_month_usd: number;
  cost_by_type: Record<string, number>;          // e.g. { sora_generate: 1.2, ... }
  videos_by_niche: Record<string, number>;       // e.g. { "finance tips": 3, ... }
}

export interface AnalyticsEvent {
  id: string;
  job_id?: string;
  event_type: string;
  tokens_used: number;
  cost_usd: number;
  created_at: string;
}

export const analytics = {
  summary: () => request<AnalyticsSummary>("/api/analytics/summary"),
  events: (limit = 50) =>
    request<{ events: AnalyticsEvent[]; total: number }>(
      `/api/analytics/events?limit=${limit}`
    ),
};
