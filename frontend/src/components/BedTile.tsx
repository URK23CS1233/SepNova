/**
 * BedTile — one ICU bed in the bedside monitor. Shows schematic ECG/SpO2 sweeps,
 * large numeric vitals from the latest recorded hour, and a risk gauge.
 */
import Link from "next/link";
import { Patient } from "@/lib/api";
import { Waveform } from "./Waveform";
import { RiskGauge } from "./RiskGauge";
import { RiskLevelChip } from "./RiskLevelChip";

function num(v: number | undefined, digits = 0) {
  return v == null ? "—" : v.toFixed(digits);
}

export function BedTile({ patient }: { patient: Patient }) {
  const level = patient.latest_risk_level ?? "low";
  const v = patient.latest_vitals;
  const seed = patient.patient_id.split("").reduce((a, c) => a + c.charCodeAt(0), 0);

  return (
    <Link
      href={`/patient/${patient.patient_id}`}
      className={`bed-tile bed-tile--${level}`}
      aria-label={`Bed ${patient.patient_id}, risk ${level}`}
    >
      <div className="bed-tile__head">
        <div>
          <p className="bed-tile__id">{patient.patient_id}</p>
          <p className="bed-tile__meta">
            {patient.age ? `${patient.age}y` : "—"} ·{" "}
            {patient.gender === 1 ? "M" : patient.gender === 0 ? "F" : "—"} · {patient.ward}
          </p>
        </div>
        <RiskLevelChip level={level} />
      </div>

      <div className="wave-row">
        <Waveform kind="ecg" label="ECG · schematic" value={v?.hr} unit="bpm" seed={seed} />
        <Waveform kind="spo2" label="SpO₂ pleth" value={v?.o2sat} unit="%" seed={seed + 3} />
      </div>

      <div className="vital-grid">
        <div className="vital">
          <div className="vital__label">HR</div>
          <div className="vital__value">
            {num(v?.hr)}<span className="vital__unit">bpm</span>
          </div>
        </div>
        <div className="vital">
          <div className="vital__label">SpO₂</div>
          <div className="vital__value">
            {num(v?.o2sat)}<span className="vital__unit">%</span>
          </div>
        </div>
        <div className="vital">
          <div className="vital__label">MAP</div>
          <div className="vital__value">
            {num(v?.map)}<span className="vital__unit">mmHg</span>
          </div>
        </div>
        <div className="vital">
          <div className="vital__label">RR</div>
          <div className="vital__value">
            {num(v?.resp)}<span className="vital__unit">/min</span>
          </div>
        </div>
        <div className="vital">
          <div className="vital__label">Temp</div>
          <div className="vital__value">
            {num(v?.temp, 1)}<span className="vital__unit">°C</span>
          </div>
        </div>
        <div className="vital">
          <div className="vital__label">SBP</div>
          <div className="vital__value">
            {num(v?.sbp)}<span className="vital__unit">mmHg</span>
          </div>
        </div>
      </div>

      <div className="risk-area">
        <RiskGauge score={patient.latest_risk_score} level={level} />
        <div style={{ textAlign: "right" }}>
          <RiskLevelChip level={level} />
          <p className="bed-tile__meta" style={{ marginTop: 5 }}>
            {patient.icu_los != null ? `${patient.icu_los}h in ICU` : "LOS unknown"}
          </p>
        </div>
      </div>
    </Link>
  );
}
