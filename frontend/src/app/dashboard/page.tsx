/**
 * Ward Bedside Monitor
 * --------------------
 * Replaces the generic admin dashboard with a clinical monitor layout:
 * dark palette, one tile per ICU bed with schematic ECG/SpO₂ sweeps, large
 * numeric vitals, a risk gauge, and a top status strip.
 */
"use client";

import { CSSProperties, useEffect, useState } from "react";
import { api, Patient, DashboardSummary } from "@/lib/api";
import { BedTile } from "@/components/BedTile";
import { StatusStrip } from "@/components/StatusStrip";
import { RefreshCw, Search } from "lucide-react";
import { cn } from "@/lib/utils";

const COLORS = {
  total: "#3ad6e0",
  critical: "#ff4d55",
  high: "#fb7d21",
  medium: "#f2b632",
  low: "#3be477",
};

export default function WardMonitor() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");

  async function load() {
    setLoading(true);
    try {
      const [p, s] = await Promise.all([api.patients.list(), api.patients.dashboard()]);
      setPatients(p);
      setSummary(s);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // Keep the bedside monitor fresh without a manual refresh.
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, []);

  const filtered = patients.filter((p) => {
    const matchSearch = !search || p.patient_id.toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === "all" || p.latest_risk_level === filter;
    return matchSearch && matchFilter;
  });

  const ORDER = ["critical", "high", "medium", "low"];
  filtered.sort(
    (a, b) =>
      ORDER.indexOf(a.latest_risk_level ?? "low") - ORDER.indexOf(b.latest_risk_level ?? "low")
  );

  const ward = patients[0]?.ward ?? "ICU-A";

  return (
    <div className="bedside">
      <StatusStrip
        ward={ward}
        alarmCount={summary?.unacknowledged_alerts ?? 0}
        criticalCount={summary?.critical_count ?? 0}
      />

      <div className="monitor-page">
        <div className="monitor-head">
          <div>
            <h1 className="monitor-title">Ward Bedside Monitor</h1>
            <p className="monitor-sub">
              Decision support, not diagnosis · sepsis risk refreshed every 30s
            </p>
          </div>
          <button type="button" onClick={load} className="monitor-btn">
            <RefreshCw size={14} className={cn(loading && "animate-spin")} aria-hidden="true" />
            Refresh
          </button>
        </div>

        {summary && (
          <div className="monitor-stats">
            {[
              { label: "Beds", value: summary.total_patients, color: COLORS.total },
              { label: "Critical", value: summary.critical_count, color: COLORS.critical },
              { label: "High", value: summary.high_risk_count, color: COLORS.high },
              { label: "Medium", value: summary.medium_risk_count, color: COLORS.medium },
              { label: "Low", value: summary.low_risk_count, color: COLORS.low },
            ].map((s) => (
              <div
                key={s.label}
                className="monitor-stat"
                style={{ "--stat": s.color } as CSSProperties}
              >
                <div className="monitor-stat__label">{s.label}</div>
                <div className="monitor-stat__value">{s.value}</div>
              </div>
            ))}
          </div>
        )}

        <div className="monitor-toolbar">
          <div className="monitor-search">
            <Search aria-hidden="true" />
            <input
              type="search"
              placeholder="Search bed / patient ID…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search patients"
            />
          </div>
          <div className="monitor-filter" role="group" aria-label="Filter by risk level">
            {["all", "critical", "high", "medium", "low"].map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setFilter(f)}
                className={cn(filter === f && "is-active")}
                aria-pressed={filter === f}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {loading && patients.length === 0 ? (
          <div className="bed-grid" aria-busy="true">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="monitor-empty">
                Loading bed…
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="monitor-empty">
            No beds match this search or filter.
          </div>
        ) : (
          <div className="bed-grid">
            {filtered.map((p) => (
              <BedTile key={p.patient_id} patient={p} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
