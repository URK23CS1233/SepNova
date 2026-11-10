"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Contribution {
  feature:     string;
  label:       string;
  unit:        string;
  current_val: number;
  importance:  number;
  direction:   string;
}

interface Counterfactual {
  label:          string;
  unit:           string;
  current_val:    number;
  target_val:     number;
  prob_before:    number;
  prob_after:     number;
  risk_reduction: number;
  narrative:      string;
}

interface ExplanationData {
  patient_id:           string;
  risk_level:           string;
  message?:             string;
  feature_contributions: Contribution[];
  counterfactuals:       Counterfactual[];
}

const DIRECTION_ICON: Record<string, string> = {
  decrease:   "↓",
  increase:   "↑",
  normalize:  "↔",
};

interface Props {
  patientId: string;
}

export default function ExplanationPanel({ patientId }: Props) {
  const [data, setData] = useState<ExplanationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"contributions" | "counterfactuals">("contributions");

  useEffect(() => {
    if (!patientId) return;
    setLoading(true);
    api
      .get<ExplanationData>(`/api/v1/insights/explain/${patientId}`)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [patientId]);

  if (loading) return (
    <div className="ex-skeleton" />
  );
  if (!data) return null;
  if (data.message) return (
    <div className="ex-panel">
      <p className="ex-eyebrow">
        Clinical Explainability
      </p>
      <p className="ex-message">{data.message}</p>
    </div>
  );

  const maxImp = Math.max(...data.feature_contributions.map(c => Math.abs(c.importance)), 0.001);

  return (
    <div className="ex-panel">
      <p className="ex-eyebrow">
        Clinical Explainability
      </p>

      {/* Tabs */}
      <div className="ex-tabs">
        {(["contributions", "counterfactuals"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn("ex-tab", tab === t && "ex-tab--active")}
          >
            {t === "contributions" ? "Risk Drivers" : "Counterfactuals"}
          </button>
        ))}
      </div>

      {/* Risk Drivers tab */}
      {tab === "contributions" && (
        <div className="ex-drivers">
          {data.feature_contributions.slice(0, 8).map((c) => {
            const barW = Math.abs(c.importance) / maxImp * 100;
            const isRisk = c.importance > 0;
            return (
              <div key={c.feature} className="ex-driver">
                <div className="ex-driver__body">
                  <div className="ex-driver__head">
                    <span className="ex-driver__label">
                      {c.label}
                      <span className="ex-driver__val">{c.current_val} {c.unit}</span>
                    </span>
                    <span className={cn("ex-driver__imp", isRisk ? "ex-driver__imp--risk" : "ex-driver__imp--protective")}>
                      {isRisk ? "+" : ""}{(c.importance * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="ex-driver__track">
                    <div
                      className={cn("ex-driver__fill", isRisk ? "ex-driver__fill--risk" : "ex-driver__fill--protective")}
                      style={{ width: `${barW}%` }}
                    />
                  </div>
                </div>
                <span className="ex-driver__dir">
                  {DIRECTION_ICON[c.direction]}
                </span>
              </div>
            );
          })}
          <p className="ex-legend">
            Red bars = features increasing risk. Green = protective. Arrow shows clinical target direction.
          </p>
        </div>
      )}

      {/* Counterfactuals tab */}
      {tab === "counterfactuals" && (
        <div className="ex-cfs">
          {data.counterfactuals.length === 0 ? (
            <p className="ex-empty">
              No single-feature intervention found that crosses the next risk threshold. Multiple simultaneous changes may be needed.
            </p>
          ) : (
            data.counterfactuals.map((cf, i) => (
              <div
                key={i}
                className="ex-cf"
              >
                <div className="ex-cf__head">
                  <span className="ex-cf__title">
                    {cf.label}
                  </span>
                  <span className="ex-cf__delta">
                    −{(cf.risk_reduction * 100).toFixed(1)}% risk
                  </span>
                </div>
                <p className="ex-cf__narrative">{cf.narrative}</p>
                <div className="ex-cf__shift">
                  <span>
                    <span className="ex-cf__muted">Now: </span>
                    <span className="ex-cf__now">{cf.current_val} {cf.unit}</span>
                  </span>
                  <span className="ex-cf__arrow">→</span>
                  <span>
                    <span className="ex-cf__muted">Target: </span>
                    <span className="ex-cf__target">{cf.target_val} {cf.unit}</span>
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
