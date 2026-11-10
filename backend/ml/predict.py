"""
SepNova — Batch Prediction Script
===================================
Loads active patients from Supabase, builds features from their
vitals + labs, runs the ensemble model, and writes predictions back.

Usage:
    cd backend
    python ml/predict.py
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_supabase
from app.ml_utils import build_patient_features
from app.models.ml_model import get_model, score_to_level


def run_batch():
    db    = get_supabase()
    model = get_model()

    patients = db.table("patients").select("patient_id").eq("status", "active").execute()
    pids = [p["patient_id"] for p in (patients.data or [])]
    print(f"Running predictions for {len(pids)} active patients…")

    ok, failed = 0, 0
    for pid in pids:
        try:
            features = build_patient_features(pid, db)
            result   = model.predict(features)

            db.table("predictions").insert({
                "patient_id":    pid,
                "risk_score":    result["risk_score"],
                "risk_level":    result["risk_level"],
                "xgb_score":     result["xgb_score"],
                "lgb_score":     result["lgb_score"],
                "model_version": result["model_version"],
            }).execute()

            # Auto-alert for high/critical
            if result["risk_level"] in ("critical", "high"):
                db.table("alerts").insert({
                    "patient_id":  pid,
                    "alert_type":  "sepsis_risk",
                    "severity":    "critical" if result["risk_level"] == "critical" else "warning",
                    "message":     f"Patient {pid} flagged as {result['risk_level'].upper()} sepsis risk (score={result['risk_score']:.2f})",
                    "risk_score":  result["risk_score"],
                    "is_acknowledged": False,
                }).execute()

            print(f"  {pid} → {result['risk_level']:8s} {result['risk_score']:.3f}")
            ok += 1
        except Exception as e:
            print(f"  {pid} → ERROR: {e}")
            failed += 1

    print(f"\nDone. ✓ {ok} succeeded, ✗ {failed} failed.")


if __name__ == "__main__":
    run_batch()
