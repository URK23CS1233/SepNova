"""
SepNova — Insights Router
===========================
Novel API endpoints exposing composite scores, multi-horizon predictions,
counterfactual explanations, and fairness audit results.
"""
from __future__ import annotations
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from ..auth import CurrentUser, get_current_user, require_role
from ..database import get_supabase
from ..models.ml_model import get_model
from ..inference_features import build_patient_feature_vector as _build_features_dict

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])

# Role dependency helpers
def clinical_no_lab(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """All clinical roles except lab technician."""
    allowed = {"intensivist", "surgeon", "nurse", "anesthesiologist", "admin"}
    if user.role not in allowed:
        raise HTTPException(403, "Lab technicians cannot access patient insights.")
    return user

def intensivist_only(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role not in {"intensivist", "admin"}:
        raise HTTPException(403, "Intensivist/admin access required.")
    return user


def _load_multi_horizon_model(horizon: str):
    """Load a horizon-specific model artifact."""
    import joblib
    from pathlib import Path
    path = Path(__file__).parent.parent.parent / "ml" / "artifacts" / f"sepnova_model_{horizon}.pkl"
    if not path.exists():
        raise HTTPException(
            503,
            f"Model for horizon '{horizon}' not found. Run: python ml/train_multi_horizon.py"
        )
    return joblib.load(str(path))


# Patient feature building lives in app/inference_features.py (the single source of
# truth shared with /predictions, /batch and ml/predict.py); imported above as
# `_build_features_dict`.


# ── Composite Score (SepNova Score) ──────────────────────────────────────────

@router.get("/composite/{patient_id}")
async def get_composite_score(
    patient_id: str,
    user: CurrentUser = Depends(clinical_no_lab),
    db: Client = Depends(get_supabase),
):
    """
    Compute the SepNova Composite Score (SNS) for a patient.
    Fuses: ML ensemble + qSOFA + SOFA velocity.
    """
    from ml.sofa import sofa_from_rows, sofa_velocity, compute_qsofa
    from ml.composite_score import compute_sns

    vitals = db.table("vitals").select("*").eq("patient_id", patient_id).order("hour").execute()
    labs   = db.table("lab_results").select("*").eq("patient_id", patient_id).order("hour").execute()

    v_rows = vitals.data or []
    l_rows = labs.data or []

    sofa_series = sofa_from_rows(v_rows, l_rows) if v_rows else []
    velocity    = sofa_velocity(sofa_series) if sofa_series else 0.0

    latest_vital = v_rows[-1] if v_rows else {}
    qsofa = compute_qsofa(
        resp_rate=latest_vital.get("resp"),
        sbp=latest_vital.get("sbp"),
    )

    # Live ML probability from the v3 model + shared feature pipeline. Falls back
    # to the most recent stored prediction if the model/features are unavailable.
    try:
        ml_prob = get_model().predict(_build_features_dict(patient_id, db))["risk_score"]
    except Exception:
        pred = (
            db.table("predictions").select("risk_score")
            .eq("patient_id", patient_id).order("predicted_at", desc=True).limit(1).execute()
        )
        ml_prob = pred.data[0]["risk_score"] if pred.data else 0.0

    sns = compute_sns(ml_prob, qsofa["qsofa_total"], velocity)
    latest_sofa = sofa_series[-1] if sofa_series else {}

    return {
        "patient_id":          patient_id,
        **sns,
        "sofa_total":          latest_sofa.get("sofa_total"),
        "qsofa_detail":        qsofa,
        "sofa_series_length":  len(sofa_series),
    }


# ── Multi-horizon Predictions ─────────────────────────────────────────────────

@router.get("/horizons/{patient_id}")
async def get_multi_horizon(
    patient_id: str,
    user: CurrentUser = Depends(clinical_no_lab),
    db: Client = Depends(get_supabase),
):
    """
    Run all three prediction horizons (3h, 6h, 12h) for a patient.
    """
    features = _build_features_dict(patient_id, db)
    results = {}
    for horizon in ["3h", "6h", "12h"]:
        try:
            artifact   = _load_multi_horizon_model(horizon)
            feat_names = artifact["feature_names"]
            xgb        = artifact["xgb"]
            lgb        = artifact["lgb"]
            threshold  = artifact["threshold"]

            x     = np.array([features.get(f, 0.0) for f in feat_names], dtype=np.float32).reshape(1, -1)
            xgb_p = float(xgb.predict_proba(x)[0, 1])
            lgb_p = float(lgb.predict_proba(x)[0, 1])
            prob  = 0.55 * xgb_p + 0.45 * lgb_p

            results[horizon] = {
                "probability": round(prob, 4),
                "threshold":   threshold,
                "positive":    prob >= threshold,
                "risk_pct":    round(prob * 100, 1),
            }
        except HTTPException as e:
            results[horizon] = {"error": str(e.detail)}

    return {"patient_id": patient_id, "horizons": results}


# ── Counterfactual Explanations ───────────────────────────────────────────────

@router.get("/explain/{patient_id}")
async def explain_patient(
    patient_id: str,
    user: CurrentUser = Depends(clinical_no_lab),
    db: Client = Depends(get_supabase),
    model=Depends(get_model),
):
    """
    Generate counterfactual clinical explanations for a high-risk patient.
    """
    from ml.explainer import explain_patient as _explain

    pred = (
        db.table("predictions").select("risk_score,risk_level")
        .eq("patient_id", patient_id).order("predicted_at", desc=True).limit(1).execute()
    )
    if not pred.data:
        raise HTTPException(404, "No prediction found. Run predictions first.")

    risk_level = pred.data[0]["risk_level"]
    if risk_level == "low":
        return {
            "patient_id": patient_id,
            "risk_level": risk_level,
            "message": "Patient is low risk — no counterfactuals needed.",
            "feature_contributions": [],
            "counterfactuals": [],
        }

    features = _build_features_dict(patient_id, db)
    artifact = {"xgb": model.xgb, "lgb": model.lgb, "feature_names": model.feature_names}
    explanation = _explain(artifact, features, risk_level)

    return {"patient_id": patient_id, "risk_level": risk_level, **explanation}


# ── Fairness Audit ────────────────────────────────────────────────────────────

@router.get("/fairness")
async def fairness_report(
    user: CurrentUser = Depends(intensivist_only),
    db: Client = Depends(get_supabase),
):
    """
    Live fairness audit using predictions stored in Supabase.
    AUROC by age group and gender. Intensivist / admin only.
    """
    from ml.fairness import subgroup_metrics

    patients = db.table("patients").select("patient_id,age,gender").execute()
    preds    = (
        db.table("predictions")
        .select("patient_id,risk_score,sepsis_label")
        .not_.is_("sepsis_label", "null")
        .execute()
    )

    if not preds.data or len(preds.data) < 20:
        return {
            "message": (
                "Insufficient labelled predictions for fairness audit "
                "(need ≥ 20 with known labels). Seed more data and run predictions."
            ),
            "subgroups": [],
        }

    pat_meta = {p["patient_id"]: p for p in (patients.data or [])}
    pred_map: dict = {}
    for p in preds.data:
        if p["patient_id"] not in pred_map:
            pred_map[p["patient_id"]] = p

    pids    = list(pred_map.keys())
    y_true  = np.array([pred_map[p]["sepsis_label"] for p in pids], dtype=int)
    y_prob  = np.array([pred_map[p]["risk_score"]   for p in pids], dtype=float)
    ages    = np.array([pat_meta.get(p, {}).get("age", 65)   for p in pids], dtype=float)
    genders = np.array([pat_meta.get(p, {}).get("gender", 0) for p in pids], dtype=float)

    return subgroup_metrics(y_true, y_prob, ages, genders)
