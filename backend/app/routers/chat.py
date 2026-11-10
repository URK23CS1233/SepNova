"""
SepNova — LLM Clinical Chat Endpoint
======================================
Role-aware chatbot powered by Anthropic Claude (or OpenAI GPT-4o).
Patient context is fetched and filtered based on the user's role BEFORE
being passed to the LLM — the model physically cannot reveal what it was never given.
"""
from __future__ import annotations
import os
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from supabase import Client

from ..auth import (
    CurrentUser, get_current_user, log_audit,
    ROLE_LLM_SCOPE, clinical_no_lab,
)
from ..database import get_supabase
from ..config import get_settings

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

# ── Request / Response models ─────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    patient_id: str | None = None
    messages: list[ChatMessage]   # full conversation history

class ChatResponse(BaseModel):
    reply: str
    patient_id: str | None = None
    role_scope: str

# ── Role-scoped patient context builder ───────────────────────────────────────

def _build_patient_context(patient_id: str, user_role: str, db: Client) -> str:
    """
    Fetch only the data the user's role is permitted to see,
    then format it as structured text for the LLM system prompt.
    """
    context_parts: list[str] = []

    # ── Patient demographics (all roles) ──────────────────────────────────────
    pat = db.table("patients").select("patient_id,age,gender,ward,icu_los,status").eq("patient_id", patient_id).single().execute()
    if not pat.data:
        return f"Patient {patient_id} not found."
    p = pat.data
    context_parts.append(
        f"Patient: {p['patient_id']} | Age: {p.get('age','?')} | "
        f"Gender: {'Male' if p.get('gender')==1 else 'Female'} | "
        f"Ward: {p.get('ward','?')} | ICU LOS: {p.get('icu_los','?')}h | Status: {p.get('status','?')}"
    )

    # ── Vitals (all except lab_technician, admin) ─────────────────────────────
    if user_role not in ("lab_technician", "admin"):
        vitals = (
            db.table("vitals").select("hour,hr,o2sat,temp,sbp,map,dbp,resp")
            .eq("patient_id", patient_id).order("hour", desc=True).limit(6).execute()
        )
        if vitals.data:
            # Role-specific column filtering
            show_cols = ["hour", "hr", "o2sat", "temp", "sbp", "map", "dbp", "resp"]
            if user_role == "surgeon":
                show_cols = ["hour", "hr", "o2sat", "sbp", "map"]
            elif user_role == "lab_technician":
                show_cols = []

            rows = []
            for r in reversed(vitals.data):
                row = {k: r.get(k) for k in show_cols if r.get(k) is not None}
                rows.append(str(row))
            context_parts.append(f"\nRecent Vitals (last 6h):\n" + "\n".join(rows))

    # ── Labs (all clinical roles) ─────────────────────────────────────────────
    if user_role != "admin":
        lab_cols = "hour,lactate,wbc,creatinine,bilirubin_total,platelets,glucose,hgb,ph,paco2,hco3,base_excess,ptt,fibrinogen"
        # Surgeons: coag + CBC only
        if user_role == "surgeon":
            lab_cols = "hour,ptt,platelets,fibrinogen,hgb,wbc"
        # Anesthesiologists: ABG + electrolytes
        elif user_role == "anesthesiologist":
            lab_cols = "hour,ph,paco2,hco3,base_excess,potassium,calcium,lactate"
        # Nurses: basic labs
        elif user_role == "nurse":
            lab_cols = "hour,wbc,hgb,glucose,lactate"

        labs = (
            db.table("lab_results").select(lab_cols)
            .eq("patient_id", patient_id).order("hour", desc=True).limit(3).execute()
        )
        if labs.data:
            rows = [str({k: v for k, v in r.items() if v is not None}) for r in reversed(labs.data)]
            context_parts.append(f"\nRecent Labs:\n" + "\n".join(rows))

    # ── Risk score (intensivist full, others get level only) ──────────────────
    if user_role in ("intensivist", "surgeon", "nurse", "anesthesiologist"):
        pred = (
            db.table("predictions").select("risk_score,risk_level,xgb_score,lgb_score,predicted_at")
            .eq("patient_id", patient_id).order("predicted_at", desc=True).limit(1).execute()
        )
        if pred.data:
            r = pred.data[0]
            if user_role == "intensivist":
                context_parts.append(
                    f"\nSepsis Risk: {r['risk_level'].upper()} | Score: {r['risk_score']:.3f} "
                    f"| XGB: {r['xgb_score']:.3f} | LGB: {r['lgb_score']:.3f} "
                    f"| Assessed: {r['predicted_at']}"
                )
            else:
                context_parts.append(f"\nSepsis Risk Level: {r['risk_level'].upper()}")

    # ── Surgical notes (intensivist + surgeon own notes) ──────────────────────
    if user_role in ("intensivist", "surgeon"):
        notes = (
            db.table("surgical_notes").select("note_type,content,procedure,created_at")
            .eq("patient_id", patient_id).order("created_at", desc=True).limit(3).execute()
        )
        if notes.data:
            note_text = "\n".join([f"[{n['note_type']}] {n.get('procedure','')} — {n['content'][:200]}" for n in notes.data])
            context_parts.append(f"\nSurgical Notes:\n{note_text}")

    # ── Anesthesia records (intensivist + anesthesiologist) ───────────────────
    if user_role in ("intensivist", "anesthesiologist"):
        anes = (
            db.table("anesthesia_records").select("agent,dose_mg,route,airway_type,etco2,fio2,recorded_at")
            .eq("patient_id", patient_id).order("recorded_at", desc=True).limit(3).execute()
        )
        if anes.data:
            anes_text = "\n".join([str({k: v for k, v in r.items() if v is not None}) for r in anes.data])
            context_parts.append(f"\nAnesthesia Records:\n{anes_text}")

    # ── Medications (intensivist + nurse) ─────────────────────────────────────
    if user_role in ("intensivist", "nurse"):
        meds = (
            db.table("medication_admin").select("drug_name,dose,route,indication,admin_time")
            .eq("patient_id", patient_id).order("admin_time", desc=True).limit(5).execute()
        )
        if meds.data:
            med_text = "\n".join([f"{m['drug_name']} {m.get('dose','')} {m.get('route','')} — {m.get('indication','')}" for m in meds.data])
            context_parts.append(f"\nMedications (recent):\n{med_text}")

    # ── Active alerts ─────────────────────────────────────────────────────────
    if user_role not in ("lab_technician", "admin"):
        alerts = (
            db.table("alerts").select("alert_type,severity,message,created_at")
            .eq("patient_id", patient_id).eq("is_acknowledged", False)
            .order("created_at", desc=True).limit(5).execute()
        )
        if alerts.data:
            alert_text = "\n".join([f"[{a['severity'].upper()}] {a['message']}" for a in alerts.data])
            context_parts.append(f"\nActive Alerts:\n{alert_text}")

    return "\n".join(context_parts)


