import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.auth.auth import supabase


CERTIFICATE_BUCKET = os.getenv("SUPABASE_CERTIFICATE_BUCKET", "honey-certificates")


def legacy_batch_data_hash(batch: dict[str, Any], hive: dict[str, Any]) -> str:
    snapshot = {
        "batch": {
            key: batch.get(key)
            for key in ("batch_id", "hive_id", "honey_type", "harvest_date", "quantity", "status")
        },
        "hive": hive,
    }
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def batch_data_hash(
    batch: dict[str, Any],
    hive: dict[str, Any],
    certificate: dict[str, Any] | None = None,
) -> str:
    snapshot = {
        "batch": {
            key: batch.get(key)
            for key in ("batch_id", "hive_id", "honey_type", "harvest_date", "quantity", "status")
        },
        "hive": hive,
        "certificate": certificate or {},
    }
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def append_batch_block(
    batch: dict[str, Any],
    hive: dict[str, Any],
    event_type: str,
    certificate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous = (
        supabase.table("blockchain_blocks")
        .select("block_hash")
        .eq("batch_id", batch["batch_id"])
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )
    previous_hash = previous.data[0]["block_hash"] if previous.data else None
    timestamp = datetime.now(timezone.utc).isoformat()
    data_hash = batch_data_hash(batch, hive, certificate)
    block_payload = {
        "batch_id": batch["batch_id"],
        "event_type": event_type,
        "timestamp": timestamp,
        "data_hash": data_hash,
        "previous_hash": previous_hash,
    }
    block_payload["block_hash"] = hashlib.sha256(
        json.dumps(block_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    response = supabase.table("blockchain_blocks").insert(block_payload).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Blockchain event could not be recorded")
    return response.data[0]


def get_stored_certificate(batch_id: str) -> dict[str, Any] | None:
    response = (
        supabase.table("batch_certificates")
        .select("*")
        .eq("batch_id", batch_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def get_batch_verification(batch_id: str) -> dict[str, Any]:
    batch_response = supabase.table("honey_batches").select("*").eq("batch_id", batch_id).limit(1).execute()
    if not batch_response.data:
        raise HTTPException(status_code=404, detail="Honey batch not found")

    blocks_response = (
        supabase.table("blockchain_blocks")
        .select("*")
        .eq("batch_id", batch_id)
        .order("timestamp")
        .execute()
    )
    batch = batch_response.data[0]
    hive_response = supabase.table("hives").select("*").eq("hive_id", batch["hive_id"]).limit(1).execute()
    if not hive_response.data:
        raise HTTPException(status_code=404, detail="Hive not found for honey batch")
    hive = hive_response.data[0]
    beekeeper_response = (
        supabase.table("beekeeper")
        .select("*")
        .eq("beekeeper_id", hive["beekeeper_id"])
        .limit(1)
        .execute()
    )
    if not beekeeper_response.data:
        raise HTTPException(status_code=404, detail="Beekeeper not found for honey batch")
    beekeeper = beekeeper_response.data[0]
    certificate = get_stored_certificate(batch_id)
    blocks = blocks_response.data or []
    data_verified = bool(blocks) and blocks[-1]["data_hash"] in {
        batch_data_hash(batch, hive),
        batch_data_hash(batch, hive, certificate),
        legacy_batch_data_hash(batch, hive),
    }
    chain_verified = True
    previous_hash = None
    for block in blocks:
        if block["previous_hash"] != previous_hash:
            chain_verified = False
        previous_hash = block["block_hash"]

    verification = {
        "data_verified": data_verified,
        "chain_verified": chain_verified,
        "verified": data_verified and chain_verified,
    }
    if not verification["verified"]:
        return {"batch_id": batch_id, "verification": verification}
    return {
        "batch": batch,
        "hive": hive,
        "beekeeper": beekeeper,
        "certificate": certificate,
        "blocks": blocks,
        "verification": verification,
    }


def get_batch_certificate(batch_id: str) -> bytes:
    certificate_record = get_stored_certificate(batch_id)
    if not certificate_record:
        raise HTTPException(status_code=404, detail="Certificate not issued for this batch")
    try:
        return supabase.storage.from_(CERTIFICATE_BUCKET).download(certificate_record["storage_path"])
    except Exception as error:
        raise HTTPException(status_code=502, detail="Stored certificate could not be fetched") from error
