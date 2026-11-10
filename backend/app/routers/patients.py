from fastapi import APIRouter, HTTPException, Depends, Query
from supabase import Client
from ..database import get_supabase
from ..models.schemas import PatientOut, DashboardSummary

router = APIRouter(prefix="/api/v1/patients", tags=["patients"])


@router.get("/", response_model=list[PatientOut])
async def list_patients(
    ward: str | None = Query(None),
    status: str = Query("active"),
    limit: int = Query(100, le=500),
    db: Client = Depends(get_supabase),
):
    """List all patients, optionally filtered by ward and status."""
    q = db.table("patients").select("*").eq("status", status).limit(limit)
    if ward:
        q = q.eq("ward", ward)
    res = q.execute()

    patients = res.data or []

    # Attach latest risk score to each patient
    for p in patients:
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

    return patients


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard_summary(db: Client = Depends(get_supabase)):
    """Aggregate counts for the ward overview header cards."""
    patients = db.table("patients").select("patient_id").eq("status", "active").execute()
    patient_ids = [p["patient_id"] for p in (patients.data or [])]

    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for pid in patient_ids:
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

    alerts = (
        db.table("alerts")
        .select("id", count="exact")
        .eq("is_acknowledged", False)
        .execute()
    )
    unacked = alerts.count or 0

    model_run = (
        db.table("model_runs")
        .select("auroc")
        .order("ran_at", desc=True)
        .limit(1)
        .execute()
    )
    auroc = model_run.data[0]["auroc"] if model_run.data else None

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
async def get_patient(patient_id: str, db: Client = Depends(get_supabase)):
    res = db.table("patients").select("*").eq("patient_id", patient_id).single().execute()
    if not res.data:
        raise HTTPException(404, f"Patient {patient_id} not found")

    p = res.data
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
    return p


@router.get("/{patient_id}/vitals")
async def get_patient_vitals(patient_id: str, db: Client = Depends(get_supabase)):
    res = (
        db.table("vitals")
        .select("*")
        .eq("patient_id", patient_id)
        .order("hour")
        .execute()
    )
    return res.data or []


@router.get("/{patient_id}/labs")
async def get_patient_labs(patient_id: str, db: Client = Depends(get_supabase)):
    res = (
        db.table("lab_results")
        .select("*")
        .eq("patient_id", patient_id)
        .order("hour")
        .execute()
    )
    return res.data or []


@router.get("/{patient_id}/predictions")
async def get_patient_predictions(
    patient_id: str,
    limit: int = Query(20),
    db: Client = Depends(get_supabase),
):
    res = (
        db.table("predictions")
        .select("*")
        .eq("patient_id", patient_id)
        .order("predicted_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []
