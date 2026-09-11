import os
import secrets
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
router = APIRouter(prefix="/api/auth", tags=["auth"])
ADMIN_USERNAME = "honey"
ADMIN_PASSWORD = "chain"
active_sessions: dict[str, str] = {}


def get_or_create_beekeeper(email: str) -> tuple[str, bool]:
    existing = supabase.table("beekeeper").select("beekeeper_id").eq("email", email).limit(1).execute()
    if existing.data:
        return existing.data[0]["beekeeper_id"], False

    beekeeper_id = f"bk_{secrets.token_hex(8)}"
    response = supabase.table("beekeeper").insert(
        {"beekeeper_id": beekeeper_id, "name": "", "email": email, "phone": "", "location": ""}
    ).execute()
    if not response.data:
        raise RuntimeError("Beekeeper profile could not be created")
    return beekeeper_id, True


def create_admin_session() -> str:
    session_id = secrets.token_urlsafe(32)
    active_sessions[session_id] = ""
    return session_id


def has_admin_session(session_id: Optional[str]) -> bool:
    return bool(session_id and session_id in active_sessions)


def get_session_beekeeper_id(session_id: Optional[str]) -> Optional[str]:
    return active_sessions.get(session_id) if session_id else None


@router.get("/config")
def auth_config() -> dict[str, str]:
    """Expose only the public Supabase values needed by the browser client."""
    return {
        "supabase_url": SUPABASE_URL,
        "supabase_anon_key": SUPABASE_ANON_KEY,
    }


@router.post("/login", include_in_schema=False, response_model=None)
def admin_login(
    username: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse | HTMLResponse:
    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        return HTMLResponse(
            content=(
                "<h1>Access denied</h1>"
                "<p>The username or password is incorrect.</p>"
                '<a href="/auth">Return to sign in</a>'
            ),
            status_code=401,
        )

    beekeeper_id, is_new = get_or_create_beekeeper(os.getenv("ADMIN_EMAIL", "honey@honeychain.local"))
    response = RedirectResponse(url="/onboarding" if is_new else "/dashboard", status_code=303)
    session_id = secrets.token_urlsafe(32)
    active_sessions[session_id] = beekeeper_id
    response.set_cookie(
        key="honeychain_session",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=3600,
    )
    return response


@router.post("/google-session", include_in_schema=False, response_model=None)
def google_session(access_token: str = Form(...)) -> RedirectResponse | HTMLResponse:
    try:
        user = supabase.auth.get_user(access_token)
    except Exception:
        return HTMLResponse(
            content='<h1>Google sign-in failed</h1><a href="/auth">Return to sign in</a>',
            status_code=401,
        )

    if not user.user:
        return HTMLResponse(
            content='<h1>Google sign-in failed</h1><a href="/auth">Return to sign in</a>',
            status_code=401,
        )

    beekeeper_id, is_new = get_or_create_beekeeper(user.user.email or "google-user@honeychain.local")
    response = RedirectResponse(url="/onboarding" if is_new else "/dashboard", status_code=303)
    session_id = secrets.token_urlsafe(32)
    active_sessions[session_id] = beekeeper_id
    response.set_cookie(
        key="honeychain_session",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=3600,
    )
    return response


@router.post("/logout", include_in_schema=False)
def admin_logout(request: Request) -> RedirectResponse:
    session_id = request.cookies.get("honeychain_session")
    active_sessions.pop(session_id, None)
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("honeychain_session")
    return response


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
