from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Patient ──────────────────────────────────────────────────────────────────

class PatientBase(BaseModel):
    patient_id: str
    age: Optional[int] = None
    gender: Optional[int] = None
    hosp_adm_time: Optional[float] = None
    icu_los: Optional[int] = None
    ward: str = "ICU-A"
    status: str = "active"


class PatientOut(PatientBase):
    id: str
    created_at: datetime
    latest_risk_score: Optional[float] = None
    latest_risk_level: Optional[str] = None
    # Latest recorded bedside hour, used by the monitor tiles.
    latest_vitals: Optional[dict] = None

    class Config:
        from_attributes = True


# ── Vitals ───────────────────────────────────────────────────────────────────

class VitalsIn(BaseModel):
    patient_id: str
    hour: int
    hr: Optional[float] = None
    o2sat: Optional[float] = None
    temp: Optional[float] = None
    sbp: Optional[float] = None
    map: Optional[float] = None
    dbp: Optional[float] = None
    resp: Optional[float] = None


class VitalsOut(VitalsIn):
    id: str
    recorded_at: datetime


# ── Labs ─────────────────────────────────────────────────────────────────────

class LabsIn(BaseModel):
    patient_id: str
    hour: int
    lactate: Optional[float] = None
    wbc: Optional[float] = None
    creatinine: Optional[float] = None
    bilirubin_total: Optional[float] = None
    bilirubin_direct: Optional[float] = None
    platelets: Optional[float] = None
    glucose: Optional[float] = None
    hgb: Optional[float] = None
    hct: Optional[float] = None
    potassium: Optional[float] = None
    ph: Optional[float] = None
    paco2: Optional[float] = None
    hco3: Optional[float] = None
    base_excess: Optional[float] = None
    ptt: Optional[float] = None
    troponin_i: Optional[float] = None
    ast: Optional[float] = None
    bun: Optional[float] = None
    calcium: Optional[float] = None


# ── Predictions ───────────────────────────────────────────────────────────────

class PredictionRequest(BaseModel):
    patient_id: str
    features: dict[str, float] = Field(
        description="Aggregated patient features (mean, std, min, max, last, range per vital/lab)"
    )


class PredictionOut(BaseModel):
    patient_id: str
    risk_score: float
    risk_level: str
    xgb_score: float
    lgb_score: float
    model_version: str
    predicted_at: datetime
    # Phase 1/3: transparent missing-data reporting + SHAP explanation.
    confidence: Optional[float] = None
    data_complete: Optional[bool] = None
    missing_features: list[str] = []
    imputed_features: Optional[int] = None
    top_features: list[dict] = []
    explanation_method: Optional[str] = None
    # Derived from the artifact's tuned threshold (single source of truth).
    alert_thresholds: Optional[dict] = None


# ── Alerts ───────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: str
    patient_id: str
    alert_type: str
    severity: str
    message: str
    risk_score: Optional[float] = None
    is_acknowledged: bool
    created_at: datetime


# ── Model Runs ────────────────────────────────────────────────────────────────

class ModelRunOut(BaseModel):
    id: str
    run_name: Optional[str]
    model_type: Optional[str]
    auroc: Optional[float]
    auprc: Optional[float]
    sensitivity: Optional[float]
    specificity: Optional[float]
    f1_score: Optional[float]
    threshold: Optional[float]
    n_patients: Optional[int]
    n_sepsis: Optional[int]
    ran_at: datetime


# ── Dashboard summary ─────────────────────────────────────────────────────────

class DashboardSummary(BaseModel):
    total_patients: int
    critical_count: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    unacknowledged_alerts: int
    latest_model_auroc: Optional[float]
