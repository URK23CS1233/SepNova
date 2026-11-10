"""
SepNova — Live Inference Feature Builder (SHARED single source of truth)
=======================================================================
Builds the full engineered feature vector for a patient from Supabase using the
SAME ml/features.py pipeline as training (build_dataset_v3 / train_v3). EVERY live
inference path — the insights endpoints, /predictions, /batch and ml/predict.py —
MUST route through build_patient_feature_vector() so the model receives exactly the
features it was trained on (the 223-key build_feature_vector output), windowed over
the same last 6 hours used in training. Anything else is silent train/inference skew.
"""
from __future__ import annotations
from supabase import Client

from ml.features import compute_base_stats, build_feature_vector, PARAMETERS

WINDOW_HOURS = 6

# Map the wide vitals/lab_results columns -> canonical PARAMETER names.
WIDE_MAP = {
    "hr": "HR", "o2sat": "O2SAT", "temp": "TEMP", "sbp": "SBP", "map": "MAP",
    "dbp": "DBP", "resp": "RESP", "lactate": "Lactate", "wbc": "WBC",
    "creatinine": "Creatinine", "bilirubin_total": "Bilirubin_total",
    "bilirubin_direct": "Bilirubin_direct", "platelets": "Platelets",
    "glucose": "Glucose", "hgb": "Hgb", "hct": "Hct", "potassium": "Potassium",
    "ph": "pH", "paco2": "PaCO2", "hco3": "HCO3", "base_excess": "BaseExcess",
    "ptt": "PTT", "troponin_i": "TroponinI", "ast": "AST", "bun": "BUN",
    "calcium": "Calcium",
}


def _readings_from_patient_readings(patient_id: str, db: Client) -> list[dict]:
    """Long-format readings from patient_readings (most recent first). [] if absent/empty."""
    try:
        res = (
            db.table("patient_readings")
            .select("parameter,value_numeric,recorded_at")
            .eq("patient_id", patient_id)
            .order("recorded_at", desc=True)
            .limit(400)
            .execute()
        )
    except Exception:
        return []
    rows = res.data or []
    readings = []
    for r in reversed(rows):                       # reverse desc -> chronological (_last = newest)
        p, v = r.get("parameter"), r.get("value_numeric")
        if p in PARAMETERS and v is not None:
            readings.append({"parameter": p, "value": v})
    return readings


def _readings_from_wide(patient_id: str, db: Client) -> list[dict]:
    """Fallback: last 6 hours from the wide vitals + lab_results tables, long-form."""
    try:
        vitals = db.table("vitals").select("*").eq("patient_id", patient_id).order("hour").execute()
        labs   = db.table("lab_results").select("*").eq("patient_id", patient_id).order("hour").execute()
    except Exception:
        return []
    v_rows, l_rows = (vitals.data or []), (labs.data or [])

    hours = sorted({r["hour"] for r in v_rows} | {r["hour"] for r in l_rows})
    window = set(hours[-WINDOW_HOURS:]) if hours else set()   # last 6 hours, like training

    tagged = []
    for rows in (v_rows, l_rows):
        for r in rows:
            if r.get("hour") in window:
                for col, val in r.items():
                    p = WIDE_MAP.get(col)
                    if p and val is not None:
                        tagged.append((r["hour"], p, val))
    tagged.sort(key=lambda t: t[0])                # chronological for _last
    return [{"parameter": p, "value": v} for _, p, v in tagged]


def build_patient_feature_vector(patient_id: str, db: Client) -> dict:
    """
    Build the full engineered feature dict the model expects (identical to training):
    last 6h of readings -> compute_base_stats -> + Age/Gender/HospAdmTime ->
    build_feature_vector. Reads patient_readings first, falling back to the wide
    vitals/lab_results tables. A patient with no data yields an all-zero vector that
    the model still scores (0.0 == missing), and a missing patients row is tolerated.
    """
    readings = _readings_from_patient_readings(patient_id, db)
    if not readings:
        readings = _readings_from_wide(patient_id, db)

    stats = compute_base_stats(readings)

    # .maybe_single() returns data=None (no raise) when the patient row is absent.
    try:
        patient = (
            db.table("patients").select("age,gender,hosp_adm_time")
            .eq("patient_id", patient_id).maybe_single().execute()
        )
        p = (patient.data or {}) if patient else {}
    except Exception:
        p = {}

    stats["Age"]         = float(p.get("age") or 0)
    stats["Gender"]      = float(p.get("gender") or 0)
    stats["HospAdmTime"] = float(p.get("hosp_adm_time") or 0)

    return build_feature_vector(stats)
