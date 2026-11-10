"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";
import { api, Patient, Vitals, Prediction } from "@/lib/api";
import { RiskBadge } from "@/components/RiskBadge";
import { StatCard } from "@/components/StatCard";
import { ArrowLeft, Activity, FlaskConical, TrendingUp } from "lucide-react";
import { pct, score, timeAgo, cn } from "@/lib/utils";

export default function PatientDetail() {
  const { id } = useParams<{ id: string }>();
  const [patient, setPatient]         = useState<Patient | null>(null);
  const [vitals, setVitals]           = useState<Vitals[]>([]);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [tab, setTab]                 = useState<"vitals" | "risk">("vitals");
  const [loading, setLoading]         = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [p, v, pred] = await Promise.all([
          api.patients.get(id),
          api.patients.vitals(id),
          api.patients.predictions(id),
        ]);
        setPatient(p);
        setVitals(v);
        setPredictions(pred);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) {
    return (
      <div className="pt-loading">
        <div className="pt-skeleton pt-skeleton--title" />
        <div className="pt-skeleton pt-skeleton--block" />
      </div>
    );
  }
  if (!patient) return <div className="pt-notfound">Patient not found.</div>;

  const latestPred = predictions[0];
  const riskHistory = [...predictions].reverse().map((p) => ({
    time: new Date(p.predicted_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    score: +(p.risk_score * 100).toFixed(1),
    xgb:  +(p.xgb_score  * 100).toFixed(1),
    lgb:  +(p.lgb_score  * 100).toFixed(1),
  }));

  return (
    <div className="page">
      {/* Back */}
      <Link href="/" className="pt-back">
        <ArrowLeft className="h-4 w-4" /> Back to Ward
      </Link>

      {/* Patient header */}
      <div className="pt-header">
        <div>
          <h1 className="pt-title">{patient.patient_id}</h1>
          <p className="pt-meta">
            {patient.age ? `Age ${patient.age}` : "—"} ·{" "}
            {patient.gender === 1 ? "Male" : patient.gender === 0 ? "Female" : "—"} ·{" "}
            {patient.ward} · ICU {patient.icu_los ?? "?"}h
          </p>
        </div>
        {latestPred && (
          <RiskBadge level={latestPred.risk_level} score={latestPred.risk_score} />
        )}
      </div>

      {/* Stats */}
      {latestPred && (
        <div className="pt-stats">
          <StatCard label="Risk Score" value={pct(latestPred.risk_score)} accent={
            latestPred.risk_level === "critical" ? "red" :
            latestPred.risk_level === "high"     ? "orange" :
            latestPred.risk_level === "medium"   ? "yellow" : "green"
          } />
          <StatCard label="XGBoost" value={pct(latestPred.xgb_score)} accent="blue" />
          <StatCard label="LightGBM" value={pct(latestPred.lgb_score)} accent="blue" />
          <StatCard
            label="Last Predicted"
            value={timeAgo(latestPred.predicted_at)}
            sub={latestPred.model_version}
            accent="blue"
          />
        </div>
      )}

      {/* Tabs */}
      <div className="pt-tabs">
        {(["vitals", "risk"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn("pt-tab", tab === t && "pt-tab--active")}
          >
            {t === "vitals" ? (
              <span className="pt-tab__inner"><Activity className="h-4 w-4" />Vitals</span>
            ) : (
              <span className="pt-tab__inner"><TrendingUp className="h-4 w-4" />Risk History</span>
            )}
          </button>
        ))}
      </div>

      {tab === "vitals" && (
        <div className="pt-charts">
          {/* HR + O2Sat */}
          <div className="pt-chart-card">
            <h3 className="pt-chart-title">Heart Rate & O₂ Saturation</h3>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={vitals}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="hour" label={{ value: "ICU Hour", position: "insideBottom", offset: -5 }} tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="hr"    stroke="#0ea5e9" name="HR (bpm)"  dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="o2sat" stroke="#22c55e" name="O₂Sat (%)" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* BP */}
          <div className="pt-chart-card">
            <h3 className="pt-chart-title">Blood Pressure</h3>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={vitals}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="hour" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="sbp" stroke="#ef4444" name="SBP" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="map" stroke="#f59e0b" name="MAP" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="dbp" stroke="#8b5cf6" name="DBP" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Resp + Temp */}
          <div className="pt-chart-card">
            <h3 className="pt-chart-title">Respiratory Rate & Temperature</h3>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={vitals}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="hour" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="resp" stroke="#06b6d4" name="Resp (bpm)" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="temp" stroke="#f97316" name="Temp (°C)"  dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {tab === "risk" && (
        <div className="pt-chart-card">
          <h3 className="pt-chart-title">Sepsis Risk Score Over Time</h3>
          {riskHistory.length === 0 ? (
            <p className="pt-chart-empty">No prediction history yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={riskHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="time" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => `${v}%`} />
                <Legend />
                <Line type="monotone" dataKey="score" stroke="#ef4444" name="Ensemble" strokeWidth={2.5} dot={false} />
                <Line type="monotone" dataKey="xgb"   stroke="#0ea5e9" name="XGBoost"  strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                <Line type="monotone" dataKey="lgb"   stroke="#22c55e" name="LightGBM" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      )}
    </div>
  );
}
