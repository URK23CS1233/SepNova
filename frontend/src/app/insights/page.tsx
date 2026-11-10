"use client";
import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { RoleGuard } from "@/components/RoleGuard";
import CompositeScoreCard from "@/components/CompositeScoreCard";
import MultiHorizonPanel from "@/components/MultiHorizonPanel";
import ExplanationPanel from "@/components/ExplanationPanel";
import FairnessChart from "@/components/FairnessChart";

export default function InsightsPage() {
  const { profile } = useAuth();
  const [patientId, setPatientId] = useState("");
  const [activePatient, setActivePatient] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (patientId.trim()) setActivePatient(patientId.trim());
  };

  return (
    <RoleGuard roles={["intensivist", "surgeon", "nurse", "anesthesiologist", "admin"]}>
      <div className="page in-page">
        {/* Page header */}
        <div className="page-header">
          <div>
            <h1 className="page-title">Novel Clinical Insights</h1>
            <p className="page-subtitle">
              SepNova Composite Score · Multi-Horizon Predictions · Counterfactual Explainability · Fairness Audit
            </p>
          </div>
        </div>

        {/* Patient selector */}
        <form onSubmit={handleSubmit} className="in-selector">
          <input
            type="text"
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
            placeholder="Enter Patient ID…"
            className="in-selector__input"
          />
          <button type="submit" className="btn in-selector__btn">
            Analyse
          </button>
        </form>

        {activePatient ? (
          <div className="in-sections">
            {/* Section 1 — Composite Score + Multi-Horizon side by side on larger screens */}
            <div className="in-duo">
              <CompositeScoreCard patientId={activePatient} />
              <MultiHorizonPanel   patientId={activePatient} />
            </div>

            {/* Section 2 — Explanations */}
            <ExplanationPanel patientId={activePatient} />

            {/* Section 3 — Fairness Audit (intensivist / admin only) */}
            {(profile?.role === "intensivist" || profile?.role === "admin") && (
              <div>
                <h2 className="in-section-title">
                  Model Fairness (Population-level)
                </h2>
                <FairnessChart />
              </div>
            )}
          </div>
        ) : (
          /* Splash when no patient selected yet */
          <div className="in-splash">
            <p className="in-splash__icon">🔬</p>
            <p className="in-splash__lead">
              Enter a Patient ID above to load all novel insights for that patient.
            </p>
            <div className="in-feature-grid">
              {[
                ["SepNova Score", "ML + qSOFA + SOFA velocity fusion"],
                ["3h/6h/12h Prediction", "Multi-horizon risk stratification"],
                ["Risk Drivers", "Which vitals/labs are elevating risk"],
                ["Counterfactuals", "What changes would reduce risk"],
              ].map(([title, desc]) => (
                <div key={title} className="in-feature">
                  <p className="in-feature__title">{title}</p>
                  <p className="in-feature__desc">{desc}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Fairness audit shown globally to intensivist even without patient */}
        {!activePatient && (profile?.role === "intensivist" || profile?.role === "admin") && (
          <div>
            <h2 className="in-section-title">
              Population Fairness Audit
            </h2>
            <FairnessChart />
          </div>
        )}
      </div>
    </RoleGuard>
  );
}
