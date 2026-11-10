"use client";
import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";
import { api, ModelRun } from "@/lib/api";
import { BarChart3, ShieldCheck } from "lucide-react";
import { pct } from "@/lib/utils";

interface MlMetrics {
  metrics: {
    auroc?: number; auprc?: number; sensitivity?: number; specificity?: number;
    f1_score?: number; threshold?: number; brier?: number;
    n_patients?: number; n_samples?: number; n_positive?: number;
    prevalence?: number; n_features?: number;
    top_features?: [string, number][];
  };
  version: string;
  threshold: number;
  feature_count: number;
  trained_at: string | null;
  methodology: string;
}

const BAR_COLORS = ["#0ea5e9", "#6366f1", "#8b5cf6", "#22c55e", "#f59e0b"];

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <tr className="rs-table__row">
      <td className="rs-table__td rs-table__td--muted">{label}</td>
      <td className="rs-table__td rs-table__td--mono">{value}</td>
    </tr>
  );
}

export default function ResultsPage() {
  const [mm, setMm]       = useState<MlMetrics | null>(null);
  const [runs, setRuns]   = useState<ModelRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      api.get<MlMetrics>("/api/v1/ml/metrics"),
      api.model.runs(),
    ]).then(([m, r]) => {
      if (m.status === "fulfilled") setMm(m.value);
      if (r.status === "fulfilled") setRuns(r.value);
      setLoading(false);
    });
  }, []);

  const M = mm?.metrics;
  const cards = M
    ? [
        { label: "AUROC", value: M.auroc },
        { label: "AUPRC", value: M.auprc },
        { label: "Sensitivity", value: M.sensitivity },
        { label: "Specificity", value: M.specificity },
        { label: "F1 Score", value: M.f1_score },
      ]
    : [];

  const featData = (M?.top_features ?? []).slice(0, 5).map(([feature, importance]) => ({
    feature,
    importance: +(importance * 100).toFixed(2),
  }));

  return (
    <div className="page">
      <div className="page-header">
        <div className="rs-head">
          <div className="rs-head__icon">
            <BarChart3 className="h-6 w-6" />
          </div>
          <div>
            <h1 className="page-title">Model Performance</h1>
            <div className="rs-subtitle-row">
              <p className="page-subtitle">Prospective sepsis early-warning — 6 hours ahead</p>
              {mm && <span className="rs-tag">{mm.version}</span>}
            </div>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="rs-skeleton" />
      ) : !mm ? (
        <div className="empty-state">
          <p className="empty-state__title">Model metrics unavailable.</p>
          <p className="empty-state__hint">
            Train the model: <code className="rs-code">cd backend &amp;&amp; python ml/train_v3.py</code>, then restart the API.
          </p>
        </div>
      ) : (
        <>
          <div className="rs-note">
            <p className="rs-note__title">
              <ShieldCheck className="h-4 w-4 text-sky-600" />
              Leakage-free evaluation
            </p>
            <p className="rs-note__body">
              {mm.methodology} Metrics are cross-validated out-of-fold, with patient-level grouping
              so no patient appears in both train and validation — they reflect genuine prospective
              performance, not the AUROC≈1.0 artefact of in-episode data leakage.
            </p>
          </div>

          <div className="rs-metrics">
            {cards.map(({ label, value }) => (
              <div key={label} className="rs-metric">
                <p className="rs-metric__label">{label}</p>
                <p className="rs-metric__value">{pct(value)}</p>
              </div>
            ))}
          </div>

          <div className="rs-charts">
            <div className="rs-chart-card">
              <h3 className="rs-chart-card__title">Top 5 Predictive Features (XGBoost gain)</h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={featData} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 10 }} />
                  <YAxis dataKey="feature" type="category" width={130} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => `${v}%`} />
                  <Bar dataKey="importance" radius={[0, 4, 4, 0]}>
                    {featData.map((_, i) => (
                      <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="rs-chart-card">
              <h3 className="rs-chart-card__title">Model Card</h3>
              <table className="rs-table">
                <tbody>
                  <FactRow label="Version" value={mm.version} />
                  <FactRow label="Features" value={String(mm.feature_count)} />
                  <FactRow label="Patients" value={M?.n_patients?.toLocaleString() ?? "—"} />
                  <FactRow label="Patient-hours" value={M?.n_samples?.toLocaleString() ?? "—"} />
                  <FactRow
                    label="Sepsis prevalence"
                    value={M?.prevalence != null ? `${(M.prevalence * 100).toFixed(1)}%` : "—"}
                  />
                  <FactRow label="Alert threshold" value={M?.threshold != null ? M.threshold.toFixed(3) : "—"} />
                  <FactRow label="Brier score" value={M?.brier != null ? M.brier.toFixed(4) : "—"} />
                  <FactRow
                    label="Trained"
                    value={mm.trained_at ? new Date(mm.trained_at).toLocaleString() : "—"}
                  />
                </tbody>
              </table>
            </div>
          </div>

          {runs.length > 0 && (
            <div className="rs-panel">
              <div className="rs-panel__head">
                <h3 className="rs-panel__title">Training Run History</h3>
              </div>
              <table className="rs-table">
                <thead className="rs-table__thead">
                  <tr>
                    {["Run", "Model", "AUROC", "AUPRC", "Sens", "Spec", "F1", "Date"].map((h) => (
                      <th key={h} className="rs-table__th">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.id} className="rs-table__row">
                      <td className="rs-table__td rs-table__td--name">{r.run_name ?? "—"}</td>
                      <td className="rs-table__td">{r.model_type ?? "—"}</td>
                      <td className="rs-table__td rs-table__td--mono">{pct(r.auroc)}</td>
                      <td className="rs-table__td rs-table__td--mono">{pct(r.auprc)}</td>
                      <td className="rs-table__td rs-table__td--mono">{pct(r.sensitivity)}</td>
                      <td className="rs-table__td rs-table__td--mono">{pct(r.specificity)}</td>
                      <td className="rs-table__td rs-table__td--mono">{pct(r.f1_score)}</td>
                      <td className="rs-table__td rs-table__td--muted">
                        {new Date(r.ran_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
