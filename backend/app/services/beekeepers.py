import os
import re
from typing import Any

from fastapi import HTTPException, UploadFile

from app.auth.auth import execute_read_with_retry, supabase

ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/png", "application/pdf"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_FILE_SIZE = 5 * 1024 * 1024
STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "kyc-documents")


def sanitize_upload_name(filename: str) -> str:
    clean_name = os.path.basename(filename or "document")
    clean_name = re.sub(r"[^A-Za-z0-9._-]", "_", clean_name)
    if not clean_name or clean_name in {".", ".."}:
        clean_name = "document"
    return clean_name


def validate_uploaded_file(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=400, detail="A file is required")
    extension = os.path.splitext(file.filename)[1].lower()
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_UPLOAD_TYPES and extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only JPG, JPEG, PNG, and PDF files are allowed")

    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Each uploaded file must be 5 MB or smaller")


async def save_uploaded_file(file: UploadFile, beekeeper_id: str, field_name: str) -> str:
    validate_uploaded_file(file)
    file_name = sanitize_upload_name(file.filename or "document")
    storage_path = f"{beekeeper_id}/{field_name}/{file_name}"
    file_bytes = await file.read()
    try:
        supabase.storage.from_(STORAGE_BUCKET).upload(
            storage_path,
            file_bytes,
            {
                "content-type": file.content_type or "application/octet-stream",
                "upsert": "true",
            },
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail="Document storage upload failed") from error
    return storage_path


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
        batches_response = execute_read_with_retry(
            lambda: supabase.table("honey_batches").select("status").in_("hive_id", hive_ids).execute()
        )
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
    clean_payload = {
        key: value if value not in (None, "") else None
        for key, value in payload.items()
        if key in {
            "name",
            "phone",
            "location",
            "kyc_status",
            "identity_document_type",
            "identity_document_path",
            "address_document_type",
            "address_document_path",
            "certificate_type",
            "certificate_path",
        }
    }
    if "kyc_status" not in clean_payload:
        clean_payload["kyc_status"] = "pending"
    response = (
        supabase.table("beekeeper")
        .update(clean_payload)
        .eq("beekeeper_id", beekeeper_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=400, detail="Beekeeper profile could not be updated")
    return response.data[0]


async def update_beekeeper_profile_with_uploads(beekeeper_id: str, form_data: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, str] = {}
    for field in ["name", "phone", "location", "kyc_status"]:
        if field in form_data and form_data[field] not in (None, ""):
            payload[field] = str(form_data[field])

    document_map = {
        "identity_document": "identity_document_path",
        "address_document": "address_document_path",
        "certificate": "certificate_path",
    }

    for file_field, db_field in document_map.items():
        file_value = form_data.get(file_field)
        if file_value is not None and getattr(file_value, "filename", ""):
            uploaded_url = await save_uploaded_file(file_value, beekeeper_id, file_field)
            payload[db_field] = uploaded_url

    for file_type_field, db_field in {
        "identity_document_type": "identity_document_type",
        "address_document_type": "address_document_type",
        "certificate_type": "certificate_type",
    }.items():
        if file_type_field in form_data and form_data[file_type_field] not in (None, ""):
            payload[db_field] = str(form_data[file_type_field])

    if not payload:
        raise HTTPException(status_code=400, detail="No profile data received")
    return update_beekeeper_profile(beekeeper_id, payload)


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
