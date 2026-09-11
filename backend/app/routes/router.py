from pathlib import Path

from fastapi import APIRouter
from fastapi import Request
from fastapi.responses import FileResponse, RedirectResponse

from app.auth.auth import has_admin_session

router = APIRouter()
FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"


@router.get("/", include_in_schema=False)
def landing_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "home" / "home.html")


@router.get("/auth", include_in_schema=False)
def auth_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "auth" / "auth.html")


@router.get("/dashboard", include_in_schema=False, response_model=None)
def dashboard_page(request: Request) -> FileResponse | RedirectResponse:
    if not has_admin_session(request.cookies.get("honeychain_session")):
        return RedirectResponse(url="/auth", status_code=303)
    return FileResponse(FRONTEND_DIR / "dashboard" / "dashboard.html")


@router.get("/homepage", include_in_schema=False, response_model=None)
def homepage(request: Request) -> FileResponse | RedirectResponse:
    if not has_admin_session(request.cookies.get("honeychain_session")):
        return RedirectResponse(url="/auth", status_code=303)
    return FileResponse(FRONTEND_DIR / "homepage" / "homepage.html")


@router.get("/verify", include_in_schema=False)
def verify_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "verify" / "verify.html")


@router.get("/assets/home/style.css", include_in_schema=False)
def home_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "home" / "style.css")


@router.get("/assets/auth/style.css", include_in_schema=False)
def auth_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "auth" / "style.css")


@router.get("/assets/auth/auth.js", include_in_schema=False)
def auth_script() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "auth" / "auth.js")


@router.get("/assets/auth/logout.js", include_in_schema=False)
def logout_script() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "auth" / "logout.js")


@router.get("/assets/dashboard/style.css", include_in_schema=False)
def dashboard_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "dashboard" / "style.css")


@router.get("/assets/verify/style.css", include_in_schema=False)
def verify_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "verify" / "style.css")


@router.get("/assets/homepage/style.css", include_in_schema=False)
def homepage_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "homepage" / "style.css")
