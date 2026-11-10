const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Patient {
  id: string;
  patient_id: string;
  age?: number;
  gender?: number;
  ward: string;
  status: string;
  icu_los?: number;
  latest_risk_score?: number;
  latest_risk_level?: string;
}

export interface Vitals {
  hour: number;
  hr?: number;
  o2sat?: number;
  temp?: number;
  sbp?: number;
  map?: number;
  dbp?: number;
  resp?: number;
}

export interface Prediction {
  patient_id: string;
  risk_score: number;
  risk_level: string;
  xgb_score: number;
  lgb_score: number;
  model_version: string;
  predicted_at: string;
}

export interface Alert {
  id: string;
  patient_id: string;
  alert_type: string;
  severity: string;
  message: string;
  risk_score?: number;
  is_acknowledged: boolean;
  created_at: string;
}

export interface ModelRun {
  id: string;
  run_name?: string;
  model_type?: string;
  auroc?: number;
  auprc?: number;
  sensitivity?: number;
  specificity?: number;
  f1_score?: number;
  threshold?: number;
  n_patients?: number;
  n_sepsis?: number;
  ran_at: string;
}

export interface DashboardSummary {
  total_patients: number;
  critical_count: number;
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
  unacknowledged_alerts: number;
  latest_model_auroc?: number;
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const api = {
  // Generic typed GET — used by insights widgets, e.g. api.get<T>("/api/v1/insights/...")
  get: <T>(path: string) => req<T>(path),
  patients: {
    list: (ward?: string) =>
      req<Patient[]>(`/api/v1/patients${ward ? `?ward=${ward}` : ""}`),
    get: (id: string) => req<Patient>(`/api/v1/patients/${id}`),
    vitals: (id: string) => req<Vitals[]>(`/api/v1/patients/${id}/vitals`),
    labs: (id: string) => req<Record<string, unknown>[]>(`/api/v1/patients/${id}/labs`),
    predictions: (id: string) => req<Prediction[]>(`/api/v1/patients/${id}/predictions`),
    dashboard: () => req<DashboardSummary>("/api/v1/patients/dashboard"),
  },
  alerts: {
    list: (acknowledged = false) =>
      req<Alert[]>(`/api/v1/alerts?acknowledged=${acknowledged}`),
    acknowledge: (id: string, by: string) =>
      req<unknown>(`/api/v1/alerts/${id}/acknowledge?acknowledged_by=${by}`, {
        method: "POST",
      }),
    stats: () => req<Record<string, number>>("/api/v1/alerts/stats"),
  },
  model: {
    runs: () => req<ModelRun[]>("/api/v1/model/runs"),
    latest: () => req<ModelRun>("/api/v1/model/runs/latest"),
  },
};
