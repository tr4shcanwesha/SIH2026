from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.auth.auth import get_authenticated_beekeeper_id, get_authenticated_user, get_beekeeper_status_by_id

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
    return FileResponse(FRONTEND_DIR / "landing" / "landing.html")


@router.get("/auth", include_in_schema=False)
def auth_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "auth" / "auth.html")


@router.get("/dashboard", include_in_schema=False, response_model=None)
def dashboard_page(request: Request) -> FileResponse | RedirectResponse:
    try:
        get_authenticated_user(request)
    except HTTPException:
        return RedirectResponse(url="/auth", status_code=303)
    beekeeper_id = get_authenticated_beekeeper_id(request)
    if get_beekeeper_status_by_id(beekeeper_id) != "approved":
        return RedirectResponse(url="/onboarding?status=pending", status_code=303)
    return HTMLResponse(render_dashboard_shell())


@router.get("/onboarding", include_in_schema=False, response_model=None)
def onboarding_page(request: Request) -> FileResponse | RedirectResponse:
    try:
        get_authenticated_user(request)
    except HTTPException:
        return RedirectResponse(url="/auth", status_code=303)
    beekeeper_id = get_authenticated_beekeeper_id(request)
    if get_beekeeper_status_by_id(beekeeper_id) == "approved":
        return RedirectResponse(url="/dashboard", status_code=303)
    return FileResponse(FRONTEND_DIR / "auth" / "onboarding.html")


@router.get("/profile", include_in_schema=False, response_model=None)
def profile_page(request: Request) -> FileResponse | RedirectResponse:
    try:
        get_authenticated_user(request)
    except HTTPException:
        return RedirectResponse(url="/auth", status_code=303)
    beekeeper_id = get_authenticated_beekeeper_id(request)
    if get_beekeeper_status_by_id(beekeeper_id) != "approved":
        return RedirectResponse(url="/onboarding?status=pending", status_code=303)
    return FileResponse(FRONTEND_DIR / "dashboard" / "profile.html")


@router.get("/dashboard/{view_name}", include_in_schema=False, response_model=None)
def dashboard_view(request: Request, view_name: str) -> HTMLResponse | RedirectResponse:
    try:
        get_authenticated_user(request)
    except HTTPException:
        return RedirectResponse(url="/auth", status_code=303)
    try:
        filename = DASHBOARD_VIEWS[view_name]
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Dashboard view not found") from error
    view_file = FRONTEND_DIR / "dashboard" / filename
    dashboard_html = render_dashboard_shell()
    view_html = view_file.read_text(encoding="utf-8")
    content_start = dashboard_html.index('<main class="dash-main')
    content_end = dashboard_html.index("</main>", content_start)
    rendered_html = (
        dashboard_html[:content_start]
        + '<main class="dash-main" id="dashboard-content">\n'
        + view_html
        + "\n"
        + dashboard_html[content_end:]
    )
    return HTMLResponse(rendered_html)


@router.get("/dashboard/batches/{batch_id}", include_in_schema=False, response_model=None)
def batch_detail_page(request: Request, batch_id: str) -> FileResponse | RedirectResponse:
    try:
        get_authenticated_user(request)
    except HTTPException:
        return RedirectResponse(url="/auth", status_code=303)
    return FileResponse(FRONTEND_DIR / "dashboard" / "batch.html")


@router.get("/verify", include_in_schema=False)
def verify_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "verify" / "verify.html")


@router.get("/verify/{batch_id}", include_in_schema=False)
def verify_batch_page(batch_id: str) -> FileResponse:
    return FileResponse(FRONTEND_DIR / "verify" / "verify.html")


@router.get("/assets/landing/style.css", include_in_schema=False)
def landing_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "landing" / "style.css")


@router.get("/assets/auth/style.css", include_in_schema=False)
def auth_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "auth" / "style.css")


@router.get("/assets/auth/auth.js", include_in_schema=False)
def auth_script() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "auth" / "auth.js")


@router.get("/assets/auth/onboarding.js", include_in_schema=False)
def onboarding_script() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "auth" / "onboarding.js")


@router.get("/assets/dashboard/profile.js", include_in_schema=False)
def profile_script() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "dashboard" / "profile.js")


@router.get("/assets/auth/logout.js", include_in_schema=False)
def logout_script() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "auth" / "logout.js")


@router.get("/assets/auth/session.js", include_in_schema=False)
def session_script() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "auth" / "session.js")


@router.get("/assets/dashboard/style.css", include_in_schema=False)
def dashboard_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "dashboard" / "style.css")


@router.get("/assets/dashboard/assistant.css", include_in_schema=False)
def assistant_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "dashboard" / "assistant.css")


@router.get("/assets/dashboard/dashboard.js", include_in_schema=False)
def dashboard_script() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "dashboard" / "dashboard.js")


@router.get("/assets/dashboard/assistant.js", include_in_schema=False)
def assistant_script() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "dashboard" / "assistant.js")


@router.get("/assets/dashboard/batch.css", include_in_schema=False)
def batch_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "dashboard" / "batch.css")


@router.get("/assets/dashboard/batch.js", include_in_schema=False)
def batch_script() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "dashboard" / "batch.js")


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


@router.get("/src/images/{filename}", include_in_schema=False)
def serve_frontend_image(filename: str) -> FileResponse:
    image_path = FRONTEND_DIR / "src" / "images" / filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path)


@router.get("/assets/verify/style.css", include_in_schema=False)
def verify_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "verify" / "style.css")
