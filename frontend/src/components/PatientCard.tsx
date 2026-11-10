import Link from "next/link";
import { Patient } from "@/lib/api";
import { RiskBadge } from "./RiskBadge";
import { cn } from "@/lib/utils";
import { User, Clock } from "lucide-react";

const BAR: Record<string, string> = {
  critical: "risk-bar__fill--critical",
  high:     "risk-bar__fill--high",
  medium:   "risk-bar__fill--medium",
  low:      "risk-bar__fill--low",
};

export function PatientCard({ patient }: { patient: Patient }) {
  const level = patient.latest_risk_level ?? "low";

  return (
    <Link href={`/patient/${patient.patient_id}`} className="patient-card">
      <div className="patient-card__head">
        <div className="patient-card__id-group">
          <div className="patient-card__avatar">
            <User className="h-4 w-4" />
          </div>
          <div>
            <p className="patient-card__id">{patient.patient_id}</p>
            <p className="patient-card__meta">
              {patient.age ? `${patient.age}y` : "—"} ·{" "}
              {patient.gender === 1 ? "M" : patient.gender === 0 ? "F" : "—"}
            </p>
          </div>
        </div>
        <RiskBadge level={patient.latest_risk_level} score={patient.latest_risk_score} size="sm" />
      </div>

      <div className="patient-card__foot">
        <span className="patient-card__stat">
          <Clock className="h-3 w-3" />
          {patient.icu_los != null ? `${patient.icu_los}h in ICU` : "—"}
        </span>
        <span>{patient.ward}</span>
      </div>

      {patient.latest_risk_score != null && (
        <div className="risk-bar">
          <div
            className={cn("risk-bar__fill", BAR[level] ?? "risk-bar__fill--low")}
            style={{ width: `${(patient.latest_risk_score * 100).toFixed(0)}%` }}
          />
        </div>
      )}
    </Link>
  );
}
