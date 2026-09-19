import os
import secrets
import time
from typing import Any, Callable, Optional, TypeVar

from dotenv import load_dotenv
from fastapi import APIRouter, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ACCESS_TOKEN_COOKIE = "honeychain_access_token"
REFRESH_TOKEN_COOKIE = "honeychain_refresh_token"


def get_cookie_security() -> bool:
    return os.getenv("APP_ENV", "production").strip().lower() == "production"


supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
router = APIRouter(prefix="/api/auth", tags=["auth"])
T = TypeVar("T")


def execute_read_with_retry(query: Callable[[], T], attempts: int = 2) -> T:
    """Retry read-only Supabase calls after a transient connection drop."""
    for attempt in range(attempts):
        try:
            return query()
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(0.2)
    raise RuntimeError("Supabase read failed")


def new_beekeeper_id() -> str:
    return f"bk_{secrets.token_hex(8)}"


def find_beekeeper(email: str) -> Optional[dict]:
    existing = supabase.table("beekeeper").select("*").eq("email", email).limit(1).execute()
    return existing.data[0] if existing.data else None


def create_beekeeper(email: str, profile: dict[str, str]) -> str:
    beekeeper_id = profile.pop("beekeeper_id", new_beekeeper_id())
    record = {
        "beekeeper_id": beekeeper_id,
        "email": email,
        "kyc_status": "pending",
        **profile,
    }
    response = supabase.table("beekeeper").insert(
        record
    ).execute()
    if not response.data:
        raise RuntimeError("Beekeeper profile could not be created")
    return beekeeper_id


def get_beekeeper_status(email: str) -> str:
    response = supabase.table("beekeeper").select("kyc_status").eq("email", email).limit(1).execute()
    if not response.data:
        return "pending"
    status = str(response.data[0].get("kyc_status", "pending")).strip().lower()
    return status if status in {"pending", "approved", "rejected"} else "pending"


def get_beekeeper_status_by_id(beekeeper_id: Optional[str]) -> str:
    if not beekeeper_id:
        return "pending"
    response = supabase.table("beekeeper").select("kyc_status").eq("beekeeper_id", beekeeper_id).limit(1).execute()
    if not response.data:
        return "pending"
    status = str(response.data[0].get("kyc_status", "pending")).strip().lower()
    return status if status in {"pending", "approved", "rejected"} else "pending"


def get_authenticated_user(request: Request) -> Any:
    cached_user = getattr(request.state, "supabase_user", None)
    if cached_user:
        return cached_user

    access_token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if access_token:
        for attempt in range(2):
            try:
                user_response = supabase.auth.get_user(access_token)
                if user_response.user:
                    request.state.supabase_user = user_response.user
                    return user_response.user
            except Exception:
                if attempt == 0:
                    time.sleep(0.15)

    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if refresh_token:
        for attempt in range(2):
            try:
                session_response = supabase.auth.refresh_session(refresh_token)
                session = getattr(session_response, "session", None)
                user = getattr(session_response, "user", None)
                if session and user:
                    request.state.supabase_user = user
                    request.state.supabase_session = session
                    return user
            except Exception:
                if attempt == 0:
                    time.sleep(0.15)

    raise HTTPException(status_code=401, detail="Authentication required")


def get_authenticated_email(request: Request) -> str:
    user = get_authenticated_user(request)
    email = getattr(user, "email", None)
    if not email:
        raise HTTPException(status_code=401, detail="Authenticated user has no email")
    return email


def get_authenticated_beekeeper_id(request: Request) -> Optional[str]:
    beekeeper = find_beekeeper(get_authenticated_email(request))
    return beekeeper.get("beekeeper_id") if beekeeper else None


def set_refreshed_auth_cookies(request: Request, response: Any) -> None:
    session = getattr(request.state, "supabase_session", None)
    if not session:
        return
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=session.access_token,
        path="/",
        httponly=True,
        samesite="lax",
        secure=get_cookie_security(),
        max_age=session.expires_in or 3600,
    )
    if session.refresh_token:
        response.set_cookie(
            key=REFRESH_TOKEN_COOKIE,
            value=session.refresh_token,
            path="/",
            httponly=True,
            samesite="lax",
            secure=get_cookie_security(),
            max_age=60 * 60 * 24 * 30,
        )


@router.get("/config")
def auth_config() -> dict[str, str]:
    """Expose only the public Supabase values needed by the browser client."""
    return {
        "supabase_url": SUPABASE_URL,
        "supabase_anon_key": SUPABASE_ANON_KEY,
    }


@router.post("/google-session", include_in_schema=False, response_model=None)
def google_session(access_token: str = Form(...), refresh_token: str = Form("")) -> RedirectResponse | HTMLResponse:
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

    email = user.user.email or "google-user@honeychain.local"
    beekeeper = find_beekeeper(email)
    beekeeper_status = get_beekeeper_status(email) if beekeeper else None
    if not beekeeper:
        destination = "/onboarding?edit=1"
    elif beekeeper_status == "approved":
        destination = "/dashboard"
    elif beekeeper_status == "rejected":
        destination = "/onboarding?status=rejected"
    else:
        destination = "/onboarding?status=pending"
    response = RedirectResponse(url=destination, status_code=303)
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        path="/",
        httponly=True,
        samesite="lax",
        secure=get_cookie_security(),
        max_age=3600,
    )
    if refresh_token:
        response.set_cookie(
            key=REFRESH_TOKEN_COOKIE,
            value=refresh_token,
            path="/",
            httponly=True,
            samesite="lax",
            secure=get_cookie_security(),
            max_age=60 * 60 * 24 * 30,
        )
    return response


@router.post("/logout", include_in_schema=False)
def admin_logout(request: Request) -> RedirectResponse:
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/")
    return response


@router.get("/session")
def auth_session(request: Request, authorization: Optional[str] = Header(default=None)) -> dict:
    access_token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if authorization and authorization.startswith("Bearer "):
        access_token = authorization.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=401, detail="A Supabase access token is required")
    try:
        user = supabase.auth.get_user(access_token)
    except Exception as error:
        raise HTTPException(status_code=401, detail="Invalid Supabase access token") from error

    return {"user": user.user.model_dump() if user.user else None}
