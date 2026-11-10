"use client";
import { useEffect, useState } from "react";
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from "recharts";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Subgroup {
  subgroup_type:  "age" | "gender";
  subgroup_label: string;
  n_total:        number;
  n_sepsis:       number;
  auroc:          number;
  auprc:          number;
  below_threshold: boolean;
}

interface FairnessData {
  subgroups:         Subgroup[];
  overall_auroc:     number | null;
  max_subgroup_gap:  number;
  fairness_passed:   boolean;
  flagged_subgroups: string[];
  message?:          string;
  criteria: {
    min_auroc_per_subgroup: number;
    max_inter_subgroup_gap: number;
  };
}

export default function FairnessChart() {
  const [data, setData] = useState<FairnessData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<FairnessData>("/api/v1/insights/fairness")
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="fr-card--skeleton" />
  );
  if (!data) return null;
  if (data.message) return (
    <div className="fr-card">
      <p className="fr-eyebrow mb-2">Fairness Audit</p>
      <p className="text-sm text-slate-500">{data.message}</p>
    </div>
  );

  const radarData = data.subgroups.map((sg) => ({
    label: sg.subgroup_label.replace("Age ", ""),
    auroc: sg.auroc,
    min:   data.criteria.min_auroc_per_subgroup,
  }));

  return (
    <div className="fr-card">
      {/* Header */}
      <div className="fr-header">
        <div>
          <p className="fr-eyebrow">
            Demographic Fairness Audit
          </p>
          {data.overall_auroc && (
            <p className="fr-overall">
              Overall AUROC: <strong>{data.overall_auroc}</strong>
              &nbsp;·&nbsp; Max gap: <strong>{data.max_subgroup_gap}</strong>
            </p>
          )}
        </div>
        <span className={cn(
          "fr-status",
          data.fairness_passed ? "fr-status--ok" : "fr-status--fail"
        )}>
          {data.fairness_passed ? "✓ Fairness OK" : "⚠ Disparity Detected"}
        </span>
      </div>

      {/* Flagged warning */}
      {data.flagged_subgroups.length > 0 && (
        <div className="fr-flagged">
          <strong>Flagged subgroups</strong> (AUROC &lt; {data.criteria.min_auroc_per_subgroup}):{" "}
          {data.flagged_subgroups.join(", ")}
        </div>
      )}

      {/* Radar */}
      <div className="fr-chart">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={radarData}>
            <PolarGrid stroke="#e5e7eb" />
            <PolarAngleAxis dataKey="label" tick={{ fontSize: 11 }} />
            <Tooltip
              formatter={(v: number) => v.toFixed(4)}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            <Radar
              name="Min threshold"
              dataKey="min"
              stroke="#e5e7eb"
              fill="#f3f4f6"
              fillOpacity={0.5}
            />
            <Radar
              name="AUROC"
              dataKey="auroc"
              stroke="#3b82f6"
              fill="#3b82f6"
              fillOpacity={0.25}
              dot={{ r: 3, fill: "#3b82f6" }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Subgroup table */}
      <div className="fr-table-wrap">
        <table className="fr-table">
          <thead>
            <tr className="fr-table__head-row">
              <th>Subgroup</th>
              <th className="fr-table__th--num">N</th>
              <th className="fr-table__th--num">Sepsis</th>
              <th className="fr-table__th--num">AUROC</th>
              <th className="fr-table__th--num">AUPRC</th>
            </tr>
          </thead>
          <tbody>
            {data.subgroups.map((sg) => (
              <tr
                key={sg.subgroup_label}
                className={cn("fr-row", sg.below_threshold && "fr-row--flagged")}
              >
                <td className="fr-cell--name">
                  {sg.below_threshold && <span className="fr-cell__warn">⚠</span>}
                  {sg.subgroup_label}
                </td>
                <td className="fr-cell--num">{sg.n_total}</td>
                <td className="fr-cell--num">{sg.n_sepsis}</td>
                <td className="fr-cell--auroc">{sg.auroc.toFixed(4)}</td>
                <td className="fr-cell--num">{sg.auprc.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="fr-criteria">
        Fairness criteria: AUROC ≥ {data.criteria.min_auroc_per_subgroup} per subgroup, max inter-group gap ≤ {data.criteria.max_inter_subgroup_gap}
      </p>
    </div>
  );
}
