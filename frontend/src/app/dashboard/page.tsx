"use client";
import { useEffect, useState } from "react";
import { api, Patient, DashboardSummary } from "@/lib/api";
import { PatientCard } from "@/components/PatientCard";
import { StatCard } from "@/components/StatCard";
import { RefreshCw, Search } from "lucide-react";
import { cn } from "@/lib/utils";

export default function WardOverview() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [summary, setSummary]   = useState<DashboardSummary | null>(null);
  const [loading, setLoading]   = useState(true);
  const [search, setSearch]     = useState("");
  const [filter, setFilter]     = useState<string>("all");

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

  useEffect(() => { load(); }, []);

  const filtered = patients.filter((p) => {
    const matchSearch =
      !search || p.patient_id.toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === "all" || p.latest_risk_level === filter;
    return matchSearch && matchFilter;
  });

  const ORDER = ["critical", "high", "medium", "low"];
  filtered.sort((a, b) =>
    ORDER.indexOf(a.latest_risk_level ?? "low") -
    ORDER.indexOf(b.latest_risk_level ?? "low")
  );

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Ward Overview</h1>
          <p className="page-subtitle">
            Real-time sepsis risk monitoring — all active ICU patients
          </p>
        </div>
        <button onClick={load} className="btn btn--ghost">
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {summary && (
        <div className="stats-grid">
          <StatCard label="Total Patients" value={summary.total_patients} accent="blue" />
          <StatCard label="Critical" value={summary.critical_count} accent="red" />
          <StatCard label="High Risk" value={summary.high_risk_count} accent="orange" />
          <StatCard label="Medium Risk" value={summary.medium_risk_count} accent="yellow" />
          <StatCard label="Low Risk" value={summary.low_risk_count} accent="green" />
          <StatCard
            label="Open Alerts"
            value={summary.unacknowledged_alerts}
            sub={summary.latest_model_auroc ? `AUROC ${summary.latest_model_auroc.toFixed(3)}` : undefined}
            accent="blue"
          />
        </div>
      )}

      <div className="toolbar">
        <div className="search">
          <Search className="search__icon" />
          <input
            type="text"
            placeholder="Search patient ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="search__input"
          />
        </div>
        <div className="filter-group">
          {["all", "critical", "high", "medium", "low"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn("filter-pill", filter === f && "filter-pill--active")}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="patient-grid">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="skeleton-card" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <p className="empty-state__title">No patients found</p>
          <p className="empty-state__hint">Try adjusting your search or filter.</p>
        </div>
      ) : (
        <div className="patient-grid">
          {filtered.map((p) => (
            <PatientCard key={p.patient_id} patient={p} />
          ))}
        </div>
      )}
    </div>
  );
}
