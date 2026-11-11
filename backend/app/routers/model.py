"""
SepNova — Model Runs Router
============================
Read-only model-run history. Requires a JWT with intensivist or admin role.
"""
from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from ..auth import CurrentUser, require_role
from ..database import get_supabase, get_db
from ..models.schemas import ModelRunOut

router = APIRouter(prefix="/api/v1/model", tags=["model"])

model_readers = require_role("intensivist", "admin")


@router.get("/runs", response_model=list[ModelRunOut])
async def list_model_runs(
    user: CurrentUser = Depends(model_readers),
    db: Client = Depends(get_db),
):
    res = db.table("model_runs").select("*").order("ran_at", desc=True).limit(20).execute()
    return res.data or []


@router.get("/runs/latest", response_model=ModelRunOut)
async def latest_model_run(
    user: CurrentUser = Depends(model_readers),
    db: Client = Depends(get_db),
):
    res = db.table("model_runs").select("*").order("ran_at", desc=True).limit(1).execute()
    if not res.data:
        raise HTTPException(404, "No model runs found. Run the training pipeline first.")
    return res.data[0]
