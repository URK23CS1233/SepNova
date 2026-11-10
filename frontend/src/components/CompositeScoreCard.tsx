"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface SNSResult {
  sns_score: number;
  sns_level: "low" | "medium" | "high" | "critical";
  sns_ml_component: number;
  sns_qsofa_component: number;
  sns_velocity_component: number;
  ml_prob: number;
  qsofa_score: number;
  sofa_velocity: number;
  sofa_total: number | null;
  alpha: number;
  beta: number;
  gamma: number;
}

const LEVEL_BADGE: Record<string, string> = {
  critical: "cs-badge--critical",
  high:     "cs-badge--high",
  medium:   "cs-badge--medium",
  low:      "cs-badge--low",
};

const LEVEL_BAR: Record<string, string> = {
  critical: "cs-bar__fill--critical",
  high:     "cs-bar__fill--high",
  medium:   "cs-bar__fill--medium",
  low:      "cs-bar__fill--low",
};

interface Props {
  patientId: string;
}

export default function CompositeScoreCard({ patientId }: Props) {
  const [data, setData] = useState<SNSResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!patientId) return;
    setLoading(true);
    api
      .get<SNSResult>(`/api/v1/insights/composite/${patientId}`)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [patientId]);

  if (loading) return (
    <div className="cs-skeleton" />
  );
  if (!data) return null;

  const pct = Math.round(data.sns_score * 100);
  const barW = Math.round(data.sns_score * 100);

  return (
    <div className="cs-card">
      {/* Header */}
      <div className="cs-header">
        <div>
          <p className="cs-label">
            SepNova Composite Score
          </p>
          <p className="cs-value">
            {pct}<span className="cs-value__unit">%</span>
          </p>
        </div>
        <span className={cn("cs-badge", LEVEL_BADGE[data.sns_level])}>
          {data.sns_level}
        </span>
      </div>

      {/* Score bar */}
      <div className="cs-bar">
        <div
          className={cn("cs-bar__fill", LEVEL_BAR[data.sns_level])}
          style={{ width: `${barW}%` }}
        />
      </div>

      {/* Breakdown */}
      <div className="cs-breakdown">
        <ComponentRow
          label={`ML Ensemble (α=${data.alpha})`}
          val={data.ml_prob}
          component={data.sns_ml_component}
          fill="cs-row__fill--ml"
        />
        <ComponentRow
          label={`qSOFA score ${data.qsofa_score}/3 (β=${data.beta})`}
          val={data.qsofa_score / 3}
          component={data.sns_qsofa_component}
          fill="cs-row__fill--qsofa"
        />
        <ComponentRow
          label={`SOFA velocity (γ=${data.gamma})`}
          val={data.sofa_velocity}
          component={data.sns_velocity_component}
          fill="cs-row__fill--sofa"
        />
      </div>

      {data.sofa_total !== null && (
        <p className="cs-note">
          Latest SOFA total: <span className="cs-note__strong">{data.sofa_total}</span>
          {data.sofa_total >= 2 && (
            <span className="cs-note__warn">⚠ Organ dysfunction</span>
          )}
        </p>
      )}

      <p className="cs-formula">
        Formula: SNS = {data.alpha}×P<sub>ML</sub> + {data.beta}×P<sub>qSOFA</sub> + {data.gamma}×V<sub>SOFA</sub>
      </p>
    </div>
  );
}

function ComponentRow({
  label,
  val,
  component,
  fill,
}: {
  label: string;
  val: number;
  component: number;
  fill: string;
}) {
  return (
    <div className="cs-row">
      <div className="cs-row__main">
        <p className="cs-row__label">{label}</p>
        <div className="cs-row__track">
          <div className={cn("cs-row__fill", fill)} style={{ width: `${Math.round(val * 100)}%` }} />
        </div>
      </div>
      <span className="cs-row__val">
        +{(component * 100).toFixed(1)}%
      </span>
    </div>
  );
}
