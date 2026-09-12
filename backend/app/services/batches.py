import secrets
from datetime import date
from typing import Any

from fastapi import HTTPException

from app.auth.auth import supabase
from app.services.blockchain import append_batch_block


def list_hives(beekeeper_id: str) -> list[dict[str, Any]]:
    response = supabase.table("hives").select("*").eq("beekeeper_id", beekeeper_id).order("hive_id").execute()
    return response.data or []


def add_hive(payload: dict[str, Any], beekeeper_id: str) -> dict[str, Any]:
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


def create_batch(payload: dict[str, Any], beekeeper_id: str, base_url: str) -> dict[str, Any]:
    hive_response = (
        supabase.table("hives")
        .select("*")
        .eq("hive_id", payload["hive_id"])
        .eq("beekeeper_id", beekeeper_id)
        .limit(1)
        .execute()
    )
    if not hive_response.data:
        raise HTTPException(status_code=404, detail="Hive not found")

    batch_id = generate_unique_batch_id()
    payload["batch_id"] = batch_id
    payload["harvest_date"] = date.today().isoformat()
    payload["status"] = "HARVESTED"
    response = supabase.table("honey_batches").insert(payload).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Honey batch could not be created")

    beekeeper_response = supabase.table("beekeeper").select("*").eq("beekeeper_id", beekeeper_id).limit(1).execute()
    if not beekeeper_response.data:
        raise HTTPException(status_code=404, detail="Beekeeper not found")
    created_batch = response.data[0]
    append_batch_block(created_batch, hive_response.data[0], "BATCH_CREATED")
    created_batch["verification_url"] = f"{base_url}/verify/{batch_id}"
    return created_batch


def generate_unique_batch_id() -> str:
    for _ in range(5):
        batch_id = f"HB-{secrets.token_hex(4).upper()}"
        existing = supabase.table("honey_batches").select("batch_id").eq("batch_id", batch_id).limit(1).execute()
        if not existing.data:
            return batch_id
    raise HTTPException(status_code=503, detail="Unable to generate a unique batch ID")


def list_batches(beekeeper_id: str, base_url: str) -> list[dict[str, Any]]:
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
    batches = response.data or []
    for batch in batches:
        batch["verification_url"] = f"{base_url}/verify/{batch['batch_id']}"
    return batches


def update_batch_status(batch_id: str, status: str, beekeeper_id: str) -> dict[str, Any]:
    batch_response = supabase.table("honey_batches").select("*").eq("batch_id", batch_id).limit(1).execute()
    if not batch_response.data:
        raise HTTPException(status_code=404, detail="Honey batch not found")
    owned_hive = (
        supabase.table("hives")
        .select("*")
        .eq("hive_id", batch_response.data[0]["hive_id"])
        .eq("beekeeper_id", beekeeper_id)
        .limit(1)
        .execute()
    )
    if not owned_hive.data:
        raise HTTPException(status_code=404, detail="Honey batch not found")
    current_status = str(batch_response.data[0]["status"]).upper()
    expected_next = {"HARVESTED": "PROCESSED", "PROCESSED": "DISTRIBUTED"}.get(current_status)
    if status != expected_next:
        raise HTTPException(status_code=409, detail="Invalid batch status transition")
    response = supabase.table("honey_batches").update({"status": status}).eq("batch_id", batch_id).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Honey batch status could not be updated")
    beekeeper_response = supabase.table("beekeeper").select("*").eq("beekeeper_id", beekeeper_id).limit(1).execute()
    if not beekeeper_response.data:
        raise HTTPException(status_code=404, detail="Beekeeper not found")
    updated_batch = response.data[0]
    append_batch_block(updated_batch, owned_hive.data[0], f"STATUS_{status}")
    return updated_batch


def remove_hive(hive_id: str, beekeeper_id: str) -> None:
    response = supabase.table("hives").delete().eq("hive_id", hive_id).eq("beekeeper_id", beekeeper_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Hive not found")