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
active_sessions: set[str] = set()


def create_admin_session() -> str:
    session_id = secrets.token_urlsafe(32)
    active_sessions.add(session_id)
    return session_id


def has_admin_session(session_id: Optional[str]) -> bool:
    return bool(session_id and session_id in active_sessions)


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

    response = RedirectResponse(url="/homepage", status_code=303)
    response.set_cookie(
        key="honeychain_session",
        value=create_admin_session(),
        httponly=True,
        samesite="lax",
        max_age=3600,
    )
    return response


@router.post("/logout", include_in_schema=False)
def admin_logout(request: Request) -> RedirectResponse:
    session_id = request.cookies.get("honeychain_session")
    active_sessions.discard(session_id)
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
