import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/config")
def auth_config() -> dict[str, str]:
    """Expose only the public Supabase values needed by the browser client."""
    return {
        "supabase_url": SUPABASE_URL,
        "supabase_anon_key": SUPABASE_ANON_KEY,
    }


@router.get("/session")
def auth_session(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="A Supabase access token is required")

    access_token = authorization.removeprefix("Bearer ").strip()
    try:
        user = supabase.auth.get_user(access_token)
    except Exception as error:
        raise HTTPException(status_code=401, detail="Invalid Supabase access token") from error

    return {"user": user.user.model_dump() if user.user else None}
