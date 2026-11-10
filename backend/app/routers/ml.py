"""
SepNova — Model Metrics Router
==============================
Read-only "model card": exposes the live model's cross-validated metrics and
metadata for the ModelResults dashboard. No DB or auth required.
"""
from fastapi import APIRouter, HTTPException
from ..models.ml_model import get_model

router = APIRouter(prefix="/api/v1/ml", tags=["ml"])


@router.get("/metrics")
async def get_model_metrics():
    try:
        model = get_model()
    except Exception as e:                # missing OR unloadable/incompatible artifact
        raise HTTPException(503, f"Model unavailable: {e}")

    return {
        "metrics":       model.get_metrics(),
        "version":       model.version,
        "threshold":     model.threshold,
        "feature_count": len(model.feature_names),
        "trained_at":    model.trained_at,
        "methodology": (
            "5-fold StratifiedGroupKFold (group=patient_id), SMOTE within each "
            "fold; XGBoost + LightGBM + HistGradientBoosting + RandomForest stacking "
            "with a LightGBM meta-learner and isotonic calibration. Predicts sepsis "
            "onset 6 hours ahead using the past 6 hours of vitals & labs."
        ),
    }