def _build_system_prompt(user: CurrentUser, patient_context: str) -> str:
    scope = ROLE_LLM_SCOPE.get(user.role, "Unknown role.")
    return f"""You are SepChat, the clinical AI assistant embedded in SepNova — an ICU sepsis monitoring system.

USER ROLE: {user.role.upper()} — {user.full_name or ""}
DATA SCOPE: {scope}

STRICT RULES:
1. Only discuss data present in the patient context below. Never fabricate or guess clinical values.
2. Do not reveal data outside your role scope, even if the user asks directly.
3. Never provide a diagnosis, prescription, or treatment decision — always recommend consulting the attending physician.
4. If asked about data you cannot access (e.g., a nurse asking for raw ML scores), say: "That information is not available to your role."
5. Keep responses concise and clinically focused. Use medical terminology appropriate for a {user.role}.
6. Flag critical values (e.g., MAP < 65, Lactate > 4, O2Sat < 90) proactively.
7. Do not reveal other patients' data under any circumstances.

--- CURRENT PATIENT CONTEXT ---
{patient_context if patient_context else "No patient selected."}
--- END CONTEXT ---

Answer the clinician's question based only on the above context."""


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    settings = get_settings()

    if not settings.llm_api_key:
        raise HTTPException(503, "LLM not configured. Set LLM_API_KEY in backend/.env")

    # Admins and lab techs get a restricted experience
    if user.role == "admin":
        return ChatResponse(
            reply="Admin accounts do not have access to patient clinical data.",
            patient_id=req.patient_id,
            role_scope=ROLE_LLM_SCOPE["admin"],
        )

    # Build patient context filtered by role
    patient_context = ""
    if req.patient_id:
        patient_context = _build_patient_context(req.patient_id, user.role, db)

    system_prompt = _build_system_prompt(user, patient_context)

    # ── Call LLM ─────────────────────────────────────────────────────────────
    try:
        if settings.llm_provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=settings.llm_api_key)
            response = client.messages.create(
                model="claude-opus-4-8",
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": m.role, "content": m.content} for m in req.messages],
            )
            reply = response.content[0].text

        else:  # openai
            from openai import OpenAI
            client = OpenAI(api_key=settings.llm_api_key)
            messages = [{"role": "system", "content": system_prompt}]
            messages += [{"role": m.role, "content": m.content} for m in req.messages]
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=1024,
                temperature=0.2,
            )
            reply = response.choices[0].message.content

    except Exception as e:
        raise HTTPException(502, f"LLM call failed: {e}")

    # Audit log every LLM query
    await log_audit(
        db, user,
        action="llm_query",
        patient_id=req.patient_id,
        details={"question": req.messages[-1].content[:200]},
        request=request,
    )

    return ChatResponse(
        reply=reply,
        patient_id=req.patient_id,
        role_scope=ROLE_LLM_SCOPE.get(user.role, ""),
    )
