"""
SepNova — Simulation Router
============================
POST /api/v1/simulate replays a synthetic ICU trajectory and returns the full
hour-by-hour risk/SOFA/qSOFA/SIRS timeline. The model stays server-side.

Requires a JWT with a clinical role (lab technicians excluded). Generated data
is clearly flagged as SIMULATED in every payload.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import CurrentUser, clinical_no_lab
from ..models.ml_model import get_model

router = APIRouter(prefix="/api/v1/simulate", tags=["simulate"])


class SimulationRequest(BaseModel):
    onset_hour: int = Field(12, ge=0, le=72, description="Hour sepsis 'begins'")
    total_hours: int = Field(30, ge=6, le=96)
    severity: float = Field(0.75, ge=0.0, le=1.0)
    noise: float = Field(0.35, ge=0.0, le=1.0)
    seed: int | None = 7
    ramp_hours: int = Field(8, ge=1, le=24)


@router.post("/")
async def simulate(
    req: SimulationRequest,
    user: CurrentUser = Depends(clinical_no_lab),
):
    """
    Generate and replay a simulated patient trajectory. Returns every hour with
    model score, derived clinical scores and SHAP drivers.
    """
    try:
        model = get_model()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Trained model unavailable: {e}. No score is fabricated.",
        )

    from ml.simulation import run_simulation

    return run_simulation(
        model,
        onset_hour=req.onset_hour,
        total_hours=req.total_hours,
        severity=req.severity,
        noise=req.noise,
        seed=req.seed,
        ramp_hours=req.ramp_hours,
    )
