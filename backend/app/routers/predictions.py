"""
SepNova — Predictions Router
=============================
All routes require a JWT. Prediction writes are restricted to the intensivist
role; response fields are filtered through ROLE_ALLOWED_PREDICTION_FIELDS.

Risk bands are NOT hardcoded here. Every alert cutoff is derived from the
artifact's tuned threshold through SepNovaModel.alert_thresholds.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from supabase import Client

from ..auth import CurrentUser, intensivist_only, mask_prediction
from ..database import get_supabase, get_db
from ..models.schemas import PredictionRequest
from ..models.ml_model import get_model, SepNovaModel

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])


def _maybe_create_alert(
    patient_id: str,
    risk_score: float,
    risk_level: str,
    model: SepNovaModel,
    db: Client,
):
    """Auto-create an alert for high/critical risk predictions."""
    if risk_level not in ("high", "critical"):
        return
    thresholds = model.alert_thresholds
    msg = (
        f"Patient {patient_id} has {risk_level.upper()} sepsis risk "
        f"(score: {risk_score:.2f}, high cutoff: {thresholds['high']:.2f}). "
        "Immediate clinical assessment recommended."
    )
    db.table("alerts").insert({
        "patient_id":  patient_id,
        "alert_type":  "sepsis_risk",
        "severity":    "critical" if risk_level == "critical" else "warning",
        "message":     msg,
        "risk_score":  risk_score,
        "is_acknowledged": False,
    }).execute()


def _prediction_payload(patient_id: str, result: dict, predicted_at: datetime) -> dict:
    return {
        "patient_id":    patient_id,
        "predicted_at":  predicted_at,
        **result,
    }


@router.post("/")
async def predict(
    req: PredictionRequest,
    user: CurrentUser = Depends(intensivist_only),
    model: SepNovaModel = Depends(get_model),
    db: Client = Depends(get_db),
):
    """
    Run sepsis risk prediction for a patient using their aggregated features.
    Stores the result and auto-creates an alert if risk is high/critical.
    """
    pat = db.table("patients").select("patient_id").eq("patient_id", req.patient_id).execute()
    if not pat.data:
        raise HTTPException(404, f"Patient {req.patient_id} not found")

    result = model.predict(req.features)
    now = datetime.now(timezone.utc)

    db.table("predictions").insert({
        "patient_id":    req.patient_id,
        "risk_score":    result["risk_score"],
        "risk_level":    result["risk_level"],
        "xgb_score":     result["xgb_score"],
        "lgb_score":     result["lgb_score"],
        "model_version": result["model_version"],
    }).execute()

    _maybe_create_alert(req.patient_id, result["risk_score"], result["risk_level"], model, db)

    payload = _prediction_payload(req.patient_id, result, now)
    payload["alert_thresholds"] = model.alert_thresholds
    try:
        payload["top_features"] = model.explain(req.features, top_k=5)
        payload["explanation_method"] = "shap"
    except Exception as e:
        # Never invent explanation values — report that SHAP is unavailable.
        payload["top_features"] = []
        payload["explanation_method"] = f"unavailable: {e}"

    return mask_prediction(payload, user.role)


@router.get("/batch")
async def batch_predict(
    user: CurrentUser = Depends(intensivist_only),
    model: SepNovaModel = Depends(get_model),
    db: Client = Depends(get_db),
):
    """Run predictions for all active patients using their stored vitals/labs."""
    from ..ml_utils import build_patient_features

    patients = db.table("patients").select("patient_id").eq("status", "active").execute()
    results = []
    for p in patients.data or []:
        pid = p["patient_id"]
        try:
            features = build_patient_features(pid, db)
            result = model.predict(features)
            db.table("predictions").insert({
                "patient_id":    pid,
                "risk_score":    result["risk_score"],
                "risk_level":    result["risk_level"],
                "xgb_score":     result["xgb_score"],
                "lgb_score":     result["lgb_score"],
                "model_version": result["model_version"],
            }).execute()
            _maybe_create_alert(pid, result["risk_score"], result["risk_level"], model, db)
            results.append(mask_prediction({"patient_id": pid, **result}, user.role))
        except Exception as e:
            results.append({"patient_id": pid, "error": str(e)})

    return {"processed": len(results), "results": results}
