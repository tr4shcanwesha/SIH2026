import os
import hashlib
import hmac
import secrets
import time
import logging
from typing import Any, Callable, Optional, TypeVar

from dotenv import load_dotenv
from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ACCESS_TOKEN_COOKIE = "honeychain_access_token"
REFRESH_TOKEN_COOKIE = "honeychain_refresh_token"
SESSION_COOKIE = "honeychain_session"
ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.getenv("HONEYCHAIN_ADMIN_EMAILS", "").split(",")
    if email.strip()
}


def get_cookie_security() -> bool:
    return os.getenv("APP_ENV", "production").strip().lower() == "production"


supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
router = APIRouter(prefix="/api/auth", tags=["auth"])
T = TypeVar("T")
active_sessions: dict[str, str] = {}
pending_sessions: dict[str, str] = {}
admin_sessions: dict[str, str] = {}
logger = logging.getLogger("honeychain.auth")
PASSWORD_HASH_ITERATIONS = 310_000
DUMMY_PASSWORD_HASH = hashlib.pbkdf2_hmac(
    "sha256",
    b"HoneyChain invalid account sentinel",
    b"honeychain-login-salt",
    PASSWORD_HASH_ITERATIONS,
).hex()
DUMMY_PASSWORD_HASH = f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}$686f6e6579636861696e2d6c6f67696e2d73616c74${DUMMY_PASSWORD_HASH}"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_password: str) -> bool:
    try:
        algorithm, iteration_count, salt_hex, digest_hex = stored_password.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return hmac.compare_digest(password.encode("utf-8"), stored_password.encode("utf-8"))
        iterations = int(iteration_count)
        if not 100_000 <= iterations <= 1_000_000:
            return False
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            iterations,
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return hmac.compare_digest(password.encode("utf-8"), stored_password.encode("utf-8"))


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
        lambda: supabase.table("beekeeper").select("*").eq("email", normalized_email).limit(1).execute()
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
    profile = dict(profile)
    beekeeper_id = profile.pop("beekeeper_id", new_beekeeper_id())
    password = profile.pop("password", None) or hash_password(secrets.token_urlsafe(32))
    record = {
        "beekeeper_id": beekeeper_id,
        "email": email,
        "kyc_status": "pending",
        "password": password,
        **profile,
    }
    response = supabase.table("beekeeper").insert(
        record
    ).execute()
    if not response.data:
        raise RuntimeError("Beekeeper profile could not be created")
    return beekeeper_id


def create_session(
    *,
    beekeeper_id: Optional[str] = None,
    email: Optional[str] = None,
    admin_email: Optional[str] = None,
) -> str:
    session_id = secrets.token_urlsafe(32)
    if beekeeper_id:
        active_sessions[session_id] = beekeeper_id
    elif email:
        pending_sessions[session_id] = email
    elif admin_email:
        admin_sessions[session_id] = admin_email
    else:
        raise ValueError("A beekeeper ID, email, or admin email is required for a session")
    return session_id


def set_session_cookie(response: Any, session_id: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        path="/",
        httponly=True,
        samesite="lax",
        secure=get_cookie_security(),
        max_age=60 * 60 * 24 * 400,
    )


def session_redirect(
    destination: str,
    *,
    beekeeper_id: Optional[str] = None,
    email: Optional[str] = None,
    admin_email: Optional[str] = None,
) -> RedirectResponse:
    session_id = create_session(beekeeper_id=beekeeper_id, email=email, admin_email=admin_email)
    response = RedirectResponse(url=destination, status_code=303)
    set_session_cookie(response, session_id)
    return response


def session_json(
    destination: str,
    *,
    beekeeper_id: Optional[str] = None,
    email: Optional[str] = None,
) -> JSONResponse:
    session_id = create_session(beekeeper_id=beekeeper_id, email=email)
    response = JSONResponse({"redirect": destination})
    set_session_cookie(response, session_id)
    return response


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
    if not session_id or (
        session_id not in active_sessions
        and session_id not in pending_sessions
        and session_id not in admin_sessions
    ):
        logger.warning("Session rejected: cookie_present=%s active_sessions=%d pending_sessions=%d", bool(session_id), len(active_sessions), len(pending_sessions))
        raise HTTPException(status_code=401, detail="Authentication required")
    logger.info("Session accepted: session_prefix=%s active=%s", session_id[:8], session_id in active_sessions)
    return session_id


def get_authenticated_email(request: Request) -> str:
    session_id = get_session_id(request)
    if session_id in admin_sessions:
        return admin_sessions[session_id]
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


def require_admin(request: Request) -> str:
    session_id = get_session_id(request)
    email = admin_sessions.get(session_id)
    if not email or email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return email


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


@router.post("/login")
def password_login(payload: dict[str, str]) -> JSONResponse:
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    beekeeper = find_beekeeper(email)
    stored_password = str(beekeeper.get("password", "")) if beekeeper else ""
    valid_password = verify_password(
        password if 0 < len(password) <= 1024 else " ",
        stored_password if beekeeper and 0 < len(password) <= 1024 else DUMMY_PASSWORD_HASH,
    )
    if not beekeeper or not 0 < len(password) <= 1024 or not valid_password:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    beekeeper_id = str(beekeeper.get("beekeeper_id", ""))
    if not beekeeper_id:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not stored_password.startswith("pbkdf2_sha256$"):
        supabase.table("beekeeper").update({"password": hash_password(password)}).eq(
            "beekeeper_id", beekeeper_id
        ).execute()
    status = str(beekeeper.get("kyc_status", "pending")).strip().lower()
    destination = {
        "approved": "/dashboard",
        "rejected": "/auth?status=rejected",
    }.get(status, "/auth?status=pending")
    return session_json(destination, beekeeper_id=beekeeper_id)


