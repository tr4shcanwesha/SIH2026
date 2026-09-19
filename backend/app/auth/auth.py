import os
import secrets
import time
import logging
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
SESSION_COOKIE = "honeychain_session"


def get_cookie_security() -> bool:
    return os.getenv("APP_ENV", "production").strip().lower() == "production"


supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
router = APIRouter(prefix="/api/auth", tags=["auth"])
T = TypeVar("T")
active_sessions: dict[str, str] = {}
pending_sessions: dict[str, str] = {}
logger = logging.getLogger("honeychain.auth")


def mask_email(email: str) -> str:
    normalized = str(email or "").strip().lower()
    if "@" not in normalized:
        return "<missing>"
    local, domain = normalized.split("@", 1)
    return f"{local[:2]}***@{domain}"


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
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return None
    existing = execute_read_with_retry(
        lambda: supabase.table("beekeeper").select("*").ilike("email", normalized_email).limit(1).execute()
    )
    if existing.data:
        return existing.data[0]

    # Keep matching resilient if older records contain accidental whitespace.
    all_beekeepers = execute_read_with_retry(
        lambda: supabase.table("beekeeper").select("*").execute()
    )
    return next(
        (
            beekeeper
            for beekeeper in (all_beekeepers.data or [])
            if str(beekeeper.get("email", "")).strip().lower() == normalized_email
        ),
        None,
    )


def find_beekeeper_for_user(user: Any) -> Optional[dict]:
    candidates = {
        str(getattr(user, "email", "") or "").strip().lower(),
    }
    for metadata_name in ("user_metadata", "app_metadata"):
        metadata = getattr(user, metadata_name, {}) or {}
        if isinstance(metadata, dict):
            candidates.add(str(metadata.get("email", "")).strip().lower())
    for identity in getattr(user, "identities", None) or []:
        identity_data = getattr(identity, "identity_data", None) or {}
        if isinstance(identity_data, dict):
            candidates.add(str(identity_data.get("email", "")).strip().lower())

    for candidate in candidates:
        if candidate:
            beekeeper = find_beekeeper(candidate)
            if beekeeper:
                logger.info(
                    "Auth DB match: email=%s beekeeper_id=%s kyc_status=%s",
                    mask_email(candidate),
                    beekeeper.get("beekeeper_id"),
                    beekeeper.get("kyc_status"),
                )
                return beekeeper
    logger.warning("Auth DB match missing for candidate emails=%s", [mask_email(candidate) for candidate in candidates if candidate])
    return None


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


def get_session_id(request: Request) -> str:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id or (session_id not in active_sessions and session_id not in pending_sessions):
        logger.warning("Session rejected: cookie_present=%s active_sessions=%d pending_sessions=%d", bool(session_id), len(active_sessions), len(pending_sessions))
        raise HTTPException(status_code=401, detail="Authentication required")
    logger.info("Session accepted: session_prefix=%s active=%s", session_id[:8], session_id in active_sessions)
    return session_id


def get_authenticated_email(request: Request) -> str:
    session_id = get_session_id(request)
    beekeeper_id = active_sessions.get(session_id)
    if beekeeper_id:
        beekeeper = execute_read_with_retry(
            lambda: supabase.table("beekeeper").select("email").eq("beekeeper_id", beekeeper_id).limit(1).execute()
        )
        if beekeeper.data:
            return str(beekeeper.data[0].get("email", "")).strip().lower()
    email = pending_sessions.get(session_id)
    if email:
        return email
    raise HTTPException(status_code=401, detail="Authenticated user has no email")


def get_authenticated_beekeeper_id(request: Request) -> Optional[str]:
    return active_sessions.get(get_session_id(request))


def activate_beekeeper_session(request: Request, beekeeper_id: str) -> None:
    session_id = get_session_id(request)
    pending_sessions.pop(session_id, None)
    active_sessions[session_id] = beekeeper_id


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
    except Exception as error:
        logger.exception("Google token validation failed: %s", type(error).__name__)
        return HTMLResponse(
            content='<h1>Google sign-in failed</h1><a href="/auth">Return to sign in</a>',
            status_code=401,
        )

    if not user.user:
        return HTMLResponse(
            content='<h1>Google sign-in failed</h1><a href="/auth">Return to sign in</a>',
            status_code=401,
        )

    email = (user.user.email or "google-user@honeychain.local").strip().lower()
    beekeeper = find_beekeeper_for_user(user.user)
    beekeeper_status = str(beekeeper.get("kyc_status", "pending")).strip().lower() if beekeeper else None
    if not beekeeper:
        destination = "/onboarding?edit=1"
    elif beekeeper_status == "approved":
        destination = "/dashboard"
    elif beekeeper_status == "rejected":
        destination = "/onboarding?status=rejected"
    else:
        destination = "/onboarding?status=pending"
    logger.info(
        "Google login decision: email=%s matched=%s status=%s destination=%s",
        mask_email(email),
        bool(beekeeper),
        beekeeper_status or "none",
        destination,
    )
    session_id = secrets.token_urlsafe(32)
    if beekeeper:
        active_sessions[session_id] = beekeeper["beekeeper_id"]
    else:
        pending_sessions[session_id] = email
    response = RedirectResponse(url=destination, status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        path="/",
        httponly=True,
        samesite="lax",
        secure=get_cookie_security(),
        max_age=60 * 60,
    )
    return response


@router.post("/logout", include_in_schema=False)
def admin_logout(request: Request) -> RedirectResponse:
    session_id = request.cookies.get(SESSION_COOKIE)
    active_sessions.pop(session_id, None)
    pending_sessions.pop(session_id, None)
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/session")
def auth_session(request: Request, authorization: Optional[str] = Header(default=None)) -> dict:
    session_id = get_session_id(request)
    return {"session_id": session_id, "beekeeper_id": active_sessions.get(session_id), "email": pending_sessions.get(session_id)}
