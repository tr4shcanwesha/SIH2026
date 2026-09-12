from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.auth.auth import has_admin_session

router = APIRouter()
FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"
DASHBOARD_VIEWS = {
    "my-hives": "my-hives.html",
    "my-harvest": "my-harvest.html",
    "alerts": "alerts.html",
    "reports": "reports.html",
    "ai-assistant": "ai-assistant.html",
}


def render_dashboard_shell() -> str:
    dashboard_file = FRONTEND_DIR / "dashboard" / "dashboard.html"
    dashboard_html = dashboard_file.read_text(encoding="utf-8")
    for slot_id, partial_name in (
        ("nav-alerts-slot", "nav-alerts.html"),
        ("nav-profile-slot", "nav-profile.html"),
    ):
        partial = (FRONTEND_DIR / "dashboard" / partial_name).read_text(encoding="utf-8")
        dashboard_html = dashboard_html.replace(
            f'<div id="{slot_id}"></div>',
            partial,
        )
    return dashboard_html


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
    return HTMLResponse(render_dashboard_shell())


@router.get("/dashboard/{view_name}", include_in_schema=False, response_model=None)
def dashboard_view(request: Request, view_name: str) -> HTMLResponse | RedirectResponse:
    if not has_admin_session(request.cookies.get("honeychain_session")):
        return RedirectResponse(url="/auth", status_code=303)
    try:
        filename = DASHBOARD_VIEWS[view_name]
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Dashboard view not found") from error
    view_file = FRONTEND_DIR / "dashboard" / filename
    dashboard_html = render_dashboard_shell()
    view_html = view_file.read_text(encoding="utf-8")
    content_start = dashboard_html.index('<main class="dash-main" id="dashboard-content">')
    content_end = dashboard_html.index("</main>", content_start)
    rendered_html = (
        dashboard_html[:content_start]
        + '<main class="dash-main" id="dashboard-content">\n'
        + view_html
        + "\n"
        + dashboard_html[content_end:]
    )
    return HTMLResponse(rendered_html)


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


@router.get("/assets/dashboard/dashboard.js", include_in_schema=False)
def dashboard_script() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "dashboard" / "dashboard.js")


@router.get("/assets/dashboard/db.png", include_in_schema=False)
def dashboard_db_image() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "src" / "images" / "db.png")


@router.get("/assets/dashboard/hive.png", include_in_schema=False)
def dashboard_hive_image() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "src" / "images" / "hive.png")


@router.get("/assets/dashboard/harvest.png", include_in_schema=False)
def dashboard_harvest_image() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "src" / "images" / "harvest.png")


@router.get("/assets/dashboard/processed.png", include_in_schema=False)
def dashboard_processed_image() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "src" / "images" / "processed.png")


@router.get("/assets/dashboard/distributed.png", include_in_schema=False)
def dashboard_distributed_image() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "src" / "images" / "distributed.png")


@router.get("/assets/dashboard/jar.png", include_in_schema=False)
def dashboard_jar_image() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "src" / "images" / "jar.png")


@router.get("/assets/verify/style.css", include_in_schema=False)
def verify_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "verify" / "style.css")


@router.get("/assets/homepage/style.css", include_in_schema=False)
def homepage_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "homepage" / "style.css")
