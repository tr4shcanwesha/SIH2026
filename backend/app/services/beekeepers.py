from typing import Any

from fastapi import HTTPException

from app.auth.auth import supabase


def get_beekeeper_profile(beekeeper_id: str) -> dict[str, Any]:
    beekeeper_response = (
        supabase.table("beekeeper")
        .select("*")
        .eq("beekeeper_id", beekeeper_id)
        .limit(1)
        .execute()
    )
    if not beekeeper_response.data:
        raise HTTPException(status_code=404, detail="Beekeeper not found")

    beekeeper = beekeeper_response.data[0]
    hives_response = supabase.table("hives").select("hive_id").eq("beekeeper_id", beekeeper_id).execute()
    hive_ids = [hive["hive_id"] for hive in (hives_response.data or [])]
    batches = []
    if hive_ids:
        batches_response = supabase.table("honey_batches").select("status").in_("hive_id", hive_ids).execute()
        batches = batches_response.data or []

    status_counts = {"HARVESTED": 0, "PROCESSED": 0, "DISTRIBUTED": 0}
    for batch in batches:
        status = str(batch.get("status", "")).upper()
        if status in status_counts:
            status_counts["HARVESTED"] += 1
        if status in {"PROCESSED", "DISTRIBUTED"}:
            status_counts["PROCESSED"] += 1
        if status == "DISTRIBUTED":
            status_counts["DISTRIBUTED"] += 1

    return {
        "beekeeper": beekeeper,
        "stats": {
            "hives": len(hive_ids),
            "harvested": status_counts["HARVESTED"],
            "processed": status_counts["PROCESSED"],
            "distributed": status_counts["DISTRIBUTED"],
        },
    }


def update_beekeeper_profile(beekeeper_id: str, payload: dict[str, str]) -> dict[str, Any]:
    response = (
        supabase.table("beekeeper")
        .update(payload)
        .eq("beekeeper_id", beekeeper_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=400, detail="Beekeeper profile could not be updated")
    return response.data[0]


def delete_beekeeper_account(beekeeper_id: str) -> None:
    hives_response = supabase.table("hives").select("hive_id").eq("beekeeper_id", beekeeper_id).execute()
    hive_ids = [hive["hive_id"] for hive in (hives_response.data or [])]
    batch_ids: list[str] = []
    if hive_ids:
        batches_response = supabase.table("honey_batches").select("batch_id").in_("hive_id", hive_ids).execute()
        batch_ids = [batch["batch_id"] for batch in (batches_response.data or [])]

    if batch_ids:
        supabase.table("blockchain_blocks").update({"batch_id": None}).in_("batch_id", batch_ids).execute()
        supabase.table("honey_batches").delete().in_("batch_id", batch_ids).execute()
    if hive_ids:
        supabase.table("hives").delete().in_("hive_id", hive_ids).execute()
    response = supabase.table("beekeeper").delete().eq("beekeeper_id", beekeeper_id).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Beekeeper account could not be deleted")
