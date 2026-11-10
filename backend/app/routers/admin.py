"""
SepNova — Admin Router
=======================
User management endpoints. Admin role only.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client

from ..auth import CurrentUser, admin_only, log_audit
from ..database import get_supabase

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

VALID_ROLES = {"intensivist", "surgeon", "nurse", "anesthesiologist", "lab_technician", "admin"}


class UserUpdate(BaseModel):
    role:       str | None = None
    ward:       str | None = None
    full_name:  str | None = None
    is_active:  bool | None = None


class InviteUser(BaseModel):
    email:      str
    full_name:  str
    role:       str
    ward:       str | None = None
    employee_id: str | None = None


@router.get("/users")
async def list_users(
    user: CurrentUser = Depends(admin_only),
    db: Client = Depends(get_supabase),
):
    res = db.table("user_profiles").select("*").order("created_at", desc=True).execute()
    return res.data or []


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UserUpdate,
    user: CurrentUser = Depends(admin_only),
    db: Client = Depends(get_supabase),
):
    if body.role and body.role not in VALID_ROLES:
        raise HTTPException(400, f"Invalid role. Must be one of: {list(VALID_ROLES)}")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "No fields to update")

    db.table("user_profiles").update(updates).eq("id", user_id).execute()
    await log_audit(db, user, action="admin_update_user", record_id=user_id, details=updates)
    return {"status": "updated", "user_id": user_id, "changes": updates}


@router.post("/users/invite")
async def invite_user(
    body: InviteUser,
    user: CurrentUser = Depends(admin_only),
    db: Client = Depends(get_supabase),
):
    """
    Invite a new user by email. Supabase sends them a setup link.
    Role is set in app_metadata so it appears in the JWT.
    """
    from ..config import get_settings
    from supabase import create_client

    settings = get_settings()
    if body.role not in VALID_ROLES:
        raise HTTPException(400, f"Invalid role '{body.role}'")

    # Use service role to create user in Supabase Auth
    admin_client = create_client(settings.supabase_url, settings.supabase_service_key)
    try:
        res = admin_client.auth.admin.create_user({
            "email": body.email,
            "email_confirm": True,
            "app_metadata": {"role": body.role},
            "user_metadata": {"full_name": body.full_name},
        })
        new_user_id = res.user.id

        # Upsert profile
        db.table("user_profiles").upsert({
            "id":          new_user_id,
            "full_name":   body.full_name,
            "role":        body.role,
            "ward":        body.ward,
            "employee_id": body.employee_id,
        }).execute()

    except Exception as e:
        raise HTTPException(400, f"Failed to create user: {e}")

    await log_audit(db, user, action="admin_invite_user", details={"email": body.email, "role": body.role})
    return {"status": "invited", "user_id": new_user_id, "email": body.email, "role": body.role}


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    user: CurrentUser = Depends(admin_only),
    db: Client = Depends(get_supabase),
):
    """Soft-delete: mark as inactive. Does not delete auth.users record."""
    db.table("user_profiles").update({"is_active": False}).eq("id", user_id).execute()
    await log_audit(db, user, action="admin_deactivate_user", record_id=user_id)
    return {"status": "deactivated", "user_id": user_id}


@router.get("/audit-log")
async def get_audit_log(
    limit: int = 100,
    user: CurrentUser = Depends(admin_only),
    db: Client = Depends(get_supabase),
):
    res = (
        db.table("audit_log").select("*")
        .order("created_at", desc=True).limit(limit).execute()
    )
    return res.data or []
