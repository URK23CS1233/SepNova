from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from supabase import Client
from ..database import get_supabase
from ..models.schemas import PredictionRequest, PredictionOut
from ..models.ml_model import get_model, SepNovaModel

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])

ALERT_THRESHOLDS = {"critical": 0.70, "high": 0.45}


def _maybe_create_alert(patient_id: str, risk_score: float, risk_level: str, db: Client):
    """Auto-create an alert for high/critical risk predictions."""
    if risk_level not in ALERT_THRESHOLDS:
        return
    msg = (
        f"Patient {patient_id} has {risk_level.upper()} sepsis risk "
        f"(score: {risk_score:.2f}). Immediate clinical assessment recommended."
    )
    db.table("alerts").insert({
        "patient_id":  patient_id,
        "alert_type":  "sepsis_risk",
        "severity":    "critical" if risk_level == "critical" else "warning",
        "message":     msg,
        "risk_score":  risk_score,
        "is_acknowledged": False,
    }).execute()


@router.post("/", response_model=PredictionOut)
async def predict(
    req: PredictionRequest,
    model: SepNovaModel = Depends(get_model),
    db: Client = Depends(get_supabase),
):
    """
    Run sepsis risk prediction for a patient using their aggregated features.
    Stores the result in Supabase and auto-creates an alert if risk is high/critical.
    """
    # Verify patient exists
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

    _maybe_create_alert(req.patient_id, result["risk_score"], result["risk_level"], db)

    return PredictionOut(
        patient_id=req.patient_id,
        predicted_at=now,
        **result,
    )


@router.get("/batch")
async def batch_predict(
    model: SepNovaModel = Depends(get_model),
    db: Client = Depends(get_supabase),
):
    """
    Run predictions for all active patients using their stored vitals/labs.
    Returns a summary of results.
    """
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
            _maybe_create_alert(pid, result["risk_score"], result["risk_level"], db)
            results.append({"patient_id": pid, **result})
        except Exception as e:
            results.append({"patient_id": pid, "error": str(e)})

    return {"processed": len(results), "results": results}
