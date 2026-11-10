"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface HorizonResult {
  probability: number;
  threshold: number;
  positive: boolean;
  risk_pct: number;
  error?: string;
}

interface HorizonsResponse {
  patient_id: string;
  horizons: Record<"3h" | "6h" | "12h", HorizonResult>;
}

const HORIZON_META = {
  "12h": { label: "12-Hour Advisory",  desc: "Early warning — high lead time",       icon: "🔭", urgency: "low"    },
  "6h":  { label: "6-Hour Warning",    desc: "Balanced — main clinical model",        icon: "⚠️", urgency: "medium" },
  "3h":  { label: "3-Hour Critical",   desc: "Imminent — act now if positive",        icon: "🚨", urgency: "high"   },
};

const URGENCY_CARD: Record<string, string> = {
  high:   "mh-card--high",
  medium: "mh-card--medium",
  low:    "mh-card--low",
};

const POSITIVE_BADGE: Record<string, string> = {
  high:   "mh-badge--high",
  medium: "mh-badge--medium",
  low:    "mh-badge--low",
};

const BAR_FILL: Record<string, string> = {
  high:   "mh-bar__fill--high",
  medium: "mh-bar__fill--medium",
  low:    "mh-bar__fill--low",
};

interface Props {
  patientId: string;
}

export default function MultiHorizonPanel({ patientId }: Props) {
  const [data, setData] = useState<HorizonsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!patientId) return;
    setLoading(true);
    api
      .get<HorizonsResponse>(`/api/v1/insights/horizons/${patientId}`)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [patientId]);

  if (loading) return (
    <div className="mh-skeleton" />
  );
  if (!data) return null;

  return (
    <div className="mh-panel">
      <p className="mh-panel__title">
        Multi-Horizon Sepsis Risk
      </p>

      <div className="mh-grid">
        {(["12h", "6h", "3h"] as const).map((h) => {
          const result = data.horizons[h];
          const meta = HORIZON_META[h];
          if (result.error) {
            return (
              <div key={h} className="mh-card--empty">
                <p className="mh-card__empty-label">{meta.label}</p>
                <p className="mh-card__empty-msg">{result.error}</p>
              </div>
            );
          }
          return (
            <div
              key={h}
              className={cn("mh-card", URGENCY_CARD[meta.urgency])}
            >
              <div className="mh-card__head">
                <span className="mh-card__icon">{meta.icon}</span>
                {result.positive ? (
                  <span className={cn("mh-badge", POSITIVE_BADGE[meta.urgency])}>
                    POSITIVE
                  </span>
                ) : (
                  <span className="mh-badge--neg">
                    negative
                  </span>
                )}
              </div>
              <p className="mh-card__label">{meta.label}</p>
              <p className="mh-card__desc">{meta.desc}</p>
              <div className="mh-value-row">
                <span className="mh-value">
                  {result.risk_pct}<span className="mh-value__unit">%</span>
                </span>
                <span className="mh-threshold">
                  threshold {Math.round(result.threshold * 100)}%
                </span>
              </div>
              <div className="mh-bar">
                <div
                  className={cn("mh-bar__fill", result.positive && BAR_FILL[meta.urgency])}
                  style={{ width: `${result.risk_pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
