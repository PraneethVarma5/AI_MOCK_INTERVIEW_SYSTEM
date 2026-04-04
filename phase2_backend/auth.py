# auth.py
"""
Pure Supabase Auth helper routes for InterviewAI.
Frontend handles:
- sign up
- email verification (Supabase built-in email)
- login
- forgot password email
- password update after recovery redirect

Backend handles only:
- guest session
- me (read current user from JWT)
- logout (best effort)
- profile sync (optional)
"""

import os
import string
import random
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
from supabase_client import get_supabase, get_supabase_admin

load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])


# ── MODELS ─────────────────────────────────────────────────────────────────────

class SyncProfileRequest(BaseModel):
    email: EmailStr
    full_name: str = ""


# ── HELPERS ────────────────────────────────────────────────────────────────────

def _generate_guest_id(length: int = 12) -> str:
    chars = string.ascii_lowercase + string.digits
    return "guest_" + "".join(random.choices(chars, k=length))


# ── PROFILE SYNC (OPTIONAL) ───────────────────────────────────────────────────
# Called by frontend after successful signup/login to ensure profiles table has row.

@router.post("/sync-profile")
async def sync_profile(req: SyncProfileRequest, request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sb = get_supabase()
    sb_admin = get_supabase_admin()

    try:
        user_resp = sb.auth.get_user(token)
        if not user_resp or not user_resp.user:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = user_resp.user
        user_id = str(user.id)

        sb_admin.table("profiles").upsert({
            "id": user_id,
            "email": user.email,
            "full_name": req.full_name or (user.user_metadata or {}).get("full_name", ""),
        }).execute()

        return {"message": "Profile synced", "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile sync failed: {str(e)}")


# ── GET CURRENT USER ──────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sb = get_supabase()

    try:
        user_resp = sb.auth.get_user(token)
        if not user_resp or not user_resp.user:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = user_resp.user
        return {
            "id": str(user.id),
            "email": user.email,
            "full_name": (user.user_metadata or {}).get("full_name", ""),
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed")


# ── LOGOUT ────────────────────────────────────────────────────────────────────
# Frontend already clears local state. This is just a best-effort sign out.

@router.post("/logout")
async def logout():
    try:
        sb = get_supabase()
        sb.auth.sign_out()
    except Exception:
        pass
    return {"message": "Logged out successfully"}


# ── GUEST ─────────────────────────────────────────────────────────────────────

@router.post("/guest")
async def create_guest():
    return {
        "guest_id": _generate_guest_id(),
        "is_guest": True,
        "message": "Guest session created. Progress won't be saved.",
        "access_token": None,
    }