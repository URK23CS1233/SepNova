/**
 * SepNova API client
 * ------------------
 * Every backend route now requires a valid Supabase JWT. This client attaches
 * the current session's access token to every request and exposes the new
 * simulation/types used by the bedside monitor.
 */
import { supabase } from "@/lib/supabase";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function authHeaders(): Promise<Record<string, string>> {
  if (
    typeof window !== "undefined" &&
    window.localStorage.getItem("sepnova_demo") === "1"
  ) {
    return { Authorization: "Bearer demo" };
  }
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const extra = (opts?.headers ?? {}) as Record<string, string>;
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
      ...extra,
    },
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

// ── Types ─────────────────────────────────────────────────────────────────────

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
  latest_vitals?: Vitals | null;
}

export interface Prediction {
  patient_id: string;
  risk_score: number;
  risk_level: string;
  xgb_score: number;
  lgb_score: number;
  model_version: string;
  predicted_at: string;
  confidence?: number;
  data_complete?: boolean;
  missing_features?: string[];
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

export interface ShapFeature {
  feature: string;
  label: string;
  value: number;
  shap: number;
}

export interface SimulatedHour {
  hour: number;
  simulated: true;
  pre_onset: boolean;
  vitals: { HR: number; MAP: number; RESP: number; TEMP: number; O2SAT: number; SBP: number; GCS: number };
  labs: { WBC: number; Lactate: number; Creatinine: number; Platelets: number; Bilirubin_total: number };
  sofa: { sofa_total: number; organ_dysfunction: boolean };
  qsofa: { qsofa_total: number; high_risk_qsofa: boolean };
  sirs: { sirs_count: number; sirs_positive: boolean };
  risk_score: number;
  risk_level: string;
  xgb_score: number;
  lgb_score: number;
  confidence: number;
  data_complete: boolean;
  missing_features: string[];
  top_features: ShapFeature[];
  explanation_method: string;
}

export interface SimulationResult {
  simulated: true;
  disclaimer: string;
  config: {
    onset_hour: number;
    total_hours: number;
    severity: number;
    noise: number;
    seed: number | null;
    ramp_hours: number;
    window_hours: number;
  };
  model_version: string;
  threshold: number;
  alert_thresholds: Record<string, number>;
  onset_hour: number;
  first_flagged_hour: number | null;
  lead_time_hours: number | null;
  lead_time_available: boolean;
  hours: SimulatedHour[];
}

export interface SimulationConfig {
  onset_hour: number;
  total_hours: number;
  severity: number;
  noise: number;
  seed?: number;
  ramp_hours?: number;
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const api = {
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
  simulate: (config: SimulationConfig) =>
    req<SimulationResult>("/api/v1/simulate/", {
      method: "POST",
      body: JSON.stringify(config),
    }),
};
