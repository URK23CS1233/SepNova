from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, timezone
from supabase import Client
from ..database import get_supabase
from ..models.schemas import AlertOut

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("/", response_model=list[AlertOut])
async def list_alerts(
    acknowledged: bool = Query(False),
    severity: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: Client = Depends(get_supabase),
):
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


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str = Query(..., description="Name or ID of the clinician acknowledging"),
    db: Client = Depends(get_supabase),
):
    res = db.table("alerts").select("id").eq("id", alert_id).execute()
    if not res.data:
        raise HTTPException(404, "Alert not found")

    db.table("alerts").update({
        "is_acknowledged":  True,
        "acknowledged_by":  acknowledged_by,
        "acknowledged_at":  datetime.now(timezone.utc).isoformat(),
    }).eq("id", alert_id).execute()

    return {"status": "acknowledged", "alert_id": alert_id}


@router.get("/stats")
async def alert_stats(db: Client = Depends(get_supabase)):
    total   = db.table("alerts").select("id", count="exact").execute()
    unacked = db.table("alerts").select("id", count="exact").eq("is_acknowledged", False).execute()
    critical = (
        db.table("alerts")
        .select("id", count="exact")
        .eq("severity", "critical")
        .eq("is_acknowledged", False)
        .execute()
    )
    return {
        "total":             total.count or 0,
        "unacknowledged":    unacked.count or 0,
        "critical_unacked":  critical.count or 0,
    }