@router.post("/register", include_in_schema=False)
async def register_beekeeper(
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    phone: str = Form(...),
    location: str = Form(...),
    identity_document_type: str = Form(...),
    identity_document: UploadFile = File(...),
    certificate_type: str = Form(...),
    certificate: UploadFile = File(...),
    address_document_type: str = Form(""),
    address_document: Optional[UploadFile] = File(None),
) -> JSONResponse:
    normalized_email = email.strip().lower()
    if (
        not normalized_email
        or "@" not in normalized_email
        or normalized_email.startswith("@")
        or normalized_email.endswith("@")
        or any(character.isspace() for character in normalized_email)
    ):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if len(password) > 1024:
        raise HTTPException(status_code=400, detail="Password is too long.")
    required_values = {
        "Name": name,
        "Phone": phone,
        "Location": location,
        "Identity document type": identity_document_type,
        "Certificate type": certificate_type,
    }
    missing = [field for field, value in required_values.items() if not value.strip()]
    if missing:
        raise HTTPException(status_code=400, detail=f"Required fields are missing: {', '.join(missing)}.")
    if not identity_document.filename or not certificate.filename:
        raise HTTPException(status_code=400, detail="Identity and certificate documents are required.")
    if address_document and address_document.filename and not address_document_type.strip():
        raise HTTPException(status_code=400, detail="Specify the type of address proof.")

    existing = find_beekeeper(normalized_email)
    if existing and str(existing.get("kyc_status", "")).strip().lower() == "approved":
        raise HTTPException(
            status_code=409,
            detail="This email is already registered. Please use the login page to access your account.",
        )

    beekeeper_id = str(existing.get("beekeeper_id")) if existing else new_beekeeper_id()
    from app.services.beekeepers import save_uploaded_file

    profile: dict[str, str] = {
        "name": name.strip(),
        "email": normalized_email,
        "phone": phone.strip(),
        "location": location.strip(),
        "kyc_status": "pending",
        "identity_document_type": identity_document_type.strip(),
        "identity_document_path": await save_uploaded_file(identity_document, beekeeper_id, "identity_document"),
        "certificate_type": certificate_type.strip(),
        "certificate_path": await save_uploaded_file(certificate, beekeeper_id, "certificate"),
        "password": hash_password(password),
    }
    if address_document and address_document.filename:
        profile["address_document_type"] = address_document_type.strip()
        profile["address_document_path"] = await save_uploaded_file(address_document, beekeeper_id, "address_document")
    elif existing:
        for field in ("address_document_type", "address_document_path"):
            if existing.get(field):
                profile[field] = str(existing[field])

    if existing:
        updated = (
            supabase.table("beekeeper")
            .update(profile)
            .eq("beekeeper_id", beekeeper_id)
            .execute()
        )
        if not updated.data:
            raise HTTPException(status_code=500, detail="Your application could not be updated.")
    else:
        profile["beekeeper_id"] = beekeeper_id
        create_beekeeper(normalized_email, profile)

    logger.info("Email registration saved: email=%s beekeeper_id=%s", mask_email(normalized_email), beekeeper_id)
    return session_json("/onboarding?status=pending", beekeeper_id=beekeeper_id)


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

    email = (user.user.email or "").strip().lower()
    if not email:
        return HTMLResponse(
            content='<h1>Google sign-in failed</h1><a href="/auth">Return to sign in</a>',
            status_code=401,
        )
    if email in ADMIN_EMAILS:
        logger.info("Admin Google login accepted: email=%s", mask_email(email))
        return session_redirect("/", admin_email=email)
    beekeeper = find_beekeeper_for_user(user.user)
    is_new_beekeeper = beekeeper is None
    if not beekeeper:
        beekeeper_id = create_beekeeper(
            email,
            {
                "name": "",
                "phone": "",
                "location": "",
                "identity_document_type": "",
                "identity_document_path": "",
                "address_document_type": "",
                "address_document_path": "",
                "certificate_type": "",
                "certificate_path": "",
            },
        )
        beekeeper = {"beekeeper_id": beekeeper_id, "kyc_status": "pending"}

    beekeeper_status = str(beekeeper.get("kyc_status", "pending")).strip().lower()
    profile_is_incomplete = any(
        not str(beekeeper.get(field, "")).strip()
        for field in (
            "name",
            "phone",
            "location",
            "identity_document_type",
            "identity_document_path",
            "certificate_type",
            "certificate_path",
        )
    )
    if is_new_beekeeper or (beekeeper_status == "pending" and profile_is_incomplete):
        destination = "/onboarding?edit=1"
    elif beekeeper_status == "approved":
        destination = "/dashboard"
    elif beekeeper_status == "rejected":
        destination = "/auth?status=rejected"
    else:
        destination = "/auth?status=pending"
    logger.info(
        "Google login decision: email=%s matched=%s status=%s destination=%s",
        mask_email(email),
        bool(beekeeper),
        beekeeper_status or "none",
        destination,
    )
    return session_redirect(destination, beekeeper_id=str(beekeeper["beekeeper_id"]))


@router.post("/logout", include_in_schema=False)
def admin_logout(request: Request) -> RedirectResponse:
    session_id = request.cookies.get(SESSION_COOKIE)
    active_sessions.pop(session_id, None)
    pending_sessions.pop(session_id, None)
    admin_sessions.pop(session_id, None)
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/session")
def auth_session(request: Request, authorization: Optional[str] = Header(default=None)) -> dict:
    session_id = get_session_id(request)
    return {"session_id": session_id, "beekeeper_id": active_sessions.get(session_id), "email": pending_sessions.get(session_id)}
