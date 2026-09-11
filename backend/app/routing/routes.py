import secrets
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth.auth import get_session_beekeeper_id, router as auth_router, supabase
from app.routing.router import router as page_router

router = APIRouter()


class HiveCreate(BaseModel):
    location: str
    bee_species: str
    hive_type: str
    installation_date: str
    status: str = "Healthy"


class HoneyBatchCreate(BaseModel):
    hive_id: str
    honey_type: str = "Wild Forest Honey"
    harvest_date: date
    quantity: float = Field(gt=0)


class HoneyBatchStatusUpdate(BaseModel):
    status: Literal["PROCESSED", "DISTRIBUTED"]


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


@router.post("/api/honey-batches", status_code=201)
def create_honey_batch(batch: HoneyBatchCreate, request: Request) -> dict[str, Any]:
    beekeeper_id = current_beekeeper_id(request)
    hive = (
        supabase.table("hives")
        .select("hive_id")
        .eq("hive_id", batch.hive_id)
        .eq("beekeeper_id", beekeeper_id)
        .limit(1)
        .execute()
    )
    if not hive.data:
        raise HTTPException(status_code=404, detail="Hive not found")

    batch_id = generate_unique_batch_id()
    payload = batch.model_dump(mode="json")
    payload["batch_id"] = batch_id
    payload["status"] = "HARVESTED"
    response = supabase.table("honey_batches").insert(payload).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Honey batch could not be created")
    return response.data[0]


def generate_unique_batch_id() -> str:
    for _ in range(5):
        batch_id = f"HB-{secrets.token_hex(4).upper()}"
        existing = supabase.table("honey_batches").select("batch_id").eq("batch_id", batch_id).limit(1).execute()
        if not existing.data:
            return batch_id
    raise HTTPException(status_code=503, detail="Unable to generate a unique batch ID")


@router.get("/api/honey-batches")
def list_honey_batches(request: Request) -> list[dict[str, Any]]:
    beekeeper_id = current_beekeeper_id(request)
    hives = supabase.table("hives").select("hive_id").eq("beekeeper_id", beekeeper_id).execute()
    hive_ids = [hive["hive_id"] for hive in (hives.data or [])]
    if not hive_ids:
        return []

    response = (
        supabase.table("honey_batches")
        .select("*")
        .in_("hive_id", hive_ids)
        .order("harvest_date", desc=True)
        .execute()
    )
    return response.data or []


@router.patch("/api/honey-batches/{batch_id}")
def update_honey_batch_status(
    batch_id: str,
    status_update: HoneyBatchStatusUpdate,
    request: Request,
) -> dict[str, Any]:
    beekeeper_id = current_beekeeper_id(request)
    batch = supabase.table("honey_batches").select("*").eq("batch_id", batch_id).limit(1).execute()
    if not batch.data:
        raise HTTPException(status_code=404, detail="Honey batch not found")

    owned_hive = (
        supabase.table("hives")
        .select("hive_id")
        .eq("hive_id", batch.data[0]["hive_id"])
        .eq("beekeeper_id", beekeeper_id)
        .limit(1)
        .execute()
    )
    if not owned_hive.data:
        raise HTTPException(status_code=404, detail="Honey batch not found")

    current_status = str(batch.data[0]["status"]).upper()
    expected_next = {"HARVESTED": "PROCESSED", "PROCESSED": "DISTRIBUTED"}.get(current_status)
    if status_update.status != expected_next:
        raise HTTPException(status_code=409, detail="Invalid batch status transition")

    response = (
        supabase.table("honey_batches")
        .update({"status": status_update.status})
        .eq("batch_id", batch_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=400, detail="Honey batch status could not be updated")
    return response.data[0]


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
