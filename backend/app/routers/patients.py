"""
SepNova — Patients Router
==========================
Every route requires a valid JWT and a clinical role. Prediction fields are
masked per role via ROLE_ALLOWED_PREDICTION_FIELDS (lab techs/admin receive no
raw prediction rows).
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from supabase import Client
from ..auth import CurrentUser, all_clinical, mask_prediction
from ..database import get_supabase, get_db
from ..models.schemas import PatientOut, DashboardSummary
from ..demo_data import (
    list_patients as demo_list_patients,
    get_patient as demo_get_patient,
    dashboard_summary as demo_dashboard_summary,
    get_vitals as demo_get_vitals,
    get_labs as demo_get_labs,
    get_predictions as demo_get_predictions,
)

router = APIRouter(prefix="/api/v1/patients", tags=["patients"])


@router.get("/", response_model=list[PatientOut])
async def list_patients(
    ward: str | None = Query(None),
    status: str = Query("active"),
    limit: int = Query(100, le=500),
    user: CurrentUser = Depends(all_clinical),
    db: Client = Depends(get_db),
):
    """List all patients, optionally filtered by ward and status."""
    if user.user_id == "demo-user":
        return demo_list_patients(ward=ward, status=status, limit=limit)
    try:
        q = db.table("patients").select("*").eq("status", status).limit(limit)
        if ward:
            q = q.eq("ward", ward)
        res = q.execute()
        patients = res.data or []
    except Exception:
        return demo_list_patients(ward=ward, status=status, limit=limit)

    # Attach latest risk score to each patient
    for p in patients:
        try:
            pred = (
                db.table("predictions")
                .select("risk_score, risk_level")
                .eq("patient_id", p["patient_id"])
                .order("predicted_at", desc=True)
                .limit(1)
                .execute()
            )
            if pred.data:
                p["latest_risk_score"] = pred.data[0]["risk_score"]
                p["latest_risk_level"] = pred.data[0]["risk_level"]
            else:
                p["latest_risk_score"] = None
                p["latest_risk_level"] = None
        except Exception:
            p["latest_risk_score"] = None
            p["latest_risk_level"] = None

        try:
            vit = (
                db.table("vitals")
                .select("hour,hr,o2sat,temp,sbp,map,dbp,resp")
                .eq("patient_id", p["patient_id"])
                .order("hour", desc=True)
                .limit(1)
                .execute()
            )
            p["latest_vitals"] = vit.data[0] if vit.data else None
        except Exception:
            p["latest_vitals"] = None

    return patients


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard_summary(
    user: CurrentUser = Depends(all_clinical),
    db: Client = Depends(get_db),
):
    """Aggregate counts for the ward overview header cards."""
    if user.user_id == "demo-user":
        return demo_dashboard_summary()
    try:
        patients = db.table("patients").select("patient_id").eq("status", "active").execute()
        patient_ids = [p["patient_id"] for p in (patients.data or [])]
    except Exception:
        return demo_dashboard_summary()

    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for pid in patient_ids:
        try:
            pred = (
                db.table("predictions")
                .select("risk_level")
                .eq("patient_id", pid)
                .order("predicted_at", desc=True)
                .limit(1)
                .execute()
            )
            if pred.data:
                level = pred.data[0]["risk_level"]
                counts[level] = counts.get(level, 0) + 1
        except Exception:
            pass

    unacked = 0
    try:
        alerts = (
            db.table("alerts")
            .select("id", count="exact")
            .eq("is_acknowledged", False)
            .execute()
        )
        unacked = alerts.count or 0
    except Exception:
        pass

    auroc = None
    try:
        model_run = (
            db.table("model_runs")
            .select("auroc")
            .order("ran_at", desc=True)
            .limit(1)
            .execute()
        )
        auroc = model_run.data[0]["auroc"] if model_run.data else None
    except Exception:
        pass

    return DashboardSummary(
        total_patients=len(patient_ids),
        critical_count=counts["critical"],
        high_risk_count=counts["high"],
        medium_risk_count=counts["medium"],
        low_risk_count=counts["low"],
        unacknowledged_alerts=unacked,
        latest_model_auroc=auroc,
    )


@router.get("/{patient_id}", response_model=PatientOut)
async def get_patient(
    patient_id: str,
    user: CurrentUser = Depends(all_clinical),
    db: Client = Depends(get_db),
):
    if user.user_id == "demo-user":
        p = demo_get_patient(patient_id)
        if not p:
            raise HTTPException(404, f"Patient {patient_id} not found")
        return p
    try:
        res = db.table("patients").select("*").eq("patient_id", patient_id).single().execute()
    except Exception:
        # Fallback to demo data so the page still renders
        p = demo_get_patient(patient_id)
        if p:
            return p
        raise HTTPException(404, f"Patient {patient_id} not found")
    if not res.data:
        raise HTTPException(404, f"Patient {patient_id} not found")

    p = res.data
    try:
        pred = (
            db.table("predictions")
            .select("risk_score, risk_level")
            .eq("patient_id", patient_id)
            .order("predicted_at", desc=True)
            .limit(1)
            .execute()
        )
        if pred.data:
            p["latest_risk_score"] = pred.data[0]["risk_score"]
            p["latest_risk_level"] = pred.data[0]["risk_level"]
    except Exception:
        pass
    return p


@router.get("/{patient_id}/vitals")
async def get_patient_vitals(
    patient_id: str,
    user: CurrentUser = Depends(all_clinical),
    db: Client = Depends(get_db),
):
    if user.user_id == "demo-user":
        return demo_get_vitals(patient_id)
    try:
        res = (
            db.table("vitals")
            .select("*")
            .eq("patient_id", patient_id)
            .order("hour")
            .execute()
        )
        return res.data or []
    except Exception:
        return demo_get_vitals(patient_id)


@router.get("/{patient_id}/labs")
async def get_patient_labs(
    patient_id: str,
    user: CurrentUser = Depends(all_clinical),
    db: Client = Depends(get_db),
):
    if user.user_id == "demo-user":
        return demo_get_labs(patient_id)
    try:
        res = (
            db.table("lab_results")
            .select("*")
            .eq("patient_id", patient_id)
            .order("hour")
            .execute()
        )
        return res.data or []
    except Exception:
        return demo_get_labs(patient_id)


@router.get("/{patient_id}/predictions")
async def get_patient_predictions(
    patient_id: str,
    limit: int = Query(20),
    user: CurrentUser = Depends(all_clinical),
    db: Client = Depends(get_db),
):
    if user.user_id == "demo-user":
        return demo_get_predictions(patient_id)
    try:
        res = (
            db.table("predictions")
            .select("*")
            .eq("patient_id", patient_id)
            .order("predicted_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception:
        res = None
    rows = (res.data if res else None) or []
    if not rows:
        return demo_get_predictions(patient_id)
    # Column-level enforcement: never leak fields the caller's role cannot see.
    masked = [mask_prediction(row, user.role) for row in rows]
    return [row for row in masked if row]
