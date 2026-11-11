"""
SepNova — Model Metrics Router
==============================
Read-only "model card": cross-validated metrics, threshold, and calibration.
Requires an intensivist or admin JWT (matches the Model Results page policy).

Phase 3: never fabricate scores. If the artifact is missing the endpoint fails
with an explicit message instead of returning made-up numbers.
"""
from fastapi import APIRouter, Depends, HTTPException

from ..auth import CurrentUser, require_role
from ..models.ml_model import get_model, SepNovaModel

router = APIRouter(prefix="/api/v1/ml", tags=["ml"])

model_readers = require_role("intensivist", "admin")


@router.get("/metrics")
async def get_model_metrics(
    user: CurrentUser = Depends(model_readers),
    model: SepNovaModel = Depends(get_model),
):
    return {
        "metrics":       model.get_metrics(),
        "version":       model.version,
        "threshold":     model.threshold,
        "alert_thresholds": model.alert_thresholds,
        "feature_count": len(model.feature_names),
        "trained_at":    model.trained_at,
        "methodology": (
            "5-fold StratifiedGroupKFold (group=patient_id), SMOTE within each "
            "fold; XGBoost + LightGBM + HistGradientBoosting + RandomForest stacking "
            "with a LightGBM meta-learner and isotonic calibration. Predicts sepsis "
            "onset 6 hours ahead using the past 6 hours of vitals & labs."
        ),
    }


@router.get("/calibration")
async def calibration_report(
    user: CurrentUser = Depends(model_readers),
    model: SepNovaModel = Depends(get_model),
):
    """
    Brier score + reliability table from the stored artifact metrics.
    The table is produced during training from doubly out-of-fold predictions.
    """
    metrics = model.get_metrics()
    brier = metrics.get("brier")
    if brier is None:
        raise HTTPException(
            503,
            "Artifact has no stored Brier score. Retrain with ml/train_v3.py.",
        )

    reliability = metrics.get("reliability")
    if reliability is None:
        # Older artifacts stored only the summary. Be explicit rather than fake a table.
        reliability = []
        note = "This artifact predates stored reliability bins; retrain to populate them."
    else:
        note = None

    return {
        "brier":        brier,
        "threshold":    model.threshold,
        "n_samples":    metrics.get("n_samples"),
        "prevalence":   metrics.get("prevalence"),
        "reliability":  reliability,
        "note":         note,
        "model_version": model.version,
        "methodology":  "Reliability computed from doubly out-of-fold calibrated probabilities.",
    }
