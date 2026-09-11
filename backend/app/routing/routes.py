import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.auth.auth import get_session_beekeeper_id, router as auth_router, supabase
from app.routing.router import router as page_router

router = APIRouter()


class HiveCreate(BaseModel):
    location: str
    bee_species: str
    hive_type: str
    installation_date: str
    status: str = "Healthy"


@router.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


def current_beekeeper_id(request: Request) -> str:
    beekeeper_id = get_session_beekeeper_id(request.cookies.get("honeychain_session"))
    if not beekeeper_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return beekeeper_id


@router.get("/api/hives")
def list_hives(request: Request) -> list[dict[str, Any]]:
    beekeeper_id = current_beekeeper_id(request)
    response = supabase.table("hives").select("*").eq("beekeeper_id", beekeeper_id).order("hive_id").execute()
    return response.data or []


@router.post("/api/hives", status_code=201)
def add_hive(hive: HiveCreate, request: Request) -> dict[str, Any]:
    beekeeper_id = current_beekeeper_id(request)
    payload = hive.model_dump()
    payload["hive_id"] = generate_unique_hive_id()
    payload["beekeeper_id"] = beekeeper_id
    response = supabase.table("hives").insert(payload).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Hive could not be added")
    return response.data[0]


def generate_unique_hive_id() -> str:
    for _ in range(5):
        hive_id = f"HC-{secrets.token_hex(4).upper()}"
        existing = supabase.table("hives").select("hive_id").eq("hive_id", hive_id).limit(1).execute()
        if not existing.data:
            return hive_id
    raise HTTPException(status_code=503, detail="Unable to generate a unique hive ID")


@router.delete("/api/hives/{hive_id}", status_code=204)
def remove_hive(hive_id: str, request: Request) -> None:
    beekeeper_id = current_beekeeper_id(request)
    response = (
        supabase.table("hives")
        .delete()
        .eq("hive_id", hive_id)
        .eq("beekeeper_id", beekeeper_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Hive not found")


router.include_router(auth_router)
router.include_router(page_router)
