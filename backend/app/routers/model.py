from fastapi import APIRouter, Depends
from supabase import Client
from ..database import get_supabase
from ..models.schemas import ModelRunOut

router = APIRouter(prefix="/api/v1/model", tags=["model"])


@router.get("/runs", response_model=list[ModelRunOut])
async def list_model_runs(db: Client = Depends(get_supabase)):
    res = db.table("model_runs").select("*").order("ran_at", desc=True).limit(20).execute()
    return res.data or []


@router.get("/runs/latest", response_model=ModelRunOut)
async def latest_model_run(db: Client = Depends(get_supabase)):
    res = db.table("model_runs").select("*").order("ran_at", desc=True).limit(1).execute()
    if not res.data:
        from fastapi import HTTPException
        raise HTTPException(404, "No model runs found. Run the training pipeline first.")
    return res.data[0]
