from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth.auth import active_sessions, get_session_beekeeper_id, router as auth_router
from app.routing.router import router as page_router
from app.services.batches import (
    add_hive as add_hive_record,
    create_batch,
    list_batches,
    list_hives as list_hive_records,
    remove_hive as remove_hive_record,
    update_batch_status,
)
from app.services.blockchain import get_batch_verification
from app.services.beekeepers import delete_beekeeper_account, get_beekeeper_profile, update_beekeeper_profile

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
    quantity: float = Field(gt=0)


class HoneyBatchStatusUpdate(BaseModel):
    status: Literal["PROCESSED", "DISTRIBUTED"]


class BeekeeperProfileUpdate(BaseModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    location: str = Field(min_length=1)


@router.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/profile")
def profile(request: Request) -> dict[str, Any]:
    return get_beekeeper_profile(current_beekeeper_id(request))


@router.patch("/api/profile")
def update_profile(profile_update: BeekeeperProfileUpdate, request: Request) -> dict[str, Any]:
    beekeeper_id = current_beekeeper_id(request)
    update_beekeeper_profile(beekeeper_id, profile_update.model_dump())
    return get_beekeeper_profile(beekeeper_id)


@router.delete("/api/profile", status_code=204)
def delete_profile(request: Request) -> None:
    session_id = request.cookies.get("honeychain_session")
    beekeeper_id = current_beekeeper_id(request)
    delete_beekeeper_account(beekeeper_id)
    active_sessions.pop(session_id, None)


def current_beekeeper_id(request: Request) -> str:
    beekeeper_id = get_session_beekeeper_id(request.cookies.get("honeychain_session"))
    if not beekeeper_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return beekeeper_id


@router.get("/api/hives")
def list_hives(request: Request) -> list[dict[str, Any]]:
    beekeeper_id = current_beekeeper_id(request)
    return list_hive_records(beekeeper_id)


@router.post("/api/hives", status_code=201)
def add_hive(hive: HiveCreate, request: Request) -> dict[str, Any]:
    beekeeper_id = current_beekeeper_id(request)
    return add_hive_record(hive.model_dump(), beekeeper_id)


@router.post("/api/honey-batches", status_code=201)
def create_honey_batch(batch: HoneyBatchCreate, request: Request) -> dict[str, Any]:
    beekeeper_id = current_beekeeper_id(request)
    return create_batch(batch.model_dump(mode="json"), beekeeper_id, str(request.base_url).rstrip("/"))


@router.get("/api/honey-batches")
def list_honey_batches(request: Request) -> list[dict[str, Any]]:
    beekeeper_id = current_beekeeper_id(request)
    return list_batches(beekeeper_id, str(request.base_url).rstrip("/"))


@router.get("/api/public/batches/{batch_id}")
def get_public_batch(batch_id: str) -> dict[str, Any]:
    return get_batch_verification(batch_id)


@router.patch("/api/honey-batches/{batch_id}")
def update_honey_batch_status(
    batch_id: str,
    status_update: HoneyBatchStatusUpdate,
    request: Request,
) -> dict[str, Any]:
    beekeeper_id = current_beekeeper_id(request)
    return update_batch_status(batch_id, status_update.status, beekeeper_id)


@router.delete("/api/hives/{hive_id}", status_code=204)
def remove_hive(hive_id: str, request: Request) -> None:
    beekeeper_id = current_beekeeper_id(request)
    remove_hive_record(hive_id, beekeeper_id)


router.include_router(auth_router)
router.include_router(page_router)
