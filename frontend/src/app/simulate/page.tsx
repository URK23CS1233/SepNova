/**
 * Sepsis Simulation (/simulate)
 * -----------------------------
 * Replays a purely synthetic ICU trajectory hour by hour. Left: bedside
 * waveforms and vitals. Right: model risk timeline against the true onset line,
 * lead time and the top SHAP drivers. Every surface is marked SIMULATED.
 */
"use client";

import { CSSProperties, useCallback, useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle, FlaskConical, Pause, Play, RotateCcw, SkipForward } from "lucide-react";
import { api, SimulationResult } from "@/lib/api";
import { StatusStrip } from "@/components/StatusStrip";
import { Waveform } from "@/components/Waveform";
import { RiskGauge } from "@/components/RiskGauge";
import { RiskLevelChip } from "@/components/RiskLevelChip";

export default function SimulatePage() {
  const [onset, setOnset] = useState(12);
  const [total, setTotal] = useState(30);
  const [severity, setSeverity] = useState(0.8);
  const [noise, setNoise] = useState(0.35);
  const [speed, setSpeed] = useState(700);

  const [result, setResult] = useState<SimulationResult | null>(null);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.simulate({
        onset_hour: onset,
        total_hours: total,
        severity,
        noise,
        seed: 7,
        ramp_hours: 8,
      });
      setResult(res);
      setIndex(0);
      setPlaying(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setLoading(false);
    }
  }, [onset, total, severity, noise]);

  // Playback clock. Respects the speed slider.
  useEffect(() => {
    if (!playing || !result) return;
    const timer = window.setInterval(() => {
      setIndex((i) => {
        if (i >= result.hours.length - 1) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, speed);
    return () => window.clearInterval(timer);
  }, [playing, speed, result]);

  const current = result?.hours[index];

  const chartData = useMemo(
    () =>
      (result?.hours ?? []).map((h) => ({
        hour: h.hour,
        risk: +(h.risk_score * 100).toFixed(1),
        pre: h.pre_onset,
      })),
    [result]
  );

  const maxShap = Math.max(
    0.0001,
    ...((current?.top_features ?? []).map((f) => Math.abs(f.shap)) as number[])
  );

  const RISK_HEX: Record<string, string> = {
    low: "#3be477",
    medium: "#f2b632",
    high: "#fb7d21",
    critical: "#ff4d55",
  };

  const leadLabel = (() => {
    if (!result) return null;
    if (result.lead_time_hours == null) return "Never flagged before onset";
    if (result.lead_time_hours >= 0) return `${result.lead_time_hours}h before true onset`;
    return `Flagged ${Math.abs(result.lead_time_hours)}h after onset`;
  })();

  return (
    <div className="bedside" style={{ "--risk": "#f2b632" } as CSSProperties}>
      <StatusStrip ward="SIMULATION" alarmCount={0} simulated />

      <div className="monitor-page">
        <div className="sim-banner" role="status">
          <AlertTriangle size={15} aria-hidden="true" />
          Simulated data — synthetic patient, not a real person. Demonstration only.
        </div>

        <div className="monitor-head">
          <div>
            <h1 className="monitor-title">Sepsis Simulation</h1>
            <p className="monitor-sub">
              Replay a synthetic ICU stay and compare model risk against true onset
            </p>
          </div>
          <button type="button" className="monitor-btn" onClick={run} disabled={loading}>
            <FlaskConical size={14} aria-hidden="true" />
            {loading ? "Generating…" : result ? "Re-run" : "Generate"}
          </button>
        </div>

        <div className="sim-controls">
          <div className="sim-field">
            <label htmlFor="onset">
              Onset hour <strong>{onset}h</strong>
            </label>
            <input
              id="onset"
              type="range"
              min={2}
              max={Math.max(2, total - 4)}
              value={onset}
              onChange={(e) => setOnset(Number(e.target.value))}
            />
          </div>

          <div className="sim-field">
            <label htmlFor="total">
              Duration <strong>{total}h</strong>
            </label>
            <input
              id="total"
              type="range"
              min={12}
              max={48}
              value={total}
              onChange={(e) => {
                const v = Number(e.target.value);
                setTotal(v);
                if (onset > v - 4) setOnset(Math.max(2, v - 4));
              }}
            />
          </div>

          <div className="sim-field">
            <label htmlFor="severity">
              Severity <strong>{severity.toFixed(2)}</strong>
            </label>
            <input
              id="severity"
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={severity}
              onChange={(e) => setSeverity(Number(e.target.value))}
            />
          </div>

          <div className="sim-field">
            <label htmlFor="noise">
              Noise <strong>{noise.toFixed(2)}</strong>
            </label>
            <input
              id="noise"
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={noise}
              onChange={(e) => setNoise(Number(e.target.value))}
            />
          </div>

          <div className="sim-field">
            <label htmlFor="speed">
              Playback speed <strong>{(1000 / speed).toFixed(1)}×</strong>
            </label>
            <input
              id="speed"
              type="range"
              min={200}
              max={2000}
              step={100}
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
            />
          </div>
        </div>

        {error && (
          <div className="monitor-empty" role="alert">
            {error}. The model artifact may be missing or the API is unavailable.
          </div>
        )}

        {result && current && (
          <>
            <div className="sim-actions" style={{ marginBottom: 12 }}>
              <button
                type="button"
                className="monitor-btn monitor-btn--active"
                onClick={() => setPlaying((p) => !p)}
              >
                {playing ? <Pause size={14} /> : <Play size={14} />}
                {playing ? "Pause" : "Play"}
              </button>
              <button
                type="button"
                className="monitor-btn"
                onClick={() => {
                  setPlaying(false);
                  setIndex((i) => Math.min(i + 1, result.hours.length - 1));
                }}
              >
                <SkipForward size={14} />
                Step
              </button>
              <button
                type="button"
                className="monitor-btn"
                onClick={() => {
                  setPlaying(false);
                  setIndex(0);
                }}
              >
                <RotateCcw size={14} />
                Reset
              </button>
              <div className="status-strip__item" style={{ marginLeft: "auto" }}>
                Hour <strong>{current.hour}</strong> / {result.hours.length}
              </div>
            </div>

            <div
              className="sim-layout"
              style={{ "--risk": RISK_HEX[current.risk_level] ?? RISK_HEX.low } as CSSProperties}
            >
              {/* Left: waveforms + vitals + organ scores */}
              <div className="monitor-panel">
                <div className="monitor-panel__title">
                  <span>Bedside waveforms · SIMULATED</span>
                  <RiskLevelChip level={current.risk_level} />
                </div>

                <div className="wave-row">
                  <Waveform kind="ecg" label="ECG · schematic" value={current.vitals.HR} unit="bpm" seed={current.hour} />
                  <Waveform kind="spo2" label="SpO₂ pleth" value={current.vitals.O2SAT} unit="%" seed={current.hour + 5} />
                </div>

                <div className="vital-grid">
                  {[
                    ["HR", current.vitals.HR, "bpm"],
                    ["MAP", current.vitals.MAP, "mmHg"],
                    ["RR", current.vitals.RESP, "/min"],
                    ["Temp", current.vitals.TEMP, "°C"],
                    ["SpO₂", current.vitals.O2SAT, "%"],
                    ["GCS", current.vitals.GCS, "pts"],
                    ["Lactate", current.labs.Lactate, "mmol/L"],
                    ["WBC", current.labs.WBC, "K/µL"],
                    ["Creatinine", current.labs.Creatinine, "mg/dL"],
                  ].map(([label, value, unit]) => (
                    <div className="vital" key={String(label)}>
                      <div className="vital__label">{label}</div>
                      <div className="vital__value">
                        {typeof value === "number" ? value.toFixed(value >= 100 ? 0 : 1) : "—"}
                        <span className="vital__unit">{unit}</span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="score-row" style={{ marginTop: 12 }}>
                  <div className="score-box" style={{ "--c": current.sofa.sofa_total >= 2 ? "#fb7d21" : "#3be477" } as CSSProperties}>
                    <div className="score-box__label">SOFA</div>
                    <div className="score-box__value">{current.sofa.sofa_total}</div>
                    <div className="score-box__hint">
                      {current.sofa.organ_dysfunction ? "organ dysfunction" : "no dysfunction"}
                    </div>
                  </div>
                  <div className="score-box" style={{ "--c": current.qsofa.qsofa_total >= 2 ? "#fb7d21" : "#3be477" } as CSSProperties}>
                    <div className="score-box__label">qSOFA</div>
                    <div className="score-box__value">{current.qsofa.qsofa_total}</div>
                    <div className="score-box__hint">
                      {current.qsofa.high_risk_qsofa ? "high risk" : "low risk"}
                    </div>
                  </div>
                  <div className="score-box" style={{ "--c": current.sirs.sirs_positive ? "#f2b632" : "#3be477" } as CSSProperties}>
                    <div className="score-box__label">SIRS</div>
                    <div className="score-box__value">{current.sirs.sirs_count}</div>
                    <div className="score-box__hint">
                      {current.sirs.sirs_positive ? "SIRS positive" : "SIRS negative"}
                    </div>
                  </div>
                </div>

                <div className="risk-area">
                  <RiskGauge score={current.risk_score} level={current.risk_level} />
                  <div style={{ textAlign: "right" }}>
                    <div className="lead-badge" style={{ "--risk": leadLabel?.includes("before") ? "#3be477" : "#f2b632" } as CSSProperties}>
                      {leadLabel ?? "—"}
                    </div>
                    <p className="bed-tile__meta" style={{ marginTop: 5 }}>
                      Confidence {(current.confidence * 100).toFixed(0)}% ·{" "}
                      {current.data_complete ? "complete inputs" : `missing ${current.missing_features.join(", ")}`}
                    </p>
                  </div>
                </div>
              </div>

              {/* Right: risk timeline + drivers */}
              <div className="monitor-panel">
                <div className="monitor-panel__title">
                  <span>Risk timeline vs true onset</span>
                  <span style={{ color: "#ff4d55" }}>onset {result.onset_hour}h</span>
                </div>

                <ResponsiveContainer width="100%" height={230}>
                  <LineChart data={chartData} margin={{ top: 8, right: 10, left: -16, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#16262c" />
                    <XAxis dataKey="hour" tick={{ fill: "#7e969f", fontSize: 10 }} stroke="#1b2b32" />
                    <YAxis domain={[0, 100]} tick={{ fill: "#7e969f", fontSize: 10 }} stroke="#1b2b32" />
                    <Tooltip
                      contentStyle={{ background: "#0a1114", border: "1px solid #1b2b32", color: "#d9e8ec", fontSize: 12 }}
                      formatter={(v) => [`${v}%`, "Risk"]}
                      labelFormatter={(l) => `Hour ${l}`}
                    />
                    <ReferenceLine
                      x={result.onset_hour}
                      stroke="#ff4d55"
                      strokeDasharray="5 3"
                      label={{ value: "true onset", fill: "#ff4d55", fontSize: 10, position: "insideTopRight" }}
                    />
                    <ReferenceLine
                      y={+(result.threshold * 100).toFixed(1)}
                      stroke="#f2b632"
                      strokeDasharray="2 4"
                      label={{ value: "alert threshold", fill: "#f2b632", fontSize: 9, position: "insideBottomRight" }}
                    />
                    <Line type="monotone" dataKey="risk" stroke="#3be477" strokeWidth={2} dot={false} isAnimationActive={false} />
                    <ReferenceDot x={current.hour} y={+(current.risk_score * 100).toFixed(1)} r={4} fill="#3be477" stroke="#04070a" />
                  </LineChart>
                </ResponsiveContainer>

                <div className="monitor-panel__title" style={{ marginTop: 12 }}>
                  <span>Top SHAP drivers (this hour)</span>
                  <span>{current.explanation_method}</span>
                </div>

                <div className="driver-list">
                  {current.top_features.length === 0 ? (
                    <div className="monitor-empty" style={{ padding: 18 }}>
                      SHAP explanation unavailable.
                    </div>
                  ) : (
                    current.top_features.map((f) => (
                      <div className="driver" key={f.feature}>
                        <div>
                          <div className="driver__label">{f.label}</div>
                          <div className="driver__value">value {f.value.toFixed(2)}</div>
                          <div className="driver__bar">
                            <div
                              className="driver__fill"
                              style={{ width: `${(Math.abs(f.shap) / maxShap) * 100}%` }}
                            />
                          </div>
                        </div>
                        <div className="driver__shap">
                          {f.shap >= 0 ? "+" : ""}
                          {f.shap.toFixed(3)}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </>
        )}

        {!result && !loading && !error && (
          <div className="monitor-empty">
            Set the onset hour, severity and noise, then press <strong>Generate</strong> to replay a
            synthetic ICU stay.
          </div>
        )}
      </div>
    </div>
  );
}
