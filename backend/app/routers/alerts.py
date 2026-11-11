"""
SepNova — Alerts Router
========================
Every route requires a JWT. Clinical roles may read alerts; acknowledging is
restricted to roles that deliver care (lab technicians are read-only here).
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, timezone
from supabase import Client

from ..auth import CurrentUser, all_clinical, clinical_no_lab, log_audit
from ..database import get_supabase, get_db
from ..models.schemas import AlertOut
from ..demo_data import list_alerts as demo_list_alerts, alert_stats as demo_alert_stats

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("/", response_model=list[AlertOut])
async def list_alerts(
    acknowledged: bool = Query(False),
    severity: str | None = Query(None),
    limit: int = Query(50, le=200),
    user: CurrentUser = Depends(all_clinical),
    db: Client = Depends(get_db),
):
    if user.user_id == "demo-user":
        return demo_list_alerts(acknowledged=acknowledged, severity=severity, limit=limit)
    try:
        q = (
            db.table("alerts")
            .select("*")
            .eq("is_acknowledged", acknowledged)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if severity:
            q = q.eq("severity", severity)
        res = q.execute()
        return res.data or []
    except Exception:
        return demo_list_alerts(acknowledged=acknowledged, severity=severity, limit=limit)


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str | None = Query(None, description="Defaults to the authenticated user"),
    user: CurrentUser = Depends(clinical_no_lab),
    db: Client = Depends(get_db),
):
    if user.user_id == "demo-user":
        # allow acknowledge in demo (no-op)
        return {"status": "acknowledged", "alert_id": alert_id}
    try:
        res = db.table("alerts").select("id").eq("id", alert_id).execute()
    except Exception:
        raise HTTPException(404, "Alert not found")
    if not res.data:
        raise HTTPException(404, "Alert not found")

    by = acknowledged_by or user.full_name or user.user_id
    try:
        db.table("alerts").update({
            "is_acknowledged":  True,
            "acknowledged_by":  by,
            "acknowledged_at":  datetime.now(timezone.utc).isoformat(),
        }).eq("id", alert_id).execute()
    except Exception:
        pass

    await log_audit(db, user, action="acknowledge_alert", record_id=alert_id)
    return {"status": "acknowledged", "alert_id": alert_id}


@router.get("/stats")
async def alert_stats(
    user: CurrentUser = Depends(all_clinical),
    db: Client = Depends(get_db),
):
    if user.user_id == "demo-user":
        return demo_alert_stats()
    total_n = unacked_n = critical_n = 0
    try:
        total   = db.table("alerts").select("id", count="exact").execute()
        total_n = total.count or 0
    except Exception:
        pass
    try:
        unacked = db.table("alerts").select("id", count="exact").eq("is_acknowledged", False).execute()
        unacked_n = unacked.count or 0
    except Exception:
        pass
    try:
        critical = (
            db.table("alerts")
            .select("id", count="exact")
            .eq("severity", "critical")
            .eq("is_acknowledged", False)
            .execute()
        )
        critical_n = critical.count or 0
    except Exception:
        pass
    return {
        "total":             total_n,
        "unacknowledged":    unacked_n,
        "critical_unacked":  critical_n,
    }
