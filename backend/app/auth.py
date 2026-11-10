"""
SepNova — JWT Authentication & Role-Based Access Control
=========================================================
Verifies Supabase-issued JWTs and enforces role-based route guards.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from functools import wraps
from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from .config import get_settings
from .database import get_supabase

# ── Roles ─────────────────────────────────────────────────────────────────────

ROLES = {
    "intensivist",
    "surgeon",
    "nurse",
    "anesthesiologist",
    "lab_technician",
    "admin",
}

# What each role is allowed to read (column-level enforcement in API layer)
ROLE_ALLOWED_PREDICTION_FIELDS = {
    "intensivist":      {"risk_score", "risk_level", "xgb_score", "lgb_score", "model_version", "predicted_at"},
    "surgeon":          {"risk_level", "predicted_at"},
    "nurse":            {"risk_level", "predicted_at"},
    "anesthesiologist": {"risk_level", "predicted_at"},
    "lab_technician":   set(),
    "admin":            set(),
}

ROLE_LLM_SCOPE = {
    "intensivist":      "Full access: vitals, labs, risk scores, ML explanations, surgical notes, anesthesia records, medications, alerts.",
    "surgeon":          "Restricted: HR, BP, O2Sat, coagulation labs (PTT, Platelets, Fibrinogen), surgical notes, pre-op anesthesia summary, surgical alerts only.",
    "nurse":            "Restricted: vitals, medications, nursing notes, basic labs (WBC, Hgb, Glucose), alerts, risk level (not raw score). No surgical notes, no anesthesia records.",
    "anesthesiologist": "Restricted: HR, BP, O2Sat, Resp, EtCO2, FiO2, ABG (pH, PaCO2, HCO3, BaseExcess), anesthesia records, airway status, electrolytes. No surgical notes, no raw ML scores.",
    "lab_technician":   "Restricted: lab results only (all lab values). No vitals, no clinical notes, no risk scores, no medications.",
    "admin":            "No patient data. User and role management only.",
}

# ── Models ────────────────────────────────────────────────────────────────────

class CurrentUser(BaseModel):
    user_id: str
    email:   str | None = None
    role:    str
    ward:    str | None = None
    full_name: str | None = None


# ── Bearer extraction ─────────────────────────────────────────────────────────

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db = Depends(get_supabase),
) -> CurrentUser:
    """
    Decode the Supabase JWT, verify it, and fetch the user's role from user_profiles.
    """
    token = credentials.credentials
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check expiry
    exp = payload.get("exp")
    if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No user ID in token")

    # Fetch role from user_profiles (source of truth — not JWT claims)
    try:
        profile = (
            db.table("user_profiles")
            .select("role, ward, full_name")
            .eq("id", user_id)
            .single()
            .execute()
        )
        if not profile.data:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User profile not found. Contact admin.")
        if not profile.data.get("is_active", True):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch user profile")

    return CurrentUser(
        user_id=user_id,
        email=payload.get("email"),
        role=profile.data["role"],
        ward=profile.data.get("ward"),
        full_name=profile.data.get("full_name"),
    )


# ── Role guards ───────────────────────────────────────────────────────────────

def require_role(*allowed_roles: str):
    """
    FastAPI dependency that enforces role-based access.
    Usage: Depends(require_role("intensivist", "nurse"))
    """
    async def guard(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not permitted for this endpoint. Required: {list(allowed_roles)}",
            )
        return user
    return guard


# Common role bundles
all_clinical = require_role("intensivist", "surgeon", "nurse", "anesthesiologist", "lab_technician")
clinical_no_lab = require_role("intensivist", "surgeon", "nurse", "anesthesiologist")
intensivist_only = require_role("intensivist")
admin_only = require_role("admin")


# ── Audit logger ──────────────────────────────────────────────────────────────

async def log_audit(
    db,
    user: CurrentUser,
    action: str,
    patient_id: str | None = None,
    table_name: str | None = None,
    record_id:  str | None = None,
    details:    dict | None = None,
    request:    Request | None = None,
):
    """Write an entry to the immutable audit_log table."""
    try:
        db.table("audit_log").insert({
            "user_id":    user.user_id,
            "user_role":  user.role,
            "action":     action,
            "patient_id": patient_id,
            "table_name": table_name,
            "record_id":  record_id,
            "details":    details,
            "ip_address": request.client.host if request else None,
        }).execute()
    except Exception:
        pass  # Never let audit failure block the main request


# ── Column masking for predictions ────────────────────────────────────────────

def mask_prediction(prediction: dict, role: str) -> dict:
    """Remove prediction fields the role is not allowed to see."""
    allowed = ROLE_ALLOWED_PREDICTION_FIELDS.get(role, set())
    if not allowed:
        return {}
    return {k: v for k, v in prediction.items() if k in allowed or k == "patient_id"}
