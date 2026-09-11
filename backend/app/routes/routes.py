from fastapi import APIRouter

from app.auth.auth import router as auth_router

router = APIRouter()


@router.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


router.include_router(auth_router)
